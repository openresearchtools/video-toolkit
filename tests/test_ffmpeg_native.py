from video_toolkit.ffmpeg_native import (
    colorchannelmixer_to_blender_stack,
    curves_to_blender_stack,
    eq_to_blender_stack,
    translate_filter_chain,
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

