"""Blender UI and operators for Open Research Video Toolkit."""

import traceback
from pathlib import Path

import bpy
from bpy.types import Menu, Operator, Panel

from .catalog import categories, enum_items, get_tool, all_tools
from .color_analysis import (
    build_auto_balance_stack,
    build_color_match_stack,
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
        _draw_operator(layout, "live_pro_color_stack", icon="MODIFIER")
        layout.separator()
        layout.menu("VIDEO_TOOLKIT_MT_live_blender_color", icon="COLOR")
        layout.menu("VIDEO_TOOLKIT_MT_native_blender_primitives", icon="NODETREE")
        layout.menu("VIDEO_TOOLKIT_MT_blender_vse_modifiers", icon="SEQ_STRIP_DUPLICATE")
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
    box.prop(scene, "video_toolkit_analysis_samples")
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
    VIDEO_TOOLKIT_OT_clear_live_modifiers,
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
    ):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
