from video_toolkit.ffmpeg_native import (
    alphaextract_to_blender_compositor,
    alphamerge_to_blender_compositor,
    backgroundkey_to_blender_compositor,
    blend_to_blender_compositor,
    chromaber_vulkan_to_blender_compositor,
    chromakey_to_blender_compositor,
    colorbalance_to_blender_stack,
    colorchannelmixer_to_blender_stack,
    colormap_to_blender_stack,
    colorkey_to_blender_compositor,
    convolution_to_blender_compositor,
    colorspace_cuda_to_blender_color_management,
    colorlevels_to_blender_stack,
    curves_to_blender_stack,
    despill_to_blender_compositor,
    detection_filter_to_blender_compositor,
    detail_cleanup_filter_to_blender_compositor,
    blur_to_blender_compositor,
    colorcorrect_to_blender_compositor,
    colorcontrast_to_blender_compositor,
    colorhold_to_blender_compositor,
    crop_to_blender_compositor,
    directional_blur_to_blender_compositor,
    edge_filter_to_blender_compositor,
    edge_preserving_blur_to_blender_compositor,
    elbg_to_blender_compositor,
    eq_to_blender_stack,
    exposure_to_blender_compositor,
    exposure_to_blender_stack,
    extractplanes_to_blender_compositor,
    colortemperature_to_blender_compositor,
    colorize_to_blender_compositor,
    geq_to_blender_stack,
    greyedge_to_blender_stack,
    grayworld_to_blender_stack,
    hsvhold_to_blender_compositor,
    huesaturation_to_blender_compositor,
    hue_to_blender_compositor,
    hsvkey_to_blender_compositor,
    identity_to_blender_compositor,
    limiter_to_blender_compositor,
    lumakey_to_blender_compositor,
    lut_file_filter_to_blender_stack,
    lut2_to_blender_compositor,
    lut_to_blender_stack,
    maskedmerge_to_blender_compositor,
    mergeplanes_to_blender_compositor,
    midwayequalizer_to_blender_stack,
    morphology_to_blender_compositor,
    monochrome_to_blender_compositor,
    negate_to_blender_compositor,
    negate_to_blender_stack,
    normalize_to_blender_stack,
    premultiply_to_blender_compositor,
    procamp_vaapi_to_blender_compositor,
    procamp_vaapi_to_blender_stack,
    pseudocolor_to_blender_stack,
    quality_compare_to_blender_compositor,
    restoration_filter_to_blender_compositor,
    flip_to_blender_compositor,
    lenscorrection_to_blender_compositor,
    rotate_to_blender_compositor,
    rgbashift_to_blender_compositor,
    scale_to_blender_compositor,
    selectivecolor_to_blender_stack,
    shuffleplanes_to_blender_compositor,
    scope_filter_to_blender_compositor,
    threshold_to_blender_compositor,
    translate_filter_chain,
    transpose_to_blender_compositor,
    tonemap_to_blender_compositor,
    accelerated_tonemap_to_blender_color_management,
    accelerated_tonemap_to_blender_compositor,
    unpremultiply_to_blender_compositor,
    unsharp_to_blender_compositor,
    vibrance_to_blender_stack,
    zscale_to_blender_color_management,
)


def test_eq_translates_to_native_blender_modifiers():
    stack = eq_to_blender_stack(contrast=1.25, brightness=0.05, saturation=1.4, gamma=1.1)
    types = [modifier_type for modifier_type, _settings in stack]
    assert types == ["BRIGHT_CONTRAST", "COLOR_BALANCE", "HUE_CORRECT", "TONEMAP"]
    assert stack[0][1]["contrast"] == 25.0
    assert stack[2][1]["__hue_correct__"]["saturation"] == 0.7


def test_colorchannelmixer_translates_to_balance_and_white_point():
    stack = colorchannelmixer_to_blender_stack(rr=1.1, gg=1.0, bb=0.9)
    assert [modifier_type for modifier_type, _settings in stack] == ["COLOR_BALANCE", "WHITE_BALANCE"]
    assert stack[0][1]["color_balance.gain"] == (1.1, 1.0, 0.9)


def test_curves_preset_translates_to_curve_points():
    stack = curves_to_blender_stack(preset="strong_contrast")
    assert stack[0][0] == "CURVES"
    points = stack[0][1]["__curve_points__"][0]
    assert points[1][1] < points[1][0]
    assert points[-2][1] > points[-2][0]


def test_colorlevels_translate_to_per_channel_curves():
    stack = colorlevels_to_blender_stack(rimin=0.05, rimax=0.95, romin=0.02, romax=0.98)
    assert stack[0][0] == "CURVES"
    points = stack[0][1]["__curve_points__"]
    assert {1, 2, 3}.issubset(points)
    assert points[1][0] == (0.0, 0.02)


def test_colorbalance_translates_to_lift_gamma_gain():
    stack = colorbalance_to_blender_stack(rs=0.2, bm=0.3, rh=-0.2, pl=1)
    assert stack[0][0] == "COLOR_BALANCE"
    settings = stack[0][1]
    assert settings["color_balance.correction_method"] == "LIFT_GAMMA_GAIN"
    assert settings["color_balance.lift"][0] > settings["color_balance.lift"][1]
    assert settings["color_balance.gamma"][2] > settings["color_balance.gamma"][1]


def test_vibrance_and_exposure_are_live_blender_stacks():
    vibrance = vibrance_to_blender_stack(intensity=0.6)
    assert [modifier_type for modifier_type, _settings in vibrance] == ["HUE_CORRECT", "COLOR_BALANCE"]
    assert vibrance[0][1]["__hue_correct__"]["saturation"] > 0.5

    exposure = exposure_to_blender_stack(exposure=0.5, black=0.05)
    assert [modifier_type for modifier_type, _settings in exposure] == ["BRIGHT_CONTRAST", "CURVES", "TONEMAP"]


def test_grayworld_negate_and_lut_translate_to_live_controls():
    grayworld = grayworld_to_blender_stack()
    assert [modifier_type for modifier_type, _settings in grayworld] == ["WHITE_BALANCE", "COLOR_BALANCE"]

    negate = negate_to_blender_stack(components="r+g+b")
    assert negate[0][0] == "CURVES"
    assert negate[0][1]["__curve_points__"][1] == [(0.0, 1.0), (1.0, 0.0)]
    assert negate[0][1]["__curve_points__"][3] == [(0.0, 1.0), (1.0, 0.0)]

    lut = lut_to_blender_stack(r="negval", g="val*0.8", b="val+16")
    assert lut[0][0] == "CURVES"
    points = lut[0][1]["__curve_points__"]
    assert points[1] == [(0.0, 1.0), (1.0, 0.0)]
    assert points[2][-1][1] == 0.8
    assert points[3][0][1] > 0.0


def test_geq_and_midway_equalizers_translate_to_live_controls():
    geq = geq_to_blender_stack(red_expr="red(X,Y)*1.04", green_expr="g(X,Y)+4", blue_expr="b(X,Y)-6")
    assert geq[0][0] == "CURVES"
    geq_points = geq[0][1]["__curve_points__"]
    assert {1, 2, 3}.issubset(geq_points)
    assert geq_points[1][1][1] > 0.5
    assert geq_points[2][0][1] > 0.0
    assert geq_points[3][1][1] < 0.5

    temporal = midwayequalizer_to_blender_stack("tmidequalizer", radius=9, sigma=0.55, planes=7)
    assert [modifier_type for modifier_type, _settings in temporal] == ["CURVES", "TONEMAP"]
    assert "source" not in temporal[0][1]
    assert temporal[1][1]["contrast"] > 0.0

    result = translate_filter_chain(
        "geq=r='r(X,Y)*1.04':g='g(X,Y)+4':b='b(X,Y)-6',"
        "midequalizer=planes=7,"
        "tmidequalizer=radius=9:sigma=0.55:planes=7"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("geq", "midequalizer", "tmidequalizer")
    sources = [settings["source"] for _node_type, settings in result.compositor_nodes]
    assert sources.count("geq") == 1
    assert sources.count("midequalizer") == 2
    assert sources.count("tmidequalizer") == 2

    unsupported = translate_filter_chain("geq=r='sin(X)'")
    assert unsupported.supported_filters == ()
    assert unsupported.unsupported_filters == ("geq",)


def test_lut_clut_and_colormap_filters_translate_to_live_controls():
    lut1d = lut_file_filter_to_blender_stack("lut1d", file="warm_print.spi1d", interp="cubic")
    assert [modifier_type for modifier_type, _settings in lut1d] == ["CURVES", "COLOR_BALANCE"]
    assert "file" not in lut1d[0][1]
    assert lut1d[1][1]["color_balance.gain"][0] > lut1d[1][1]["color_balance.gain"][2]

    lut3d = lut_file_filter_to_blender_stack("lut3d", file="teal_orange.cube", interp="tetrahedral")
    hald = lut_file_filter_to_blender_stack("haldclut", clut="all", interp="tetrahedral")
    assert [modifier_type for modifier_type, _settings in lut3d] == ["CURVES", "COLOR_BALANCE", "TONEMAP"]
    assert [modifier_type for modifier_type, _settings in hald] == ["CURVES", "COLOR_BALANCE", "TONEMAP"]

    colormap = colormap_to_blender_stack(patch_size="64x64", nb_patches=32, type="absolute", kernel="weuclidean")
    assert [modifier_type for modifier_type, _settings in colormap] == ["HUE_CORRECT", "CURVES", "COLOR_BALANCE"]
    assert {0, 1, 2}.issubset(colormap[0][1]["__curve_points__"])

    result = translate_filter_chain(
        "lut1d=file=warm_print.spi1d:interp=cubic,"
        "lut3d=file=teal_orange.cube:interp=tetrahedral,"
        "haldclut=interp=tetrahedral:clut=all,"
        "colormap=patch_size=64x64:nb_patches=32:type=absolute:kernel=weuclidean"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("lut1d", "lut3d", "haldclut", "colormap")
    sources = [settings["source"] for _node_type, settings in result.compositor_nodes]
    for source in ("lut1d", "lut3d", "haldclut", "colormap"):
        assert source in sources
    assert sources.count("lut1d") == 2
    assert sources.count("lut3d") == 3
    assert sources.count("haldclut") == 3
    assert sources.count("colormap") == 3


def test_greyedge_and_pseudocolor_translate_to_live_controls():
    greyedge = greyedge_to_blender_stack(difford=2, minknorm=5, sigma=3)
    assert [modifier_type for modifier_type, _settings in greyedge] == ["WHITE_BALANCE", "COLOR_BALANCE", "CURVES"]
    assert greyedge[1][1]["color_balance.correction_method"] == "LIFT_GAMMA_GAIN"
    assert greyedge[2][1]["__curve_points__"][0][1][1] < 0.25

    pseudocolor = pseudocolor_to_blender_stack(preset="viridis", opacity=0.75, index=2)
    assert [modifier_type for modifier_type, _settings in pseudocolor] == ["HUE_CORRECT", "CURVES", "COLOR_BALANCE"]
    assert {0, 1, 2}.issubset(pseudocolor[0][1]["__curve_points__"])
    assert pseudocolor[2][1]["color_balance.gamma"][1] != 1.0


def test_normalize_translates_to_live_curves_and_tonemap():
    stack = normalize_to_blender_stack(blackpt="#101020", whitept="#f0f4ff", smoothing=30, independence=0.8, strength=0.7)
    assert [modifier_type for modifier_type, _settings in stack] == ["CURVES", "TONEMAP"]
    points = stack[0][1]["__curve_points__"]
    assert {0, 1, 2, 3}.issubset(points)
    assert points[1][0][1] > 0.0
    assert stack[1][1]["intensity"] > 0.0


def test_selectivecolor_translates_to_hue_zones_and_tonal_balance():
    stack = selectivecolor_to_blender_stack(
        correction_method="relative",
        reds="0.12 -0.08 -0.04 0.00",
        blues="-0.04 0.02 0.12 0.03",
        whites="0.02 0.00 -0.08 0.01",
        neutrals="0.00 -0.04 0.03 0.00",
        blacks="-0.03 0.02 0.00 0.06",
    )
    assert [modifier_type for modifier_type, _settings in stack] == ["HUE_CORRECT", "COLOR_BALANCE"]
    hue_points = stack[0][1]["__curve_points__"]
    assert {0, 1, 2}.issubset(hue_points)
    assert hue_points[1][0][1] != hue_points[1][1][1]
    settings = stack[1][1]
    assert settings["color_balance.correction_method"] == "LIFT_GAMMA_GAIN"
    assert settings["color_balance.gain"][2] > settings["color_balance.gain"][0]


def test_direct_color_filters_translate_to_compositor_nodes():
    hue = hue_to_blender_compositor(h=30, s=1.2, b=0.1)
    assert hue[0][0] == "HUE_SAT"
    assert hue[0][1]["hue"] > 0.5
    assert hue[0][1]["saturation"] == 1.2

    hue_sat = huesaturation_to_blender_compositor(hue=45, saturation=0.25, intensity=0.1, strength=0.8)
    assert hue_sat[0][0] == "HUE_SAT"
    assert hue_sat[0][1]["saturation"] > 1.0
    assert hue_sat[0][1]["factor"] == 0.8

    exposure = exposure_to_blender_compositor(exposure=0.5, black=0.05)
    assert exposure[0][0] == "EXPOSURE"
    assert exposure[0][1]["exposure"] == 0.5

    correction = colorcorrect_to_blender_compositor(rl=0.1, bl=-0.05, rh=0.03, bh=-0.02, saturation=1.08)
    assert correction[0][0] == "COLOR_CORRECTION"
    assert correction[0][1]["saturation"] == 1.08
    assert "approximation" in correction[0][1]

    monochrome = monochrome_to_blender_compositor(cb=0.1, cr=-0.1, high=0.2)
    assert monochrome[0][0] == "HUE_SAT"
    assert monochrome[0][1]["saturation"] == 0.0
    assert monochrome[0][1]["value"] > 1.0

    negate = negate_to_blender_compositor(components="r+g+b", negate_alpha=1)
    assert negate[0][0] == "INVERT"
    assert negate[0][1]["invert_color"] is True
    assert negate[0][1]["invert_alpha"] is True

    result = translate_filter_chain(
        "hue=h=30:s=1.2:b=0.1,"
        "huesaturation=hue=45:saturation=0.25:intensity=0.1:strength=0.8,"
        "exposure=exposure=0.5:black=0.05,"
        "colorcorrect=rl=0.1:bl=-0.05:rh=0.03:bh=-0.02:saturation=1.08,"
        "monochrome=cb=0.1:cr=-0.1:high=0.2,"
        "negate=components=r+g+b:negate_alpha=1"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("hue", "huesaturation", "exposure", "colorcorrect", "monochrome", "negate")
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "HUE_SAT",
        "HUE_SAT",
        "EXPOSURE",
        "COLOR_CORRECTION",
        "HUE_SAT",
        "INVERT",
    ]


def test_direct_pro_color_filters_translate_to_compositor_nodes():
    temperature = colortemperature_to_blender_compositor(temperature=5200, mix=0.7)
    assert [node_type for node_type, _settings in temperature] == ["COLOR_BALANCE", "COLOR_BALANCE"]
    assert temperature[0][1]["source"] == "colortemperature"
    assert "white_value" in temperature[0][1]

    limiter = limiter_to_blender_compositor(min=16, max=235)
    assert limiter[0][0] == "CURVE_RGB"
    assert limiter[0][1]["minimum"] > 0.0
    assert limiter[0][1]["maximum"] < 1.0

    tonemap = tonemap_to_blender_compositor(tonemap="mobius", param=0.35, desat=0.4, peak=400)
    assert [node_type for node_type, _settings in tonemap] == ["TONEMAP", "HUE_CORRECT"]
    assert tonemap[0][1]["tonemap_type"] == "RD_PHOTORECEPTOR"

    procamp_stack = procamp_vaapi_to_blender_stack(brightness=8, contrast=1.2, saturation=1.15, hue=5)
    assert [modifier_type for modifier_type, _settings in procamp_stack] == ["BRIGHT_CONTRAST", "HUE_CORRECT", "COLOR_BALANCE"]
    assert procamp_stack[0][1]["bright"] == 0.08

    procamp_nodes = procamp_vaapi_to_blender_compositor(brightness=8, contrast=1.2, saturation=1.15, hue=5)
    assert [node_type for node_type, _settings in procamp_nodes] == ["BRIGHT_CONTRAST", "HUE_SAT", "COLOR_BALANCE"]
    assert procamp_nodes[1][1]["hue_degrees"] == 5

    opencl_tonemap = accelerated_tonemap_to_blender_compositor(
        "tonemap_opencl",
        tonemap=6,
        param=0.35,
        desat=0.4,
        peak=500,
        transfer="bt709",
        matrix="bt709",
        primaries="bt709",
        range="pc",
    )
    assert [node_type for node_type, _settings in opencl_tonemap] == ["TONEMAP", "HUE_CORRECT"]
    assert opencl_tonemap[0][1]["source"] == "tonemap_opencl"
    assert opencl_tonemap[0][1]["hardware_filter"] == "tonemap_opencl"
    assert ("output_range", "full") in accelerated_tonemap_to_blender_color_management(range="pc")
    assert colorspace_cuda_to_blender_color_management(range="tv") == (("output_range", "limited"),)

    contrast = colorcontrast_to_blender_compositor(rc=0.2, gm=-0.1, by=0.15, rcw=0.6, gmw=0.4, byw=0.5, pl=1)
    assert [node_type for node_type, _settings in contrast] == ["COLOR_BALANCE", "COLOR_BALANCE"]
    assert contrast[0][1]["red_cyan"] == 0.2

    colorize = colorize_to_blender_compositor(hue=210, saturation=0.45, lightness=0.55, mix=0.65)
    assert [node_type for node_type, _settings in colorize] == ["HUE_CORRECT", "COLOR_BALANCE", "COLOR_BALANCE"]
    assert colorize[0][1]["source"] == "colorize"
    assert colorize[0][1]["mix"] == 0.65

    hold = colorhold_to_blender_compositor("colorhold", color="blue", similarity=0.12, blend=0.2)
    assert hold[0][0] == "HUE_CORRECT"
    assert hold[0][1]["source"] == "colorhold"
    assert 1 in hold[0][1]["__curve_points__"]

    hsv_hold = hsvhold_to_blender_compositor(hue=210, similarity=0.10)
    assert hsv_hold[0][0] == "HUE_CORRECT"
    assert hsv_hold[0][1]["hue_degrees"] == 210

    result = translate_filter_chain(
        "colortemperature=temperature=5200:mix=0.7,"
        "limiter=min=16:max=235,"
        "tonemap=tonemap=mobius:param=0.35:desat=0.4,"
        "colorcontrast=rc=0.2:gm=-0.1:by=0.15:rcw=0.6:gmw=0.4:byw=0.5:pl=1,"
        "colorize=hue=210:saturation=0.45:lightness=0.55:mix=0.65,"
        "colorhold=color=blue:similarity=0.12:blend=0.2,"
        "hsvhold=hue=210:similarity=0.10"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "colortemperature",
        "limiter",
        "tonemap",
        "colorcontrast",
        "colorize",
        "colorhold",
        "hsvhold",
    )
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "COLOR_BALANCE",
        "COLOR_BALANCE",
        "CURVE_RGB",
        "TONEMAP",
        "HUE_CORRECT",
        "COLOR_BALANCE",
        "COLOR_BALANCE",
        "HUE_CORRECT",
        "COLOR_BALANCE",
        "COLOR_BALANCE",
        "HUE_CORRECT",
        "HUE_CORRECT",
    ]


def test_ffmpeg_scope_filters_translate_to_blender_diagnostic_graphlets():
    scope = scope_filter_to_blender_compositor("waveform", display="overlay", components=7, intensity=0.8)
    assert scope[0][0] == "SCOPE_MONITOR"
    assert scope[0][1]["scope"] == "waveform"
    assert scope[0][1]["components"] == "7"
    assert scope[0][1]["intensity"] == 0.8

    result = translate_filter_chain(
        "histogram=mode=levels,"
        "thistogram=mode=levels,"
        "waveform=display=overlay:components=7,"
        "vectorscope=mode=color3,"
        "ciescope=system=rec709,"
        "datascope=mode=color2,"
        "oscilloscope=components=7,"
        "pixscope=x=0.55:y=0.45:w=11:h=9:o=0.7,"
        "signalstats=stat=tout+vrep+brng,"
        "colordetect=mode=color_range+alpha_mode+all"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "histogram",
        "thistogram",
        "waveform",
        "vectorscope",
        "ciescope",
        "datascope",
        "oscilloscope",
        "pixscope",
        "signalstats",
        "colordetect",
    )
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["SCOPE_MONITOR"] * 10
    pixscope = result.compositor_nodes[7][1]
    assert pixscope["scope"] == "pixscope"
    assert pixscope["pixel_x"] == 0.55
    assert pixscope["pixel_y"] == 0.45
    assert pixscope["pixel_width"] == 11
    assert pixscope["pixel_height"] == 9
    assert pixscope["window_opacity"] == 0.7


def test_ffmpeg_detection_filters_translate_to_blender_diagnostic_graphlets():
    black = detection_filter_to_blender_compositor("blackdetect", d=1.5, pic_th=0.96, pix_th=0.08)
    assert black[0][0] == "SCOPE_MONITOR"
    assert black[0][1]["scope"] == "blackdetect"
    assert black[0][1]["mode"] == "black_segment"
    assert black[0][1]["threshold"] == 0.08
    assert black[0][1]["duration"] == "1.5"

    blur = detection_filter_to_blender_compositor("blurdetect", high=0.12, low=0.06, radius=40, block_pct=80)
    assert blur[0][1]["scope"] == "blurdetect"
    assert blur[0][1]["high"] == 0.12
    assert blur[0][1]["low"] == 0.06
    assert blur[0][1]["radius"] == 40

    result = translate_filter_chain(
        "blackdetect=d=1.0:pic_th=0.96:pix_th=0.08,"
        "blackdetect_vulkan=d=1.0:pic_th=0.96:pix_th=0.08,"
        "blackframe=amount=96:threshold=28,"
        "blockdetect=period_min=3:period_max=24:planes=1,"
        "blurdetect=high=0.12:low=0.06:radius=40:block_pct=80:planes=1,"
        "cropdetect=limit=0.094:round=16:reset=30:skip=2,"
        "bbox=min_val=16,"
        "bitplanenoise=bitplane=1:filter=1,"
        "freezedetect=n=0.001:d=2,"
        "scdet=threshold=10:sc_pass=0,"
        "scdet_vulkan=threshold=10:sc_pass=0,"
        "vfrdet,"
        "idet=intl_thres=1.04:prog_thres=1.5:rep_thres=3"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "blackdetect",
        "blackdetect_vulkan",
        "blackframe",
        "blockdetect",
        "blurdetect",
        "cropdetect",
        "bbox",
        "bitplanenoise",
        "freezedetect",
        "scdet",
        "scdet_vulkan",
        "vfrdet",
        "idet",
    )
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["SCOPE_MONITOR"] * 13
    assert result.compositor_nodes[5][1]["round"] == 16
    assert result.compositor_nodes[7][1]["bitplane"] == 1
    assert result.compositor_nodes[-1][1]["intl_thres"] == 1.04


def test_identity_filter_translates_to_blender_reference_difference_graphlet():
    identity = identity_to_blender_compositor(eof_action="pass", shortest=1, repeatlast=0, ts_sync_mode="nearest")
    assert identity[0][0] == "IDENTITY_COMPARE"
    assert identity[0][1]["source"] == "identity"
    assert identity[0][1]["reference"] == "selected_strip_derived_branch"
    assert identity[0][1]["eof_action"] == "pass"
    assert identity[0][1]["shortest"] is True
    assert identity[0][1]["repeatlast"] is False
    assert identity[0][1]["ts_sync_mode"] == "nearest"

    result = translate_filter_chain("identity=eof_action=pass:shortest=1:repeatlast=0:ts_sync_mode=nearest")
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("identity",)
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["IDENTITY_COMPARE"]


def test_quality_metric_filters_translate_to_blender_reference_compare_graphlets():
    ssim = quality_compare_to_blender_compositor("ssim", stats_file="ssim.log", eof_action="pass", shortest=1)
    assert ssim[0][0] == "QUALITY_COMPARE"
    assert ssim[0][1]["source"] == "ssim"
    assert ssim[0][1]["metric_mode"] == "structure_similarity"
    assert ssim[0][1]["stats_file"] == "ssim.log"
    assert ssim[0][1]["shortest"] is True
    assert ssim[0][1]["eof_action"] == "pass"

    psnr = quality_compare_to_blender_compositor("psnr", f="psnr.log", stats_version=2, output_max=1)
    assert psnr[0][1]["metric_mode"] == "peak_error"
    assert psnr[0][1]["stats_file"] == "psnr.log"
    assert psnr[0][1]["stats_version"] == 2
    assert psnr[0][1]["output_max"] is True

    xcorrelate = quality_compare_to_blender_compositor("xcorrelate", planes=3, secondary="first")
    assert xcorrelate[0][1]["metric_mode"] == "cross_correlation"
    assert xcorrelate[0][1]["planes"] == "3"
    assert xcorrelate[0][1]["secondary"] == "first"

    result = translate_filter_chain(
        "ssim=stats_file=ssim.log,"
        "psnr=f=psnr.log:stats_version=2:output_max=1,"
        "xpsnr=stats_file=xpsnr.log,"
        "corr,"
        "msad,"
        "xcorrelate=planes=7:secondary=all"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("ssim", "psnr", "xpsnr", "corr", "msad", "xcorrelate")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["QUALITY_COMPARE"] * 6


def test_remaining_live_color_filters_emit_compositor_node_specs():
    result = translate_filter_chain(
        "eq=contrast=1.2:saturation=1.3:gamma=1.05,"
        "colorchannelmixer=rr=1.1:gg=1.0:bb=0.9,"
        "curves=preset=strong_contrast,"
        "colorlevels=rimin=0.02:rimax=0.98,"
        "colorbalance=rs=0.1:bm=0.2:bh=-0.1,"
        "vibrance=intensity=0.4,"
        "normalize=smoothing=18:independence=0.65:strength=0.55,"
        "selectivecolor=reds=0.10 -0.04 -0.02 0.00:blues=-0.04 0.02 0.10 0.03,"
        "grayworld,"
        "greyedge=difford=2:minknorm=5:sigma=2,"
        "pseudocolor=preset=viridis:opacity=0.75:index=1,"
        "lut1d=file=warm_print.spi1d:interp=cubic,"
        "lut3d=file=teal_orange.cube:interp=tetrahedral,"
        "haldclut=interp=tetrahedral:clut=all,"
        "colormap=patch_size=64x64:nb_patches=32:type=absolute:kernel=weuclidean,"
        "geq=r='r(X,Y)*1.04':g='g(X,Y)+4':b='b(X,Y)-6',"
        "lutrgb=r=negval:g=val*0.9:b=val+12,"
        "histeq=strength=0.35:intensity=0.25:antibanding=1,"
        "midequalizer=planes=7,"
        "tmidequalizer=radius=9:sigma=0.55:planes=7"
    )
    assert result.unsupported_filters == ()
    sources = [settings["source"] for _node_type, settings in result.compositor_nodes]
    for source in (
        "eq",
        "colorchannelmixer",
        "curves",
        "colorlevels",
        "colorbalance",
        "vibrance",
        "normalize",
        "selectivecolor",
        "grayworld",
        "greyedge",
        "pseudocolor",
        "lut1d",
        "lut3d",
        "haldclut",
        "colormap",
        "geq",
        "lutrgb",
        "histeq",
        "midequalizer",
        "tmidequalizer",
    ):
        assert source in sources
    node_types = {node_type for node_type, _settings in result.compositor_nodes}
    assert {"BRIGHT_CONTRAST", "COLOR_BALANCE", "CURVE_RGB", "HUE_CORRECT", "TONEMAP"}.issubset(node_types)
    assert sources.count("lut1d") == 2
    assert sources.count("lut3d") == 3
    assert sources.count("haldclut") == 3
    assert sources.count("colormap") == 3
    assert sources.count("lutrgb") == 1


def test_filter_chain_reports_non_native_filters():
    result = translate_filter_chain(
        "normalize=smoothing=30,eq=contrast=1.08:saturation=1.1:gamma=1.02,unsharp=5:5:0.45,hqdn3d=1.5:1.5:6:6,tmix=frames=5"
    )
    assert "normalize" in result.supported_filters
    assert "eq" in result.supported_filters
    assert "unsharp" in result.supported_filters
    assert "hqdn3d" in result.supported_filters
    assert "tmix" in result.supported_filters
    assert result.unsupported_filters == ()
    assert [modifier_type for modifier_type, _settings in result.stack][:5] == [
        "CURVES",
        "TONEMAP",
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "HUE_CORRECT",
    ]
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "CURVE_RGB",
        "TONEMAP",
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "HUE_CORRECT",
        "TONEMAP",
        "FILTER",
        "DENOISE",
        "BLUR",
        "BLEND_COMPOSITE",
    ]


def test_temporal_motion_filters_translate_to_blender_graphlets():
    result = translate_filter_chain(
        "deflicker=s=12:m=median,"
        "bwdif=mode=send_frame:parity=auto:deint=all,"
        "bwdif_cuda=mode=send_frame:parity=auto:deint=all,"
        "bwdif_vulkan=mode=send_frame:parity=auto:deint=all,"
        "yadif=mode=send_field:parity=tff:deint=interlaced,"
        "yadif_cuda=mode=send_field:parity=tff:deint=interlaced,"
        "estdif=mode=send_frame:parity=auto:deint=all,"
        "w3fdif=mode=send_frame:parity=auto:deint=all,"
        "deinterlace_qsv=mode=send_frame:parity=auto:deint=all,"
        "deinterlace_vaapi=mode=send_frame:parity=auto:deint=all,"
        "deshake=rx=16:ry=12,"
        "deshake_opencl=rx=18:ry=14,"
        "vidstabdetect=shakiness=6:accuracy=12:result=motion.trf,"
        "vidstabtransform=input=motion.trf:smoothing=24:zoom=2,"
        "tmix=frames=5:weights='1 2 3 2 1',"
        "fps=fps=24:round=near,"
        "framerate=fps=48,"
        "minterpolate=fps=60:mi_mode=mci"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "deflicker",
        "bwdif",
        "bwdif_cuda",
        "bwdif_vulkan",
        "yadif",
        "yadif_cuda",
        "estdif",
        "w3fdif",
        "deinterlace_qsv",
        "deinterlace_vaapi",
        "deshake",
        "deshake_opencl",
        "vidstabdetect",
        "vidstabtransform",
        "tmix",
        "fps",
        "framerate",
        "minterpolate",
    )
    node_types = [node_type for node_type, _settings in result.compositor_nodes]
    assert "TONEMAP" in node_types
    assert node_types.count("ANTI_ALIASING") == 9
    assert node_types.count("NATIVE_NODE") >= 4
    assert "BLEND_COMPOSITE" in node_types
    assert node_types[-3:] == ["DIRECTIONAL_BLUR", "DIRECTIONAL_BLUR", "DIRECTIONAL_BLUR"]
    deinterlace_sources = {
        settings["source"]
        for node_type, settings in result.compositor_nodes
        if node_type == "ANTI_ALIASING"
    }
    assert {
        "bwdif",
        "bwdif_cuda",
        "bwdif_vulkan",
        "yadif",
        "yadif_cuda",
        "estdif",
        "w3fdif",
        "deinterlace_qsv",
        "deinterlace_vaapi",
    }.issubset(deinterlace_sources)
    tmix = next(settings for node_type, settings in result.compositor_nodes if node_type == "BLEND_COMPOSITE" and settings["source"] == "tmix")
    assert tmix["frames"] == 5
    assert tmix["factor"] == 3 / 9
    deshake = next(settings for node_type, settings in result.compositor_nodes if node_type == "NATIVE_NODE" and settings["source"] == "deshake")
    assert deshake["metadata"]["rx"] == 16
    assert deshake["metadata"]["ry"] == 12
    opencl_deshake = next(settings for node_type, settings in result.compositor_nodes if node_type == "NATIVE_NODE" and settings["source"] == "deshake_opencl")
    assert opencl_deshake["metadata"]["hardware_filter"] == "deshake_opencl"
    minterpolate = result.compositor_nodes[-1][1]
    assert minterpolate["source"] == "minterpolate"
    assert minterpolate["fps"] == 60


def test_filter_chain_supports_color_space_metadata():
    result = translate_filter_chain(
        "colorspace=iall=bt709:all=bt2020:irange=tv:range=pc,"
        "colormatrix=src=smpte170m:dst=bt709,"
        "setparams=color_primaries=bt2020:color_trc=bt2020-10:colorspace=bt2020nc:range=full,"
        "setrange=limited,"
        "zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("colorspace", "colormatrix", "setparams", "setrange", "zscale")
    assert ("sequencer_input", "bt709") in result.color_management
    assert ("output_matrix", "bt2020") in result.color_management
    assert ("output_transfer", "bt2020-10") in result.color_management
    assert ("output_range", "limited") in result.color_management
    assert ("input_range", "limited") in result.color_management


def test_zscale_metadata_translates_to_blender_color_management():
    pairs = zscale_to_blender_color_management(
        primariesin="bt709",
        transferin="bt709",
        matrixin="bt709",
        rangein="limited",
        primaries="bt2020",
        transfer="bt2020-10",
        matrix="bt2020nc",
        range="full",
    )
    assert ("sequencer_input", "bt709") in pairs
    assert ("input_matrix", "bt709") in pairs
    assert ("output_matrix", "bt2020") in pairs
    assert ("output_primaries", "bt2020") in pairs
    assert ("output_transfer", "bt2020-10") in pairs
    assert ("input_range", "limited") in pairs
    assert ("output_range", "full") in pairs


def test_key_filters_translate_to_compositor_only_nodes():
    chroma = chromakey_to_blender_compositor(color="green", similarity=0.12, blend=0.04)
    assert chroma[0][0] == "CHROMA_MATTE"
    assert chroma[0][1]["key_color"] == (0.0, 1.0, 0.0)

    color = colorkey_to_blender_compositor(color="blue", similarity=0.10, blend=0.03)
    assert color[0][0] == "COLOR_MATTE"
    assert color[0][1]["key_color"] == (0.0, 0.0, 1.0)

    hsv = hsvkey_to_blender_compositor(hue=210, sat=0.75, val=0.85, similarity=0.10, blend=0.02)
    assert hsv[0][0] == "COLOR_MATTE"
    assert hsv[0][1]["key_color"][2] > hsv[0][1]["key_color"][0]

    luma = lumakey_to_blender_compositor(threshold=0.20, tolerance=0.08, softness=0.02)
    assert luma[0][0] == "LUMA_MATTE"
    assert luma[0][1]["minimum"] < 0.20 < luma[0][1]["maximum"]

    despill = despill_to_blender_compositor(type="blue", mix=0.65, expand=0.2, blue=-1.2, brightness=0.1, alpha=True)
    assert despill[0][0] == "COLOR_SPILL"
    assert despill[0][1]["spill_channel"] == "Blue"
    assert despill[0][1]["factor"] == 0.65
    assert despill[0][1]["limit_strength"] == 0.2
    assert despill[0][1]["alpha"] is True

    background = backgroundkey_to_blender_compositor(threshold=0.08, similarity=0.12, blend=0.04)
    assert background[0][0] == "BACKGROUND_KEY"
    assert background[0][1]["tolerance"] == 0.12
    assert background[0][1]["falloff"] > 0.04
    assert background[0][1]["blur_size"] >= 6

    threshold = threshold_to_blender_compositor("threshold", planes=7)
    masked_threshold = threshold_to_blender_compositor("maskedthreshold", threshold=2048, planes=7, mode="abs")
    assert threshold[0][0] == "LUMA_MATTE"
    assert threshold[0][1]["minimum"] < 0.5 < threshold[0][1]["maximum"]
    assert masked_threshold[0][0] == "LUMA_MATTE"
    assert masked_threshold[0][1]["source"] == "maskedthreshold"
    assert masked_threshold[0][1]["mode"] == "abs"

    result = translate_filter_chain(
        "chromakey=color=green:similarity=0.12:blend=0.04,"
        "colorkey=color=blue:similarity=0.10:blend=0.03,"
        "hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.10:blend=0.02,"
        "lumakey=threshold=0.20:tolerance=0.08:softness=0.02,"
        "despill=type=green:mix=0.65:expand=0.12:green=-1.0,"
        "backgroundkey=threshold=0.08:similarity=0.12:blend=0.04,"
        "threshold=planes=7,"
        "maskedthreshold=threshold=2048:planes=7:mode=abs"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("chromakey", "colorkey", "hsvkey", "lumakey", "despill", "backgroundkey", "threshold", "maskedthreshold")
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "CHROMA_MATTE",
        "COLOR_MATTE",
        "COLOR_MATTE",
        "LUMA_MATTE",
        "COLOR_SPILL",
        "BACKGROUND_KEY",
        "LUMA_MATTE",
        "LUMA_MATTE",
    ]


def test_blend_lut2_maskedmerge_and_mergeplanes_translate_to_native_graph_specs():
    blend = blend_to_blender_compositor("blend", all_mode="overlay", all_opacity=0.35)
    assert blend[0][0] == "BLEND_COMPOSITE"
    assert blend[0][1]["mode"] == "overlay"
    assert blend[0][1]["factor"] == 0.35

    temporal = blend_to_blender_compositor("tblend", all_mode="average", all_opacity=0.45)
    assert temporal[0][0] == "BLEND_COMPOSITE"
    assert temporal[0][1]["temporal"] is True

    lut2 = lut2_to_blender_compositor(c0="(x+y)/2", c1="(x+y)/2", c2="(x+y)/2", c3="x")
    assert lut2[0][0] == "BLEND_COMPOSITE"
    assert lut2[0][1]["source"] == "lut2"
    assert lut2[0][1]["factor"] == 0.5
    assert lut2[0][1]["expressions"][0] == "(x+y)/2"

    tlut2 = lut2_to_blender_compositor(source="tlut2", c0="(x+y)/2", c1="(x+y)/2", c2="(x+y)/2", c3="x")
    assert tlut2[0][0] == "BLEND_COMPOSITE"
    assert tlut2[0][1]["source"] == "tlut2"
    assert tlut2[0][1]["temporal"] is True

    masked = maskedmerge_to_blender_compositor(planes=15)
    assert masked[0][0] == "MASKED_BLEND_COMPOSITE"
    assert masked[0][1]["source"] == "maskedmerge"
    assert masked[0][1]["planes"] == "15"

    merged = mergeplanes_to_blender_compositor(map0p=2, map1p=1, map2p=0, map3p=3)
    assert merged[0][0] == "PLANE_SHUFFLE"
    assert merged[0][1]["source"] == "mergeplanes"
    assert merged[0][1]["outputs"] == {"red": "blue", "green": "green", "blue": "red", "alpha": "alpha"}

    result = translate_filter_chain(
        "blend=all_mode=overlay:all_opacity=0.35,"
        "tblend=all_mode=average:all_opacity=0.45,"
        "lut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
        "tlut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
        "maskedmerge=planes=15,"
        "mergeplanes=map0p=2:map1p=1:map2p=0:map3p=3"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("blend", "tblend", "lut2", "tlut2", "maskedmerge", "mergeplanes")
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "BLEND_COMPOSITE",
        "BLEND_COMPOSITE",
        "BLEND_COMPOSITE",
        "BLEND_COMPOSITE",
        "MASKED_BLEND_COMPOSITE",
        "PLANE_SHUFFLE",
    ]


def test_channel_shift_filters_translate_to_compositor_graph_specs():
    rgba = rgbashift_to_blender_compositor(rh=4, rv=-2, gh=0, gv=1, bh=-3, bv=2, ah=1, av=0)
    assert rgba[0][0] == "CHANNEL_SHIFT"
    assert rgba[0][1]["offsets"]["red"] == (4.0, -2.0)
    assert rgba[0][1]["offsets"]["blue"] == (-3.0, 2.0)
    assert rgba[0][1]["offsets"]["alpha"] == (1.0, 0.0)

    result = translate_filter_chain("rgbashift=rh=4:rv=-2:bh=-3:bv=2,chromashift=cbh=2:cbv=-1:crh=-2:crv=1")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("rgbashift", "chromashift")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["CHANNEL_SHIFT", "CHANNEL_SHIFT"]
    assert result.compositor_nodes[1][1]["offsets"]["red"] == (-2.0, 1.0)
    assert result.compositor_nodes[1][1]["offsets"]["blue"] == (2.0, -1.0)

    chromaber = chromaber_vulkan_to_blender_compositor(dist_x=2.0, dist_y=-1.0)
    assert chromaber[0][0] == "CHANNEL_SHIFT"
    assert chromaber[0][1]["source"] == "chromaber_vulkan"
    assert chromaber[0][1]["offsets"]["red"] == (6.0, -3.0)
    assert chromaber[0][1]["offsets"]["blue"] == (-6.0, 3.0)

    result = translate_filter_chain(
        "rgbashift=rh=4:rv=-2:bh=-3:bv=2,"
        "chromashift=cbh=2:cbv=-1:crh=-2:crv=1,"
        "chromaber_vulkan=dist_x=2.0:dist_y=-1.0"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("rgbashift", "chromashift", "chromaber_vulkan")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["CHANNEL_SHIFT", "CHANNEL_SHIFT", "CHANNEL_SHIFT"]


def test_alpha_and_plane_extract_translate_to_compositor_graph_specs():
    alpha = alphaextract_to_blender_compositor()
    assert alpha == (("PLANE_EXTRACT", {"plane": "alpha", "source": "alphaextract"}),)

    merged_alpha = alphamerge_to_blender_compositor()
    assert merged_alpha[0][0] == "ALPHA_MERGE"
    assert merged_alpha[0][1]["source"] == "alphamerge"
    assert merged_alpha[0][1]["alpha_source"] == "luma"

    luma = extractplanes_to_blender_compositor(planes="y")
    assert luma == (("PLANE_EXTRACT", {"plane": "y", "source": "extractplanes"}),)

    first_multi = extractplanes_to_blender_compositor(planes="g+b")
    assert first_multi[0][1]["plane"] == "g"

    result = translate_filter_chain("alphaextract,alphamerge,extractplanes=planes=y")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("alphaextract", "alphamerge", "extractplanes")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["PLANE_EXTRACT", "ALPHA_MERGE", "PLANE_EXTRACT"]
    assert [settings.get("plane") for _node_type, settings in result.compositor_nodes] == ["alpha", None, "y"]


def test_alpha_premultiply_filters_translate_to_premul_key_nodes():
    premul = premultiply_to_blender_compositor()
    assert premul == (("PREMUL_KEY", {"mode": "To Premultiplied", "source": "premultiply"}),)

    straight = unpremultiply_to_blender_compositor()
    assert straight == (("PREMUL_KEY", {"mode": "To Straight", "source": "unpremultiply"}),)

    result = translate_filter_chain("premultiply,unpremultiply")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("premultiply", "unpremultiply")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["PREMUL_KEY", "PREMUL_KEY"]
    assert [settings["mode"] for _node_type, settings in result.compositor_nodes] == ["To Premultiplied", "To Straight"]


def test_shuffleplanes_translates_to_plane_shuffle_graph_specs():
    shuffle = shuffleplanes_to_blender_compositor(map0=2, map1=1, map2=0, map3=3)
    assert shuffle == (
        (
            "PLANE_SHUFFLE",
            {
                "outputs": {"red": "blue", "green": "green", "blue": "red", "alpha": "alpha"},
                "source": "shuffleplanes",
            },
        ),
    )

    result = translate_filter_chain("shuffleplanes=2:1:0:3,shuffleplanes=map0=1:map1=2:map2=0:map3=3")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("shuffleplanes", "shuffleplanes")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["PLANE_SHUFFLE", "PLANE_SHUFFLE"]
    assert result.compositor_nodes[0][1]["outputs"]["red"] == "blue"
    assert result.compositor_nodes[1][1]["outputs"]["green"] == "blue"


def test_elbg_translates_to_posterize_graph_specs():
    posterize = elbg_to_blender_compositor(l=64, n=3, seed=17, use_alpha=0)
    assert posterize == (
        (
            "POSTERIZE",
            {
                "steps": 4.0,
                "codebook_length": 64,
                "nb_steps": 3,
                "seed": 17,
                "pal8": False,
                "use_alpha": False,
                "source": "elbg",
            },
        ),
    )

    result = translate_filter_chain("elbg=64:2:17,elbg=codebook_length=81:nb_steps=4:use_alpha=1")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("elbg", "elbg")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["POSTERIZE", "POSTERIZE"]
    assert result.compositor_nodes[0][1]["steps"] == 4.0
    assert result.compositor_nodes[1][1]["steps"] == 3.0
    assert result.compositor_nodes[1][1]["use_alpha"] is True


def test_unsharp_translates_to_native_filter_graph_specs():
    sharpen = unsharp_to_blender_compositor(lx=7, ly=5, la=0.8, cx=3, cy=3, ca=0.2)
    assert sharpen[0][0] == "FILTER"
    sharpen_settings = sharpen[0][1]
    assert sharpen_settings["filter_type"] == "Box Sharpen"
    assert sharpen_settings["factor"] > 0.8
    assert sharpen_settings["luma_size"] == (7, 5)
    assert sharpen_settings["chroma_amount"] == 0.2

    soften = unsharp_to_blender_compositor(arg0=5, arg1=5, arg2=-0.6)
    assert soften[0][1]["filter_type"] == "Soften"
    assert soften[0][1]["factor"] == 0.6

    opencl = unsharp_to_blender_compositor(source="unsharp_opencl", lx=7, ly=5, la=0.8)
    assert opencl[0][0] == "FILTER"
    assert opencl[0][1]["source"] == "unsharp_opencl"
    assert opencl[0][1]["hardware_filter"] == "unsharp_opencl"

    result = translate_filter_chain("unsharp=5:5:0.45:3:3:0.20,unsharp=lx=7:ly=7:la=-0.40,unsharp_opencl=lx=7:ly=5:la=0.80")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("unsharp", "unsharp", "unsharp_opencl")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["FILTER", "FILTER", "FILTER"]
    assert result.compositor_nodes[0][1]["filter_type"] == "Box Sharpen"
    assert result.compositor_nodes[1][1]["filter_type"] == "Soften"
    assert result.compositor_nodes[2][1]["source"] == "unsharp_opencl"


def test_edge_filters_translate_to_native_filter_graph_specs():
    sobel = edge_filter_to_blender_compositor("sobel", scale=1.2, delta=0.02)
    assert sobel[0][0] == "FILTER"
    assert sobel[0][1]["filter_type"] == "Sobel"
    assert sobel[0][1]["factor"] > 1.19

    prewitt = edge_filter_to_blender_compositor("prewitt", scale=0.9)
    opencl_sobel = edge_filter_to_blender_compositor("sobel_opencl", scale=1.1)
    opencl_prewitt = edge_filter_to_blender_compositor("prewitt_opencl", scale=0.9)
    opencl_roberts = edge_filter_to_blender_compositor("roberts_opencl", scale=0.9)
    kirsch = edge_filter_to_blender_compositor("kirsch", scale=0.8)
    edgedetect = edge_filter_to_blender_compositor("edgedetect", high=0.20, low=0.08, mode="wires")
    assert prewitt[0][1]["filter_type"] == "Prewitt"
    assert opencl_sobel[0][1]["hardware_filter"] == "sobel_opencl"
    assert opencl_prewitt[0][1]["filter_type"] == "Prewitt"
    assert opencl_roberts[0][1]["source"] == "roberts_opencl"
    assert opencl_roberts[0][1]["filter_type"] == "Sobel"
    assert kirsch[0][1]["filter_type"] == "Kirsch"
    assert edgedetect[0][1]["filter_type"] == "Sobel"
    assert edgedetect[0][1]["label"] == "Edge Detect"

    result = translate_filter_chain(
        "sobel=scale=1.2:delta=0.02,"
        "sobel_opencl=scale=1.1,"
        "prewitt=scale=0.9,"
        "prewitt_opencl=scale=0.9,"
        "roberts_opencl=scale=0.9,"
        "kirsch=scale=0.8,"
        "edgedetect=high=0.20:low=0.08:mode=wires"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("sobel", "sobel_opencl", "prewitt", "prewitt_opencl", "roberts_opencl", "kirsch", "edgedetect")
    assert [settings["filter_type"] for _node_type, settings in result.compositor_nodes] == ["Sobel", "Sobel", "Prewitt", "Prewitt", "Sobel", "Kirsch", "Sobel"]
    assert [settings["source"] for _node_type, settings in result.compositor_nodes] == ["sobel", "sobel_opencl", "prewitt", "prewitt_opencl", "roberts_opencl", "kirsch", "edgedetect"]


def test_morphology_filters_translate_to_dilate_erode_graph_specs():
    erosion = morphology_to_blender_compositor("erosion", coordinates=255, threshold0=64000)
    dilation = morphology_to_blender_compositor("dilation", coordinates=255, threshold0=64000)
    opencl_erosion = morphology_to_blender_compositor("erosion_opencl", coordinates=255, threshold0=64000)
    opencl_dilation = morphology_to_blender_compositor("dilation_opencl", coordinates=255, threshold0=64000)
    assert erosion[0][0] == "DILATE_ERODE"
    assert dilation[0][0] == "DILATE_ERODE"
    assert opencl_erosion[0][1]["hardware_filter"] == "erosion_opencl"
    assert opencl_dilation[0][1]["hardware_filter"] == "dilation_opencl"
    assert erosion[0][1]["size"] == -1
    assert dilation[0][1]["size"] == 1
    assert erosion[0][1]["thresholds"][0] == 64000
    assert dilation[0][1]["label"] == "Dilate"

    result = translate_filter_chain(
        "erosion=coordinates=255:threshold0=64000:threshold1=64000,"
        "erosion_opencl=coordinates=255:threshold0=64000:threshold1=64000,"
        "dilation=coordinates=15:threshold2=32000,"
        "dilation_opencl=coordinates=15:threshold2=32000"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("erosion", "erosion_opencl", "dilation", "dilation_opencl")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["DILATE_ERODE", "DILATE_ERODE", "DILATE_ERODE", "DILATE_ERODE"]
    assert result.compositor_nodes[0][1]["source"] == "erosion"
    assert result.compositor_nodes[1][1]["source"] == "erosion_opencl"
    assert result.compositor_nodes[2][1]["source"] == "dilation"
    assert result.compositor_nodes[3][1]["source"] == "dilation_opencl"


def test_convolution_translates_to_native_convolve_graph_specs():
    sharpen = convolution_to_blender_compositor(
        **{
            "0m": "0 -1 0 -1 5 -1 0 -1 0",
            "0rdiv": 1,
            "0bias": 0,
        }
    )
    assert sharpen[0][0] == "CONVOLVE"
    sharpen_settings = sharpen[0][1]
    assert sharpen_settings["kernel_size"] == (3, 3)
    assert sharpen_settings["kernel"] == (0.0, -1.0, 0.0, -1.0, 5.0, -1.0, 0.0, -1.0, 0.0)
    assert sharpen_settings["kernel_channels"]["red"] == sharpen_settings["kernel_channels"]["green"]
    assert sharpen_settings["rdiv"] == 1.0
    assert sharpen_settings["bias"] == 0.0

    blur = convolution_to_blender_compositor(**{"0m": "1 1 1 1 1 1 1 1 1"})
    assert blur[0][1]["kernel"][0] == 1.0 / 9.0
    assert blur[0][1]["kernel"][4] == 1.0 / 9.0

    row = convolution_to_blender_compositor(**{"0m": "-1 2 -1", "0mode": "row", "0bias": 16})
    assert row[0][1]["kernel_size"] == (3, 1)
    assert row[0][1]["mode"] == "row"
    assert row[0][1]["bias"] > 0.06

    result = translate_filter_chain("convolution=0m='0 -1 0 -1 5 -1 0 -1 0':0rdiv=1:0bias=0")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("convolution",)
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["CONVOLVE"]


def test_blur_filters_translate_to_native_blender_blur_nodes():
    avg = blur_to_blender_compositor("avgblur", sizeX=4, sizeY=6)
    assert avg[0][0] == "BLUR"
    assert avg[0][1]["blur_type"] == "Flat"
    assert avg[0][1]["size"] == (4.0, 6.0)

    box = blur_to_blender_compositor("boxblur", lr=3, lp=2)
    assert box[0][1]["label"] == "Box Blur"
    assert box[0][1]["size"] == (6.0, 6.0)

    gaussian = blur_to_blender_compositor("gblur", sigma=1.2, steps=2, sigmaV=0.8)
    assert gaussian[0][1]["blur_type"] == "Gaussian"
    assert gaussian[0][1]["size"][0] > gaussian[0][1]["size"][1]

    opencl_average = blur_to_blender_compositor("avgblur_opencl", sizeX=4, sizeY=6)
    vulkan_average = blur_to_blender_compositor("avgblur_vulkan", sizeX=4, sizeY=6)
    opencl_box = blur_to_blender_compositor("boxblur_opencl", lr=3, lp=2)
    vulkan_gaussian = blur_to_blender_compositor("gblur_vulkan", sigma=1.2, steps=2, sigmaV=0.8)
    assert [item[0][0] for item in (opencl_average, vulkan_average, opencl_box, vulkan_gaussian)] == ["BLUR"] * 4
    assert opencl_average[0][1]["source"] == "avgblur_opencl"
    assert vulkan_average[0][1]["source"] == "avgblur_vulkan"
    assert opencl_box[0][1]["source"] == "boxblur_opencl"
    assert vulkan_gaussian[0][1]["source"] == "gblur_vulkan"

    bilateral = edge_preserving_blur_to_blender_compositor("bilateral", sigmaS=3, sigmaR=0.12)
    cuda_bilateral = edge_preserving_blur_to_blender_compositor("bilateral_cuda", sigmaS=3, sigmaR=0.12)
    smart = edge_preserving_blur_to_blender_compositor("smartblur", lr=2.0, ls=0.8, lt=8)
    assert smart[0][0] == "BILATERAL_BLUR"
    assert bilateral[0][1]["source"] == "bilateral"
    assert cuda_bilateral[0][1]["hardware_filter"] == "bilateral_cuda"
    assert smart[0][1]["size"] >= 1
    assert smart[0][1]["threshold"] > 0.05

    sab = edge_preserving_blur_to_blender_compositor("sab", lr=2.0, lpfr=1.0, ls=12)
    yaep = edge_preserving_blur_to_blender_compositor("yaepblur", r=4, s=192)
    assert sab[0][1]["label"] == "Shape Adaptive Blur"
    assert yaep[0][1]["label"] == "Edge Preserving Blur"
    assert yaep[0][1]["threshold"] > sab[0][1]["threshold"]

    directional = directional_blur_to_blender_compositor(angle=30, radius=12)
    assert directional[0][0] == "DIRECTIONAL_BLUR"
    assert directional[0][1]["samples"] == 24
    assert 0.52 < directional[0][1]["direction"] < 0.53

    result = translate_filter_chain(
        "avgblur=sizeX=4:sizeY=6,"
        "avgblur_opencl=sizeX=4:sizeY=6,"
        "avgblur_vulkan=sizeX=4:sizeY=6,"
        "boxblur=lr=3:lp=2,"
        "boxblur_opencl=lr=3:lp=2,"
        "gblur=sigma=1.2:steps=2:sigmaV=0.8,"
        "gblur_vulkan=sigma=1.2:steps=2:sigmaV=0.8,"
        "bilateral=sigmaS=3:sigmaR=0.12,"
        "bilateral_cuda=sigmaS=3:sigmaR=0.12,"
        "smartblur=lr=2:ls=0.8:lt=8,"
        "sab=lr=2:lpfr=1:ls=12,"
        "yaepblur=r=4:s=192,"
        "dblur=angle=30:radius=12"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "avgblur",
        "avgblur_opencl",
        "avgblur_vulkan",
        "boxblur",
        "boxblur_opencl",
        "gblur",
        "gblur_vulkan",
        "bilateral",
        "bilateral_cuda",
        "smartblur",
        "sab",
        "yaepblur",
        "dblur",
    )
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "BLUR",
        "BLUR",
        "BLUR",
        "BLUR",
        "BLUR",
        "BLUR",
        "BLUR",
        "BILATERAL_BLUR",
        "BILATERAL_BLUR",
        "BILATERAL_BLUR",
        "BILATERAL_BLUR",
        "BILATERAL_BLUR",
        "DIRECTIONAL_BLUR",
    ]


def test_geometry_filters_translate_to_native_blender_nodes():
    scale = scale_to_blender_compositor(arg0=960, arg1=540)
    assert scale[0][0] == "SCALE"
    assert scale[0][1]["type"] == "Absolute"
    assert scale[0][1]["x"] == 960.0
    assert scale[0][1]["y"] == 540.0

    relative = scale_to_blender_compositor(arg0="iw*0.5", arg1="ih/2")
    assert relative[0][1]["type"] == "Relative"
    assert relative[0][1]["x"] == 0.5
    assert relative[0][1]["y"] == 0.5
    cuda_scale = scale_to_blender_compositor(source="scale_cuda", w=1920, h=1080)
    assert cuda_scale[0][1]["source"] == "scale_cuda"
    assert cuda_scale[0][1]["hardware_filter"] == "scale_cuda"

    crop = crop_to_blender_compositor(w=1280, h=720, x=320, y=180, exact=1)
    assert crop[0][0] == "CROP"
    assert crop[0][1]["width"] == 1280
    assert crop[0][1]["height"] == 720
    assert crop[0][1]["x"] == 320
    assert crop[0][1]["exact"] is True

    rotate = rotate_to_blender_compositor(angle="PI/6")
    assert rotate[0][0] == "ROTATE"
    assert 0.52 < rotate[0][1]["angle"] < 0.53

    transpose = transpose_to_blender_compositor(arg0="clock")
    assert transpose[0][0] == "ROTATE"
    assert transpose[0][1]["label"] == "Transpose Rotate"
    assert transpose[0][1]["angle"] == 1.5707963267948966
    assert transpose[0][1]["source"] == "transpose"
    vulkan_transpose = transpose_to_blender_compositor(source="transpose_vulkan", arg0="clock")
    assert vulkan_transpose[0][1]["source"] == "transpose_vulkan"
    assert vulkan_transpose[0][1]["hardware_filter"] == "transpose_vulkan"

    hflip = flip_to_blender_compositor("hflip")
    vflip = flip_to_blender_compositor("vflip")
    vulkan_hflip = flip_to_blender_compositor("hflip_vulkan")
    vulkan_vflip = flip_to_blender_compositor("vflip_vulkan")
    vulkan_flip = flip_to_blender_compositor("flip_vulkan")
    assert hflip[0][1]["flip_x"] is True
    assert hflip[0][1]["flip_y"] is False
    assert vflip[0][1]["flip_x"] is False
    assert vflip[0][1]["flip_y"] is True
    assert vulkan_hflip[0][1]["hardware_filter"] == "hflip_vulkan"
    assert vulkan_vflip[0][1]["hardware_filter"] == "vflip_vulkan"
    assert vulkan_flip[0][1]["flip_x"] is True
    assert vulkan_flip[0][1]["flip_y"] is True

    lens = lenscorrection_to_blender_compositor(k1=-0.12, k2=0.04, cx=0.45, cy=0.55)
    assert lens[0][0] == "LENS_DISTORTION"
    assert lens[0][1]["distortion"] < -0.09
    assert lens[0][1]["center"] == (0.45, 0.55)

    result = translate_filter_chain(
        "scale=960:540,"
        "scale_cuda=w=1920:h=1080,"
        "scale_qsv=w=1920:h=1080,"
        "scale_vaapi=w=1920:h=1080,"
        "scale_vulkan=w=1920:h=1080,"
        "crop=w=1280:h=720:x=320:y=180,"
        "rotate=angle=PI/6,"
        "transpose=clock,"
        "transpose_opencl=clock,"
        "transpose_vaapi=clock,"
        "transpose_vulkan=clock,"
        "hflip,"
        "hflip_vulkan,"
        "vflip,"
        "vflip_vulkan,"
        "flip_vulkan,"
        "lenscorrection=k1=-0.12:k2=0.04:cx=0.45:cy=0.55"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "scale",
        "scale_cuda",
        "scale_qsv",
        "scale_vaapi",
        "scale_vulkan",
        "crop",
        "rotate",
        "transpose",
        "transpose_opencl",
        "transpose_vaapi",
        "transpose_vulkan",
        "hflip",
        "hflip_vulkan",
        "vflip",
        "vflip_vulkan",
        "flip_vulkan",
        "lenscorrection",
    )
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "SCALE",
        "SCALE",
        "SCALE",
        "SCALE",
        "SCALE",
        "CROP",
        "ROTATE",
        "ROTATE",
        "ROTATE",
        "ROTATE",
        "ROTATE",
        "FLIP",
        "FLIP",
        "FLIP",
        "FLIP",
        "FLIP",
        "LENS_DISTORTION",
    ]


def test_restoration_filters_translate_to_native_blender_nodes():
    hq = restoration_filter_to_blender_compositor("hqdn3d", arg0=1.5, arg1=1.5, arg2=6, arg3=6)
    assert hq[0][0] == "DENOISE"
    assert hq[0][1]["quality"] == "High"
    assert hq[0][1]["strength"] > 4.0

    nlmeans = restoration_filter_to_blender_compositor("nlmeans", s=2.5, p=7, r=9)
    opencl_nlmeans = restoration_filter_to_blender_compositor("nlmeans_opencl", s=2.5, p=7, r=9)
    vulkan_nlmeans = restoration_filter_to_blender_compositor("nlmeans_vulkan", s=2.5, p=7, r=9)
    bm3d = restoration_filter_to_blender_compositor("bm3d", sigma=3.0, group=8, range=12)
    dct = restoration_filter_to_blender_compositor("dctdnoiz", sigma=4.5, overlap=0.5)
    ow = restoration_filter_to_blender_compositor("owdenoise", ls=2.0, cs=1.5)
    vague = restoration_filter_to_blender_compositor("vaguedenoiser", threshold=2.5, percent=80)
    ata = restoration_filter_to_blender_compositor("atadenoise", s=9)
    assert [item[0][0] for item in (nlmeans, opencl_nlmeans, vulkan_nlmeans, bm3d, dct, ow, vague, ata)] == ["DENOISE"] * 8
    assert nlmeans[0][1]["label"] == "Non-Local Means Denoise"
    assert opencl_nlmeans[0][1]["hardware_filter"] == "nlmeans_opencl"
    assert vulkan_nlmeans[0][1]["hardware_filter"] == "nlmeans_vulkan"
    assert bm3d[0][1]["label"] == "BM3D Denoise"
    assert dct[0][1]["label"] == "DCT Denoise"

    median = restoration_filter_to_blender_compositor("median", radius=3, radiusV=5, percentile=0.55)
    dedot = restoration_filter_to_blender_compositor("dedot", lt=0.08, tl=0.09, tc=0.06, ct=0.02)
    assert median[0][0] == "DESPECKLE"
    assert dedot[0][0] == "DESPECKLE"
    assert median[0][1]["neighbor_threshold"] > median[0][1]["color_threshold"]

    deband = restoration_filter_to_blender_compositor("deband", **{"1thr": 0.03, "2thr": 0.025, "3thr": 0.02, "range": 20})
    deblock = restoration_filter_to_blender_compositor("deblock", block=16, alpha=0.12, beta=0.08)
    assert deband[0][0] == "BILATERAL_BLUR"
    assert deblock[0][0] == "ANTI_ALIASING"
    assert deblock[0][1]["contrast_limit"] > 2.0

    result = translate_filter_chain(
        "hqdn3d=1.5:1.5:6:6,"
        "nlmeans=s=2.5:p=7:r=9,"
        "nlmeans_opencl=s=2.5:p=7:r=9,"
        "nlmeans_vulkan=s=2.5:p=7:r=9,"
        "bm3d=sigma=3:group=8:range=12,"
        "dctdnoiz=sigma=4.5:overlap=0.5,"
        "owdenoise=ls=2:cs=1.5,"
        "vaguedenoiser=threshold=2.5:percent=80,"
        "atadenoise=s=9,"
        "median=radius=3:radiusV=5:percentile=0.55,"
        "dedot=lt=0.08:tl=0.09:tc=0.06:ct=0.02,"
        "deband=1thr=0.03:2thr=0.025:3thr=0.02:range=20,"
        "deblock=block=16:alpha=0.12:beta=0.08"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "hqdn3d",
        "nlmeans",
        "nlmeans_opencl",
        "nlmeans_vulkan",
        "bm3d",
        "dctdnoiz",
        "owdenoise",
        "vaguedenoiser",
        "atadenoise",
        "median",
        "dedot",
        "deband",
        "deblock",
    )
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "DENOISE",
        "DENOISE",
        "DENOISE",
        "DENOISE",
        "DENOISE",
        "DENOISE",
        "DENOISE",
        "DENOISE",
        "DENOISE",
        "DESPECKLE",
        "DESPECKLE",
        "BILATERAL_BLUR",
        "ANTI_ALIASING",
    ]


def test_detail_cleanup_filters_translate_to_native_blender_nodes():
    cas = detail_cleanup_filter_to_blender_compositor("cas", strength=0.45)
    assert cas[0][0] == "FILTER"
    assert cas[0][1]["filter_type"] == "Box Sharpen"

    chroma = detail_cleanup_filter_to_blender_compositor("chromanr", thres=24, sizew=5, sizeh=7)
    assert chroma[0][0] == "BILATERAL_BLUR"
    assert chroma[0][1]["source"] == "chromanr"

    fft_denoise = detail_cleanup_filter_to_blender_compositor("fftdnoiz", sigma=1.8, amount=1.0)
    assert fft_denoise[0][0] == "DENOISE"
    assert fft_denoise[0][1]["source"] == "fftdnoiz"

    vaapi_denoise = detail_cleanup_filter_to_blender_compositor("denoise_vaapi", denoise=18)
    assert vaapi_denoise[0][0] == "DENOISE"
    assert vaapi_denoise[0][1]["source"] == "denoise_vaapi"

    fft_detail = detail_cleanup_filter_to_blender_compositor("fftfilt", dc_Y=0, weight_Y=1.35)
    assert fft_detail[0][0] == "FILTER"
    assert fft_detail[0][1]["source"] == "fftfilt"

    gradfun = detail_cleanup_filter_to_blender_compositor("gradfun", strength=1.2, radius=12)
    assert gradfun[0][0] == "BILATERAL_BLUR"
    assert gradfun[0][1]["source"] == "gradfun"

    vaapi_sharpness = detail_cleanup_filter_to_blender_compositor("sharpness_vaapi", sharpness=44)
    assert vaapi_sharpness[0][0] == "FILTER"
    assert vaapi_sharpness[0][1]["source"] == "sharpness_vaapi"

    xbr = detail_cleanup_filter_to_blender_compositor("xbr", n=2)
    assert xbr[0][0] == "SCALE"
    assert xbr[0][1]["x"] == 2.0

    result = translate_filter_chain("cas=strength=0.45,chromanr=thres=24,denoise_vaapi=denoise=18,fftdnoiz=sigma=1.8,fftfilt=weight_Y=1.35,gradfun=strength=1.2,sharpness_vaapi=sharpness=44,xbr=n=2")
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("cas", "chromanr", "denoise_vaapi", "fftdnoiz", "fftfilt", "gradfun", "sharpness_vaapi", "xbr")
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "FILTER",
        "BILATERAL_BLUR",
        "DENOISE",
        "DENOISE",
        "FILTER",
        "BILATERAL_BLUR",
        "FILTER",
        "SCALE",
    ]


def test_filter_chain_supports_more_color_grading_filters():
    result = translate_filter_chain(
        "colorspace=iall=bt709:all=bt709:range=pc,"
        "colorspace_cuda=range=pc,"
        "colorlevels=rimin=0.02:rimax=0.98,"
        "colorbalance=rs=0.1:bm=0.2,"
        "vibrance=intensity=0.4,"
        "exposure=exposure=0.3:black=0.02,"
        "colortemperature=temperature=5200:mix=0.7,"
        "limiter=min=16:max=235,"
        "tonemap=tonemap=mobius:param=0.35:desat=0.4,"
        "procamp_vaapi=brightness=8:contrast=1.18:saturation=1.14:hue=4,"
        "tonemap_opencl=tonemap=mobius:param=0.35:desat=0.45:peak=600:transfer=bt709:matrix=bt709:primaries=bt709:range=pc,"
        "tonemap_vaapi=transfer=bt709:matrix=bt709:primaries=bt709:range=pc,"
        "colorcorrect=rl=0.1:bl=-0.05:rh=0.03:bh=-0.02:saturation=1.08,"
        "colorcontrast=rc=0.2:gm=-0.1:by=0.15:rcw=0.6:gmw=0.4:byw=0.5:pl=1,"
        "selectivecolor=reds=0.10 -0.04 -0.02 0.00:blues=-0.04 0.02 0.10 0.03:whites=0.02 0.00 -0.08 0.01,"
        "monochrome=cb=0.1:cr=-0.1:high=0.2,"
        "colorize=hue=210:saturation=0.45:lightness=0.55:mix=0.65,"
        "grayworld,"
        "greyedge=difford=2:minknorm=5:sigma=2,"
        "lut1d=file=warm_print.spi1d:interp=cubic,"
        "lut3d=file=teal_orange.cube:interp=tetrahedral,"
        "haldclut=interp=tetrahedral:clut=all,"
        "colormap=patch_size=64x64:nb_patches=32:type=absolute:kernel=weuclidean,"
        "geq=r='r(X,Y)*1.04':g='g(X,Y)+4':b='b(X,Y)-6',"
        "negate=components=r+g+b,"
        "colorhold=color=blue:similarity=0.12:blend=0.2,"
        "hsvhold=hue=210:similarity=0.10,"
        "chromakey=color=green:similarity=0.12:blend=0.04,"
        "chromakey_cuda=color=green:similarity=0.12:blend=0.04,"
        "colorkey=color=blue:similarity=0.10:blend=0.03,"
        "colorkey_opencl=color=blue:similarity=0.10:blend=0.03,"
        "hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.10:blend=0.02,"
        "lumakey=threshold=0.20:tolerance=0.08:softness=0.02,"
        "despill=type=green:mix=0.65:expand=0.12:green=-1.0,"
        "backgroundkey=threshold=0.08:similarity=0.12:blend=0.04,"
        "threshold=planes=7,"
        "maskedthreshold=threshold=2048:planes=7:mode=abs,"
        "blend=all_mode=overlay:all_opacity=0.35,"
        "blend_vulkan=all_mode=multiply:all_opacity=0.42,"
        "tblend=all_mode=average:all_opacity=0.45,"
        "lut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
        "tlut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
        "maskedmerge=planes=15,"
        "mergeplanes=map0p=2:map1p=1:map2p=0:map3p=3,"
        "rgbashift=rh=4:rv=-2:bh=-3:bv=2,"
        "chromashift=cbh=2:cbv=-1:crh=-2:crv=1,"
        "chromaber_vulkan=dist_x=2.0:dist_y=-1.0,"
        "alphaextract,"
        "alphamerge,"
        "extractplanes=planes=y,"
        "premultiply,"
        "unpremultiply,"
        "shuffleplanes=map0=2:map1=1:map2=0:map3=3,"
        "elbg=l=64:n=2:seed=17,"
        "unsharp=5:5:0.45:3:3:0.20,"
        "cas=strength=0.45,"
        "sobel=scale=1.2:delta=0.02,"
        "prewitt=scale=0.9:delta=0.01,"
        "kirsch=scale=0.8,"
        "edgedetect=high=0.20:low=0.08:mode=wires,"
        "erosion=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000,"
        "dilation=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000,"
        "convolution=0m='0 -1 0 -1 5 -1 0 -1 0':0rdiv=1:0bias=0,"
        "convolution_opencl=0m='0 -1 0 -1 5 -1 0 -1 0':0rdiv=1:0bias=0,"
        "avgblur=sizeX=4:sizeY=6,"
        "boxblur=lr=3:lp=2,"
        "gblur=sigma=1.2:steps=2:sigmaV=0.8,"
        "smartblur=lr=2:ls=0.8:lt=8,"
        "sab=lr=2:lpfr=1:ls=12,"
        "yaepblur=r=4:s=192,"
        "dblur=angle=30:radius=12,"
        "scale=960:540,"
        "crop=w=1280:h=720:x=320:y=180,"
        "rotate=angle=PI/6,"
        "transpose=clock,"
        "hflip,"
        "vflip,"
        "lenscorrection=k1=-0.12:k2=0.04:cx=0.45:cy=0.55,"
        "hqdn3d=1.5:1.5:6:6,"
        "nlmeans=s=2.5:p=7:r=9,"
        "bm3d=sigma=3:group=8:range=12,"
        "owdenoise=ls=2:cs=1.5,"
        "vaguedenoiser=threshold=2.5:percent=80,"
        "atadenoise=s=9,"
        "median=radius=3:radiusV=5:percentile=0.55,"
        "dedot=lt=0.08:tl=0.09:tc=0.06:ct=0.02,"
        "deband=1thr=0.03:2thr=0.025:3thr=0.02:range=20,"
        "deblock=block=16:alpha=0.12:beta=0.08,"
        "deflicker=s=12:m=median,"
        "bwdif=mode=send_frame:parity=auto:deint=all,"
        "yadif=mode=send_frame:parity=auto:deint=all,"
        "deshake=rx=16:ry=16,"
        "vidstabdetect=shakiness=5:accuracy=15:result=motion.trf,"
        "vidstabtransform=input=motion.trf:smoothing=30:zoom=2,"
        "tmix=frames=3:weights='1 2 1',"
        "fps=fps=30:round=near,"
        "framerate=fps=60,"
        "minterpolate=fps=60:mi_mode=mci,"
        "chromanr=thres=24:sizew=5:sizeh=5,"
        "fftdnoiz=sigma=1.8:amount=1.0,"
        "fftfilt=dc_Y=0:weight_Y=1.35,"
        "gradfun=strength=1.2:radius=12,"
        "xbr=n=2,"
        "histogram=mode=levels,"
        "thistogram=mode=levels,"
        "waveform=display=overlay:components=7,"
        "vectorscope=mode=color3,"
        "ciescope=system=rec709,"
        "datascope=mode=color2,"
        "oscilloscope=components=7,"
        "pixscope=x=0.55:y=0.45:w=11:h=9:o=0.7,"
        "signalstats=stat=tout+vrep+brng,"
        "colordetect=mode=color_range+alpha_mode+all,"
        "blackdetect=d=1.0:pic_th=0.96:pix_th=0.08,"
        "blackdetect_vulkan=d=1.0:pic_th=0.96:pix_th=0.08,"
        "blackframe=amount=96:threshold=28,"
        "blockdetect=period_min=3:period_max=24:planes=1,"
        "blurdetect=high=0.12:low=0.06:radius=40:block_pct=80:planes=1,"
        "cropdetect=limit=0.094:round=16:reset=30:skip=2,"
        "bbox=min_val=16,"
        "bitplanenoise=bitplane=1:filter=1,"
        "freezedetect=n=0.001:d=2,"
        "scdet=threshold=10:sc_pass=0,"
        "scdet_vulkan=threshold=10:sc_pass=0,"
        "vfrdet,"
        "idet=intl_thres=1.04:prog_thres=1.5:rep_thres=3,"
        "identity=eof_action=repeat:repeatlast=1:ts_sync_mode=nearest,"
        "ssim=stats_file=vtk_ssim.log:eof_action=repeat:repeatlast=1:ts_sync_mode=nearest,"
        "psnr=stats_file=vtk_psnr.log:stats_version=2:output_max=1:eof_action=repeat,"
        "xpsnr=stats_file=vtk_xpsnr.log:eof_action=repeat,"
        "corr=eof_action=repeat:repeatlast=1,"
        "msad=eof_action=repeat:repeatlast=1,"
        "xcorrelate=planes=7:secondary=all:eof_action=repeat,"
        "pseudocolor=preset=viridis:opacity=0.75:index=1,"
        "lutrgb=r=negval:g=val*0.9:b=val+12,"
        "histeq=strength=0.35:intensity=0.25:antibanding=1,"
        "midequalizer=planes=7,"
        "tmidequalizer=radius=9:sigma=0.55:planes=7,"
        "zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "colorspace",
        "colorspace_cuda",
        "colorlevels",
        "colorbalance",
        "vibrance",
        "exposure",
        "colortemperature",
        "limiter",
        "tonemap",
        "procamp_vaapi",
        "tonemap_opencl",
        "tonemap_vaapi",
        "colorcorrect",
        "colorcontrast",
        "selectivecolor",
        "monochrome",
        "colorize",
        "grayworld",
        "greyedge",
        "lut1d",
        "lut3d",
        "haldclut",
        "colormap",
        "geq",
        "negate",
        "colorhold",
        "hsvhold",
        "chromakey",
        "chromakey_cuda",
        "colorkey",
        "colorkey_opencl",
        "hsvkey",
        "lumakey",
        "despill",
        "backgroundkey",
        "threshold",
        "maskedthreshold",
        "blend",
        "blend_vulkan",
        "tblend",
        "lut2",
        "tlut2",
        "maskedmerge",
        "mergeplanes",
        "rgbashift",
        "chromashift",
        "chromaber_vulkan",
        "alphaextract",
        "alphamerge",
        "extractplanes",
        "premultiply",
        "unpremultiply",
        "shuffleplanes",
        "elbg",
        "unsharp",
        "cas",
        "sobel",
        "prewitt",
        "kirsch",
        "edgedetect",
        "erosion",
        "dilation",
        "convolution",
        "convolution_opencl",
        "avgblur",
        "boxblur",
        "gblur",
        "smartblur",
        "sab",
        "yaepblur",
        "dblur",
        "scale",
        "crop",
        "rotate",
        "transpose",
        "hflip",
        "vflip",
        "lenscorrection",
        "hqdn3d",
        "nlmeans",
        "bm3d",
        "owdenoise",
        "vaguedenoiser",
        "atadenoise",
        "median",
        "dedot",
        "deband",
        "deblock",
        "deflicker",
        "bwdif",
        "yadif",
        "deshake",
        "vidstabdetect",
        "vidstabtransform",
        "tmix",
        "fps",
        "framerate",
        "minterpolate",
        "chromanr",
        "fftdnoiz",
        "fftfilt",
        "gradfun",
        "xbr",
        "histogram",
        "thistogram",
        "waveform",
        "vectorscope",
        "ciescope",
        "datascope",
        "oscilloscope",
        "pixscope",
        "signalstats",
        "colordetect",
        "blackdetect",
        "blackdetect_vulkan",
        "blackframe",
        "blockdetect",
        "blurdetect",
        "cropdetect",
        "bbox",
        "bitplanenoise",
        "freezedetect",
        "scdet",
        "scdet_vulkan",
        "vfrdet",
        "idet",
        "identity",
        "ssim",
        "psnr",
        "xpsnr",
        "corr",
        "msad",
        "xcorrelate",
        "pseudocolor",
        "lutrgb",
        "histeq",
        "midequalizer",
        "tmidequalizer",
        "zscale",
    )
    assert {"CURVES", "COLOR_BALANCE", "HUE_CORRECT", "BRIGHT_CONTRAST", "WHITE_BALANCE", "TONEMAP"}.issubset(
        {modifier_type for modifier_type, _settings in result.stack}
    )
    assert {"COLOR_BALANCE", "CURVE_RGB", "TONEMAP", "HUE_CORRECT", "HUE_SAT", "EXPOSURE", "COLOR_CORRECTION", "INVERT", "CHROMA_MATTE", "COLOR_MATTE", "COLOR_SPILL", "BACKGROUND_KEY", "LUMA_MATTE", "BLEND_COMPOSITE", "MASKED_BLEND_COMPOSITE", "CHANNEL_SHIFT", "PLANE_EXTRACT", "ALPHA_MERGE", "PREMUL_KEY", "PLANE_SHUFFLE", "POSTERIZE", "FILTER", "DILATE_ERODE", "CONVOLVE", "BLUR", "BILATERAL_BLUR", "DIRECTIONAL_BLUR", "SCALE", "CROP", "ROTATE", "FLIP", "LENS_DISTORTION", "DENOISE", "DESPECKLE", "ANTI_ALIASING", "SCOPE_MONITOR", "IDENTITY_COMPARE", "QUALITY_COMPARE"}.issubset(
        {node_type for node_type, _settings in result.compositor_nodes}
    )
    assert ("sequencer_input", "bt709") in result.color_management
