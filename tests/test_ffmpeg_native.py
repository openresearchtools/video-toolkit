from video_toolkit.ffmpeg_native import (
    colorbalance_to_blender_stack,
    colorchannelmixer_to_blender_stack,
    colorlevels_to_blender_stack,
    curves_to_blender_stack,
    eq_to_blender_stack,
    exposure_to_blender_stack,
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


def test_filter_chain_reports_non_native_filters():
    result = translate_filter_chain(
        "normalize=smoothing=30,eq=contrast=1.08:saturation=1.1:gamma=1.02,unsharp=5:5:0.45"
    )
    assert "eq" in result.supported_filters
    assert result.unsupported_filters == ("normalize", "unsharp")
    assert [modifier_type for modifier_type, _settings in result.stack][:3] == [
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "HUE_CORRECT",
    ]


def test_filter_chain_supports_more_color_grading_filters():
    result = translate_filter_chain(
        "colorlevels=rimin=0.02:rimax=0.98,"
        "colorbalance=rs=0.1:bm=0.2,"
        "vibrance=intensity=0.4,"
        "exposure=exposure=0.3:black=0.02,"
        "colortemperature=temperature=5200:mix=0.7,"
        "limiter=min=16:max=235,"
        "tonemap=tonemap=mobius:param=0.35:desat=0.4"
    )
    assert result.unsupported_filters == ()
    assert result.supported_filters == (
        "colorlevels",
        "colorbalance",
        "vibrance",
        "exposure",
        "colortemperature",
        "limiter",
        "tonemap",
    )
    assert {"CURVES", "COLOR_BALANCE", "HUE_CORRECT", "BRIGHT_CONTRAST", "WHITE_BALANCE", "TONEMAP"}.issubset(
        {modifier_type for modifier_type, _settings in result.stack}
    )
