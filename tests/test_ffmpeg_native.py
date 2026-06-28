from video_toolkit.ffmpeg_native import (
    alphaextract_to_blender_compositor,
    chromakey_to_blender_compositor,
    colorbalance_to_blender_stack,
    colorchannelmixer_to_blender_stack,
    colorkey_to_blender_compositor,
    colorlevels_to_blender_stack,
    curves_to_blender_stack,
    elbg_to_blender_compositor,
    eq_to_blender_stack,
    exposure_to_blender_stack,
    extractplanes_to_blender_compositor,
    greyedge_to_blender_stack,
    grayworld_to_blender_stack,
    hsvkey_to_blender_compositor,
    lumakey_to_blender_compositor,
    lut_to_blender_stack,
    negate_to_blender_stack,
    normalize_to_blender_stack,
    premultiply_to_blender_compositor,
    pseudocolor_to_blender_stack,
    rgbashift_to_blender_compositor,
    selectivecolor_to_blender_stack,
    shuffleplanes_to_blender_compositor,
    translate_filter_chain,
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


def test_filter_chain_reports_non_native_filters():
    result = translate_filter_chain(
        "normalize=smoothing=30,eq=contrast=1.08:saturation=1.1:gamma=1.02,unsharp=5:5:0.45,hqdn3d=1.5:1.5:6:6"
    )
    assert "normalize" in result.supported_filters
    assert "eq" in result.supported_filters
    assert "unsharp" in result.supported_filters
    assert result.unsupported_filters == ("hqdn3d",)
    assert [modifier_type for modifier_type, _settings in result.stack][:5] == [
        "CURVES",
        "TONEMAP",
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "HUE_CORRECT",
    ]
    assert result.compositor_nodes[0][0] == "FILTER"


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

    result = translate_filter_chain(
        "chromakey=color=green:similarity=0.12:blend=0.04,"
        "colorkey=color=blue:similarity=0.10:blend=0.03,"
        "hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.10:blend=0.02,"
        "lumakey=threshold=0.20:tolerance=0.08:softness=0.02"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("chromakey", "colorkey", "hsvkey", "lumakey")
    assert [node_type for node_type, _settings in result.compositor_nodes] == [
        "CHROMA_MATTE",
        "COLOR_MATTE",
        "COLOR_MATTE",
        "LUMA_MATTE",
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


def test_alpha_and_plane_extract_translate_to_compositor_graph_specs():
    alpha = alphaextract_to_blender_compositor()
    assert alpha == (("PLANE_EXTRACT", {"plane": "alpha", "source": "alphaextract"}),)

    luma = extractplanes_to_blender_compositor(planes="y")
    assert luma == (("PLANE_EXTRACT", {"plane": "y", "source": "extractplanes"}),)

    first_multi = extractplanes_to_blender_compositor(planes="g+b")
    assert first_multi[0][1]["plane"] == "g"

    result = translate_filter_chain("alphaextract,extractplanes=planes=y")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("alphaextract", "extractplanes")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["PLANE_EXTRACT", "PLANE_EXTRACT"]
    assert [settings["plane"] for _node_type, settings in result.compositor_nodes] == ["alpha", "y"]


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

    result = translate_filter_chain("unsharp=5:5:0.45:3:3:0.20,unsharp=lx=7:ly=7:la=-0.40")
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("unsharp", "unsharp")
    assert [node_type for node_type, _settings in result.compositor_nodes] == ["FILTER", "FILTER"]
    assert result.compositor_nodes[0][1]["filter_type"] == "Box Sharpen"
    assert result.compositor_nodes[1][1]["filter_type"] == "Soften"


def test_filter_chain_supports_more_color_grading_filters():
    result = translate_filter_chain(
        "colorspace=iall=bt709:all=bt709:range=pc,"
        "colorlevels=rimin=0.02:rimax=0.98,"
        "colorbalance=rs=0.1:bm=0.2,"
        "vibrance=intensity=0.4,"
        "exposure=exposure=0.3:black=0.02,"
        "colortemperature=temperature=5200:mix=0.7,"
        "limiter=min=16:max=235,"
        "tonemap=tonemap=mobius:param=0.35:desat=0.4,"
        "colorcorrect=rl=0.1:bl=-0.05:rh=0.03:bh=-0.02:saturation=1.08,"
        "colorcontrast=rc=0.2:gm=-0.1:by=0.15:rcw=0.6:gmw=0.4:byw=0.5:pl=1,"
        "selectivecolor=reds=0.10 -0.04 -0.02 0.00:blues=-0.04 0.02 0.10 0.03:whites=0.02 0.00 -0.08 0.01,"
        "monochrome=cb=0.1:cr=-0.1:high=0.2,"
        "colorize=hue=210:saturation=0.45:lightness=0.55:mix=0.65,"
        "grayworld,"
        "greyedge=difford=2:minknorm=5:sigma=2,"
        "negate=components=r+g+b,"
        "colorhold=color=blue:similarity=0.12:blend=0.2,"
        "hsvhold=hue=210:similarity=0.10,"
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
        "pseudocolor=preset=viridis:opacity=0.75:index=1,"
        "lutrgb=r=negval:g=val*0.9:b=val+12,"
        "histeq=strength=0.35:intensity=0.25:antibanding=1,"
        "zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "colorspace",
        "colorlevels",
        "colorbalance",
        "vibrance",
        "exposure",
        "colortemperature",
        "limiter",
        "tonemap",
        "colorcorrect",
        "colorcontrast",
        "selectivecolor",
        "monochrome",
        "colorize",
        "grayworld",
        "greyedge",
        "negate",
        "colorhold",
        "hsvhold",
        "chromakey",
        "colorkey",
        "hsvkey",
        "lumakey",
        "rgbashift",
        "chromashift",
        "alphaextract",
        "extractplanes",
        "premultiply",
        "unpremultiply",
        "shuffleplanes",
        "elbg",
        "unsharp",
        "pseudocolor",
        "lutrgb",
        "histeq",
        "zscale",
    )
    assert {"CURVES", "COLOR_BALANCE", "HUE_CORRECT", "BRIGHT_CONTRAST", "WHITE_BALANCE", "TONEMAP"}.issubset(
        {modifier_type for modifier_type, _settings in result.stack}
    )
    assert {"CHROMA_MATTE", "COLOR_MATTE", "LUMA_MATTE", "CHANNEL_SHIFT", "PLANE_EXTRACT", "PREMUL_KEY", "PLANE_SHUFFLE", "POSTERIZE", "FILTER"}.issubset(
        {node_type for node_type, _settings in result.compositor_nodes}
    )
    assert ("sequencer_input", "bt709") in result.color_management
