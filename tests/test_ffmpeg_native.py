from video_toolkit.ffmpeg_native import (
    colorbalance_to_blender_stack,
    colorchannelmixer_to_blender_stack,
    colorlevels_to_blender_stack,
    curves_to_blender_stack,
    eq_to_blender_stack,
    exposure_to_blender_stack,
    grayworld_to_blender_stack,
    lut_to_blender_stack,
    negate_to_blender_stack,
    normalize_to_blender_stack,
    selectivecolor_to_blender_stack,
    translate_filter_chain,
    vibrance_to_blender_stack,
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
        "normalize=smoothing=30,eq=contrast=1.08:saturation=1.1:gamma=1.02,unsharp=5:5:0.45"
    )
    assert "normalize" in result.supported_filters
    assert "eq" in result.supported_filters
    assert result.unsupported_filters == ("unsharp",)
    assert [modifier_type for modifier_type, _settings in result.stack][:5] == [
        "CURVES",
        "TONEMAP",
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "HUE_CORRECT",
    ]


def test_filter_chain_supports_color_space_metadata():
    result = translate_filter_chain(
        "colorspace=iall=bt709:all=bt2020:irange=tv:range=pc,"
        "colormatrix=src=smpte170m:dst=bt709,"
        "setparams=color_primaries=bt2020:color_trc=bt2020-10:colorspace=bt2020nc:range=full,"
        "setrange=limited"
    )
    assert result.stack == ()
    assert result.unsupported_filters == ()
    assert result.supported_filters == ("colorspace", "colormatrix", "setparams", "setrange")
    assert ("sequencer_input", "bt709") in result.color_management
    assert ("output_matrix", "bt2020") in result.color_management
    assert ("output_transfer", "bt2020-10") in result.color_management
    assert ("output_range", "limited") in result.color_management


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
        "negate=components=r+g+b,"
        "colorhold=color=blue:similarity=0.12:blend=0.2,"
        "hsvhold=hue=210:similarity=0.10,"
        "lutrgb=r=negval:g=val*0.9:b=val+12,"
        "histeq=strength=0.35:intensity=0.25:antibanding=1"
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
        "negate",
        "colorhold",
        "hsvhold",
        "lutrgb",
        "histeq",
    )
    assert {"CURVES", "COLOR_BALANCE", "HUE_CORRECT", "BRIGHT_CONTRAST", "WHITE_BALANCE", "TONEMAP"}.issubset(
        {modifier_type for modifier_type, _settings in result.stack}
    )
    assert ("sequencer_input", "bt709") in result.color_management
