#!/usr/bin/env python3
"""Capture proof screenshots of the Blender Video Toolkit UI."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "output" / "blender_ui"
VIDEO = ROOT / "tests" / "fixtures" / "real_user_video.mp4"


def main() -> None:
    _hide_startup_splash()
    sys.path.insert(0, str(ROOT))
    import video_toolkit

    video_toolkit.register()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _ensure_selected_movie_strip()
    area, region, space = _sequencer_area()
    with bpy.context.temp_override(area=area, region=region, space_data=space):
        _frame_selected_strip()
        bpy.ops.wm.call_panel(name="VIDEO_TOOLKIT_PT_video_filters", keep_open=True)
    bpy.app.timers.register(_screenshot_and_quit, first_interval=1.5)


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
    scene.video_toolkit_ffmpeg_chain = "eq=contrast=1.08:saturation=1.05:gamma=1.02,colorbalance=rs=0.05:bh=-0.04"
    if hasattr(scene.view_settings, "use_curve_mapping"):
        scene.view_settings.use_curve_mapping = True


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
