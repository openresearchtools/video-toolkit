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
bpy.ops.video_toolkit.apply_filter(filter_id='neutral_grade')
assert any(m.name.startswith('VTK Neutral Grade') for m in strip.modifiers)
assert any(m.name.startswith('VTK Neutral Grade') for m in second_strip.modifiers)
scene.video_toolkit_apply_target = 'ACTIVE'
bpy.ops.video_toolkit.analyze_color(mode='AUTO')
assert len(strip.modifiers) >= 5
bpy.ops.video_toolkit.analyze_color(mode='PALETTE')
assert 'palette #' in scene.video_toolkit_last_analysis
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
assert len(strip.modifiers) >= 77
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
bpy.ops.video_toolkit.apply_filter(filter_id='deflicker_normalize')
assert scene.video_toolkit_last_output
assert os.path.exists(scene.video_toolkit_last_output)
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
