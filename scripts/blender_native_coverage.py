#!/usr/bin/env python3
"""Verify Video Toolkit covers Blender's native VSE color modifier surface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))
REQUIRED_MODIFIERS = {
    "BRIGHT_CONTRAST",
    "COLOR_BALANCE",
    "CURVES",
    "HUE_CORRECT",
    "MASK",
    "TONEMAP",
    "WHITE_BALANCE",
}


def main() -> int:
    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    script = f"""
import json
import os
import sys
sys.path.insert(0, {str(ROOT)!r})
from video_toolkit.catalog import blender_modifier_tools
import bpy

scene = bpy.context.scene
scene.sequence_editor_create()
strip = scene.sequence_editor.strips.new_movie(
    name='coverage',
    filepath=os.path.abspath('tests/fixtures/api_probe.mp4'),
    channel=1,
    frame_start=1,
)
available = {{}}
for modifier_type in {sorted(REQUIRED_MODIFIERS)!r}:
    modifier = strip.modifiers.new(name=modifier_type, type=modifier_type)
    available[modifier_type] = sorted(
        prop.identifier for prop in modifier.bl_rna.properties
        if prop.identifier not in {{'rna_type', 'name'}}
    )
covered = sorted({{
    modifier_type
    for tool in blender_modifier_tools()
    for modifier_type in tool.blender_modifiers
}})
scene_props = sorted(
    prop.identifier for prop in scene.view_settings.bl_rna.properties
    if prop.identifier != 'rna_type'
)
sequencer_color_props = []
if hasattr(scene, 'sequencer_colorspace_settings'):
    sequencer_color_props = sorted(
        prop.identifier for prop in scene.sequencer_colorspace_settings.bl_rna.properties
        if prop.identifier != 'rna_type'
    )
print(json.dumps({{
    'available': available,
    'covered': covered,
    'scene_view_settings': scene_props,
    'sequencer_colorspace_settings': sequencer_color_props,
}}, indent=2))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = Path(handle.name)
    try:
        result = subprocess.run(
            [str(BLENDER), "--background", "--factory-startup", "--python", str(path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        path.unlink(missing_ok=True)
    payload = _extract_json(result.stdout)
    missing = REQUIRED_MODIFIERS - set(payload["covered"])
    if missing:
        raise SystemExit(f"Missing Blender VSE color modifiers: {sorted(missing)}")
    if "gamma" not in payload["scene_view_settings"] or "exposure" not in payload["scene_view_settings"]:
        raise SystemExit("Blender Color Management exposure/gamma controls were not visible")
    if "name" not in payload["sequencer_colorspace_settings"]:
        raise SystemExit("Blender Sequencer input color-space control was not visible")
    print(json.dumps(payload, indent=2))
    return 0


def _extract_json(stdout: str) -> dict:
    start = stdout.find("{")
    end = stdout.rfind("}") + 1
    if start < 0 or end <= start:
        raise SystemExit(f"Could not find JSON in Blender output:\n{stdout}")
    return json.loads(stdout[start:end])


if __name__ == "__main__":
    raise SystemExit(main())

