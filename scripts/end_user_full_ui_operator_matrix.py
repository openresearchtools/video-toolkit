#!/usr/bin/env python3
"""Exercise every Video Effects UI operator in Blender on a real MP4.

This is the broad end-user matrix: it opens footage in the Sequencer, selects
real movie strips, invokes the same operators wired to the sidecar/menu
buttons, and writes JSON evidence for every catalog tool and workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from end_user_blender_preview_test import (
    BLENDER,
    DEFAULT_VIDEO,
    ROOT,
    _ensure_real_video,
    _make_reference_video,
    _probe,
)


DEFAULT_OUTPUT = ROOT / "tests" / "output" / "full_ui_matrix"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg and ffprobe are required for the full UI operator matrix")

    original_video = _ensure_real_video(args.video)
    _probe(original_video)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_video = _make_matrix_source(original_video, output_dir / "matrix_source.mp4")
    reference_video = _make_reference_video(matrix_video, output_dir / "matrix_reference.mp4")

    script = _blender_script(matrix_video, reference_video, output_dir)
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
    print(output_dir / "report.json")
    return 0


def _make_matrix_source(source: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(source),
            "-t",
            "1.25",
            "-vf",
            "scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2,fps=12",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _probe(output)
    return output


def _blender_script(video: Path, reference_video: Path, output_dir: Path) -> str:
    template = r'''
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__ROOT__)
VIDEO = Path(__VIDEO__)
REFERENCE_VIDEO = Path(__REFERENCE_VIDEO__)
OUTPUT_DIR = Path(__OUTPUT_DIR__)
RENDERED_DIR = OUTPUT_DIR / "rendered_tools"
REPORT_PATH = OUTPUT_DIR / "report.json"
BEFORE_PREVIEW = OUTPUT_DIR / "matrix_preview_before.png"
AFTER_PREVIEW = OUTPUT_DIR / "matrix_preview_after.png"
BLEND_PATH = OUTPUT_DIR / "full_ui_operator_matrix.blend"

sys.path.insert(0, str(ROOT))

import bpy
import video_toolkit
from video_toolkit.addon import (
    COLOR_MANAGEMENT_PRESET_ITEMS,
    COMPOSITOR_STACK_ITEMS,
    SIDECAR_SECTION_ITEMS,
    _enum_key,
    _tool_has_compositor_stack,
)
from video_toolkit.catalog import all_tools, categories

video_toolkit.register()

scene = bpy.context.scene
scene.sequence_editor_create()
editor = scene.sequence_editor
scene.video_toolkit_output_dir = str(RENDERED_DIR)
scene.video_toolkit_crf = 32
scene.video_toolkit_preset = "ultrafast"
scene.video_toolkit_keep_audio = False
scene.video_toolkit_add_strip = False
scene.video_toolkit_apply_target = "ACTIVE"
scene.video_toolkit_analysis_samples = 8
scene.video_toolkit_recommendation_mix_count = 3
scene.video_toolkit_flicker_smoothing = 3
scene.video_toolkit_match_smoothing = 3
scene.video_toolkit_color_match_smoothing = 3
scene.video_toolkit_ffmpeg_chain = (
    "colorspace=iall=bt709:all=bt709:irange=tv:range=pc,"
    "normalize=smoothing=12:independence=0.55:strength=0.45,"
    "eq=contrast=1.10:saturation=1.06:gamma=1.02,"
    "colorlevels=rimin=0.02:rimax=0.98,"
    "colorbalance=rs=0.03:bm=0.02:bh=-0.03:pl=1,"
    "vibrance=intensity=0.25,"
    "exposure=exposure=0.18:black=0.02,"
    "grayworld,"
    "negate=components=r+g+b,"
    "colorhold=color=blue:similarity=0.12:blend=0.2,"
    "lutrgb=r=negval:g=val*0.9:b=val+12,"
    "histeq=strength=0.18:intensity=0.14"
)

target_strip = editor.strips.new_movie(
    name="UI MATRIX TARGET REAL VIDEO",
    filepath=str(VIDEO),
    channel=1,
    frame_start=1,
)
reference_strip = editor.strips.new_movie(
    name="UI MATRIX REFERENCE REAL VIDEO",
    filepath=str(REFERENCE_VIDEO),
    channel=2,
    frame_start=1,
)
reference_strip.mute = True

scene.frame_start = target_strip.frame_final_start
scene.frame_end = target_strip.frame_final_end
scene.frame_current = min(target_strip.frame_final_start + 5, target_strip.frame_final_end - 1)
scene.render.use_sequencer = True
scene.render.resolution_x = 160
scene.render.resolution_y = 90
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

results = []
failures = []


def sorted_result(result):
    return sorted(str(item) for item in result)


def select_target(with_reference=False):
    for candidate in editor.strips_all:
        candidate.select = False
    target_strip.select = True
    if with_reference:
        reference_strip.select = True
    editor.active_strip = target_strip
    scene.sequence_editor.active_strip = target_strip


def assert_finished(result):
    if result != {"FINISHED"}:
        raise AssertionError(f"operator returned {sorted_result(result)}")


def vtk_modifiers(prefix=None):
    mods = []
    for modifier in target_strip.modifiers:
        if not modifier.name.startswith("VTK "):
            continue
        if prefix is not None and not modifier.name.startswith(prefix):
            continue
        mods.append(modifier)
    return mods


def modifier_evidence(prefix=None):
    mods = vtk_modifiers(prefix)
    evidence = []
    for modifier in mods:
        item = {
            "name": modifier.name,
            "type": modifier.type,
            "mute": bool(getattr(modifier, "mute", False)),
            "show_expanded": bool(getattr(modifier, "show_expanded", False)),
        }
        for prop in ("enable", "show_preview", "is_active"):
            if hasattr(modifier, prop):
                item[prop] = bool(getattr(modifier, prop))
        evidence.append(item)
    return evidence


def clear_modifiers():
    select_target()
    result = bpy.ops.video_toolkit.clear_live_modifiers()
    assert_finished(result)


def tree():
    return scene.compositing_node_group if hasattr(scene, "compositing_node_group") else scene.node_tree


def node_evidence(prefix):
    nodes = [node for node in tree().nodes if node.name.startswith(prefix)]
    return {
        "count": len(nodes),
        "types": sorted({node.bl_idname for node in nodes}),
        "links": len(tree().links),
    }


def action_keyframe_count(action, data_path):
    if action is None:
        return 0
    if hasattr(action, "fcurves"):
        return sum(len(fcurve.keyframe_points) for fcurve in action.fcurves if fcurve.data_path == data_path)
    total = 0
    for layer in getattr(action, "layers", []):
        for action_strip in getattr(layer, "strips", []):
            for channelbag in getattr(action_strip, "channelbags", []):
                total += sum(len(fcurve.keyframe_points) for fcurve in channelbag.fcurves if fcurve.data_path == data_path)
    return total


def render_preview(path):
    if hasattr(scene.render, "use_compositing"):
        scene.render.use_compositing = False
    try:
        bpy.ops.sequencer.refresh_all()
    except Exception:
        pass
    scene.frame_set(scene.frame_current)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = list(image.pixels)
    channels = len(pixels) // 4
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


def record(name, group, func):
    try:
        evidence = func()
        results.append({"name": name, "group": group, "status": "passed", "evidence": evidence})
        print(f"PASS {group}: {name}")
    except Exception as exc:
        detail = {
            "error": str(exc),
            "traceback": traceback.format_exc(limit=8),
        }
        results.append({"name": name, "group": group, "status": "failed", "evidence": detail})
        failures.append({"name": name, "group": group, **detail})
        print(f"FAIL {group}: {name}: {exc}")


def record_note(name, group, evidence):
    results.append({"name": name, "group": group, "status": "noted", "evidence": evidence})
    print(f"NOTE {group}: {name}")


def exercise_catalog_tool(tool):
    def run():
        clear_modifiers()
        select_target()
        scene.video_toolkit_apply_target = "ACTIVE"
        scene.video_toolkit_last_output = ""
        result = bpy.ops.video_toolkit.apply_filter(filter_id=tool.id, target="ACTIVE")
        assert_finished(result)
        if tool.is_blender_modifier:
            prefix = f"VTK {tool.label}"
            mods = modifier_evidence(prefix)
            expected = len(tool.blender_stack) if tool.blender_stack else 1
            if len(mods) < expected:
                raise AssertionError(f"expected at least {expected} modifiers, found {len(mods)}")
            return {
                "tool_id": tool.id,
                "category": tool.category,
                "engine": tool.engine,
                "modifier_count": len(mods),
                "modifier_types": [item["type"] for item in mods],
                "live_sequencer_strip": target_strip.name,
            }
        output = Path(scene.video_toolkit_last_output)
        if not output.exists() or output.stat().st_size <= 0:
            raise AssertionError(f"rendered output missing: {output}")
        return {
            "tool_id": tool.id,
            "category": tool.category,
            "engine": tool.engine,
            "output": str(output),
            "bytes": output.stat().st_size,
        }
    record(tool.id, "catalog_apply_filter", run)


def exercise_tool_nodes(tool):
    def run():
        select_target()
        result = bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id=tool.id)
        assert_finished(result)
        evidence = node_evidence(f"VTK Tool {tool.label} ")
        if evidence["count"] <= 0:
            raise AssertionError("no compositor nodes were created")
        return {
            "tool_id": tool.id,
            "category": tool.category,
            "last_summary": scene.video_toolkit_last_compositor_nodes,
            **evidence,
        }
    record(tool.id, "catalog_tool_nodes", run)


def exercise_sidecar_group(group):
    group_tools = [tool for tool in all_tools() if tool.category == group]
    first_tool = group_tools[0]

    def apply_selected():
        clear_modifiers()
        select_target()
        scene.video_toolkit_sidecar_group = _enum_key(group)
        scene.video_toolkit_sidecar_tool = first_tool.id
        scene.video_toolkit_last_output = ""
        result = bpy.ops.video_toolkit.apply_sidecar_tool()
        assert_finished(result)
        if first_tool.is_blender_modifier:
            mods = modifier_evidence(f"VTK {first_tool.label}")
            if not mods:
                raise AssertionError("sidecar Apply did not add modifiers")
            output = None
        else:
            output_path = Path(scene.video_toolkit_last_output)
            if not output_path.exists():
                raise AssertionError("sidecar Apply did not render output")
            mods = []
            output = str(output_path)
        return {
            "group": group,
            "selected_tool": first_tool.id,
            "apply_result": "FINISHED",
            "modifiers": mods,
            "output": output,
        }

    record(group, "sidecar_apply", apply_selected)

    node_tool = next((tool for tool in group_tools if _tool_has_compositor_stack(tool)), None)
    if node_tool is None:
        record_note(group, "sidecar_nodes", {"reason": "group has no compositor-compatible selected tool"})
        return

    def create_selected_nodes():
        select_target()
        scene.video_toolkit_sidecar_group = _enum_key(group)
        scene.video_toolkit_sidecar_tool = node_tool.id
        result = bpy.ops.video_toolkit.create_sidecar_compositor_nodes()
        assert_finished(result)
        evidence = node_evidence(f"VTK Tool {node_tool.label} ")
        if evidence["count"] <= 0:
            raise AssertionError("sidecar Nodes did not create a graph")
        return {
            "group": group,
            "selected_tool": node_tool.id,
            "last_summary": scene.video_toolkit_last_compositor_nodes,
            **evidence,
        }

    record(group, "sidecar_nodes", create_selected_nodes)


def set_reference_selection():
    select_target(with_reference=True)


def live_modifier_control_probe():
    clear_modifiers()
    select_target()
    result = bpy.ops.video_toolkit.apply_filter(filter_id="live_gamma_grade", target="ACTIVE")
    assert_finished(result)
    modifiers = vtk_modifiers("VTK Live Gamma Grade")
    if not modifiers:
        raise AssertionError("no live modifier to edit")
    modifier = modifiers[0]
    modifier.show_expanded = True
    modifier.mute = False
    if hasattr(modifier, "bright"):
        modifier.bright = float(modifier.bright) + 0.015
    if hasattr(modifier, "show_preview"):
        modifier.show_preview = True
    return {
        "edited_modifier": modifier.name,
        "type": modifier.type,
        "controls": modifier_evidence("VTK Live Gamma Grade"),
    }


def strip_control_probe():
    select_target()
    target_strip.blend_alpha = 0.82
    if hasattr(target_strip, "transform"):
        target_strip.transform.offset_x = 3.0
        target_strip.transform.offset_y = -2.0
        target_strip.transform.scale_x = 0.98
        target_strip.transform.scale_y = 0.98
    if hasattr(target_strip, "crop"):
        target_strip.crop.min_x = 1
        target_strip.crop.max_x = 1
        target_strip.crop.min_y = 1
        target_strip.crop.max_y = 1
    return {
        "blend_alpha": target_strip.blend_alpha,
        "transform": {
            "offset_x": getattr(target_strip.transform, "offset_x", None),
            "offset_y": getattr(target_strip.transform, "offset_y", None),
            "scale_x": getattr(target_strip.transform, "scale_x", None),
            "scale_y": getattr(target_strip.transform, "scale_y", None),
        } if hasattr(target_strip, "transform") else {},
        "crop": {
            "min_x": getattr(target_strip.crop, "min_x", None),
            "max_x": getattr(target_strip.crop, "max_x", None),
            "min_y": getattr(target_strip.crop, "min_y", None),
            "max_y": getattr(target_strip.crop, "max_y", None),
        } if hasattr(target_strip, "crop") else {},
    }


def workflow_operator(name, op, *, reference=False, minimum_modifiers=0, minimum_nodes=0, summary_attr=None):
    def run():
        clear_modifiers()
        set_reference_selection() if reference else select_target()
        result = op()
        assert_finished(result)
        mods = modifier_evidence()
        if minimum_modifiers and len(mods) < minimum_modifiers:
            raise AssertionError(f"expected at least {minimum_modifiers} live modifiers, found {len(mods)}")
        evidence = {
            "result": "FINISHED",
            "modifier_count": len(mods),
            "modifier_types": [item["type"] for item in mods],
        }
        if minimum_nodes:
            all_vtk_nodes = [node for node in tree().nodes if node.name.startswith("VTK ")]
            if len(all_vtk_nodes) < minimum_nodes:
                raise AssertionError(f"expected at least {minimum_nodes} VTK nodes, found {len(all_vtk_nodes)}")
            evidence["total_vtk_nodes"] = len(all_vtk_nodes)
        if summary_attr:
            evidence["summary"] = getattr(scene, summary_attr)
        return evidence
    record(name, "workflow_operators", run)


def node_stack_operator(stack_type):
    requires_reference = stack_type in {"MATCHED_COLOR", "REFERENCE_COLOR_BOARD", "COLOR_TIMELINE_MATCH"}

    def run():
        set_reference_selection() if requires_reference else select_target()
        if stack_type == "TRANSLATED_COLOR":
            scene.video_toolkit_ffmpeg_chain = (
                "colorspace=iall=bt709:all=bt709:irange=tv:range=pc,"
                "eq=contrast=1.12:saturation=1.08:gamma=1.02,"
                "colorbalance=rs=0.04:bm=0.03:bh=-0.04:pl=1,"
                "curves=preset=strong_contrast,"
                "grayworld,"
                "negate=components=r+g+b,"
                "colorhold=color=blue:similarity=0.12:blend=0.2,"
                "lutrgb=r=negval:g=val*0.9:b=val+12,"
                "histeq=strength=0.20:intensity=0.18"
            )
        result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type=stack_type)
        assert_finished(result)
        all_vtk_nodes = [node for node in tree().nodes if node.name.startswith("VTK ")]
        if not all_vtk_nodes:
            raise AssertionError("no VTK compositor nodes exist after node stack operation")
        return {
            "stack_type": stack_type,
            "result": "FINISHED",
            "last_summary": scene.video_toolkit_last_compositor_nodes,
            "total_vtk_nodes": len(all_vtk_nodes),
            "node_types": sorted({node.bl_idname for node in all_vtk_nodes}),
        }
    record(stack_type, "compositor_stack_operators", run)


def preview_probe():
    clear_modifiers()
    select_target()
    before = render_preview(BEFORE_PREVIEW)
    result = bpy.ops.video_toolkit.apply_filter(filter_id="live_contrast_pop", target="ACTIVE")
    assert_finished(result)
    modifier = vtk_modifiers("VTK Live Contrast Pop")[0]
    if hasattr(modifier, "contrast"):
        modifier.contrast = float(modifier.contrast) + 8.0
    after = render_preview(AFTER_PREVIEW)
    delta = abs(after["luma"] - before["luma"])
    if delta <= 0.0001:
        raise AssertionError(f"preview did not change enough: {delta}")
    return {
        "before": before,
        "after": after,
        "luma_delta": delta,
        "before_png": str(BEFORE_PREVIEW),
        "after_png": str(AFTER_PREVIEW),
    }


select_target()

record(
    "sequencer_sidecar_registration",
    "ui_registration",
    lambda: {
        "panel_space": bpy.types.VIDEO_TOOLKIT_PT_video_filters.bl_space_type,
        "panel_region": bpy.types.VIDEO_TOOLKIT_PT_video_filters.bl_region_type,
        "panel_category": bpy.types.VIDEO_TOOLKIT_PT_video_filters.bl_category,
        "menu_label": bpy.types.VIDEO_TOOLKIT_MT_tools.bl_label,
        "sections": [item[0] for item in SIDECAR_SECTION_ITEMS],
        "groups": list(categories()),
    },
)

for section, _label, _description, _icon, _index in SIDECAR_SECTION_ITEMS:
    record(
        section,
        "sidecar_sections",
        lambda section=section: (
            assert_finished(bpy.ops.video_toolkit.set_sidecar_section(section=section))
            or {"section": scene.video_toolkit_sidecar_section}
        ),
    )

record("strip_edit_controls", "sidecar_controls", strip_control_probe)
record("modifier_stack_controls", "sidecar_controls", live_modifier_control_probe)

for tool in all_tools():
    exercise_catalog_tool(tool)

for tool in all_tools():
    if _tool_has_compositor_stack(tool):
        exercise_tool_nodes(tool)

for group in categories():
    exercise_sidecar_group(group)

for preset_id, label, _description in COLOR_MANAGEMENT_PRESET_ITEMS:
    record(
        preset_id,
        "color_management_presets",
        lambda preset_id=preset_id, label=label: (
            assert_finished(bpy.ops.video_toolkit.apply_color_management_preset(preset_id=preset_id))
            or {"preset": preset_id, "label": label, "summary": scene.video_toolkit_last_color_management}
        ),
    )

workflow_operator(
    "apply_sampled_color_management",
    lambda: bpy.ops.video_toolkit.apply_sampled_color_management(),
    summary_attr="video_toolkit_last_sampled_color_management",
)
workflow_operator("analyze_color_auto", lambda: bpy.ops.video_toolkit.analyze_color(mode="AUTO"), minimum_modifiers=1, summary_attr="video_toolkit_last_analysis")
workflow_operator("analyze_color_palette", lambda: bpy.ops.video_toolkit.analyze_color(mode="PALETTE"), minimum_modifiers=1, summary_attr="video_toolkit_last_analysis")
workflow_operator("analyze_color_match", lambda: bpy.ops.video_toolkit.analyze_color(mode="MATCH"), reference=True, minimum_modifiers=1, summary_attr="video_toolkit_last_analysis")
workflow_operator("color_diagnostics", lambda: bpy.ops.video_toolkit.color_diagnostics(), summary_attr="video_toolkit_last_diagnostics")
workflow_operator("recommend_catalog_recipes", lambda: bpy.ops.video_toolkit.recommend_catalog_recipes(), summary_attr="video_toolkit_last_recipe_recommendations")
workflow_operator("apply_recommended_recipe_mix", lambda: bpy.ops.video_toolkit.apply_recommended_recipe_mix(target="ACTIVE"), minimum_modifiers=1, summary_attr="video_toolkit_last_recommended_recipe_mix")
workflow_operator("create_recommended_recipe_mix_nodes", lambda: bpy.ops.video_toolkit.create_recommended_recipe_mix_nodes(), minimum_nodes=1, summary_attr="video_toolkit_last_compositor_nodes")
workflow_operator("apply_diagnostic_grade", lambda: bpy.ops.video_toolkit.apply_diagnostic_grade(), minimum_modifiers=1, summary_attr="video_toolkit_last_diagnostic_grade")
workflow_operator("apply_sampled_white_balance", lambda: bpy.ops.video_toolkit.apply_sampled_white_balance(), minimum_modifiers=1, summary_attr="video_toolkit_last_sampled_white_balance")
workflow_operator("apply_sampled_levels_gamma", lambda: bpy.ops.video_toolkit.apply_sampled_levels_gamma(), minimum_modifiers=1, summary_attr="video_toolkit_last_sampled_levels_gamma")
workflow_operator("apply_sampled_hue_chroma", lambda: bpy.ops.video_toolkit.apply_sampled_hue_chroma(), minimum_modifiers=1, summary_attr="video_toolkit_last_sampled_hue_chroma")
workflow_operator("apply_sampled_pro_grade", lambda: bpy.ops.video_toolkit.apply_sampled_pro_grade(), minimum_modifiers=1, summary_attr="video_toolkit_last_sampled_pro_grade")
workflow_operator("apply_sampled_color_board", lambda: bpy.ops.video_toolkit.apply_sampled_color_board(target="ACTIVE"), minimum_modifiers=1, minimum_nodes=1, summary_attr="video_toolkit_last_sampled_color_board")
workflow_operator("apply_reference_color_board", lambda: bpy.ops.video_toolkit.apply_reference_color_board(target="ACTIVE"), reference=True, minimum_modifiers=1, minimum_nodes=1, summary_attr="video_toolkit_last_reference_color_board")
workflow_operator("normalize_lighting", lambda: bpy.ops.video_toolkit.normalize_lighting(), minimum_modifiers=1, summary_attr="video_toolkit_last_analysis")
workflow_operator("match_lighting_timeline", lambda: bpy.ops.video_toolkit.match_lighting_timeline(), reference=True, minimum_modifiers=1, summary_attr="video_toolkit_last_analysis")
workflow_operator("match_color_timeline", lambda: bpy.ops.video_toolkit.match_color_timeline(), reference=True, minimum_modifiers=1, summary_attr="video_toolkit_last_analysis")
workflow_operator("translate_ffmpeg_chain", lambda: bpy.ops.video_toolkit.translate_ffmpeg_chain(target="ACTIVE"), minimum_modifiers=1, summary_attr="video_toolkit_last_translation")
workflow_operator("apply_translated_color_workflow", lambda: bpy.ops.video_toolkit.apply_translated_color_workflow(target="ACTIVE"), minimum_modifiers=1, minimum_nodes=1, summary_attr="video_toolkit_last_translated_workflow")
workflow_operator("apply_professional_color_workflow", lambda: bpy.ops.video_toolkit.apply_professional_color_workflow(target="ACTIVE"), minimum_modifiers=1, minimum_nodes=1, summary_attr="video_toolkit_last_professional_workflow")

for stack_type, _label, _description in COMPOSITOR_STACK_ITEMS:
    node_stack_operator(stack_type)

record(
    "create_all_tool_compositor_nodes",
    "workflow_operators",
    lambda: (
        select_target()
        or assert_finished(bpy.ops.video_toolkit.create_all_tool_compositor_nodes())
        or {
            "summary": scene.video_toolkit_last_compositor_nodes,
            "recipe_ids": scene.get("video_toolkit_last_compositor_recipe_ids", ""),
        }
    ),
)
record(
    "write_catalog_coverage_report",
    "workflow_operators",
    lambda: (
        assert_finished(bpy.ops.video_toolkit.write_catalog_coverage_report())
        or {
            "text": scene.video_toolkit_last_catalog_report,
            "characters": len(bpy.data.texts[scene.video_toolkit_last_catalog_report].as_string()),
        }
    ),
)
record(
    "clear_live_modifiers",
    "workflow_operators",
    lambda: (
        select_target()
        or assert_finished(bpy.ops.video_toolkit.apply_filter(filter_id="neutral_grade", target="ACTIVE"))
        or assert_finished(bpy.ops.video_toolkit.clear_live_modifiers())
        or {"remaining_vtk_modifiers": len(vtk_modifiers())}
    ),
)
record(
    "sequencer_preview_live_change",
    "preview_pixels",
    preview_probe,
)

record_note(
    "open_output_folder",
    "headless_ui_limit",
    {
        "reason": "The OS folder launcher is not deterministic in background Blender; output directory creation is verified instead.",
        "output_dir": str(RENDERED_DIR),
        "exists": RENDERED_DIR.exists(),
    },
)

bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

report = {
    "source_video": str(VIDEO),
    "reference_video": str(REFERENCE_VIDEO),
    "blend": str(BLEND_PATH),
    "total_catalog_tools": len(all_tools()),
    "categories": {category: sum(1 for tool in all_tools() if tool.category == category) for category in categories()},
    "compositor_compatible_catalog_tools": sum(1 for tool in all_tools() if _tool_has_compositor_stack(tool)),
    "passed": sum(1 for result in results if result["status"] == "passed"),
    "failed": len(failures),
    "noted": sum(1 for result in results if result["status"] == "noted"),
    "results": results,
    "failures": failures,
}
REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

video_toolkit.unregister()

if failures:
    raise SystemExit(f"{len(failures)} full UI operator matrix failures; see {REPORT_PATH}")
print(json.dumps({"report": str(REPORT_PATH), "passed": report["passed"], "failed": report["failed"]}, indent=2))
'''
    return (
        template.replace("__ROOT__", repr(str(ROOT)))
        .replace("__VIDEO__", repr(str(video)))
        .replace("__REFERENCE_VIDEO__", repr(str(reference_video)))
        .replace("__OUTPUT_DIR__", repr(str(output_dir)))
    )


if __name__ == "__main__":
    raise SystemExit(main())
