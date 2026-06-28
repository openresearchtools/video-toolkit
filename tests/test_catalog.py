from video_toolkit.catalog import (
    blender_modifier_tools,
    categories,
    ffmpeg_tools,
    get_tool,
    all_tools,
)
from video_toolkit.compositor import (
    COLOR_WORKSPACE_STACK_NODE_TYPES,
    RESTORATION_WORKSPACE_STACK_NODE_TYPES,
    compositor_node_types,
)


def test_tool_ids_are_unique():
    ids = [tool.id for tool in all_tools()]
    assert len(ids) == len(set(ids))


def test_expected_blender_vse_modifiers_are_covered():
    modifiers = set()
    for tool in blender_modifier_tools():
        modifiers.update(tool.blender_modifiers)
    assert modifiers == {
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "CURVES",
        "HUE_CORRECT",
        "MASK",
        "TONEMAP",
        "WHITE_BALANCE",
    }


def test_professional_restoration_tools_are_present():
    expected = {
        "deflicker",
        "lighting_normalizer",
        "deflicker_normalize",
        "denoise_light",
        "denoise_strong",
        "restore_sharpness",
        "deinterlace",
        "quick_deshake",
        "stabilize",
        "native_compositor_restore_nodes",
        "native_compositor_sharpen_cleanup",
        "native_compositor_lens_repair",
    }
    assert expected.issubset({tool.id for tool in all_tools()})


def test_native_compositor_catalog_tools_are_exposed():
    expected = {
        "native_compositor_all_color_primitives": {
            "EXPOSURE",
            "BRIGHT_CONTRAST",
            "COLOR_BALANCE",
            "COLOR_CORRECTION",
            "CURVE_RGB",
            "HUE_SAT",
            "HUE_CORRECT",
            "TONEMAP",
            "INVERT",
            "POSTERIZE",
            "PREMUL_KEY",
        },
        "native_compositor_exposure": {"EXPOSURE"},
        "native_compositor_color_correction": {"COLOR_CORRECTION"},
        "native_compositor_hue_saturation": {"HUE_SAT"},
        "native_compositor_invert": {"INVERT"},
        "native_compositor_posterize": {"POSTERIZE"},
        "native_compositor_premultiply": {"PREMUL_KEY"},
        "native_compositor_restore_nodes": {"DENOISE", "DESPECKLE", "BILATERAL_BLUR", "ANTI_ALIASING"},
        "native_compositor_sharpen_cleanup": {"FILTER", "DESPECKLE", "ANTI_ALIASING"},
        "native_compositor_lens_repair": {"LENS_DISTORTION", "SCALE", "ANTI_ALIASING"},
        "native_compositor_resize_reframe": {"SCALE", "CROP"},
        "native_compositor_motion_geometry": {"ROTATE", "DIRECTIONAL_BLUR", "SCALE"},
    }
    for tool_id, node_types in expected.items():
        tool = get_tool(tool_id)
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert {node_type for node_type, _settings in tool.compositor_stack} == node_types
        assert tool.category in {"Native Blender Primitives", "Restoration", "Resolution & Motion"}


def test_categories_keep_ui_order():
    assert categories() == (
        "Live Blender Color",
        "Native Blender Primitives",
        "Restoration",
        "Resolution & Motion",
        "Live Blender Modifiers",
    )


def test_color_enhance_tools_are_blender_native_live_stacks():
    for tool_id in (
        "auto_enhance",
        "neutral_grade",
        "punchy_color",
        "soft_contrast",
        "exposure_lift",
        "gamma_brighten",
        "gamma_deepen",
        "warm_balance",
        "cool_balance",
        "saturation_boost",
        "saturation_reduce",
        "monochrome",
        "faded_film",
        "high_contrast_curve",
        "medium_contrast_curve",
        "levels_expand",
        "levels_soft_clamp",
        "shadow_highlight_balance",
        "vibrance",
        "skin_safe_vibrance",
        "exposure_protect",
        "temperature_warm",
        "temperature_cool",
        "legal_range_clamp",
        "hdr_tone_compress",
        "black_point_cleanup",
        "white_point_recovery",
        "luma_s_curve",
        "red_gamma_trim",
        "green_gamma_trim",
        "blue_gamma_trim",
        "magenta_green_tint",
        "green_cast_repair",
        "shadow_cool_tint",
        "highlight_warm_tint",
        "skin_tone_isolation",
        "primary_color_board",
        "log_zone_color_board",
        "asc_cdl_finish_board",
        "six_vector_hue_board",
        "secondary_skin_vector",
        "palette_separation_board",
        "broadcast_safe_finish",
        "match_prep_neutralizer",
        "selective_color_punch",
        "colorize_blue_steel",
        "grey_edge_balance",
        "pseudocolor_viridis",
        "lut_invert_curve",
        "histogram_equalize",
        "color_hold_blue",
        "hsv_hold_blue",
    ):
        tool = get_tool(tool_id)
        assert tool.is_blender_modifier
        assert tool.blender_modifiers
        assert not tool.ffmpeg_filter


def test_translated_ffmpeg_color_intent_tools_are_live_and_node_ready():
    expected = {
        "selective_color_punch",
        "colorize_blue_steel",
        "grey_edge_balance",
        "pseudocolor_viridis",
        "lut_invert_curve",
        "histogram_equalize",
        "color_hold_blue",
        "hsv_hold_blue",
    }
    for tool_id in expected:
        tool = get_tool(tool_id)
        assert tool.category == "Live Blender Color"
        assert tool.is_blender_modifier
        assert tool.blender_stack
        assert tool.compositor_stack
    assert get_tool("pseudocolor_viridis").blender_modifiers == ("HUE_CORRECT", "CURVES", "COLOR_BALANCE")
    assert get_tool("lut_invert_curve").blender_modifiers == ("CURVES",)
    assert "TONEMAP" in get_tool("histogram_equalize").blender_modifiers


def test_professional_color_board_tools_are_native_and_node_ready():
    expected = {
        "primary_color_board",
        "log_zone_color_board",
        "asc_cdl_finish_board",
        "six_vector_hue_board",
        "secondary_skin_vector",
        "palette_separation_board",
        "broadcast_safe_finish",
        "match_prep_neutralizer",
    }
    for tool_id in expected:
        tool = get_tool(tool_id)
        modifier_types = set(tool.blender_modifiers)
        assert tool.category == "Live Blender Color"
        assert tool.is_blender_modifier
        assert tool.blender_stack
        assert modifier_types.issubset(
            {"BRIGHT_CONTRAST", "COLOR_BALANCE", "CURVES", "HUE_CORRECT", "TONEMAP", "WHITE_BALANCE"}
        )
    assert {"COLOR_BALANCE", "CURVES", "HUE_CORRECT", "TONEMAP"}.issubset(
        set(get_tool("primary_color_board").blender_modifiers)
    )
    assert get_tool("six_vector_hue_board").blender_modifiers[0] == "HUE_CORRECT"
    assert "CURVES" in get_tool("broadcast_safe_finish").blender_modifiers


def test_every_native_blender_color_primitive_is_exposed():
    stack = get_tool("native_all_color_tools").blender_modifiers
    assert stack.count("BRIGHT_CONTRAST") == 1
    assert stack.count("COLOR_BALANCE") == 2
    assert stack.count("TONEMAP") == 2
    assert {"WHITE_BALANCE", "CURVES", "HUE_CORRECT", "MASK"}.issubset(set(stack))
    for tool_id in (
        "native_bright_contrast",
        "native_lift_gamma_gain",
        "native_asc_cdl",
        "native_rd_tonemap",
        "native_rh_tonemap",
        "native_curves_editor",
        "native_hue_correct_editor",
        "native_white_balance_editor",
        "native_mask_slot",
    ):
        assert get_tool(tool_id).is_blender_modifier


def test_native_compositor_video_nodes_are_tracked():
    nodes = set(compositor_node_types())
    assert {
        "CompositorNodeExposure",
        "CompositorNodeBrightContrast",
        "CompositorNodeColorBalance",
        "CompositorNodeColorCorrection",
        "CompositorNodeCurveRGB",
        "CompositorNodeHueSat",
        "CompositorNodeHueCorrect",
        "CompositorNodeTonemap",
        "CompositorNodeDenoise",
        "CompositorNodeDBlur",
        "CompositorNodeStabilize",
        "CompositorNodeMovieDistortion",
        "CompositorNodeGroup",
        "CompositorNodeOutputFile",
        "CompositorNodeViewer",
    }.issubset(nodes)
    assert len(compositor_node_types()) == len(nodes)
    assert set(COLOR_WORKSPACE_STACK_NODE_TYPES).issubset(nodes)
    assert set(RESTORATION_WORKSPACE_STACK_NODE_TYPES).issubset(nodes)


def test_ffmpeg_tools_have_filters_or_stabilization():
    for tool in ffmpeg_tools():
        assert tool.ffmpeg_filter or tool.two_pass_stabilize


def test_get_tool_rejects_unknown_id():
    try:
        get_tool("missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("unknown tool id should raise KeyError")
