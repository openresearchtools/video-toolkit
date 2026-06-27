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
    build_lighting_match_keyframes,
    build_lighting_normalization_keyframes,
    sample_video_luma_timeline,
    sample_video_color,
    summarize_stats,
)
from .ffmpeg_backend import FFmpegError, process_video


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
    ("RESTORATION", "Restoration Node Stack", "Build a Blender compositor restoration node graph from the active movie strip"),
)


def _tool_items(_self, _context):
    return enum_items()


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
                return {"FINISHED"}
            output_path = _render_ffmpeg_tool(context, strip, tool)
            self.report({"INFO"}, f"Rendered {tool.label}: {output_path}")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


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
            if self.stack_type == "RESTORATION":
                created = _create_compositor_restoration_stack(context.scene, strip)
                label = "restoration"
            else:
                created = _create_compositor_color_stack(context.scene, strip)
                label = "color"
            context.scene.video_toolkit_last_compositor_nodes = ", ".join(node.label or node.bl_idname for node in created)
            self.report({"INFO"}, f"Created {len(created)} Blender compositor {label} node(s)")
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
    bl_label = "Tools"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Video Filters", icon="SEQ_SEQUENCER")
        op = layout.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Analyze: Live Auto Balance", icon="COLOR")
        op.mode = "AUTO"
        op = layout.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Analyze: Match Selected", icon="EYEDROPPER")
        op.mode = "MATCH"
        op = layout.operator(VIDEO_TOOLKIT_OT_analyze_color.bl_idname, text="Analyze: Identify Colors", icon="COLOR")
        op.mode = "PALETTE"
        layout.operator(VIDEO_TOOLKIT_OT_normalize_lighting.bl_idname, text="Analyze: Normalize Flicker", icon="IPO_EASE_IN_OUT")
        layout.operator(VIDEO_TOOLKIT_OT_match_lighting_timeline.bl_idname, text="Analyze: Match Lighting Timeline", icon="GRAPH")
        _draw_operator(layout, "live_pro_color_stack", icon="MODIFIER")
        layout.separator()
        layout.menu("VIDEO_TOOLKIT_MT_live_blender_color", icon="COLOR")
        layout.menu("VIDEO_TOOLKIT_MT_native_blender_primitives", icon="NODETREE")
        layout.menu("VIDEO_TOOLKIT_MT_blender_vse_modifiers", icon="SEQ_STRIP_DUPLICATE")
        op = layout.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Create Color Node Stack", icon="NODETREE")
        op.stack_type = "COLOR"
        op = layout.operator(
            VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname,
            text="Create Restoration Node Stack",
            icon="NODETREE",
        )
        op.stack_type = "RESTORATION"
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


class VIDEO_TOOLKIT_PT_video_filters(Panel):
    bl_idname = "VIDEO_TOOLKIT_PT_video_filters"
    bl_label = "Video Filters"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Video Filters"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        strip = scene.sequence_editor.active_strip if scene.sequence_editor else None

        if not strip:
            layout.label(text="Select a strip to enable one-click filters.", icon="INFO")
            return

        layout.label(text=f"Active: {strip.name}", icon="SEQ_STRIP_META")
        _draw_live_analysis(layout, scene, strip, context)
        _draw_scene_color_management(layout, scene)
        _draw_compositor_nodes(layout, scene, strip)
        _draw_live_color_tools(layout, scene)
        _draw_strip_editing_tools(layout, strip)
        _draw_live_modifier_editor(layout, strip)
        _draw_render_tools(layout, scene)


def _draw_category(layout, category: str) -> None:
    for tool in all_tools():
        if tool.category == category:
            _draw_operator(layout, tool.id)


def _draw_operator(layout, tool_id: str, icon: str = "NONE") -> None:
    tool = get_tool(tool_id)
    op = layout.operator(VIDEO_TOOLKIT_OT_apply_filter.bl_idname, text=tool.label, icon=icon)
    op.filter_id = tool.id


def _draw_header_menu(self, _context) -> None:
    self.layout.menu(VIDEO_TOOLKIT_MT_tools.bl_idname, text="Tools", icon="TOOL_SETTINGS")


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
    box.operator(VIDEO_TOOLKIT_OT_normalize_lighting.bl_idname, text="Normalize Lighting Flicker", icon="IPO_EASE_IN_OUT")
    box.operator(VIDEO_TOOLKIT_OT_match_lighting_timeline.bl_idname, text="Match Lighting Timeline", icon="GRAPH")
    box.prop(scene, "video_toolkit_analysis_samples")
    row = box.row(align=True)
    row.prop(scene, "video_toolkit_flicker_smoothing", text="Smooth")
    row.prop(scene, "video_toolkit_flicker_strength", text="Strength")
    row = box.row(align=True)
    row.prop(scene, "video_toolkit_match_smoothing", text="Match Smooth")
    row.prop(scene, "video_toolkit_match_strength", text="Match Strength")
    if scene.video_toolkit_last_analysis:
        box.label(text=scene.video_toolkit_last_analysis, icon="INFO")


def _draw_scene_color_management(layout, scene) -> None:
    box = layout.box()
    box.label(text="Blender Color Management", icon="WORLD")
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


def _draw_compositor_nodes(layout, scene, strip) -> None:
    if strip.type != "MOVIE":
        return
    box = layout.box()
    box.label(text="Native Compositor Nodes", icon="NODE_COMPOSITING")
    row = box.row(align=True)
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Color Stack", icon="COLOR")
    op.stack_type = "COLOR"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Restore Stack", icon="MODIFIER")
    op.stack_type = "RESTORATION"
    if scene.video_toolkit_last_compositor_nodes:
        box.label(text=scene.video_toolkit_last_compositor_nodes, icon="INFO")


def _draw_live_color_tools(layout, scene) -> None:
    box = layout.box()
    box.label(text="Live Blender Color Tools", icon="COLOR")
    box.prop(scene, "video_toolkit_apply_target", text="Target")
    for category in ("Live Blender Color", "Native Blender Primitives", "Live Blender Modifiers"):
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
        _draw_modifier_controls(mod_box, modifier)


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
        for prop in ("input_mask_type", "input_mask_strip", "input_mask_id", "mask_time"):
            if hasattr(modifier, prop):
                layout.prop(modifier, prop)
    else:
        for prop in ("enable", "show_preview", "input_mask_type"):
            if hasattr(modifier, prop):
                layout.prop(modifier, prop)


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


def _add_blender_tool(strip, tool):
    if tool.blender_stack:
        return _add_blender_stack(strip, tool.blender_stack, tool.label)
    return [_add_blender_modifier(strip, tool.blender_modifier, tool.blender_settings, tool.label)]


def _add_blender_stack(strip, stack, label: str):
    modifiers = []
    for modifier_type, settings in stack:
        modifiers.append(_add_blender_modifier(strip, modifier_type, settings, label))
    return modifiers


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
    clip = bpy.data.movieclips.load(str(path), check_existing=True)
    node.clip = clip
    return clip


def _assign_node_clip(node, clip) -> None:
    if hasattr(node, "clip"):
        node.clip = clip


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


def _first_socket(sockets):
    return next(iter(sockets), None)


def _set_input_default(node, socket_name: str, value) -> None:
    socket = _socket_by_name(node.inputs, socket_name)
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


def _modifier_label(modifier_type: str) -> str:
    return modifier_type.replace("_", " ").title()


def _set_nested_attr(target, dotted_path: str, value) -> None:
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
    VIDEO_TOOLKIT_OT_analyze_color,
    VIDEO_TOOLKIT_OT_normalize_lighting,
    VIDEO_TOOLKIT_OT_match_lighting_timeline,
    VIDEO_TOOLKIT_OT_clear_live_modifiers,
    VIDEO_TOOLKIT_OT_create_compositor_nodes,
    VIDEO_TOOLKIT_OT_open_output_folder,
    VIDEO_TOOLKIT_MT_live_blender_color,
    VIDEO_TOOLKIT_MT_native_blender_primitives,
    VIDEO_TOOLKIT_MT_restoration,
    VIDEO_TOOLKIT_MT_resolution_motion,
    VIDEO_TOOLKIT_MT_blender_vse_modifiers,
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
    bpy.types.Scene.video_toolkit_apply_target = bpy.props.EnumProperty(
        name="Target",
        description="Where live Blender color tools are applied",
        items=APPLY_TARGET_ITEMS,
        default="ACTIVE",
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
    bpy.types.Scene.video_toolkit_last_compositor_nodes = bpy.props.StringProperty(
        name="Last Compositor Nodes",
        default="",
    )
    bpy.types.SEQUENCER_MT_editor_menus.append(_draw_header_menu)


def unregister() -> None:
    try:
        bpy.types.SEQUENCER_MT_editor_menus.remove(_draw_header_menu)
    except Exception:
        pass
    for attr in (
        "video_toolkit_output_dir",
        "video_toolkit_crf",
        "video_toolkit_preset",
        "video_toolkit_keep_audio",
        "video_toolkit_add_strip",
        "video_toolkit_last_output",
        "video_toolkit_analysis_samples",
        "video_toolkit_last_analysis",
        "video_toolkit_apply_target",
        "video_toolkit_flicker_smoothing",
        "video_toolkit_flicker_strength",
        "video_toolkit_match_smoothing",
        "video_toolkit_match_strength",
        "video_toolkit_last_compositor_nodes",
    ):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
