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

result = bpy.ops.video_toolkit.analyze_color(mode='PALETTE')
assert result == {{'FINISHED'}}, result
palette_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Frame Color Identity')]
assert palette_types == ['WHITE_BALANCE', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT', 'TONEMAP'], palette_types
assert 'palette #' in scene.video_toolkit_last_analysis
palette_summary = scene.video_toolkit_last_analysis

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

bpy.ops.wm.save_as_mainfile(filepath={str(blend)!r})
Path({str(report)!r}).write_text(json.dumps({{
    'video': {str(video)!r},
    'selected_strip': strip.name,
    'before_png': {str(before)!r},
    'after_png': {str(after)!r},
    'before': before_stats,
    'after': after_stats,
    'rgb_abs_diff': diff,
    'edited_modifiers': edited,
    'native_modifier_types': types,
    'palette_modifier_types': palette_types,
    'palette_summary': palette_summary,
    'normalizer_keyframes': normalizer_keyframes,
    'timeline_match_reference': {str(reference_video)!r},
    'timeline_match_keyframes': timeline_match_keyframes,
    'color_timeline_gamma_keyframes': color_timeline_gamma_keyframes,
    'color_timeline_gain_keyframes': color_timeline_gain_keyframes,
    'compositor_color_node_types': color_node_types,
    'compositor_all_node_types': all_node_types,
    'compositor_links': len(tree.links),
    'blend': {str(blend)!r},
}}, indent=2), encoding='utf-8')
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
