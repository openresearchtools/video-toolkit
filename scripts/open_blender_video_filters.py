#!/usr/bin/env python3
"""Open Blender's Sequencer with the Video Effects sidebar ready for manual testing."""

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
    reference.mute = True
    editor.active_strip = strip
    scene.frame_start = int(strip.frame_final_start)
    scene.frame_end = int(strip.frame_final_end)
    scene.frame_current = min(scene.frame_start + 24, scene.frame_end - 1)
    scene.video_toolkit_analysis_samples = 24
    scene.video_toolkit_apply_target = "ACTIVE"
    scene.video_toolkit_sidecar_section = "ENHANCE"
    scene.video_toolkit_ffmpeg_chain = (
        "colorspace=iall=bt709:all=bt709:irange=tv:range=pc,"
        "normalize=smoothing=24:independence=0.7:strength=0.55,"
        "eq=contrast=1.08:saturation=1.05:gamma=1.02,"
        "colorbalance=rs=0.05:bh=-0.04,"
        "colorcorrect=rl=0.04:bl=-0.02:saturation=1.04,"
        "greyedge=difford=2:minknorm=5:sigma=2,"
        "chromakey=color=green:similarity=0.12:blend=0.04,"
        "colorkey=color=blue:similarity=0.10:blend=0.03,"
        "hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.10:blend=0.02,"
        "lumakey=threshold=0.20:tolerance=0.08:softness=0.02,"
        "rgbashift=rh=4:rv=-2:bh=-3:bv=2,"
        "chromashift=cbh=2:cbv=-1:crh=-2:crv=1,"
        "alphaextract,"
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
        "pseudocolor=preset=viridis:opacity=0.75:index=1,"
        "histeq=strength=0.20:intensity=0.18,"
        "zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full"
    )
    try:
        bpy.ops.video_toolkit.color_diagnostics()
        bpy.ops.video_toolkit.recommend_catalog_recipes()
        bpy.ops.video_toolkit.apply_recommended_recipe_mix()
        bpy.ops.video_toolkit.create_recommended_recipe_mix_nodes()
        bpy.ops.video_toolkit.apply_professional_color_workflow()
        bpy.ops.video_toolkit.apply_translated_color_workflow()
        bpy.ops.video_toolkit.apply_filter(filter_id="primary_color_board")
        bpy.ops.video_toolkit.apply_filter(filter_id="six_vector_hue_board")
        bpy.ops.video_toolkit.apply_filter(filter_id="broadcast_safe_finish")
        bpy.ops.video_toolkit.apply_diagnostic_grade()
        bpy.ops.video_toolkit.apply_sampled_white_balance()
        bpy.ops.video_toolkit.apply_sampled_levels_gamma()
        bpy.ops.video_toolkit.apply_sampled_hue_chroma()
        bpy.ops.video_toolkit.apply_sampled_pro_grade()
        bpy.ops.video_toolkit.apply_sampled_color_board()
        bpy.ops.video_toolkit.apply_reference_color_board()
        bpy.ops.video_toolkit.apply_sampled_color_management()
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="NATIVE_COLOR_ROOM")
        bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id="primary_color_board")
        bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id="live_pro_color_stack")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="SAMPLED_COLOR_MANAGEMENT")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="SAMPLED_COLOR_BOARD")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="SAMPLED_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="IDENTITY_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="DIAGNOSTIC_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="MATCHED_COLOR")
        bpy.ops.video_toolkit.create_compositor_nodes(stack_type="REFERENCE_COLOR_BOARD")
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
    area, region, space = _maximize_sequencer_area(area, region, space)
    _activate_video_effects_sidebar(area)
    _frame_selected_strip(area, region, space)


def _sequencer_area():
    screen = bpy.context.window.screen
    area = max(screen.areas, key=lambda item: item.width * item.height)
    area.type = "SEQUENCE_EDITOR"
    space = area.spaces.active
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
