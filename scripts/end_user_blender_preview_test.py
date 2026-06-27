#!/usr/bin/env python3
"""Exercise the add-on like an end user inside Blender on a real MP4.

The test opens real footage in the Video Sequencer, selects the movie strip,
invokes the same Blender operators the UI buttons call, edits live Blender
modifier values, renders before/after preview frames, and fails if the rendered
preview pixels do not change.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))
DEFAULT_VIDEO = ROOT / "tests" / "fixtures" / "real_user_video.mp4"
DEFAULT_OUTPUT = ROOT / "tests" / "output" / "end_user_preview"
SAMPLE_URLS = (
    "https://filesamples.com/samples/video/mp4/sample_640x360.mp4",
    "https://samplelib.com/lib/preview/mp4/sample-5s.mp4",
    "https://media.w3.org/2010/05/sintel/trailer.mp4",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg and ffprobe are required for the end-user preview test")

    video = _ensure_real_video(args.video)
    _probe(video)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_video = _make_reference_video(video, output_dir / "reference_lighting_match.mp4")

    script = _blender_script(video, reference_video, output_dir)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        subprocess.run(
            [str(BLENDER), "--background", "--factory-startup", "--python", str(script_path)],
            cwd=ROOT,
            check=True,
        )
    finally:
        script_path.unlink(missing_ok=True)
    print(output_dir / "report.json")
    return 0


def _ensure_real_video(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for url in SAMPLE_URLS:
        try:
            print(f"Downloading real MP4 sample: {url}")
            with urllib.request.urlopen(url, timeout=45) as response, path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            if path.stat().st_size > 0:
                return path
        except Exception as exc:  # pragma: no cover - network fallback path
            last_error = exc
            path.unlink(missing_ok=True)
    raise SystemExit(f"Could not download a real MP4 sample: {last_error}")


def _probe(path: Path) -> None:
    subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name",
            "-of",
            "default=nw=1",
            str(path),
        ],
        check=True,
    )


def _make_reference_video(source: Path, output: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(source),
            "-an",
            "-vf",
            "colorchannelmixer=rr=1.08:gg=1.00:bb=0.90,eq=brightness=0.10:contrast=1.05:saturation=1.02",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output


def _blender_script(video: Path, reference_video: Path, output_dir: Path) -> str:
    before = output_dir / "before_live_edit.png"
    after = output_dir / "after_live_edit.png"
    translated = output_dir / "after_native_color_chain.png"
    color_managed = output_dir / "after_color_management_preset.png"
    diagnostic_grade = output_dir / "after_diagnostic_grade.png"
    blend = output_dir / "end_user_preview.blend"
    report = output_dir / "report.json"
    return f"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, {str(ROOT)!r})
import bpy
import video_toolkit
from video_toolkit.compositor import compositor_node_types

video_toolkit.register()
scene = bpy.context.scene
scene.sequence_editor_create()
editor = scene.sequence_editor
strip = editor.strips.new_movie(
    name='END USER SELECTED REAL VIDEO',
    filepath={str(video)!r},
    channel=1,
    frame_start=1,
)
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
editor.active_strip = strip

scene.frame_current = min(strip.frame_final_start + 24, strip.frame_final_end - 1)
scene.frame_start = strip.frame_final_start
scene.frame_end = strip.frame_final_end
scene.render.use_sequencer = True
scene.render.resolution_x = 320
scene.render.resolution_y = 180
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'

def render_preview(path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = list(image.pixels)
    channels = len(pixels) // 4
    stats = {{
        'r': sum(pixels[0::4]) / channels,
        'g': sum(pixels[1::4]) / channels,
        'b': sum(pixels[2::4]) / channels,
        'luma': sum(0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2] for i in range(0, len(pixels), 4)) / channels,
        'pixels': channels,
    }}
    bpy.data.images.remove(image)
    return stats

before_stats = render_preview({str(before)!r})

result = bpy.ops.video_toolkit.apply_filter(filter_id='auto_enhance')
assert result == {{'FINISHED'}}, result
assert editor.active_strip == strip
assert strip.select

edited = []
for modifier in strip.modifiers:
    if modifier.name.startswith('VTK Auto Enhance') and modifier.type == 'BRIGHT_CONTRAST':
        modifier.bright = 0.08
        modifier.contrast = 18.0
        edited.append(modifier.name)
    elif modifier.name.startswith('VTK Auto Enhance') and modifier.type == 'COLOR_BALANCE':
        modifier.color_balance.gamma = (1.14, 1.10, 1.06)
        modifier.color_balance.gain = (1.10, 1.08, 1.04)
        modifier.color_multiply = 1.06
        edited.append(modifier.name)
assert edited, 'No live modifiers were edited'

after_stats = render_preview({str(after)!r})
diff = abs(after_stats['r'] - before_stats['r']) + abs(after_stats['g'] - before_stats['g']) + abs(after_stats['b'] - before_stats['b'])
assert diff > 0.015, f'Live edit did not visibly change preview pixels: {{diff}}'

result = bpy.ops.video_toolkit.apply_filter(filter_id='native_all_color_tools')
assert result == {{'FINISHED'}}, result
types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK ')]
for required in ['BRIGHT_CONTRAST', 'COLOR_BALANCE', 'TONEMAP', 'WHITE_BALANCE', 'CURVES', 'HUE_CORRECT', 'MASK']:
    assert required in types, required
for filter_id in ['luma_s_curve', 'green_cast_repair', 'red_gamma_trim']:
    result = bpy.ops.video_toolkit.apply_filter(filter_id=filter_id)
    assert result == {{'FINISHED'}}, result
primary_correction_types = [
    modifier.type
    for modifier in strip.modifiers
    if (
        modifier.name.startswith('VTK Luma S-Curve')
        or modifier.name.startswith('VTK Green Cast Repair')
        or modifier.name.startswith('VTK Red Gamma Trim')
    )
]
assert {{'CURVES', 'COLOR_BALANCE', 'WHITE_BALANCE'}}.issubset(set(primary_correction_types))

scene.video_toolkit_ffmpeg_chain = (
    'eq=contrast=1.12:saturation=1.08:gamma=1.02,'
    'colorbalance=rs=0.05:bm=0.03:bh=-0.04:pl=1,'
    'colortemperature=temperature=5600:mix=0.55'
)
result = bpy.ops.video_toolkit.translate_ffmpeg_chain()
assert result == {{'FINISHED'}}, result
assert 'translated eq, colorbalance, colortemperature' in scene.video_toolkit_last_translation
translated_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Translated Color Chain')]
for required in ['BRIGHT_CONTRAST', 'COLOR_BALANCE', 'HUE_CORRECT', 'TONEMAP', 'WHITE_BALANCE']:
    assert required in translated_types, required
translated_stats = render_preview({str(translated)!r})
translated_diff = (
    abs(translated_stats['r'] - before_stats['r'])
    + abs(translated_stats['g'] - before_stats['g'])
    + abs(translated_stats['b'] - before_stats['b'])
)
assert translated_diff > 0.015, f'Translated live color chain did not visibly change preview pixels: {{translated_diff}}'

result = bpy.ops.video_toolkit.apply_color_management_preset(preset_id='VIEW_CURVE_CONTRAST')
assert result == {{'FINISHED'}}, result
assert scene.view_settings.use_curve_mapping
assert 'View Curve Contrast' in scene.video_toolkit_last_color_management
color_managed_stats = render_preview({str(color_managed)!r})
color_management_diff = (
    abs(color_managed_stats['r'] - translated_stats['r'])
    + abs(color_managed_stats['g'] - translated_stats['g'])
    + abs(color_managed_stats['b'] - translated_stats['b'])
)
assert color_management_diff > 0.001, f'Color Management preset did not visibly change preview pixels: {{color_management_diff}}'

result = bpy.ops.video_toolkit.analyze_color(mode='PALETTE')
assert result == {{'FINISHED'}}, result
palette_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Frame Color Identity')]
assert palette_types == ['WHITE_BALANCE', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT', 'TONEMAP'], palette_types
assert 'palette #' in scene.video_toolkit_last_analysis
palette_summary = scene.video_toolkit_last_analysis
result = bpy.ops.video_toolkit.color_diagnostics()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_diagnostics.startswith('diagnosis')
diagnostics_text_name = scene.video_toolkit_last_diagnostics_text
assert diagnostics_text_name in bpy.data.texts
diagnostics_report = bpy.data.texts[diagnostics_text_name].as_string()
assert 'Video Toolkit Color Diagnostics' in diagnostics_report
assert 'Suggested native Blender tools' in diagnostics_report
result = bpy.ops.video_toolkit.apply_diagnostic_grade()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_diagnostic_grade.startswith('diagnostic grade')
diagnostic_grade_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Diagnostic Grade')]
assert diagnostic_grade_types, 'No diagnostic grade modifiers were added'
diagnostic_grade_stats = render_preview({str(diagnostic_grade)!r})
diagnostic_grade_diff = (
    abs(diagnostic_grade_stats['r'] - color_managed_stats['r'])
    + abs(diagnostic_grade_stats['g'] - color_managed_stats['g'])
    + abs(diagnostic_grade_stats['b'] - color_managed_stats['b'])
)
assert diagnostic_grade_diff > 0.001, f'Diagnostic grade did not visibly change preview pixels: {{diagnostic_grade_diff}}'

result = bpy.ops.video_toolkit.normalize_lighting()
assert result == {{'FINISHED'}}, result
normalizer = next(modifier for modifier in strip.modifiers if modifier.name.startswith('VTK Live Flicker Normalizer'))
def action_keyframe_count(action, data_path):
    if hasattr(action, 'fcurves'):
        return sum(len(fcurve.keyframe_points) for fcurve in action.fcurves if fcurve.data_path == data_path)
    total = 0
    for layer in action.layers:
        for action_strip in layer.strips:
            for channelbag in action_strip.channelbags:
                total += sum(len(fcurve.keyframe_points) for fcurve in channelbag.fcurves if fcurve.data_path == data_path)
    return total
assert scene.animation_data is not None
assert scene.animation_data.action is not None
normalizer_keyframes = action_keyframe_count(scene.animation_data.action, normalizer.path_from_id('bright'))
assert normalizer_keyframes >= 2, normalizer_keyframes

reference_strip = editor.strips.new_movie(
    name='END USER REFERENCE LIGHTING VIDEO',
    filepath={str(reference_video)!r},
    channel=2,
    frame_start=1,
)
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
reference_strip.select = True
editor.active_strip = strip
result = bpy.ops.video_toolkit.match_lighting_timeline()
assert result == {{'FINISHED'}}, result
timeline_match = next(modifier for modifier in strip.modifiers if modifier.name.startswith('VTK Live Timeline Match'))
timeline_match_keyframes = action_keyframe_count(scene.animation_data.action, timeline_match.path_from_id('bright'))
assert timeline_match_keyframes >= 2, timeline_match_keyframes

result = bpy.ops.video_toolkit.match_color_timeline()
assert result == {{'FINISHED'}}, result
color_timeline_match = next(modifier for modifier in strip.modifiers if modifier.name.startswith('VTK Live Color Timeline Match'))
color_timeline_gamma_keyframes = action_keyframe_count(scene.animation_data.action, color_timeline_match.color_balance.path_from_id('gamma'))
color_timeline_gain_keyframes = action_keyframe_count(scene.animation_data.action, color_timeline_match.color_balance.path_from_id('gain'))
assert color_timeline_gamma_keyframes >= 6, color_timeline_gamma_keyframes
assert color_timeline_gain_keyframes >= 6, color_timeline_gain_keyframes

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='COLOR')
assert result == {{'FINISHED'}}, result
if hasattr(scene, 'compositing_node_group'):
    tree = scene.compositing_node_group
else:
    tree = scene.node_tree
assert tree is not None, 'No compositor node tree was created'
color_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeExposure',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeColorCorrection',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueSat',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in color_node_types, required
assert len(tree.links) >= 12, f'Expected linked compositor color graph, got {{len(tree.links)}} links'

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='RESTORATION')
assert result == {{'FINISHED'}}, result
all_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
for required in [
    'CompositorNodeStabilize',
    'CompositorNodeMovieDistortion',
    'CompositorNodeDenoise',
    'CompositorNodeDespeckle',
    'CompositorNodeBilateralblur',
    'CompositorNodeAntiAliasing',
]:
    assert required in all_node_types, required

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='NODE_LIBRARY')
assert result == {{'FINISHED'}}, result
library_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Library ')
]
for required in [
    'CompositorNodeConvertToDisplay',
    'CompositorNodeRGBToBW',
    'CompositorNodeNormalize',
    'CompositorNodeGlare',
    'CompositorNodeLensdist',
    'CompositorNodeCornerPin',
    'CompositorNodeTransform',
    'CompositorNodeChannelMatte',
    'CompositorNodeLumaMatte',
    'CompositorNodeSequencerStripInfo',
    'CompositorNodeConvolve',
    'CompositorNodeOutputFile',
]:
    assert required in library_node_types, required
assert len(set(library_node_types)) == len(compositor_node_types())
library_summary = scene.video_toolkit_last_compositor_nodes
assert library_summary.startswith(str(len(compositor_node_types())) + ' nodes:')

bpy.ops.wm.save_as_mainfile(filepath={str(blend)!r})
Path({str(report)!r}).write_text(json.dumps({{
    'video': {str(video)!r},
    'selected_strip': strip.name,
    'before_png': {str(before)!r},
    'after_png': {str(after)!r},
    'translated_png': {str(translated)!r},
    'color_managed_png': {str(color_managed)!r},
    'diagnostic_grade_png': {str(diagnostic_grade)!r},
    'before': before_stats,
    'after': after_stats,
    'translated': translated_stats,
    'color_managed': color_managed_stats,
    'diagnostic_grade': diagnostic_grade_stats,
    'rgb_abs_diff': diff,
    'translated_rgb_abs_diff': translated_diff,
    'color_management_rgb_abs_diff': color_management_diff,
    'diagnostic_grade_rgb_abs_diff': diagnostic_grade_diff,
    'edited_modifiers': edited,
    'native_modifier_types': types,
    'translated_chain_summary': scene.video_toolkit_last_translation,
    'translated_modifier_types': translated_types,
    'color_management_summary': scene.video_toolkit_last_color_management,
    'palette_modifier_types': palette_types,
    'palette_summary': palette_summary,
    'diagnostics_summary': scene.video_toolkit_last_diagnostics,
    'diagnostics_text': diagnostics_text_name,
    'diagnostics_report_excerpt': diagnostics_report.splitlines()[:12],
    'diagnostic_grade_summary': scene.video_toolkit_last_diagnostic_grade,
    'diagnostic_grade_modifier_types': diagnostic_grade_types,
    'primary_correction_modifier_types': primary_correction_types,
    'normalizer_keyframes': normalizer_keyframes,
    'timeline_match_reference': {str(reference_video)!r},
    'timeline_match_keyframes': timeline_match_keyframes,
    'color_timeline_gamma_keyframes': color_timeline_gamma_keyframes,
    'color_timeline_gain_keyframes': color_timeline_gain_keyframes,
    'compositor_color_node_types': color_node_types,
    'compositor_all_node_types': all_node_types,
    'compositor_library_node_types': library_node_types,
    'compositor_library_summary': library_summary,
    'compositor_links': len(tree.links),
    'blend': {str(blend)!r},
}}, indent=2), encoding='utf-8')
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
