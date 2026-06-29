#!/usr/bin/env python3
"""Smoke-test Video Effects parameter editing inside Blender on a real MP4."""

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


DEFAULT_OUTPUT = ROOT / "tests" / "output" / "effect_parameter_smoke"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffprobe"):
        raise SystemExit("ffprobe is required for the effect parameter smoke test")

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
            [str(BLENDER), "--background", "--factory-startup", "--python", str(script_path)],
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
from video_toolkit.catalog import all_tools, get_tool
from video_toolkit import addon

try:
    video_toolkit.unregister()
except Exception:
    pass
video_toolkit.register()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.sequence_editor_create()
editor = scene.sequence_editor
strip = editor.strips.new_movie(
    name="EFFECT PARAMETER SMOKE REAL VIDEO",
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
scene.video_toolkit_apply_target = "ACTIVE"
scene.video_toolkit_live_preview = False
scene.video_toolkit_auto_ffmpeg_preview = False
scene.video_toolkit_sidecar_section = "BROWSER"

failures = []
results = []


def record(name, status, evidence):
    item = {{"name": name, "status": status, "evidence": evidence}}
    results.append(item)
    if status == "failed":
        failures.append(item)
    print(f"{{status.upper()}} {{name}}", flush=True)


def fail(name, message, **evidence):
    evidence["error"] = message
    record(name, "failed", evidence)


def assert_finished(name, result, **evidence):
    if result != {{'FINISHED'}}:
        fail(name, f"operator returned {{result}}", **evidence)
        return False
    return True


def parameter_rows_for(tool):
    return [param for param in scene.video_toolkit_tool_parameters if param.tool_id == tool.id]


def parameter_items_for(tool):
    return [
        (index, param)
        for index, param in enumerate(scene.video_toolkit_tool_parameters)
        if param.tool_id == tool.id
    ]


def verify_parameter_expansion(tool):
    toggled = 0
    for parameter_index, param in parameter_items_for(tool):
        if bpy.ops.video_toolkit.toggle_tool_parameter(parameter_index=parameter_index) != {{'FINISHED'}}:
            fail(f"parameter_expand:{{tool.id}}:{{parameter_index}}", "parameter row did not finish expanding", path=param.path)
            continue
        if scene.video_toolkit_expanded_parameter_index != parameter_index:
            fail(
                f"parameter_expand:{{tool.id}}:{{parameter_index}}",
                "parameter row did not become the expanded row",
                path=param.path,
                expanded=scene.video_toolkit_expanded_parameter_index,
                expected=parameter_index,
            )
        if bpy.ops.video_toolkit.toggle_tool_parameter(parameter_index=parameter_index) != {{'FINISHED'}}:
            fail(f"parameter_collapse:{{tool.id}}:{{parameter_index}}", "parameter row did not finish collapsing", path=param.path)
            continue
        if scene.video_toolkit_expanded_parameter_index != -1:
            fail(
                f"parameter_collapse:{{tool.id}}:{{parameter_index}}",
                "parameter row did not collapse",
                path=param.path,
                expanded=scene.video_toolkit_expanded_parameter_index,
            )
        toggled += 1
    return toggled


def mutate_first_parameter(params):
    for param in params:
        if param.value_kind == "FLOAT":
            param.float_value = float(param.float_value) + 0.025
            return param.path
        if param.value_kind == "INT":
            param.int_value = int(param.int_value) + 1
            return param.path
        if param.value_kind == "BOOL":
            param.bool_value = not bool(param.bool_value)
            return param.path
    for param in params:
        if param.value_kind == "TEXT":
            param.text_value = f"{{param.text_value}}_edited"
            return param.path
    return ""


def clear_modifiers():
    for modifier in reversed(list(strip.modifiers)):
        strip.modifiers.remove(modifier)


try:
    visible_sections = [item[1] for item in addon.SIDECAR_SECTION_ITEMS]
    if visible_sections != ["Effects", "Strip", "Modifiers", "Render"]:
        fail("visible_sidecar_sections", "unexpected visible sidecar section labels", sections=visible_sections)
    else:
        record("visible_sidecar_sections", "passed", {{"sections": visible_sections}})

    legacy_panel_ids = [
        "VIDEO_TOOLKIT_PT_video_effects_analysis",
        "VIDEO_TOOLKIT_PT_video_effects_color_management",
        "VIDEO_TOOLKIT_PT_video_effects_compositor",
        "VIDEO_TOOLKIT_PT_video_effects_live_tools",
        "VIDEO_TOOLKIT_PT_video_effects_strip",
        "VIDEO_TOOLKIT_PT_video_effects_modifiers",
        "VIDEO_TOOLKIT_PT_video_effects_render",
    ]
    visible_legacy_panels = [
        panel_id
        for panel_id in legacy_panel_ids
        if getattr(bpy.types, panel_id, None) is not None
        and getattr(bpy.types, panel_id).poll(bpy.context)
    ]
    if visible_legacy_panels:
        fail(
            "legacy_child_panels_hidden",
            "legacy overlapping child panels are still visible in the Video Effects sidebar",
            panels=visible_legacy_panels,
        )
    else:
        record("legacy_child_panels_hidden", "passed", {{"panels": legacy_panel_ids}})

    internal_tools = [tool for tool in all_tools() if addon._tool_is_internal_effect(tool)]
    external_tools = [tool for tool in all_tools() if tool.is_ffmpeg]
    node_tools = [tool for tool in all_tools() if addon._tool_is_node_section_effect(tool)]
    node_only_tools = [tool for tool in all_tools() if tool.is_compositor]
    node_only_in_internal = sorted(tool.id for tool in node_only_tools if tool in internal_tools)
    node_section_in_internal = sorted(set(tool.id for tool in node_tools) & set(tool.id for tool in internal_tools))
    mask_tools_in_internal = sorted(
        tool.id
        for tool in internal_tools
        if addon._tool_uses_mask_modifier(tool)
    )
    if node_only_in_internal or node_section_in_internal or mask_tools_in_internal:
        fail(
            "tool_section_separation",
            "node-section or mask tools leaked into the Internal applied-effects section",
            node_only_in_internal=node_only_in_internal,
            node_section_in_internal=node_section_in_internal[:40],
            mask_tools_in_internal=mask_tools_in_internal,
        )
    else:
        record(
            "tool_section_separation",
            "passed",
            {{
                "internal": len(internal_tools),
                "external": len(external_tools),
                "nodes": len(node_tools),
                "node_only": len(node_only_tools),
            }},
        )

    internal_checked = 0
    internal_rows = 0
    internal_toggled_rows = 0
    internal_control_rows = 0
    curve_rows = 0
    hue_rows = 0
    no_internal_rows = []
    for tool in internal_tools:
        clear_modifiers()
        if not assert_finished(
            f"internal_select:{{tool.id}}",
            bpy.ops.video_toolkit.select_sidecar_tool(filter_id=tool.id),
            tool_id=tool.id,
        ):
            continue
        params = parameter_rows_for(tool)
        if not params:
            no_internal_rows.append(tool.id)
            continue
        internal_toggled_rows += verify_parameter_expansion(tool)
        for index, param in enumerate(params):
            if not param.label or not param.group_label or not param.default_text or not param.control_hint or not param.range_hint:
                fail(
                    f"internal_parameter_metadata:{{tool.id}}:{{index}}",
                    "parameter row is missing label, group, default, control hint, or range hint",
                    path=param.path,
                    label=param.label,
                    group=param.group_label,
                    default=param.default_text,
                    control=param.control_hint,
                    range=param.range_hint,
                )
            else:
                internal_control_rows += 1
            if param.path.startswith("__curve_points__."):
                curve_rows += 1
            elif param.path.startswith("__hue_correct__."):
                hue_rows += 1
            elif param.path.startswith("__"):
                fail(
                    f"internal_parameter_path:{{tool.id}}:{{index}}",
                    "unsupported internal parameter path was exposed",
                    path=param.path,
                )
        changed_path = mutate_first_parameter(params)
        assert_finished(
            f"internal_apply:{{tool.id}}",
            bpy.ops.video_toolkit.apply_filter(filter_id=tool.id, target="ACTIVE"),
            tool_id=tool.id,
            changed_path=changed_path,
        )
        if not strip.modifiers:
            fail(f"internal_modifier_created:{{tool.id}}", "applying internal tool did not add VSE modifiers")
        internal_checked += 1
        internal_rows += len(params)
    if no_internal_rows:
        fail("internal_parameter_rows", "internal tools missing editable parameter rows", tools=no_internal_rows)
    else:
        record(
            "internal_parameter_rows",
            "passed",
            {{
                "tools": internal_checked,
                "rows": internal_rows,
                "toggled_rows": internal_toggled_rows,
                "control_rows": internal_control_rows,
                "curve_rows": curve_rows,
                "hue_correct_rows": hue_rows,
            }},
        )

    ffmpeg_checked = 0
    ffmpeg_rows = 0
    ffmpeg_toggled_rows = 0
    ffmpeg_control_rows = 0
    no_ffmpeg_rows = []
    unchanged_ffmpeg = []
    generic_ffmpeg_parameters = []
    for tool in external_tools:
        if not assert_finished(
            f"external_select:{{tool.id}}",
            bpy.ops.video_toolkit.select_sidecar_tool(filter_id=tool.id),
            tool_id=tool.id,
        ):
            continue
        params = parameter_rows_for(tool)
        source_chain = addon._ffmpeg_tool_edit_chain(tool)
        parsed_args = [
            arg
            for segment in addon._parse_ffmpeg_filter_chain(source_chain)
            for arg in segment["args"]
        ]
        if parsed_args and not params:
            no_ffmpeg_rows.append(tool.id)
            continue
        if params:
            ffmpeg_toggled_rows += verify_parameter_expansion(tool)
            generic_ffmpeg_parameters.extend(
                {{
                    "tool_id": tool.id,
                    "filter": param.filter_name,
                    "arg_index": param.arg_index,
                    "label": param.label,
                    "path": param.path,
                }}
                for param in params
                if param.label.startswith("Argument ") or param.path.startswith("argument_")
            )
            for index, param in enumerate(params):
                if not param.control_hint or not param.range_hint:
                    fail(
                        f"external_parameter_metadata:{{tool.id}}:{{index}}",
                        "external parameter row is missing control or range hint",
                        path=param.path,
                        label=param.label,
                        control=param.control_hint,
                        range=param.range_hint,
                    )
                else:
                    ffmpeg_control_rows += 1
            changed_path = mutate_first_parameter(params)
            edited = addon._tool_with_parameter_overrides(scene, tool)
            edited_chain = addon._ffmpeg_tool_edit_chain(edited)
            if edited_chain == source_chain:
                unchanged_ffmpeg.append({{"tool_id": tool.id, "changed_path": changed_path}})
            ffmpeg_rows += len(params)
        ffmpeg_checked += 1
    if no_ffmpeg_rows or unchanged_ffmpeg or generic_ffmpeg_parameters:
        fail(
            "external_parameter_rows",
            "external tools did not expose named editable FFmpeg parameters or apply edits",
            missing_rows=no_ffmpeg_rows,
            unchanged=unchanged_ffmpeg[:20],
            generic_parameters=generic_ffmpeg_parameters[:20],
        )
    else:
        record(
            "external_parameter_rows",
            "passed",
            {{"tools": ffmpeg_checked, "rows": ffmpeg_rows, "toggled_rows": ffmpeg_toggled_rows, "control_rows": ffmpeg_control_rows}},
        )

    clear_modifiers()
    live_tool = get_tool("live_gamma_grade")
    assert_finished(
        "parameter_expand",
        bpy.ops.video_toolkit.select_sidecar_tool(filter_id=live_tool.id),
        tool_id=live_tool.id,
    )
    live_params = parameter_rows_for(live_tool)
    bright_index = next((index for index, param in enumerate(scene.video_toolkit_tool_parameters) if param.tool_id == live_tool.id and param.path == "bright"), -1)
    if bright_index < 0:
        fail("parameter_expand", "live_gamma_grade bright parameter was not exposed")
    else:
        assert_finished(
            "parameter_expand_toggle",
            bpy.ops.video_toolkit.toggle_tool_parameter(parameter_index=bright_index),
            parameter_index=bright_index,
        )
        if scene.video_toolkit_expanded_parameter_index != bright_index:
            fail("parameter_expand_toggle", "parameter row did not expand", expanded=scene.video_toolkit_expanded_parameter_index, expected=bright_index)
        scene.video_toolkit_tool_parameters[bright_index].float_value += 0.05
        assert_finished(
            "parameter_row_apply",
            bpy.ops.video_toolkit.apply_tool_parameter(parameter_index=bright_index),
            parameter_index=bright_index,
        )
        record("parameter_row_apply", "passed", {{"parameter_index": bright_index, "rows": len(live_params)}})

    clear_modifiers()
    scene.video_toolkit_live_preview = True
    assert_finished(
        "live_preview_select",
        bpy.ops.video_toolkit.select_sidecar_tool(filter_id="live_gamma_grade"),
        tool_id="live_gamma_grade",
    )
    preview_modifiers = [modifier.name for modifier in strip.modifiers if modifier.name.startswith("VTK Preview live_gamma_grade ")]
    if not preview_modifiers:
        fail("live_preview_modifiers", "live preview did not create temporary preview modifiers")
    else:
        record("live_preview_modifiers", "passed", {{"modifiers": preview_modifiers}})
    scene.video_toolkit_live_preview = False

    node_section_tool = get_tool("native_compositor_exposure")
    if not addon._tool_is_node_section_effect(node_section_tool):
        fail("node_create", "selected node smoke tool is not exposed in the Nodes section", tool_id=node_section_tool.id)
    clear_modifiers()
    assert_finished(
        "node_create",
        bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id=node_section_tool.id),
        tool_id=node_section_tool.id,
    )
    tree = addon._compositor_tree_or_none(scene)
    vtk_nodes = [node for node in tree.nodes if node.name.startswith("VTK Tool Compositor Exposure")]
    movie_nodes = [node for node in vtk_nodes if node.bl_idname == "CompositorNodeMovieClip"]
    if not vtk_nodes or not movie_nodes:
        fail(
            "node_create",
            "Nodes-section tool did not create a compositor graph from the selected movie strip",
            node_count=len(vtk_nodes),
            movie_nodes=len(movie_nodes),
        )
    else:
        clip_path = Path(bpy.path.abspath(movie_nodes[0].clip.filepath)) if getattr(movie_nodes[0], "clip", None) else None
        if clip_path != VIDEO:
            fail("node_create", "movie clip node did not use the selected strip file", clip_path=str(clip_path), expected=str(VIDEO))
        else:
            record(
                "node_create",
                "passed",
                {{
                    "node_count": len(vtk_nodes),
                    "movie_clip": str(clip_path),
                    "expanded_tool": scene.video_toolkit_expanded_tool,
                    "summary": scene.video_toolkit_last_compositor_nodes,
                }},
            )

    mask_node_tool = get_tool("native_mask_slot")
    if not addon._tool_is_node_section_effect(mask_node_tool):
        fail("mask_node_create", "mask tool is not exposed in the Nodes section", tool_id=mask_node_tool.id)
    assert_finished(
        "mask_node_create",
        bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id=mask_node_tool.id),
        tool_id=mask_node_tool.id,
    )
    tree = addon._compositor_tree_or_none(scene)
    mask_vtk_nodes = [node for node in tree.nodes if node.name.startswith("VTK Tool Mask Slot")]
    mask_movie_nodes = [node for node in mask_vtk_nodes if node.bl_idname == "CompositorNodeMovieClip"]
    mask_alpha_nodes = [
        node
        for node in mask_vtk_nodes
        if node.bl_idname in {{"CompositorNodeBoxMask", "CompositorNodeSetAlpha"}}
    ]
    if not mask_vtk_nodes or not mask_movie_nodes or not mask_alpha_nodes:
        fail(
            "mask_node_create",
            "mask node-section tool did not create an editable compositor mask graph",
            node_count=len(mask_vtk_nodes),
            movie_nodes=len(mask_movie_nodes),
            mask_alpha_nodes=len(mask_alpha_nodes),
        )
    else:
        mask_clip_path = Path(bpy.path.abspath(mask_movie_nodes[0].clip.filepath)) if getattr(mask_movie_nodes[0], "clip", None) else None
        if mask_clip_path != VIDEO:
            fail("mask_node_create", "mask Movie Clip node did not use the selected strip file", clip_path=str(mask_clip_path), expected=str(VIDEO))
        else:
            record(
                "mask_node_create",
                "passed",
                {{
                    "node_count": len(mask_vtk_nodes),
                    "movie_clip": str(mask_clip_path),
                    "summary": scene.video_toolkit_last_compositor_nodes,
                }},
            )

except Exception as exc:
    fail("unexpected_exception", str(exc), traceback=traceback.format_exc(limit=12))

report = {{
    "source_video": str(VIDEO),
    "failed": len(failures),
    "passed": sum(1 for item in results if item["status"] == "passed"),
    "results": results,
}}
(OUTPUT_DIR / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
if failures:
    raise SystemExit(f"{{len(failures)}} effect parameter smoke failure(s)")
"""


if __name__ == "__main__":
    raise SystemExit(main())
