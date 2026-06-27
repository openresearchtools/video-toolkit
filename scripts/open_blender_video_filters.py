#!/usr/bin/env python3
"""Open Blender's Sequencer with Video Toolkit ready for manual testing."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "output" / "blender_ui"
VIDEO = ROOT / "tests" / "fixtures" / "real_user_video.mp4"


def main() -> None:
    _hide_startup_splash()
    sys.path.insert(0, str(ROOT))
    import video_toolkit

    try:
        video_toolkit.unregister()
    except Exception:
        pass
    video_toolkit.register()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    _setup_scene()
    _open_sequencer()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "video_toolkit_open_ready.blend"))
    bpy.app.timers.register(_show_panel, first_interval=0.5)


def _hide_startup_splash() -> None:
    if hasattr(bpy.context.preferences.view, "show_splash"):
        bpy.context.preferences.view.show_splash = False


def _setup_scene() -> None:
    scene = bpy.context.scene
    if scene.sequence_editor is None:
        scene.sequence_editor_create()
    editor = scene.sequence_editor
    strip = editor.active_strip
    if strip is None or strip.type != "MOVIE":
        strip = editor.strips.new_movie(
            name="SELECTED VIDEO - OPEN RESEARCH TOOLKIT",
            filepath=str(VIDEO),
            channel=1,
            frame_start=1,
        )
    reference = next((candidate for candidate in editor.strips_all if candidate.name.startswith("REFERENCE VIDEO")), None)
    if reference is None or reference.type != "MOVIE":
        reference = editor.strips.new_movie(
            name="REFERENCE VIDEO - OPEN RESEARCH TOOLKIT",
            filepath=str(VIDEO),
            channel=2,
            frame_start=1,
        )
    for candidate in editor.strips_all:
        candidate.select = False
    strip.select = True
    reference.select = True
    editor.active_strip = strip
    scene.frame_start = int(strip.frame_final_start)
    scene.frame_end = int(strip.frame_final_end)
    scene.frame_current = min(scene.frame_start + 24, scene.frame_end - 1)
    scene.video_toolkit_analysis_samples = 24
    scene.video_toolkit_apply_target = "ACTIVE"
    scene.video_toolkit_ffmpeg_chain = "eq=contrast=1.08:saturation=1.05:gamma=1.02,colorbalance=rs=0.05:bh=-0.04"
    try:
        bpy.ops.video_toolkit.color_diagnostics()
        bpy.ops.video_toolkit.apply_diagnostic_grade()
        bpy.ops.video_toolkit.apply_sampled_white_balance()
        bpy.ops.video_toolkit.apply_sampled_levels_gamma()
        bpy.ops.video_toolkit.apply_sampled_hue_chroma()
        bpy.ops.video_toolkit.apply_sampled_pro_grade()
        bpy.ops.video_toolkit.apply_sampled_color_management()
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="SAMPLED_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="IDENTITY_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="MATCHED_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="COLOR_TIMELINE_MATCH")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="TRANSLATED_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="LIGHTING_NORMALIZE")
    except Exception:
        traceback.print_exc()


def _open_sequencer() -> None:
    area, region, space = _sequencer_area()
    area.type = "SEQUENCE_EDITOR"
    if hasattr(space, "view_type"):
        space.view_type = "SEQUENCER_PREVIEW"
    if hasattr(space, "show_region_ui"):
        space.show_region_ui = True
    _frame_selected_strip(area, region, space)


def _show_panel():
    try:
        area, region, space = _sequencer_area()
        _frame_selected_strip(area, region, space)
        with bpy.context.temp_override(area=area, region=region, space_data=space):
            bpy.ops.wm.call_panel(name="VIDEO_TOOLKIT_PT_video_filters", keep_open=True)
    except Exception:
        traceback.print_exc()
    return None


def _sequencer_area():
    screen = bpy.context.window.screen
    area = max(screen.areas, key=lambda item: item.width * item.height)
    area.type = "SEQUENCE_EDITOR"
    space = area.spaces.active
    region = next(region for region in area.regions if region.type == "WINDOW")
    return area, region, space


def _frame_selected_strip(area, region, space) -> None:
    with bpy.context.temp_override(area=area, region=region, space_data=space):
        for operator in (
            bpy.ops.sequencer.refresh_all,
            bpy.ops.sequencer.view_selected,
            bpy.ops.sequencer.view_all_preview,
        ):
            try:
                operator()
            except Exception:
                pass


main()
