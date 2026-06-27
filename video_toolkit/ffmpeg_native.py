"""Translate FFmpeg-style color intent into Blender-native VSE modifier stacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BlenderStack = tuple[tuple[str, dict[str, Any]], ...]


@dataclass(frozen=True)
class NativeTranslation:
    stack: BlenderStack
    supported_filters: tuple[str, ...] = ()
    unsupported_filters: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def translate_filter_chain(chain: str) -> NativeTranslation:
    """Translate supported FFmpeg color filters into Blender VSE modifiers.

    This intentionally covers color/tone intent that Blender can preview live in
    the VSE. Temporal filters such as deflicker, denoise, vidstab, and frame
    interpolation remain render tools because there is no equivalent native VSE
    live modifier.
    """

    stack: list[tuple[str, dict[str, Any]]] = []
    supported: list[str] = []
    unsupported: list[str] = []
    notes: list[str] = []
    for name, args in _split_filters(chain):
        name = name.lower()
        if name == "eq":
            stack.extend(eq_to_blender_stack(**args))
            supported.append(name)
        elif name == "hue":
            stack.extend(hue_to_blender_stack(**args))
            supported.append(name)
        elif name == "huesaturation":
            stack.extend(huesaturation_to_blender_stack(**args))
            supported.append(name)
        elif name == "colorchannelmixer":
            stack.extend(colorchannelmixer_to_blender_stack(**args))
            supported.append(name)
            notes.append("Color channel mixer is approximated with Blender Color Balance and White Balance.")
        elif name == "curves":
            stack.extend(curves_to_blender_stack(**args))
            supported.append(name)
        elif name == "colorlevels":
            stack.extend(colorlevels_to_blender_stack(**args))
            supported.append(name)
        elif name == "colorbalance":
            stack.extend(colorbalance_to_blender_stack(**args))
            supported.append(name)
        elif name == "vibrance":
            stack.extend(vibrance_to_blender_stack(**args))
            supported.append(name)
            notes.append("Vibrance is approximated with Blender Hue Correct and Color Balance saturation controls.")
        elif name == "exposure":
            stack.extend(exposure_to_blender_stack(**args))
            supported.append(name)
        elif name == "colortemperature":
            stack.extend(colortemperature_to_blender_stack(**args))
            supported.append(name)
        elif name == "limiter":
            stack.extend(limiter_to_blender_stack(**args))
            supported.append(name)
            notes.append("Limiter is approximated with Blender RGB curves because VSE has no legal-range clamp modifier.")
        elif name == "tonemap":
            stack.extend(tonemap_to_blender_stack(**args))
            supported.append(name)
        elif name == "normalize":
            stack.extend(normalize_to_blender_stack(**args))
            supported.append(name)
            notes.append("Normalize is approximated as a live Blender curves/tone-map stack; temporal smoothing is not native VSE.")
        elif name == "colorcorrect":
            stack.extend(colorcorrect_to_blender_stack(**args))
            supported.append(name)
            notes.append("Colorcorrect is approximated with Blender Lift/Gamma/Gain plus Hue Correct saturation.")
        elif name == "colorcontrast":
            stack.extend(colorcontrast_to_blender_stack(**args))
            supported.append(name)
            notes.append("Colorcontrast is approximated with Blender opponent-channel Color Balance controls.")
        elif name == "monochrome":
            stack.extend(monochrome_to_blender_stack(**args))
            supported.append(name)
        elif name == "colorize":
            stack.extend(colorize_to_blender_stack(**args))
            supported.append(name)
            notes.append("Colorize is approximated with Blender Hue Correct and Color Balance tinting.")
        elif name == "histeq":
            stack.extend(histeq_to_blender_stack(**args))
            supported.append(name)
            notes.append("Histogram equalization is approximated with live Blender curves and tone mapping.")
        elif name in {"unsharp"}:
            unsupported.append(name)
            notes.append(f"{name} is not a native live VSE color primitive and is omitted from the live stack.")
        else:
            unsupported.append(name)
    return NativeTranslation(tuple(stack), tuple(supported), tuple(unsupported), tuple(notes))


def eq_to_blender_stack(
    *,
    brightness: str | float = 0.0,
    contrast: str | float = 1.0,
    saturation: str | float = 1.0,
    gamma: str | float = 1.0,
    gamma_r: str | float = 1.0,
    gamma_g: str | float = 1.0,
    gamma_b: str | float = 1.0,
    gamma_weight: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    brightness_value = _float(brightness, 0.0)
    contrast_value = _float(contrast, 1.0)
    saturation_value = _float(saturation, 1.0)
    gamma_value = _float(gamma, 1.0)
    gamma_tuple = (
        _clamp(gamma_value * _float(gamma_r, 1.0), 0.25, 4.0),
        _clamp(gamma_value * _float(gamma_g, 1.0), 0.25, 4.0),
        _clamp(gamma_value * _float(gamma_b, 1.0), 0.25, 4.0),
    )
    blender_contrast = _clamp((contrast_value - 1.0) * 100.0, -100.0, 100.0)
    stack: list[tuple[str, dict[str, Any]]] = [
        ("BRIGHT_CONTRAST", {"bright": _clamp(brightness_value, -1.0, 1.0), "contrast": blender_contrast}),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gamma": gamma_tuple,
                "color_balance.gain": tuple(_clamp(1.0 + (contrast_value - 1.0) * 0.25, 0.5, 1.8) for _ in range(3)),
                "color_multiply": _clamp(1.0 + (saturation_value - 1.0) * 0.08, 0.2, 2.0),
            },
        ),
        ("HUE_CORRECT", {"__hue_correct__": {"saturation": _saturation_to_curve_y(saturation_value)}}),
    ]
    gamma_weight_value = _float(gamma_weight, 1.0)
    if gamma_value != 1.0 or gamma_weight_value != 1.0:
        stack.append(
            (
                "TONEMAP",
                {
                    "tonemap_type": "RD_PHOTORECEPTOR",
                    "gamma": _clamp(gamma_value, 0.25, 4.0),
                    "intensity": _clamp(abs(gamma_value - 1.0) * (2.0 - gamma_weight_value), 0.0, 0.35),
                    "contrast": _clamp(abs(contrast_value - 1.0), 0.0, 0.35),
                },
            )
        )
    return tuple(stack)


def hue_to_blender_stack(
    *,
    h: str | float = 0.0,
    H: str | float | None = None,
    s: str | float = 1.0,
    b: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    hue_degrees = _float(h, 0.0)
    if H is not None:
        hue_degrees = _float(H, 0.0) * 57.29577951308232
    return (
        ("BRIGHT_CONTRAST", {"bright": _clamp(_float(b, 0.0), -1.0, 1.0), "contrast": 0.0}),
        (
            "HUE_CORRECT",
            {
                "__hue_correct__": {
                    "hue": _hue_shift_to_curve_y(hue_degrees),
                    "saturation": _saturation_to_curve_y(_float(s, 1.0)),
                }
            },
        ),
    )


def huesaturation_to_blender_stack(
    *,
    hue: str | float = 0.0,
    saturation: str | float = 0.0,
    intensity: str | float = 0.0,
    strength: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    strength_value = _clamp(_float(strength, 1.0), 0.0, 100.0) / 100.0 if _float(strength, 1.0) > 1.0 else _clamp(_float(strength, 1.0), 0.0, 1.0)
    saturation_factor = 1.0 + _float(saturation, 0.0) * strength_value
    return (
        (
            "HUE_CORRECT",
            {
                "__hue_correct__": {
                    "hue": _hue_shift_to_curve_y(_float(hue, 0.0) * strength_value),
                    "saturation": _saturation_to_curve_y(saturation_factor),
                    "value": _value_to_curve_y(1.0 + _float(intensity, 0.0) * strength_value),
                }
            },
        ),
    )


def colorchannelmixer_to_blender_stack(
    *,
    rr: str | float = 1.0,
    rg: str | float = 0.0,
    rb: str | float = 0.0,
    gr: str | float = 0.0,
    gg: str | float = 1.0,
    gb: str | float = 0.0,
    br: str | float = 0.0,
    bg: str | float = 0.0,
    bb: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    red_gain = _clamp(_float(rr, 1.0) + 0.5 * _float(rg, 0.0) + 0.5 * _float(rb, 0.0), 0.2, 2.0)
    green_gain = _clamp(_float(gg, 1.0) + 0.5 * _float(gr, 0.0) + 0.5 * _float(gb, 0.0), 0.2, 2.0)
    blue_gain = _clamp(_float(bb, 1.0) + 0.5 * _float(br, 0.0) + 0.5 * _float(bg, 0.0), 0.2, 2.0)
    return (
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gain": (red_gain, green_gain, blue_gain),
                "color_balance.gamma": (
                    _clamp((1.0 + red_gain) * 0.5, 0.3, 2.0),
                    _clamp((1.0 + green_gain) * 0.5, 0.3, 2.0),
                    _clamp((1.0 + blue_gain) * 0.5, 0.3, 2.0),
                ),
            },
        ),
        ("WHITE_BALANCE", {"white_value": (red_gain, green_gain, blue_gain)}),
    )


def curves_to_blender_stack(
    *,
    preset: str | int = "none",
    master: str | None = None,
    m: str | None = None,
    red: str | None = None,
    r: str | None = None,
    green: str | None = None,
    g: str | None = None,
    blue: str | None = None,
    b: str | None = None,
    all: str | None = None,
    **_unused: str,
) -> BlenderStack:
    points: dict[int, list[tuple[float, float]]] = {}
    preset_points = _curve_preset_points(preset)
    if preset_points:
        points[0] = preset_points
    all_points = _parse_curve_points(all)
    if all_points:
        points[0] = all_points
        points[1] = all_points
        points[2] = all_points
        points[3] = all_points
    master_points = _parse_curve_points(master or m)
    if master_points:
        points[0] = master_points
    for index, value in ((1, red or r), (2, green or g), (3, blue or b)):
        parsed = _parse_curve_points(value)
        if parsed:
            points[index] = parsed
    return (("CURVES", {"__curve_points__": points}),)


def colorlevels_to_blender_stack(
    *,
    rimin: str | float = 0.0,
    gimin: str | float = 0.0,
    bimin: str | float = 0.0,
    rimax: str | float = 1.0,
    gimax: str | float = 1.0,
    bimax: str | float = 1.0,
    romin: str | float = 0.0,
    gomin: str | float = 0.0,
    bomin: str | float = 0.0,
    romax: str | float = 1.0,
    gomax: str | float = 1.0,
    bomax: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    points = {
        1: _range_curve_points(_float(rimin, 0.0), _float(rimax, 1.0), _float(romin, 0.0), _float(romax, 1.0)),
        2: _range_curve_points(_float(gimin, 0.0), _float(gimax, 1.0), _float(gomin, 0.0), _float(gomax, 1.0)),
        3: _range_curve_points(_float(bimin, 0.0), _float(bimax, 1.0), _float(bomin, 0.0), _float(bomax, 1.0)),
    }
    return (("CURVES", {"__curve_points__": points}),)


def colorbalance_to_blender_stack(
    *,
    rs: str | float = 0.0,
    gs: str | float = 0.0,
    bs: str | float = 0.0,
    rm: str | float = 0.0,
    gm: str | float = 0.0,
    bm: str | float = 0.0,
    rh: str | float = 0.0,
    gh: str | float = 0.0,
    bh: str | float = 0.0,
    pl: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    preserve_luma = _float(pl, 0.0) > 0.0
    lift = _balance_triplet(rs, gs, bs, scale=0.38, preserve_luma=preserve_luma)
    gamma = _balance_triplet(rm, gm, bm, scale=0.30, preserve_luma=preserve_luma)
    gain = _balance_triplet(rh, gh, bh, scale=0.46, preserve_luma=preserve_luma)
    return (
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.lift": lift,
                "color_balance.gamma": gamma,
                "color_balance.gain": gain,
            },
        ),
    )


def vibrance_to_blender_stack(
    *,
    intensity: str | float = 0.0,
    rbal: str | float = 1.0,
    gbal: str | float = 1.0,
    bbal: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    intensity_value = _clamp(_float(intensity, 0.0), -2.0, 2.0)
    saturation_factor = _clamp(1.0 + intensity_value * 0.35, 0.0, 2.0)
    red = _clamp(1.0 + (_float(rbal, 1.0) - 1.0) * 0.35, 0.5, 1.5)
    green = _clamp(1.0 + (_float(gbal, 1.0) - 1.0) * 0.35, 0.5, 1.5)
    blue = _clamp(1.0 + (_float(bbal, 1.0) - 1.0) * 0.35, 0.5, 1.5)
    return (
        (
            "HUE_CORRECT",
            {
                "__hue_correct__": {
                    "saturation": _saturation_to_curve_y(saturation_factor),
                    "value": _value_to_curve_y(_clamp(1.0 + max(intensity_value, 0.0) * 0.04, 0.8, 1.12)),
                }
            },
        ),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gamma": (red, green, blue),
                "color_multiply": _clamp(1.0 + intensity_value * 0.04, 0.6, 1.4),
            },
        ),
    )


def exposure_to_blender_stack(
    *,
    exposure: str | float = 0.0,
    black: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    exposure_value = _clamp(_float(exposure, 0.0), -3.0, 3.0)
    black_value = _clamp(_float(black, 0.0), -1.0, 1.0)
    midpoint = _clamp(0.5 + exposure_value * 0.08 - black_value * 0.05, 0.18, 0.82)
    return (
        ("BRIGHT_CONTRAST", {"bright": _clamp(exposure_value * 0.045 - black_value * 0.08, -0.35, 0.35), "contrast": 0.0}),
        (
            "CURVES",
            {
                "__curve_points__": {
                    0: [
                        (0.0, _clamp(black_value * 0.08, 0.0, 0.20)),
                        (0.50, midpoint),
                        (1.0, 1.0),
                    ]
                }
            },
        ),
        (
            "TONEMAP",
            {
                "tonemap_type": "RD_PHOTORECEPTOR",
                "intensity": _clamp(max(exposure_value, 0.0) * 0.08, 0.0, 0.35),
                "contrast": _clamp(abs(black_value) * 0.15, 0.0, 0.28),
                "gamma": _clamp(1.0 + exposure_value * 0.06, 0.65, 1.45),
            },
        ),
    )


def colortemperature_to_blender_stack(
    *,
    temperature: str | float = 6500.0,
    mix: str | float = 1.0,
    pl: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    temperature_value = _clamp(_float(temperature, 6500.0), 1000.0, 40000.0)
    mix_value = _clamp(_float(mix, 1.0), 0.0, 1.0)
    warmth = _clamp((6500.0 - temperature_value) / 6500.0, -1.2, 1.2) * mix_value
    red = _clamp(1.0 + warmth * 0.24, 0.55, 1.55)
    green = _clamp(1.0 + warmth * 0.04, 0.75, 1.25)
    blue = _clamp(1.0 - warmth * 0.26, 0.55, 1.55)
    if _float(pl, 0.0) > 0.0:
        red, green, blue = _preserve_average((red, green, blue))
    return (
        ("WHITE_BALANCE", {"white_value": (red, green, blue)}),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gamma": (red, green, blue),
                "color_balance.gain": (red, green, blue),
            },
        ),
    )


def limiter_to_blender_stack(
    *,
    min: str | float = 0.0,
    max: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    minimum = _normalize_limiter_value(_float(min, 0.0))
    maximum = _normalize_limiter_value(_float(max, 1.0))
    if maximum <= minimum:
        maximum = 1.0 if minimum + 0.01 > 1.0 else minimum + 0.01
    points = _range_curve_points(minimum, maximum, minimum, maximum)
    return (("CURVES", {"__curve_points__": {0: points}}),)


def tonemap_to_blender_stack(
    *,
    tonemap: str | int = "reinhard",
    param: str | float = 0.0,
    desat: str | float = 0.0,
    peak: str | float = 100.0,
    **_unused: str,
) -> BlenderStack:
    method = str(tonemap).lower()
    tonemap_type = "RH_SIMPLE" if method in {"reinhard", "clip", "linear", "gamma"} else "RD_PHOTORECEPTOR"
    param_value = abs(_float(param, 0.0))
    peak_value = _float(peak, 100.0)
    desat_value = _float(desat, 0.0)
    stack: list[tuple[str, dict[str, Any]]] = [
        (
            "TONEMAP",
            {
                "tonemap_type": tonemap_type,
                "key": _clamp(0.18 + param_value * 0.08, 0.02, 1.0),
                "offset": _clamp(1.0 + param_value * 0.10, 0.1, 4.0),
                "gamma": _clamp(1.0 + (100.0 / max(peak_value, 1.0) - 1.0) * 0.08, 0.65, 1.45),
                "intensity": _clamp(param_value * 0.08, 0.0, 0.45),
                "contrast": _clamp(param_value * 0.06, 0.0, 0.35),
            },
        )
    ]
    if desat_value:
        stack.append(("HUE_CORRECT", {"__hue_correct__": {"saturation": _saturation_to_curve_y(_clamp(1.0 - desat_value * 0.08, 0.0, 1.2))}}))
    return tuple(stack)


def normalize_to_blender_stack(
    *,
    blackpt: str = "black",
    whitept: str = "white",
    smoothing: str | float = 0,
    independence: str | float = 1.0,
    strength: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    strength_value = _clamp(_float(strength, 1.0), 0.0, 1.0)
    independence_value = _clamp(_float(independence, 1.0), 0.0, 1.0)
    black = _parse_color(blackpt, (0.0, 0.0, 0.0))
    white = _parse_color(whitept, (1.0, 1.0, 1.0))
    in_min = 0.035 * strength_value
    in_max = 1.0 - 0.035 * strength_value
    linked_points = _range_curve_points(in_min, in_max, sum(black) / 3.0, sum(white) / 3.0)
    points: dict[int, list[tuple[float, float]]] = {0: linked_points}
    if independence_value > 0.0:
        for index, black_channel, white_channel in ((1, black[0], white[0]), (2, black[1], white[1]), (3, black[2], white[2])):
            channel_black = _mix(sum(black) / 3.0, black_channel, independence_value)
            channel_white = _mix(sum(white) / 3.0, white_channel, independence_value)
            points[index] = _range_curve_points(in_min, in_max, channel_black, channel_white)
    return (
        ("CURVES", {"__curve_points__": points}),
        (
            "TONEMAP",
            {
                "tonemap_type": "RD_PHOTORECEPTOR",
                "intensity": _clamp(0.06 + strength_value * 0.10 + min(_float(smoothing, 0.0), 120.0) / 2400.0, 0.0, 0.22),
                "contrast": _clamp(strength_value * 0.14, 0.0, 0.30),
                "gamma": _clamp(1.0 + (strength_value - 0.5) * 0.06, 0.85, 1.15),
            },
        ),
    )


def colorcorrect_to_blender_stack(
    *,
    rl: str | float = 0.0,
    bl: str | float = 0.0,
    rh: str | float = 0.0,
    bh: str | float = 0.0,
    saturation: str | float = 1.0,
    analyze: str | int = 0,
    **_unused: str,
) -> BlenderStack:
    analyze_strength = 1.0 + (0.10 if str(analyze).lower() not in {"0", "manual"} else 0.0)
    lift = (
        _clamp(1.0 + _float(rl, 0.0) * 0.30 * analyze_strength, 0.45, 1.65),
        1.0,
        _clamp(1.0 + _float(bl, 0.0) * 0.30 * analyze_strength, 0.45, 1.65),
    )
    gain = (
        _clamp(1.0 + _float(rh, 0.0) * 0.38 * analyze_strength, 0.45, 1.75),
        1.0,
        _clamp(1.0 + _float(bh, 0.0) * 0.38 * analyze_strength, 0.45, 1.75),
    )
    return (
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.lift": lift,
                "color_balance.gamma": _preserve_average(((lift[0] + gain[0]) * 0.5, 1.0, (lift[2] + gain[2]) * 0.5)),
                "color_balance.gain": gain,
            },
        ),
        ("HUE_CORRECT", {"__hue_correct__": {"saturation": _saturation_to_curve_y(_float(saturation, 1.0))}}),
    )


def colorcontrast_to_blender_stack(
    *,
    rc: str | float = 0.0,
    gm: str | float = 0.0,
    by: str | float = 0.0,
    rcw: str | float = 0.0,
    gmw: str | float = 0.0,
    byw: str | float = 0.0,
    pl: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    red = 1.0 + _float(rc, 0.0) * _opponent_weight(rcw)
    green = 1.0 + _float(gm, 0.0) * _opponent_weight(gmw)
    blue = 1.0 + _float(by, 0.0) * _opponent_weight(byw)
    gamma = (_clamp(red, 0.45, 1.65), _clamp(green, 0.45, 1.65), _clamp(blue, 0.45, 1.65))
    if _float(pl, 0.0) > 0.0:
        gamma = _preserve_average(gamma)
    gain = tuple(_clamp(1.0 + (value - 1.0) * 0.55, 0.55, 1.45) for value in gamma)
    return (
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gamma": gamma,
                "color_balance.gain": gain,
                "color_multiply": _clamp(1.0 + (abs(_float(rc, 0.0)) + abs(_float(gm, 0.0)) + abs(_float(by, 0.0))) * 0.035, 0.8, 1.2),
            },
        ),
        ("WHITE_BALANCE", {"white_value": gain}),
    )


def monochrome_to_blender_stack(
    *,
    cb: str | float = 0.0,
    cr: str | float = 0.0,
    size: str | float = 1.0,
    high: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    high_value = _clamp(_float(high, 0.0), 0.0, 1.0)
    return (
        ("HUE_CORRECT", {"__hue_correct__": {"saturation": 0.0, "value": _value_to_curve_y(1.0 + high_value * 0.12)}}),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gamma": _preserve_average(
                    (
                        _clamp(1.0 + _float(cr, 0.0) * 0.08, 0.75, 1.25),
                        1.0,
                        _clamp(1.0 + _float(cb, 0.0) * 0.08, 0.75, 1.25),
                    )
                ),
                "color_multiply": _clamp(1.0 + (_float(size, 1.0) - 1.0) * 0.025, 0.8, 1.2),
            },
        ),
    )


def colorize_to_blender_stack(
    *,
    hue: str | float = 0.0,
    saturation: str | float = 0.5,
    lightness: str | float = 0.5,
    mix: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    hue_value = _float(hue, 0.0)
    saturation_value = _clamp(_float(saturation, 0.5), 0.0, 1.0)
    lightness_value = _clamp(_float(lightness, 0.5), 0.0, 1.0)
    mix_value = _clamp(_float(mix, 1.0), 0.0, 1.0)
    tint = _hsl_to_rgb(hue_value, saturation_value, lightness_value)
    strength = 1.0 - mix_value
    white_value = tuple(_clamp(_mix(1.0, channel, strength * 0.65), 0.45, 1.55) for channel in tint)
    return (
        (
            "HUE_CORRECT",
            {
                "__hue_correct__": {
                    "hue": _hue_shift_to_curve_y(hue_value * strength),
                    "saturation": _saturation_to_curve_y(1.0 + saturation_value * strength),
                    "value": _value_to_curve_y(1.0 + (lightness_value - 0.5) * strength),
                }
            },
        ),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gamma": white_value,
                "color_balance.gain": white_value,
                "color_multiply": _clamp(1.0 + saturation_value * strength * 0.08, 0.8, 1.25),
            },
        ),
        ("WHITE_BALANCE", {"white_value": white_value}),
    )


def histeq_to_blender_stack(
    *,
    strength: str | float = 0.2,
    intensity: str | float = 0.21,
    antibanding: str | int = 0,
    **_unused: str,
) -> BlenderStack:
    strength_value = _clamp(_float(strength, 0.2), 0.0, 1.0)
    intensity_value = _clamp(_float(intensity, 0.21), 0.0, 1.0)
    band_soften = _clamp(_float(antibanding, 0.0), 0.0, 2.0) * 0.015
    low = _clamp(0.25 - strength_value * 0.12 + band_soften, 0.05, 0.40)
    high = _clamp(0.75 + strength_value * 0.12 - band_soften, 0.60, 0.95)
    return (
        (
            "CURVES",
            {
                "__curve_points__": {
                    0: [
                        (0.0, 0.0),
                        (low, _clamp(low - intensity_value * 0.12, 0.0, 1.0)),
                        (0.50, _clamp(0.50 + (intensity_value - 0.21) * 0.10, 0.35, 0.65)),
                        (high, _clamp(high + intensity_value * 0.12, 0.0, 1.0)),
                        (1.0, 1.0),
                    ]
                }
            },
        ),
        (
            "TONEMAP",
            {
                "tonemap_type": "RD_PHOTORECEPTOR",
                "intensity": _clamp(strength_value * 0.12, 0.0, 0.20),
                "contrast": _clamp(intensity_value * 0.18, 0.0, 0.24),
                "gamma": _clamp(1.0 + (intensity_value - 0.21) * 0.08, 0.90, 1.12),
            },
        ),
    )


def _split_filters(chain: str) -> list[tuple[str, dict[str, str]]]:
    filters: list[tuple[str, dict[str, str]]] = []
    for item in chain.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            filters.append((item, {}))
            continue
        name, arg_text = item.split("=", 1)
        args: dict[str, str] = {}
        for part in arg_text.split(":"):
            if not part:
                continue
            if "=" in part:
                key, value = part.split("=", 1)
                args[key.strip()] = value.strip().strip("'\"")
            else:
                args.setdefault("preset", part.strip().strip("'\""))
        filters.append((name.strip(), args))
    return filters


def _parse_curve_points(value: str | None) -> list[tuple[float, float]]:
    if not value:
        return []
    points: list[tuple[float, float]] = []
    for point in value.split():
        if "/" not in point:
            continue
        x_text, y_text = point.split("/", 1)
        points.append((_clamp(_float(x_text, 0.0), 0.0, 1.0), _clamp(_float(y_text, 0.0), 0.0, 1.0)))
    return points


def _curve_preset_points(preset: str | int) -> list[tuple[float, float]]:
    key = str(preset).lower()
    presets = {
        "3": [(0.0, 0.0), (0.5, 0.42), (1.0, 0.85)],
        "darker": [(0.0, 0.0), (0.5, 0.42), (1.0, 0.85)],
        "4": [(0.0, 0.0), (0.25, 0.18), (0.75, 0.82), (1.0, 1.0)],
        "increase_contrast": [(0.0, 0.0), (0.25, 0.18), (0.75, 0.82), (1.0, 1.0)],
        "5": [(0.0, 0.1), (0.5, 0.58), (1.0, 1.0)],
        "lighter": [(0.0, 0.1), (0.5, 0.58), (1.0, 1.0)],
        "7": [(0.0, 0.0), (0.35, 0.28), (0.65, 0.72), (1.0, 1.0)],
        "medium_contrast": [(0.0, 0.0), (0.35, 0.28), (0.65, 0.72), (1.0, 1.0)],
        "9": [(0.0, 0.0), (0.20, 0.10), (0.80, 0.90), (1.0, 1.0)],
        "strong_contrast": [(0.0, 0.0), (0.20, 0.10), (0.80, 0.90), (1.0, 1.0)],
    }
    return presets.get(key, [])


def _range_curve_points(in_min: float, in_max: float, out_min: float, out_max: float) -> list[tuple[float, float]]:
    in_min = _clamp(in_min, 0.0, 1.0)
    in_max = _clamp(in_max, in_min + 0.001, 1.0)
    out_min = _clamp(out_min, 0.0, 1.0)
    out_max = _clamp(out_max, 0.0, 1.0)
    midpoint_x = (in_min + in_max) * 0.5
    midpoint_y = (out_min + out_max) * 0.5
    raw_points = [
        (0.0, out_min),
        (in_min, out_min),
        (midpoint_x, midpoint_y),
        (in_max, out_max),
        (1.0, out_max),
    ]
    points: list[tuple[float, float]] = []
    for x, y in sorted(raw_points):
        if points and abs(points[-1][0] - x) < 0.001:
            points[-1] = (points[-1][0], y)
            continue
        points.append((x, y))
    return points


def _balance_triplet(
    red: str | float,
    green: str | float,
    blue: str | float,
    *,
    scale: float,
    preserve_luma: bool,
) -> tuple[float, float, float]:
    triplet = (
        _clamp(1.0 + _float(red, 0.0) * scale, 0.35, 1.85),
        _clamp(1.0 + _float(green, 0.0) * scale, 0.35, 1.85),
        _clamp(1.0 + _float(blue, 0.0) * scale, 0.35, 1.85),
    )
    return _preserve_average(triplet) if preserve_luma else triplet


def _preserve_average(values: tuple[float, float, float]) -> tuple[float, float, float]:
    average = sum(values) / max(len(values), 1)
    if average <= 1e-6:
        return values
    return tuple(_clamp(value / average, 0.35, 1.85) for value in values)


def _normalize_limiter_value(value: float) -> float:
    if value > 1.0:
        return _clamp(value / 255.0, 0.0, 1.0)
    return _clamp(value, 0.0, 1.0)


def _parse_color(value: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if not value:
        return default
    key = str(value).strip().lower()
    named = {
        "black": (0.0, 0.0, 0.0),
        "white": (1.0, 1.0, 1.0),
        "gray": (0.5, 0.5, 0.5),
        "grey": (0.5, 0.5, 0.5),
        "red": (1.0, 0.0, 0.0),
        "green": (0.0, 1.0, 0.0),
        "blue": (0.0, 0.0, 1.0),
    }
    if key in named:
        return named[key]
    if key.startswith("0x"):
        key = key[2:]
    if key.startswith("#"):
        key = key[1:]
    if len(key) == 6:
        try:
            return (
                int(key[0:2], 16) / 255.0,
                int(key[2:4], 16) / 255.0,
                int(key[4:6], 16) / 255.0,
            )
        except ValueError:
            return default
    return default


def _opponent_weight(value: str | float) -> float:
    return 0.22 + _clamp(_float(value, 0.0), 0.0, 1.0) * 0.38


def _mix(a: float, b: float, factor: float) -> float:
    factor = _clamp(factor, 0.0, 1.0)
    return a * (1.0 - factor) + b * factor


def _hsl_to_rgb(hue: float, saturation: float, lightness: float) -> tuple[float, float, float]:
    hue = (hue % 360.0) / 360.0
    saturation = _clamp(saturation, 0.0, 1.0)
    lightness = _clamp(lightness, 0.0, 1.0)
    if saturation == 0.0:
        return (lightness, lightness, lightness)
    q = lightness * (1.0 + saturation) if lightness < 0.5 else lightness + saturation - lightness * saturation
    p = 2.0 * lightness - q
    return (
        _hue_to_rgb_channel(p, q, hue + 1.0 / 3.0),
        _hue_to_rgb_channel(p, q, hue),
        _hue_to_rgb_channel(p, q, hue - 1.0 / 3.0),
    )


def _hue_to_rgb_channel(p: float, q: float, t: float) -> float:
    if t < 0.0:
        t += 1.0
    if t > 1.0:
        t -= 1.0
    if t < 1.0 / 6.0:
        return p + (q - p) * 6.0 * t
    if t < 1.0 / 2.0:
        return q
    if t < 2.0 / 3.0:
        return p + (q - p) * (2.0 / 3.0 - t) * 6.0
    return p


def _saturation_to_curve_y(value: float) -> float:
    return _clamp(0.5 * value, 0.0, 1.0)


def _value_to_curve_y(value: float) -> float:
    return _clamp(0.5 + (value - 1.0) * 0.5, 0.0, 1.0)


def _hue_shift_to_curve_y(degrees: float) -> float:
    return _clamp(0.5 + degrees / 360.0, 0.0, 1.0)


def _float(value: str | float | int | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
