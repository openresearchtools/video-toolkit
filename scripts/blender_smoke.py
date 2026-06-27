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
assert len(strip.modifiers) >= 55
high_curve = next(m for m in strip.modifiers if m.name.startswith('VTK High Contrast Curve') and m.type == 'CURVES')
high_points = [tuple(p.location[:]) for p in high_curve.curve_mapping.curves[0].points]
assert high_points[1][1] < high_points[1][0]
assert high_points[-2][1] > high_points[-2][0]
saturation = next(m for m in strip.modifiers if m.name.startswith('VTK Saturation Boost') and m.type == 'HUE_CORRECT')
assert saturation.curve_mapping.curves[1].points[0].location[1] > 0.5
monochrome = next(m for m in strip.modifiers if m.name.startswith('VTK Monochrome') and m.type == 'HUE_CORRECT')
assert monochrome.curve_mapping.curves[1].points[0].location[1] == 0.0
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
bpy.ops.video_toolkit.apply_filter(filter_id='deflicker_normalize')
assert scene.video_toolkit_last_output
assert os.path.exists(scene.video_toolkit_last_output)
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
