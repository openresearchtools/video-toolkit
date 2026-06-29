#!/usr/bin/env python3
"""Capture proof screenshots of the Blender Video Effects sidebar."""

from __future__ import annotations

import sys
import os
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "output" / "blender_ui"
VIDEO = Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", str(ROOT / "tests" / "fixtures" / "real_user_video.mp4")))
USE_INSTALLED_ADDON = os.environ.get("VIDEO_TOOLKIT_USE_INSTALLED_ADDON") == "1"
SCREENSHOT_DELAY = float(os.environ.get("VIDEO_TOOLKIT_SCREENSHOT_DELAY", "1.5"))


def main() -> None:
    _hide_startup_splash()
    _enable_video_toolkit()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _ensure_selected_movie_strip()
    _prepare_effects_panel_state()
    area, region, space = _sequencer_area()
    area, region, space = _maximize_sequencer_area(area, region, space)
    _activate_video_effects_sidebar(area)
    with bpy.context.temp_override(area=area, region=region, space_data=space):
        _frame_selected_strip()
    bpy.app.timers.register(_screenshot_and_quit, first_interval=SCREENSHOT_DELAY)


def _enable_video_toolkit() -> None:
    if USE_INSTALLED_ADDON:
        bpy.ops.preferences.addon_enable(module="video_toolkit")
        return
    sys.path.insert(0, str(ROOT))
    import video_toolkit

    try:
        video_toolkit.unregister()
    except Exception:
        pass
    video_toolkit.register()


def _hide_startup_splash() -> None:
    if hasattr(bpy.context.preferences.view, "show_splash"):
        bpy.context.preferences.view.show_splash = False


def _ensure_selected_movie_strip() -> None:
    scene = bpy.context.scene
    if scene.sequence_editor is None:
        scene.sequence_editor_create()
    editor = scene.sequence_editor
    strip = editor.active_strip
    if strip is None or strip.type != "MOVIE":
        strip = editor.strips.new_movie(
            name="SELECTED VIDEO - OPEN RESEARCH TOOLKIT TEST",
            filepath=str(VIDEO),
            channel=1,
            frame_start=1,
        )
    for candidate in editor.strips_all:
        candidate.select = False
    strip.select = True
    editor.active_strip = strip
    scene.frame_start = int(strip.frame_final_start)
    scene.frame_end = int(strip.frame_final_end)
    scene.frame_current = min(scene.frame_start + 24, scene.frame_end - 1)
    scene.video_toolkit_analysis_samples = 24
    scene.video_toolkit_apply_target = "ACTIVE"
    scene.video_toolkit_sidecar_section = "BROWSER"
    scene.video_toolkit_ffmpeg_chain = "eq=contrast=1.08:saturation=1.05:gamma=1.02,colorbalance=rs=0.05:bh=-0.04"
    if hasattr(scene.view_settings, "use_curve_mapping"):
        scene.view_settings.use_curve_mapping = True


def _prepare_effects_panel_state() -> None:
    scene = bpy.context.scene
    try:
        bpy.ops.video_toolkit.select_sidecar_tool(filter_id="live_gamma_grade")
    except Exception:
        return
    for index, parameter in enumerate(getattr(scene, "video_toolkit_tool_parameters", [])):
        if parameter.path == "bright":
            try:
                bpy.ops.video_toolkit.toggle_tool_parameter(parameter_index=index)
            except Exception:
                pass
            break


def _sequencer_area():
    screen = bpy.context.window.screen
    area = max(screen.areas, key=lambda item: item.width * item.height)
    area.type = "SEQUENCE_EDITOR"
    space = area.spaces.active
    if hasattr(space, "view_type"):
        space.view_type = "SEQUENCER_PREVIEW"
    if hasattr(space, "show_region_ui"):
        space.show_region_ui = True
    region = next(region for region in area.regions if region.type == "WINDOW")
    return area, region, space


def _maximize_sequencer_area(area, region, space):
    with bpy.context.temp_override(area=area, region=region, space_data=space):
        try:
            bpy.ops.screen.screen_full_area(use_hide_panels=False)
        except Exception:
            pass
    return _sequencer_area()


def _activate_video_effects_sidebar(area) -> None:
    for region in area.regions:
        if region.type == "UI" and hasattr(region, "active_panel_category"):
            try:
                region.active_panel_category = "Video Effects"
                region.tag_refresh_ui()
            except AttributeError:
                pass
            break


def _frame_selected_strip() -> None:
    for operator in (
        bpy.ops.sequencer.refresh_all,
        bpy.ops.sequencer.view_selected,
        bpy.ops.sequencer.view_all_preview,
    ):
        try:
            operator()
        except Exception:
            pass


def _screenshot_and_quit():
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=3)
    bpy.ops.screen.screenshot(filepath=str(OUTPUT / "video_filters_panel_open.png"))
    bpy.ops.wm.quit_blender()
    return None

main()
