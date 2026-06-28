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
    compositor_node_tools,
    compositor_node_types,
)
from video_toolkit.ffmpeg_native import NATIVE_FFMPEG_COMPOSITOR_FILTERS


STACK_TYPE_TO_COMPOSITOR_NODE = {
    "ANTI_ALIASING": "CompositorNodeAntiAliasing",
    "BILATERAL_BLUR": "CompositorNodeBilateralblur",
    "BLUR": "CompositorNodeBlur",
    "BRIGHT_CONTRAST": "CompositorNodeBrightContrast",
    "CHANNEL_SHIFT": "CompositorNodeTranslate",
    "CHROMA_MATTE": "CompositorNodeChromaMatte",
    "COLOR_BALANCE": "CompositorNodeColorBalance",
    "COLOR_CORRECTION": "CompositorNodeColorCorrection",
    "COLOR_MATTE": "CompositorNodeColorMatte",
    "COLOR_SPILL": "CompositorNodeColorSpill",
    "CONVOLVE": "CompositorNodeConvolve",
    "CROP": "CompositorNodeCrop",
    "CURVE_RGB": "CompositorNodeCurveRGB",
    "DENOISE": "CompositorNodeDenoise",
    "DESPECKLE": "CompositorNodeDespeckle",
    "DILATE_ERODE": "CompositorNodeDilateErode",
    "DIRECTIONAL_BLUR": "CompositorNodeDBlur",
    "EXPOSURE": "CompositorNodeExposure",
    "FILTER": "CompositorNodeFilter",
    "FLIP": "CompositorNodeFlip",
    "HUE_CORRECT": "CompositorNodeHueCorrect",
    "HUE_SAT": "CompositorNodeHueSat",
    "INVERT": "CompositorNodeInvert",
    "LENS_DISTORTION": "CompositorNodeLensdist",
    "LUMA_MATTE": "CompositorNodeLumaMatte",
    "PLANE_EXTRACT": "CompositorNodeRGBToBW",
    "PLANE_SHUFFLE": "CompositorNodeSeparateColor",
    "POSTERIZE": "CompositorNodePosterize",
    "PREMUL_KEY": "CompositorNodePremulKey",
    "ROTATE": "CompositorNodeRotate",
    "SCALE": "CompositorNodeScale",
    "TONEMAP": "CompositorNodeTonemap",
}

SPECIAL_STACK_TYPE_TO_COMPOSITOR_NODES = {
    "BACKGROUND_KEY": {"CompositorNodeBlur", "CompositorNodeDiffMatte", "CompositorNodeSetAlpha"},
    "BOX_MASK_ALPHA": {"CompositorNodeBoxMask", "CompositorNodeSetAlpha"},
    "BLEND_COMPOSITE": {"CompositorNodeAlphaOver"},
    "BLANK_IMAGE_OVERLAY": {"CompositorNodeAlphaOver", "CompositorNodeBlankImage"},
    "BOKEH_IMAGE_BLUR": {"CompositorNodeBokehBlur", "CompositorNodeBokehImage"},
    "ELLIPSE_MASK_ALPHA": {"CompositorNodeEllipseMask", "CompositorNodeSetAlpha"},
    "DOUBLE_EDGE_MASK_ALPHA": {
        "CompositorNodeBoxMask",
        "CompositorNodeEllipseMask",
        "CompositorNodeDoubleEdgeMask",
        "CompositorNodeSetAlpha",
    },
    "MASK_TO_SDF_ALPHA": {"CompositorNodeBoxMask", "CompositorNodeMaskToSDF", "CompositorNodeSetAlpha"},
    "MASKED_BLEND_COMPOSITE": {"CompositorNodeAlphaOver", "CompositorNodeLumaMatte"},
    "NORMALIZE_LUMA": {"CompositorNodeCombineColor", "CompositorNodeNormalize", "CompositorNodeRGBToBW"},
    "RGB_OVERLAY": {"CompositorNodeAlphaOver", "CompositorNodeRGB"},
    "SCOPE_MONITOR": {
        "CompositorNodeCombineColor",
        "CompositorNodeImageInfo",
        "CompositorNodeLevels",
        "CompositorNodeRGBToBW",
        "CompositorNodeSeparateColor",
        "CompositorNodeViewer",
    },
    "TEXT_OVERLAY": {"CompositorNodeAlphaOver", "CompositorNodeStringToImage"},
}


def _tool_compositor_node_classes(tool_id):
    tool = get_tool(tool_id)
    node_classes = set()
    for stack_type, settings in tool.compositor_stack:
        if stack_type == "NATIVE_NODE":
            node_classes.add(settings["node_type"])
        elif stack_type in STACK_TYPE_TO_COMPOSITOR_NODE:
            node_classes.add(STACK_TYPE_TO_COMPOSITOR_NODE[stack_type])
        elif stack_type in SPECIAL_STACK_TYPE_TO_COMPOSITOR_NODES:
            node_classes.update(SPECIAL_STACK_TYPE_TO_COMPOSITOR_NODES[stack_type])
    return node_classes


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


def test_live_gamma_channel_math_tools_are_exposed():
    expected = {
        "rgb_gamma_board": ({"BRIGHT_CONTRAST", "COLOR_BALANCE", "HUE_CORRECT", "TONEMAP"}, {"CompositorNodeBrightContrast", "CompositorNodeColorBalance", "CompositorNodeHueCorrect", "CompositorNodeTonemap"}),
        "channel_mixer_balance": ({"COLOR_BALANCE", "WHITE_BALANCE"}, {"CompositorNodeColorBalance"}),
        "opponent_color_contrast": ({"COLOR_BALANCE", "WHITE_BALANCE"}, {"CompositorNodeColorBalance"}),
        "low_high_colorcorrect": ({"COLOR_BALANCE", "HUE_CORRECT"}, {"CompositorNodeColorCorrection"}),
        "independent_rgb_normalize": ({"CURVES", "TONEMAP"}, {"CompositorNodeCurveRGB", "CompositorNodeTonemap"}),
        "hue_sat_intensity_board": ({"HUE_CORRECT"}, {"CompositorNodeHueSat"}),
        "highlight_desat_tonemap": ({"TONEMAP", "HUE_CORRECT"}, {"CompositorNodeTonemap", "CompositorNodeHueCorrect"}),
        "broadcast_gamma_guard": ({"CURVES", "BRIGHT_CONTRAST", "COLOR_BALANCE", "HUE_CORRECT", "TONEMAP"}, {"CompositorNodeCurveRGB", "CompositorNodeBrightContrast", "CompositorNodeColorBalance", "CompositorNodeHueCorrect", "CompositorNodeTonemap"}),
        "gray_world_neutralizer": ({"WHITE_BALANCE", "COLOR_BALANCE", "BRIGHT_CONTRAST", "HUE_CORRECT"}, {"CompositorNodeColorBalance", "CompositorNodeBrightContrast", "CompositorNodeHueCorrect"}),
        "rgb_lut_trim": ({"CURVES"}, {"CompositorNodeCurveRGB"}),
        "selective_neutral_balance": ({"HUE_CORRECT", "COLOR_BALANCE"}, {"CompositorNodeHueCorrect", "CompositorNodeColorBalance"}),
        "geq_rgb_math": ({"CURVES"}, {"CompositorNodeCurveRGB"}),
        "lut1d_film_curve": ({"CURVES", "COLOR_BALANCE"}, {"CompositorNodeCurveRGB", "CompositorNodeColorBalance"}),
        "lut3d_scene_look": ({"CURVES", "COLOR_BALANCE", "TONEMAP"}, {"CompositorNodeCurveRGB", "CompositorNodeColorBalance", "CompositorNodeTonemap"}),
        "haldclut_display_match": ({"CURVES", "COLOR_BALANCE", "TONEMAP"}, {"CompositorNodeCurveRGB", "CompositorNodeColorBalance", "CompositorNodeTonemap"}),
        "colormap_palette_match": ({"HUE_CORRECT", "CURVES", "COLOR_BALANCE"}, {"CompositorNodeHueCorrect", "CompositorNodeCurveRGB", "CompositorNodeColorBalance"}),
        "midway_equalize": ({"CURVES", "TONEMAP"}, {"CompositorNodeCurveRGB", "CompositorNodeTonemap"}),
        "temporal_midway_equalize": ({"CURVES", "TONEMAP"}, {"CompositorNodeCurveRGB", "CompositorNodeTonemap"}),
    }
    for tool_id, (modifier_types, node_classes) in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Live Blender Color"
        assert tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert not tool.is_compositor
        assert modifier_types.issubset(set(tool.blender_modifiers))
        assert tool.compositor_stack
        assert node_classes.issubset(_tool_compositor_node_classes(tool_id))


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


def test_native_matte_and_channel_tools_are_exposed():
    expected = {
        "native_chroma_key_matte": {"CHROMA_MATTE"},
        "native_color_key_matte": {"COLOR_MATTE"},
        "native_hsv_key_matte": {"COLOR_MATTE"},
        "native_luma_key_matte": {"LUMA_MATTE"},
        "native_despill_color_spill": {"COLOR_SPILL"},
        "native_background_key_matte": {"BACKGROUND_KEY"},
        "native_threshold_matte": {"LUMA_MATTE"},
        "native_masked_threshold_matte": {"LUMA_MATTE"},
        "native_blend_overlay_composite": {"BLEND_COMPOSITE"},
        "native_temporal_blend_ghost": {"BLEND_COMPOSITE"},
        "native_lut2_expression_mix": {"BLEND_COMPOSITE"},
        "native_tlut2_temporal_expression": {"BLEND_COMPOSITE"},
        "native_masked_merge": {"MASKED_BLEND_COMPOSITE"},
        "native_mergeplanes_router": {"PLANE_SHUFFLE"},
        "native_rgba_channel_shift": {"CHANNEL_SHIFT"},
        "native_chroma_channel_shift": {"CHANNEL_SHIFT"},
        "native_chromatic_aberration_offset": {"CHANNEL_SHIFT"},
        "native_luma_plane_extract": {"PLANE_EXTRACT"},
        "native_alpha_extract": {"PLANE_EXTRACT"},
        "native_premultiply_alpha": {"PREMUL_KEY"},
        "native_plane_shuffle_bgr": {"PLANE_SHUFFLE"},
        "native_straight_alpha": {"PREMUL_KEY"},
    }
    for tool_id, node_types in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Matte & Channel"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert {node_type for node_type, _settings in tool.compositor_stack} == node_types


def test_native_color_and_composite_node_tools_are_exposed():
    expected = {
        "native_compositor_color_space_convert": "CompositorNodeConvertColorSpace",
        "native_compositor_display_convert": "CompositorNodeConvertToDisplay",
        "native_compositor_set_alpha": "CompositorNodeSetAlpha",
        "native_compositor_alpha_over": "CompositorNodeAlphaOver",
    }
    for tool_id, node_type in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Color & Composite"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert tool.compositor_stack == (("NATIVE_NODE", tool.compositor_stack[0][1]),)
        assert tool.compositor_stack[0][1]["node_type"] == node_type


def test_native_matte_keying_node_tools_are_exposed():
    expected = {
        "native_compositor_channel_matte": "CompositorNodeChannelMatte",
        "native_compositor_difference_matte": "CompositorNodeDiffMatte",
        "native_compositor_distance_matte": "CompositorNodeDistanceMatte",
        "native_compositor_keying": "CompositorNodeKeying",
        "native_compositor_color_spill": "CompositorNodeColorSpill",
    }
    for tool_id, node_type in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Matte & Channel"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert tool.compositor_stack[0][0] == "NATIVE_NODE"
        assert tool.compositor_stack[0][1]["node_type"] == node_type


def test_native_matte_mask_alpha_tools_are_exposed():
    expected = {
        "native_compositor_box_mask_alpha": {"CompositorNodeBoxMask", "CompositorNodeSetAlpha"},
        "native_compositor_ellipse_mask_alpha": {"CompositorNodeEllipseMask", "CompositorNodeSetAlpha"},
        "native_compositor_double_edge_mask_alpha": {
            "CompositorNodeBoxMask",
            "CompositorNodeEllipseMask",
            "CompositorNodeDoubleEdgeMask",
            "CompositorNodeSetAlpha",
        },
        "native_compositor_mask_to_sdf_alpha": {"CompositorNodeBoxMask", "CompositorNodeMaskToSDF", "CompositorNodeSetAlpha"},
    }
    for tool_id, node_types in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Matte & Channel"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert node_types.issubset(_tool_compositor_node_classes(tool_id))


def test_native_matte_source_tools_are_exposed():
    expected = {
        "native_compositor_blender_mask_source": "CompositorNodeMask",
        "native_compositor_keying_screen": "CompositorNodeKeyingScreen",
        "native_compositor_id_mask": "CompositorNodeIDMask",
    }
    for tool_id, node_type in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Matte & Channel"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert tool.compositor_stack[0][0] == "NATIVE_NODE"
        assert tool.compositor_stack[0][1]["node_type"] == node_type


def test_native_filter_and_blur_tools_are_exposed():
    expected = {
        "native_unsharp_filter": {"FILTER"},
        "native_cas_sharpen": {"FILTER"},
        "native_elbg_posterize": {"POSTERIZE"},
        "native_sobel_edges": {"FILTER"},
        "native_prewitt_edges": {"FILTER"},
        "native_kirsch_edges": {"FILTER"},
        "native_edge_detect": {"FILTER"},
        "native_erode_matte": {"DILATE_ERODE"},
        "native_dilate_matte": {"DILATE_ERODE"},
        "native_convolution_sharpen": {"CONVOLVE"},
        "native_fftfilt_detail": {"FILTER"},
        "native_average_blur": {"BLUR"},
        "native_box_blur": {"BLUR"},
        "native_gaussian_blur": {"BLUR"},
        "native_smart_blur": {"BILATERAL_BLUR"},
        "native_shape_adaptive_blur": {"BILATERAL_BLUR"},
        "native_edge_preserving_blur": {"BILATERAL_BLUR"},
        "native_directional_blur": {"DIRECTIONAL_BLUR"},
        "native_deband_cleanup": {"BILATERAL_BLUR"},
        "native_gradfun_deband": {"BILATERAL_BLUR"},
        "native_deblock_cleanup": {"ANTI_ALIASING"},
    }
    for tool_id, node_types in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Filter & Blur"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert {node_type for node_type, _settings in tool.compositor_stack} == node_types


def test_native_denoise_and_cleanup_tools_are_exposed():
    expected = {
        "native_hqdn3d_denoise": {"DENOISE"},
        "native_chromanr_cleanup": {"BILATERAL_BLUR"},
        "native_fft_denoise": {"DENOISE"},
        "native_nlmeans_denoise": {"DENOISE"},
        "native_bm3d_denoise": {"DENOISE"},
        "native_wavelet_denoise": {"DENOISE"},
        "native_vague_denoise": {"DENOISE"},
        "native_adaptive_temporal_denoise": {"DENOISE"},
        "native_median_despeckle": {"DESPECKLE"},
        "native_dedot_cleanup": {"DESPECKLE"},
    }
    for tool_id, node_types in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Denoise & Cleanup"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert {node_type for node_type, _settings in tool.compositor_stack} == node_types


def test_native_visual_fx_node_tools_are_exposed():
    expected = {
        "native_compositor_bokeh_blur": "CompositorNodeBokehBlur",
        "native_compositor_defocus": "CompositorNodeDefocus",
        "native_compositor_glare": "CompositorNodeGlare",
        "native_compositor_inpaint": "CompositorNodeInpaint",
        "native_compositor_kuwahara": "CompositorNodeKuwahara",
        "native_compositor_pixelate": "CompositorNodePixelate",
        "native_compositor_vector_blur": "CompositorNodeVecBlur",
    }
    for tool_id, node_type in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Visual FX Nodes"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert tool.compositor_stack[0][0] == "NATIVE_NODE"
        assert tool.compositor_stack[0][1]["node_type"] == node_type


def test_native_analysis_and_utility_node_tools_are_exposed():
    expected = {
        "native_compositor_levels_monitor": "CompositorNodeLevels",
        "native_compositor_image_info": "CompositorNodeImageInfo",
        "native_compositor_split_compare": "CompositorNodeSplit",
        "native_compositor_switch_compare": "CompositorNodeSwitch",
        "native_compositor_cryptomatte": "CompositorNodeCryptomatte",
        "native_compositor_cryptomatte_v2": "CompositorNodeCryptomatteV2",
        "native_compositor_map_uv": "CompositorNodeMapUV",
        "native_compositor_plane_track_deform": "CompositorNodePlaneTrackDeform",
        "native_compositor_z_combine": "CompositorNodeZcombine",
        "native_compositor_sequencer_strip_info": "CompositorNodeSequencerStripInfo",
        "native_compositor_scene_time": "CompositorNodeSceneTime",
        "native_compositor_time": "CompositorNodeTime",
        "native_compositor_track_position": "CompositorNodeTrackPos",
        "native_compositor_image_coordinates": "CompositorNodeImageCoordinates",
        "native_compositor_relative_to_pixel": "CompositorNodeRelativeToPixel",
    }
    for tool_id, node_type in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Analysis & Utility"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert tool.compositor_stack[0][0] == "NATIVE_NODE"
        assert tool.compositor_stack[0][1]["node_type"] == node_type


def test_native_analysis_graphlet_tools_are_exposed():
    expected = {
        "native_compositor_normalize_luma": {"CompositorNodeCombineColor", "CompositorNodeNormalize", "CompositorNodeRGBToBW"},
        "native_ffmpeg_histogram_scope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_temporal_histogram_scope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_waveform_scope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_vectorscope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_cie_scope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_datascope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_oscilloscope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_pixel_scope": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_signal_stats": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
        "native_ffmpeg_color_detect": {
            "CompositorNodeCombineColor",
            "CompositorNodeImageInfo",
            "CompositorNodeLevels",
            "CompositorNodeRGBToBW",
            "CompositorNodeSeparateColor",
            "CompositorNodeViewer",
        },
    }
    for tool_id, node_types in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Analysis & Utility"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert node_types.issubset(_tool_compositor_node_classes(tool_id))


def test_native_source_and_output_tools_are_exposed():
    expected_native = {
        "native_compositor_movie_clip_source": "CompositorNodeMovieClip",
        "native_compositor_viewer_tap": "CompositorNodeViewer",
        "native_compositor_output_file_tap": "CompositorNodeOutputFile",
        "native_compositor_image_source": "CompositorNodeImage",
        "native_compositor_render_layers_source": "CompositorNodeRLayers",
        "native_compositor_normal_source": "CompositorNodeNormal",
        "native_compositor_node_group_placeholder": "CompositorNodeGroup",
        "native_compositor_switch_view": "CompositorNodeSwitchView",
    }
    for tool_id, node_type in expected_native.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Source & Output"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert tool.compositor_stack[0][0] == "NATIVE_NODE"
        assert tool.compositor_stack[0][1]["node_type"] == node_type

    expected_graphlets = {
        "native_compositor_rgb_overlay": {"CompositorNodeAlphaOver", "CompositorNodeRGB"},
        "native_compositor_blank_image_overlay": {"CompositorNodeAlphaOver", "CompositorNodeBlankImage"},
        "native_compositor_text_overlay": {"CompositorNodeAlphaOver", "CompositorNodeStringToImage"},
        "native_compositor_bokeh_image_blur": {"CompositorNodeBokehBlur", "CompositorNodeBokehImage"},
    }
    for tool_id, node_types in expected_graphlets.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Source & Output"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert node_types.issubset(_tool_compositor_node_classes(tool_id))


def test_native_geometry_and_lens_tools_are_exposed():
    expected = {
        "native_compositor_scale_fit": {"SCALE"},
        "native_compositor_center_crop": {"CROP"},
        "native_compositor_rotate_level": {"ROTATE"},
        "native_compositor_transpose_clockwise": {"ROTATE"},
        "native_compositor_flip_horizontal": {"FLIP"},
        "native_compositor_flip_vertical": {"FLIP"},
        "native_compositor_lens_correction": {"LENS_DISTORTION"},
    }
    for tool_id, node_types in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Geometry & Lens"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert {node_type for node_type, _settings in tool.compositor_stack} == node_types


def test_native_geometry_tracking_node_tools_are_exposed():
    expected = {
        "native_compositor_stabilize_node": "CompositorNodeStabilize",
        "native_compositor_movie_distortion_node": "CompositorNodeMovieDistortion",
        "native_compositor_corner_pin": "CompositorNodeCornerPin",
        "native_compositor_displace": "CompositorNodeDisplace",
        "native_compositor_transform": "CompositorNodeTransform",
        "native_compositor_translate": "CompositorNodeTranslate",
    }
    for tool_id, node_type in expected.items():
        tool = get_tool(tool_id)
        assert tool.category == "Native Geometry & Lens"
        assert tool.is_compositor
        assert not tool.is_blender_modifier
        assert not tool.is_ffmpeg
        assert tool.compositor_stack[0][0] == "NATIVE_NODE"
        assert tool.compositor_stack[0][1]["node_type"] == node_type


def test_applicable_tracked_compositor_nodes_have_one_click_tools():
    node_to_tool = {
        "CompositorNodeAlphaOver": "native_compositor_alpha_over",
        "CompositorNodeBlankImage": "native_compositor_blank_image_overlay",
        "CompositorNodeBokehBlur": "native_compositor_bokeh_blur",
        "CompositorNodeBokehImage": "native_compositor_bokeh_image_blur",
        "CompositorNodeBoxMask": "native_compositor_box_mask_alpha",
        "CompositorNodeChannelMatte": "native_compositor_channel_matte",
        "CompositorNodeColorSpill": "native_compositor_color_spill",
        "CompositorNodeCombineColor": "native_compositor_normalize_luma",
        "CompositorNodeConvertColorSpace": "native_compositor_color_space_convert",
        "CompositorNodeConvertToDisplay": "native_compositor_display_convert",
        "CompositorNodeCornerPin": "native_compositor_corner_pin",
        "CompositorNodeCryptomatte": "native_compositor_cryptomatte",
        "CompositorNodeCryptomatteV2": "native_compositor_cryptomatte_v2",
        "CompositorNodeDefocus": "native_compositor_defocus",
        "CompositorNodeDiffMatte": "native_compositor_difference_matte",
        "CompositorNodeDisplace": "native_compositor_displace",
        "CompositorNodeDistanceMatte": "native_compositor_distance_matte",
        "CompositorNodeDoubleEdgeMask": "native_compositor_double_edge_mask_alpha",
        "CompositorNodeEllipseMask": "native_compositor_ellipse_mask_alpha",
        "CompositorNodeGlare": "native_compositor_glare",
        "CompositorNodeGroup": "native_compositor_node_group_placeholder",
        "CompositorNodeIDMask": "native_compositor_id_mask",
        "CompositorNodeImage": "native_compositor_image_source",
        "CompositorNodeImageCoordinates": "native_compositor_image_coordinates",
        "CompositorNodeImageInfo": "native_compositor_image_info",
        "CompositorNodeInpaint": "native_compositor_inpaint",
        "CompositorNodeKeying": "native_compositor_keying",
        "CompositorNodeKeyingScreen": "native_compositor_keying_screen",
        "CompositorNodeKuwahara": "native_compositor_kuwahara",
        "CompositorNodeLevels": "native_compositor_levels_monitor",
        "CompositorNodeMapUV": "native_compositor_map_uv",
        "CompositorNodeMask": "native_compositor_blender_mask_source",
        "CompositorNodeMaskToSDF": "native_compositor_mask_to_sdf_alpha",
        "CompositorNodeMovieClip": "native_compositor_movie_clip_source",
        "CompositorNodeMovieDistortion": "native_compositor_movie_distortion_node",
        "CompositorNodeNormal": "native_compositor_normal_source",
        "CompositorNodeNormalize": "native_compositor_normalize_luma",
        "CompositorNodeOutputFile": "native_compositor_output_file_tap",
        "CompositorNodePixelate": "native_compositor_pixelate",
        "CompositorNodePlaneTrackDeform": "native_compositor_plane_track_deform",
        "CompositorNodeRGB": "native_compositor_rgb_overlay",
        "CompositorNodeRLayers": "native_compositor_render_layers_source",
        "CompositorNodeRelativeToPixel": "native_compositor_relative_to_pixel",
        "CompositorNodeSceneTime": "native_compositor_scene_time",
        "CompositorNodeSequencerStripInfo": "native_compositor_sequencer_strip_info",
        "CompositorNodeSetAlpha": "native_compositor_set_alpha",
        "CompositorNodeSplit": "native_compositor_split_compare",
        "CompositorNodeStringToImage": "native_compositor_text_overlay",
        "CompositorNodeStabilize": "native_compositor_stabilize_node",
        "CompositorNodeSwitch": "native_compositor_switch_compare",
        "CompositorNodeSwitchView": "native_compositor_switch_view",
        "CompositorNodeTime": "native_compositor_time",
        "CompositorNodeTrackPos": "native_compositor_track_position",
        "CompositorNodeTransform": "native_compositor_transform",
        "CompositorNodeTranslate": "native_compositor_translate",
        "CompositorNodeVecBlur": "native_compositor_vector_blur",
        "CompositorNodeViewer": "native_compositor_viewer_tap",
        "CompositorNodeZcombine": "native_compositor_z_combine",
    }
    tracked_nodes = {tool.node_type for tool in compositor_node_tools()}
    assert set(node_to_tool).issubset(tracked_nodes)
    for node_type, tool_id in node_to_tool.items():
        assert node_type in _tool_compositor_node_classes(tool_id)


def test_all_tracked_compositor_nodes_have_one_click_catalog_coverage():
    tracked_nodes = {tool.node_type for tool in compositor_node_tools()}
    catalog_nodes = set()
    for tool in all_tools():
        catalog_nodes.update(_tool_compositor_node_classes(tool.id))
    assert tracked_nodes.issubset(catalog_nodes)


def test_every_native_ffmpeg_compositor_filter_has_one_click_tool():
    filter_to_tool = {
        "chromakey": "native_chroma_key_matte",
        "colorkey": "native_color_key_matte",
        "hsvkey": "native_hsv_key_matte",
        "lumakey": "native_luma_key_matte",
        "despill": "native_despill_color_spill",
        "backgroundkey": "native_background_key_matte",
        "threshold": "native_threshold_matte",
        "maskedthreshold": "native_masked_threshold_matte",
        "blend": "native_blend_overlay_composite",
        "tblend": "native_temporal_blend_ghost",
        "lut2": "native_lut2_expression_mix",
        "tlut2": "native_tlut2_temporal_expression",
        "maskedmerge": "native_masked_merge",
        "mergeplanes": "native_mergeplanes_router",
        "rgbashift": "native_rgba_channel_shift",
        "chromashift": "native_chroma_channel_shift",
        "chromaber_vulkan": "native_chromatic_aberration_offset",
        "alphaextract": "native_alpha_extract",
        "extractplanes": "native_luma_plane_extract",
        "premultiply": "native_premultiply_alpha",
        "unpremultiply": "native_straight_alpha",
        "shuffleplanes": "native_plane_shuffle_bgr",
        "elbg": "native_elbg_posterize",
        "unsharp": "native_unsharp_filter",
        "cas": "native_cas_sharpen",
        "sobel": "native_sobel_edges",
        "prewitt": "native_prewitt_edges",
        "kirsch": "native_kirsch_edges",
        "edgedetect": "native_edge_detect",
        "erosion": "native_erode_matte",
        "dilation": "native_dilate_matte",
        "convolution": "native_convolution_sharpen",
        "fftfilt": "native_fftfilt_detail",
        "avgblur": "native_average_blur",
        "boxblur": "native_box_blur",
        "gblur": "native_gaussian_blur",
        "smartblur": "native_smart_blur",
        "sab": "native_shape_adaptive_blur",
        "yaepblur": "native_edge_preserving_blur",
        "dblur": "native_directional_blur",
        "scale": "native_compositor_scale_fit",
        "crop": "native_compositor_center_crop",
        "rotate": "native_compositor_rotate_level",
        "transpose": "native_compositor_transpose_clockwise",
        "hflip": "native_compositor_flip_horizontal",
        "vflip": "native_compositor_flip_vertical",
        "lenscorrection": "native_compositor_lens_correction",
        "hqdn3d": "native_hqdn3d_denoise",
        "chromanr": "native_chromanr_cleanup",
        "fftdnoiz": "native_fft_denoise",
        "nlmeans": "native_nlmeans_denoise",
        "bm3d": "native_bm3d_denoise",
        "owdenoise": "native_wavelet_denoise",
        "vaguedenoiser": "native_vague_denoise",
        "atadenoise": "native_adaptive_temporal_denoise",
        "median": "native_median_despeckle",
        "dedot": "native_dedot_cleanup",
        "deband": "native_deband_cleanup",
        "gradfun": "native_gradfun_deband",
        "deblock": "native_deblock_cleanup",
        "xbr": "native_xbr_upscale",
        "histogram": "native_ffmpeg_histogram_scope",
        "thistogram": "native_ffmpeg_temporal_histogram_scope",
        "waveform": "native_ffmpeg_waveform_scope",
        "vectorscope": "native_ffmpeg_vectorscope",
        "ciescope": "native_ffmpeg_cie_scope",
        "datascope": "native_ffmpeg_datascope",
        "oscilloscope": "native_ffmpeg_oscilloscope",
        "pixscope": "native_ffmpeg_pixel_scope",
        "signalstats": "native_ffmpeg_signal_stats",
        "colordetect": "native_ffmpeg_color_detect",
    }
    assert set(NATIVE_FFMPEG_COMPOSITOR_FILTERS) == set(filter_to_tool)
    for tool_id in filter_to_tool.values():
        tool = get_tool(tool_id)
        assert tool.is_compositor
        assert tool.compositor_stack


def test_categories_keep_ui_order():
    assert categories() == (
        "Live Blender Color",
        "Native Blender Primitives",
        "Native Color & Composite",
        "Native Matte & Channel",
        "Native Filter & Blur",
        "Native Visual FX Nodes",
        "Native Analysis & Utility",
        "Native Source & Output",
        "Native Denoise & Cleanup",
        "Restoration",
        "Native Geometry & Lens",
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
