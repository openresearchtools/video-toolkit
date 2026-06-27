"""Blender UI and operators for Open Research Video Toolkit."""

import traceback
from pathlib import Path

import bpy
from bpy.types import Menu, Operator, Panel

from .catalog import categories, enum_items, get_tool, all_tools
from .ffmpeg_backend import FFmpegError, process_video


PRESET_ITEMS = (
    ("ultrafast", "Ultrafast", "Fastest encode, largest file"),
    ("veryfast", "Very Fast", "Fast preview encode"),
    ("medium", "Medium", "Balanced encode"),
    ("slow", "Slow", "Slower encode, smaller file"),
)


def _tool_items(_self, _context):
    return enum_items()


class VIDEO_TOOLKIT_OT_apply_filter(Operator):
    bl_idname = "video_toolkit.apply_filter"
    bl_label = "Apply Video Filter"
    bl_description = "Apply a one-click video enhancement or restoration tool"
    bl_options = {"REGISTER", "UNDO"}

    filter_id: bpy.props.EnumProperty(name="Filter", items=_tool_items)

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
                modifier = _add_blender_modifier(strip, tool)
                self.report({"INFO"}, f"Added {modifier.name} to {strip.name}")
                return {"FINISHED"}
            output_path = _render_ffmpeg_tool(context, strip, tool)
            self.report({"INFO"}, f"Rendered {tool.label}: {output_path}")
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
        _draw_operator(layout, "auto_enhance", icon="COLOR")
        _draw_operator(layout, "deflicker_normalize", icon="LIGHT")
        _draw_operator(layout, "stabilize", icon="TRACKING")
        layout.separator()
        layout.menu("VIDEO_TOOLKIT_MT_enhance", icon="COLOR")
        layout.menu("VIDEO_TOOLKIT_MT_color_tone", icon="SHADING_TEXTURE")
        layout.menu("VIDEO_TOOLKIT_MT_restoration", icon="MODIFIER")
        layout.menu("VIDEO_TOOLKIT_MT_resolution_motion", icon="RENDER_ANIMATION")
        layout.menu("VIDEO_TOOLKIT_MT_blender_vse_modifiers", icon="SEQ_STRIP_DUPLICATE")
        layout.separator()
        layout.operator(VIDEO_TOOLKIT_OT_open_output_folder.bl_idname, icon="FILE_FOLDER")


class VIDEO_TOOLKIT_MT_enhance(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_enhance"
    bl_label = "Enhance"

    def draw(self, _context):
        _draw_category(self.layout, "Enhance")


class VIDEO_TOOLKIT_MT_color_tone(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_color_tone"
    bl_label = "Color & Tone"

    def draw(self, _context):
        _draw_category(self.layout, "Color & Tone")


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
    bl_label = "Blender VSE Modifiers"

    def draw(self, _context):
        _draw_category(self.layout, "Blender VSE Modifiers")


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

        row = layout.row(align=True)
        row.prop(scene, "video_toolkit_output_dir", text="")
        row.operator(VIDEO_TOOLKIT_OT_open_output_folder.bl_idname, text="", icon="FILE_FOLDER")

        settings = layout.box()
        row = settings.row(align=True)
        row.prop(scene, "video_toolkit_crf")
        row.prop(scene, "video_toolkit_preset", text="")
        settings.prop(scene, "video_toolkit_keep_audio")
        settings.prop(scene, "video_toolkit_add_strip")

        if not strip:
            layout.label(text="Select a strip to enable one-click filters.", icon="INFO")
            return

        layout.label(text=f"Active: {strip.name}", icon="SEQ_STRIP_META")
        for category in categories():
            box = layout.box()
            box.label(text=category)
            col = box.column(align=True)
            for tool in all_tools():
                if tool.category == category:
                    _draw_operator(col, tool.id)


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


def _add_blender_modifier(strip, tool):
    if not hasattr(strip, "modifiers"):
        raise RuntimeError(f"{strip.name} does not support VSE modifiers")
    modifier = strip.modifiers.new(name=tool.label, type=tool.blender_modifier)
    for path, value in tool.blender_settings.items():
        _set_nested_attr(modifier, path, value)
    return modifier


def _set_nested_attr(target, dotted_path: str, value) -> None:
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
    VIDEO_TOOLKIT_OT_open_output_folder,
    VIDEO_TOOLKIT_MT_enhance,
    VIDEO_TOOLKIT_MT_color_tone,
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
    ):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
