#!/usr/bin/env python3
"""Verify Video Toolkit covers Blender's native VSE and compositor video surface."""

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
from video_toolkit.compositor import compositor_node_types
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
if hasattr(scene, 'compositing_node_group'):
    tree = scene.compositing_node_group
    if tree is None:
        tree = bpy.data.node_groups.new('VTK Coverage Compositor', 'CompositorNodeTree')
        scene.compositing_node_group = tree
else:
    scene.use_nodes = True
    tree = scene.node_tree
available_compositor_nodes = {{}}
for node_type in compositor_node_types():
    try:
        node = tree.nodes.new(node_type)
        available_compositor_nodes[node_type] = {{
            'inputs': [socket.name for socket in node.inputs],
            'outputs': [socket.name for socket in node.outputs],
        }}
        tree.nodes.remove(node)
    except Exception as exc:
        available_compositor_nodes[node_type] = {{'error': str(exc)}}
print(json.dumps({{
    'available': available,
    'covered': covered,
    'available_compositor_nodes': available_compositor_nodes,
    'covered_compositor_nodes': list(compositor_node_types()),
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
    failed_nodes = {
        node_type: node_info["error"]
        for node_type, node_info in payload["available_compositor_nodes"].items()
        if "error" in node_info
    }
    if failed_nodes:
        raise SystemExit(f"Missing Blender compositor video nodes: {json.dumps(failed_nodes, indent=2)}")
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
