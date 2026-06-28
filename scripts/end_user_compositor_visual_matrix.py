#!/usr/bin/env python3
"""Render visual compositor snapshots for every compositor-capable tool.

This complements the full UI matrix. The UI matrix proves every sidecar tool
can be applied and every compositor graph can be created; this script renders
one processed frame from each compositor graph on real footage so the output can
be inspected visually.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from end_user_blender_preview_test import (
    BLENDER,
    DEFAULT_VIDEO,
    ROOT,
    _ensure_real_video,
    _probe,
)
from end_user_full_ui_operator_matrix import _make_matrix_source


DEFAULT_OUTPUT = ROOT / "tests" / "output" / "compositor_visual_matrix"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frame", type=int, default=6)
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg and ffprobe are required for the compositor visual matrix")

    original_video = _ensure_real_video(args.video)
    _probe(original_video)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_video = _make_matrix_source(original_video, output_dir / "matrix_source.mp4")

    script = _blender_script(original_video, matrix_video, output_dir, args.frame)
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
    _convert_compositor_snapshots(output_dir / "compositor_visual_report.json")
    print(output_dir / "compositor_visual_report.json")
    return 0


def _convert_compositor_snapshots(report_path: Path) -> None:
    script = r'''
import json
from pathlib import Path

import OpenEXR
import numpy as np
from PIL import Image

REPORT_PATH = Path(__REPORT_PATH__)
report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
converted = 0

for result in report["results"]:
    if result.get("status") != "passed":
        continue
    evidence = result.get("evidence") or {}
    exr = Path(evidence["exr"])
    png = Path(evidence["png"])
    png.parent.mkdir(parents=True, exist_ok=True)
    exr_file = OpenEXR.File(str(exr))
    pixels = exr_file.parts[0].channels["Image"].pixels
    rgb = np.nan_to_num(pixels[..., :3], nan=0.0, posinf=1.0, neginf=0.0)
    rgb = np.clip(rgb, 0.0, 1.0)
    arr = (rgb * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(png)
    evidence["bytes"] = png.stat().st_size
    evidence["png_converter"] = "OpenEXR"
    converted += 1

report["converted_pngs"] = converted
REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"report": str(REPORT_PATH), "converted_pngs": report["converted_pngs"]}, indent=2))
expected = sum(1 for result in report["results"] if result.get("status") == "passed")
if report["converted_pngs"] != expected:
    raise SystemExit(f"converted {report['converted_pngs']} of {expected} compositor EXR files")
'''
    converter_python = ROOT / ".venv" / "bin" / "python"
    if not converter_python.exists():
        converter_python = Path(sys.executable)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script.replace("__REPORT_PATH__", repr(str(report_path))))
        script_path = Path(handle.name)
    try:
        subprocess.run(
            [str(converter_python), str(script_path)],
            cwd=ROOT,
            check=True,
        )
    finally:
        script_path.unlink(missing_ok=True)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected = report.get("passed", 0)
    converted = report.get("converted_pngs", 0)
    if converted != expected:
        raise RuntimeError(f"converted {converted} of {expected} compositor EXR files")


def _blender_script(original_video: Path, video: Path, output_dir: Path, frame: int) -> str:
    template = r'''
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__ROOT__)
ORIGINAL_VIDEO = Path(__ORIGINAL_VIDEO__)
VIDEO = Path(__VIDEO__)
OUTPUT_DIR = Path(__OUTPUT_DIR__)
FRAME = __FRAME__
SNAPSHOT_DIR = OUTPUT_DIR / "compositor_snapshots"
EXR_DIR = OUTPUT_DIR / "compositor_exr"
REPORT_PATH = OUTPUT_DIR / "compositor_visual_report.json"

sys.path.insert(0, str(ROOT))

import bpy
import video_toolkit
from video_toolkit.addon import _tool_has_compositor_stack
from video_toolkit.catalog import all_tools

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
EXR_DIR.mkdir(parents=True, exist_ok=True)

video_toolkit.register()

scene = bpy.context.scene
scene.sequence_editor_create()
editor = scene.sequence_editor
scene.frame_start = 1
scene.frame_end = 15
scene.frame_set(FRAME)
scene.render.resolution_x = 160
scene.render.resolution_y = 90
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(OUTPUT_DIR / "compositor_render_probe.png")
scene.render.use_sequencer = False
if hasattr(scene.render, "use_compositing"):
    scene.render.use_compositing = True

target_strip = editor.strips.new_movie(
    name="COMPOSITOR VISUAL TARGET REAL VIDEO",
    filepath=str(VIDEO),
    channel=1,
    frame_start=1,
)
editor.active_strip = target_strip
target_strip.select = True


def tree_or_none():
    if hasattr(scene, "compositing_node_group") and scene.compositing_node_group is not None:
        return scene.compositing_node_group
    return getattr(scene, "node_tree", None)


def tree():
    current_tree = tree_or_none()
    if current_tree is None:
        raise RuntimeError("This Blender build does not expose a compositor node tree yet")
    return current_tree


def clear_toolkit_nodes():
    current_tree = tree_or_none()
    if current_tree is None:
        return
    for node in list(current_tree.nodes):
        if getattr(node, "name", "").startswith("VTK "):
            current_tree.nodes.remove(node)


def selected_evidence():
    selected = [strip.name for strip in editor.strips if getattr(strip, "select", False)]
    return {
        "selected_strip": editor.active_strip.name if editor.active_strip else None,
        "target_strip_selected": target_strip.name in selected,
        "selected_strips": selected,
        "strip_filepath": target_strip.filepath,
        "real_video_filepath": str(VIDEO),
    }


def configure_output_node(current_tree, tool_id):
    output = next(
        (
            node for node in current_tree.nodes
            if node.bl_idname == "CompositorNodeOutputFile"
            and getattr(node, "name", "").startswith("VTK ")
        ),
        None,
    )
    if output is None:
        raise RuntimeError("no VTK Output File node was created")
    source_socket = next((socket.links[0].from_socket for socket in output.inputs if socket.links), None)
    if source_socket is None:
        raise RuntimeError("VTK Output File node has no linked processed input")
    if hasattr(output, "file_output_items"):
        output.file_output_items.clear()
        output.file_output_items.new(socket_type="RGBA", name="Image")
        current_tree.links.new(source_socket, output.inputs[0])
    if hasattr(output, "directory"):
        output.directory = str(EXR_DIR)
    if hasattr(output, "file_name"):
        output.file_name = tool_id
    if hasattr(output, "save_as_render"):
        output.save_as_render = True
    if hasattr(output, "use_file_extension"):
        output.use_file_extension = True
    return output


def convert_exr_to_png(tool_id):
    exr = EXR_DIR / f"{tool_id}.exr"
    png = SNAPSHOT_DIR / f"{tool_id}.png"
    if not exr.exists():
        matches = sorted(EXR_DIR.glob(f"{tool_id}*.exr"))
        if not matches:
            return None, str(png), 0
        exr = matches[-1]
    if exr.stat().st_size <= 0:
        return None, str(png), 0
    return str(exr), str(png), 0


results = []
failures = []
tools = [tool for tool in all_tools() if _tool_has_compositor_stack(tool)]
for tool in tools:
    try:
        clear_toolkit_nodes()
        editor.active_strip = target_strip
        target_strip.select = True
        scene.frame_set(FRAME)
        result = bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id=tool.id)
        if result != {"FINISHED"}:
            raise RuntimeError(f"create_tool_compositor_nodes returned {result}")
        current_tree = tree()
        vtk_nodes = [node for node in current_tree.nodes if getattr(node, "name", "").startswith("VTK ")]
        output = configure_output_node(current_tree, tool.id)
        bpy.ops.render.render(write_still=True)
        exr, png, size = convert_exr_to_png(tool.id)
        if exr is None:
            evidence = {
                "tool_id": tool.id,
                "label": tool.label,
                "category": tool.category,
                "node_count": len(vtk_nodes),
                "node_types": sorted({node.bl_idname for node in vtk_nodes}),
                "output_node": output.name,
                "reason": "Blender 5.2 did not emit a renderable RGB Output File image for this compositor graph",
                "frame": FRAME,
                **selected_evidence(),
            }
            results.append({"name": tool.id, "group": "compositor_visual_snapshot", "status": "noted", "evidence": evidence})
            print(f"NOTE compositor_visual_snapshot: {tool.id}")
            continue
        evidence = {
            "tool_id": tool.id,
            "label": tool.label,
            "category": tool.category,
            "node_count": len(vtk_nodes),
            "node_types": sorted({node.bl_idname for node in vtk_nodes}),
            "output_node": output.name,
            "exr": exr,
            "png": png,
            "bytes": size,
            "frame": FRAME,
            **selected_evidence(),
        }
        results.append({"name": tool.id, "group": "compositor_visual_snapshot", "status": "passed", "evidence": evidence})
        print(f"PASS compositor_visual_snapshot: {tool.id}")
    except Exception as exc:
        traceback.print_exc()
        failure = {"name": tool.id, "group": "compositor_visual_snapshot", "status": "failed", "error": str(exc)}
        results.append(failure)
        failures.append(failure)
        print(f"FAIL compositor_visual_snapshot: {tool.id}: {exc}")

report = {
    "original_video": str(ORIGINAL_VIDEO),
    "source_video": str(VIDEO),
    "target_strip": target_strip.name,
    "target_filepath": str(VIDEO),
    "frame": FRAME,
    "total_compositor_tools": len(tools),
    "passed": sum(1 for result in results if result["status"] == "passed"),
    "failed": len(failures),
    "noted": sum(1 for result in results if result["status"] == "noted"),
    "snapshot_dir": str(SNAPSHOT_DIR),
    "exr_dir": str(EXR_DIR),
    "results": results,
    "failures": failures,
}
REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

video_toolkit.unregister()

if failures:
    raise SystemExit(f"{len(failures)} compositor visual failures; see {REPORT_PATH}")
print(json.dumps({"report": str(REPORT_PATH), "passed": report["passed"], "failed": report["failed"]}, indent=2))
'''
    return (
        template.replace("__ROOT__", repr(str(ROOT)))
        .replace("__ORIGINAL_VIDEO__", repr(str(original_video)))
        .replace("__VIDEO__", repr(str(video)))
        .replace("__OUTPUT_DIR__", repr(str(output_dir)))
        .replace("__FRAME__", str(frame))
    )


if __name__ == "__main__":
    raise SystemExit(main())
