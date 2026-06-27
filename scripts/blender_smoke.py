#!/usr/bin/env python3
"""Run a headless Blender smoke test against the local add-on."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))


def main() -> int:
    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    fixture = ROOT / "tests" / "fixtures" / "blender_smoke.mp4"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=96x64:rate=12:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(fixture),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    script = _smoke_script(fixture)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        smoke_path = Path(handle.name)
    try:
        subprocess.run(
            [str(BLENDER), "--background", "--factory-startup", "--python", str(smoke_path)],
            cwd=ROOT,
            check=True,
        )
    finally:
        smoke_path.unlink(missing_ok=True)
    return 0


def _smoke_script(fixture: Path) -> str:
    return f"""
import os
import sys
sys.path.insert(0, {str(ROOT)!r})
import bpy
import video_toolkit
from video_toolkit.compositor import compositor_node_types

video_toolkit.register()
scene = bpy.context.scene
scene.sequence_editor_create()
scene.video_toolkit_output_dir = {str((ROOT / 'tests' / 'output'))!r}
scene.video_toolkit_crf = 28
scene.video_toolkit_preset = 'veryfast'
scene.video_toolkit_analysis_samples = 12
strip = scene.sequence_editor.strips.new_movie(
    name='smoke',
    filepath={str(fixture)!r},
    channel=1,
    frame_start=1,
)
second_strip = scene.sequence_editor.strips.new_movie(
    name='smoke second selected',
    filepath={str(fixture)!r},
    channel=2,
    frame_start=1,
)
for candidate in scene.sequence_editor.strips_all:
    candidate.select = False
strip.select = True
second_strip.select = True
scene.sequence_editor.active_strip = strip
scene.video_toolkit_apply_target = 'SELECTED'
bpy.ops.video_toolkit.apply_color_management_preset(preset_id='STANDARD_VIDEO')
assert scene.view_settings.view_transform == 'Standard'
assert scene.view_settings.gamma == 1.0
bpy.ops.video_toolkit.apply_color_management_preset(preset_id='AGX_PUNCH')
assert scene.view_settings.view_transform in {{'AgX', 'Khronos PBR Neutral', 'Standard'}}
assert 'AgX Punch' in scene.video_toolkit_last_color_management
bpy.ops.video_toolkit.apply_color_management_preset(preset_id='VIEW_CURVE_CONTRAST')
assert scene.view_settings.use_curve_mapping
view_curve_points = [tuple(point.location[:]) for point in scene.view_settings.curve_mapping.curves[0].points]
assert view_curve_points[1][1] < view_curve_points[1][0]
assert view_curve_points[-2][1] > view_curve_points[-2][0]
result = bpy.ops.video_toolkit.apply_sampled_color_management()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_sampled_color_management.startswith('sampled color management')
assert scene.view_settings.use_curve_mapping
assert scene.view_settings.view_transform in {{'AgX', 'Khronos PBR Neutral', 'Filmic', 'Standard'}}
assert 0.88 <= scene.view_settings.gamma <= 1.16
sampled_view_curve_points = [tuple(point.location[:]) for point in scene.view_settings.curve_mapping.curves[0].points]
assert len(sampled_view_curve_points) >= 5
assert sampled_view_curve_points[2][0] == 0.5
bpy.ops.video_toolkit.apply_filter(filter_id='neutral_grade')
assert any(m.name.startswith('VTK Neutral Grade') for m in strip.modifiers)
assert any(m.name.startswith('VTK Neutral Grade') for m in second_strip.modifiers)
scene.video_toolkit_apply_target = 'ACTIVE'
bpy.ops.video_toolkit.analyze_color(mode='AUTO')
assert len(strip.modifiers) >= 5
bpy.ops.video_toolkit.analyze_color(mode='PALETTE')
assert 'palette #' in scene.video_toolkit_last_analysis
bpy.ops.video_toolkit.color_diagnostics()
assert scene.video_toolkit_last_diagnostics.startswith('diagnosis')
assert scene.video_toolkit_last_diagnostics_text in bpy.data.texts
assert 'Suggested native Blender tools' in bpy.data.texts[scene.video_toolkit_last_diagnostics_text].as_string()
scene.video_toolkit_apply_target = 'SELECTED'
bpy.ops.video_toolkit.apply_diagnostic_grade()
assert scene.video_toolkit_last_diagnostic_grade.startswith('diagnostic grade')
assert any(m.name.startswith('VTK Diagnostic Grade') for m in strip.modifiers)
assert any(m.name.startswith('VTK Diagnostic Grade') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_white_balance()
assert scene.video_toolkit_last_sampled_white_balance.startswith('sampled white balance')
sampled_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled White Balance')]
assert sampled_types == ['WHITE_BALANCE', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'CURVES', 'HUE_CORRECT'], sampled_types
assert any(m.name.startswith('VTK Sampled White Balance') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_levels_gamma()
assert scene.video_toolkit_last_sampled_levels_gamma.startswith('sampled levels/gamma')
levels_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled Levels Gamma')]
assert levels_types == ['CURVES', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'TONEMAP', 'HUE_CORRECT'], levels_types
assert any(m.name.startswith('VTK Sampled Levels Gamma') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_hue_chroma()
assert scene.video_toolkit_last_sampled_hue_chroma.startswith('sampled hue/chroma')
hue_chroma_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled Hue Chroma')]
assert hue_chroma_types == ['HUE_CORRECT', 'COLOR_BALANCE', 'CURVES'], hue_chroma_types
assert any(m.name.startswith('VTK Sampled Hue Chroma') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_pro_grade()
assert scene.video_toolkit_last_sampled_pro_grade.startswith('sampled pro grade')
pro_grade_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled Pro Grade')]
assert pro_grade_types == [
    'WHITE_BALANCE', 'COLOR_BALANCE', 'CURVES', 'COLOR_BALANCE', 'BRIGHT_CONTRAST',
    'TONEMAP', 'HUE_CORRECT', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT'
], pro_grade_types
assert any(m.name.startswith('VTK Sampled Pro Grade') for m in second_strip.modifiers)
scene.video_toolkit_apply_target = 'ACTIVE'
bpy.ops.video_toolkit.normalize_lighting()
normalizer = next(m for m in strip.modifiers if m.name.startswith('VTK Live Flicker Normalizer'))
def action_keyframe_count(action, data_path):
    if hasattr(action, 'fcurves'):
        return sum(len(fcurve.keyframe_points) for fcurve in action.fcurves if fcurve.data_path == data_path)
    total = 0
    for layer in action.layers:
        for action_strip in layer.strips:
            for channelbag in action_strip.channelbags:
                total += sum(len(fcurve.keyframe_points) for fcurve in channelbag.fcurves if fcurve.data_path == data_path)
    return total
normalizer_path = normalizer.path_from_id('bright')
assert scene.animation_data is not None
assert scene.animation_data.action is not None
assert action_keyframe_count(scene.animation_data.action, normalizer_path) >= 2
bpy.ops.video_toolkit.match_lighting_timeline()
timeline_match = next(m for m in strip.modifiers if m.name.startswith('VTK Live Timeline Match'))
timeline_match_path = timeline_match.path_from_id('bright')
assert action_keyframe_count(scene.animation_data.action, timeline_match_path) >= 2
bpy.ops.video_toolkit.match_color_timeline()
color_timeline_match = next(m for m in strip.modifiers if m.name.startswith('VTK Live Color Timeline Match'))
color_gamma_path = color_timeline_match.color_balance.path_from_id('gamma')
color_gain_path = color_timeline_match.color_balance.path_from_id('gain')
assert action_keyframe_count(scene.animation_data.action, color_gamma_path) >= 6
assert action_keyframe_count(scene.animation_data.action, color_gain_path) >= 6
scene.video_toolkit_ffmpeg_chain = (
    'colorspace=iall=bt709:all=bt709:irange=tv:range=pc,'
    'normalize=smoothing=18:independence=0.65:strength=0.55,'
    'colorlevels=rimin=0.02:rimax=0.98,'
    'colorcorrect=rl=0.05:bl=-0.04:rh=0.03:bh=-0.02:saturation=1.06,'
    'colorcontrast=rc=0.12:gm=-0.05:by=0.08:rcw=0.5:gmw=0.4:byw=0.5:pl=1,'
    'selectivecolor=reds=0.10 -0.04 -0.02 0.00:blues=-0.04 0.02 0.10 0.03:whites=0.02 0.00 -0.08 0.01,'
    'monochrome=cb=0.05:cr=-0.04:high=0.1,'
    'colorize=hue=35:saturation=0.25:lightness=0.55:mix=0.85,'
    'vibrance=intensity=0.4,'
    'exposure=exposure=0.25:black=0.02,'
    'histeq=strength=0.25:intensity=0.22:antibanding=1'
)
bpy.ops.video_toolkit.translate_ffmpeg_chain()
assert 'translated colorspace, normalize, colorlevels, colorcorrect, colorcontrast, selectivecolor, monochrome, colorize, vibrance, exposure, histeq' in scene.video_toolkit_last_translation
assert 'color management:' in scene.video_toolkit_last_translation
assert scene.sequencer_colorspace_settings.name in {'sRGB', 'Gamma 2.2 Encoded Rec.709', 'Gamma 2.4 Encoded Rec.709', 'Rec.1886', 'Linear Rec.709'}
translated_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Translated Color Chain')]
assert {{'CURVES', 'HUE_CORRECT', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'TONEMAP', 'WHITE_BALANCE'}}.issubset(set(translated_types))
scene.video_toolkit_ffmpeg_chain = 'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=full,setrange=limited'
bpy.ops.video_toolkit.translate_ffmpeg_chain()
assert 'translated setparams, setrange into 0 live modifier(s)' in scene.video_toolkit_last_translation
assert 'color management:' in scene.video_toolkit_last_translation
for filter_id in (
    'live_pro_color_stack',
    'auto_enhance',
    'neutral_grade',
    'punchy_color',
    'soft_contrast',
    'exposure_lift',
    'gamma_brighten',
    'gamma_deepen',
    'warm_balance',
    'cool_balance',
    'saturation_boost',
    'saturation_reduce',
    'monochrome',
    'faded_film',
    'high_contrast_curve',
    'medium_contrast_curve',
    'levels_expand',
    'levels_soft_clamp',
    'shadow_highlight_balance',
    'vibrance',
    'skin_safe_vibrance',
    'exposure_protect',
    'temperature_warm',
    'temperature_cool',
    'legal_range_clamp',
    'hdr_tone_compress',
    'black_point_cleanup',
    'white_point_recovery',
    'luma_s_curve',
    'red_gamma_trim',
    'green_gamma_trim',
    'blue_gamma_trim',
    'magenta_green_tint',
    'green_cast_repair',
    'shadow_cool_tint',
    'highlight_warm_tint',
    'skin_tone_isolation',
    'native_all_color_tools',
    'vse_bright_contrast',
    'vse_color_balance',
    'vse_curves',
    'vse_hue_correct',
    'vse_mask',
    'vse_tonemap',
    'vse_white_balance',
):
    bpy.ops.video_toolkit.apply_filter(filter_id=filter_id)
assert len(strip.modifiers) >= 99
high_curve = next(m for m in strip.modifiers if m.name.startswith('VTK High Contrast Curve') and m.type == 'CURVES')
high_points = [tuple(p.location[:]) for p in high_curve.curve_mapping.curves[0].points]
assert high_points[1][1] < high_points[1][0]
assert high_points[-2][1] > high_points[-2][0]
saturation = next(m for m in strip.modifiers if m.name.startswith('VTK Saturation Boost') and m.type == 'HUE_CORRECT')
assert saturation.curve_mapping.curves[1].points[0].location[1] > 0.5
monochrome = next(m for m in strip.modifiers if m.name.startswith('VTK Monochrome') and m.type == 'HUE_CORRECT')
assert monochrome.curve_mapping.curves[1].points[0].location[1] == 0.0
levels = next(m for m in strip.modifiers if m.name.startswith('VTK Levels Expand') and m.type == 'CURVES')
assert len(levels.curve_mapping.curves[1].points) >= 4
vibrance = next(m for m in strip.modifiers if m.name.startswith('VTK Vibrance') and m.type == 'HUE_CORRECT')
assert vibrance.curve_mapping.curves[1].points[0].location[1] > 0.5
temperature = next(m for m in strip.modifiers if m.name.startswith('VTK Temperature Warm') and m.type == 'WHITE_BALANCE')
assert temperature.white_value[0] > temperature.white_value[2]
red_trim = next(m for m in strip.modifiers if m.name.startswith('VTK Red Gamma Trim') and m.type == 'COLOR_BALANCE')
assert red_trim.color_balance.gamma[0] > red_trim.color_balance.gamma[1]
green_repair = next(m for m in strip.modifiers if m.name.startswith('VTK Green Cast Repair') and m.type == 'WHITE_BALANCE')
assert green_repair.white_value[1] < green_repair.white_value[0]
white_recovery = next(m for m in strip.modifiers if m.name.startswith('VTK White Point Recovery') and m.type == 'TONEMAP')
assert white_recovery.intensity > 0.0
scene.sequence_editor.active_strip = strip
for candidate in scene.sequence_editor.strips_all:
    candidate.select = False
strip.select = True
scene.video_toolkit_apply_target = 'ADJUSTMENT'
bpy.ops.video_toolkit.apply_filter(filter_id='auto_enhance')
adjustment = scene.sequence_editor.active_strip
assert adjustment.type == 'ADJUSTMENT'
assert adjustment.channel > strip.channel
assert any(m.name.startswith('VTK Auto Enhance') for m in adjustment.modifiers)
scene.sequence_editor.active_strip = strip
for candidate in scene.sequence_editor.strips_all:
    candidate.select = False
strip.select = True
scene.video_toolkit_apply_target = 'ACTIVE'
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='COLOR')
tree = scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree
node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
assert 'CompositorNodeMovieClip' in node_types
assert 'CompositorNodeColorCorrection' in node_types
assert 'CompositorNodeTonemap' in node_types
assert len(tree.links) >= 12
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='RESTORATION')
node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
assert 'CompositorNodeStabilize' in node_types
assert 'CompositorNodeMovieDistortion' in node_types
assert 'CompositorNodeDenoise' in node_types
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='NODE_LIBRARY')
library_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Library ')
]
for required in compositor_node_types():
    assert required in library_node_types, required
assert len(set(library_node_types)) == len(compositor_node_types())
assert scene.video_toolkit_last_compositor_nodes.startswith(str(len(compositor_node_types())) + ' nodes:')
bpy.ops.video_toolkit.apply_filter(filter_id='deflicker_normalize')
assert scene.video_toolkit_last_output
assert os.path.exists(scene.video_toolkit_last_output)
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
