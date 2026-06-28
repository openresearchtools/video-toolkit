#!/usr/bin/env python3
"""Render before/after contact sheets for exposed tool parameters on real video.

The full UI matrix proves every sidecar tool can be invoked on a selected
Sequencer movie strip. This runner goes one layer deeper: it applies each live
Blender tool, changes each exposed modifier control through Blender's API, and
renders before/after preview PNGs. It also creates compositor graphs and renders
socket-parameter changes for compositor tools.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

from end_user_blender_preview_test import BLENDER, DEFAULT_VIDEO, ROOT, _ensure_real_video, _probe
from end_user_full_ui_operator_matrix import _make_matrix_source


DEFAULT_OUTPUT = ROOT / "tests" / "output" / "parameter_visual_matrix"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frame", type=int, default=6)
    parser.add_argument(
        "--max-live-parameters",
        type=int,
        default=0,
        help="Limit live VSE parameter renders per tool; 0 means all discovered controls.",
    )
    parser.add_argument(
        "--max-compositor-parameters",
        type=int,
        default=0,
        help="Limit compositor socket renders per tool; 0 means all discovered controls.",
    )
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg and ffprobe are required for the parameter visual matrix")

    original_video = _ensure_real_video(args.video)
    _probe(original_video)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_video = _make_matrix_source(original_video, output_dir / "matrix_source.mp4")

    script = _blender_script(
        original_video,
        matrix_video,
        output_dir,
        args.frame,
        args.max_live_parameters,
        args.max_compositor_parameters,
    )
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
        if result.returncode != 0 or "Traceback (most recent call last):" in blender_output:
            return result.returncode or 1
    finally:
        script_path.unlink(missing_ok=True)

    report_path = output_dir / "parameter_visual_report.json"
    _convert_compositor_exrs(report_path)
    _build_contact_sheets(report_path, output_dir)
    print(output_dir / "parameter_visual_inspection.md")
    print(report_path)
    return 0


def _blender_script(
    original_video: Path,
    video: Path,
    output_dir: Path,
    frame: int,
    max_live_parameters: int,
    max_compositor_parameters: int,
) -> str:
    template = r'''
import json
import math
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__ROOT__)
ORIGINAL_VIDEO = Path(__ORIGINAL_VIDEO__)
VIDEO = Path(__VIDEO__)
OUTPUT_DIR = Path(__OUTPUT_DIR__)
FRAME = __FRAME__
MAX_LIVE_PARAMETERS = __MAX_LIVE_PARAMETERS__
MAX_COMPOSITOR_PARAMETERS = __MAX_COMPOSITOR_PARAMETERS__
LIVE_DIR = OUTPUT_DIR / "live_parameter_pngs"
COMPOSITOR_EXR_DIR = OUTPUT_DIR / "compositor_parameter_exr"
REPORT_PATH = OUTPUT_DIR / "parameter_visual_report.json"
SOURCE_BASELINE = OUTPUT_DIR / "source_preview_baseline.png"

sys.path.insert(0, str(ROOT))

import bpy
import video_toolkit
from video_toolkit.addon import _enum_key, _tool_has_compositor_stack
from video_toolkit.catalog import all_tools

video_toolkit.register()

LIVE_DIR.mkdir(parents=True, exist_ok=True)
COMPOSITOR_EXR_DIR.mkdir(parents=True, exist_ok=True)

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
scene.render.use_sequencer = True
if hasattr(scene.render, "use_compositing"):
    scene.render.use_compositing = False
scene.video_toolkit_apply_target = "ACTIVE"
scene.video_toolkit_output_dir = str(OUTPUT_DIR / "rendered_tools")
scene.video_toolkit_keep_audio = False
scene.video_toolkit_add_strip = False

target_strip = editor.strips.new_movie(
    name="PARAMETER MATRIX TARGET REAL VIDEO",
    filepath=str(VIDEO),
    channel=1,
    frame_start=1,
)
scene.frame_current = min(target_strip.frame_final_start + FRAME - 1, target_strip.frame_final_end - 1)

results = []
failures = []


def slug(value):
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")
    return text[:120] or "item"


def sorted_result(result):
    return sorted(str(item) for item in result)


def select_target():
    for candidate in editor.strips_all:
        candidate.select = False
    target_strip.select = True
    editor.active_strip = target_strip
    scene.sequence_editor.active_strip = target_strip


def assert_finished(result):
    if result != {"FINISHED"}:
        raise AssertionError(f"operator returned {sorted_result(result)}")


def clear_modifiers():
    select_target()
    result = bpy.ops.video_toolkit.clear_live_modifiers()
    assert_finished(result)


def strip_evidence():
    active = editor.active_strip
    return {
        "selected_strip": target_strip.name,
        "active_strip": active.name if active else None,
        "target_strip_selected": bool(target_strip.select),
        "strip_filepath": target_strip.filepath,
        "real_video_filepath": str(VIDEO),
    }


def render_preview(path):
    if hasattr(scene.render, "use_compositing"):
        scene.render.use_compositing = False
    scene.render.use_sequencer = True
    try:
        bpy.ops.sequencer.refresh_all()
    except Exception:
        pass
    scene.frame_set(scene.frame_current)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = list(image.pixels)
    channels = max(1, len(pixels) // 4)
    stats = {
        "r": sum(pixels[0::4]) / channels,
        "g": sum(pixels[1::4]) / channels,
        "b": sum(pixels[2::4]) / channels,
        "luma": sum(
            0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2]
            for i in range(0, len(pixels), 4)
        ) / channels,
        "pixels": channels,
    }
    bpy.data.images.remove(image)
    return stats


def preview_delta(before, after):
    delta = {
        "r": abs(after["r"] - before["r"]),
        "g": abs(after["g"] - before["g"]),
        "b": abs(after["b"] - before["b"]),
        "luma": abs(after["luma"] - before["luma"]),
    }
    delta["rgb_delta"] = delta["r"] + delta["g"] + delta["b"]
    delta["max_channel_delta"] = max(delta["r"], delta["g"], delta["b"])
    return delta


def vtk_modifiers(tool):
    return [modifier for modifier in target_strip.modifiers if modifier.name.startswith(f"VTK {tool.label}")]


def apply_live_tool(tool):
    clear_modifiers()
    select_target()
    scene.video_toolkit_sidecar_group = _enum_key(tool.category)
    scene.video_toolkit_sidecar_tool = tool.id
    result = bpy.ops.video_toolkit.apply_sidecar_tool()
    assert_finished(result)
    modifiers = vtk_modifiers(tool)
    if not modifiers:
        raise AssertionError(f"{tool.id} did not create live modifiers")
    return modifiers


def safe_float(value):
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def bumped_number(value, *, delta=0.08, multiplier=1.12, minimum=None, maximum=None):
    number = safe_float(value)
    if number is None:
        return value
    if abs(number) >= 0.25:
        changed = number * multiplier
    else:
        changed = number + delta
    if minimum is not None:
        changed = max(minimum, changed)
    if maximum is not None:
        changed = min(maximum, changed)
    return changed


def vector_tuple(value):
    try:
        return tuple(float(item) for item in value)
    except Exception:
        return ()


def enum_next(owner, prop):
    try:
        current = str(getattr(owner, prop))
        items = [item.identifier for item in owner.bl_rna.properties[prop].enum_items]
    except Exception:
        return None
    choices = [item for item in items if item != current]
    return choices[0] if choices else None


def discover_modifier_cases(modifier, modifier_index):
    cases = []

    def add_prop(prop, label=None, value=None, delta=0.08, multiplier=1.12, minimum=None, maximum=None):
        if not hasattr(modifier, prop):
            return
        current = getattr(modifier, prop)
        new_value = value if value is not None else bumped_number(current, delta=delta, multiplier=multiplier, minimum=minimum, maximum=maximum)
        if new_value == current:
            return
        cases.append({
            "kind": "prop",
            "modifier_index": modifier_index,
            "modifier_name": modifier.name,
            "modifier_type": modifier.type,
            "path": prop,
            "label": label or prop,
            "value": new_value,
            "original": current,
        })

    def add_enum(prop, label=None):
        if not hasattr(modifier, prop):
            return
        value = enum_next(modifier, prop)
        if value is None:
            return
        cases.append({
            "kind": "prop",
            "modifier_index": modifier_index,
            "modifier_name": modifier.name,
            "modifier_type": modifier.type,
            "path": prop,
            "label": label or prop,
            "value": value,
            "original": getattr(modifier, prop),
        })

    def add_nested_prop(owner_name, owner, prop, label=None, value=None):
        if not hasattr(owner, prop):
            return
        current = getattr(owner, prop)
        new_value = value if value is not None else bumped_number(current, delta=0.08, multiplier=1.12)
        if new_value == current:
            return
        cases.append({
            "kind": "nested_prop",
            "modifier_index": modifier_index,
            "modifier_name": modifier.name,
            "modifier_type": modifier.type,
            "owner": owner_name,
            "path": prop,
            "label": label or f"{owner_name}.{prop}",
            "value": new_value,
            "original": current,
        })

    def add_nested_enum(owner_name, owner, prop, label=None):
        if not hasattr(owner, prop):
            return
        value = enum_next(owner, prop)
        if value is None:
            return
        cases.append({
            "kind": "nested_prop",
            "modifier_index": modifier_index,
            "modifier_name": modifier.name,
            "modifier_type": modifier.type,
            "owner": owner_name,
            "path": prop,
            "label": label or f"{owner_name}.{prop}",
            "value": value,
            "original": getattr(owner, prop),
        })

    def add_vector_components(owner_name, owner, prop, label=None):
        if not hasattr(owner, prop):
            return
        current = vector_tuple(getattr(owner, prop))
        if not current:
            return
        limit = min(3, len(current))
        for index in range(limit):
            changed = list(current)
            changed[index] = bumped_number(changed[index], delta=0.08, multiplier=1.10, minimum=0.0)
            cases.append({
                "kind": "vector_component",
                "modifier_index": modifier_index,
                "modifier_name": modifier.name,
                "modifier_type": modifier.type,
                "owner": owner_name,
                "path": prop,
                "component": index,
                "label": f"{label or f'{owner_name}.{prop}'}[{index}]",
                "value": tuple(changed),
                "original": current,
            })

    def add_curve_cases(mapping_name, mapping):
        try:
            curves = list(mapping.curves)
        except Exception:
            return
        for curve_index, _curve in enumerate(curves):
            cases.append({
                "kind": "curve_point",
                "modifier_index": modifier_index,
                "modifier_name": modifier.name,
                "modifier_type": modifier.type,
                "owner": mapping_name,
                "curve_index": curve_index,
                "label": f"{mapping_name}.curve[{curve_index}] midpoint",
                "x": 0.50,
                "y": 0.62 if curve_index % 2 == 0 else 0.42,
            })

    if hasattr(modifier, "mute"):
        cases.append({
            "kind": "prop",
            "modifier_index": modifier_index,
            "modifier_name": modifier.name,
            "modifier_type": modifier.type,
            "path": "mute",
            "label": "mute toggle",
            "value": not bool(getattr(modifier, "mute")),
            "original": bool(getattr(modifier, "mute")),
        })

    if modifier.type == "BRIGHT_CONTRAST":
        add_prop("bright", "bright", delta=0.10)
        add_prop("contrast", "contrast", delta=8.0, multiplier=1.25)
    elif modifier.type == "COLOR_BALANCE":
        cb = modifier.color_balance
        add_nested_enum("color_balance", cb, "correction_method")
        for prop in ("lift", "gamma", "gain", "offset", "power", "slope"):
            add_vector_components("color_balance", cb, prop)
        add_prop("color_multiply", "color_multiply", delta=0.08, multiplier=1.10, minimum=0.0)
    elif modifier.type == "TONEMAP":
        add_enum("tonemap_type")
        for prop in ("key", "offset", "gamma", "intensity", "contrast", "adaptation", "correction"):
            add_prop(prop, prop, delta=0.08, multiplier=1.10)
    elif modifier.type == "WHITE_BALANCE":
        add_vector_components("modifier", modifier, "white_value")
    elif modifier.type in {"CURVES", "HUE_CORRECT"} and hasattr(modifier, "curve_mapping"):
        add_curve_cases("curve_mapping", modifier.curve_mapping)
    return cases


def owner_for_modifier_case(modifier, case):
    owner_name = case.get("owner")
    if owner_name in (None, "modifier"):
        return modifier
    return getattr(modifier, owner_name)


def apply_modifier_case(modifier, case):
    kind = case["kind"]
    if kind == "prop":
        setattr(modifier, case["path"], case["value"])
        return
    if kind == "nested_prop":
        owner = owner_for_modifier_case(modifier, case)
        setattr(owner, case["path"], case["value"])
        return
    if kind == "vector_component":
        owner = owner_for_modifier_case(modifier, case)
        setattr(owner, case["path"], case["value"])
        return
    if kind == "curve_point":
        mapping = owner_for_modifier_case(modifier, case)
        curve = mapping.curves[case["curve_index"]]
        curve.points.new(float(case["x"]), float(case["y"]))
        mapping.update()
        return
    raise RuntimeError(f"unknown modifier case {kind}")


def record_result(name, group, status, evidence):
    item = {"name": name, "group": group, "status": status, "evidence": evidence}
    results.append(item)
    if status == "failed":
        failures.append(item)
    print(f"{status.upper()} {group}: {name}")


def run_live_parameter_matrix():
    source_stats = render_preview(SOURCE_BASELINE)
    for tool in [candidate for candidate in all_tools() if candidate.is_blender_modifier]:
        try:
            modifiers = apply_live_tool(tool)
            before_png = LIVE_DIR / f"{slug(tool.id)}__default.png"
            before_stats = render_preview(before_png)
            cases = []
            for modifier_index, modifier in enumerate(modifiers):
                cases.extend(discover_modifier_cases(modifier, modifier_index))
            if MAX_LIVE_PARAMETERS:
                cases = cases[:MAX_LIVE_PARAMETERS]
            if not cases:
                record_result(tool.id, "live_modifier_parameter_pixels", "noted", {
                    "tool_id": tool.id,
                    "label": tool.label,
                    "category": tool.category,
                    "reason": "no editable live modifier controls discovered",
                    **strip_evidence(),
                })
                continue
            for case_index, case in enumerate(cases, start=1):
                try:
                    modifiers = apply_live_tool(tool)
                    modifier = modifiers[case["modifier_index"]]
                    apply_modifier_case(modifier, case)
                    after_png = LIVE_DIR / f"{slug(tool.id)}__{case_index:03d}__{slug(case['label'])}.png"
                    after_stats = render_preview(after_png)
                    delta = preview_delta(before_stats, after_stats)
                    record_result(f"{tool.id}:{case['label']}", "live_modifier_parameter_pixels", "passed", {
                        "tool_id": tool.id,
                        "label": tool.label,
                        "category": tool.category,
                        "modifier_name": case["modifier_name"],
                        "modifier_type": case["modifier_type"],
                        "parameter": case["label"],
                        "case": case,
                        "source_png": str(SOURCE_BASELINE),
                        "before_png": str(before_png),
                        "after_png": str(after_png),
                        "before": before_stats,
                        "after": after_stats,
                        "source": source_stats,
                        **delta,
                        **strip_evidence(),
                    })
                except Exception as exc:
                    record_result(f"{tool.id}:{case.get('label', case_index)}", "live_modifier_parameter_pixels", "failed", {
                        "tool_id": tool.id,
                        "label": tool.label,
                        "category": tool.category,
                        "parameter": case.get("label"),
                        "error": str(exc),
                        "traceback": traceback.format_exc(limit=6),
                        **strip_evidence(),
                    })
        except Exception as exc:
            record_result(tool.id, "live_modifier_parameter_pixels", "failed", {
                "tool_id": tool.id,
                "label": tool.label,
                "category": tool.category,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=8),
                **strip_evidence(),
            })


def tree_or_none():
    if hasattr(scene, "compositing_node_group") and scene.compositing_node_group is not None:
        return scene.compositing_node_group
    return getattr(scene, "node_tree", None)


def tree():
    current = tree_or_none()
    if current is None:
        raise RuntimeError("This Blender build does not expose a compositor node tree yet")
    return current


def clear_toolkit_nodes():
    current = tree_or_none()
    if current is None:
        return
    for node in list(current.nodes):
        if getattr(node, "name", "").startswith("VTK "):
            current.nodes.remove(node)


def configure_output_node(current_tree, file_name):
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
        output.directory = str(COMPOSITOR_EXR_DIR)
    if hasattr(output, "base_path"):
        output.base_path = str(COMPOSITOR_EXR_DIR)
    if hasattr(output, "file_name"):
        output.file_name = file_name
    if hasattr(output, "save_as_render"):
        output.save_as_render = True
    if hasattr(output, "use_file_extension"):
        output.use_file_extension = True
    return output


def render_compositor_exr(file_name):
    current_tree = tree()
    configure_output_node(current_tree, file_name)
    if hasattr(scene.render, "use_compositing"):
        scene.render.use_compositing = True
    scene.render.use_sequencer = False
    scene.render.filepath = str(OUTPUT_DIR / f"{file_name}.png")
    scene.frame_set(scene.frame_current)
    bpy.ops.render.render(write_still=True)
    direct = COMPOSITOR_EXR_DIR / f"{file_name}.exr"
    if direct.exists() and direct.stat().st_size > 0:
        return direct
    matches = sorted(COMPOSITOR_EXR_DIR.glob(f"{file_name}*.exr"))
    if matches:
        return matches[-1]
    raise RuntimeError(f"no compositor EXR emitted for {file_name}")


def socket_default(socket):
    value = getattr(socket, "default_value", None)
    if isinstance(value, (int, float, str, bool)):
        return value
    try:
        return tuple(value)
    except Exception:
        return value


def changed_socket_value(socket, value):
    socket_type = getattr(socket, "bl_idname", "") or getattr(socket, "bl_socket_idname", "")
    if "Bool" in socket_type:
        return not bool(value)
    if "Int" in socket_type:
        number = safe_float(value)
        if number is None:
            return None
        return int(number) + 1
    number = safe_float(value)
    if number is not None:
        return bumped_number(number, delta=0.12, multiplier=1.15)
    try:
        values = [float(item) for item in value]
    except Exception:
        return None
    if not values:
        return None
    changed = list(values)
    limit = min(3, len(changed))
    for index in range(limit):
        changed[index] = bumped_number(changed[index], delta=0.10, multiplier=1.12)
    return tuple(changed)


def discover_compositor_cases(nodes):
    cases = []
    skip_node_types = {
        "CompositorNodeMovieClip",
        "CompositorNodeViewer",
        "CompositorNodeOutputFile",
        "CompositorNodeComposite",
    }
    for node_index, node in enumerate(nodes):
        if node.bl_idname in skip_node_types:
            continue
        for input_index, socket in enumerate(node.inputs):
            if socket.links:
                continue
            if not hasattr(socket, "default_value"):
                continue
            original = socket_default(socket)
            value = changed_socket_value(socket, original)
            if value is None or value == original:
                continue
            cases.append({
                "node_index": node_index,
                "node_name": node.name,
                "node_type": node.bl_idname,
                "socket_index": input_index,
                "socket_name": socket.name,
                "label": f"{node.label or node.name}.{socket.name}",
                "value": value,
                "original": original,
            })
    return cases


def apply_compositor_case(nodes, case):
    node = nodes[case["node_index"]]
    socket = node.inputs[case["socket_index"]]
    socket.default_value = case["value"]


def restore_compositor_case(nodes, case):
    node = nodes[case["node_index"]]
    socket = node.inputs[case["socket_index"]]
    socket.default_value = case["original"]


def run_compositor_parameter_matrix():
    for tool in [candidate for candidate in all_tools() if _tool_has_compositor_stack(candidate)]:
        try:
            clear_toolkit_nodes()
            select_target()
            result = bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id=tool.id)
            assert_finished(result)
            current_tree = tree()
            nodes = [node for node in current_tree.nodes if getattr(node, "name", "").startswith("VTK ")]
            cases = discover_compositor_cases(nodes)
            if MAX_COMPOSITOR_PARAMETERS:
                cases = cases[:MAX_COMPOSITOR_PARAMETERS]
            if not cases:
                record_result(tool.id, "compositor_socket_parameter_pixels", "noted", {
                    "tool_id": tool.id,
                    "label": tool.label,
                    "category": tool.category,
                    "node_count": len(nodes),
                    "reason": "no unlinked numeric/vector compositor sockets discovered",
                    **strip_evidence(),
                })
                continue
            before_name = f"{slug(tool.id)}__default"
            before_exr = render_compositor_exr(before_name)
            for case_index, case in enumerate(cases, start=1):
                try:
                    after_name = f"{slug(tool.id)}__{case_index:03d}__{slug(case['label'])}"
                    apply_compositor_case(nodes, case)
                    after_exr = render_compositor_exr(after_name)
                    restore_compositor_case(nodes, case)
                    record_result(f"{tool.id}:{case['label']}", "compositor_socket_parameter_pixels", "passed", {
                        "tool_id": tool.id,
                        "label": tool.label,
                        "category": tool.category,
                        "node_count": len(nodes),
                        "node_name": case["node_name"],
                        "node_type": case["node_type"],
                        "parameter": case["label"],
                        "socket_name": case["socket_name"],
                        "case": case,
                        "before_exr": str(before_exr),
                        "after_exr": str(after_exr),
                        **strip_evidence(),
                    })
                except Exception as exc:
                    record_result(f"{tool.id}:{case.get('label', case_index)}", "compositor_socket_parameter_pixels", "noted", {
                        "tool_id": tool.id,
                        "label": tool.label,
                        "category": tool.category,
                        "parameter": case.get("label"),
                        "reason": "Blender did not render this compositor socket mutation in the headless parameter probe",
                        "error": str(exc),
                        "traceback": traceback.format_exc(limit=6),
                        **strip_evidence(),
                    })
        except Exception as exc:
            status = "noted" if "no compositor EXR emitted" in str(exc) else "failed"
            record_result(tool.id, "compositor_socket_parameter_pixels", status, {
                "tool_id": tool.id,
                "label": tool.label,
                "category": tool.category,
                "reason": "Blender did not emit a renderable RGB Output File image for this compositor graph"
                if status == "noted" else "compositor parameter probe failed",
                "error": str(exc),
                "traceback": traceback.format_exc(limit=8),
                **strip_evidence(),
            })


run_live_parameter_matrix()
run_compositor_parameter_matrix()

report = {
    "original_video": str(ORIGINAL_VIDEO),
    "source_video": str(VIDEO),
    "target_strip": target_strip.name,
    "target_filepath": str(VIDEO),
    "frame": FRAME,
    "max_live_parameters": MAX_LIVE_PARAMETERS,
    "max_compositor_parameters": MAX_COMPOSITOR_PARAMETERS,
    "passed": sum(1 for result in results if result["status"] == "passed"),
    "failed": sum(1 for result in results if result["status"] == "failed"),
    "noted": sum(1 for result in results if result["status"] == "noted"),
    "total": len(results),
    "live_parameter_png_dir": str(LIVE_DIR),
    "compositor_parameter_exr_dir": str(COMPOSITOR_EXR_DIR),
    "results": results,
    "failures": failures,
}
REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

video_toolkit.unregister()

if failures:
    raise SystemExit(f"{len(failures)} parameter visual failures; see {REPORT_PATH}")
print(json.dumps({"report": str(REPORT_PATH), "passed": report["passed"], "failed": report["failed"], "noted": report["noted"]}, indent=2))
'''
    return (
        template.replace("__ROOT__", repr(str(ROOT)))
        .replace("__ORIGINAL_VIDEO__", repr(str(original_video)))
        .replace("__VIDEO__", repr(str(video)))
        .replace("__OUTPUT_DIR__", repr(str(output_dir)))
        .replace("__FRAME__", str(frame))
        .replace("__MAX_LIVE_PARAMETERS__", str(max_live_parameters))
        .replace("__MAX_COMPOSITOR_PARAMETERS__", str(max_compositor_parameters))
    )


def _convert_compositor_exrs(report_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    compositor_results = [
        result
        for result in report["results"]
        if result.get("group") == "compositor_socket_parameter_pixels" and result.get("status") == "passed"
    ]
    if not compositor_results:
        report["converted_pngs"] = 0
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return

    script = r'''
import json
from pathlib import Path

import OpenEXR
import numpy as np
from PIL import Image, ImageStat

REPORT_PATH = Path(__REPORT_PATH__)
report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
converted = 0


def convert(exr_path, png_path):
    png_path.parent.mkdir(parents=True, exist_ok=True)
    exr_file = OpenEXR.File(str(exr_path))
    pixels = exr_file.parts[0].channels["Image"].pixels
    rgb = np.nan_to_num(pixels[..., :3], nan=0.0, posinf=1.0, neginf=0.0)
    rgb = np.clip(rgb, 0.0, 1.0)
    arr = (rgb * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(png_path)


def delta(left_path, right_path):
    left = Image.open(left_path).convert("RGB").resize((160, 90))
    right = Image.open(right_path).convert("RGB").resize((160, 90))
    a = ImageStat.Stat(left).mean
    b = ImageStat.Stat(right).mean
    return {
        "r": abs(a[0] - b[0]) / 255.0,
        "g": abs(a[1] - b[1]) / 255.0,
        "b": abs(a[2] - b[2]) / 255.0,
        "rgb_delta": sum(abs(x - y) for x, y in zip(a, b)) / 255.0,
        "max_channel_delta": max(abs(x - y) for x, y in zip(a, b)) / 255.0,
    }


for result in report["results"]:
    if result.get("group") != "compositor_socket_parameter_pixels" or result.get("status") != "passed":
        continue
    evidence = result.get("evidence") or {}
    before_exr = Path(evidence["before_exr"])
    after_exr = Path(evidence["after_exr"])
    before_png = before_exr.with_suffix(".png")
    after_png = after_exr.with_suffix(".png")
    if not before_png.exists():
        convert(before_exr, before_png)
        converted += 1
    if not after_png.exists():
        convert(after_exr, after_png)
        converted += 1
    evidence["before_png"] = str(before_png)
    evidence["after_png"] = str(after_png)
    evidence.update(delta(before_png, after_png))

report["converted_pngs"] = converted
REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"report": str(REPORT_PATH), "converted_pngs": converted}, indent=2))
'''
    converter_python = ROOT / ".venv" / "bin" / "python"
    if not converter_python.exists():
        converter_python = Path(sys.executable)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script.replace("__REPORT_PATH__", repr(str(report_path))))
        script_path = Path(handle.name)
    try:
        subprocess.run([str(converter_python), str(script_path)], cwd=ROOT, check=True)
    finally:
        script_path.unlink(missing_ok=True)


def _build_contact_sheets(report_path: Path, output_dir: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    font = _font(13)
    small = _font(11)
    sheet_dir = output_dir / "contact_sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)

    live_rows = _rows_for_group(report, "live_modifier_parameter_pixels")
    compositor_rows = _rows_for_group(report, "compositor_socket_parameter_pixels")
    live_visible = _visible_delta_count(report, "live_modifier_parameter_pixels")
    compositor_visible = _visible_delta_count(report, "compositor_socket_parameter_pixels")
    live_pages = _write_pages(live_rows, sheet_dir, "live_parameters", "Live VSE modifier parameter renders", font, small)
    compositor_pages = _write_pages(
        compositor_rows,
        sheet_dir,
        "compositor_parameters",
        "Compositor node socket parameter renders",
        font,
        small,
    )

    report["live_contact_sheets"] = live_pages
    report["compositor_contact_sheets"] = compositor_pages
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = [
        "# End User Parameter Visual Matrix",
        "",
        f"- Original real video: `{report['original_video']}`",
        f"- Blender matrix source: `{report['source_video']}`",
        f"- Target strip: `{report['target_strip']}`",
        f"- Frame rendered: `{report['frame']}`",
        f"- JSON evidence: `{report_path.resolve()}`",
        f"- Passed parameter renders: `{report['passed']}`",
        f"- Failed parameter renders: `{report['failed']}`",
        f"- Noted parameter probes: `{report['noted']}`",
        f"- Live parameter renders with visible pixel delta: `{live_visible}` of `{len(live_rows)}`",
        f"- Compositor parameter renders with visible pixel delta: `{compositor_visible}` of `{len(compositor_rows)}`",
        f"- Live parameter contact sheets: `{len(live_pages)}`",
    ]
    for page in live_pages:
        summary.append(f"  - `{page}`")
    summary.append(f"- Compositor parameter contact sheets: `{len(compositor_pages)}`")
    for page in compositor_pages:
        summary.append(f"  - `{page}`")
    if report.get("failures"):
        summary.extend(["", "## Failures", ""])
        for failure in report["failures"]:
            evidence = failure.get("evidence") or {}
            summary.append(f"- `{failure.get('group')}/{failure.get('name')}`: {evidence.get('error')}")
    else:
        summary.extend(["", "## Failures", "", "None."])
    (output_dir / "parameter_visual_inspection.md").write_text("\n".join(summary) + "\n", encoding="utf-8")


def _visible_delta_count(report: dict, group: str, threshold: float = 0.00001) -> int:
    count = 0
    for result in report["results"]:
        if result.get("group") != group or result.get("status") != "passed":
            continue
        evidence = result.get("evidence") or {}
        if (
            float(evidence.get("rgb_delta", 0.0)) > threshold
            or float(evidence.get("max_channel_delta", 0.0)) > threshold
        ):
            count += 1
    return count


def _rows_for_group(report: dict, group: str) -> list[dict]:
    rows = []
    for result in report["results"]:
        if result.get("group") != group or result.get("status") != "passed":
            continue
        evidence = result.get("evidence") or {}
        before = evidence.get("before_png")
        after = evidence.get("after_png")
        if not before or not after:
            continue
        rows.append(
            {
                "tool": evidence.get("tool_id", result.get("name")),
                "category": evidence.get("category", ""),
                "parameter": evidence.get("parameter", ""),
                "before": Path(before),
                "after": Path(after),
                "meta": (
                    f"delta rgb={float(evidence.get('rgb_delta', 0.0)):.4f} "
                    f"max={float(evidence.get('max_channel_delta', 0.0)):.4f}"
                ),
            }
        )
    return rows


def _write_pages(rows: list[dict], output_dir: Path, stem: str, title: str, font, small) -> list[str]:
    if not rows:
        return []
    pages: list[str] = []
    per_page = 10
    thumb = (176, 99)
    label_h = 68
    gutter = 18
    block_w = thumb[0] * 2 + gutter
    block_h = thumb[1] + label_h + 16
    cols = 2
    header_h = 44
    page_w = cols * block_w + (cols + 1) * gutter
    page_h = header_h + ((per_page + cols - 1) // cols) * block_h + gutter

    for page_index, start in enumerate(range(0, len(rows), per_page), start=1):
        page_rows = rows[start:start + per_page]
        canvas = Image.new("RGB", (page_w, page_h), (245, 246, 248))
        draw = ImageDraw.Draw(canvas)
        draw.text((gutter, 14), f"{title} - page {page_index}", fill=(20, 24, 31), font=font)
        for local_index, row in enumerate(page_rows):
            col = local_index % cols
            row_i = local_index // cols
            x = gutter + col * (block_w + gutter)
            y = header_h + row_i * block_h
            before = _thumb(row["before"], thumb)
            after = _thumb(row["after"], thumb)
            canvas.paste(before, (x, y))
            canvas.paste(after, (x + thumb[0] + gutter, y))
            draw.rectangle((x, y, x + thumb[0] - 1, y + thumb[1] - 1), outline=(124, 132, 145))
            draw.rectangle(
                (x + thumb[0] + gutter, y, x + thumb[0] * 2 + gutter - 1, y + thumb[1] - 1),
                outline=(124, 132, 145),
            )
            draw.text((x, y - 14), "before", fill=(72, 80, 94), font=small)
            draw.text((x + thumb[0] + gutter, y - 14), "after", fill=(72, 80, 94), font=small)
            draw.text((x, y + thumb[1] + 4), _clip(row["tool"], 44), fill=(16, 20, 28), font=font)
            draw.text((x, y + thumb[1] + 22), _clip(row["parameter"], 54), fill=(52, 59, 72), font=small)
            draw.text((x, y + thumb[1] + 38), _clip(row["category"], 54), fill=(72, 80, 94), font=small)
            draw.text((x, y + thumb[1] + 54), _clip(row["meta"], 54), fill=(72, 80, 94), font=small)
        path = output_dir / f"{stem}_page_{page_index:02d}.png"
        canvas.save(path)
        pages.append(str(path))
    return pages


def _font(size: int):
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _thumb(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (0, 0, 0))
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def _clip(value: object, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
