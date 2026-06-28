"""Blender UI and operators for Open Research Video Toolkit."""

import traceback
from pathlib import Path

import bpy
from bpy.types import Menu, Operator, Panel

from .catalog import categories, enum_items, get_tool, all_tools
from .color_analysis import (
    build_auto_balance_stack,
    build_color_identity_stack,
    build_color_match_stack,
    build_reference_color_board_stack,
    build_sampled_color_management,
    build_sampled_color_board_stack,
    build_sampled_compositor_grade,
    build_sampled_hue_chroma_stack,
    build_sampled_levels_gamma_stack,
    build_sampled_pro_grade_stack,
    build_sampled_white_balance_stack,
    build_color_timeline_match_keyframes,
    build_lighting_match_keyframes,
    build_lighting_normalization_keyframes,
    diagnose_color,
    sample_video_color_timeline,
    sample_video_luma_timeline,
    sample_video_color,
    summarize_stats,
)
from .compositor import compositor_node_tools
from .ffmpeg_backend import FFmpegError, process_video
from .ffmpeg_native import (
    NATIVE_FFMPEG_COLOR_FILTERS,
    NATIVE_FFMPEG_COLOR_MANAGEMENT_FILTERS,
    NATIVE_FFMPEG_COMPOSITOR_FILTERS,
    NATIVE_FFMPEG_FILTERS,
    translate_filter_chain,
)


PRESET_ITEMS = (
    ("ultrafast", "Ultrafast", "Fastest encode, largest file"),
    ("veryfast", "Very Fast", "Fast preview encode"),
    ("medium", "Medium", "Balanced encode"),
    ("slow", "Slow", "Slower encode, smaller file"),
)

APPLY_TARGET_ITEMS = (
    ("ACTIVE", "Active Strip", "Apply live tools to the active strip"),
    ("SELECTED", "Selected Strips", "Apply live tools to every selected strip that supports modifiers"),
    ("ADJUSTMENT", "Adjustment Layer", "Create a native Blender adjustment strip over the selected range"),
)

COMPOSITOR_STACK_ITEMS = (
    ("COLOR", "Color Node Stack", "Build a Blender compositor color node graph from the active movie strip"),
    ("NATIVE_COLOR_ROOM", "Native Color Room Node Stack", "Build a connected graph of Blender's native compositor color controls"),
    ("SAMPLED_COLOR_MANAGEMENT", "Sampled Color Management Node Stack", "Sample real frames and build a compositor graph for view exposure, gamma, white balance, and display conversion"),
    ("SAMPLED_COLOR_BOARD", "Sampled Color Board Node Stack", "Sample real frames and build a compositor graph from a dynamic primary/secondary color board"),
    ("SAMPLED_COLOR", "Sampled Color Node Stack", "Sample real frames and build a Blender compositor color graph from the measured footage"),
    ("IDENTITY_COLOR", "Palette Identity Node Stack", "Identify dominant colors and build a Blender compositor palette-aware graph"),
    ("MATCHED_COLOR", "Matched Color Node Stack", "Match the active movie strip to a selected reference strip with Blender compositor nodes"),
    ("REFERENCE_COLOR_BOARD", "Reference Color Board Node Stack", "Match the active strip to a selected reference strip with a full color-board compositor graph"),
    ("COLOR_TIMELINE_MATCH", "Color Timeline Match Node Stack", "Sample active/reference RGB over time and animate Blender compositor color balance"),
    ("DIAGNOSTIC_COLOR", "Diagnostic Grade Node Stack", "Diagnose real frames and build the recommended Blender compositor color graph"),
    ("TRANSLATED_COLOR", "Translated Color Node Stack", "Translate the FFmpeg-style color chain into a Blender compositor graph"),
    ("LIGHTING_NORMALIZE", "Lighting Normalize Node Stack", "Sample luma over time and animate Blender compositor brightness correction"),
    ("RESTORATION", "Restoration Node Stack", "Build a Blender compositor restoration node graph from the active movie strip"),
    ("NODE_LIBRARY", "Native Node Library", "Create every tracked Blender compositor video-finishing node in organized groups"),
)

COMPOSITOR_MODIFIER_TYPES = frozenset(
    {
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "CURVES",
        "HUE_CORRECT",
        "TONEMAP",
        "WHITE_BALANCE",
    }
)

COLOR_MANAGEMENT_PRESET_ITEMS = (
    ("AGX_BALANCED", "AgX Balanced", "AgX view transform with a moderate editorial contrast look"),
    ("AGX_PUNCH", "AgX Punch", "AgX with a stronger contrast look and tiny exposure lift"),
    ("FILMIC_SOFT", "Filmic Soft", "Filmic-style softer review transform for highlight-safe grading"),
    ("STANDARD_VIDEO", "Standard Video", "Standard display transform for direct Rec.709-style review"),
    ("WARM_REVIEW", "Warm Review", "Native Color Management white-balance warm review preset"),
    ("VIEW_CURVE_CONTRAST", "View Curve Contrast", "Enable Blender view curve mapping with a gentle S-curve"),
)

SIDECAR_GROUP_ICONS = {
    "Live Blender Color": "COLOR",
    "Native Blender Primitives": "PROPERTIES",
    "Native Color & Composite": "NODETREE",
    "Native Matte & Channel": "NODETREE",
    "Native Filter & Blur": "NODETREE",
    "Native Visual FX Nodes": "NODETREE",
    "Native Analysis & Utility": "NODETREE",
    "Native Source & Output": "NODETREE",
    "Native Denoise & Cleanup": "NODETREE",
    "Native Geometry & Lens": "NODETREE",
    "Live Blender Modifiers": "MODIFIER",
    "Restoration": "RENDER_ANIMATION",
    "Resolution & Motion": "RENDER_ANIMATION",
}

SIDECAR_SECTION_ITEMS = (
    ("BROWSER", "Tools", "Video effect browser", "TOOL_SETTINGS", 0),
    ("ENHANCE", "Enhance", "One-click sampled and recommended video enhancements", "COLOR", 1),
    ("ANALYSIS", "Analyze", "Sample frames, diagnose color, and match lighting or color", "EYEDROPPER", 2),
    ("COLOR", "Color Mgmt", "Blender scene and view color-management controls", "WORLD", 3),
    ("COMPOSITOR", "Nodes", "Native Blender compositor node stacks and recipe graphs", "NODETREE", 4),
    ("LIVE", "Live", "Live Blender color tools and FFmpeg-style native color translation", "COLOR", 5),
    ("STRIP", "Strip", "Selected strip transform, crop, opacity, and lock controls", "SEQ_STRIP_META", 6),
    ("MODIFIERS", "Modifiers", "Editable VSE live modifier stack for the selected strip", "MODIFIER", 7),
    ("RENDER", "Render", "Rendered restoration, scaling, motion, and output settings", "RENDER_ANIMATION", 8),
)

LIVE_COLOR_SIDECAR_CATEGORIES = (
    "Live Blender Color",
    "Native Blender Primitives",
    "Native Color & Composite",
    "Live Blender Modifiers",
)

COMPOSITOR_NODE_CONTROL_PROPS = {
    "CompositorNodeConvertColorSpace": ("from_color_space", "to_color_space"),
    "CompositorNodeSeparateColor": ("mode", "ycc_mode"),
    "CompositorNodeCombineColor": ("mode", "ycc_mode"),
}
COMPOSITOR_CURVE_NODE_TYPES = {"CompositorNodeCurveRGB", "CompositorNodeHueCorrect"}
COMPOSITOR_CONTROL_SKIP_INPUTS = {
    "Image",
    "Image 1",
    "Image 2",
    "Background",
    "Foreground",
}


def _enum_key(value: str) -> str:
    cleaned = "".join(ch.upper() if ch.isalnum() else "_" for ch in value).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "TOOLS"


SIDECAR_GROUP_BY_KEY = {_enum_key(category): category for category in categories()}
SIDECAR_GROUP_ITEMS = tuple(
    (
        key,
        category,
        f"{sum(1 for tool in all_tools() if tool.category == category)} video tools",
        SIDECAR_GROUP_ICONS.get(category, "TOOL_SETTINGS"),
        index,
    )
    for index, (key, category) in enumerate(SIDECAR_GROUP_BY_KEY.items())
)


def _tool_items(_self, _context):
    return enum_items()


def _sidecar_group_name(scene) -> str:
    key = getattr(scene, "video_toolkit_sidecar_group", "")
    return SIDECAR_GROUP_BY_KEY.get(key) or next(iter(SIDECAR_GROUP_BY_KEY.values()), "")


def _sidecar_tools_for_scene(scene):
    group = _sidecar_group_name(scene)
    return tuple(tool for tool in all_tools() if tool.category == group)


def _sidecar_tool_items(self, context):
    scene = self if hasattr(self, "video_toolkit_sidecar_group") else getattr(context, "scene", None)
    tools = _sidecar_tools_for_scene(scene) if scene is not None else ()
    if not tools:
        return [("none", "No tools", "No tools are available in this group", "ERROR", 0)]
    return [
        (tool.id, tool.label, tool.description, _sidecar_tool_icon(tool), index)
        for index, tool in enumerate(tools)
    ]


def _selected_sidecar_tool(scene):
    tools = _sidecar_tools_for_scene(scene)
    selected = getattr(scene, "video_toolkit_sidecar_tool", "")
    for tool in tools:
        if tool.id == selected:
            return tool
    return tools[0] if tools else None


def _sync_sidecar_tool_to_group(self, _context) -> None:
    tool = _selected_sidecar_tool(self)
    if tool is not None and getattr(self, "video_toolkit_sidecar_tool", "") != tool.id:
        self.video_toolkit_sidecar_tool = tool.id


def _sidecar_tool_icon(tool) -> str:
    if tool is None:
        return "ERROR"
    if tool.is_blender_modifier:
        return "MODIFIER"
    if tool.is_ffmpeg:
        return "RENDER_ANIMATION"
    if tool.is_compositor:
        return "NODETREE"
    return "TOOL_SETTINGS"


def _tool_compositor_stack(tool):
    if tool.blender_stack:
        return tool.blender_stack
    if tool.blender_modifier:
        return ((tool.blender_modifier, tool.blender_settings),)
    return ()


def _tool_compositor_filter_stack(tool):
    return getattr(tool, "compositor_stack", ())


def _tool_has_compositor_stack(tool) -> bool:
    if _tool_compositor_filter_stack(tool):
        return True
    if not tool.is_blender_modifier:
        return False
    return any(modifier_type in COMPOSITOR_MODIFIER_TYPES for modifier_type, _settings in _tool_compositor_stack(tool))


def _tool_modifier_names(tool) -> tuple[str, ...]:
    return tuple(modifier_type for modifier_type, _settings in _tool_compositor_stack(tool))


def _compositor_tool_items(_self, _context):
    return tuple(
        (tool.id, tool.label, f"Create a Blender compositor graph for {tool.label}")
        for tool in all_tools()
        if _tool_has_compositor_stack(tool)
    )


class VIDEO_TOOLKIT_OT_apply_filter(Operator):
    bl_idname = "video_toolkit.apply_filter"
    bl_label = "Apply Video Filter"
    bl_description = "Apply a one-click video enhancement or restoration tool"
    bl_options = {"REGISTER", "UNDO"}

    filter_id: bpy.props.EnumProperty(name="Filter", items=_tool_items)
    target: bpy.props.EnumProperty(
        name="Target",
        items=(("SCENE", "Panel Target", "Use the panel target setting"),) + APPLY_TARGET_ITEMS,
        default="SCENE",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        return bool(editor and editor.active_strip)

    def execute(self, context):
        try:
            tool = get_tool(self.filter_id)
            strip = context.scene.sequence_editor.active_strip
            if tool.is_blender_modifier:
                target = self.target
                if target == "SCENE":
                    target = context.scene.video_toolkit_apply_target
                color_management = _apply_tool_color_management(context, tool)
                if target == "ADJUSTMENT":
                    adjustment = _create_adjustment_strip(context, tool.label)
                    modifiers = _add_blender_tool(adjustment, tool)
                    self.report(
                        {"INFO"},
                        f"Added {len(modifiers)} live Blender modifier(s) to adjustment layer {adjustment.name}",
                    )
                elif target == "SELECTED":
                    strips = _selected_modifier_strips(context) or [strip]
                    count = 0
                    for selected_strip in strips:
                        count += len(_add_blender_tool(selected_strip, tool))
                    self.report({"INFO"}, f"Added {count} live Blender modifier(s) to {len(strips)} strip(s)")
                else:
                    modifiers = _add_blender_tool(strip, tool)
                    self.report({"INFO"}, f"Added {len(modifiers)} live Blender modifier(s) to {strip.name}")
                if color_management:
                    self.report({"INFO"}, f"{tool.label} color management: {', '.join(color_management)}")
                return {"FINISHED"}
            if tool.is_compositor:
                if strip.type != "MOVIE":
                    raise RuntimeError("Native compositor tools require an active movie strip")
                if not _tool_has_compositor_stack(tool):
                    raise RuntimeError(f"{tool.label} does not have a compositor node recipe")
                stack = _tool_compositor_stack(tool)
                compositor_stack = _tool_compositor_filter_stack(tool)
                created = _create_tool_compositor_color_stack(context.scene, strip, tool, stack, compositor_stack)
                color_management = _apply_tool_color_management(context, tool)
                context.scene.video_toolkit_last_compositor_nodes = (
                    f"tool compositor {tool.label}: {_compositor_node_summary(created)}"
                )
                if color_management:
                    context.scene.video_toolkit_last_compositor_nodes += (
                        f"; color management: {', '.join(color_management)}"
                    )
                self.report({"INFO"}, f"Created {len(created)} Blender compositor {tool.label} node(s)")
                return {"FINISHED"}
            output_path = _render_ffmpeg_tool(context, strip, tool)
            self.report({"INFO"}, f"Rendered {tool.label}: {output_path}")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_sidecar_tool(Operator):
    bl_idname = "video_toolkit.apply_sidecar_tool"
    bl_label = "Apply Video Effect"
    bl_description = "Apply the selected Video Effects sidebar tool to the active Sequencer strip"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        return bool(editor and editor.active_strip)

    def execute(self, context):
        tool = _selected_sidecar_tool(context.scene)
        if tool is None:
            self.report({"ERROR"}, "No Video Effects tool is selected")
            return {"CANCELLED"}
        return bpy.ops.video_toolkit.apply_filter(filter_id=tool.id, target="SCENE")


class VIDEO_TOOLKIT_OT_set_sidecar_section(Operator):
    bl_idname = "video_toolkit.set_sidecar_section"
    bl_label = "Show Video Effects Section"
    bl_description = "Switch the active mini tab in the Video Effects sidebar"
    bl_options = {"REGISTER"}

    section: bpy.props.EnumProperty(name="Section", items=SIDECAR_SECTION_ITEMS)

    def execute(self, context):
        context.scene.video_toolkit_sidecar_section = self.section
        return {"FINISHED"}


class VIDEO_TOOLKIT_OT_analyze_color(Operator):
    bl_idname = "video_toolkit.analyze_color"
    bl_label = "Analyze Color"
    bl_description = "Sample real video frames and create live Blender color modifiers"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("AUTO", "Auto Balance", "Balance the active strip against a neutral Rec.709-style target"),
            ("MATCH", "Match Selected", "Match the active movie strip to another selected movie strip"),
            ("PALETTE", "Identify Colors", "Identify dominant colors and build a live palette-aware grade"),
        ),
        default="AUTO",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            scene = context.scene
            active = scene.sequence_editor.active_strip
            active_path = _movie_path(active)
            target_stats = sample_video_color(active_path, max_samples=scene.video_toolkit_analysis_samples)
            if self.mode == "MATCH":
                reference = _reference_movie_strip(context, active)
                if reference is None:
                    raise RuntimeError("Select a reference movie strip as well as the active target strip")
                reference_stats = sample_video_color(
                    _movie_path(reference),
                    max_samples=scene.video_toolkit_analysis_samples,
                )
                stack = build_color_match_stack(target_stats, reference_stats)
                label = f"Frame Match to {reference.name}"
                summary = f"{summarize_stats(target_stats)} -> {summarize_stats(reference_stats)}"
            elif self.mode == "PALETTE":
                stack = build_color_identity_stack(target_stats)
                label = "Frame Color Identity"
                summary = summarize_stats(target_stats)
            else:
                stack = build_auto_balance_stack(target_stats)
                label = "Frame Auto Balance"
                summary = summarize_stats(target_stats)
            modifiers = _add_blender_stack(active, stack, label)
            scene.video_toolkit_last_analysis = summary
            self.report({"INFO"}, f"Added {len(modifiers)} live modifiers from {summary}")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_color_diagnostics(Operator):
    bl_idname = "video_toolkit.color_diagnostics"
    bl_label = "Color Diagnostics"
    bl_description = "Sample real frames and write a professional color diagnostics report"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            diagnosis = diagnose_color(stats)
            text = _write_diagnostics_text(strip, diagnosis.report)
            scene.video_toolkit_last_diagnostics = diagnosis.summary
            scene.video_toolkit_last_diagnostics_text = text.name
            self.report({"INFO"}, f"{diagnosis.summary}; report {text.name}")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_recommend_catalog_recipes(Operator):
    bl_idname = "video_toolkit.recommend_catalog_recipes"
    bl_label = "Recommend Color Recipes"
    bl_description = "Sample real frames and rank Blender-native color tools against the selected footage"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            diagnosis = diagnose_color(stats)
            recommendations = _rank_catalog_recipes(stats, diagnosis)
            if not recommendations:
                raise RuntimeError("No Blender-native color recipes were available for recommendation")
            text = _write_recipe_recommendation_text(strip, stats, diagnosis, recommendations)
            top_score, top_tool, _top_reasons = recommendations[0]
            scene.video_toolkit_last_recipe_recommendations = text.name
            scene["video_toolkit_last_recommended_recipe_ids"] = ",".join(
                tool.id for _score, tool, _reasons in recommendations[:12]
            )
            scene.video_toolkit_sidecar_group = _enum_key(top_tool.category)
            scene.video_toolkit_sidecar_tool = top_tool.id
            self.report({"INFO"}, f"recommended {top_tool.label} ({top_score:.0f}); report {text.name}")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_recommended_recipe_mix(Operator):
    bl_idname = "video_toolkit.apply_recommended_recipe_mix"
    bl_label = "Apply Recommended Recipe Mix"
    bl_description = "Sample real frames and apply a blended stack from the top-ranked native Blender color recipes"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="Target",
        items=(("SCENE", "Panel Target", "Use the panel target setting"),) + APPLY_TARGET_ITEMS,
        default="SCENE",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            diagnosis = diagnose_color(stats)
            recommendations = _rank_catalog_recipes(stats, diagnosis)
            if not recommendations:
                raise RuntimeError("No Blender-native color recipes were available for recommendation")
            text = _write_recipe_recommendation_text(strip, stats, diagnosis, recommendations)
            count = max(1, min(scene.video_toolkit_recommendation_mix_count, len(recommendations)))
            stack, labels, recipe_ids = _recommended_recipe_mix_stack(recommendations, count)
            if not stack:
                raise RuntimeError("Recommended recipes did not contain any live Blender modifiers")
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Recommended Recipe Mix", self.target)
            scene.video_toolkit_last_recipe_recommendations = text.name
            scene.video_toolkit_last_recommended_recipe_mix = (
                f"recommended recipe mix {len(modifiers)} modifier(s) on {len(targets)} target(s): "
                f"{', '.join(labels)}"
            )
            scene["video_toolkit_last_recommended_recipe_ids"] = ",".join(
                tool.id for _score, tool, _reasons in recommendations[:12]
            )
            scene["video_toolkit_last_recommended_recipe_mix_ids"] = ",".join(recipe_ids)
            top_tool = recommendations[0][1]
            scene.video_toolkit_sidecar_group = _enum_key(top_tool.category)
            scene.video_toolkit_sidecar_tool = top_tool.id
            self.report({"INFO"}, scene.video_toolkit_last_recommended_recipe_mix)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_diagnostic_grade(Operator):
    bl_idname = "video_toolkit.apply_diagnostic_grade"
    bl_label = "Apply Diagnostic Grade"
    bl_description = "Sample the selected video, diagnose color issues, and apply recommended native Blender live tools"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            diagnosis = diagnose_color(stats)
            text = _write_diagnostics_text(strip, diagnosis.report)
            stack, labels = _diagnostic_recommended_stack(diagnosis)
            if not stack:
                raise RuntimeError("No live Blender diagnostic tools were available for this diagnosis")
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Diagnostic Grade")
            scene.video_toolkit_last_diagnostics = diagnosis.summary
            scene.video_toolkit_last_diagnostics_text = text.name
            scene.video_toolkit_last_diagnostic_grade = (
                f"diagnostic grade {len(modifiers)} modifier(s) on {len(targets)} target(s): {', '.join(labels)}"
            )
            self.report({"INFO"}, scene.video_toolkit_last_diagnostic_grade)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_sampled_white_balance(Operator):
    bl_idname = "video_toolkit.apply_sampled_white_balance"
    bl_label = "Sampled White Balance"
    bl_description = "Sample real frames and create editable Blender modifiers that neutralize color cast"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            stack = build_sampled_white_balance_stack(stats)
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Sampled White Balance")
            white_value = stack[0][1]["white_value"]
            scene.video_toolkit_last_sampled_white_balance = (
                f"sampled white balance {len(modifiers)} modifier(s) on {len(targets)} target(s), "
                f"RGB {stats.mean_r:.1f}/{stats.mean_g:.1f}/{stats.mean_b:.1f}, "
                f"white {white_value[0]:.2f}/{white_value[1]:.2f}/{white_value[2]:.2f}"
            )
            self.report({"INFO"}, scene.video_toolkit_last_sampled_white_balance)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma(Operator):
    bl_idname = "video_toolkit.apply_sampled_levels_gamma"
    bl_label = "Sampled Levels & Gamma"
    bl_description = "Sample real frames and normalize black point, white point, midtone gamma, and contrast with live Blender modifiers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            stack = build_sampled_levels_gamma_stack(stats)
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Sampled Levels Gamma")
            color_balance = stack[1][1]
            gamma = color_balance["color_balance.gamma"][0]
            scene.video_toolkit_last_sampled_levels_gamma = (
                f"sampled levels/gamma {len(modifiers)} modifier(s) on {len(targets)} target(s), "
                f"luma {stats.luma_p05:.1f}/{stats.mean_luma:.1f}/{stats.luma_p95:.1f}, gamma {gamma:.2f}"
            )
            self.report({"INFO"}, scene.video_toolkit_last_sampled_levels_gamma)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma(Operator):
    bl_idname = "video_toolkit.apply_sampled_hue_chroma"
    bl_label = "Sampled Hue & Chroma"
    bl_description = "Sample real frames and balance dominant hue zones, saturation, and chroma with live Blender modifiers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            stack = build_sampled_hue_chroma_stack(stats)
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Sampled Hue Chroma")
            scene.video_toolkit_last_sampled_hue_chroma = (
                f"sampled hue/chroma {len(modifiers)} modifier(s) on {len(targets)} target(s), "
                f"sat/chroma {stats.mean_saturation:.2f}/{stats.mean_chroma:.1f}, "
                f"warm/cool/skin {stats.warm_ratio:.2f}/{stats.cool_ratio:.2f}/{stats.skin_ratio:.2f}"
            )
            self.report({"INFO"}, scene.video_toolkit_last_sampled_hue_chroma)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_sampled_pro_grade(Operator):
    bl_idname = "video_toolkit.apply_sampled_pro_grade"
    bl_label = "Sampled Pro Grade"
    bl_description = "Sample real frames and apply a complete editable Blender-native finishing stack"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            stack = build_sampled_pro_grade_stack(stats)
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Sampled Pro Grade")
            scene.video_toolkit_last_sampled_pro_grade = (
                f"sampled pro grade {len(modifiers)} modifier(s) on {len(targets)} target(s), "
                f"RGB {stats.mean_r:.1f}/{stats.mean_g:.1f}/{stats.mean_b:.1f}, "
                f"luma {stats.luma_p05:.1f}/{stats.mean_luma:.1f}/{stats.luma_p95:.1f}"
            )
            self.report({"INFO"}, scene.video_toolkit_last_sampled_pro_grade)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_sampled_color_board(Operator):
    bl_idname = "video_toolkit.apply_sampled_color_board"
    bl_label = "Sampled Color Board"
    bl_description = "Sample real frames and apply a dynamic primary/secondary Blender color-board stack plus compositor nodes"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="Target",
        items=(("SCENE", "Panel Target", "Use the panel target setting"),) + APPLY_TARGET_ITEMS,
        default="SCENE",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            stack = build_sampled_color_board_stack(stats)
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Sampled Color Board", self.target)
            nodes = _create_compositor_nodes_from_blender_stack(scene, strip, stack, "Sampled Color Board")
            for node in nodes:
                node["video_toolkit_sampled_color_board"] = summarize_stats(stats)
                node["video_toolkit_source_strip"] = strip.name
            scene.video_toolkit_last_sampled_color_board = (
                f"sampled color board {stats.samples} frames, {len(modifiers)} modifier(s), {len(nodes)} node(s), "
                f"RGB {stats.mean_r:.1f}/{stats.mean_g:.1f}/{stats.mean_b:.1f}, "
                f"luma {stats.luma_p05:.1f}/{stats.mean_luma:.1f}/{stats.luma_p95:.1f}, "
                f"sat/chroma {stats.mean_saturation:.2f}/{stats.mean_chroma:.1f}"
            )
            scene.video_toolkit_last_compositor_nodes = (
                f"sampled color board nodes {len(nodes)} node(s): {_compositor_node_summary(nodes)}"
            )
            scene["video_toolkit_last_sampled_color_board_node_count"] = len(nodes)
            scene["video_toolkit_last_sampled_color_board_modifier_count"] = len(modifiers)
            self.report({"INFO"}, scene.video_toolkit_last_sampled_color_board)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_reference_color_board(Operator):
    bl_idname = "video_toolkit.apply_reference_color_board"
    bl_label = "Reference Color Board"
    bl_description = "Match the active movie strip to another selected reference strip with editable live Blender color-board modifiers"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="Target",
        items=APPLY_TARGET_ITEMS,
        default="ACTIVE",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            active = scene.sequence_editor.active_strip
            reference = _reference_movie_strip(context, active)
            if reference is None:
                raise RuntimeError("Select a reference movie strip as well as the active target strip")
            target_stats = sample_video_color(_movie_path(active), max_samples=scene.video_toolkit_analysis_samples)
            reference_stats = sample_video_color(
                _movie_path(reference),
                max_samples=scene.video_toolkit_analysis_samples,
            )
            stack = build_reference_color_board_stack(target_stats, reference_stats)
            modifiers, targets = _add_blender_stack_for_target(context, stack, "Reference Color Board", self.target)
            nodes = _create_compositor_nodes_from_blender_stack(scene, active, stack, "Reference Color Board")
            for node in nodes:
                node["video_toolkit_reference_strip"] = reference.name
                node["video_toolkit_source_strip"] = active.name
                node["video_toolkit_target_stats"] = summarize_stats(target_stats)
                node["video_toolkit_reference_stats"] = summarize_stats(reference_stats)
            scene.video_toolkit_last_reference_color_board = (
                f"reference color board to {reference.name}, {target_stats.samples}/{reference_stats.samples} frames, "
                f"{len(modifiers)} modifier(s) on {len(targets)} target(s), {len(nodes)} node(s): "
                f"{summarize_stats(target_stats)} -> {summarize_stats(reference_stats)}"
            )
            scene.video_toolkit_last_compositor_nodes = (
                f"reference color board nodes {len(nodes)} node(s): {_compositor_node_summary(nodes)}"
            )
            scene["video_toolkit_last_reference_color_board_node_count"] = len(nodes)
            scene["video_toolkit_last_reference_color_board_modifier_count"] = len(modifiers)
            scene["video_toolkit_last_reference_color_board_reference"] = reference.name
            self.report({"INFO"}, scene.video_toolkit_last_reference_color_board)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_normalize_lighting(Operator):
    bl_idname = "video_toolkit.normalize_lighting"
    bl_label = "Normalize Lighting Flicker"
    bl_description = "Sample luma over time and create live keyframed Blender brightness correction"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            samples = sample_video_luma_timeline(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            keyframes = build_lighting_normalization_keyframes(
                samples,
                smoothing=scene.video_toolkit_flicker_smoothing,
                strength=scene.video_toolkit_flicker_strength,
            )
            if not keyframes:
                raise RuntimeError("No lighting samples were available for normalization")
            modifier = _add_blender_modifier(
                strip,
                "BRIGHT_CONTRAST",
                {"bright": keyframes[0][1], "contrast": 0.0},
                "Live Flicker Normalizer",
            )
            inserted = _insert_modifier_keyframes(strip, modifier, keyframes, "bright")
            scene.video_toolkit_last_analysis = (
                f"lighting keyframes {inserted}, luma {min(sample.luma for sample in samples):.1f}-"
                f"{max(sample.luma for sample in samples):.1f}, smoothing {scene.video_toolkit_flicker_smoothing}, "
                f"strength {scene.video_toolkit_flicker_strength:.2f}"
            )
            self.report({"INFO"}, f"Added live flicker normalizer with {inserted} keyframes")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_match_lighting_timeline(Operator):
    bl_idname = "video_toolkit.match_lighting_timeline"
    bl_label = "Match Lighting Timeline"
    bl_description = "Match active strip lighting over time to another selected movie strip with live Blender keyframes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            active = scene.sequence_editor.active_strip
            reference = _reference_movie_strip(context, active)
            if reference is None:
                raise RuntimeError("Select a reference movie strip as well as the active target strip")
            target_samples = sample_video_luma_timeline(_movie_path(active), max_samples=scene.video_toolkit_analysis_samples)
            reference_samples = sample_video_luma_timeline(_movie_path(reference), max_samples=scene.video_toolkit_analysis_samples)
            keyframes = build_lighting_match_keyframes(
                target_samples,
                reference_samples,
                smoothing=scene.video_toolkit_match_smoothing,
                strength=scene.video_toolkit_match_strength,
            )
            if not keyframes:
                raise RuntimeError("No lighting samples were available for timeline matching")
            modifier = _add_blender_modifier(
                active,
                "BRIGHT_CONTRAST",
                {"bright": keyframes[0][1], "contrast": 0.0},
                f"Live Timeline Match to {reference.name}",
            )
            inserted = _insert_modifier_keyframes(active, modifier, keyframes, "bright")
            scene.video_toolkit_last_analysis = (
                f"timeline match keyframes {inserted}, target luma "
                f"{min(sample.luma for sample in target_samples):.1f}-{max(sample.luma for sample in target_samples):.1f}, "
                f"reference {min(sample.luma for sample in reference_samples):.1f}-{max(sample.luma for sample in reference_samples):.1f}"
            )
            self.report({"INFO"}, f"Added live timeline match with {inserted} keyframes")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_match_color_timeline(Operator):
    bl_idname = "video_toolkit.match_color_timeline"
    bl_label = "Match Color Timeline"
    bl_description = "Match active strip RGB color over time to another selected movie strip with live Blender Color Balance keyframes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            active = scene.sequence_editor.active_strip
            reference = _reference_movie_strip(context, active)
            if reference is None:
                raise RuntimeError("Select a reference movie strip as well as the active target strip")
            target_samples = sample_video_color_timeline(_movie_path(active), max_samples=scene.video_toolkit_analysis_samples)
            reference_samples = sample_video_color_timeline(_movie_path(reference), max_samples=scene.video_toolkit_analysis_samples)
            keyframes = build_color_timeline_match_keyframes(
                target_samples,
                reference_samples,
                smoothing=scene.video_toolkit_color_match_smoothing,
                strength=scene.video_toolkit_color_match_strength,
            )
            if not keyframes:
                raise RuntimeError("No color samples were available for timeline matching")
            modifier = _add_blender_modifier(
                active,
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.gamma": keyframes[0].gamma,
                    "color_balance.gain": keyframes[0].gain,
                },
                f"Live Color Timeline Match to {reference.name}",
            )
            gamma_count = _insert_color_balance_keyframes(active, modifier, keyframes, "gamma")
            gain_count = _insert_color_balance_keyframes(active, modifier, keyframes, "gain")
            scene.video_toolkit_last_analysis = (
                f"color timeline match keyframes gamma {gamma_count}, gain {gain_count}, "
                f"target RGB {_timeline_rgb_summary(target_samples)}, reference {_timeline_rgb_summary(reference_samples)}"
            )
            self.report({"INFO"}, f"Added live color timeline match with {gamma_count} gamma keyframes")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_translate_ffmpeg_chain(Operator):
    bl_idname = "video_toolkit.translate_ffmpeg_chain"
    bl_label = "Translate Color Chain to Live Blender Stack"
    bl_description = "Convert supported FFmpeg-style color filters into editable live Blender VSE modifiers"
    bl_options = {"REGISTER", "UNDO"}

    chain: bpy.props.StringProperty(
        name="Color Chain",
        description="FFmpeg-style color filter chain to translate into native Blender VSE modifiers",
        default="",
    )
    target: bpy.props.EnumProperty(
        name="Target",
        items=(("SCENE", "Panel Target", "Use the panel target setting"),) + APPLY_TARGET_ITEMS,
        default="SCENE",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            chain = (self.chain or scene.video_toolkit_ffmpeg_chain).strip()
            if not chain:
                raise RuntimeError("Enter an FFmpeg-style color chain before translating")
            translation = translate_filter_chain(chain)
            if not translation.stack and not translation.compositor_nodes and not translation.color_management:
                unsupported = ", ".join(translation.unsupported_filters) or "none"
                raise RuntimeError(f"No native Blender live color stack could be built. Unsupported: {unsupported}")
            modifiers, targets = [], []
            if translation.stack:
                modifiers, targets = _add_blender_stack_for_target(
                    context,
                    translation.stack,
                    "Translated Color Chain",
                    self.target,
                )
            color_management = _apply_translation_color_management(context, translation)
            scene.video_toolkit_last_translation = _translation_summary(
                translation,
                len(modifiers),
                len(targets),
                color_management,
            )
            self.report({"INFO"}, scene.video_toolkit_last_translation)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_translated_color_workflow(Operator):
    bl_idname = "video_toolkit.apply_translated_color_workflow"
    bl_label = "Apply FFmpeg Color Workflow"
    bl_description = "Translate an FFmpeg-style color chain into Blender live modifiers, Color Management, and compositor nodes"
    bl_options = {"REGISTER", "UNDO"}

    chain: bpy.props.StringProperty(
        name="Color Chain",
        description="FFmpeg-style color filter chain to translate into native Blender tools",
        default="",
    )
    target: bpy.props.EnumProperty(
        name="Target",
        items=(("SCENE", "Panel Target", "Use the panel target setting"),) + APPLY_TARGET_ITEMS,
        default="SCENE",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            chain = (self.chain or scene.video_toolkit_ffmpeg_chain).strip()
            if not chain:
                raise RuntimeError("Enter an FFmpeg-style color chain before running the workflow")
            translation = translate_filter_chain(chain)
            if not translation.stack and not translation.compositor_nodes and not translation.color_management:
                unsupported = ", ".join(translation.unsupported_filters) or "none"
                raise RuntimeError(f"No native Blender color workflow could be built. Unsupported: {unsupported}")

            modifiers, targets, nodes = [], [], []
            if translation.stack:
                modifiers, targets = _add_blender_stack_for_target(
                    context,
                    translation.stack,
                    "Translated Color Workflow",
                    self.target,
                )
            if translation.stack or translation.compositor_nodes:
                nodes = _create_translated_compositor_color_stack(
                    scene,
                    strip,
                    translation,
                    label_prefix="Translated Color Workflow",
                )
            color_management = _apply_translation_color_management(context, translation)
            for node in nodes:
                node["video_toolkit_ffmpeg_supported_filters"] = ",".join(translation.supported_filters)
                node["video_toolkit_ffmpeg_unsupported_filters"] = ",".join(translation.unsupported_filters)
                node["video_toolkit_ffmpeg_chain"] = chain
                node["video_toolkit_source_strip"] = strip.name

            scene.video_toolkit_last_translation = _translation_summary(
                translation,
                len(modifiers),
                len(targets),
                color_management,
            )
            scene.video_toolkit_last_compositor_nodes = _translated_compositor_summary(
                translation,
                len(nodes),
                color_management,
            )
            supported = ", ".join(translation.supported_filters) or "none"
            unsupported = ", ".join(translation.unsupported_filters)
            scene.video_toolkit_last_translated_workflow = (
                f"translated color workflow {len(translation.supported_filters)} filter(s), "
                f"{len(modifiers)} modifier(s), {len(nodes)} node(s): {supported}"
            )
            if color_management:
                scene.video_toolkit_last_translated_workflow += f"; color management {', '.join(color_management)}"
            if unsupported:
                scene.video_toolkit_last_translated_workflow += f"; rendered-only/not native {unsupported}"
            scene["video_toolkit_last_translated_workflow_supported_filters"] = ",".join(translation.supported_filters)
            scene["video_toolkit_last_translated_workflow_unsupported_filters"] = ",".join(translation.unsupported_filters)
            scene["video_toolkit_last_translated_workflow_node_count"] = len(nodes)
            self.report({"INFO"}, scene.video_toolkit_last_translated_workflow)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_clear_live_modifiers(Operator):
    bl_idname = "video_toolkit.clear_live_modifiers"
    bl_label = "Clear Video Toolkit Modifiers"
    bl_description = "Remove live modifiers added by Video Toolkit from the active strip"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and hasattr(strip, "modifiers"))

    def execute(self, context):
        strip = context.scene.sequence_editor.active_strip
        removed = 0
        for modifier in reversed(list(strip.modifiers)):
            if modifier.name.startswith("VTK "):
                strip.modifiers.remove(modifier)
                removed += 1
        self.report({"INFO"}, f"Removed {removed} Video Toolkit modifier(s)")
        return {"FINISHED"}


class VIDEO_TOOLKIT_OT_create_compositor_nodes(Operator):
    bl_idname = "video_toolkit.create_compositor_nodes"
    bl_label = "Create Compositor Nodes"
    bl_description = "Create a Blender-native compositor node stack from the active movie strip"
    bl_options = {"REGISTER", "UNDO"}

    stack_type: bpy.props.EnumProperty(name="Stack", items=COMPOSITOR_STACK_ITEMS, default="COLOR")

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            strip = context.scene.sequence_editor.active_strip
            summary = None
            if self.stack_type == "NODE_LIBRARY":
                created = _create_compositor_node_library(context.scene, strip)
                label = "native node library"
            elif self.stack_type == "RESTORATION":
                created = _create_compositor_restoration_stack(context.scene, strip)
                label = "restoration"
            elif self.stack_type == "NATIVE_COLOR_ROOM":
                created = _create_native_color_room_compositor_stack(context.scene, strip)
                label = "native color room"
                summary = f"native color room graph; {_compositor_node_summary(created)}"
            elif self.stack_type == "SAMPLED_COLOR_MANAGEMENT":
                stats = sample_video_color(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                profile = build_sampled_color_management(stats)
                created = _create_sampled_color_management_compositor_stack(context.scene, strip, profile)
                label = "sampled color management"
                summary = (
                    f"{profile.summary}, view {profile.view_transform_candidates[0]}, "
                    f"look {profile.look_candidates[0]}, input {profile.sequencer_input}; "
                    f"{_compositor_node_summary(created)}"
                )
            elif self.stack_type == "SAMPLED_COLOR_BOARD":
                stats = sample_video_color(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                stack = build_sampled_color_board_stack(stats)
                created = _create_compositor_nodes_from_blender_stack(context.scene, strip, stack, "Sampled Color Board")
                label = "sampled color board"
                summary = f"sampled color board compositor {summarize_stats(stats)}; {_compositor_node_summary(created)}"
            elif self.stack_type == "SAMPLED_COLOR":
                stats = sample_video_color(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                profile = build_sampled_compositor_grade(stats)
                created = _create_sampled_compositor_color_stack(context.scene, strip, profile)
                label = "sampled color"
                summary = f"{profile.summary}; {_compositor_node_summary(created)}"
            elif self.stack_type == "IDENTITY_COLOR":
                stats = sample_video_color(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                stack = build_color_identity_stack(stats)
                created = _create_identity_compositor_color_stack(context.scene, strip, stack)
                label = "palette identity"
                summary = f"palette compositor {summarize_stats(stats)}; {_compositor_node_summary(created)}"
            elif self.stack_type == "MATCHED_COLOR":
                reference = _reference_movie_strip(context, strip)
                if reference is None:
                    raise RuntimeError("Select a reference movie strip as well as the active target strip")
                target_stats = sample_video_color(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                reference_stats = sample_video_color(
                    _movie_path(reference),
                    max_samples=context.scene.video_toolkit_analysis_samples,
                )
                stack = build_color_match_stack(target_stats, reference_stats)
                created = _create_matched_compositor_color_stack(context.scene, strip, stack, reference.name)
                label = "matched color"
                summary = (
                    f"matched compositor to {reference.name}, "
                    f"{summarize_stats(target_stats)} -> {summarize_stats(reference_stats)}; "
                    f"{_compositor_node_summary(created)}"
                )
            elif self.stack_type == "REFERENCE_COLOR_BOARD":
                reference = _reference_movie_strip(context, strip)
                if reference is None:
                    raise RuntimeError("Select a reference movie strip as well as the active target strip")
                target_stats = sample_video_color(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                reference_stats = sample_video_color(
                    _movie_path(reference),
                    max_samples=context.scene.video_toolkit_analysis_samples,
                )
                stack = build_reference_color_board_stack(target_stats, reference_stats)
                created = _create_compositor_nodes_from_blender_stack(
                    context.scene,
                    strip,
                    stack,
                    f"Reference Color Board to {reference.name}",
                )
                for node in created:
                    node["video_toolkit_reference_strip"] = reference.name
                    node["video_toolkit_source_strip"] = strip.name
                    node["video_toolkit_target_stats"] = summarize_stats(target_stats)
                    node["video_toolkit_reference_stats"] = summarize_stats(reference_stats)
                label = "reference color board"
                summary = (
                    f"reference color board compositor to {reference.name}, "
                    f"{summarize_stats(target_stats)} -> {summarize_stats(reference_stats)}; "
                    f"{_compositor_node_summary(created)}"
                )
            elif self.stack_type == "COLOR_TIMELINE_MATCH":
                reference = _reference_movie_strip(context, strip)
                if reference is None:
                    raise RuntimeError("Select a reference movie strip as well as the active target strip")
                target_samples = sample_video_color_timeline(
                    _movie_path(strip),
                    max_samples=context.scene.video_toolkit_analysis_samples,
                )
                reference_samples = sample_video_color_timeline(
                    _movie_path(reference),
                    max_samples=context.scene.video_toolkit_analysis_samples,
                )
                keyframes = build_color_timeline_match_keyframes(
                    target_samples,
                    reference_samples,
                    smoothing=context.scene.video_toolkit_color_match_smoothing,
                    strength=context.scene.video_toolkit_color_match_strength,
                )
                if not keyframes:
                    raise RuntimeError("No color samples were available for compositor timeline matching")
                created, gamma_count, gain_count = _create_color_timeline_match_compositor_stack(
                    context.scene,
                    strip,
                    keyframes,
                    reference.name,
                )
                label = "color timeline match"
                summary = (
                    f"compositor color timeline match to {reference.name}, "
                    f"gamma {gamma_count} keyframes, gain {gain_count} keyframes, "
                    f"target RGB {_timeline_rgb_summary(target_samples)}, "
                    f"reference {_timeline_rgb_summary(reference_samples)}; "
                    f"{_compositor_node_summary(created)}"
                )
            elif self.stack_type == "DIAGNOSTIC_COLOR":
                stats = sample_video_color(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                diagnosis = diagnose_color(stats)
                text = _write_diagnostics_text(strip, diagnosis.report)
                stack, labels = _diagnostic_recommended_stack(diagnosis)
                if not stack:
                    raise RuntimeError("No Blender compositor diagnostic tools were available for this diagnosis")
                created = _create_diagnostic_compositor_color_stack(context.scene, strip, stack)
                context.scene.video_toolkit_last_diagnostics = diagnosis.summary
                context.scene.video_toolkit_last_diagnostics_text = text.name
                label = "diagnostic grade"
                summary = (
                    f"diagnostic compositor grade {len(created)} nodes, tools: {', '.join(labels)}; "
                    f"{summarize_stats(stats)}; report {text.name}; {_compositor_node_summary(created)}"
                )
            elif self.stack_type == "TRANSLATED_COLOR":
                chain = context.scene.video_toolkit_ffmpeg_chain.strip()
                if not chain:
                    raise RuntimeError("Enter an FFmpeg-style color chain before creating translated compositor nodes")
                translation = translate_filter_chain(chain)
                if not translation.stack and not translation.compositor_nodes and not translation.color_management:
                    unsupported = ", ".join(translation.unsupported_filters) or "none"
                    raise RuntimeError(f"No native Blender compositor graph could be built. Unsupported: {unsupported}")
                created = _create_translated_compositor_color_stack(context.scene, strip, translation)
                color_management = _apply_translation_color_management(context, translation)
                label = "translated color"
                summary = _translated_compositor_summary(translation, len(created), color_management)
            elif self.stack_type == "LIGHTING_NORMALIZE":
                samples = sample_video_luma_timeline(_movie_path(strip), max_samples=context.scene.video_toolkit_analysis_samples)
                keyframes = build_lighting_normalization_keyframes(
                    samples,
                    smoothing=context.scene.video_toolkit_flicker_smoothing,
                    strength=context.scene.video_toolkit_flicker_strength,
                )
                if not keyframes:
                    raise RuntimeError("No lighting samples were available for compositor normalization")
                created, inserted = _create_lighting_normalizer_compositor_stack(context.scene, strip, keyframes)
                label = "lighting normalizer"
                summary = (
                    f"compositor lighting normalizer {inserted} keyframes, "
                    f"luma {min(sample.luma for sample in samples):.1f}-{max(sample.luma for sample in samples):.1f}; "
                    f"{_compositor_node_summary(created)}"
                )
            else:
                created = _create_compositor_color_stack(context.scene, strip)
                label = "color"
            if summary is None:
                summary = _compositor_node_summary(created)
            context.scene.video_toolkit_last_compositor_nodes = summary
            self.report({"INFO"}, f"Created {len(created)} Blender compositor {label} node(s)")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_create_tool_compositor_nodes(Operator):
    bl_idname = "video_toolkit.create_tool_compositor_nodes"
    bl_label = "Create Tool Compositor Nodes"
    bl_description = "Create a Blender compositor node graph from a catalog color tool"
    bl_options = {"REGISTER", "UNDO"}

    filter_id: bpy.props.EnumProperty(name="Tool", items=_compositor_tool_items)

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            tool = get_tool(self.filter_id)
            stack = _tool_compositor_stack(tool)
            compositor_stack = _tool_compositor_filter_stack(tool)
            supported_count = sum(1 for modifier_type, _settings in stack if modifier_type in COMPOSITOR_MODIFIER_TYPES)
            if not supported_count and not compositor_stack:
                raise RuntimeError(f"{tool.label} does not have a compositor-compatible Blender color stack")
            created = _create_tool_compositor_color_stack(scene, strip, tool, stack, compositor_stack)
            color_management = _apply_tool_color_management(context, tool)
            skipped = len(stack) - supported_count
            summary = f"tool compositor {tool.label}: {_compositor_node_summary(created)}"
            if skipped:
                summary = f"{summary}; skipped {skipped} VSE-only modifier(s)"
            if color_management:
                summary = f"{summary}; color management: {', '.join(color_management)}"
            scene.video_toolkit_last_compositor_nodes = summary
            self.report({"INFO"}, f"Created {len(created)} Blender compositor {tool.label} recipe node(s)")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_create_sidecar_compositor_nodes(Operator):
    bl_idname = "video_toolkit.create_sidecar_compositor_nodes"
    bl_label = "Create Selected Tool Nodes"
    bl_description = "Create Blender compositor nodes for the selected Video Effects sidebar tool"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        tool = _selected_sidecar_tool(context.scene)
        if tool is None:
            self.report({"ERROR"}, "No Video Effects tool is selected")
            return {"CANCELLED"}
        if not _tool_has_compositor_stack(tool):
            self.report({"ERROR"}, f"{tool.label} does not have a compositor node recipe")
            return {"CANCELLED"}
        return bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id=tool.id)


class VIDEO_TOOLKIT_OT_create_all_tool_compositor_nodes(Operator):
    bl_idname = "video_toolkit.create_all_tool_compositor_nodes"
    bl_label = "Create All Tool Compositor Nodes"
    bl_description = "Create Blender compositor node graphs for every compositor-compatible catalog color tool"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            tools = tuple(tool for tool in all_tools() if _tool_has_compositor_stack(tool))
            if not tools:
                raise RuntimeError("No compositor-compatible Blender color tools are available")
            created = []
            tool_ids = []
            for tool in tools:
                stack = _tool_compositor_stack(tool)
                nodes = _create_tool_compositor_color_stack(scene, strip, tool, stack, _tool_compositor_filter_stack(tool))
                created.extend(nodes)
                tool_ids.append(tool.id)
            scene.video_toolkit_last_compositor_nodes = (
                f"all tool compositor recipes: {len(tools)} tools, {len(created)} nodes"
            )
            scene["video_toolkit_last_compositor_recipe_ids"] = ",".join(tool_ids)
            self.report({"INFO"}, f"Created {len(created)} Blender compositor node(s) for {len(tools)} catalog recipes")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_create_recommended_recipe_mix_nodes(Operator):
    bl_idname = "video_toolkit.create_recommended_recipe_mix_nodes"
    bl_label = "Create Recommended Mix Nodes"
    bl_description = "Sample real frames and create one Blender compositor graph from the ranked native recipe mix"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            diagnosis = diagnose_color(stats)
            recommendations = _rank_catalog_recipes(stats, diagnosis)
            if not recommendations:
                raise RuntimeError("No Blender-native color recipes were available for recommendation")
            text = _write_recipe_recommendation_text(strip, stats, diagnosis, recommendations)
            count = max(1, min(scene.video_toolkit_recommendation_mix_count, len(recommendations)))
            stack, labels, recipe_ids = _recommended_recipe_mix_stack(recommendations, count)
            supported_count = sum(1 for modifier_type, _settings in stack if modifier_type in COMPOSITOR_MODIFIER_TYPES)
            if not supported_count:
                raise RuntimeError("Recommended recipes did not contain any compositor-compatible Blender nodes")
            created = _create_compositor_nodes_from_blender_stack(scene, strip, stack, "Recommended Recipe Mix")
            skipped = len(stack) - supported_count
            for node in created:
                node["video_toolkit_recommended_recipe_ids"] = ",".join(recipe_ids)
                node["video_toolkit_recommended_recipe_labels"] = ", ".join(labels)
                node["video_toolkit_source_strip"] = strip.name
            scene.video_toolkit_last_recipe_recommendations = text.name
            scene["video_toolkit_last_recommended_recipe_ids"] = ",".join(
                tool.id for _score, tool, _reasons in recommendations[:12]
            )
            scene["video_toolkit_last_recommended_recipe_mix_ids"] = ",".join(recipe_ids)
            scene["video_toolkit_last_recommended_recipe_mix_node_ids"] = ",".join(recipe_ids)
            top_tool = recommendations[0][1]
            scene.video_toolkit_sidecar_group = _enum_key(top_tool.category)
            scene.video_toolkit_sidecar_tool = top_tool.id
            summary = (
                f"recommended recipe mix nodes {len(created)} node(s) from {len(recipe_ids)} recipe(s): "
                f"{', '.join(labels)}"
            )
            if skipped:
                summary = f"{summary}; skipped {skipped} VSE-only modifier(s)"
            scene.video_toolkit_last_compositor_nodes = summary
            self.report({"INFO"}, summary)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_professional_color_workflow(Operator):
    bl_idname = "video_toolkit.apply_professional_color_workflow"
    bl_label = "Apply Pro Color Workflow"
    bl_description = "Sample frames once, then apply Blender Color Management, ranked live grade, reports, and compositor graphs"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="Target",
        items=(("SCENE", "Panel Target", "Use the panel target setting"),) + APPLY_TARGET_ITEMS,
        default="SCENE",
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE" and hasattr(strip, "modifiers"))

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            diagnosis = diagnose_color(stats)
            recommendations = _rank_catalog_recipes(stats, diagnosis)
            if not recommendations:
                raise RuntimeError("No Blender-native color recipes were available for workflow")

            diagnostics_text = _write_diagnostics_text(strip, diagnosis.report)
            recommendations_text = _write_recipe_recommendation_text(strip, stats, diagnosis, recommendations)
            color_profile = build_sampled_color_management(stats)
            color_management_summary = _apply_sampled_color_management_profile(scene, color_profile)
            count = max(1, min(scene.video_toolkit_recommendation_mix_count, len(recommendations)))
            stack, labels, recipe_ids = _recommended_recipe_mix_stack(recommendations, count)
            if not stack:
                raise RuntimeError("Recommended recipes did not contain any live Blender modifiers")

            modifiers, targets = _add_blender_stack_for_target(context, stack, "Professional Color Workflow", self.target)
            recipe_nodes = _create_compositor_nodes_from_blender_stack(scene, strip, stack, "Professional Color Workflow")
            color_nodes = _create_sampled_color_management_compositor_stack(
                scene,
                strip,
                color_profile,
                label_prefix="Professional Color Management",
            )

            for node in recipe_nodes + color_nodes:
                node["video_toolkit_professional_workflow_recipe_ids"] = ",".join(recipe_ids)
                node["video_toolkit_professional_workflow_recipe_labels"] = ", ".join(labels)
                node["video_toolkit_source_strip"] = strip.name

            scene.video_toolkit_last_diagnostics = diagnosis.summary
            scene.video_toolkit_last_diagnostics_text = diagnostics_text.name
            scene.video_toolkit_last_recipe_recommendations = recommendations_text.name
            scene.video_toolkit_last_sampled_color_management = color_management_summary
            scene.video_toolkit_last_color_management = color_management_summary
            scene.video_toolkit_last_recommended_recipe_mix = (
                f"professional workflow live mix {len(modifiers)} modifier(s) on {len(targets)} target(s): "
                f"{', '.join(labels)}"
            )
            scene.video_toolkit_last_compositor_nodes = (
                f"professional workflow nodes {len(recipe_nodes) + len(color_nodes)} node(s): "
                f"{len(recipe_nodes)} recipe, {len(color_nodes)} color management"
            )
            scene.video_toolkit_last_professional_workflow = (
                f"professional color workflow {stats.samples} frames, {len(modifiers)} modifier(s), "
                f"{len(recipe_nodes) + len(color_nodes)} node(s): {', '.join(labels)}"
            )
            scene["video_toolkit_last_recommended_recipe_ids"] = ",".join(
                tool.id for _score, tool, _reasons in recommendations[:12]
            )
            scene["video_toolkit_last_recommended_recipe_mix_ids"] = ",".join(recipe_ids)
            scene["video_toolkit_last_professional_workflow_recipe_ids"] = ",".join(recipe_ids)
            scene["video_toolkit_last_professional_workflow_node_count"] = len(recipe_nodes) + len(color_nodes)
            top_tool = recommendations[0][1]
            scene.video_toolkit_sidecar_group = _enum_key(top_tool.category)
            scene.video_toolkit_sidecar_tool = top_tool.id
            self.report({"INFO"}, scene.video_toolkit_last_professional_workflow)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_write_catalog_coverage_report(Operator):
    bl_idname = "video_toolkit.write_catalog_coverage_report"
    bl_label = "Write Catalog Coverage Report"
    bl_description = "Write a Blender text report showing native, compositor, and rendered fallback tool coverage"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        text = _write_catalog_coverage_text()
        context.scene.video_toolkit_last_catalog_report = text.name
        self.report({"INFO"}, f"Wrote {text.name}")
        return {"FINISHED"}


class VIDEO_TOOLKIT_OT_apply_color_management_preset(Operator):
    bl_idname = "video_toolkit.apply_color_management_preset"
    bl_label = "Apply Blender Color Management Preset"
    bl_description = "Apply a one-click native Blender Color Management look to the Sequencer preview"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: bpy.props.EnumProperty(name="Preset", items=COLOR_MANAGEMENT_PRESET_ITEMS, default="AGX_BALANCED")

    def execute(self, context):
        try:
            summary = _apply_color_management_preset(context.scene, self.preset_id)
            context.scene.video_toolkit_last_color_management = summary
            self.report({"INFO"}, summary)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_apply_sampled_color_management(Operator):
    bl_idname = "video_toolkit.apply_sampled_color_management"
    bl_label = "Sampled Color Management"
    bl_description = "Sample real frames and set native Blender scene Color Management for the Sequencer preview"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        editor = getattr(scene, "sequence_editor", None) if scene else None
        strip = editor.active_strip if editor else None
        return bool(strip and strip.type == "MOVIE")

    def execute(self, context):
        try:
            scene = context.scene
            strip = scene.sequence_editor.active_strip
            stats = sample_video_color(_movie_path(strip), max_samples=scene.video_toolkit_analysis_samples)
            profile = build_sampled_color_management(stats)
            summary = _apply_sampled_color_management_profile(scene, profile)
            scene.video_toolkit_last_sampled_color_management = summary
            scene.video_toolkit_last_color_management = summary
            self.report({"INFO"}, summary)
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class VIDEO_TOOLKIT_OT_open_output_folder(Operator):
    bl_idname = "video_toolkit.open_output_folder"
    bl_label = "Open Output Folder"
    bl_description = "Open the configured Video Toolkit output folder"

    def execute(self, context):
        output_dir = _output_dir(context.scene)
        output_dir.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.path_open(filepath=str(output_dir))
        return {"FINISHED"}


class VIDEO_TOOLKIT_MT_tools(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_tools"
    bl_label = "Video Effects"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Video Effects", icon="SEQ_SEQUENCER")
        op = layout.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Analyze: Live Auto Balance", icon="COLOR")
        op.mode = "AUTO"
        op = layout.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Analyze: Match Selected", icon="EYEDROPPER")
        op.mode = "MATCH"
        op = layout.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Analyze: Identify Colors", icon="COLOR")
        op.mode = "PALETTE"
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_pro_grade.bl_idname, text="Apply: Sampled Pro Grade", icon="MODIFIER")
        layout.operator(
            VIDEO_TOOLKIT_OT_apply_sampled_color_management.bl_idname,
            text="Analyze: Sampled Color Management",
            icon="WORLD",
        )
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_color_board.bl_idname, text="Analyze: Sampled Color Board", icon="COLOR")
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_white_balance.bl_idname, text="Analyze: Neutralize Color Cast", icon="EYEDROPPER")
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma.bl_idname, text="Analyze: Normalize Levels/Gamma", icon="IPO_EASE_IN_OUT")
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma.bl_idname, text="Analyze: Balance Hue/Chroma", icon="COLOR")
        layout.operator(VIDEO_TOOLKIT_OT_color_diagnostics.bl_idname, text="Analyze: Color Diagnostics", icon="TEXT")
        layout.operator(VIDEO_TOOLKIT_OT_apply_diagnostic_grade.bl_idname, text="Apply Diagnostic Grade", icon="COLOR")
        layout.operator(VIDEO_TOOLKIT_OT_normalize_lighting.bl_idname, text="Analyze: Normalize Flicker", icon="IPO_EASE_IN_OUT")
        layout.operator(VIDEO_TOOLKIT_OT_match_lighting_timeline.bl_idname, text="Analyze: Match Lighting Timeline", icon="GRAPH")
        layout.operator(VIDEO_TOOLKIT_OT_match_color_timeline.bl_idname, text="Analyze: Match Color Timeline", icon="COLOR")
        layout.operator(VIDEO_TOOLKIT_OT_apply_reference_color_board.bl_idname, text="Analyze: Reference Color Board", icon="EYEDROPPER")
        layout.menu("VIDEO_TOOLKIT_MT_color_management", icon="WORLD")
        layout.operator(
            VIDEO_TOOLKIT_OT_translate_ffmpeg_chain.bl_idname,
            text="Translate Color Chain to Live Stack",
            icon="MODIFIER",
        )
        _draw_operator(layout, "live_pro_color_stack", icon="MODIFIER")
        layout.separator()
        layout.menu("VIDEO_TOOLKIT_MT_live_blender_color", icon="COLOR")
        layout.menu("VIDEO_TOOLKIT_MT_native_blender_primitives", icon="NODETREE")
        layout.menu("VIDEO_TOOLKIT_MT_blender_vse_modifiers", icon="SEQ_STRIP_DUPLICATE")
        layout.menu("VIDEO_TOOLKIT_MT_compositor_recipes", icon="NODETREE")
        layout.operator(VIDEO_TOOLKIT_OT_create_all_tool_compositor_nodes.bl_idname, text="Create All Color Recipe Nodes", icon="NODETREE")
        layout.operator(VIDEO_TOOLKIT_OT_write_catalog_coverage_report.bl_idname, text="Write Catalog Coverage Report", icon="TEXT")
        op = layout.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Create Color Node Stack", icon="NODETREE")
        op.stack_type = "COLOR"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Native Color Room Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "NATIVE_COLOR_ROOM"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Sampled Color Management Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "SAMPLED_COLOR_MANAGEMENT"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Sampled Color Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "SAMPLED_COLOR"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Palette Identity Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "IDENTITY_COLOR"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Matched Color Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "MATCHED_COLOR"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Reference Color Board Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "REFERENCE_COLOR_BOARD"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Timeline Color Match Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "COLOR_TIMELINE_MATCH"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Diagnostic Grade Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "DIAGNOSTIC_COLOR"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Translated Color Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "TRANSLATED_COLOR"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Lighting Normalize Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "LIGHTING_NORMALIZE"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Restoration Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "RESTORATION"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Native Node Library",
            icon="NODETREE",
        )
        op.stack_type = "NODE_LIBRARY"
        layout.separator()
        _draw_operator(layout, "deflicker_normalize", icon="LIGHT")
        _draw_operator(layout, "stabilize", icon="TRACKING")
        layout.separator()
        layout.menu("VIDEO_TOOLKIT_MT_restoration", icon="MODIFIER")
        layout.menu("VIDEO_TOOLKIT_MT_resolution_motion", icon="RENDER_ANIMATION")
        layout.operator(VIDEO_TOOLKIT_OT_open_output_folder.bl_idname, icon="FILE_FOLDER")


class VIDEO_TOOLKIT_MT_live_blender_color(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_live_blender_color"
    bl_label = "Live Blender Color"

    def draw(self, _context):
        _draw_category(self.layout, "Live Blender Color")


class VIDEO_TOOLKIT_MT_native_blender_primitives(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_native_blender_primitives"
    bl_label = "Native Blender Primitives"

    def draw(self, _context):
        _draw_category(self.layout, "Native Blender Primitives")


class VIDEO_TOOLKIT_MT_restoration(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_restoration"
    bl_label = "Restoration"

    def draw(self, _context):
        _draw_category(self.layout, "Restoration")


class VIDEO_TOOLKIT_MT_resolution_motion(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_resolution_motion"
    bl_label = "Resolution & Motion"

    def draw(self, _context):
        _draw_category(self.layout, "Resolution & Motion")


class VIDEO_TOOLKIT_MT_blender_vse_modifiers(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_blender_vse_modifiers"
    bl_label = "Live Blender Modifiers"

    def draw(self, _context):
        _draw_category(self.layout, "Live Blender Modifiers")


class VIDEO_TOOLKIT_MT_compositor_recipes(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_compositor_recipes"
    bl_label = "Compositor Color Recipes"

    def draw(self, _context):
        current_category = None
        for tool in all_tools():
            if not _tool_has_compositor_stack(tool):
                continue
            if tool.category != current_category:
                if current_category is not None:
                    self.layout.separator()
                self.layout.label(text=tool.category, icon="COLOR")
                current_category = tool.category
            op = self.layout.operator(VIDEO_TOOLKIT_OT_create_tool_compositor_nodes.bl_idname, text=tool.label, icon="NODETREE")
            op.filter_id = tool.id


class VIDEO_TOOLKIT_MT_color_management(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_color_management"
    bl_label = "Blender Color Management"

    def draw(self, _context):
        for preset_id, label, _description in COLOR_MANAGEMENT_PRESET_ITEMS:
            op = self.layout.operator(VIDEO_TOOLKIT_OT_apply_color_management_preset.bl_idname, text=label, icon="WORLD")
            op.preset_id = preset_id


class VIDEO_TOOLKIT_PT_video_filters(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_filters"
    bl_label = "Video Effects"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        strip = scene.sequence_editor.active_strip if scene.sequence_editor else None
        layout.use_property_split = True
        layout.use_property_decorate = False

        _draw_sidecar_browser(layout, scene, strip, context)


class VIDEO_TOOLKIT_PT_video_effects_analysis(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_effects_analysis"
    bl_label = "Frame Analysis"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"
    bl_parent_id = VIDEO_TOOLKIT_PT_video_filters.bl_idname

    def draw(self, context):
        scene = context.scene
        strip = scene.sequence_editor.active_strip if scene.sequence_editor else None
        layout = self.layout
        if not strip:
            layout.label(text="Select a strip.", icon="INFO")
            return
        _draw_live_analysis(layout, scene, strip, context)


class VIDEO_TOOLKIT_PT_video_effects_color_management(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_effects_color_management"
    bl_label = "Color Management"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"
    bl_parent_id = VIDEO_TOOLKIT_PT_video_filters.bl_idname

    def draw(self, context):
        _draw_scene_color_management(self.layout, context.scene)


class VIDEO_TOOLKIT_PT_video_effects_compositor(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_effects_compositor"
    bl_label = "Compositor Nodes"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"
    bl_parent_id = VIDEO_TOOLKIT_PT_video_filters.bl_idname

    def draw(self, context):
        scene = context.scene
        strip = scene.sequence_editor.active_strip if scene.sequence_editor else None
        layout = self.layout
        if not strip:
            layout.label(text="Select a movie strip.", icon="INFO")
            return
        _draw_compositor_nodes(layout, scene, strip)


class VIDEO_TOOLKIT_PT_video_effects_live_tools(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_effects_live_tools"
    bl_label = "Live Blender Tools"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"
    bl_parent_id = VIDEO_TOOLKIT_PT_video_filters.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        scene = context.scene
        strip = scene.sequence_editor.active_strip if scene.sequence_editor else None
        layout = self.layout
        if not strip:
            layout.label(text="Select a strip.", icon="INFO")
            return
        _draw_live_color_tools(layout, scene)


class VIDEO_TOOLKIT_PT_video_effects_strip(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_effects_strip"
    bl_label = "Strip Edit"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"
    bl_parent_id = VIDEO_TOOLKIT_PT_video_filters.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        strip = context.scene.sequence_editor.active_strip if context.scene.sequence_editor else None
        layout = self.layout
        if not strip:
            layout.label(text="Select a strip.", icon="INFO")
            return
        _draw_strip_editing_tools(layout, strip)


class VIDEO_TOOLKIT_PT_video_effects_modifiers(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_effects_modifiers"
    bl_label = "Modifier Stack"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"
    bl_parent_id = VIDEO_TOOLKIT_PT_video_filters.bl_idname

    def draw(self, context):
        strip = context.scene.sequence_editor.active_strip if context.scene.sequence_editor else None
        layout = self.layout
        if not strip:
            layout.label(text="Select a strip.", icon="INFO")
            return
        _draw_live_modifier_editor(layout, strip)


class VIDEO_TOOLKIT_PT_video_effects_render(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_effects_render"
    bl_label = "Rendered Restoration"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Effects"
    bl_parent_id = VIDEO_TOOLKIT_PT_video_filters.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        _draw_render_tools(self.layout, context.scene)


def _draw_category(layout, category: str) -> None:
    for tool in all_tools():
        if tool.category == category:
            _draw_operator(layout, tool.id)


def _draw_operator(layout, tool_id: str, icon: str = "NONE") -> None:
    tool = get_tool(tool_id)
    op = layout.operator(VIDEO_TOOLKIT_OT_apply_filter.bl_idname, text=tool.label, icon=icon)
    op.filter_id = tool.id


def _append_menu(menu_name: str, drawer) -> None:
    menu = getattr(bpy.types, menu_name, None)
    if menu is not None:
        menu.append(drawer)


def _remove_menu(menu_name: str, drawer) -> None:
    menu = getattr(bpy.types, menu_name, None)
    if menu is not None:
        try:
            menu.remove(drawer)
        except Exception:
            pass


def _draw_video_toolkit_menu(self, _context) -> None:
    self.layout.separator()
    self.layout.menu(VIDEO_TOOLKIT_MT_tools.bl_idname, icon="SEQ_SEQUENCER")


def _draw_video_toolkit_header(self, context) -> None:
    space = getattr(context, "space_data", None)
    if space is not None and getattr(space, "view_type", "") in {"SEQUENCER", "SEQUENCER_PREVIEW"}:
        row = self.layout.row(align=True)
        row.menu(VIDEO_TOOLKIT_MT_tools.bl_idname, text="Video Effects", icon="SEQ_SEQUENCER")


def _draw_sidecar_browser(layout, scene, strip, context) -> None:
    _draw_sidecar_selection(layout, scene, strip)
    _draw_sidecar_tabs(layout, scene)
    _draw_sidecar_section_body(layout, scene, strip, context)
    _draw_sidecar_inline_modifier_stack(layout, scene, strip)
    _draw_sidecar_status(layout, scene)


def _draw_sidecar_selection(layout, scene, strip) -> None:
    editor = scene.sequence_editor
    selected = [candidate for candidate in editor.strips_all if candidate.select] if editor else []

    selected_box = layout.box()
    selected_box.use_property_split = False
    row = selected_box.row(align=True)
    row.label(text=f"{len(selected)} selected", icon="SEQ_STRIP_DUPLICATE" if selected else "ERROR")
    row.menu(VIDEO_TOOLKIT_MT_tools.bl_idname, text="", icon="DOWNARROW_HLT")
    if strip is not None:
        selected_box.label(text=getattr(strip, "name", "Active Strip"), icon="SEQ_STRIP_META")
    else:
        selected_box.label(text="Select a movie or video strip", icon="INFO")


def _draw_sidecar_tabs(layout, scene) -> None:
    current = getattr(scene, "video_toolkit_sidecar_section", "BROWSER")
    tabs = layout.box()
    tabs.label(text="Video Effects Sidecar", icon="SEQ_SEQUENCER")
    grid = tabs.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
    for section, label, _description, icon, _index in SIDECAR_SECTION_ITEMS:
        op = grid.operator(
            VIDEO_TOOLKIT_OT_set_sidecar_section.bl_idname,
            text=label,
            icon=icon,
            depress=current == section,
        )
        op.section = section


def _draw_sidecar_section_body(layout, scene, strip, context) -> None:
    section = getattr(scene, "video_toolkit_sidecar_section", "BROWSER")
    if section == "BROWSER":
        _draw_sidecar_tool_browser(layout, scene, strip)
    elif section == "ENHANCE":
        _draw_one_click_video_effects(layout, scene, strip)
    elif section == "ANALYSIS":
        if strip is None or getattr(strip, "type", None) != "MOVIE":
            layout.label(text="Select a movie strip for frame analysis.", icon="INFO")
        else:
            _draw_live_analysis(layout, scene, strip, context)
    elif section == "COLOR":
        _draw_scene_color_management(layout, scene)
    elif section == "COMPOSITOR":
        if strip is None or getattr(strip, "type", None) != "MOVIE":
            layout.label(text="Select a movie strip for compositor nodes.", icon="INFO")
        else:
            _draw_compositor_nodes(layout, scene, strip)
    elif section == "LIVE":
        if strip is None:
            layout.label(text="Select a strip for live Blender tools.", icon="INFO")
        else:
            _draw_live_color_tools(layout, scene)
    elif section == "STRIP":
        if strip is None:
            layout.label(text="Select a strip for strip editing.", icon="INFO")
        else:
            _draw_strip_editing_tools(layout, strip)
    elif section == "MODIFIERS":
        if strip is None:
            layout.label(text="Select a strip to edit live modifiers.", icon="INFO")
        else:
            _draw_live_modifier_editor(layout, strip)
    elif section == "RENDER":
        _draw_render_tools(layout, scene)
    else:
        _draw_sidecar_tool_browser(layout, scene, strip)


def _draw_sidecar_inline_modifier_stack(layout, scene, strip) -> None:
    section = getattr(scene, "video_toolkit_sidecar_section", "BROWSER")
    if section == "MODIFIERS" or strip is None or not hasattr(strip, "modifiers"):
        return
    if len(strip.modifiers) == 0:
        return
    _draw_live_modifier_editor(layout, strip)


def _draw_sidecar_tool_browser(layout, scene, strip) -> None:
    selected_tool = _selected_sidecar_tool(scene)
    group_tools = _sidecar_tools_for_scene(scene)

    browser = layout.box()
    browser.label(text="Video Effects Browser", icon="TOOL_SETTINGS")
    browser.use_property_split = True
    browser.use_property_decorate = False
    browser.prop(scene, "video_toolkit_sidecar_group", text="Group")
    browser.prop(scene, "video_toolkit_sidecar_tool", text="Tool")
    browser.prop(scene, "video_toolkit_apply_target", text="Target")
    action = browser.row(align=True)
    apply_action = action.row(align=True)
    apply_action.enabled = strip is not None and selected_tool is not None
    apply_action.operator(
        VIDEO_TOOLKIT_OT_apply_sidecar_tool.bl_idname,
        text="Apply",
        icon=_sidecar_tool_icon(selected_tool),
    )
    node_action = action.row(align=True)
    node_action.enabled = strip is not None and selected_tool is not None and _tool_has_compositor_stack(selected_tool)
    node_action.operator(
        VIDEO_TOOLKIT_OT_create_sidecar_compositor_nodes.bl_idname,
        text="Nodes",
        icon="NODETREE",
    )
    if selected_tool is not None:
        if selected_tool.is_blender_modifier:
            browser.label(text="Live Blender effect", icon="MODIFIER")
        elif selected_tool.is_ffmpeg:
            browser.label(text="Rendered video effect", icon="RENDER_ANIMATION")
    if group_tools:
        tools_col = browser.column(align=True)
        tools_col.label(text=f"Supported Tools ({len(group_tools)})", icon="SORT_ASC")
        for tool in group_tools:
            row = tools_col.row(align=True)
            row.enabled = strip is not None
            op = row.operator(VIDEO_TOOLKIT_OT_apply_filter.bl_idname, text=tool.label, icon=_sidecar_tool_icon(tool))
            op.filter_id = tool.id
            op.target = "SCENE"
            node_row = row.row(align=True)
            node_row.enabled = strip is not None and _tool_has_compositor_stack(tool)
            node = node_row.operator(VIDEO_TOOLKIT_OT_create_tool_compositor_nodes.bl_idname, text="", icon="NODETREE")
            node.filter_id = tool.id


def _draw_one_click_video_effects(layout, scene, strip) -> None:
    quick = layout.box()
    quick.label(text="One-Click Video Effects", icon="COLOR")
    controls = quick.column(align=True)
    controls.enabled = strip is not None
    controls.operator(
        VIDEO_TOOLKIT_OT_apply_professional_color_workflow.bl_idname,
        text="Pro Color Workflow",
        icon="COLOR",
    )
    controls.operator(
        VIDEO_TOOLKIT_OT_apply_translated_color_workflow.bl_idname,
        text="FFmpeg Color Workflow",
        icon="MODIFIER",
    )
    row = controls.row(align=True)
    _draw_operator(row, "primary_color_board", icon="COLOR")
    _draw_operator(row, "six_vector_hue_board", icon="COLOR")
    row = controls.row(align=True)
    _draw_operator(row, "broadcast_safe_finish", icon="MODIFIER")
    _draw_operator(row, "match_prep_neutralizer", icon="EYEDROPPER")
    row = controls.row(align=True)
    _draw_operator(row, "native_ffmpeg_color_metadata_pipeline", icon="WORLD")
    _draw_operator(row, "native_compositor_all_color_primitives", icon="NODETREE")
    row = controls.row(align=True)
    _draw_operator(row, "native_rgb_channel_board", icon="COLOR")
    _draw_operator(row, "native_ycc_709_video_board", icon="COLOR")
    row = controls.row(align=True)
    row.operator(VIDEO_TOOLKIT_OT_apply_sampled_pro_grade.bl_idname, text="Pro Grade", icon="MODIFIER")
    row.operator(VIDEO_TOOLKIT_OT_apply_sampled_color_board.bl_idname, text="Color Board", icon="COLOR")
    row = controls.row(align=True)
    row.operator(VIDEO_TOOLKIT_OT_apply_reference_color_board.bl_idname, text="Ref Board", icon="EYEDROPPER")
    row.operator(VIDEO_TOOLKIT_OT_match_color_timeline.bl_idname, text="Match Color", icon="COLOR")
    controls.operator(VIDEO_TOOLKIT_OT_apply_sampled_color_management.bl_idname, text="Color Mgmt", icon="WORLD")
    row = controls.row(align=True)
    row.operator(VIDEO_TOOLKIT_OT_apply_sampled_white_balance.bl_idname, text="White Balance", icon="EYEDROPPER")
    row.operator(VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma.bl_idname, text="Levels/Gamma", icon="IPO_EASE_IN_OUT")
    row = controls.row(align=True)
    row.operator(VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma.bl_idname, text="Hue/Chroma", icon="COLOR")
    row.operator(VIDEO_TOOLKIT_OT_apply_diagnostic_grade.bl_idname, text="Fix Grade", icon="COLOR")
    row = controls.row(align=True)
    row.operator(VIDEO_TOOLKIT_OT_color_diagnostics.bl_idname, text="Diagnostics", icon="TEXT")
    row.operator(VIDEO_TOOLKIT_OT_recommend_catalog_recipes.bl_idname, text="Recommend", icon="SORT_ASC")
    row = controls.row(align=True)
    row.operator(VIDEO_TOOLKIT_OT_apply_recommended_recipe_mix.bl_idname, text="Apply Mix", icon="MODIFIER")
    row.operator(VIDEO_TOOLKIT_OT_create_recommended_recipe_mix_nodes.bl_idname, text="Mix Nodes", icon="NODETREE")
    row = controls.row(align=True)
    row.operator(VIDEO_TOOLKIT_OT_normalize_lighting.bl_idname, text="Deflicker", icon="IPO_EASE_IN_OUT")
    row.operator(VIDEO_TOOLKIT_OT_match_lighting_timeline.bl_idname, text="Match Light", icon="GRAPH")
    row = controls.row(align=True)
    row.menu("VIDEO_TOOLKIT_MT_compositor_recipes", text="Recipe Nodes", icon="NODETREE")
    controls.operator(
        VIDEO_TOOLKIT_OT_create_all_tool_compositor_nodes.bl_idname,
        text="All Recipe Nodes",
        icon="NODETREE",
    )
    controls.operator(
        VIDEO_TOOLKIT_OT_write_catalog_coverage_report.bl_idname,
        text="Catalog Coverage Report",
        icon="TEXT",
    )
    quick.prop(scene, "video_toolkit_recommendation_mix_count", text="Mix Count")
    if strip is None:
        quick.label(text="Select a movie or video strip", icon="INFO")


def _draw_sidecar_status(layout, scene) -> None:
    if scene.video_toolkit_last_professional_workflow:
        layout.label(text=scene.video_toolkit_last_professional_workflow, icon="COLOR")
    if scene.video_toolkit_last_translated_workflow:
        layout.label(text=scene.video_toolkit_last_translated_workflow, icon="MODIFIER")
    if scene.video_toolkit_last_analysis:
        layout.label(text=scene.video_toolkit_last_analysis, icon="INFO")
    if scene.video_toolkit_last_compositor_nodes:
        layout.label(text=scene.video_toolkit_last_compositor_nodes, icon="NODETREE")
    if scene.video_toolkit_last_catalog_report:
        layout.label(text=scene.video_toolkit_last_catalog_report, icon="TEXT")
    if scene.video_toolkit_last_recipe_recommendations:
        layout.label(text=scene.video_toolkit_last_recipe_recommendations, icon="SORT_ASC")
    if scene.video_toolkit_last_recommended_recipe_mix:
        layout.label(text=scene.video_toolkit_last_recommended_recipe_mix, icon="MODIFIER")
    if scene.video_toolkit_last_sampled_color_board:
        layout.label(text=scene.video_toolkit_last_sampled_color_board, icon="COLOR")
    if scene.video_toolkit_last_reference_color_board:
        layout.label(text=scene.video_toolkit_last_reference_color_board, icon="EYEDROPPER")
    if scene.video_toolkit_last_output:
        layout.label(text=scene.video_toolkit_last_output, icon="FILE_MOVIE")


def _draw_live_analysis(layout, scene, strip, context) -> None:
    box = layout.box()
    box.label(text="Frame Analysis / Live Match", icon="EYEDROPPER")
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Auto Balance", icon="COLOR")
    op.mode = "AUTO"
    op = row.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Match", icon="EYEDROPPER")
    op.mode = "MATCH"
    op = row.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Identify", icon="COLOR")
    op.mode = "PALETTE"
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_pro_grade.bl_idname, text="Sampled Pro Grade", icon="MODIFIER")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_color_board.bl_idname, text="Sampled Color Board", icon="COLOR")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_color_management.bl_idname, text="Sampled Color Management", icon="WORLD")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_white_balance.bl_idname, text="Sampled White Balance / Cast Fix", icon="EYEDROPPER")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma.bl_idname, text="Sampled Levels / Gamma Normalize", icon="IPO_EASE_IN_OUT")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma.bl_idname, text="Sampled Hue / Chroma Balance", icon="COLOR")
    box.operator(VIDEO_TOOLKIT_OT_normalize_lighting.bl_idname, text="Normalize Lighting Flicker", icon="IPO_EASE_IN_OUT")
    box.operator(VIDEO_TOOLKIT_OT_match_lighting_timeline.bl_idname, text="Match Lighting Timeline", icon="GRAPH")
    box.operator(VIDEO_TOOLKIT_OT_match_color_timeline.bl_idname, text="Match Color Timeline", icon="COLOR")
    box.operator(VIDEO_TOOLKIT_OT_apply_reference_color_board.bl_idname, text="Reference Color Board", icon="EYEDROPPER")
    box.operator(VIDEO_TOOLKIT_OT_color_diagnostics.bl_idname, text="Color Diagnostics Report", icon="TEXT")
    box.operator(VIDEO_TOOLKIT_OT_apply_professional_color_workflow.bl_idname, text="Apply Pro Color Workflow", icon="COLOR")
    box.operator(VIDEO_TOOLKIT_OT_recommend_catalog_recipes.bl_idname, text="Recommend Catalog Recipes", icon="SORT_ASC")
    box.operator(VIDEO_TOOLKIT_OT_apply_recommended_recipe_mix.bl_idname, text="Apply Recommended Recipe Mix", icon="MODIFIER")
    box.operator(VIDEO_TOOLKIT_OT_create_recommended_recipe_mix_nodes.bl_idname, text="Recommended Recipe Mix Nodes", icon="NODETREE")
    box.operator(VIDEO_TOOLKIT_OT_apply_diagnostic_grade.bl_idname, text="Apply Diagnostic Grade", icon="COLOR")
    box.prop(scene, "video_toolkit_analysis_samples")
    box.prop(scene, "video_toolkit_recommendation_mix_count", text="Mix Count")
    row = box.row(align=True)
    row.prop(scene, "video_toolkit_flicker_smoothing", text="Smooth")
    row.prop(scene, "video_toolkit_flicker_strength", text="Strength")
    row = box.row(align=True)
    row.prop(scene, "video_toolkit_match_smoothing", text="Match Smooth")
    row.prop(scene, "video_toolkit_match_strength", text="Match Strength")
    row = box.row(align=True)
    row.prop(scene, "video_toolkit_color_match_smoothing", text="Color Smooth")
    row.prop(scene, "video_toolkit_color_match_strength", text="Color Strength")
    if scene.video_toolkit_last_analysis:
        box.label(text=scene.video_toolkit_last_analysis, icon="INFO")
    if scene.video_toolkit_last_diagnostics:
        box.label(text=scene.video_toolkit_last_diagnostics, icon="INFO")
        if scene.video_toolkit_last_diagnostics_text:
            box.label(text=scene.video_toolkit_last_diagnostics_text, icon="TEXT")
    if scene.video_toolkit_last_recipe_recommendations:
        box.label(text=scene.video_toolkit_last_recipe_recommendations, icon="SORT_ASC")
    if scene.video_toolkit_last_recommended_recipe_mix:
        box.label(text=scene.video_toolkit_last_recommended_recipe_mix, icon="MODIFIER")
    if scene.video_toolkit_last_diagnostic_grade:
        box.label(text=scene.video_toolkit_last_diagnostic_grade, icon="MODIFIER")
    if scene.video_toolkit_last_sampled_white_balance:
        box.label(text=scene.video_toolkit_last_sampled_white_balance, icon="EYEDROPPER")
    if scene.video_toolkit_last_sampled_levels_gamma:
        box.label(text=scene.video_toolkit_last_sampled_levels_gamma, icon="IPO_EASE_IN_OUT")
    if scene.video_toolkit_last_sampled_hue_chroma:
        box.label(text=scene.video_toolkit_last_sampled_hue_chroma, icon="COLOR")
    if scene.video_toolkit_last_sampled_pro_grade:
        box.label(text=scene.video_toolkit_last_sampled_pro_grade, icon="MODIFIER")
    if scene.video_toolkit_last_sampled_color_board:
        box.label(text=scene.video_toolkit_last_sampled_color_board, icon="COLOR")
    if scene.video_toolkit_last_reference_color_board:
        box.label(text=scene.video_toolkit_last_reference_color_board, icon="EYEDROPPER")
    if scene.video_toolkit_last_sampled_color_management:
        box.label(text=scene.video_toolkit_last_sampled_color_management, icon="WORLD")


def _draw_scene_color_management(layout, scene) -> None:
    box = layout.box()
    box.label(text="Blender Color Management", icon="WORLD")
    box.operator(
        VIDEO_TOOLKIT_OT_apply_sampled_color_management.bl_idname,
        text="Sampled Color Management",
        icon="EYEDROPPER",
    )
    preset_grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
    for preset_id, label, _description in COLOR_MANAGEMENT_PRESET_ITEMS:
        op = preset_grid.operator(VIDEO_TOOLKIT_OT_apply_color_management_preset.bl_idname, text=label, icon="WORLD")
        op.preset_id = preset_id
    display = getattr(scene, "display_settings", None)
    if display is not None:
        row = box.row(align=True)
        if hasattr(display, "display_device"):
            row.prop(display, "display_device", text="Display")
        if hasattr(display, "emulation"):
            row.prop(display, "emulation", text="Emulation")
    if hasattr(scene, "sequencer_colorspace_settings"):
        box.prop(scene.sequencer_colorspace_settings, "name", text="Input")
    view = scene.view_settings
    for prop in ("view_transform", "look", "exposure", "gamma"):
        if hasattr(view, prop):
            box.prop(view, prop)
    if hasattr(view, "use_white_balance"):
        box.prop(view, "use_white_balance")
        if view.use_white_balance:
            row = box.row(align=True)
            row.prop(view, "white_balance_temperature", text="Temp")
            row.prop(view, "white_balance_tint", text="Tint")
            if hasattr(view, "white_balance_whitepoint"):
                box.prop(view, "white_balance_whitepoint", text="White Point")
    if hasattr(view, "use_curve_mapping"):
        box.prop(view, "use_curve_mapping", text="Use View Curves")
        if view.use_curve_mapping and hasattr(view, "curve_mapping"):
            try:
                box.template_curve_mapping(view, "curve_mapping")
            except Exception:
                box.label(text="Open Color Management for curve editing.", icon="INFO")
    if scene.video_toolkit_last_color_management:
        box.label(text=scene.video_toolkit_last_color_management, icon="INFO")
    if scene.video_toolkit_last_sampled_color_management:
        box.label(text=scene.video_toolkit_last_sampled_color_management, icon="WORLD")


def _draw_compositor_nodes(layout, scene, strip) -> None:
    if strip.type != "MOVIE":
        return
    box = layout.box()
    box.label(text="Native Compositor Nodes", icon="NODE_COMPOSITING")
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Color Stack", icon="COLOR")
    op.stack_type = "COLOR"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Color Room", icon="NODETREE")
    op.stack_type = "NATIVE_COLOR_ROOM"
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Sampled CM", icon="WORLD")
    op.stack_type = "SAMPLED_COLOR_MANAGEMENT"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Board", icon="COLOR")
    op.stack_type = "SAMPLED_COLOR_BOARD"
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Sampled", icon="EYEDROPPER")
    op.stack_type = "SAMPLED_COLOR"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Identity", icon="COLOR")
    op.stack_type = "IDENTITY_COLOR"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Matched", icon="EYEDROPPER")
    op.stack_type = "MATCHED_COLOR"
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Ref Board", icon="EYEDROPPER")
    op.stack_type = "REFERENCE_COLOR_BOARD"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Timeline", icon="GRAPH")
    op.stack_type = "COLOR_TIMELINE_MATCH"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Translated", icon="MODIFIER")
    op.stack_type = "TRANSLATED_COLOR"
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Diagnostic", icon="TEXT")
    op.stack_type = "DIAGNOSTIC_COLOR"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Normalize", icon="IPO_EASE_IN_OUT")
    op.stack_type = "LIGHTING_NORMALIZE"
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Restore Stack", icon="MODIFIER")
    op.stack_type = "RESTORATION"
    box.menu("VIDEO_TOOLKIT_MT_compositor_recipes", text="Color Recipe Nodes", icon="NODETREE")
    box.operator(
        VIDEO_TOOLKIT_OT_create_recommended_recipe_mix_nodes.bl_idname,
        text="Recommended Recipe Mix Nodes",
        icon="NODETREE",
    )
    box.operator(VIDEO_TOOLKIT_OT_create_all_tool_compositor_nodes.bl_idname, text="All Color Recipe Nodes", icon="NODETREE")
    box.operator(VIDEO_TOOLKIT_OT_write_catalog_coverage_report.bl_idname, text="Catalog Coverage Report", icon="TEXT")
    op = box.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Native Node Library", icon="NODETREE")
    op.stack_type = "NODE_LIBRARY"
    if scene.video_toolkit_last_compositor_nodes:
        box.label(text=scene.video_toolkit_last_compositor_nodes, icon="INFO")
    if scene.video_toolkit_last_catalog_report:
        box.label(text=scene.video_toolkit_last_catalog_report, icon="TEXT")
    _draw_compositor_node_controls(layout, scene)


def _draw_compositor_node_controls(layout, scene) -> None:
    nodes = _video_toolkit_compositor_control_nodes(scene)
    box = layout.box()
    box.label(text="Created Node Controls", icon="NODETREE")
    if not nodes:
        box.label(text="Create a Video Toolkit compositor graph to edit node controls here.", icon="INFO")
        return
    for node in nodes:
        node_box = box.box()
        header = node_box.row(align=True)
        header.prop(node, "label", text="")
        if hasattr(node, "mute"):
            header.prop(node, "mute", text="", icon="HIDE_ON" if node.mute else "HIDE_OFF")
        _draw_compositor_node_control_body(node_box, node)


def _draw_compositor_node_control_body(layout, node) -> None:
    drew = False
    for prop_name in COMPOSITOR_NODE_CONTROL_PROPS.get(node.bl_idname, ()):
        if hasattr(node, prop_name):
            layout.prop(node, prop_name, text=prop_name.replace("_", " ").title())
            drew = True
    if node.bl_idname in COMPOSITOR_CURVE_NODE_TYPES and hasattr(node, "mapping"):
        try:
            layout.template_curve_mapping(node, "mapping")
            drew = True
        except Exception:
            layout.label(text="Open the compositor editor for this curve map.", icon="INFO")
    for socket in node.inputs:
        if _is_editable_compositor_input(socket):
            layout.prop(socket, "default_value", text=socket.name)
            drew = True
    if not drew:
        layout.label(text=node.bl_idname, icon="NODE")


def _video_toolkit_compositor_control_nodes(scene, limit: int = 12):
    tree = _compositor_tree_or_none(scene)
    if tree is None:
        return ()
    candidates = [
        node for node in tree.nodes
        if bool(node.get("video_toolkit")) and _compositor_node_control_names(node)
    ]
    selected_tool = _selected_sidecar_tool(scene)
    selected_id = selected_tool.id if selected_tool is not None else ""
    if selected_id:
        selected_nodes = [
            node for node in candidates
            if node.get("video_toolkit_filter_id") == selected_id
        ]
        if selected_nodes:
            return tuple(sorted(selected_nodes, key=_node_position_key)[:limit])
    return tuple(sorted(candidates, key=_node_position_key, reverse=True)[:limit])


def _compositor_node_control_names(node) -> tuple[str, ...]:
    names: list[str] = []
    for prop_name in COMPOSITOR_NODE_CONTROL_PROPS.get(node.bl_idname, ()):
        if hasattr(node, prop_name):
            names.append(prop_name)
    if node.bl_idname in COMPOSITOR_CURVE_NODE_TYPES and hasattr(node, "mapping"):
        names.append("mapping")
    for socket in node.inputs:
        if _is_editable_compositor_input(socket):
            names.append(socket.name)
    return tuple(names)


def _is_editable_compositor_input(socket) -> bool:
    if socket.name in COMPOSITOR_CONTROL_SKIP_INPUTS:
        return False
    if getattr(socket, "is_linked", False):
        return False
    if not getattr(socket, "enabled", True):
        return False
    return hasattr(socket, "default_value")


def _node_position_key(node):
    return (float(node.location.x), float(node.location.y), node.name)


def _draw_live_color_tools(layout, scene) -> None:
    box = layout.box()
    box.label(text="Live Blender Color Tools", icon="COLOR")
    box.prop(scene, "video_toolkit_apply_target", text="Target")
    translation = box.box()
    translation.label(text="Native Color Chain Translation", icon="MODIFIER")
    translation.prop(scene, "video_toolkit_ffmpeg_chain", text="")
    translation.operator(
        VIDEO_TOOLKIT_OT_translate_ffmpeg_chain.bl_idname,
        text="Translate to Live Stack",
        icon="COLOR",
    )
    translation.operator(
        VIDEO_TOOLKIT_OT_apply_translated_color_workflow.bl_idname,
        text="Apply FFmpeg Color Workflow",
        icon="NODETREE",
    )
    if scene.video_toolkit_last_translation:
        translation.label(text=scene.video_toolkit_last_translation, icon="INFO")
    if scene.video_toolkit_last_translated_workflow:
        translation.label(text=scene.video_toolkit_last_translated_workflow, icon="NODETREE")
    for category in LIVE_COLOR_SIDECAR_CATEGORIES:
        section = box.box()
        section.label(text=category)
        grid = section.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
        for tool in all_tools():
            if tool.category == category:
                _draw_operator(grid, tool.id)


def _draw_strip_editing_tools(layout, strip) -> None:
    box = layout.box()
    box.label(text="Live Strip Edit", icon="SEQ_STRIP_META")
    row = box.row(align=True)
    if hasattr(strip, "blend_type"):
        row.prop(strip, "blend_type", text="")
    if hasattr(strip, "blend_alpha"):
        row.prop(strip, "blend_alpha", text="Opacity")
    row = box.row(align=True)
    for prop in ("mute", "lock", "use_flip_x", "use_flip_y"):
        if hasattr(strip, prop):
            row.prop(strip, prop, text=prop.replace("use_", "").replace("_", " ").title())
    if hasattr(strip, "transform"):
        transform = strip.transform
        box.label(text="Transform")
        row = box.row(align=True)
        row.prop(transform, "offset_x", text="X")
        row.prop(transform, "offset_y", text="Y")
        row = box.row(align=True)
        row.prop(transform, "scale_x", text="Scale X")
        row.prop(transform, "scale_y", text="Scale Y")
        box.prop(transform, "rotation")
        if hasattr(transform, "filter"):
            box.prop(transform, "filter")
    if hasattr(strip, "crop"):
        crop = strip.crop
        box.label(text="Crop")
        row = box.row(align=True)
        row.prop(crop, "min_x", text="Left")
        row.prop(crop, "max_x", text="Right")
        row = box.row(align=True)
        row.prop(crop, "min_y", text="Bottom")
        row.prop(crop, "max_y", text="Top")


def _draw_live_modifier_editor(layout, strip) -> None:
    box = layout.box()
    header = box.row(align=True)
    header.label(text="Live Modifier Stack", icon="MODIFIER")
    header.operator(VIDEO_TOOLKIT_OT_clear_live_modifiers.bl_idname, text="", icon="TRASH")
    if not hasattr(strip, "modifiers") or len(strip.modifiers) == 0:
        box.label(text="Add a live color tool above to create editable controls.", icon="INFO")
        return
    for modifier in strip.modifiers:
        mod_box = box.box()
        row = mod_box.row(align=True)
        row.prop(modifier, "show_expanded", text="", emboss=False)
        row.prop(modifier, "name", text="")
        row.prop(modifier, "mute", text="", icon="HIDE_ON" if modifier.mute else "HIDE_OFF")
        if not modifier.show_expanded:
            continue
        _draw_modifier_common_controls(mod_box, modifier)
        _draw_modifier_controls(mod_box, modifier)


def _draw_modifier_common_controls(layout, modifier) -> None:
    row = layout.row(align=True)
    drew = False
    for prop, text in (("enable", "Enabled"), ("show_preview", "Preview"), ("is_active", "Active")):
        if hasattr(modifier, prop):
            row.prop(modifier, prop, text=text)
            drew = True
    if not drew:
        return
    mask_props = ("input_mask_type", "input_mask_strip", "input_mask_id", "mask_time")
    if not any(hasattr(modifier, prop) for prop in mask_props):
        return
    mask_box = layout.box()
    mask_box.label(text="Mask", icon="MOD_MASK")
    if hasattr(modifier, "input_mask_type"):
        mask_box.prop(modifier, "input_mask_type", text="Type")
    if hasattr(modifier, "input_mask_strip"):
        mask_box.prop(modifier, "input_mask_strip", text="Strip")
    if hasattr(modifier, "input_mask_id"):
        mask_box.prop(modifier, "input_mask_id", text="ID")
    if hasattr(modifier, "mask_time"):
        mask_box.prop(modifier, "mask_time", text="Time")
    if hasattr(modifier, "open_mask_input_panel"):
        mask_box.prop(modifier, "open_mask_input_panel", text="Open Mask Panel")


def _draw_modifier_controls(layout, modifier) -> None:
    if modifier.type == "BRIGHT_CONTRAST":
        row = layout.row(align=True)
        row.prop(modifier, "bright")
        row.prop(modifier, "contrast")
    elif modifier.type == "COLOR_BALANCE":
        cb = modifier.color_balance
        layout.prop(cb, "correction_method")
        if cb.correction_method == "OFFSET_POWER_SLOPE":
            for prop in ("offset", "power", "slope"):
                layout.prop(cb, prop)
        else:
            for prop in ("lift", "gamma", "gain"):
                layout.prop(cb, prop)
        layout.prop(modifier, "color_multiply")
    elif modifier.type == "TONEMAP":
        layout.prop(modifier, "tonemap_type")
        for prop in ("key", "offset", "gamma", "intensity", "contrast", "adaptation", "correction"):
            if hasattr(modifier, prop):
                layout.prop(modifier, prop)
    elif modifier.type == "WHITE_BALANCE":
        layout.prop(modifier, "white_value")
    elif modifier.type in {"CURVES", "HUE_CORRECT"}:
        try:
            layout.template_curve_mapping(modifier, "curve_mapping")
        except Exception:
            layout.label(text="Open Blender's modifier panel for curve editing.", icon="INFO")
    elif modifier.type == "MASK":
        layout.label(text="Native mask modifier controls are shown above.", icon="MOD_MASK")
    else:
        layout.label(text=f"{modifier.type} controls are exposed through Blender's native modifier data.", icon="MODIFIER")


def _draw_render_tools(layout, scene) -> None:
    box = layout.box()
    box.label(text="Rendered Restoration / FFmpeg", icon="RENDER_ANIMATION")
    for category in ("Restoration", "Resolution & Motion"):
        section = box.box()
        section.label(text=category)
        grid = section.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
        for tool in all_tools():
            if tool.category == category:
                _draw_operator(grid, tool.id)
    settings = box.box()
    settings.label(text="Render Settings")
    row = settings.row(align=True)
    row.prop(scene, "video_toolkit_output_dir", text="")
    row.operator(VIDEO_TOOLKIT_OT_open_output_folder.bl_idname, text="", icon="FILE_FOLDER")
    row = settings.row(align=True)
    row.prop(scene, "video_toolkit_crf")
    row.prop(scene, "video_toolkit_preset", text="")
    settings.prop(scene, "video_toolkit_keep_audio")
    settings.prop(scene, "video_toolkit_add_strip")


def _apply_color_management_preset(scene, preset_id: str) -> str:
    view = scene.view_settings
    presets = {
        "AGX_BALANCED": {
            "view_transform": ("AgX", "Khronos PBR Neutral", "Standard"),
            "look": ("Medium High Contrast", "High Contrast", "None"),
            "exposure": 0.0,
            "gamma": 1.0,
            "white_balance": False,
            "curves": None,
        },
        "AGX_PUNCH": {
            "view_transform": ("AgX", "Khronos PBR Neutral", "Standard"),
            "look": ("Very High Contrast", "High Contrast", "Medium High Contrast", "None"),
            "exposure": 0.05,
            "gamma": 0.98,
            "white_balance": False,
            "curves": None,
        },
        "FILMIC_SOFT": {
            "view_transform": ("Filmic", "AgX", "Khronos PBR Neutral", "Standard"),
            "look": ("Medium Low Contrast", "Low Contrast", "None"),
            "exposure": 0.05,
            "gamma": 1.02,
            "white_balance": False,
            "curves": None,
        },
        "STANDARD_VIDEO": {
            "view_transform": ("Standard", "Khronos PBR Neutral", "AgX"),
            "look": ("None",),
            "exposure": 0.0,
            "gamma": 1.0,
            "white_balance": False,
            "curves": None,
        },
        "WARM_REVIEW": {
            "view_transform": ("AgX", "Khronos PBR Neutral", "Standard"),
            "look": ("Medium High Contrast", "High Contrast", "None"),
            "exposure": 0.03,
            "gamma": 1.0,
            "white_balance": True,
            "temperature": 5600.0,
            "tint": 6.0,
            "curves": None,
        },
        "VIEW_CURVE_CONTRAST": {
            "view_transform": ("AgX", "Khronos PBR Neutral", "Standard"),
            "look": ("None",),
            "exposure": 0.0,
            "gamma": 1.0,
            "white_balance": False,
            "curves": {0: ((0.0, 0.0), (0.22, 0.17), (0.72, 0.78), (1.0, 1.0))},
        },
    }
    preset = presets[preset_id]
    view_transform = _set_enum_candidate(view, "view_transform", preset["view_transform"])
    look = _set_enum_candidate(view, "look", preset["look"])
    _set_if_present(view, "exposure", preset["exposure"])
    _set_if_present(view, "gamma", preset["gamma"])
    if hasattr(view, "use_white_balance"):
        view.use_white_balance = bool(preset["white_balance"])
        if view.use_white_balance:
            _set_if_present(view, "white_balance_temperature", preset.get("temperature", 6500.0))
            _set_if_present(view, "white_balance_tint", preset.get("tint", 0.0))
    if hasattr(view, "use_curve_mapping"):
        view.use_curve_mapping = bool(preset["curves"])
        if view.use_curve_mapping and hasattr(view, "curve_mapping"):
            _apply_curve_points(view.curve_mapping, preset["curves"])
    label = dict((item[0], item[1]) for item in COLOR_MANAGEMENT_PRESET_ITEMS).get(preset_id, preset_id)
    return f"{label}: {view_transform or view.view_transform}, {look or view.look}, exposure {view.exposure:.2f}, gamma {view.gamma:.2f}"


def _apply_sampled_color_management_profile(scene, profile) -> str:
    view = scene.view_settings
    sequencer_input = None
    if getattr(profile, "sequencer_input", None) and hasattr(scene, "sequencer_colorspace_settings"):
        sequencer_input = _set_sequencer_input_colorspace(scene, profile.sequencer_input)
    view_transform = _set_enum_candidate(view, "view_transform", profile.view_transform_candidates)
    look = _set_enum_candidate(view, "look", profile.look_candidates)
    _set_if_present(view, "exposure", profile.exposure)
    _set_if_present(view, "gamma", profile.gamma)
    if hasattr(view, "use_white_balance"):
        view.use_white_balance = bool(profile.use_white_balance)
        if view.use_white_balance:
            _set_if_present(view, "white_balance_temperature", profile.white_balance_temperature)
            _set_if_present(view, "white_balance_tint", profile.white_balance_tint)
    if hasattr(view, "use_curve_mapping"):
        view.use_curve_mapping = True
        if hasattr(view, "curve_mapping"):
            _apply_curve_points(view.curve_mapping, {0: profile.curve_points})
    summary = (
        f"{profile.summary}, {view_transform or view.view_transform}, {look or view.look}"
    )
    if sequencer_input:
        summary += f", input {sequencer_input}"
    return summary


def _set_enum_candidate(target, prop: str, candidates) -> str | None:
    for candidate in candidates:
        try:
            setattr(target, prop, candidate)
            return getattr(target, prop)
        except Exception:
            continue
    return getattr(target, prop, None)


def _set_if_present(target, prop: str, value) -> None:
    if hasattr(target, prop):
        try:
            setattr(target, prop, value)
        except Exception:
            return


def _diagnostic_recommended_stack(diagnosis):
    tools_by_label = {tool.label: tool for tool in all_tools() if tool.is_blender_modifier}
    stack = []
    labels = []
    for label in diagnosis.suggested_tools:
        tool = tools_by_label.get(label)
        if tool is None:
            continue
        labels.append(tool.label)
        if tool.blender_stack:
            stack.extend(tool.blender_stack)
        elif tool.blender_modifier:
            stack.append((tool.blender_modifier, tool.blender_settings))
    return tuple(stack), tuple(labels)


def _add_blender_tool(strip, tool):
    if tool.blender_stack:
        return _add_blender_stack(strip, tool.blender_stack, tool.label)
    return [_add_blender_modifier(strip, tool.blender_modifier, tool.blender_settings, tool.label)]


def _add_blender_stack_for_target(context, stack, label: str, target: str = "SCENE"):
    strip = context.scene.sequence_editor.active_strip
    if target == "SCENE":
        target = context.scene.video_toolkit_apply_target
    if target == "ADJUSTMENT":
        adjustment = _create_adjustment_strip(context, label)
        return _add_blender_stack(adjustment, stack, label), [adjustment]
    if target == "SELECTED":
        strips = _selected_modifier_strips(context) or [strip]
        modifiers = []
        for selected_strip in strips:
            modifiers.extend(_add_blender_stack(selected_strip, stack, label))
        return modifiers, strips
    return _add_blender_stack(strip, stack, label), [strip]


def _add_blender_stack(strip, stack, label: str):
    modifiers = []
    for modifier_type, settings in stack:
        modifiers.append(_add_blender_modifier(strip, modifier_type, settings, label))
    return modifiers


def _translation_summary(translation, modifier_count: int, target_count: int, color_management: tuple[str, ...] = ()) -> str:
    supported = ", ".join(translation.supported_filters) or "none"
    unsupported = ", ".join(translation.unsupported_filters)
    summary = f"translated {supported} into {modifier_count} live modifier(s) on {target_count} target(s)"
    if translation.compositor_nodes:
        summary += f"; compositor-native node(s): {len(translation.compositor_nodes)}"
    if color_management:
        summary += f"; color management: {', '.join(color_management)}"
    if unsupported:
        summary += f"; rendered-only/not native: {unsupported}"
    return summary


def _translated_compositor_summary(translation, node_count: int, color_management: tuple[str, ...] = ()) -> str:
    supported = ", ".join(translation.supported_filters) or "none"
    unsupported = ", ".join(translation.unsupported_filters)
    summary = f"translated compositor {supported} into {node_count} node(s)"
    if translation.compositor_nodes:
        summary += f"; compositor-native filter node(s): {len(translation.compositor_nodes)}"
    if color_management:
        summary += f"; color management: {', '.join(color_management)}"
    if unsupported:
        summary += f"; rendered-only/not native: {unsupported}"
    return summary


def _apply_tool_color_management(context, tool) -> tuple[str, ...]:
    color_management_pairs = getattr(tool, "color_management", ())
    if not color_management_pairs:
        return ()
    applied = _apply_color_management_pairs(context, color_management_pairs)
    if applied:
        context.scene.video_toolkit_last_color_management = f"{tool.label}: {', '.join(applied)}"
    return applied


def _apply_translation_color_management(context, translation) -> tuple[str, ...]:
    return _apply_color_management_pairs(context, translation.color_management)


def _apply_color_management_pairs(context, color_management_pairs) -> tuple[str, ...]:
    scene = context.scene
    applied: list[str] = []
    values = {key: value for key, value in color_management_pairs}
    for key, value in values.items():
        scene[f"video_toolkit_color_management_{key}"] = value
    if "sequencer_input" in values and hasattr(scene, "sequencer_colorspace_settings"):
        selected = _set_sequencer_input_colorspace(scene, values["sequencer_input"])
        if selected:
            applied.append(f"input {selected}")
    for key in ("input_range", "output_range", "input_matrix", "output_matrix", "input_transfer", "output_transfer", "input_primaries", "output_primaries"):
        if key in values:
            applied.append(f"{key.replace('_', ' ')} {values[key]}")
    return tuple(applied)


def _set_sequencer_input_colorspace(scene, intent: str) -> str | None:
    candidates = _sequencer_colorspace_candidates(intent)
    if not candidates:
        return None
    return _set_enum_candidate(scene.sequencer_colorspace_settings, "name", candidates)


def _sequencer_colorspace_candidates(intent: str) -> tuple[str, ...]:
    key = str(intent).lower()
    mapping = {
        "bt709": ("sRGB", "Gamma 2.2 Encoded Rec.709", "Gamma 2.4 Encoded Rec.709", "Rec.1886", "Linear Rec.709"),
        "smpte170m": ("sRGB", "Gamma 2.2 Encoded Rec.709", "Rec.1886", "Linear Rec.709"),
        "bt470bg": ("Gamma 2.2 Encoded Rec.709", "sRGB", "Rec.1886", "Linear Rec.709"),
        "bt470m": ("Gamma 1.8 Encoded Rec.709", "Gamma 2.2 Encoded Rec.709", "sRGB"),
        "smpte240m": ("Gamma 2.2 Encoded Rec.709", "sRGB", "Linear Rec.709"),
        "srgb": ("sRGB", "Filmic sRGB", "AgX Base sRGB"),
        "linear": ("Linear Rec.709", "scene_linear"),
        "gbr": ("Linear Rec.709", "scene_linear"),
        "bt2020": ("Rec.2020", "Linear Rec.2020", "Rec.2100-HLG", "Rec.2100-PQ"),
        "bt2020-10": ("Rec.2020", "Linear Rec.2020", "Rec.2100-HLG"),
        "bt2020-12": ("Rec.2020", "Linear Rec.2020", "Rec.2100-HLG"),
        "hlg": ("Rec.2100-HLG", "Rec.2020", "Linear Rec.2020"),
        "pq": ("Rec.2100-PQ", "Rec.2020", "Linear Rec.2020"),
    }
    return mapping.get(key, ())


def _add_blender_modifier(strip, modifier_type, settings, label):
    if not hasattr(strip, "modifiers"):
        raise RuntimeError(f"{strip.name} does not support VSE modifiers")
    modifier = strip.modifiers.new(name=f"VTK {label} - {_modifier_label(modifier_type)}", type=modifier_type)
    modifier.show_expanded = True
    for path, value in settings.items():
        _set_nested_attr(modifier, path, value)
    return modifier


def _insert_modifier_keyframes(strip, modifier, keyframes, property_name: str) -> int:
    if not hasattr(modifier, property_name):
        raise RuntimeError(f"{modifier.name} does not expose {property_name}")
    start = int(getattr(strip, "frame_final_start", getattr(strip, "frame_start", 1)))
    end = int(getattr(strip, "frame_final_end", start + getattr(strip, "frame_final_duration", 1))) - 1
    duration = max(1, end - start)
    max_index = max((index for index, _value in keyframes), default=1)
    inserted = 0
    seen_frames: set[int] = set()
    for sample_index, value in keyframes:
        frame = start + round((sample_index / max(max_index, 1)) * duration)
        if frame in seen_frames:
            continue
        seen_frames.add(frame)
        setattr(modifier, property_name, value)
        modifier.keyframe_insert(data_path=property_name, frame=frame)
        inserted += 1
    _set_keyframes_linear(modifier)
    return inserted


def _insert_color_balance_keyframes(strip, modifier, keyframes, property_name: str) -> int:
    color_balance = modifier.color_balance
    if not hasattr(color_balance, property_name):
        raise RuntimeError(f"{modifier.name} does not expose color_balance.{property_name}")
    start = int(getattr(strip, "frame_final_start", getattr(strip, "frame_start", 1)))
    end = int(getattr(strip, "frame_final_end", start + getattr(strip, "frame_final_duration", 1))) - 1
    duration = max(1, end - start)
    max_index = max((keyframe.sample_index for keyframe in keyframes), default=1)
    inserted = 0
    seen_frames: set[int] = set()
    for keyframe in keyframes:
        frame = start + round((keyframe.sample_index / max(max_index, 1)) * duration)
        if frame in seen_frames:
            continue
        seen_frames.add(frame)
        setattr(color_balance, property_name, getattr(keyframe, property_name))
        color_balance.keyframe_insert(data_path=property_name, frame=frame)
        inserted += 1
    _set_keyframes_linear(color_balance)
    return inserted


def _insert_node_socket_keyframes(strip, socket, keyframes) -> int:
    start = int(getattr(strip, "frame_final_start", getattr(strip, "frame_start", 1)))
    end = int(getattr(strip, "frame_final_end", start + getattr(strip, "frame_final_duration", 1))) - 1
    duration = max(1, end - start)
    max_index = max((index for index, _value in keyframes), default=1)
    inserted = 0
    seen_frames: set[int] = set()
    for sample_index, value in keyframes:
        frame = start + round((sample_index / max(max_index, 1)) * duration)
        if frame in seen_frames:
            continue
        seen_frames.add(frame)
        socket.default_value = value
        socket.keyframe_insert(data_path="default_value", frame=frame)
        inserted += 1
    _set_keyframes_linear(socket)
    return inserted


def _insert_color_node_socket_keyframes(strip, socket, keyframes, property_name: str) -> int:
    start = int(getattr(strip, "frame_final_start", getattr(strip, "frame_start", 1)))
    end = int(getattr(strip, "frame_final_end", start + getattr(strip, "frame_final_duration", 1))) - 1
    duration = max(1, end - start)
    max_index = max((keyframe.sample_index for keyframe in keyframes), default=1)
    inserted = 0
    seen_frames: set[int] = set()
    for keyframe in keyframes:
        frame = start + round((keyframe.sample_index / max(max_index, 1)) * duration)
        if frame in seen_frames:
            continue
        seen_frames.add(frame)
        if not _try_set_socket_default(socket, _rgba(getattr(keyframe, property_name))):
            raise RuntimeError(f"Blender compositor socket does not accept {property_name} color keyframes")
        socket.keyframe_insert(data_path="default_value", frame=frame)
        inserted += 1
    _set_keyframes_linear(socket)
    return inserted


def _timeline_rgb_summary(samples) -> str:
    if not samples:
        return "no samples"
    red = sum(sample.rgb[0] for sample in samples) / len(samples)
    green = sum(sample.rgb[1] for sample in samples) / len(samples)
    blue = sum(sample.rgb[2] for sample in samples) / len(samples)
    return f"{red:.1f}/{green:.1f}/{blue:.1f}"


def _set_keyframes_linear(target) -> None:
    owners = [target]
    owner_id = getattr(target, "id_data", None)
    if owner_id is not None and owner_id is not target:
        owners.append(owner_id)
    for owner in owners:
        animation = getattr(owner, "animation_data", None)
        action = getattr(animation, "action", None) if animation else None
        if action is None:
            continue
        for fcurve in _iter_action_fcurves(action):
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "LINEAR"


def _iter_action_fcurves(action):
    if hasattr(action, "fcurves"):
        yield from action.fcurves
        return
    for layer in getattr(action, "layers", []):
        for action_strip in getattr(layer, "strips", []):
            for channelbag in getattr(action_strip, "channelbags", []):
                yield from getattr(channelbag, "fcurves", [])


def _count_action_keyframes(action, data_path: str) -> int:
    if action is None:
        return 0
    total = 0
    for fcurve in _iter_action_fcurves(action):
        if fcurve.data_path == data_path:
            total += len(fcurve.keyframe_points)
    return total


def _set_action_keyframes_linear(action, data_path: str) -> None:
    for fcurve in _iter_action_fcurves(action):
        if fcurve.data_path != data_path:
            continue
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "LINEAR"


def _create_compositor_color_stack(scene, strip):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", "VTK Movie Clip", 0, origin=origin)
    _assign_movie_clip(movie, _movie_path(strip))
    convert = _new_compositor_node(tree, "CompositorNodeConvertColorSpace", "VTK Color Space", 1, origin=origin)
    exposure = _new_compositor_node(tree, "CompositorNodeExposure", "VTK Exposure", 2, origin=origin)
    _set_input_default(exposure, "Exposure", 0.10)
    bright = _new_compositor_node(tree, "CompositorNodeBrightContrast", "VTK Brightness/Contrast", 3, origin=origin)
    _set_input_default(bright, "Bright", 0.015)
    _set_input_default(bright, "Contrast", 8.0)
    balance = _new_compositor_node(tree, "CompositorNodeColorBalance", "VTK Color Balance", 4, origin=origin)
    _set_input_default(balance, "Fac", 1.0)
    _set_input_default(balance, "Color Gamma", (1.04, 1.03, 1.02, 1.0))
    _set_input_default(balance, "Color Gain", (1.05, 1.04, 1.03, 1.0))
    correction = _new_compositor_node(tree, "CompositorNodeColorCorrection", "VTK Zone Correction", 5, origin=origin)
    _set_input_default(correction, "Master Saturation", 1.06)
    _set_input_default(correction, "Master Contrast", 1.05)
    _set_input_default(correction, "Master Gamma", 1.0)
    _set_input_default(correction, "Master Gain", 1.02)
    _set_input_default(correction, "Midtones Start", 0.20)
    _set_input_default(correction, "Midtones End", 0.78)
    curves = _new_compositor_node(tree, "CompositorNodeCurveRGB", "VTK RGB Curves", 6, origin=origin)
    _apply_curve_points(curves.mapping, {0: ((0.0, 0.0), (0.25, 0.21), (0.75, 0.80), (1.0, 1.0))})
    hue_sat = _new_compositor_node(tree, "CompositorNodeHueSat", "VTK Hue/Saturation", 7, origin=origin)
    _set_input_default(hue_sat, "Saturation", 1.04)
    _set_input_default(hue_sat, "Value", 1.01)
    hue_correct = _new_compositor_node(tree, "CompositorNodeHueCorrect", "VTK Hue Correct", 8, origin=origin)
    _apply_hue_correct(hue_correct.mapping, {"saturation": 0.56})
    tonemap = _new_compositor_node(tree, "CompositorNodeTonemap", "VTK Tone Map", 9, origin=origin)
    _set_input_default(tonemap, "Type", "RD_PHOTORECEPTOR")
    _set_input_default(tonemap, "Intensity", 0.10)
    _set_input_default(tonemap, "Contrast", 0.12)
    separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", "VTK Separate Color", 10, y_offset=-120, origin=origin)
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", "VTK Combine Color", 11, y_offset=-120, origin=origin)
    levels = _new_compositor_node(tree, "CompositorNodeLevels", "VTK Levels", 12, y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", "VTK Viewer", 13, origin=origin)
    output = _new_output_file_node(tree, scene, 13, y_offset=-160, origin=origin)

    final_socket = _link_compositor_chain(
        tree,
        [movie, convert, exposure, bright, balance, correction, curves, hue_sat, hue_correct, tonemap],
    )
    _link_socket(tree, final_socket, _image_input(separate))
    for socket_name in ("Red", "Green", "Blue", "Alpha"):
        _link_socket(tree, _socket_by_name(separate.outputs, socket_name), _socket_by_name(combine.inputs, socket_name))
    combined_socket = _image_output(combine)
    _link_socket(tree, combined_socket, _image_input(levels))
    _link_socket(tree, combined_socket, _image_input(viewer))
    _link_socket(tree, combined_socket, _first_socket(output.inputs))
    return [movie, convert, exposure, bright, balance, correction, curves, hue_sat, hue_correct, tonemap, separate, combine, levels, viewer, output]


def _create_native_color_room_compositor_stack(scene, strip):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", "VTK Native Color Room Movie Clip", 0, origin=origin)
    _assign_movie_clip(movie, _movie_path(strip))
    convert = _new_compositor_node(tree, "CompositorNodeConvertColorSpace", "VTK Native Color Room Color Space", 1, origin=origin)
    exposure = _new_compositor_node(tree, "CompositorNodeExposure", "VTK Native Color Room Exposure", 2, origin=origin)
    _set_input_default(exposure, "Exposure", 0.0)
    bright = _new_compositor_node(tree, "CompositorNodeBrightContrast", "VTK Native Color Room Brightness Contrast", 3, origin=origin)
    _set_input_default_candidates(bright, ("Brightness", "Bright"), 0.0)
    _set_input_default(bright, "Contrast", 0.0)
    balance = _new_compositor_node(tree, "CompositorNodeColorBalance", "VTK Native Color Room Lift Gamma Gain", 4, origin=origin)
    _set_input_default_candidates(balance, ("Fac", "Factor"), 1.0)
    _set_input_default_candidates(balance, ("Type",), "LIFT_GAMMA_GAIN")
    _set_input_default_candidates(balance, ("Color Lift", "Lift"), (1.0, 1.0, 1.0, 1.0))
    _set_input_default_candidates(balance, ("Color Gamma", "Gamma"), (1.0, 1.0, 1.0, 1.0))
    _set_input_default_candidates(balance, ("Color Gain", "Gain"), (1.0, 1.0, 1.0, 1.0))
    correction = _new_compositor_node(tree, "CompositorNodeColorCorrection", "VTK Native Color Room Zone Correction", 5, origin=origin)
    _set_input_default_candidates(correction, ("Saturation", "Master Saturation"), 1.0)
    _set_input_default_candidates(correction, ("Contrast", "Master Contrast"), 1.0)
    _set_input_default_candidates(correction, ("Gamma", "Master Gamma"), 1.0)
    _set_input_default_candidates(correction, ("Gain", "Master Gain"), 1.0)
    _set_input_default_candidates(correction, ("Midtones Start",), 0.20)
    _set_input_default_candidates(correction, ("Midtones End",), 0.80)
    curves = _new_compositor_node(tree, "CompositorNodeCurveRGB", "VTK Native Color Room RGB Curves", 6, origin=origin)
    _apply_curve_points(curves.mapping, {0: ((0.0, 0.0), (0.25, 0.25), (0.50, 0.50), (0.75, 0.75), (1.0, 1.0))})
    hue_sat = _new_compositor_node(tree, "CompositorNodeHueSat", "VTK Native Color Room Hue Saturation Value", 7, origin=origin)
    _set_input_default(hue_sat, "Hue", 0.5)
    _set_input_default(hue_sat, "Saturation", 1.0)
    _set_input_default(hue_sat, "Value", 1.0)
    _set_input_default_candidates(hue_sat, ("Factor", "Fac"), 1.0)
    hue_correct = _new_compositor_node(tree, "CompositorNodeHueCorrect", "VTK Native Color Room Hue Correct", 8, origin=origin)
    _apply_hue_correct(hue_correct.mapping, {"saturation": 0.50, "value": 0.50})
    tonemap = _new_compositor_node(tree, "CompositorNodeTonemap", "VTK Native Color Room Tone Map", 9, origin=origin)
    _set_input_default(tonemap, "Type", "RD_PHOTORECEPTOR")
    _set_input_default(tonemap, "Intensity", 0.0)
    _set_input_default(tonemap, "Contrast", 0.0)
    _set_input_default(tonemap, "Gamma", 1.0)
    display = _new_compositor_node(tree, "CompositorNodeConvertToDisplay", "VTK Native Color Room Display Convert", 10, origin=origin)
    separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", "VTK Native Color Room Separate Color", 11, y_offset=-120, origin=origin)
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", "VTK Native Color Room Combine Color", 12, y_offset=-120, origin=origin)
    luma = _new_compositor_node(tree, "CompositorNodeRGBToBW", "VTK Native Color Room Luma Monitor", 11, y_offset=-360, origin=origin)
    normalize = _new_compositor_node(tree, "CompositorNodeNormalize", "VTK Native Color Room Normalize Monitor", 12, y_offset=-360, origin=origin)
    levels = _new_compositor_node(tree, "CompositorNodeLevels", "VTK Native Color Room Levels", 13, y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", "VTK Native Color Room Viewer", 14, origin=origin)
    output = _new_output_file_node(tree, scene, 14, y_offset=-160, origin=origin)
    output.name = "VTK Native Color Room Output File"
    output.label = "VTK Native Color Room Output File"

    final_socket = _link_compositor_chain(
        tree,
        [movie, convert, exposure, bright, balance, correction, curves, hue_sat, hue_correct, tonemap, display],
    )
    _link_socket(tree, final_socket, _image_input(separate))
    for socket_name in ("Red", "Green", "Blue", "Alpha"):
        _link_socket(tree, _socket_by_name(separate.outputs, socket_name), _socket_by_name(combine.inputs, socket_name))
    combined_socket = _image_output(combine)
    _link_socket(tree, combined_socket, _image_input(luma))
    _link_socket(tree, _first_socket(luma.outputs), _first_socket(normalize.inputs))
    _link_socket(tree, combined_socket, _image_input(levels))
    _link_socket(tree, combined_socket, _image_input(viewer))
    _link_socket(tree, combined_socket, _first_socket(output.inputs))
    return [
        movie,
        convert,
        exposure,
        bright,
        balance,
        correction,
        curves,
        hue_sat,
        hue_correct,
        tonemap,
        display,
        separate,
        combine,
        luma,
        normalize,
        levels,
        viewer,
        output,
    ]


def _create_sampled_color_management_compositor_stack(scene, strip, profile, label_prefix: str = "Sampled Color Management"):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    label = f"VTK {label_prefix}"
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", f"{label} Movie Clip", 0, origin=origin)
    _assign_movie_clip(movie, _movie_path(strip))
    convert = _new_compositor_node(tree, "CompositorNodeConvertColorSpace", f"{label} Color Space", 1, origin=origin)
    exposure = _new_compositor_node(tree, "CompositorNodeExposure", f"{label} Exposure", 2, origin=origin)
    _set_input_default(exposure, "Exposure", profile.exposure)
    balance = _new_compositor_node(tree, "CompositorNodeColorBalance", f"{label} White Balance", 3, origin=origin)
    white_balance = _sampled_color_management_white_balance(profile)
    _set_input_default_candidates(balance, ("Fac", "Factor"), 1.0)
    _set_input_default_candidates(balance, ("Type",), "LIFT_GAMMA_GAIN")
    _set_input_default_candidates(balance, ("Color Gamma", "Gamma"), white_balance)
    _set_input_default_candidates(balance, ("Color Gain", "Gain"), white_balance)
    correction = _new_compositor_node(tree, "CompositorNodeColorCorrection", f"{label} View Gamma", 4, origin=origin)
    _set_input_default_candidates(correction, ("Gamma", "Master Gamma"), profile.gamma)
    _set_input_default_candidates(correction, ("Gain", "Master Gain"), _clamp_node_value(1.0 + profile.exposure * 0.18, 0.88, 1.12))
    _set_input_default_candidates(correction, ("Saturation", "Master Saturation"), 1.0)
    curves = _new_compositor_node(tree, "CompositorNodeCurveRGB", f"{label} View Curves", 5, origin=origin)
    _apply_curve_points(curves.mapping, {0: profile.curve_points})
    hue_sat = _new_compositor_node(tree, "CompositorNodeHueSat", f"{label} Review HSV", 6, origin=origin)
    _set_input_default(hue_sat, "Saturation", 1.0)
    _set_input_default(hue_sat, "Value", _clamp_node_value(profile.gamma, 0.88, 1.16))
    tonemap = _new_compositor_node(tree, "CompositorNodeTonemap", f"{label} View Transform", 7, origin=origin)
    _set_input_default(tonemap, "Type", "RD_PHOTORECEPTOR")
    _set_input_default(tonemap, "Intensity", _clamp_node_value(max(-profile.exposure, 0.0) * 0.35, 0.0, 0.18))
    _set_input_default(tonemap, "Contrast", 0.06 if profile.look_candidates and "High" in profile.look_candidates[0] else 0.03)
    _set_input_default(tonemap, "Gamma", profile.gamma)
    display = _new_compositor_node(tree, "CompositorNodeConvertToDisplay", f"{label} Display Convert", 8, origin=origin)
    levels = _new_compositor_node(tree, "CompositorNodeLevels", f"{label} Levels", 9, y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", f"{label} Viewer", 10, origin=origin)
    output = _new_output_file_node(tree, scene, 10, y_offset=-160, origin=origin)
    output.name = f"{label} Output File"
    output.label = f"{label} Output File"

    final_socket = _link_compositor_chain(
        tree,
        [movie, convert, exposure, balance, correction, curves, hue_sat, tonemap, display],
    )
    _link_socket(tree, final_socket, _image_input(levels))
    _link_socket(tree, final_socket, _image_input(viewer))
    _link_socket(tree, final_socket, _first_socket(output.inputs))
    created = [movie, convert, exposure, balance, correction, curves, hue_sat, tonemap, display, levels, viewer, output]
    for node in created:
        node["video_toolkit_view_transform"] = profile.view_transform_candidates[0] if profile.view_transform_candidates else ""
        node["video_toolkit_look"] = profile.look_candidates[0] if profile.look_candidates else ""
        node["video_toolkit_sequencer_input"] = profile.sequencer_input
        node["video_toolkit_white_balance_temperature"] = profile.white_balance_temperature
        node["video_toolkit_white_balance_tint"] = profile.white_balance_tint
    return created


def _create_sampled_compositor_color_stack(scene, strip, profile):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", "VTK Sampled Movie Clip", 0, origin=origin)
    _assign_movie_clip(movie, _movie_path(strip))
    convert = _new_compositor_node(tree, "CompositorNodeConvertColorSpace", "VTK Sampled Color Space", 1, origin=origin)
    exposure = _new_compositor_node(tree, "CompositorNodeExposure", "VTK Sampled Exposure", 2, origin=origin)
    _set_input_default(exposure, "Exposure", profile.exposure)
    bright = _new_compositor_node(tree, "CompositorNodeBrightContrast", "VTK Sampled Brightness/Contrast", 3, origin=origin)
    _set_input_default(bright, "Brightness", profile.brightness)
    _set_input_default(bright, "Bright", profile.brightness)
    _set_input_default(bright, "Contrast", profile.contrast)
    balance = _new_compositor_node(tree, "CompositorNodeColorBalance", "VTK Sampled Lift Gamma Gain", 4, origin=origin)
    _set_input_default_candidates(balance, ("Fac", "Factor"), 1.0)
    _set_input_default_candidates(balance, ("Type",), "LIFT_GAMMA_GAIN")
    _set_input_default_candidates(balance, ("Color Lift", "Lift"), profile.lift + (1.0,))
    _set_input_default_candidates(balance, ("Color Gamma", "Gamma"), profile.gamma + (1.0,))
    _set_input_default_candidates(balance, ("Color Gain", "Gain"), profile.gain + (1.0,))
    correction = _new_compositor_node(tree, "CompositorNodeColorCorrection", "VTK Sampled Zone Correction", 5, origin=origin)
    _set_input_default_candidates(correction, ("Saturation", "Master Saturation"), profile.saturation)
    _set_input_default_candidates(correction, ("Contrast", "Master Contrast"), _clamp_node_value(1.0 + profile.contrast / 100.0, 0.75, 1.35))
    _set_input_default_candidates(correction, ("Gamma", "Master Gamma"), profile.master_gamma)
    _set_input_default_candidates(correction, ("Gain", "Master Gain"), profile.master_gain)
    _set_input_default_candidates(correction, ("Midtones Start",), profile.midtones_start)
    _set_input_default_candidates(correction, ("Midtones End",), profile.midtones_end)
    curves = _new_compositor_node(tree, "CompositorNodeCurveRGB", "VTK Sampled RGB Curves", 6, origin=origin)
    _apply_curve_points(curves.mapping, {0: profile.curve_points})
    hue_sat = _new_compositor_node(tree, "CompositorNodeHueSat", "VTK Sampled Hue/Saturation", 7, origin=origin)
    _set_input_default(hue_sat, "Saturation", profile.saturation)
    _set_input_default(hue_sat, "Value", _clamp_node_value(1.0 + profile.exposure * 0.12, 0.92, 1.08))
    hue_correct = _new_compositor_node(tree, "CompositorNodeHueCorrect", "VTK Sampled Hue Correct", 8, origin=origin)
    _apply_curve_points(hue_correct.mapping, profile.hue_curve_points)
    tonemap = _new_compositor_node(tree, "CompositorNodeTonemap", "VTK Sampled Tone Map", 9, origin=origin)
    _set_input_default(tonemap, "Type", "RD_PHOTORECEPTOR")
    _set_input_default(tonemap, "Intensity", profile.tonemap_intensity)
    _set_input_default(tonemap, "Contrast", profile.tonemap_contrast)
    _set_input_default(tonemap, "Gamma", profile.tonemap_gamma)
    separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", "VTK Sampled Separate Color", 10, y_offset=-120, origin=origin)
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", "VTK Sampled Combine Color", 11, y_offset=-120, origin=origin)
    levels = _new_compositor_node(tree, "CompositorNodeLevels", "VTK Sampled Levels", 12, y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", "VTK Sampled Viewer", 13, origin=origin)
    output = _new_output_file_node(tree, scene, 13, y_offset=-160, origin=origin)
    output.name = "VTK Sampled Output File"
    output.label = "VTK Sampled Output File"

    final_socket = _link_compositor_chain(
        tree,
        [movie, convert, exposure, bright, balance, correction, curves, hue_sat, hue_correct, tonemap],
    )
    _link_socket(tree, final_socket, _image_input(separate))
    for socket_name in ("Red", "Green", "Blue", "Alpha"):
        _link_socket(tree, _socket_by_name(separate.outputs, socket_name), _socket_by_name(combine.inputs, socket_name))
    combined_socket = _image_output(combine)
    _link_socket(tree, combined_socket, _image_input(levels))
    _link_socket(tree, combined_socket, _image_input(viewer))
    _link_socket(tree, combined_socket, _first_socket(output.inputs))
    return [movie, convert, exposure, bright, balance, correction, curves, hue_sat, hue_correct, tonemap, separate, combine, levels, viewer, output]


def _create_translated_compositor_color_stack(scene, strip, translation, label_prefix: str = "Translated"):
    return _create_compositor_nodes_from_blender_stack(
        scene,
        strip,
        translation.stack,
        label_prefix,
        translation.compositor_nodes,
    )


def _create_identity_compositor_color_stack(scene, strip, stack):
    return _create_compositor_nodes_from_blender_stack(scene, strip, stack, "Palette Identity")


def _create_matched_compositor_color_stack(scene, strip, stack, reference_name: str):
    return _create_compositor_nodes_from_blender_stack(scene, strip, stack, f"Matched to {reference_name}")


def _create_diagnostic_compositor_color_stack(scene, strip, stack):
    return _create_compositor_nodes_from_blender_stack(scene, strip, stack, "Diagnostic Grade")


def _create_color_timeline_match_compositor_stack(scene, strip, keyframes, reference_name: str):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", "VTK Color Timeline Match Movie Clip", 0, origin=origin)
    _assign_movie_clip(movie, _movie_path(strip))
    convert = _new_compositor_node(tree, "CompositorNodeConvertColorSpace", "VTK Color Timeline Match Color Space", 1, origin=origin)
    balance = _new_compositor_node(tree, "CompositorNodeColorBalance", "VTK Color Timeline Match Balance", 2, origin=origin)
    _set_input_default_candidates(balance, ("Fac", "Factor"), 1.0)
    _set_input_default_candidates(balance, ("Type",), "LIFT_GAMMA_GAIN")
    gamma_socket = _color_input_socket(balance, ("Color Gamma", "Gamma"), _rgba(keyframes[0].gamma))
    gain_socket = _color_input_socket(balance, ("Color Gain", "Gain"), _rgba(keyframes[0].gain))
    if gamma_socket is None or gain_socket is None:
        raise RuntimeError("Blender compositor Color Balance node does not expose color Gamma/Gain sockets")
    gamma_count = _insert_color_node_socket_keyframes(strip, gamma_socket, keyframes, "gamma")
    gain_count = _insert_color_node_socket_keyframes(strip, gain_socket, keyframes, "gain")
    tonemap = _new_compositor_node(tree, "CompositorNodeTonemap", "VTK Color Timeline Match Tone Map", 3, origin=origin)
    _set_input_default(tonemap, "Type", "RD_PHOTORECEPTOR")
    _set_input_default(tonemap, "Intensity", 0.03)
    _set_input_default(tonemap, "Contrast", 0.03)
    levels = _new_compositor_node(tree, "CompositorNodeLevels", "VTK Color Timeline Match Levels", 4, y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", "VTK Color Timeline Match Viewer", 5, origin=origin)
    output = _new_output_file_node(tree, scene, 5, y_offset=-160, origin=origin)
    output.name = "VTK Color Timeline Match Output File"
    output.label = "VTK Color Timeline Match Output File"

    matched_socket = _link_compositor_chain(tree, [movie, convert, balance, tonemap])
    _link_socket(tree, matched_socket, _image_input(levels))
    leveled_socket = _image_output(levels)
    _link_socket(tree, leveled_socket, _image_input(viewer))
    _link_socket(tree, leveled_socket, _first_socket(output.inputs))
    balance["video_toolkit_reference"] = reference_name
    balance["video_toolkit_gamma_keyframes"] = gamma_count
    balance["video_toolkit_gain_keyframes"] = gain_count
    balance["video_toolkit_gamma_socket_path"] = gamma_socket.path_from_id("default_value")
    balance["video_toolkit_gain_socket_path"] = gain_socket.path_from_id("default_value")
    created = [movie, convert, balance, tonemap, levels, viewer, output]
    for node in created:
        node["video_toolkit_color_timeline_keyframes"] = min(gamma_count, gain_count)
    return created, gamma_count, gain_count


def _create_lighting_normalizer_compositor_stack(scene, strip, keyframes):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", "VTK Lighting Normalizer Movie Clip", 0, origin=origin)
    _assign_movie_clip(movie, _movie_path(strip))
    convert = _new_compositor_node(tree, "CompositorNodeConvertColorSpace", "VTK Lighting Normalizer Color Space", 1, origin=origin)
    bright = _new_compositor_node(tree, "CompositorNodeBrightContrast", "VTK Lighting Normalizer Brightness", 2, origin=origin)
    brightness_socket = _socket_by_name(bright.inputs, "Brightness") or _socket_by_name(bright.inputs, "Bright")
    if brightness_socket is None:
        raise RuntimeError("Blender compositor Brightness/Contrast node does not expose a brightness socket")
    _set_input_default_candidates(bright, ("Brightness", "Bright"), keyframes[0][1])
    _set_input_default(bright, "Contrast", 0.0)
    inserted = _insert_node_socket_keyframes(strip, brightness_socket, keyframes)
    tonemap = _new_compositor_node(tree, "CompositorNodeTonemap", "VTK Lighting Normalizer Tone Map", 3, origin=origin)
    _set_input_default(tonemap, "Type", "RD_PHOTORECEPTOR")
    _set_input_default(tonemap, "Intensity", 0.04)
    _set_input_default(tonemap, "Contrast", 0.04)
    levels = _new_compositor_node(tree, "CompositorNodeLevels", "VTK Lighting Normalizer Levels", 4, y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", "VTK Lighting Normalizer Viewer", 5, origin=origin)
    output = _new_output_file_node(tree, scene, 5, y_offset=-160, origin=origin)
    output.name = "VTK Lighting Normalizer Output File"
    output.label = "VTK Lighting Normalizer Output File"

    normalized_socket = _link_compositor_chain(tree, [movie, convert, bright, tonemap])
    _link_socket(tree, normalized_socket, _image_input(levels))
    leveled_socket = _image_output(levels)
    _link_socket(tree, leveled_socket, _image_input(viewer))
    _link_socket(tree, leveled_socket, _first_socket(output.inputs))
    created = [movie, convert, bright, tonemap, levels, viewer, output]
    for node in created:
        node["video_toolkit_lighting_keyframes"] = inserted
    return created, inserted


def _create_compositor_nodes_from_blender_stack(scene, strip, stack, label_prefix: str, compositor_nodes=()):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", f"VTK {label_prefix} Movie Clip", 0, origin=origin)
    clip = _assign_movie_clip(movie, _movie_path(strip))
    convert = _new_compositor_node(tree, "CompositorNodeConvertColorSpace", f"VTK {label_prefix} Color Space", 1, origin=origin)
    chain_nodes = [movie, convert]
    skipped = 0
    for modifier_type, settings in stack:
        node = _translated_modifier_to_compositor_node(
            tree,
            modifier_type,
            settings,
            len(chain_nodes),
            origin,
            label_prefix,
        )
        if node is None:
            skipped += 1
            continue
        chain_nodes.append(node)
    final_socket = _link_compositor_chain(tree, chain_nodes)
    created = list(chain_nodes)
    for compositor_type, settings in compositor_nodes:
        final_socket, filter_nodes = _append_translated_compositor_filter(
            tree,
            final_socket,
            compositor_type,
            settings,
            len(created),
            origin,
            label_prefix,
            source_clip=clip,
        )
        if not filter_nodes:
            skipped += 1
            continue
        created.extend(filter_nodes)
    levels = _new_compositor_node(tree, "CompositorNodeLevels", f"VTK {label_prefix} Levels", len(created), y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", f"VTK {label_prefix} Viewer", len(created) + 1, origin=origin)
    output = _new_output_file_node(tree, scene, len(created) + 1, y_offset=-160, origin=origin)
    output.name = f"VTK {label_prefix} Output File"
    output.label = f"VTK {label_prefix} Output File"
    _link_socket(tree, final_socket, _image_input(levels))
    _link_socket(tree, final_socket, _image_input(viewer))
    _link_socket(tree, final_socket, _first_socket(output.inputs))
    created += [levels, viewer, output]
    if skipped:
        for node in created:
            node["video_toolkit_skipped_translated_modifiers"] = skipped
    return created


def _create_tool_compositor_color_stack(scene, strip, tool, stack=(), compositor_nodes=()):
    created = _create_compositor_nodes_from_blender_stack(
        scene,
        strip,
        stack,
        f"Tool {tool.label}",
        compositor_nodes=compositor_nodes,
    )
    for node in created:
        node["video_toolkit_filter_id"] = tool.id
        node["video_toolkit_tool_label"] = tool.label
        if getattr(tool, "color_management", ()):
            node["video_toolkit_color_management"] = _format_pairs(tool.color_management)
            for key, value in tool.color_management:
                node[f"video_toolkit_color_management_{key}"] = value
    return created


def _translated_modifier_to_compositor_node(tree, modifier_type: str, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    label = f"VTK {label_prefix} {_modifier_label(modifier_type)}"
    if modifier_type == "BRIGHT_CONTRAST":
        node = _new_compositor_node(tree, "CompositorNodeBrightContrast", label, index, origin=origin)
        _set_input_default_candidates(node, ("Brightness", "Bright"), settings.get("bright", 0.0))
        _set_input_default(node, "Contrast", settings.get("contrast", 0.0))
        return node
    if modifier_type == "COLOR_BALANCE":
        node = _new_compositor_node(tree, "CompositorNodeColorBalance", label, index, origin=origin)
        _set_input_default_candidates(node, ("Fac", "Factor"), 1.0)
        _set_input_default_candidates(node, ("Type",), _color_balance_method_name(settings))
        for key, socket_names in (
            ("color_balance.lift", ("Color Lift", "Lift")),
            ("color_balance.gamma", ("Color Gamma", "Gamma")),
            ("color_balance.gain", ("Color Gain", "Gain")),
            ("color_balance.offset", ("Color Offset", "Offset")),
            ("color_balance.power", ("Color Power", "Power")),
            ("color_balance.slope", ("Color Slope", "Slope")),
        ):
            value = settings.get(key)
            if value is not None:
                _set_input_default_candidates(node, socket_names, _rgba(value))
        return node
    if modifier_type == "CURVES":
        node = _new_compositor_node(tree, "CompositorNodeCurveRGB", label, index, origin=origin)
        curve_points = settings.get("__curve_points__")
        if curve_points:
            _apply_curve_points(node.mapping, curve_points)
        return node
    if modifier_type == "HUE_CORRECT":
        node = _new_compositor_node(tree, "CompositorNodeHueCorrect", label, index, origin=origin)
        hue_values = settings.get("__hue_correct__")
        curve_points = settings.get("__curve_points__")
        if hue_values:
            _apply_hue_correct(node.mapping, hue_values)
        if curve_points:
            _apply_curve_points(node.mapping, curve_points)
        return node
    if modifier_type == "TONEMAP":
        node = _new_compositor_node(tree, "CompositorNodeTonemap", label, index, origin=origin)
        _set_input_default(node, "Type", _tonemap_type_name(settings.get("tonemap_type")))
        for key, socket_name in (
            ("key", "Key"),
            ("offset", "Offset"),
            ("gamma", "Gamma"),
            ("intensity", "Intensity"),
            ("contrast", "Contrast"),
            ("adaptation", "Light Adaptation"),
            ("correction", "Chromatic Adaptation"),
        ):
            if key in settings:
                _set_input_default(node, socket_name, settings[key])
        return node
    if modifier_type == "WHITE_BALANCE":
        node = _new_compositor_node(tree, "CompositorNodeColorBalance", label, index, origin=origin)
        white_value = _rgba(settings.get("white_value", (1.0, 1.0, 1.0)))
        _set_input_default_candidates(node, ("Fac", "Factor"), 1.0)
        _set_input_default_candidates(node, ("Type",), "LIFT_GAMMA_GAIN")
        _set_input_default_candidates(node, ("Color Gamma", "Gamma"), white_value)
        _set_input_default_candidates(node, ("Color Gain", "Gain"), white_value)
        return node
    return None


def _append_translated_compositor_filter(
    tree,
    input_socket,
    compositor_type: str,
    settings: dict[str, object],
    index: int,
    origin,
    label_prefix: str = "Translated",
    source_clip=None,
):
    if compositor_type == "CONVOLVE":
        return _append_convolve_compositor_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "CHANNEL_SHIFT":
        return _append_channel_shift_compositor_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "PLANE_EXTRACT":
        return _append_plane_extract_compositor_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "ALPHA_MERGE":
        return _append_alpha_merge_compositor_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "PLANE_SHUFFLE":
        return _append_plane_shuffle_compositor_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "COLOR_MODEL_BOARD":
        return _append_color_model_board_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "BLEND_COMPOSITE":
        return _append_blend_composite_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "MASKED_BLEND_COMPOSITE":
        return _append_masked_blend_composite_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "BACKGROUND_KEY":
        return _append_background_key_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "BOX_MASK_ALPHA":
        return _append_shape_mask_alpha_filter(tree, input_socket, settings, index, origin, label_prefix, "CompositorNodeBoxMask")
    if compositor_type == "ELLIPSE_MASK_ALPHA":
        return _append_shape_mask_alpha_filter(tree, input_socket, settings, index, origin, label_prefix, "CompositorNodeEllipseMask")
    if compositor_type == "DOUBLE_EDGE_MASK_ALPHA":
        return _append_double_edge_mask_alpha_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "MASK_TO_SDF_ALPHA":
        return _append_mask_to_sdf_alpha_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type in {"RGB_OVERLAY", "BLANK_IMAGE_OVERLAY", "TEXT_OVERLAY"}:
        return _append_source_overlay_filter(tree, input_socket, settings, index, origin, label_prefix, compositor_type)
    if compositor_type == "BOKEH_IMAGE_BLUR":
        return _append_bokeh_image_blur_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "NORMALIZE_LUMA":
        return _append_normalize_luma_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "SCOPE_MONITOR":
        return _append_scope_monitor_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "IDENTITY_COMPARE":
        return _append_identity_compare_filter(tree, input_socket, settings, index, origin, label_prefix)
    if compositor_type == "QUALITY_COMPARE":
        return _append_quality_compare_filter(tree, input_socket, settings, index, origin, label_prefix)
    node = _translated_compositor_filter_to_node(tree, compositor_type, settings, index, origin, label_prefix, source_clip=source_clip)
    if node is None:
        return input_socket, []
    input_name = settings.get("__image_input__")
    output_name = settings.get("__image_output__")
    node_input = _socket_by_name(node.inputs, str(input_name)) if input_name else _image_input(node)
    node_output = _socket_by_name(node.outputs, str(output_name)) if output_name else _image_output(node)
    if not settings.get("__skip_link_input__"):
        _link_socket(tree, input_socket, node_input)
    if settings.get("__passthrough__"):
        return input_socket, [node]
    return node_output, [node]


def _append_convolve_compositor_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    label = f"VTK {label_prefix} {settings.get('label') or 'Convolve'}"
    kernel_node = _new_compositor_node(tree, "CompositorNodeImage", f"{label} Kernel", index, y_offset=-220, origin=origin)
    kernel_image = _create_convolution_kernel_image(settings, f"{label} Kernel Image")
    kernel_node.image = kernel_image
    convolve = _new_compositor_node(tree, "CompositorNodeConvolve", label, index + 1, origin=origin)
    _set_input_default(convolve, "Kernel Data Type", "Color")
    _set_input_default(convolve, "Normalize Kernel", bool(settings.get("normalize", False)))
    _link_socket(tree, input_socket, _image_input(convolve))
    kernel_input = _socket_by_name(convolve.inputs, "Color Kernel")
    if kernel_input is None:
        kernel_input = next((socket for socket in convolve.inputs if socket.name == "Kernel" and socket.bl_idname == "NodeSocketColor"), None)
    _link_socket(tree, _image_output(kernel_node), kernel_input)
    convolve["video_toolkit_ffmpeg_filter"] = settings.get("source", "convolution")
    convolve["video_toolkit_kernel_size"] = tuple(settings.get("kernel_size", (3, 3)))
    convolve["video_toolkit_kernel_rdiv"] = float(settings.get("rdiv", 1.0) or 1.0)
    convolve["video_toolkit_kernel_bias"] = float(settings.get("bias", 0.0) or 0.0)
    convolve["video_toolkit_kernel_mode"] = str(settings.get("mode", "square"))
    created = [kernel_node, convolve]
    final_socket = _image_output(convolve)
    bias = float(settings.get("bias", 0.0) or 0.0)
    if abs(bias) > 1e-6:
        bias_node = _new_compositor_node(tree, "CompositorNodeBrightContrast", f"{label} Bias", index + 2, y_offset=120, origin=origin)
        _set_input_default_candidates(bias_node, ("Brightness", "Bright"), bias)
        _set_input_default(bias_node, "Contrast", 0.0)
        _link_socket(tree, final_socket, _image_input(bias_node))
        final_socket = _image_output(bias_node)
        created.append(bias_node)
    return final_socket, created


def _create_convolution_kernel_image(settings: dict[str, object], name: str):
    width, height = _kernel_size(settings.get("kernel_size", (3, 3)))
    image = bpy.data.images.new(name, width=width, height=height, alpha=True, float_buffer=True)
    if hasattr(image, "use_fake_user"):
        image.use_fake_user = True
    pixels = _convolution_kernel_pixels(settings, width * height)
    image.pixels.foreach_set(pixels)
    image.update()
    return image


def _kernel_size(value) -> tuple[int, int]:
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        width = int(max(1, min(31, round(float(value[0] or 3)))))
        height = int(max(1, min(31, round(float(value[1] or 3)))))
        return width, height
    return (3, 3)


def _convolution_kernel_pixels(settings: dict[str, object], count: int) -> list[float]:
    channels = settings.get("kernel_channels") or {}
    if not isinstance(channels, dict):
        channels = {}
    fallback = _kernel_channel_values(settings.get("kernel"), count, None)
    red = _kernel_channel_values(channels.get("red"), count, fallback)
    green = _kernel_channel_values(channels.get("green"), count, red)
    blue = _kernel_channel_values(channels.get("blue"), count, red)
    alpha = _kernel_channel_values(channels.get("alpha"), count, red)
    pixels: list[float] = []
    for index in range(count):
        pixels.extend([red[index], green[index], blue[index], alpha[index]])
    return pixels


def _kernel_channel_values(value, count: int, fallback) -> list[float]:
    values = []
    if isinstance(value, (tuple, list)):
        for item in value[:count]:
            try:
                values.append(float(item))
            except Exception:
                values.append(0.0)
    if not values and fallback is not None:
        values = list(fallback[:count])
    while len(values) < count:
        values.append(0.0)
    if not values and count:
        values = [0.0] * count
        values[count // 2] = 1.0
    return values[:count]


def _append_channel_shift_compositor_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    offsets = settings.get("offsets") or {}
    if not isinstance(offsets, dict):
        return input_socket, []

    label = f"VTK {label_prefix} {settings.get('label') or 'Channel Shift'}"
    base_separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", f"{label} Separate", index, y_offset=-140, origin=origin)
    _link_socket(tree, input_socket, _image_input(base_separate))
    created = [base_separate]
    channel_outputs = []

    channel_specs = (
        ("red", "Red", "Red", -360),
        ("green", "Green", "Green", -120),
        ("blue", "Blue", "Blue", 120),
        ("alpha", "Alpha", "Alpha", 360),
    )
    for channel_key, output_name, input_name, y_offset in channel_specs:
        dx, dy = _channel_shift_offset(offsets.get(channel_key))
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            shift = _new_compositor_node(
                tree,
                "CompositorNodeTranslate",
                f"{label} {input_name} Offset",
                index + len(created),
                y_offset=y_offset,
                origin=origin,
            )
            _set_input_default(shift, "X", dx)
            _set_input_default(shift, "Y", dy)
            shifted_separate = _new_compositor_node(
                tree,
                "CompositorNodeSeparateColor",
                f"{label} {input_name} Separate",
                index + len(created) + 1,
                y_offset=y_offset,
                origin=origin,
            )
            _link_socket(tree, input_socket, _image_input(shift))
            _link_socket(tree, _image_output(shift), _image_input(shifted_separate))
            channel_outputs.append((_socket_by_name(shifted_separate.outputs, output_name), input_name))
            created.extend([shift, shifted_separate])
        else:
            channel_outputs.append((_socket_by_name(base_separate.outputs, output_name), input_name))
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Combine", index + len(created), y_offset=-140, origin=origin)
    for output_socket, input_name in channel_outputs:
        _link_socket(tree, output_socket, _socket_by_name(combine.inputs, input_name))
    created.append(combine)
    return _image_output(combine), created


def _channel_shift_offset(value) -> tuple[float, float]:
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return float(value[0] or 0.0), float(value[1] or 0.0)
    return (0.0, 0.0)


def _append_plane_extract_compositor_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    plane = str(settings.get("plane", "red")).lower()
    label = f"VTK {label_prefix} {plane.upper()} Plane"
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Combine", index + 1, y_offset=-140, origin=origin)
    _set_input_default(combine, "Alpha", 1.0)
    created = []

    if plane == "y":
        luma = _new_compositor_node(tree, "CompositorNodeRGBToBW", f"{label} Luma", index, y_offset=-140, origin=origin)
        _link_socket(tree, input_socket, _image_input(luma))
        for input_name in ("Red", "Green", "Blue"):
            _link_socket(tree, _first_socket(luma.outputs), _socket_by_name(combine.inputs, input_name))
        created.append(luma)
    else:
        separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", f"{label} Separate", index, y_offset=-140, origin=origin)
        _link_socket(tree, input_socket, _image_input(separate))
        output_name = _plane_extract_output_name(plane)
        output_socket = _socket_by_name(separate.outputs, output_name)
        for input_name in ("Red", "Green", "Blue"):
            _link_socket(tree, output_socket, _socket_by_name(combine.inputs, input_name))
        created.append(separate)
    created.append(combine)
    return _image_output(combine), created


def _plane_extract_output_name(plane: str) -> str:
    return {
        "r": "Red",
        "red": "Red",
        "g": "Green",
        "green": "Green",
        "b": "Blue",
        "blue": "Blue",
        "alpha": "Alpha",
        "a": "Alpha",
        "u": "Blue",
        "v": "Red",
    }.get(plane, "Red")


def _append_alpha_merge_compositor_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    label = f"VTK {label_prefix} {settings.get('label') or 'Alpha Merge Luma Matte'}"
    luma = _new_compositor_node(tree, "CompositorNodeRGBToBW", f"{label} Luma", index, y_offset=-180, origin=origin)
    set_alpha = _new_compositor_node(tree, "CompositorNodeSetAlpha", label, index + 1, origin=origin)
    _set_input_default(set_alpha, "Type", settings.get("type", "Apply Mask"))
    _link_socket(tree, input_socket, _image_input(luma))
    _link_socket(tree, input_socket, _image_input(set_alpha))
    _link_socket(tree, _first_socket(luma.outputs), _socket_by_name(set_alpha.inputs, "Alpha"))
    for node in (luma, set_alpha):
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "alphamerge")
        node["video_toolkit_alpha_source"] = settings.get("alpha_source", "luma")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
    return _image_output(set_alpha), [luma, set_alpha]


def _append_plane_shuffle_compositor_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    outputs = settings.get("outputs") or {}
    if not isinstance(outputs, dict):
        return input_socket, []
    label = f"VTK {label_prefix} Plane Shuffle"
    separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", f"{label} Separate", index, y_offset=-140, origin=origin)
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Combine", index + 1, y_offset=-140, origin=origin)
    _link_socket(tree, input_socket, _image_input(separate))
    for output_name, input_name in (
        (_plane_extract_output_name(str(outputs.get("red", "red"))), "Red"),
        (_plane_extract_output_name(str(outputs.get("green", "green"))), "Green"),
        (_plane_extract_output_name(str(outputs.get("blue", "blue"))), "Blue"),
        (_plane_extract_output_name(str(outputs.get("alpha", "alpha"))), "Alpha"),
    ):
        _link_socket(tree, _socket_by_name(separate.outputs, output_name), _socket_by_name(combine.inputs, input_name))
    return _image_output(combine), [separate, combine]


def _append_color_model_board_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    mode = str(settings.get("mode", "RGB") or "RGB").upper()
    ycc_mode = str(settings.get("ycc_mode", "ITUBT709") or "ITUBT709").upper()
    label = f"VTK {label_prefix} {settings.get('label') or mode + ' Color Board'}"
    separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", f"{label} Separate", index, y_offset=-160, origin=origin)
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Combine", index + 1, y_offset=-160, origin=origin)
    for node in (separate, combine):
        _set_node_property(node, "mode", mode)
        _set_node_property(node, "ycc_mode", ycc_mode)
        node["video_toolkit_color_model"] = mode
        node["video_toolkit_ycc_mode"] = ycc_mode
        node["video_toolkit_native_color_model_board"] = True
    _link_socket(tree, input_socket, _image_input(separate))
    for output_socket, input_socket_target in zip(separate.outputs, combine.inputs):
        _link_socket(tree, output_socket, input_socket_target)

    grade_type = str(settings.get("grade_type", "HUE_SAT") or "HUE_SAT").upper()
    grade = dict(settings.get("grade", {}) or {})
    created = [separate, combine]
    final_socket = _image_output(combine)
    if grade_type == "COLOR_BALANCE":
        grade_node = _new_compositor_node(tree, "CompositorNodeColorBalance", f"{label} Balance", index + 2, origin=origin)
        _set_input_default_candidates(grade_node, ("Factor", "Fac"), grade.get("factor", 1.0))
        _set_input_default_candidates(grade_node, ("Type",), grade.get("type", "Lift/Gamma/Gain"))
        if "lift" in grade:
            _set_input_default_candidates(grade_node, ("Color Lift", "Lift"), _rgba(grade.get("lift")))
        if "gamma" in grade:
            _set_input_default_candidates(grade_node, ("Color Gamma", "Gamma"), _rgba(grade.get("gamma")))
        if "gain" in grade:
            _set_input_default_candidates(grade_node, ("Color Gain", "Gain"), _rgba(grade.get("gain")))
    elif grade_type == "COLOR_CORRECTION":
        grade_node = _new_compositor_node(tree, "CompositorNodeColorCorrection", f"{label} Correction", index + 2, origin=origin)
        _set_input_default_candidates(grade_node, ("Master Saturation", "Saturation"), grade.get("saturation", 1.0))
        _set_input_default_candidates(grade_node, ("Master Contrast", "Contrast"), grade.get("contrast", 1.0))
        _set_input_default_candidates(grade_node, ("Master Gamma", "Gamma"), grade.get("gamma", 1.0))
        _set_input_default_candidates(grade_node, ("Master Gain", "Gain"), grade.get("gain", 1.0))
        _set_input_default_candidates(grade_node, ("Master Offset", "Offset"), grade.get("offset", 0.0))
    else:
        grade_node = _new_compositor_node(tree, "CompositorNodeHueSat", f"{label} Hue Saturation", index + 2, origin=origin)
        _set_input_default(grade_node, "Hue", grade.get("hue", 0.5))
        _set_input_default(grade_node, "Saturation", grade.get("saturation", 1.0))
        _set_input_default(grade_node, "Value", grade.get("value", 1.0))
        _set_input_default_candidates(grade_node, ("Factor", "Fac"), grade.get("factor", 1.0))
    _link_socket(tree, final_socket, _image_input(grade_node))
    grade_node["video_toolkit_color_model"] = mode
    grade_node["video_toolkit_ycc_mode"] = ycc_mode
    grade_node["video_toolkit_native_color_model_board"] = True
    final_socket = _image_output(grade_node)
    created.append(grade_node)
    return final_socket, created


def _append_blend_composite_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    label = f"VTK {label_prefix} {settings.get('label') or 'Blend Composite'}"
    foreground_socket, processor_nodes = _processed_blend_foreground(tree, input_socket, settings, index, origin, label)
    alpha = _new_compositor_node(tree, "CompositorNodeAlphaOver", label, index + len(processor_nodes), origin=origin)
    _set_input_default(alpha, "Factor", settings.get("factor", 0.35))
    _set_input_default(alpha, "Type", settings.get("type", "Straight"))
    _set_input_default(alpha, "Straight Alpha", bool(settings.get("straight_alpha", True)))
    _link_socket(tree, input_socket, _socket_by_name(alpha.inputs, "Background"))
    _link_socket(tree, foreground_socket, _socket_by_name(alpha.inputs, "Foreground"))
    alpha["video_toolkit_ffmpeg_filter"] = settings.get("source", "blend")
    alpha["video_toolkit_blend_mode"] = str(settings.get("mode", "average"))
    alpha["video_toolkit_blend_factor"] = float(settings.get("factor", 0.35) or 0.0)
    if settings.get("temporal"):
        alpha["video_toolkit_temporal_approximation"] = True
    if settings.get("expression"):
        alpha["video_toolkit_blend_expression"] = settings.get("expression")
    if settings.get("expressions"):
        alpha["video_toolkit_lut2_expressions"] = ",".join(str(item) for item in settings.get("expressions", ()))
    if settings.get("approximation"):
        alpha["video_toolkit_approximation"] = settings.get("approximation")
    return _image_output(alpha), [*processor_nodes, alpha]


def _processed_blend_foreground(tree, input_socket, settings: dict[str, object], index: int, origin, label: str):
    mode = str(settings.get("mode", "average")).lower()
    if mode in {"difference", "subtract", "negation"}:
        invert = _new_compositor_node(tree, "CompositorNodeInvert", f"{label} Difference Branch", index, y_offset=-180, origin=origin)
        _set_input_default_candidates(invert, ("Factor", "Fac"), 1.0)
        _set_input_default(invert, "Invert Color", True)
        _set_input_default(invert, "Invert Alpha", False)
        _link_socket(tree, input_socket, _image_input(invert))
        invert["video_toolkit_blend_mode"] = mode
        return _image_output(invert), [invert]
    if mode in {"screen", "lighten", "dodge", "addition", "glow"}:
        bright = _new_compositor_node(tree, "CompositorNodeBrightContrast", f"{label} Lighten Branch", index, y_offset=-180, origin=origin)
        _set_input_default_candidates(bright, ("Brightness", "Bright"), 0.08)
        _set_input_default(bright, "Contrast", 8.0)
        _link_socket(tree, input_socket, _image_input(bright))
        bright["video_toolkit_blend_mode"] = mode
        return _image_output(bright), [bright]
    if mode in {"multiply", "darken", "burn", "and", "stain"}:
        curves = _new_compositor_node(tree, "CompositorNodeCurveRGB", f"{label} Multiply Branch", index, y_offset=-180, origin=origin)
        _apply_curve_points(curves.mapping, {0: [(0.0, 0.0), (0.45, 0.28), (1.0, 0.82)]})
        _link_socket(tree, input_socket, _image_input(curves))
        curves["video_toolkit_blend_mode"] = mode
        return _image_output(curves), [curves]
    if mode in {"overlay", "softlight", "hardlight", "hardoverlay"}:
        curves = _new_compositor_node(tree, "CompositorNodeCurveRGB", f"{label} Contrast Branch", index, y_offset=-180, origin=origin)
        _apply_curve_points(curves.mapping, {0: [(0.0, 0.0), (0.25, 0.18), (0.50, 0.50), (0.75, 0.84), (1.0, 1.0)]})
        _link_socket(tree, input_socket, _image_input(curves))
        curves["video_toolkit_blend_mode"] = mode
        return _image_output(curves), [curves]
    return input_socket, []


def _append_masked_blend_composite_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    label = f"VTK {label_prefix} {settings.get('label') or 'Masked Blend Composite'}"
    matte = _new_compositor_node(tree, "CompositorNodeLumaMatte", f"{label} Luma Matte", index, y_offset=-180, origin=origin)
    _set_input_default(matte, "Minimum", settings.get("minimum", 0.08))
    _set_input_default(matte, "Maximum", settings.get("maximum", 0.92))
    _link_socket(tree, input_socket, _image_input(matte))
    foreground_socket, processor_nodes = _processed_blend_foreground(tree, input_socket, {"mode": "overlay"}, index + 1, origin, label)
    alpha = _new_compositor_node(tree, "CompositorNodeAlphaOver", label, index + 1 + len(processor_nodes), origin=origin)
    _set_input_default(alpha, "Factor", settings.get("factor", 1.0))
    _set_input_default(alpha, "Type", settings.get("type", "Straight"))
    _set_input_default(alpha, "Straight Alpha", bool(settings.get("straight_alpha", True)))
    _link_socket(tree, input_socket, _socket_by_name(alpha.inputs, "Background"))
    _link_socket(tree, foreground_socket, _socket_by_name(alpha.inputs, "Foreground"))
    _link_socket(tree, _socket_by_name(matte.outputs, "Matte"), _socket_by_name(alpha.inputs, "Factor"))
    alpha["video_toolkit_ffmpeg_filter"] = settings.get("source", "maskedmerge")
    alpha["video_toolkit_planes"] = str(settings.get("planes", "15"))
    if settings.get("approximation"):
        alpha["video_toolkit_approximation"] = settings.get("approximation")
    return _image_output(alpha), [matte, *processor_nodes, alpha]


def _append_background_key_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str = "Translated"):
    label = f"VTK {label_prefix} {settings.get('label') or 'Background Key Matte'}"
    blur = _new_compositor_node(tree, "CompositorNodeBlur", f"{label} Background Plate", index, y_offset=-200, origin=origin)
    blur_size = float(settings.get("blur_size", 6.0) or 6.0)
    _set_input_default(blur, "Size", (blur_size, blur_size))
    _set_input_default(blur, "Type", "Gaussian")
    _set_input_default(blur, "Extend Bounds", True)
    _set_input_default(blur, "Separable", True)
    matte = _new_compositor_node(tree, "CompositorNodeDiffMatte", f"{label} Difference Matte", index + 1, y_offset=-100, origin=origin)
    _set_input_default(matte, "Tolerance", settings.get("tolerance", 0.10))
    _set_input_default(matte, "Falloff", settings.get("falloff", 0.0))
    set_alpha = _new_compositor_node(tree, "CompositorNodeSetAlpha", label, index + 2, origin=origin)
    _set_input_default(set_alpha, "Type", "Apply Mask")

    _link_socket(tree, input_socket, _image_input(blur))
    _link_socket(tree, input_socket, _socket_by_name(matte.inputs, "Image 1"))
    _link_socket(tree, _image_output(blur), _socket_by_name(matte.inputs, "Image 2"))
    _link_socket(tree, input_socket, _image_input(set_alpha))
    _link_socket(tree, _socket_by_name(matte.outputs, "Matte"), _socket_by_name(set_alpha.inputs, "Alpha"))

    for node in (blur, matte, set_alpha):
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "backgroundkey")
        node["video_toolkit_backgroundkey_threshold"] = float(settings.get("threshold", 0.08) or 0.08)
        node["video_toolkit_backgroundkey_similarity"] = float(settings.get("similarity", 0.10) or 0.10)
        node["video_toolkit_backgroundkey_blend"] = float(settings.get("blend", 0.0) or 0.0)
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
    return _image_output(set_alpha), [blur, matte, set_alpha]


def _append_shape_mask_alpha_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str, node_type: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Mask Alpha'}"
    mask = _new_compositor_node(tree, node_type, f"{label} Mask", index, y_offset=-160, origin=origin)
    for socket_name, value in dict(settings.get("mask_inputs", {})).items():
        _set_input_default(mask, str(socket_name), value)
    set_alpha = _new_compositor_node(tree, "CompositorNodeSetAlpha", label, index + 1, origin=origin)
    _set_input_default(set_alpha, "Type", settings.get("type", "Apply Mask"))
    _link_socket(tree, input_socket, _image_input(set_alpha))
    _link_socket(tree, _socket_by_name(mask.outputs, "Mask"), _socket_by_name(set_alpha.inputs, "Alpha"))
    return _image_output(set_alpha), [mask, set_alpha]


def _append_double_edge_mask_alpha_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Double Edge Mask'}"
    outer = _new_compositor_node(tree, "CompositorNodeBoxMask", f"{label} Outer", index, y_offset=-260, origin=origin)
    inner = _new_compositor_node(tree, "CompositorNodeEllipseMask", f"{label} Inner", index + 1, y_offset=-80, origin=origin)
    for socket_name, value in dict(settings.get("outer_inputs", {})).items():
        _set_input_default(outer, str(socket_name), value)
    for socket_name, value in dict(settings.get("inner_inputs", {})).items():
        _set_input_default(inner, str(socket_name), value)
    double_edge = _new_compositor_node(tree, "CompositorNodeDoubleEdgeMask", label, index + 2, y_offset=-160, origin=origin)
    _set_input_default(double_edge, "Only Inside Outer", bool(settings.get("only_inside_outer", True)))
    _link_socket(tree, _socket_by_name(outer.outputs, "Mask"), _socket_by_name(double_edge.inputs, "Outer Mask"))
    _link_socket(tree, _socket_by_name(inner.outputs, "Mask"), _socket_by_name(double_edge.inputs, "Inner Mask"))
    set_alpha = _new_compositor_node(tree, "CompositorNodeSetAlpha", f"{label} Alpha", index + 3, origin=origin)
    _set_input_default(set_alpha, "Type", settings.get("type", "Apply Mask"))
    _link_socket(tree, input_socket, _image_input(set_alpha))
    _link_socket(tree, _socket_by_name(double_edge.outputs, "Mask"), _socket_by_name(set_alpha.inputs, "Alpha"))
    return _image_output(set_alpha), [outer, inner, double_edge, set_alpha]


def _append_mask_to_sdf_alpha_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Mask to SDF'}"
    mask = _new_compositor_node(tree, "CompositorNodeBoxMask", f"{label} Source Mask", index, y_offset=-180, origin=origin)
    for socket_name, value in dict(settings.get("mask_inputs", {})).items():
        _set_input_default(mask, str(socket_name), value)
    sdf = _new_compositor_node(tree, "CompositorNodeMaskToSDF", label, index + 1, y_offset=-180, origin=origin)
    _link_socket(tree, _socket_by_name(mask.outputs, "Mask"), _socket_by_name(sdf.inputs, "Mask"))
    set_alpha = _new_compositor_node(tree, "CompositorNodeSetAlpha", f"{label} Alpha", index + 2, origin=origin)
    _set_input_default(set_alpha, "Type", settings.get("type", "Apply Mask"))
    _link_socket(tree, input_socket, _image_input(set_alpha))
    _link_socket(tree, _socket_by_name(sdf.outputs, "SDF"), _socket_by_name(set_alpha.inputs, "Alpha"))
    return _image_output(set_alpha), [mask, sdf, set_alpha]


def _append_source_overlay_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str, compositor_type: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Source Overlay'}"
    source_type = {
        "RGB_OVERLAY": "CompositorNodeRGB",
        "BLANK_IMAGE_OVERLAY": "CompositorNodeBlankImage",
        "TEXT_OVERLAY": "CompositorNodeStringToImage",
    }[compositor_type]
    source = _new_compositor_node(tree, source_type, f"{label} Source", index, y_offset=-160, origin=origin)
    for socket_name, value in dict(settings.get("inputs", {})).items():
        _set_input_default(source, str(socket_name), value)
    for socket_name, value in dict(settings.get("outputs", {})).items():
        _set_output_default(source, str(socket_name), value)
    alpha = _new_compositor_node(tree, "CompositorNodeAlphaOver", label, index + 1, origin=origin)
    _set_input_default(alpha, "Factor", settings.get("factor", 0.25))
    _set_input_default(alpha, "Type", settings.get("type", "Straight"))
    _set_input_default(alpha, "Straight Alpha", bool(settings.get("straight_alpha", True)))
    _link_socket(tree, input_socket, _socket_by_name(alpha.inputs, "Background"))
    _link_socket(tree, _image_output(source), _socket_by_name(alpha.inputs, "Foreground"))
    if settings.get("source"):
        for node in (source, alpha):
            node["video_toolkit_ffmpeg_filter"] = settings.get("source")
            if settings.get("approximation"):
                node["video_toolkit_approximation"] = settings.get("approximation")
            for key, value in dict(settings.get("metadata", {})).items():
                try:
                    node[f"video_toolkit_{key}"] = value
                except Exception:
                    node[f"video_toolkit_{key}"] = str(value)
    return _image_output(alpha), [source, alpha]


def _append_bokeh_image_blur_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Bokeh Image Blur'}"
    bokeh = _new_compositor_node(tree, "CompositorNodeBokehImage", f"{label} Bokeh", index, y_offset=-180, origin=origin)
    for socket_name, value in dict(settings.get("bokeh_inputs", {})).items():
        _set_input_default(bokeh, str(socket_name), value)
    blur = _new_compositor_node(tree, "CompositorNodeBokehBlur", label, index + 1, origin=origin)
    for socket_name, value in dict(settings.get("blur_inputs", {})).items():
        _set_input_default(blur, str(socket_name), value)
    _link_socket(tree, input_socket, _image_input(blur))
    _link_socket(tree, _image_output(bokeh), _socket_by_name(blur.inputs, "Bokeh"))
    return _image_output(blur), [bokeh, blur]


def _append_normalize_luma_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Normalize Luma'}"
    luma = _new_compositor_node(tree, "CompositorNodeRGBToBW", f"{label} Luma", index, y_offset=-160, origin=origin)
    normalize = _new_compositor_node(tree, "CompositorNodeNormalize", label, index + 1, y_offset=-160, origin=origin)
    combine = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Combine", index + 2, origin=origin)
    _set_input_default(combine, "Alpha", 1.0)
    _link_socket(tree, input_socket, _image_input(luma))
    _link_socket(tree, _first_socket(luma.outputs), _socket_by_name(normalize.inputs, "Value"))
    for input_name in ("Red", "Green", "Blue"):
        _link_socket(tree, _first_socket(normalize.outputs), _socket_by_name(combine.inputs, input_name))
    return _image_output(combine), [luma, normalize, combine]


def _append_scope_monitor_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Scope Monitor'}"
    separate = _new_compositor_node(tree, "CompositorNodeSeparateColor", f"{label} Separate RGB", index, y_offset=-360, origin=origin)
    image_levels = _new_compositor_node(tree, "CompositorNodeLevels", f"{label} Image Levels", index + 1, y_offset=-180, origin=origin)
    luma = _new_compositor_node(tree, "CompositorNodeRGBToBW", f"{label} Luma", index + 2, y_offset=0, origin=origin)
    luma_image = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Luma Image", index + 3, y_offset=0, origin=origin)
    luma_levels = _new_compositor_node(tree, "CompositorNodeLevels", f"{label} Luma Levels", index + 4, y_offset=180, origin=origin)
    info = _new_compositor_node(tree, "CompositorNodeImageInfo", f"{label} Image Info", index + 5, y_offset=360, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", f"{label} Viewer", index + 6, y_offset=0, origin=origin)
    _set_input_default(luma_image, "Alpha", 1.0)
    _link_socket(tree, input_socket, _image_input(separate))
    _link_socket(tree, input_socket, _image_input(image_levels))
    _link_socket(tree, input_socket, _image_input(luma))
    _link_socket(tree, input_socket, _image_input(info))
    for input_name in ("Red", "Green", "Blue"):
        _link_socket(tree, _first_socket(luma.outputs), _socket_by_name(luma_image.inputs, input_name))
    _link_socket(tree, _image_output(luma_image), _image_input(luma_levels))
    _link_socket(tree, _image_output(luma_image), _image_input(viewer))
    for node in (separate, image_levels, luma, luma_image, luma_levels, info, viewer):
        node["video_toolkit_scope"] = settings.get("scope", "scope")
        node["video_toolkit_scope_mode"] = settings.get("mode", "")
        node["video_toolkit_scope_components"] = settings.get("components", "")
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", settings.get("scope", "scope"))
        for key in ("pixel_x", "pixel_y", "pixel_width", "pixel_height", "window_opacity", "window_x", "window_y"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings[key]
        for key in (
            "threshold",
            "high",
            "low",
            "duration",
            "ratio",
            "pixel_threshold",
            "alpha",
            "period_min",
            "period_max",
            "radius",
            "block_pct",
            "block_width",
            "block_height",
            "round",
            "reset",
            "skip",
            "max_outliers",
            "mv_threshold",
            "min_val",
            "bitplane",
            "filter",
            "noise",
            "scene_threshold",
            "sc_pass",
            "intl_thres",
            "prog_thres",
            "rep_thres",
            "half_life",
            "analyze_interlaced_flag",
            "window",
            "method",
            "shakiness",
            "accuracy",
            "smoothing",
            "zoom",
        ):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings[key]
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
    return input_socket, [separate, image_levels, luma, luma_image, luma_levels, info, viewer]


def _append_identity_compare_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Identity Reference Difference'}"
    reference = _new_compositor_node(tree, "CompositorNodeBlur", f"{label} Reference Branch", index, y_offset=-240, origin=origin)
    blur_size = float(settings.get("blur_size", 3.0) or 0.0)
    _set_input_default(reference, "Size", (blur_size, blur_size))
    _set_input_default(reference, "Type", "Gaussian")
    _set_input_default(reference, "Extend Bounds", True)
    _set_input_default(reference, "Separable", True)

    diff = _new_compositor_node(tree, "CompositorNodeDiffMatte", f"{label} Difference Matte", index + 1, y_offset=-80, origin=origin)
    _set_input_default(diff, "Tolerance", settings.get("tolerance", 0.015))
    _set_input_default(diff, "Falloff", settings.get("falloff", 0.025))

    overlay = _new_compositor_node(tree, "CompositorNodeRGB", f"{label} Difference Color", index + 2, y_offset=120, origin=origin)
    _set_output_default(overlay, "Image", _rgba(settings.get("overlay_color", (1.0, 0.08, 0.0, 1.0))))

    alpha = _new_compositor_node(tree, "CompositorNodeAlphaOver", label, index + 3, origin=origin)
    _set_input_default(alpha, "Factor", settings.get("factor", 0.75))
    _set_input_default(alpha, "Type", settings.get("type", "Straight"))
    _set_input_default(alpha, "Straight Alpha", bool(settings.get("straight_alpha", True)))

    _link_socket(tree, input_socket, _image_input(reference))
    _link_socket(tree, input_socket, _socket_by_name(diff.inputs, "Image 1"))
    _link_socket(tree, _image_output(reference), _socket_by_name(diff.inputs, "Image 2"))
    _link_socket(tree, input_socket, _socket_by_name(alpha.inputs, "Background"))
    _link_socket(tree, _image_output(overlay), _socket_by_name(alpha.inputs, "Foreground"))
    _link_socket(tree, _socket_by_name(diff.outputs, "Matte"), _socket_by_name(alpha.inputs, "Factor"))

    for node in (reference, diff, overlay, alpha):
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "identity")
        node["video_toolkit_reference"] = settings.get("reference", "selected_strip_derived_branch")
        node["video_toolkit_identity_eof_action"] = settings.get("eof_action", "repeat")
        node["video_toolkit_identity_shortest"] = bool(settings.get("shortest", False))
        node["video_toolkit_identity_repeatlast"] = bool(settings.get("repeatlast", True))
        node["video_toolkit_identity_ts_sync_mode"] = settings.get("ts_sync_mode", "default")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
    return _image_output(alpha), [reference, diff, overlay, alpha]


def _append_quality_compare_filter(tree, input_socket, settings: dict[str, object], index: int, origin, label_prefix: str):
    label = f"VTK {label_prefix} {settings.get('label') or 'Quality Compare'}"
    luma = _new_compositor_node(tree, "CompositorNodeRGBToBW", f"{label} Source Luma", index, y_offset=-360, origin=origin)
    luma_image = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Source Luma Image", index + 1, y_offset=-360, origin=origin)
    reference = _new_compositor_node(tree, "CompositorNodeBlur", f"{label} Reference Branch", index + 2, y_offset=-160, origin=origin)
    reference_luma = _new_compositor_node(tree, "CompositorNodeRGBToBW", f"{label} Reference Luma", index + 3, y_offset=-160, origin=origin)
    reference_luma_image = _new_compositor_node(tree, "CompositorNodeCombineColor", f"{label} Reference Luma Image", index + 4, y_offset=-160, origin=origin)
    source_filter = _new_compositor_node(tree, "CompositorNodeFilter", f"{label} Source Emphasis", index + 5, y_offset=40, origin=origin)
    reference_filter = _new_compositor_node(tree, "CompositorNodeFilter", f"{label} Reference Emphasis", index + 6, y_offset=200, origin=origin)
    diff = _new_compositor_node(tree, "CompositorNodeDiffMatte", f"{label} Difference Matte", index + 7, y_offset=80, origin=origin)
    overlay = _new_compositor_node(tree, "CompositorNodeRGB", f"{label} Difference Color", index + 8, y_offset=260, origin=origin)
    alpha = _new_compositor_node(tree, "CompositorNodeAlphaOver", label, index + 9, origin=origin)

    blur_size = float(settings.get("blur_size", 2.0) or 0.0)
    _set_input_default(reference, "Size", (blur_size, blur_size))
    _set_input_default(reference, "Type", "Gaussian")
    _set_input_default(reference, "Extend Bounds", True)
    _set_input_default(reference, "Separable", True)
    for combine in (luma_image, reference_luma_image):
        _set_input_default(combine, "Alpha", 1.0)
    for filter_node in (source_filter, reference_filter):
        _set_input_default(filter_node, "Type", settings.get("filter_type", "Box Sharpen"))
        _set_input_default(filter_node, "Factor", settings.get("filter_factor", 1.0))
    _set_input_default(diff, "Tolerance", settings.get("tolerance", 0.018))
    _set_input_default(diff, "Falloff", settings.get("falloff", 0.025))
    _set_output_default(overlay, "Image", _rgba(settings.get("overlay_color", (1.0, 0.08, 0.0, 1.0))))
    _set_input_default(alpha, "Factor", settings.get("factor", 0.72))
    _set_input_default(alpha, "Type", settings.get("type", "Straight"))
    _set_input_default(alpha, "Straight Alpha", bool(settings.get("straight_alpha", True)))

    _link_socket(tree, input_socket, _image_input(luma))
    for input_name in ("Red", "Green", "Blue"):
        _link_socket(tree, _first_socket(luma.outputs), _socket_by_name(luma_image.inputs, input_name))
    _link_socket(tree, input_socket, _image_input(reference))
    _link_socket(tree, _image_output(reference), _image_input(reference_luma))
    for input_name in ("Red", "Green", "Blue"):
        _link_socket(tree, _first_socket(reference_luma.outputs), _socket_by_name(reference_luma_image.inputs, input_name))
    _link_socket(tree, _image_output(luma_image), _image_input(source_filter))
    _link_socket(tree, _image_output(reference_luma_image), _image_input(reference_filter))
    _link_socket(tree, _image_output(source_filter), _socket_by_name(diff.inputs, "Image 1"))
    _link_socket(tree, _image_output(reference_filter), _socket_by_name(diff.inputs, "Image 2"))
    _link_socket(tree, input_socket, _socket_by_name(alpha.inputs, "Background"))
    _link_socket(tree, _image_output(overlay), _socket_by_name(alpha.inputs, "Foreground"))
    _link_socket(tree, _socket_by_name(diff.outputs, "Matte"), _socket_by_name(alpha.inputs, "Factor"))

    created = [luma, luma_image, reference, reference_luma, reference_luma_image, source_filter, reference_filter, diff, overlay, alpha]
    for node in created:
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", settings.get("metric", "quality_compare"))
        node["video_toolkit_quality_metric"] = settings.get("metric", "")
        node["video_toolkit_quality_metric_mode"] = settings.get("metric_mode", "")
        node["video_toolkit_reference"] = settings.get("reference", "selected_strip_derived_branch")
        node["video_toolkit_framesync_eof_action"] = settings.get("eof_action", "repeat")
        node["video_toolkit_framesync_shortest"] = bool(settings.get("shortest", False))
        node["video_toolkit_framesync_repeatlast"] = bool(settings.get("repeatlast", True))
        node["video_toolkit_framesync_ts_sync_mode"] = settings.get("ts_sync_mode", "default")
        for key in ("stats_file", "stats_version", "output_max", "planes", "secondary"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings[key]
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
    return _image_output(alpha), created


def _translated_compositor_filter_to_node(
    tree,
    compositor_type: str,
    settings: dict[str, object],
    index: int,
    origin,
    label_prefix: str = "Translated",
    source_clip=None,
):
    labels = {
        "CHROMA_MATTE": "Chroma Matte",
        "COLOR_MATTE": "Color Matte",
        "COLOR_SPILL": "Color Spill",
        "BACKGROUND_KEY": "Background Key",
        "LUMA_MATTE": "Luma Matte",
        "BRIGHT_CONTRAST": "Brightness/Contrast",
        "COLOR_BALANCE": "Color Balance",
        "CURVE_RGB": "RGB Curves",
        "HUE_SAT": "Hue/Saturation",
        "HUE_CORRECT": "Hue Correct",
        "EXPOSURE": "Exposure",
        "COLOR_CORRECTION": "Color Correction",
        "TONEMAP": "Tone Map",
        "INVERT": "Invert",
        "CHANNEL_SHIFT": "Channel Shift",
        "PLANE_EXTRACT": "Plane Extract",
        "ALPHA_MERGE": "Alpha Merge",
        "PLANE_SHUFFLE": "Plane Shuffle",
        "POSTERIZE": "Posterize",
        "PREMUL_KEY": "Premul Key",
        "FILTER": "Filter",
        "DILATE_ERODE": "Dilate/Erode",
        "CONVOLVE": "Convolve",
        "BLUR": "Blur",
        "BILATERAL_BLUR": "Bilateral Blur",
        "DIRECTIONAL_BLUR": "Directional Blur",
        "SCALE": "Scale",
        "CROP": "Crop",
        "ROTATE": "Rotate",
        "FLIP": "Flip",
        "LENS_DISTORTION": "Lens Distortion",
        "DENOISE": "Denoise",
        "DESPECKLE": "Despeckle",
        "ANTI_ALIASING": "Anti-Aliasing",
        "IDENTITY_COMPARE": "Identity Compare",
        "QUALITY_COMPARE": "Quality Compare",
        "NATIVE_NODE": "Native Node",
    }
    node_label = str(settings.get("label") or labels.get(compositor_type, compositor_type.title()))
    label = f"VTK {label_prefix} {node_label}"
    if compositor_type == "NATIVE_NODE":
        node_type = str(settings.get("node_type", ""))
        if not node_type:
            return None
        node = _new_compositor_node(tree, node_type, label, index, origin=origin)
        if settings.get("assign_source_clip") and source_clip is not None:
            _assign_node_clip(node, source_clip)
        for socket_name, value in dict(settings.get("inputs", {})).items():
            _set_input_default(node, str(socket_name), value)
        for attr_name, value in dict(settings.get("properties", {})).items():
            attr = str(attr_name)
            if hasattr(node, attr):
                try:
                    setattr(node, attr, value)
                except Exception:
                    node[f"video_toolkit_property_{attr}"] = value
        node["video_toolkit_native_node"] = node_type
        node["video_toolkit_native_node_label"] = node_label
        if settings.get("source"):
            node["video_toolkit_ffmpeg_filter"] = settings.get("source")
        for key, value in dict(settings.get("metadata", {})).items():
            node[f"video_toolkit_{key}"] = value
        if settings.get("note"):
            node["video_toolkit_note"] = settings.get("note")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "CHROMA_MATTE":
        node = _new_compositor_node(tree, "CompositorNodeChromaMatte", label, index, origin=origin)
        _set_input_default(node, "Key Color", _rgba(settings.get("key_color", (0.0, 0.0, 0.0))))
        _set_input_default(node, "Minimum", settings.get("minimum", 0.0))
        _set_input_default(node, "Maximum", settings.get("maximum", 0.1))
        _set_input_default(node, "Falloff", settings.get("falloff", 0.0))
        return node
    if compositor_type == "COLOR_MATTE":
        node = _new_compositor_node(tree, "CompositorNodeColorMatte", label, index, origin=origin)
        _set_input_default(node, "Key Color", _rgba(settings.get("key_color", (0.0, 0.0, 0.0))))
        _set_input_default(node, "Hue", settings.get("hue", 0.02))
        _set_input_default(node, "Saturation", settings.get("saturation", 0.02))
        _set_input_default(node, "Value", settings.get("value", 0.02))
        return node
    if compositor_type == "COLOR_SPILL":
        node = _new_compositor_node(tree, "CompositorNodeColorSpill", label, index, origin=origin)
        _set_input_default(node, "Factor", settings.get("factor", 0.5))
        _set_input_default(node, "Spill Channel", settings.get("spill_channel", "Green"))
        _set_input_default(node, "Limit Method", settings.get("limit_method", "Single"))
        _set_input_default(node, "Limit Channel", settings.get("limit_channel", "Red"))
        _set_input_default(node, "Limit Strength", settings.get("limit_strength", 0.0))
        _set_input_default(node, "Use Spill Strength", bool(settings.get("use_spill_strength", True)))
        _set_input_default(node, "Strength", settings.get("strength", 0.6))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "despill")
        node["video_toolkit_spill_channel"] = settings.get("spill_channel", "")
        node["video_toolkit_channel_scales"] = str(settings.get("channel_scales", {}))
        node["video_toolkit_brightness"] = float(settings.get("brightness", 0.0) or 0.0)
        node["video_toolkit_alpha"] = bool(settings.get("alpha", False))
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "LUMA_MATTE":
        node = _new_compositor_node(tree, "CompositorNodeLumaMatte", label, index, origin=origin)
        _set_input_default(node, "Minimum", settings.get("minimum", 0.0))
        _set_input_default(node, "Maximum", settings.get("maximum", 1.0))
        return node
    if compositor_type == "BRIGHT_CONTRAST":
        node = _new_compositor_node(tree, "CompositorNodeBrightContrast", label, index, origin=origin)
        _set_input_default_candidates(node, ("Brightness", "Bright"), settings.get("bright", 0.0))
        _set_input_default(node, "Contrast", settings.get("contrast", 0.0))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "bright_contrast")
        return node
    if compositor_type == "COLOR_BALANCE":
        node = _new_compositor_node(tree, "CompositorNodeColorBalance", label, index, origin=origin)
        _set_input_default_candidates(node, ("Fac", "Factor"), settings.get("factor", 1.0))
        _set_input_default_candidates(node, ("Type",), _color_balance_method_name(settings))
        white_value = settings.get("white_value")
        if white_value is not None:
            rgba = _rgba(white_value)
            _set_input_default_candidates(node, ("Color Gamma", "Gamma"), rgba)
            _set_input_default_candidates(node, ("Color Gain", "Gain"), rgba)
        for key, socket_names in (
            ("color_balance.lift", ("Color Lift", "Lift")),
            ("color_balance.gamma", ("Color Gamma", "Gamma")),
            ("color_balance.gain", ("Color Gain", "Gain")),
            ("color_balance.offset", ("Color Offset", "Offset")),
            ("color_balance.power", ("Color Power", "Power")),
            ("color_balance.slope", ("Color Slope", "Slope")),
        ):
            value = settings.get(key)
            if value is not None:
                _set_input_default_candidates(node, socket_names, _rgba(value))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "color_balance")
        node["video_toolkit_modifier_type"] = settings.get("modifier_type", "")
        if "color_multiply" in settings:
            node["video_toolkit_color_multiply"] = float(settings.get("color_multiply", 1.0) or 1.0)
        for key in ("red_cyan", "green_magenta", "blue_yellow", "mix", "tint"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings.get(key)
        return node
    if compositor_type == "CURVE_RGB":
        node = _new_compositor_node(tree, "CompositorNodeCurveRGB", label, index, origin=origin)
        curve_points = settings.get("__curve_points__")
        if curve_points:
            _apply_curve_points(node.mapping, curve_points)
        if "black_level" in settings:
            _set_input_default(node, "Black Level", _rgba(settings.get("black_level")))
        if "white_level" in settings:
            _set_input_default(node, "White Level", _rgba(settings.get("white_level")))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "curves")
        node["video_toolkit_modifier_type"] = settings.get("modifier_type", "")
        for key in ("minimum", "maximum"):
            if key in settings:
                node[f"video_toolkit_{key}"] = float(settings.get(key, 0.0) or 0.0)
        return node
    if compositor_type == "HUE_SAT":
        node = _new_compositor_node(tree, "CompositorNodeHueSat", label, index, origin=origin)
        _set_input_default(node, "Hue", settings.get("hue", 0.5))
        _set_input_default(node, "Saturation", settings.get("saturation", 1.0))
        _set_input_default(node, "Value", settings.get("value", 1.0))
        _set_input_default_candidates(node, ("Factor", "Fac"), settings.get("factor", 1.0))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "hue")
        return node
    if compositor_type == "HUE_CORRECT":
        node = _new_compositor_node(tree, "CompositorNodeHueCorrect", label, index, origin=origin)
        hue_values = settings.get("__hue_correct__")
        curve_points = settings.get("__curve_points__")
        if hue_values:
            _apply_hue_correct(node.mapping, hue_values)
        if curve_points:
            _apply_curve_points(node.mapping, curve_points)
        _set_input_default_candidates(node, ("Factor", "Fac"), settings.get("factor", 1.0))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "hue_correct")
        node["video_toolkit_modifier_type"] = settings.get("modifier_type", "")
        for key in ("held_color", "hue_degrees", "similarity", "blend", "mix", "tint"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings.get(key)
        return node
    if compositor_type == "EXPOSURE":
        node = _new_compositor_node(tree, "CompositorNodeExposure", label, index, origin=origin)
        _set_input_default(node, "Exposure", settings.get("exposure", 0.0))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "exposure")
        node["video_toolkit_black_level"] = float(settings.get("black", 0.0) or 0.0)
        return node
    if compositor_type == "COLOR_CORRECTION":
        node = _new_compositor_node(tree, "CompositorNodeColorCorrection", label, index, origin=origin)
        _set_input_default_candidates(node, ("Master Saturation", "Saturation"), settings.get("saturation", 1.0))
        _set_input_default_candidates(node, ("Shadows Offset",), settings.get("shadow_offset", 0.0))
        _set_input_default_candidates(node, ("Highlights Gain",), settings.get("highlight_gain", 1.0))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "colorcorrect")
        for key in ("red_low", "blue_low", "red_high", "blue_high"):
            if key in settings:
                node[f"video_toolkit_{key}"] = float(settings.get(key, 0.0) or 0.0)
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "TONEMAP":
        node = _new_compositor_node(tree, "CompositorNodeTonemap", label, index, origin=origin)
        _set_input_default(node, "Type", _tonemap_type_name(settings.get("tonemap_type")))
        for key, socket_name in (
            ("key", "Key"),
            ("offset", "Offset"),
            ("gamma", "Gamma"),
            ("intensity", "Intensity"),
            ("contrast", "Contrast"),
            ("adaptation", "Light Adaptation"),
            ("correction", "Chromatic Adaptation"),
        ):
            if key in settings:
                _set_input_default(node, socket_name, settings[key])
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "tonemap")
        node["video_toolkit_modifier_type"] = settings.get("modifier_type", "")
        for key in ("window", "method"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings[key]
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "INVERT":
        node = _new_compositor_node(tree, "CompositorNodeInvert", label, index, origin=origin)
        _set_input_default_candidates(node, ("Factor", "Fac"), settings.get("factor", 1.0))
        _set_input_default(node, "Invert Color", bool(settings.get("invert_color", True)))
        _set_input_default(node, "Invert Alpha", bool(settings.get("invert_alpha", False)))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "negate")
        node["video_toolkit_components"] = settings.get("components", "")
        return node
    if compositor_type == "PREMUL_KEY":
        node = _new_compositor_node(tree, "CompositorNodePremulKey", label, index, origin=origin)
        _set_input_default(node, "Type", settings.get("mode", "To Premultiplied"))
        return node
    if compositor_type == "POSTERIZE":
        node = _new_compositor_node(tree, "CompositorNodePosterize", label, index, origin=origin)
        _set_input_default(node, "Steps", settings.get("steps", 8.0))
        return node
    if compositor_type == "FILTER":
        node = _new_compositor_node(tree, "CompositorNodeFilter", label, index, origin=origin)
        _set_input_default(node, "Type", settings.get("filter_type", "Box Sharpen"))
        _set_input_default(node, "Factor", settings.get("factor", 1.0))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "filter")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "DILATE_ERODE":
        node = _new_compositor_node(tree, "CompositorNodeDilateErode", label, index, origin=origin)
        _set_input_default(node, "Type", settings.get("mode", "Steps"))
        _set_input_default(node, "Size", settings.get("size", 1))
        _set_input_default(node, "Falloff Size", settings.get("falloff_size", 0.0))
        _set_input_default(node, "Falloff", settings.get("falloff", "Smooth"))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "dilate_erode")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "BLUR":
        node = _new_compositor_node(tree, "CompositorNodeBlur", label, index, origin=origin)
        _set_input_default(node, "Size", settings.get("size", (1.0, 1.0)))
        _set_input_default(node, "Type", settings.get("blur_type", "Gaussian"))
        _set_input_default(node, "Extend Bounds", bool(settings.get("extend_bounds", False)))
        _set_input_default(node, "Separable", bool(settings.get("separable", True)))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "blur")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        node["video_toolkit_blur_samples"] = int(settings.get("samples", 1) or 1)
        for key in ("mode", "parity", "deint", "frames", "weights"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings[key]
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "BILATERAL_BLUR":
        node = _new_compositor_node(tree, "CompositorNodeBilateralblur", label, index, origin=origin)
        _set_input_default(node, "Size", settings.get("size", 1))
        _set_input_default(node, "Threshold", settings.get("threshold", 0.1))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "smartblur")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        node["video_toolkit_blur_strength"] = float(settings.get("strength", 1.0) or 1.0)
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "DIRECTIONAL_BLUR":
        node = _new_compositor_node(tree, "CompositorNodeDBlur", label, index, origin=origin)
        _set_input_default(node, "Samples", settings.get("samples", 1))
        _set_input_default(node, "Center", settings.get("center", (0.5, 0.5)))
        _set_input_default(node, "Rotation", settings.get("rotation", 0.0))
        _set_input_default(node, "Scale", settings.get("scale", 1.0))
        _set_input_default(node, "Amount", settings.get("amount", 0.0))
        _set_input_default(node, "Direction", settings.get("direction", 0.0))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "dblur")
        node["video_toolkit_blur_angle"] = float(settings.get("angle", 0.0) or 0.0)
        node["video_toolkit_blur_radius"] = float(settings.get("radius", 0.0) or 0.0)
        for key in ("fps", "mi_mode"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings[key]
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "SCALE":
        node = _new_compositor_node(tree, "CompositorNodeScale", label, index, origin=origin)
        _set_input_default(node, "Type", settings.get("type", "Relative"))
        _set_input_default(node, "X", settings.get("x", 1.0))
        _set_input_default(node, "Y", settings.get("y", 1.0))
        _set_input_default(node, "Frame Type", settings.get("frame_type", "Stretch"))
        _set_input_default(node, "Interpolation", settings.get("interpolation", "Bilinear"))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "scale")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        node["video_toolkit_width_expression"] = settings.get("width_expression", "")
        node["video_toolkit_height_expression"] = settings.get("height_expression", "")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "CROP":
        node = _new_compositor_node(tree, "CompositorNodeCrop", label, index, origin=origin)
        _set_input_default(node, "X", settings.get("x", 0))
        _set_input_default(node, "Y", settings.get("y", 0))
        _set_input_default(node, "Width", settings.get("width", 1920))
        _set_input_default(node, "Height", settings.get("height", 1080))
        _set_input_default(node, "Alpha Crop", bool(settings.get("alpha_crop", False)))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "crop")
        node["video_toolkit_width_expression"] = settings.get("width_expression", "")
        node["video_toolkit_height_expression"] = settings.get("height_expression", "")
        return node
    if compositor_type == "ROTATE":
        node = _new_compositor_node(tree, "CompositorNodeRotate", label, index, origin=origin)
        _set_input_default(node, "Angle", settings.get("angle", 0.0))
        _set_input_default(node, "Interpolation", settings.get("interpolation", "Bilinear"))
        _set_input_default(node, "Extension X", settings.get("extension_x", "Clip"))
        _set_input_default(node, "Extension Y", settings.get("extension_y", "Clip"))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "rotate")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        node["video_toolkit_angle_expression"] = settings.get("angle_expression", "")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "FLIP":
        node = _new_compositor_node(tree, "CompositorNodeFlip", label, index, origin=origin)
        _set_input_default(node, "Flip X", bool(settings.get("flip_x", False)))
        _set_input_default(node, "Flip Y", bool(settings.get("flip_y", False)))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "flip")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "LENS_DISTORTION":
        node = _new_compositor_node(tree, "CompositorNodeLensdist", label, index, origin=origin)
        _set_input_default(node, "Type", settings.get("type", "Radial"))
        _set_input_default(node, "Distortion", settings.get("distortion", 0.0))
        _set_input_default(node, "Dispersion", settings.get("dispersion", 0.0))
        _set_input_default(node, "Fit", bool(settings.get("fit", True)))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "lenscorrection")
        node["video_toolkit_lens_center"] = tuple(settings.get("center", (0.5, 0.5)))
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "DENOISE":
        node = _new_compositor_node(tree, "CompositorNodeDenoise", label, index, origin=origin)
        _set_input_default(node, "HDR", bool(settings.get("hdr", False)))
        _set_input_default(node, "Prefilter", settings.get("prefilter", "Accurate"))
        _set_input_default(node, "Quality", settings.get("quality", "Balanced"))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "denoise")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        node["video_toolkit_denoise_strength"] = float(settings.get("strength", 1.0) or 1.0)
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    if compositor_type == "DESPECKLE":
        node = _new_compositor_node(tree, "CompositorNodeDespeckle", label, index, origin=origin)
        _set_input_default_candidates(node, ("Factor", "Fac"), settings.get("factor", 0.35))
        _set_input_default(node, "Color Threshold", settings.get("color_threshold", 0.35))
        _set_input_default(node, "Neighbor Threshold", settings.get("neighbor_threshold", 0.35))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "median")
        return node
    if compositor_type == "ANTI_ALIASING":
        node = _new_compositor_node(tree, "CompositorNodeAntiAliasing", label, index, origin=origin)
        _set_input_default(node, "Threshold", settings.get("threshold", 0.2))
        _set_input_default(node, "Contrast Limit", settings.get("contrast_limit", 2.0))
        _set_input_default(node, "Corner Rounding", settings.get("corner_rounding", 0.25))
        node["video_toolkit_ffmpeg_filter"] = settings.get("source", "deblock")
        if settings.get("hardware_filter"):
            node["video_toolkit_hardware_filter"] = settings.get("hardware_filter")
        node["video_toolkit_block_size"] = float(settings.get("block", 8.0) or 8.0)
        for key in ("mode", "parity", "deint"):
            if key in settings:
                node[f"video_toolkit_{key}"] = settings[key]
        if settings.get("approximation"):
            node["video_toolkit_approximation"] = settings.get("approximation")
        return node
    return None


def _create_compositor_restoration_stack(scene, strip):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", "VTK Restore Source", 0, origin=origin)
    clip = _assign_movie_clip(movie, _movie_path(strip))
    stabilize = _new_compositor_node(tree, "CompositorNodeStabilize", "VTK Stabilize", 1, origin=origin)
    _assign_node_clip(stabilize, clip)
    distortion = _new_compositor_node(tree, "CompositorNodeMovieDistortion", "VTK Movie Distortion", 2, origin=origin)
    _assign_node_clip(distortion, clip)
    denoise = _new_compositor_node(tree, "CompositorNodeDenoise", "VTK Denoise", 3, origin=origin)
    _set_input_default(denoise, "HDR", False)
    despeckle = _new_compositor_node(tree, "CompositorNodeDespeckle", "VTK Despeckle", 4, origin=origin)
    _set_input_default(despeckle, "Factor", 0.35)
    _set_input_default(despeckle, "Color Threshold", 0.35)
    _set_input_default(despeckle, "Neighbor Threshold", 0.35)
    bilateral = _new_compositor_node(tree, "CompositorNodeBilateralblur", "VTK Bilateral Blur", 5, origin=origin)
    _set_input_default(bilateral, "Size", 3.0)
    _set_input_default(bilateral, "Threshold", 0.08)
    antialias = _new_compositor_node(tree, "CompositorNodeAntiAliasing", "VTK Anti-Aliasing", 6, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", "VTK Restore Viewer", 7, origin=origin)
    output = _new_output_file_node(tree, scene, 7, y_offset=-160, origin=origin)
    final_socket = _link_compositor_chain(tree, [movie, stabilize, distortion, denoise, despeckle, bilateral, antialias])
    _link_socket(tree, final_socket, _image_input(viewer))
    _link_socket(tree, final_socket, _first_socket(output.inputs))
    return [movie, stabilize, distortion, denoise, despeckle, bilateral, antialias, viewer, output]


def _create_compositor_node_library(scene, strip):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    clip = _assign_movie_clip_to_data(_movie_path(strip))
    created = []
    category_rows: dict[str, int] = {}
    category_columns: dict[str, int] = {}
    for tool in compositor_node_tools():
        if tool.category not in category_rows:
            category_rows[tool.category] = len(category_rows)
            category_columns[tool.category] = 0
        row = category_rows[tool.category]
        column = category_columns[tool.category]
        category_columns[tool.category] += 1
        node = _new_compositor_node(
            tree,
            tool.node_type,
            f"VTK Library {tool.category} - {tool.label}",
            column,
            y_offset=-(row * 280),
            origin=origin,
        )
        _configure_library_node(node, scene, clip)
        created.append(node)
    return created


def _ensure_compositor_tree(scene):
    if hasattr(scene.render, "use_compositing"):
        scene.render.use_compositing = True
    if hasattr(scene, "compositing_node_group"):
        tree = scene.compositing_node_group
        if tree is None:
            tree = bpy.data.node_groups.new("Video Toolkit Compositor", "CompositorNodeTree")
            scene.compositing_node_group = tree
        return tree
    if hasattr(scene, "use_nodes"):
        scene.use_nodes = True
    tree = getattr(scene, "node_tree", None)
    if tree is None:
        raise RuntimeError("This Blender build does not expose a compositor node tree")
    return tree


def _compositor_tree_or_none(scene):
    if hasattr(scene, "compositing_node_group"):
        return scene.compositing_node_group
    if hasattr(scene, "use_nodes") and not scene.use_nodes:
        return None
    return getattr(scene, "node_tree", None)


def _new_compositor_node(tree, node_type: str, label: str, index: int, y_offset: int = 0, origin=(0, 0)):
    node = tree.nodes.new(node_type)
    node.label = label
    node.name = label
    node.location = (origin[0] + (index * 240), origin[1] + y_offset)
    node["video_toolkit"] = True
    return node


def _new_output_file_node(tree, scene, index: int, y_offset: int = 0, origin=(0, 0)):
    node = _new_compositor_node(tree, "CompositorNodeOutputFile", "VTK Output File", index, y_offset=y_offset, origin=origin)
    if hasattr(node, "base_path"):
        node.base_path = str(_output_dir(scene))
    return node


def _next_node_origin(tree) -> tuple[int, int]:
    toolkit_nodes = [node for node in tree.nodes if getattr(node, "name", "").startswith("VTK ")]
    if not toolkit_nodes:
        return (0, 0)
    return (int(max(node.location.x for node in toolkit_nodes) + 320), int(min(node.location.y for node in toolkit_nodes) - 260))


def _assign_movie_clip(node, path: Path):
    clip = _assign_movie_clip_to_data(path)
    node.clip = clip
    return clip


def _assign_movie_clip_to_data(path: Path):
    return bpy.data.movieclips.load(str(path), check_existing=True)


def _assign_node_clip(node, clip) -> None:
    if hasattr(node, "clip"):
        node.clip = clip


def _configure_library_node(node, scene, clip) -> None:
    if node.bl_idname == "CompositorNodeMovieClip":
        node.clip = clip
    else:
        _assign_node_clip(node, clip)
    if node.bl_idname == "CompositorNodeOutputFile" and hasattr(node, "base_path"):
        node.base_path = str(_output_dir(scene))
    if node.bl_idname == "CompositorNodeRGB":
        _set_output_default(node, "Color", (1.0, 1.0, 1.0, 1.0))
    _set_input_default(node, "Factor", 1.0)
    _set_input_default(node, "Fac", 1.0)
    _set_input_default(node, "Threshold", 0.08)
    _set_input_default(node, "Size", 3.0)
    _set_input_default(node, "Saturation", 1.0)
    _set_input_default(node, "Value", 1.0)


def _compositor_node_summary(nodes) -> str:
    labels = [node.label or node.bl_idname for node in nodes]
    if len(labels) <= 8:
        return ", ".join(labels)
    return f"{len(labels)} nodes: " + ", ".join(labels[:8]) + ", ..."


def _link_compositor_chain(tree, nodes):
    current = _image_output(nodes[0])
    for node in nodes[1:]:
        _link_socket(tree, current, _image_input(node))
        current = _image_output(node)
    return current


def _link_socket(tree, output_socket, input_socket) -> None:
    if output_socket is None or input_socket is None:
        raise RuntimeError("Could not link compositor node sockets")
    tree.links.new(output_socket, input_socket)


def _image_input(node):
    return _socket_by_name(node.inputs, "Image") or _first_socket(node.inputs)


def _image_output(node):
    return _socket_by_name(node.outputs, "Image") or _first_socket(node.outputs)


def _socket_by_name(sockets, name: str):
    for socket in sockets:
        if socket.name == name or getattr(socket, "identifier", "") == name:
            return socket
    return None


def _color_input_socket(node, socket_names, value):
    names = set(socket_names)
    for socket in node.inputs:
        if socket.name not in names and getattr(socket, "identifier", "") not in names:
            continue
        if _try_set_socket_default(socket, value):
            return socket
    return None


def _first_socket(sockets):
    return next(iter(sockets), None)


def _set_input_default(node, socket_name: str, value) -> None:
    _set_input_default_candidates(node, (socket_name,), value)


def _set_node_property(node, attr: str, value) -> bool:
    if not hasattr(node, attr):
        node[f"video_toolkit_property_{attr}"] = value
        return False
    try:
        setattr(node, attr, value)
        return True
    except Exception:
        node[f"video_toolkit_property_{attr}"] = value
        return False


def _set_input_default_candidates(node, socket_names, value) -> bool:
    names = set(socket_names)
    for socket in node.inputs:
        if socket.name not in names and getattr(socket, "identifier", "") not in names:
            continue
        if _try_set_socket_default(socket, value):
            return True
    return False


def _try_set_socket_default(socket, value) -> bool:
    if socket is None or not hasattr(socket, "default_value"):
        return False
    current = socket.default_value
    try:
        if hasattr(current, "__setitem__") and isinstance(value, (tuple, list)):
            for index, item in enumerate(value[: len(current)]):
                current[index] = item
        else:
            socket.default_value = value
        return True
    except Exception:
        return False


def _rgba(value, alpha: float = 1.0) -> tuple[float, float, float, float]:
    if not isinstance(value, (tuple, list)):
        return (float(value), float(value), float(value), alpha)
    values = list(value)
    if len(values) >= 4:
        return tuple(float(item) for item in values[:4])
    while len(values) < 3:
        values.append(1.0)
    return (float(values[0]), float(values[1]), float(values[2]), alpha)


def _sampled_color_management_white_balance(profile) -> tuple[float, float, float, float]:
    temperature_delta = _clamp_node_value((float(profile.white_balance_temperature) - 6500.0) / 2400.0, -1.0, 1.0)
    tint_delta = _clamp_node_value(float(profile.white_balance_tint) / 45.0, -1.0, 1.0)
    red = _clamp_node_value(1.0 + temperature_delta * 0.10 + max(tint_delta, 0.0) * 0.025, 0.86, 1.14)
    green = _clamp_node_value(1.0 - tint_delta * 0.08, 0.88, 1.12)
    blue = _clamp_node_value(1.0 - temperature_delta * 0.10 + max(tint_delta, 0.0) * 0.025, 0.86, 1.14)
    return (red, green, blue, 1.0)


def _color_balance_method_name(settings: dict[str, object]) -> str:
    method = str(settings.get("color_balance.correction_method", "LIFT_GAMMA_GAIN"))
    if method == "OFFSET_POWER_SLOPE":
        return "OFFSET_POWER_SLOPE"
    return "LIFT_GAMMA_GAIN"


def _tonemap_type_name(value) -> str:
    if str(value) == "RH_SIMPLE":
        return "RH_SIMPLE"
    return "RD_PHOTORECEPTOR"


def _set_output_default(node, socket_name: str, value) -> None:
    socket = _socket_by_name(node.outputs, socket_name)
    if socket is None or not hasattr(socket, "default_value"):
        return
    current = socket.default_value
    try:
        if hasattr(current, "__setitem__") and isinstance(value, (tuple, list)):
            for index, item in enumerate(value[: len(current)]):
                current[index] = item
        else:
            socket.default_value = value
    except Exception:
        return


def _clamp_node_value(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _modifier_label(modifier_type: str) -> str:
    return modifier_type.replace("_", " ").title()


def _set_nested_attr(target, dotted_path: str, value) -> None:
    if dotted_path == "__metadata__":
        _store_modifier_metadata(target, value)
        return
    if dotted_path == "__curve_points__":
        _apply_curve_points(target.curve_mapping, value)
        return
    if dotted_path == "__hue_correct__":
        _apply_hue_correct(target.curve_mapping, value)
        return
    parts = dotted_path.split(".")
    obj = target
    for part in parts[:-1]:
        obj = getattr(obj, part)
    attr = parts[-1]
    current = getattr(obj, attr, None)
    if hasattr(current, "__setitem__") and isinstance(value, (tuple, list)):
        current[:] = value
    else:
        setattr(obj, attr, value)


def _store_modifier_metadata(target, metadata) -> None:
    for key, value in dict(metadata or {}).items():
        prop_name = f"video_toolkit_{key}"
        try:
            target[prop_name] = value
        except Exception:
            try:
                target[prop_name] = str(value)
            except Exception:
                continue


def _apply_curve_points(curve_mapping, curve_points) -> None:
    for curve_index, points in curve_points.items():
        curve = curve_mapping.curves[int(curve_index)]
        _set_curve_points(curve, points)
    curve_mapping.update()


def _apply_hue_correct(curve_mapping, values) -> None:
    for name, curve_index in (("hue", 0), ("saturation", 1), ("value", 2)):
        if name not in values:
            continue
        y_value = float(values[name])
        curve = curve_mapping.curves[curve_index]
        for point in curve.points:
            point.location[1] = y_value
    curve_mapping.update()


def _set_curve_points(curve, points) -> None:
    points = list(points)
    while len(curve.points) > len(points):
        curve.points.remove(curve.points[-1])
    while len(curve.points) < len(points):
        x, y = points[len(curve.points)]
        curve.points.new(float(x), float(y))
    for point, (x, y) in zip(curve.points, points):
        point.location[0] = float(x)
        point.location[1] = float(y)
        point.handle_type = "AUTO"


def _render_ffmpeg_tool(context, strip, tool) -> Path:
    if strip.type != "MOVIE":
        raise RuntimeError("FFmpeg tools require an active movie strip")
    source_path = Path(bpy.path.abspath(strip.filepath))
    if not source_path.exists():
        raise RuntimeError(f"Source movie does not exist: {source_path}")
    scene = context.scene
    output_dir = _output_dir(scene)
    output_path = _unique_output_path(output_dir, source_path, tool.id)
    try:
        process_video(
            tool.id,
            source_path,
            output_path,
            crf=scene.video_toolkit_crf,
            preset=scene.video_toolkit_preset,
            keep_audio=scene.video_toolkit_keep_audio,
            work_dir=output_dir,
        )
    except FFmpegError as exc:
        raise RuntimeError(str(exc)) from exc
    scene.video_toolkit_last_output = str(output_path)
    if scene.video_toolkit_add_strip:
        _add_rendered_strip(scene, strip, output_path, tool.label)
    return output_path


def _movie_path(strip) -> Path:
    if strip.type != "MOVIE":
        raise RuntimeError("Color analysis requires a movie strip")
    path = Path(bpy.path.abspath(strip.filepath))
    if not path.exists():
        raise RuntimeError(f"Source movie does not exist: {path}")
    return path


def _write_diagnostics_text(strip, report: str):
    name = f"VTK Color Diagnostics - {strip.name}"
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    text.clear()
    text.write(report + "\n")
    return text


def _write_catalog_coverage_text():
    name = "VTK Video Effects Catalog Coverage"
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    text.clear()
    text.write(_catalog_coverage_report() + "\n")
    return text


def _write_recipe_recommendation_text(strip, stats, diagnosis, recommendations):
    name = f"VTK Recipe Recommendations - {strip.name}"
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    text.clear()
    text.write(_recipe_recommendation_report(strip, stats, diagnosis, recommendations) + "\n")
    return text


def _recipe_recommendation_report(strip, stats, diagnosis, recommendations) -> str:
    dynamic_range = stats.luma_p95 - stats.luma_p05
    top_ids = ", ".join(tool.id for _score, tool, _reasons in recommendations[:12])
    lines = [
        "Open Research Video Toolkit Recipe Recommendations",
        "",
        f"Source strip: {strip.name}",
        f"Sampled frames: {stats.samples}",
        f"Frame stats: {summarize_stats(stats)}",
        f"Luma p05/mean/p95/range: {stats.luma_p05:.1f}/{stats.mean_luma:.1f}/{stats.luma_p95:.1f}/{dynamic_range:.1f}",
        f"Saturation/chroma: {stats.mean_saturation:.2f}/{stats.mean_chroma:.1f}",
        f"Warm/cool/skin: {stats.warm_ratio:.2f}/{stats.cool_ratio:.2f}/{stats.skin_ratio:.2f}",
        "Palette: " + (" ".join(diagnosis.palette_hex) if diagnosis.palette_hex else "none"),
        "",
        "Diagnosis:",
        *[f"- {finding}" for finding in diagnosis.findings],
        "",
        "Diagnostic suggested tools:",
        *[f"- {tool}" for tool in diagnosis.suggested_tools],
        "",
        "Top Blender-native recipes:",
    ]
    for rank, (score, tool, reasons) in enumerate(recommendations[:12], start=1):
        compatibility = "compositor-compatible" if _tool_has_compositor_stack(tool) else "VSE live only"
        modifiers = ", ".join(_tool_modifier_names(tool)) or "none"
        lines.extend(
            [
                f"{rank}. {tool.label} ({tool.id}) - score {score:.1f}",
                f"   Category: {tool.category}; {compatibility}",
                f"   Blender modifiers: {modifiers}",
                "   Reasons: " + "; ".join(reasons[:6]),
            ]
        )
    lines.extend(
        [
            "",
            "Recommended sidecar order:",
            top_ids,
            "",
            "How to use:",
            "Open the Video Effects sidecar, keep the selected Tool entry or choose another ranked recipe, then Apply for live VSE modifiers or Nodes for the compositor graph when available.",
        ]
    )
    return "\n".join(lines)


def _rank_catalog_recipes(stats, diagnosis):
    recommendations = []
    for tool in all_tools():
        if not _is_color_recommendation_tool(tool):
            continue
        score, reasons = _score_catalog_recipe(tool, stats, diagnosis)
        if score <= 0.0:
            continue
        recommendations.append((score, tool, tuple(reasons)))
    recommendations.sort(key=lambda item: (-item[0], item[1].category, item[1].label))
    return tuple(recommendations)


def _recommended_recipe_mix_stack(recommendations, count: int):
    stack = []
    labels = []
    recipe_ids = []
    for _score, tool, _reasons in recommendations[:count]:
        recipe_stack = _tool_compositor_stack(tool)
        if not recipe_stack:
            continue
        labels.append(tool.label)
        recipe_ids.append(tool.id)
        stack.extend(recipe_stack)
    return tuple(stack), tuple(labels), tuple(recipe_ids)


def _is_color_recommendation_tool(tool) -> bool:
    if not tool.is_blender_modifier:
        return False
    if tool.category not in {"Live Blender Color", "Native Blender Primitives", "Live Blender Modifiers"}:
        return False
    if "mask" in tool.id:
        return False
    return bool(_tool_modifier_names(tool))


def _score_catalog_recipe(tool, stats, diagnosis):
    text = f"{tool.id} {tool.label} {tool.description}".lower()
    modifiers = set(_tool_modifier_names(tool))
    dynamic_range = stats.luma_p95 - stats.luma_p05
    warm_delta = stats.warm_ratio - stats.cool_ratio
    score = 0.0
    reasons: list[str] = []

    def add(points: float, reason: str) -> None:
        nonlocal score
        score += points
        if reason not in reasons:
            reasons.append(reason)

    if tool.label in diagnosis.suggested_tools:
        add(40.0, "direct match to sampled color diagnosis")
    if _tool_has_compositor_stack(tool):
        add(2.0, "can also generate a native compositor recipe")
    if tool.category == "Live Blender Color":
        add(3.0, "one-click live Blender color recipe")
    if tool.id in {"live_pro_color_stack", "auto_enhance", "primary_color_board"}:
        add(8.0, "broad finishing stack for mixed luma/color issues")
    if tool.id == "neutral_grade" and 108.0 <= stats.mean_luma <= 170.0 and 0.20 <= stats.mean_saturation <= 0.58:
        add(9.0, "sampled exposure and saturation are close to neutral")

    if stats.mean_luma < 92.0:
        if _matches(text, "exposure", "lift", "gamma", "brighten", "shadow", "recovery"):
            add(26.0, "underexposed average luma needs lift/gamma")
        if "BRIGHT_CONTRAST" in modifiers or "COLOR_BALANCE" in modifiers:
            add(5.0, "has native brightness or gamma controls")
    elif stats.mean_luma > 176.0 or stats.luma_p95 > 236.0:
        if _matches(text, "protect", "hdr", "compress", "white point", "recovery", "clamp"):
            add(27.0, "bright or highlight-heavy footage needs roll-off/protection")
        if "TONEMAP" in modifiers or "CURVES" in modifiers:
            add(5.0, "has native tone-map or curve controls")
    else:
        if _matches(text, "neutral", "pro color", "auto enhance", "shadow/highlight", "color board", "asc cdl"):
            add(9.0, "balanced exposure benefits from a complete editorial baseline")

    if dynamic_range < 118.0 or stats.luma_std < 34.0:
        if _matches(text, "contrast", "levels", "curve", "s-curve", "black point", "auto enhance", "primary", "log zone"):
            add(24.0, "low tonal separation needs curve/levels expansion")
        if "CURVES" in modifiers or "BRIGHT_CONTRAST" in modifiers:
            add(4.0, "contains native contrast/curve controls")
    elif dynamic_range > 222.0:
        if _matches(text, "hdr", "tone", "compress", "soft contrast", "white point", "legal", "broadcast-safe"):
            add(18.0, "wide tonal range benefits from compression")

    if stats.mean_saturation < 0.18 or stats.mean_chroma < 28.0:
        if _matches(text, "vibrance", "saturation boost", "punchy", "pro color", "palette", "six-vector", "secondary"):
            add(22.0, "low sampled chroma needs vibrance/saturation")
        if "HUE_CORRECT" in modifiers:
            add(4.0, "has native Hue Correct saturation control")
    elif stats.mean_saturation > 0.62:
        if _matches(text, "saturation reduce", "skin-safe", "legal", "broadcast-safe"):
            add(22.0, "high sampled saturation needs restraint")
        if "HUE_CORRECT" in modifiers:
            add(3.0, "can control saturation with Hue Correct")

    if warm_delta > 0.18:
        if _matches(text, "cool", "temperature cool", "blue gamma", "white balance"):
            add(24.0, "warm cast detected; cool/white-balance correction fits")
        if "WHITE_BALANCE" in modifiers:
            add(5.0, "contains native White Balance")
    elif warm_delta < -0.18:
        if _matches(text, "warm", "temperature warm", "highlight warm", "red gamma", "white balance"):
            add(24.0, "cool cast detected; warm/white-balance correction fits")
        if "WHITE_BALANCE" in modifiers:
            add(5.0, "contains native White Balance")

    if stats.mean_g > stats.mean_r + 4.0 and stats.mean_g > stats.mean_b + 4.0:
        if _matches(text, "green cast", "magenta/green", "green gamma", "white balance"):
            add(18.0, "sampled average RGB suggests a green/magenta tint issue")
    if stats.mean_r > stats.mean_g + 6.0 and stats.mean_r > stats.mean_b + 6.0:
        if _matches(text, "red gamma", "cool", "temperature cool"):
            add(12.0, "sampled average RGB leans red")
    if stats.mean_b > stats.mean_r + 6.0 and stats.mean_b > stats.mean_g + 6.0:
        if _matches(text, "blue gamma", "warm", "temperature warm"):
            add(12.0, "sampled average RGB leans blue")

    if stats.skin_ratio > 0.10:
        if _matches(text, "skin", "skin-safe", "vibrance", "secondary"):
            add(18.0, "skin-tone-like pixels detected; prefer skin-safe tools")
    if stats.shadow_count > stats.highlight_count * 1.35:
        if _matches(text, "shadow", "black point", "lift", "gamma", "log zone"):
            add(10.0, "shadow-heavy sample distribution")
    if stats.highlight_count > stats.shadow_count * 1.35:
        if _matches(text, "highlight", "white point", "protect", "hdr", "broadcast-safe"):
            add(10.0, "highlight-heavy sample distribution")

    if not reasons and tool.id in {"live_pro_color_stack", "auto_enhance", "neutral_grade", "primary_color_board"}:
        add(4.0, "fallback broad Blender-native grade")
    return score, reasons


def _matches(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _catalog_coverage_report() -> str:
    tools = all_tools()
    blender_tools = tuple(tool for tool in tools if tool.is_blender_modifier)
    compositor_tools = tuple(tool for tool in tools if _tool_has_compositor_stack(tool))
    vse_only_tools = tuple(tool for tool in blender_tools if not _tool_has_compositor_stack(tool))
    rendered_tools = tuple(tool for tool in tools if tool.is_ffmpeg)
    modifier_types = sorted({modifier for tool in blender_tools for modifier in _tool_modifier_names(tool)})
    unsupported_modifier_types = sorted(set(modifier_types) - set(COMPOSITOR_MODIFIER_TYPES))
    rendered_filter_names = sorted({name for tool in rendered_tools for name in _ffmpeg_filter_names_for_tool(tool)})
    rendered_only_filter_names = sorted(set(rendered_filter_names) - set(NATIVE_FFMPEG_FILTERS))
    live_and_rendered_filter_names = sorted(set(rendered_filter_names) & set(NATIVE_FFMPEG_FILTERS))
    translation_sample = translate_filter_chain(_ffmpeg_translation_coverage_chain())

    lines = [
        "Open Research Video Toolkit Catalog Coverage",
        "",
        f"Total catalog tools: {len(tools)}",
        f"Blender-native live tools: {len(blender_tools)}",
        f"Compositor-compatible catalog recipes: {len(compositor_tools)}",
        f"VSE-only native tools: {len(vse_only_tools)}",
        f"Rendered fallback tools: {len(rendered_tools)}",
        f"Color Management presets: {len(COLOR_MANAGEMENT_PRESET_ITEMS)}",
        f"Tracked native compositor nodes: {len(compositor_node_tools())}",
        f"Native-translated FFmpeg filters: {len(NATIVE_FFMPEG_FILTERS)}",
        f"Rendered FFmpeg filters in catalog: {len(rendered_filter_names)}",
        "",
        "Supported compositor modifier types: " + ", ".join(sorted(COMPOSITOR_MODIFIER_TYPES)),
        "VSE-only modifier types: " + (", ".join(unsupported_modifier_types) if unsupported_modifier_types else "None"),
        "Native-translated FFmpeg color filters: " + ", ".join(NATIVE_FFMPEG_COLOR_FILTERS),
        "Native compositor-only FFmpeg filters: " + ", ".join(NATIVE_FFMPEG_COMPOSITOR_FILTERS),
        "Native Color Management metadata filters: " + ", ".join(NATIVE_FFMPEG_COLOR_MANAGEMENT_FILTERS),
        "Rendered fallback FFmpeg filters: " + (", ".join(rendered_filter_names) if rendered_filter_names else "None"),
        "Rendered-only FFmpeg filters: " + (", ".join(rendered_only_filter_names) if rendered_only_filter_names else "None"),
        "Live approximation plus rendered fallback filters: "
        + (", ".join(live_and_rendered_filter_names) if live_and_rendered_filter_names else "None"),
        "",
        "Representative FFmpeg color-chain translation:",
        "- Supported filters: " + ", ".join(translation_sample.supported_filters),
        "- Blender modifier stack: " + ", ".join(modifier for modifier, _settings in translation_sample.stack),
        "- Color Management metadata: " + _format_pairs(translation_sample.color_management),
        "- Approximation notes:",
    ]
    lines.extend(f"  - {note}" for note in translation_sample.notes)
    lines.extend([
        "",
        "Compositor-compatible catalog recipes:",
    ])
    lines.extend(_tool_report_lines(compositor_tools))
    lines.extend(["", "VSE-only native tools:"])
    lines.extend(_tool_report_lines(vse_only_tools))
    lines.extend(["", "Rendered fallback tools:"])
    lines.extend(_tool_report_lines(rendered_tools))
    lines.extend(["", "Blender Color Management presets:"])
    for preset_id, label, description in COLOR_MANAGEMENT_PRESET_ITEMS:
        lines.append(f"- {preset_id}: {label} - {description}")
    lines.extend(["", "Tracked native compositor node library:"])
    for node in compositor_node_tools():
        lines.append(f"- {node.node_type}: {node.label} ({node.category})")
    return "\n".join(lines)


def _ffmpeg_filter_names_for_tool(tool) -> tuple[str, ...]:
    names: list[str] = []
    for chain in (getattr(tool, "ffmpeg_filter", None), getattr(tool, "ffmpeg_filter_after_stabilize", None)):
        names.extend(_ffmpeg_filter_names(chain))
    if getattr(tool, "two_pass_stabilize", False):
        names.extend(("vidstabdetect", "vidstabtransform"))
    return tuple(dict.fromkeys(name for name in names if name))


def _ffmpeg_filter_names(chain: str | None) -> list[str]:
    if not chain:
        return []
    names = []
    quote = ""
    token = []
    for char in chain:
        if quote:
            token.append(char)
            if char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
            token.append(char)
            continue
        if char == ",":
            names.append(_ffmpeg_filter_name("".join(token)))
            token = []
            continue
        token.append(char)
    if token:
        names.append(_ffmpeg_filter_name("".join(token)))
    return [name for name in names if name]


def _ffmpeg_filter_name(filter_text: str) -> str:
    head = filter_text.strip().split("=", 1)[0].split(":", 1)[0].strip()
    return head.lower()


def _ffmpeg_translation_coverage_chain() -> str:
    return (
        "colorspace=iall=bt709:all=bt709:irange=tv:range=pc,"
        "colormatrix=src=smpte170m:dst=bt709,"
        "setparams=color_primaries=bt2020:color_trc=bt2020-10:colorspace=bt2020nc:range=full,"
        "setrange=limited,"
        "zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full,"
        "normalize=smoothing=24:independence=0.7:strength=0.55,"
        "eq=contrast=1.12:saturation=1.08:gamma=1.02,"
        "hue=s=1.05,"
        "huesaturation=saturation=0.15:intensity=0.04:strength=0.8,"
        "colorchannelmixer=rr=1.03:gg=1.0:bb=0.97,"
        "curves=preset=medium_contrast,"
        "colorlevels=rimin=0.02:rimax=0.98,"
        "colorbalance=rs=0.05:bm=0.03:bh=-0.04:pl=1,"
        "vibrance=intensity=0.4,"
        "exposure=exposure=0.25:black=0.02,"
        "colortemperature=temperature=5600:mix=0.55,"
        "limiter=min=16:max=235,"
        "tonemap=tonemap=mobius:param=0.35:desat=0.4,"
        "colorcorrect=rl=0.05:bl=-0.03:rh=0.02:bh=-0.02:saturation=1.05,"
        "colorcontrast=rc=0.12:gm=-0.04:by=0.08:rcw=0.5:gmw=0.35:byw=0.45:pl=1,"
        "selectivecolor=reds=0.08 -0.03 -0.02 0.00:blues=-0.03 0.01 0.08 0.02:whites=0.01 0.00 -0.06 0.01,"
        "monochrome=cb=0.05:cr=-0.04:high=0.1,"
        "colorize=hue=35:saturation=0.25:lightness=0.55:mix=0.85,"
        "grayworld,"
        "greyedge=difford=2:minknorm=5:sigma=2,"
        "lut1d=file=warm_print.spi1d:interp=cubic,"
        "lut3d=file=teal_orange.cube:interp=tetrahedral,"
        "haldclut=interp=tetrahedral:clut=all,"
        "colormap=patch_size=64x64:nb_patches=32:type=absolute:kernel=weuclidean,"
        "negate=components=r+g+b,"
        "colorhold=color=blue:similarity=0.12:blend=0.2,"
        "hsvhold=hue=210:similarity=0.10,"
        "chromakey=color=green:similarity=0.12:blend=0.04,"
        "colorkey=color=blue:similarity=0.10:blend=0.03,"
        "hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.10:blend=0.02,"
        "lumakey=threshold=0.20:tolerance=0.08:softness=0.02,"
        "despill=type=green:mix=0.65:expand=0.12:green=-1.0,"
        "backgroundkey=threshold=0.08:similarity=0.12:blend=0.04,"
        "threshold=planes=7,"
        "maskedthreshold=threshold=2048:planes=7:mode=abs,"
        "blend=all_mode=overlay:all_opacity=0.35,"
        "tblend=all_mode=average:all_opacity=0.45,"
        "lut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
        "tlut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
        "maskedmerge=planes=15,"
        "mergeplanes=map0p=2:map1p=1:map2p=0:map3p=3,"
        "rgbashift=rh=4:rv=-2:bh=-3:bv=2,"
        "chromashift=cbh=2:cbv=-1:crh=-2:crv=1,"
        "chromaber_vulkan=dist_x=2.0:dist_y=-1.0,"
        "alphaextract,"
        "alphamerge,"
        "extractplanes=planes=y,"
        "premultiply,"
        "unpremultiply,"
        "shuffleplanes=map0=2:map1=1:map2=0:map3=3,"
        "elbg=l=64:n=2:seed=17,"
        "unsharp=5:5:0.45:3:3:0.20,"
        "sobel=scale=1.2:delta=0.02,"
        "prewitt=scale=0.9:delta=0.01,"
        "kirsch=scale=0.8,"
        "edgedetect=high=0.20:low=0.08:mode=wires,"
        "erosion=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000,"
        "dilation=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000,"
        "convolution=0m=\"0 -1 0 -1 5 -1 0 -1 0\":0rdiv=1:0bias=0,"
        "avgblur=sizeX=4:sizeY=6,"
        "boxblur=lr=3:lp=2,"
        "gblur=sigma=1.2:steps=2:sigmaV=0.8,"
        "smartblur=lr=2:ls=0.8:lt=8,"
        "sab=lr=2:lpfr=1:ls=12,"
        "yaepblur=r=4:s=192,"
        "dblur=angle=30:radius=12,"
        "scale=960:540,"
        "crop=w=1280:h=720:x=320:y=180,"
        "rotate=angle=PI/6,"
        "transpose=clock,"
        "hflip,"
        "vflip,"
        "lenscorrection=k1=-0.12:k2=0.04:cx=0.45:cy=0.55,"
        "hqdn3d=1.5:1.5:6:6,"
        "nlmeans=s=2.5:p=7:r=9,"
        "bm3d=sigma=3:group=8:range=12,"
        "owdenoise=ls=2:cs=1.5,"
        "vaguedenoiser=threshold=2.5:percent=80,"
        "atadenoise=s=9,"
        "median=radius=3:radiusV=5:percentile=0.55,"
        "dedot=lt=0.08:tl=0.09:tc=0.06:ct=0.02,"
        "deband=1thr=0.03:2thr=0.025:3thr=0.02:range=20,"
        "deblock=block=16:alpha=0.12:beta=0.08,"
        "deflicker=s=12:m=median,"
        "bwdif=mode=send_frame:parity=auto:deint=all,"
        "yadif=mode=send_frame:parity=auto:deint=all,"
        "deshake=rx=16:ry=16,"
        "vidstabdetect=shakiness=5:accuracy=15:result=motion.trf,"
        "vidstabtransform=input=motion.trf:smoothing=30:zoom=2,"
        "tmix=frames=3:weights='1 2 1',"
        "fps=fps=30:round=near,"
        "framerate=fps=60,"
        "minterpolate=fps=60:mi_mode=mci,"
        "blackdetect=d=1.0:pic_th=0.96:pix_th=0.08,"
        "blackdetect_vulkan=d=1.0:pic_th=0.96:pix_th=0.08,"
        "blackframe=amount=96:threshold=28,"
        "blockdetect=period_min=3:period_max=24:planes=1,"
        "blurdetect=high=0.12:low=0.06:radius=40:block_pct=80:planes=1,"
        "cropdetect=limit=0.094:round=16:reset=30:skip=2,"
        "bbox=min_val=16,"
        "bitplanenoise=bitplane=1:filter=1,"
        "freezedetect=n=0.001:d=2,"
        "scdet=threshold=10:sc_pass=0,"
        "scdet_vulkan=threshold=10:sc_pass=0,"
        "vfrdet,"
        "idet=intl_thres=1.04:prog_thres=1.5:rep_thres=3,"
        "identity=eof_action=repeat:repeatlast=1:ts_sync_mode=nearest,"
        "ssim=stats_file=vtk_ssim.log:eof_action=repeat:repeatlast=1:ts_sync_mode=nearest,"
        "psnr=stats_file=vtk_psnr.log:stats_version=2:output_max=1:eof_action=repeat,"
        "xpsnr=stats_file=vtk_xpsnr.log:eof_action=repeat,"
        "corr=eof_action=repeat:repeatlast=1,"
        "msad=eof_action=repeat:repeatlast=1,"
        "xcorrelate=planes=7:secondary=all:eof_action=repeat,"
        "pseudocolor=preset=viridis:opacity=0.75:index=1,"
        "lutrgb=r=negval:g=val*0.9:b=val+12,"
        "histeq=strength=0.22:intensity=0.20:antibanding=1"
    )


def _format_pairs(pairs: tuple[tuple[str, str], ...]) -> str:
    if not pairs:
        return "None"
    return ", ".join(f"{key}={value}" for key, value in pairs)


def _tool_report_lines(tools) -> list[str]:
    if not tools:
        return ["- None"]
    lines = []
    for tool in tools:
        modifiers = _tool_modifier_names(tool)
        suffix = f" -> {', '.join(modifiers)}" if modifiers else ""
        lines.append(f"- {tool.id}: {tool.label} [{tool.category}]{suffix}")
    return lines


def _reference_movie_strip(context, active):
    selected = _selected_movie_strips(context)
    for strip in selected:
        if strip != active:
            return strip
    return None


def _selected_movie_strips(context) -> list:
    selected = []
    for strip in getattr(context, "selected_sequences", []) or []:
        if strip.type == "MOVIE":
            selected.append(strip)
    if selected:
        return selected
    editor = context.scene.sequence_editor
    return [strip for strip in editor.strips_all if strip.type == "MOVIE" and getattr(strip, "select", False)]


def _selected_modifier_strips(context) -> list:
    selected = []
    for strip in getattr(context, "selected_sequences", []) or []:
        if hasattr(strip, "modifiers"):
            selected.append(strip)
    if selected:
        return selected
    editor = context.scene.sequence_editor
    return [strip for strip in editor.strips_all if hasattr(strip, "modifiers") and getattr(strip, "select", False)]


def _create_adjustment_strip(context, label: str):
    scene = context.scene
    if scene.sequence_editor is None:
        scene.sequence_editor_create()
    editor = scene.sequence_editor
    active = editor.active_strip
    selected = _selected_modifier_strips(context) or ([active] if active else [])
    if not selected:
        raise RuntimeError("Select a strip or range before creating an adjustment layer")
    start = min(strip.frame_final_start for strip in selected)
    end = max(strip.frame_final_end for strip in selected)
    length = max(1, end - start)
    minimum_channel = max(strip.channel for strip in selected) + 1
    channel = _find_free_channel(editor, start, end, minimum_channel)
    adjustment = editor.strips.new_effect(
        name=f"VTK {label} Adjustment",
        type="ADJUSTMENT",
        channel=channel,
        frame_start=start,
        length=length,
    )
    for strip in editor.strips_all:
        strip.select = False
    adjustment.select = True
    editor.active_strip = adjustment
    return adjustment


def _output_dir(scene) -> Path:
    configured = scene.video_toolkit_output_dir or "//video_toolkit_outputs"
    return Path(bpy.path.abspath(configured)).expanduser()


def _unique_output_path(output_dir: Path, source_path: Path, tool_id: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"{source_path.stem}__{tool_id}"
    candidate = output_dir / f"{base}.mp4"
    index = 2
    while candidate.exists():
        candidate = output_dir / f"{base}_{index}.mp4"
        index += 1
    return candidate


def _add_rendered_strip(scene, source_strip, output_path: Path, label: str) -> None:
    if scene.sequence_editor is None:
        scene.sequence_editor_create()
    editor = scene.sequence_editor
    channel = _find_free_channel(editor, source_strip.frame_final_start, source_strip.frame_final_end, source_strip.channel + 1)
    new_strip = editor.strips.new_movie(
        name=f"{label} - {source_strip.name}",
        filepath=str(output_path),
        channel=channel,
        frame_start=source_strip.frame_final_start,
    )
    new_strip.frame_final_duration = source_strip.frame_final_duration
    editor.active_strip = new_strip


def _find_free_channel(editor, start: int, end: int, minimum: int) -> int:
    channel = max(1, minimum)
    strips = list(editor.strips_all)
    while any(_overlaps(strip, start, end) and strip.channel == channel for strip in strips):
        channel += 1
    return channel


def _overlaps(strip, start: int, end: int) -> bool:
    return strip.frame_final_start < end and start < strip.frame_final_end


CLASSES = (
    VIDEO_TOOLKIT_OT_apply_filter,
    VIDEO_TOOLKIT_OT_apply_sidecar_tool,
    VIDEO_TOOLKIT_OT_set_sidecar_section,
    VIDEO_TOOLKIT_OT_analyze_color,
    VIDEO_TOOLKIT_OT_color_diagnostics,
    VIDEO_TOOLKIT_OT_recommend_catalog_recipes,
    VIDEO_TOOLKIT_OT_apply_recommended_recipe_mix,
    VIDEO_TOOLKIT_OT_apply_diagnostic_grade,
    VIDEO_TOOLKIT_OT_apply_sampled_white_balance,
    VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma,
    VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma,
    VIDEO_TOOLKIT_OT_apply_sampled_pro_grade,
    VIDEO_TOOLKIT_OT_apply_sampled_color_board,
    VIDEO_TOOLKIT_OT_apply_reference_color_board,
    VIDEO_TOOLKIT_OT_normalize_lighting,
    VIDEO_TOOLKIT_OT_match_lighting_timeline,
    VIDEO_TOOLKIT_OT_match_color_timeline,
    VIDEO_TOOLKIT_OT_translate_ffmpeg_chain,
    VIDEO_TOOLKIT_OT_apply_translated_color_workflow,
    VIDEO_TOOLKIT_OT_clear_live_modifiers,
    VIDEO_TOOLKIT_OT_create_compositor_nodes,
    VIDEO_TOOLKIT_OT_create_tool_compositor_nodes,
    VIDEO_TOOLKIT_OT_create_sidecar_compositor_nodes,
    VIDEO_TOOLKIT_OT_create_all_tool_compositor_nodes,
    VIDEO_TOOLKIT_OT_create_recommended_recipe_mix_nodes,
    VIDEO_TOOLKIT_OT_apply_professional_color_workflow,
    VIDEO_TOOLKIT_OT_write_catalog_coverage_report,
    VIDEO_TOOLKIT_OT_apply_color_management_preset,
    VIDEO_TOOLKIT_OT_apply_sampled_color_management,
    VIDEO_TOOLKIT_OT_open_output_folder,
    VIDEO_TOOLKIT_MT_live_blender_color,
    VIDEO_TOOLKIT_MT_native_blender_primitives,
    VIDEO_TOOLKIT_MT_restoration,
    VIDEO_TOOLKIT_MT_resolution_motion,
    VIDEO_TOOLKIT_MT_blender_vse_modifiers,
    VIDEO_TOOLKIT_MT_compositor_recipes,
    VIDEO_TOOLKIT_MT_color_management,
    VIDEO_TOOLKIT_MT_tools,
    VIDEO_TOOLKIT_PT_video_filters,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.video_toolkit_output_dir = bpy.props.StringProperty(
        name="Output Folder",
        description="Where rendered Video Toolkit results are written",
        subtype="DIR_PATH",
        default="//video_toolkit_outputs",
    )
    bpy.types.Scene.video_toolkit_crf = bpy.props.IntProperty(
        name="CRF",
        description="x264 quality. Lower is larger and higher quality",
        min=0,
        max=51,
        default=18,
    )
    bpy.types.Scene.video_toolkit_preset = bpy.props.EnumProperty(
        name="Preset",
        items=PRESET_ITEMS,
        default="medium",
    )
    bpy.types.Scene.video_toolkit_keep_audio = bpy.props.BoolProperty(
        name="Keep Audio",
        description="Copy source audio into rendered output when present",
        default=True,
    )
    bpy.types.Scene.video_toolkit_add_strip = bpy.props.BoolProperty(
        name="Add Rendered Strip",
        description="Add the processed output above the source strip",
        default=True,
    )
    bpy.types.Scene.video_toolkit_sidecar_section = bpy.props.EnumProperty(
        name="Section",
        description="Mini tab shown inside the Video Effects sidebar",
        items=SIDECAR_SECTION_ITEMS,
        default="BROWSER",
    )
    bpy.types.Scene.video_toolkit_sidecar_group = bpy.props.EnumProperty(
        name="Group",
        description="Video effect group shown in the Video Sequencer sidebar",
        items=SIDECAR_GROUP_ITEMS,
        default=SIDECAR_GROUP_ITEMS[0][0] if SIDECAR_GROUP_ITEMS else "",
        update=_sync_sidecar_tool_to_group,
    )
    bpy.types.Scene.video_toolkit_sidecar_tool = bpy.props.EnumProperty(
        name="Tool",
        description="Video effect to apply from the Video Effects sidebar",
        items=_sidecar_tool_items,
    )
    bpy.types.Scene.video_toolkit_last_output = bpy.props.StringProperty(
        name="Last Output",
        subtype="FILE_PATH",
        default="",
    )
    bpy.types.Scene.video_toolkit_analysis_samples = bpy.props.IntProperty(
        name="Frames",
        description="Maximum number of frames sampled for live color analysis",
        min=1,
        max=5000,
        default=240,
    )
    bpy.types.Scene.video_toolkit_last_analysis = bpy.props.StringProperty(
        name="Last Analysis",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_diagnostics = bpy.props.StringProperty(
        name="Last Color Diagnostics",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_diagnostics_text = bpy.props.StringProperty(
        name="Last Color Diagnostics Text",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_catalog_report = bpy.props.StringProperty(
        name="Last Catalog Coverage Report",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_recipe_recommendations = bpy.props.StringProperty(
        name="Last Recipe Recommendations",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_recommended_recipe_mix = bpy.props.StringProperty(
        name="Last Recommended Recipe Mix",
        default="",
    )
    bpy.types.Scene.video_toolkit_recommendation_mix_count = bpy.props.IntProperty(
        name="Recipe Mix Count",
        description="How many top-ranked Blender-native recipes are combined by Apply Recommended Recipe Mix",
        min=1,
        max=8,
        default=4,
    )
    bpy.types.Scene.video_toolkit_last_diagnostic_grade = bpy.props.StringProperty(
        name="Last Diagnostic Grade",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_sampled_white_balance = bpy.props.StringProperty(
        name="Last Sampled White Balance",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_sampled_levels_gamma = bpy.props.StringProperty(
        name="Last Sampled Levels Gamma",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_sampled_hue_chroma = bpy.props.StringProperty(
        name="Last Sampled Hue Chroma",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_sampled_pro_grade = bpy.props.StringProperty(
        name="Last Sampled Pro Grade",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_sampled_color_board = bpy.props.StringProperty(
        name="Last Sampled Color Board",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_reference_color_board = bpy.props.StringProperty(
        name="Last Reference Color Board",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_sampled_color_management = bpy.props.StringProperty(
        name="Last Sampled Color Management",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_professional_workflow = bpy.props.StringProperty(
        name="Last Professional Color Workflow",
        default="",
    )
    bpy.types.Scene.video_toolkit_apply_target = bpy.props.EnumProperty(
        name="Target",
        description="Where live Blender color tools are applied",
        items=APPLY_TARGET_ITEMS,
        default="ACTIVE",
    )
    bpy.types.Scene.video_toolkit_ffmpeg_chain = bpy.props.StringProperty(
        name="FFmpeg Color Chain",
        description="Supported FFmpeg-style color filters are converted into native live Blender VSE modifiers",
        default="eq=contrast=1.08:saturation=1.05:gamma=1.02",
    )
    bpy.types.Scene.video_toolkit_last_translation = bpy.props.StringProperty(
        name="Last Color Translation",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_translated_workflow = bpy.props.StringProperty(
        name="Last Translated Color Workflow",
        default="",
    )
    bpy.types.Scene.video_toolkit_last_color_management = bpy.props.StringProperty(
        name="Last Color Management Preset",
        default="",
    )
    bpy.types.Scene.video_toolkit_flicker_smoothing = bpy.props.IntProperty(
        name="Flicker Smoothing",
        description="Odd-sized sample window used by the live lighting normalizer",
        min=1,
        max=99,
        default=9,
    )
    bpy.types.Scene.video_toolkit_flicker_strength = bpy.props.FloatProperty(
        name="Flicker Strength",
        description="How strongly keyframed Blender brightness follows the smoothed luma target",
        min=0.0,
        max=1.5,
        default=0.80,
    )
    bpy.types.Scene.video_toolkit_match_smoothing = bpy.props.IntProperty(
        name="Timeline Match Smoothing",
        description="Odd-sized sample window used when matching active lighting to a reference strip",
        min=1,
        max=99,
        default=5,
    )
    bpy.types.Scene.video_toolkit_match_strength = bpy.props.FloatProperty(
        name="Timeline Match Strength",
        description="How strongly keyframed Blender brightness follows the selected reference strip",
        min=0.0,
        max=1.5,
        default=0.85,
    )
    bpy.types.Scene.video_toolkit_color_match_smoothing = bpy.props.IntProperty(
        name="Color Timeline Smoothing",
        description="Odd-sized sample window used when matching active RGB timeline to a reference strip",
        min=1,
        max=99,
        default=5,
    )
    bpy.types.Scene.video_toolkit_color_match_strength = bpy.props.FloatProperty(
        name="Color Timeline Strength",
        description="How strongly keyframed Blender Color Balance follows the selected reference strip",
        min=0.0,
        max=1.5,
        default=0.75,
    )
    bpy.types.Scene.video_toolkit_last_compositor_nodes = bpy.props.StringProperty(
        name="Last Compositor Nodes",
        default="",
    )
    _append_menu("SEQUENCER_HT_header", _draw_video_toolkit_header)
    _append_menu("SEQUENCER_MT_editor_menus", _draw_video_toolkit_menu)
    _append_menu("SEQUENCER_MT_context_menu", _draw_video_toolkit_menu)
    _append_menu("SEQUENCER_MT_strip", _draw_video_toolkit_menu)


def unregister() -> None:
    _remove_menu("SEQUENCER_MT_strip", _draw_video_toolkit_menu)
    _remove_menu("SEQUENCER_MT_context_menu", _draw_video_toolkit_menu)
    _remove_menu("SEQUENCER_MT_editor_menus", _draw_video_toolkit_menu)
    _remove_menu("SEQUENCER_HT_header", _draw_video_toolkit_header)
    for attr in (
        "video_toolkit_output_dir",
        "video_toolkit_crf",
        "video_toolkit_preset",
        "video_toolkit_keep_audio",
        "video_toolkit_add_strip",
        "video_toolkit_sidecar_section",
        "video_toolkit_sidecar_group",
        "video_toolkit_sidecar_tool",
        "video_toolkit_last_output",
        "video_toolkit_analysis_samples",
        "video_toolkit_last_analysis",
        "video_toolkit_last_diagnostics",
        "video_toolkit_last_diagnostics_text",
        "video_toolkit_last_catalog_report",
        "video_toolkit_last_recipe_recommendations",
        "video_toolkit_last_recommended_recipe_mix",
        "video_toolkit_recommendation_mix_count",
        "video_toolkit_last_diagnostic_grade",
        "video_toolkit_last_sampled_white_balance",
        "video_toolkit_last_sampled_levels_gamma",
        "video_toolkit_last_sampled_hue_chroma",
        "video_toolkit_last_sampled_pro_grade",
        "video_toolkit_last_sampled_color_board",
        "video_toolkit_last_reference_color_board",
        "video_toolkit_last_sampled_color_management",
        "video_toolkit_last_professional_workflow",
        "video_toolkit_apply_target",
        "video_toolkit_ffmpeg_chain",
        "video_toolkit_last_translation",
        "video_toolkit_last_translated_workflow",
        "video_toolkit_last_color_management",
        "video_toolkit_flicker_smoothing",
        "video_toolkit_flicker_strength",
        "video_toolkit_match_smoothing",
        "video_toolkit_match_strength",
        "video_toolkit_color_match_smoothing",
        "video_toolkit_color_match_strength",
        "video_toolkit_last_compositor_nodes",
    ):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
