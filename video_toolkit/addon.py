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
    build_sampled_color_management,
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
from .ffmpeg_native import translate_filter_chain


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
    ("SAMPLED_COLOR", "Sampled Color Node Stack", "Sample real frames and build a Blender compositor color graph from the measured footage"),
    ("IDENTITY_COLOR", "Palette Identity Node Stack", "Identify dominant colors and build a Blender compositor palette-aware graph"),
    ("MATCHED_COLOR", "Matched Color Node Stack", "Match the active movie strip to a selected reference strip with Blender compositor nodes"),
    ("COLOR_TIMELINE_MATCH", "Color Timeline Match Node Stack", "Sample active/reference RGB over time and animate Blender compositor color balance"),
    ("DIAGNOSTIC_COLOR", "Diagnostic Grade Node Stack", "Diagnose real frames and build the recommended Blender compositor color graph"),
    ("TRANSLATED_COLOR", "Translated Color Node Stack", "Translate the FFmpeg-style color chain into a Blender compositor graph"),
    ("LIGHTING_NORMALIZE", "Lighting Normalize Node Stack", "Sample luma over time and animate Blender compositor brightness correction"),
    ("RESTORATION", "Restoration Node Stack", "Build a Blender compositor restoration node graph from the active movie strip"),
    ("NODE_LIBRARY", "Native Node Library", "Create every tracked Blender compositor video-finishing node in organized groups"),
)

COLOR_MANAGEMENT_PRESET_ITEMS = (
    ("AGX_BALANCED", "AgX Balanced", "AgX view transform with a moderate editorial contrast look"),
    ("AGX_PUNCH", "AgX Punch", "AgX with a stronger contrast look and tiny exposure lift"),
    ("FILMIC_SOFT", "Filmic Soft", "Filmic-style softer review transform for highlight-safe grading"),
    ("STANDARD_VIDEO", "Standard Video", "Standard display transform for direct Rec.709-style review"),
    ("WARM_REVIEW", "Warm Review", "Native Color Management white-balance warm review preset"),
    ("VIEW_CURVE_CONTRAST", "View Curve Contrast", "Enable Blender view curve mapping with a gentle S-curve"),
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
            if not translation.stack and not translation.color_management:
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
                if not translation.stack and not translation.color_management:
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
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_pro_grade.bl_idname, text="Apply: Sampled Pro Grade", icon="MODIFIER")
        layout.operator(
            VIDEO_TOOLKIT_OT_apply_sampled_color_management.bl_idname,
            text="Analyze: Sampled Color Management",
            icon="WORLD",
        )
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_white_balance.bl_idname, text="Analyze: Neutralize Color Cast", icon="EYEDROPPER")
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma.bl_idname, text="Analyze: Normalize Levels/Gamma", icon="IPO_EASE_IN_OUT")
        layout.operator(VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma.bl_idname, text="Analyze: Balance Hue/Chroma", icon="COLOR")
        layout.operator(VIDEO_TOOLKIT_OT_color_diagnostics.bl_idname, text="Analyze: Color Diagnostics", icon="TEXT")
        layout.operator(VIDEO_TOOLKIT_OT_apply_diagnostic_grade.bl_idname, text="Apply Diagnostic Grade", icon="COLOR")
        layout.operator(VIDEO_TOOLKIT_OT_normalize_lighting.bl_idname, text="Analyze: Normalize Flicker", icon="IPO_EASE_IN_OUT")
        layout.operator(VIDEO_TOOLKIT_OT_match_lighting_timeline.bl_idname, text="Analyze: Match Lighting Timeline", icon="GRAPH")
        layout.operator(VIDEO_TOOLKIT_OT_match_color_timeline.bl_idname, text="Analyze: Match Color Timeline", icon="COLOR")
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


class VIDEO_TOOLKIT_MT_color_management(Menu):
    bl_idname = "VIDEO_TOOLKIT_MT_color_management"
    bl_label = "Blender Color Management"

    def draw(self, _context):
        for preset_id, label, _description in COLOR_MANAGEMENT_PRESET_ITEMS:
            op = self.layout.operator(VIDEO_TOOLKIT_OT_apply_color_management_preset.bl_idname, text=label, icon="WORLD")
            op.preset_id = preset_id


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
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_pro_grade.bl_idname, text="Sampled Pro Grade", icon="MODIFIER")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_color_management.bl_idname, text="Sampled Color Management", icon="WORLD")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_white_balance.bl_idname, text="Sampled White Balance / Cast Fix", icon="EYEDROPPER")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma.bl_idname, text="Sampled Levels / Gamma Normalize", icon="IPO_EASE_IN_OUT")
    box.operator(VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma.bl_idname, text="Sampled Hue / Chroma Balance", icon="COLOR")
    box.operator(VIDEO_TOOLKIT_OT_normalize_lighting.bl_idname, text="Normalize Lighting Flicker", icon="IPO_EASE_IN_OUT")
    box.operator(VIDEO_TOOLKIT_OT_match_lighting_timeline.bl_idname, text="Match Lighting Timeline", icon="GRAPH")
    box.operator(VIDEO_TOOLKIT_OT_match_color_timeline.bl_idname, text="Match Color Timeline", icon="COLOR")
    box.operator(VIDEO_TOOLKIT_OT_color_diagnostics.bl_idname, text="Color Diagnostics Report", icon="TEXT")
    box.operator(VIDEO_TOOLKIT_OT_apply_diagnostic_grade.bl_idname, text="Apply Diagnostic Grade", icon="COLOR")
    box.prop(scene, "video_toolkit_analysis_samples")
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
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Sampled", icon="EYEDROPPER")
    op.stack_type = "SAMPLED_COLOR"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Identity", icon="COLOR")
    op.stack_type = "IDENTITY_COLOR"
    op = row.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Matched", icon="EYEDROPPER")
    op.stack_type = "MATCHED_COLOR"
    row = box.row(align=True)
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
    op = box.operator(VIDEO_TOOLKIT_OT_create_compositor_nodes.bl_idname, text="Native Node Library", icon="NODETREE")
    op.stack_type = "NODE_LIBRARY"
    if scene.video_toolkit_last_compositor_nodes:
        box.label(text=scene.video_toolkit_last_compositor_nodes, icon="INFO")


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
    if scene.video_toolkit_last_translation:
        translation.label(text=scene.video_toolkit_last_translation, icon="INFO")
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
    if color_management:
        summary += f"; color management: {', '.join(color_management)}"
    if unsupported:
        summary += f"; rendered-only/not native: {unsupported}"
    return summary


def _translated_compositor_summary(translation, node_count: int, color_management: tuple[str, ...] = ()) -> str:
    supported = ", ".join(translation.supported_filters) or "none"
    unsupported = ", ".join(translation.unsupported_filters)
    summary = f"translated compositor {supported} into {node_count} node(s)"
    if color_management:
        summary += f"; color management: {', '.join(color_management)}"
    if unsupported:
        summary += f"; rendered-only/not native: {unsupported}"
    return summary


def _apply_translation_color_management(context, translation) -> tuple[str, ...]:
    scene = context.scene
    applied: list[str] = []
    values = {key: value for key, value in translation.color_management}
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


def _create_translated_compositor_color_stack(scene, strip, translation):
    return _create_compositor_nodes_from_blender_stack(scene, strip, translation.stack, "Translated")


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


def _create_compositor_nodes_from_blender_stack(scene, strip, stack, label_prefix: str):
    tree = _ensure_compositor_tree(scene)
    origin = _next_node_origin(tree)
    movie = _new_compositor_node(tree, "CompositorNodeMovieClip", f"VTK {label_prefix} Movie Clip", 0, origin=origin)
    _assign_movie_clip(movie, _movie_path(strip))
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
    levels = _new_compositor_node(tree, "CompositorNodeLevels", f"VTK {label_prefix} Levels", len(chain_nodes), y_offset=160, origin=origin)
    viewer = _new_compositor_node(tree, "CompositorNodeViewer", f"VTK {label_prefix} Viewer", len(chain_nodes) + 1, origin=origin)
    output = _new_output_file_node(tree, scene, len(chain_nodes) + 1, y_offset=-160, origin=origin)
    output.name = f"VTK {label_prefix} Output File"
    output.label = f"VTK {label_prefix} Output File"
    final_socket = _link_compositor_chain(tree, chain_nodes)
    _link_socket(tree, final_socket, _image_input(levels))
    _link_socket(tree, final_socket, _image_input(viewer))
    _link_socket(tree, final_socket, _first_socket(output.inputs))
    created = chain_nodes + [levels, viewer, output]
    if skipped:
        for node in created:
            node["video_toolkit_skipped_translated_modifiers"] = skipped
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


def _write_diagnostics_text(strip, report: str):
    name = f"VTK Color Diagnostics - {strip.name}"
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    text.clear()
    text.write(report + "\n")
    return text


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
    VIDEO_TOOLKIT_OT_color_diagnostics,
    VIDEO_TOOLKIT_OT_apply_diagnostic_grade,
    VIDEO_TOOLKIT_OT_apply_sampled_white_balance,
    VIDEO_TOOLKIT_OT_apply_sampled_levels_gamma,
    VIDEO_TOOLKIT_OT_apply_sampled_hue_chroma,
    VIDEO_TOOLKIT_OT_apply_sampled_pro_grade,
    VIDEO_TOOLKIT_OT_normalize_lighting,
    VIDEO_TOOLKIT_OT_match_lighting_timeline,
    VIDEO_TOOLKIT_OT_match_color_timeline,
    VIDEO_TOOLKIT_OT_translate_ffmpeg_chain,
    VIDEO_TOOLKIT_OT_clear_live_modifiers,
    VIDEO_TOOLKIT_OT_create_compositor_nodes,
    VIDEO_TOOLKIT_OT_apply_color_management_preset,
    VIDEO_TOOLKIT_OT_apply_sampled_color_management,
    VIDEO_TOOLKIT_OT_open_output_folder,
    VIDEO_TOOLKIT_MT_live_blender_color,
    VIDEO_TOOLKIT_MT_native_blender_primitives,
    VIDEO_TOOLKIT_MT_restoration,
    VIDEO_TOOLKIT_MT_resolution_motion,
    VIDEO_TOOLKIT_MT_blender_vse_modifiers,
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
    bpy.types.Scene.video_toolkit_last_sampled_color_management = bpy.props.StringProperty(
        name="Last Sampled Color Management",
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
        "video_toolkit_last_diagnostics",
        "video_toolkit_last_diagnostics_text",
        "video_toolkit_last_diagnostic_grade",
        "video_toolkit_last_sampled_white_balance",
        "video_toolkit_last_sampled_levels_gamma",
        "video_toolkit_last_sampled_hue_chroma",
        "video_toolkit_last_sampled_pro_grade",
        "video_toolkit_last_sampled_color_management",
        "video_toolkit_apply_target",
        "video_toolkit_ffmpeg_chain",
        "video_toolkit_last_translation",
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
