#!/usr/bin/env python3
"""Verify node tools switch a real Blender window to Compositing."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from end_user_blender_preview_test import BLENDER, DEFAULT_VIDEO, ROOT, _ensure_real_video, _probe


DEFAULT_OUTPUT = ROOT / "tests" / "output" / "node_workspace_smoke"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffprobe"):
        raise SystemExit("ffprobe is required for the node workspace smoke test")

    video = _ensure_real_video(args.video)
    _probe(video)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    script = _blender_script(video, output_dir)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        result = subprocess.run(
            [str(BLENDER), "--factory-startup", "--python", str(script_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        blender_output = result.stdout + result.stderr
        if (
            result.returncode != 0
            or "Traceback (most recent call last):" in blender_output
            or "AssertionError" in blender_output
        ):
            return result.returncode or 1
    finally:
        script_path.unlink(missing_ok=True)
    report_path = output_dir / "report.json"
    if not report_path.exists():
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("failed"):
        return 1
    print(output_dir / "report.json")
    return 0


def _blender_script(video: Path, output_dir: Path) -> str:
    return f"""
import json
import sys
import traceback
from pathlib import Path

import bpy

ROOT = Path({str(ROOT)!r})
VIDEO = Path({str(video)!r})
OUTPUT_DIR = Path({str(output_dir)!r})

sys.path.insert(0, str(ROOT))
import video_toolkit
from video_toolkit import addon

try:
    video_toolkit.unregister()
except Exception:
    pass
video_toolkit.register()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
failures = []


def fail(message, **evidence):
    evidence["error"] = message
    failures.append(evidence)


state = {{
    "active_clip_path": None,
    "movie_clip_path": None,
    "selected_nodes": [],
    "node_count": 0,
    "checks": [],
}}


def run_smoke():
    try:
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
        _run_node_operator(
            route="create_tool_compositor_nodes",
            tool_id="primary_color_board",
            tool_label="Primary Color Board",
            use_apply_filter=False,
        )
    except Exception as exc:
        fail("unexpected exception", traceback=traceback.format_exc(limit=12), exception=str(exc))
        finish_smoke()
        return None
    bpy.app.timers.register(check_create_tool_smoke, first_interval=0.5)
    return None


def _run_node_operator(route, tool_id, tool_label, use_apply_filter):
    if bpy.context.window is None:
        fail("Blender did not create a UI window for the workspace smoke test")
        return
    video_workspace = bpy.data.workspaces.get("Video Editing")
    if video_workspace is not None:
        bpy.context.window.workspace = video_workspace
    state["before_workspace"] = bpy.context.window.workspace.name
    state["route"] = route
    state["tool_id"] = tool_id
    state["tool_label"] = tool_label

    scene = bpy.context.scene
    scene.sequence_editor_create()
    editor = scene.sequence_editor
    strip = next((candidate for candidate in editor.strips_all if candidate.type == "MOVIE"), None)
    if strip is None:
        strip = editor.strips.new_movie(
            name="NODE WORKSPACE SMOKE REAL VIDEO",
            filepath=str(VIDEO),
            channel=1,
            frame_start=1,
        )
    editor.active_strip = strip
    for candidate in editor.strips_all:
        candidate.select = False
    strip.select = True
    scene.frame_start = int(strip.frame_final_start)
    scene.frame_end = int(strip.frame_final_end)
    scene.frame_current = min(scene.frame_start + 12, scene.frame_end - 1)

    if use_apply_filter:
        result = bpy.ops.video_toolkit.apply_filter(filter_id=tool_id)
    else:
        result = bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id=tool_id)
    if result != {{'FINISHED'}}:
        fail("node operator did not finish", route=route, tool_id=tool_id, result=str(result))


def check_create_tool_smoke():
    try:
        _check_node_workspace()
    except Exception as exc:
        fail("unexpected check exception", traceback=traceback.format_exc(limit=12), exception=str(exc))
    if failures:
        finish_smoke()
        return None
    try:
        _run_node_operator(
            route="apply_filter_compositor",
            tool_id="native_compositor_exposure",
            tool_label="Compositor Exposure",
            use_apply_filter=True,
        )
    except Exception as exc:
        fail("unexpected apply-filter route exception", traceback=traceback.format_exc(limit=12), exception=str(exc))
        finish_smoke()
        return None
    bpy.app.timers.register(check_apply_filter_smoke, first_interval=0.5)
    return None


def check_apply_filter_smoke():
    try:
        _check_node_workspace()
    except Exception as exc:
        fail("unexpected apply-filter check exception", traceback=traceback.format_exc(limit=12), exception=str(exc))
    finish_smoke()
    return None


def _check_node_workspace():
    route = state.get("route", "")
    tool_id = state.get("tool_id", "")
    tool_label = state.get("tool_label", "")
    node_prefix = f"VTK Tool {{tool_label}}"
    if bpy.context.window is None:
        fail("Blender window disappeared before workspace verification", route=route, tool_id=tool_id)
        return
    after_workspace = bpy.context.window.workspace.name
    screen = bpy.context.window.screen
    node_areas = [area for area in screen.areas if area.type == "NODE_EDITOR"]
    if after_workspace != "Compositing":
        fail("node operator did not switch to the Compositing workspace", route=route, tool_id=tool_id, before=state.get("before_workspace"), after=after_workspace)
    if not node_areas:
        fail("Compositing workspace does not expose a node editor area", route=route, tool_id=tool_id, workspace=after_workspace)

    scene = bpy.context.scene
    tree = addon._compositor_tree_or_none(scene)
    vtk_nodes = [node for node in tree.nodes if node.name.startswith(node_prefix)]
    selected_nodes = [node.name for node in vtk_nodes if node.select]
    state["selected_nodes"] = selected_nodes
    state["node_count"] = len(vtk_nodes)
    active_node = tree.nodes.active
    active_clip = getattr(scene, "active_clip", None)
    active_clip_path = Path(bpy.path.abspath(active_clip.filepath)) if active_clip else None
    movie_nodes = [node for node in vtk_nodes if node.bl_idname == "CompositorNodeMovieClip"]
    movie_clip_path = Path(bpy.path.abspath(movie_nodes[0].clip.filepath)) if movie_nodes and movie_nodes[0].clip else None
    state["active_clip_path"] = active_clip_path
    state["movie_clip_path"] = movie_clip_path
    state["checks"].append(
        {{
            "route": route,
            "tool_id": tool_id,
            "workspace": after_workspace,
            "node_count": len(vtk_nodes),
            "movie_clip": str(movie_clip_path) if movie_clip_path else "",
            "active_clip": str(active_clip_path) if active_clip_path else "",
            "selected_nodes": selected_nodes,
        }}
    )
    if not vtk_nodes:
        fail("node operator did not create VTK compositor nodes", route=route, tool_id=tool_id, prefix=node_prefix)
    if not movie_nodes:
        fail("node graph does not include a Movie Clip node", route=route, tool_id=tool_id)
    if movie_clip_path != VIDEO:
        fail("Movie Clip node does not use the selected strip file", route=route, tool_id=tool_id, movie_clip=str(movie_clip_path), expected=str(VIDEO))
    if active_clip_path != VIDEO:
        fail("scene active clip was not set to the selected strip file", route=route, tool_id=tool_id, active_clip=str(active_clip_path), expected=str(VIDEO))
    if active_node is None or active_node.name not in selected_nodes:
        fail(
            "created compositor nodes were not selected/focused",
            route=route,
            tool_id=tool_id,
            active_node=getattr(active_node, "name", ""),
            selected_nodes=selected_nodes,
        )


def finish_smoke():
    report = {{
        "source_video": str(VIDEO),
        "failed": len(failures),
        "failures": failures,
        "workspace": bpy.context.window.workspace.name if bpy.context.window else "",
        "active_clip": str(state["active_clip_path"]) if state["active_clip_path"] else "",
        "movie_clip": str(state["movie_clip_path"]) if state["movie_clip_path"] else "",
        "node_count": state["node_count"],
        "selected_nodes": state["selected_nodes"],
        "checks": state["checks"],
    }}
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("VIDEO_TOOLKIT_NODE_WORKSPACE_SMOKE=" + json.dumps(report, sort_keys=True))
    try:
        bpy.ops.wm.quit_blender()
    except Exception:
        pass


bpy.app.timers.register(run_smoke, first_interval=1.0)
"""


if __name__ == "__main__":
    raise SystemExit(main())
