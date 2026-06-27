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
strip = scene.sequence_editor.strips.new_movie(
    name='smoke',
    filepath={str(fixture)!r},
    channel=1,
    frame_start=1,
)
scene.sequence_editor.active_strip = strip
for filter_id in (
    'vse_bright_contrast',
    'vse_color_balance',
    'vse_curves',
    'vse_hue_correct',
    'vse_mask',
    'vse_tonemap',
    'vse_white_balance',
):
    bpy.ops.video_toolkit.apply_filter(filter_id=filter_id)
assert len(strip.modifiers) == 7
bpy.ops.video_toolkit.apply_filter(filter_id='auto_enhance')
assert scene.video_toolkit_last_output
assert os.path.exists(scene.video_toolkit_last_output)
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
