"""Translate FFmpeg-style color intent into Blender-native VSE/compositor tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BlenderStack = tuple[tuple[str, dict[str, Any]], ...]
CompositorStack = tuple[tuple[str, dict[str, Any]], ...]

NATIVE_FFMPEG_COLOR_FILTERS = (
    "eq",
    "hue",
    "huesaturation",
    "colorchannelmixer",
    "curves",
    "colorlevels",
    "colorbalance",
    "vibrance",
    "exposure",
    "colortemperature",
    "limiter",
    "tonemap",
    "normalize",
    "colorcorrect",
    "colorcontrast",
    "selectivecolor",
    "monochrome",
    "colorize",
    "grayworld",
    "greyedge",
    "negate",
    "chromahold",
    "colorhold",
    "hsvhold",
    "pseudocolor",
    "lut",
    "lutrgb",
    "lutyuv",
    "histeq",
)

NATIVE_FFMPEG_COLOR_MANAGEMENT_FILTERS = (
    "colorspace",
    "colormatrix",
    "setparams",
    "setrange",
    "zscale",
)

NATIVE_FFMPEG_COMPOSITOR_FILTERS = (
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
)

NATIVE_FFMPEG_FILTERS = NATIVE_FFMPEG_COLOR_FILTERS + NATIVE_FFMPEG_COMPOSITOR_FILTERS + NATIVE_FFMPEG_COLOR_MANAGEMENT_FILTERS


@dataclass(frozen=True)
class NativeTranslation:
    stack: BlenderStack
    compositor_nodes: CompositorStack = ()
    supported_filters: tuple[str, ...] = ()
    unsupported_filters: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    color_management: tuple[tuple[str, str], ...] = ()


def translate_filter_chain(chain: str) -> NativeTranslation:
    """Translate supported FFmpeg color filters into Blender VSE modifiers.

    This intentionally covers color/tone intent that Blender can preview live in
    the VSE. Temporal filters such as deflicker, denoise, vidstab, and frame
    interpolation remain render tools because there is no equivalent native VSE
    live modifier.
    """

    stack: list[tuple[str, dict[str, Any]]] = []
    compositor_nodes: list[tuple[str, dict[str, Any]]] = []
    supported: list[str] = []
    unsupported: list[str] = []
    notes: list[str] = []
    color_management: list[tuple[str, str]] = []
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
        elif name == "selectivecolor":
            stack.extend(selectivecolor_to_blender_stack(**args))
            supported.append(name)
            notes.append("Selectivecolor is approximated with Blender Hue Correct hue-zone curves and Color Balance tonal zones.")
        elif name == "monochrome":
            stack.extend(monochrome_to_blender_stack(**args))
            supported.append(name)
        elif name == "colorize":
            stack.extend(colorize_to_blender_stack(**args))
            supported.append(name)
            notes.append("Colorize is approximated with Blender Hue Correct and Color Balance tinting.")
        elif name == "grayworld":
            stack.extend(grayworld_to_blender_stack(**args))
            supported.append(name)
            notes.append("Grayworld is exposed as editable Blender White Balance/Lift-Gamma-Gain controls; use sampled white balance for frame-measured auto values.")
        elif name == "greyedge":
            stack.extend(greyedge_to_blender_stack(**args))
            supported.append(name)
            notes.append("Greyedge is approximated with editable Blender White Balance plus edge-weighted contrast curves; use sampled white balance for frame-measured auto values.")
        elif name == "negate":
            stack.extend(negate_to_blender_stack(**args))
            supported.append(name)
        elif name in {"chromahold", "colorhold"}:
            stack.extend(colorhold_to_blender_stack(**args))
            supported.append(name)
            notes.append(f"{name} is approximated with Blender Hue Correct saturation-zone curves.")
        elif name == "hsvhold":
            stack.extend(hsvhold_to_blender_stack(**args))
            supported.append(name)
            notes.append("Hsvhold is approximated with Blender Hue Correct saturation-zone curves.")
        elif name == "chromakey":
            compositor_nodes.extend(chromakey_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Chromakey is translated to Blender compositor Chroma Matte nodes.")
        elif name == "colorkey":
            compositor_nodes.extend(colorkey_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Colorkey is translated to Blender compositor Color Matte nodes.")
        elif name == "hsvkey":
            compositor_nodes.extend(hsvkey_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Hsvkey is translated to Blender compositor Color Matte nodes using HSV-derived key color and tolerance controls.")
        elif name == "lumakey":
            compositor_nodes.extend(lumakey_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Lumakey is translated to Blender compositor Luma Matte nodes.")
        elif name == "rgbashift":
            compositor_nodes.extend(rgbashift_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Rgbashift is translated to Blender compositor Separate/Translate/Combine channel nodes.")
        elif name == "chromashift":
            compositor_nodes.extend(chromashift_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Chromashift is approximated with Blender compositor red/blue channel Translate nodes.")
        elif name == "alphaextract":
            compositor_nodes.extend(alphaextract_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Alphaextract is translated to Blender compositor Separate/Combine alpha-plane nodes.")
        elif name == "extractplanes":
            compositor_nodes.extend(extractplanes_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Extractplanes is translated to Blender compositor plane extraction nodes; multi-output requests use the first requested plane in this single-chain workflow.")
        elif name == "premultiply":
            compositor_nodes.extend(premultiply_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Premultiply is translated to Blender compositor Premul Key alpha conversion nodes.")
        elif name == "unpremultiply":
            compositor_nodes.extend(unpremultiply_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Unpremultiply is translated to Blender compositor Premul Key alpha conversion nodes.")
        elif name == "pseudocolor":
            stack.extend(pseudocolor_to_blender_stack(**args))
            supported.append(name)
            notes.append("Pseudocolor is approximated with editable Blender Hue Correct curves, RGB curves, and Color Balance palette tinting.")
        elif name in {"lut", "lutrgb", "lutyuv"}:
            lut_stack = lut_to_blender_stack(**args)
            if lut_stack:
                stack.extend(lut_stack)
                supported.append(name)
                notes.append(f"{name} linear/identity/negation expressions are approximated with Blender RGB Curves.")
            else:
                unsupported.append(name)
                notes.append(f"{name} uses expressions that do not map safely to native Blender live curves.")
        elif name == "histeq":
            stack.extend(histeq_to_blender_stack(**args))
            supported.append(name)
            notes.append("Histogram equalization is approximated with live Blender curves and tone mapping.")
        elif name == "colorspace":
            color_management.extend(colorspace_to_blender_color_management(**args))
            supported.append(name)
            notes.append("Colorspace is applied through Blender Sequencer input color-management settings where possible.")
        elif name == "colormatrix":
            color_management.extend(colormatrix_to_blender_color_management(**args))
            supported.append(name)
            notes.append("Colormatrix is tracked as Blender color-management intent; exact YUV matrix conversion is not a VSE modifier.")
        elif name == "setparams":
            color_management.extend(setparams_to_blender_color_management(**args))
            supported.append(name)
            notes.append("Setparams color metadata is tracked as Blender color-management intent.")
        elif name == "setrange":
            color_management.extend(setrange_to_blender_color_management(**args))
            supported.append(name)
            notes.append("Setrange is tracked as color-range metadata; Blender VSE has no direct range flag modifier.")
        elif name == "zscale":
            color_management.extend(zscale_to_blender_color_management(**args))
            supported.append(name)
            notes.append("Zscale color metadata is tracked through Blender Sequencer color-management intent; scaling remains a rendered tool.")
        elif name in {"unsharp"}:
            unsupported.append(name)
            notes.append(f"{name} is not a native live VSE color primitive and is omitted from the live stack.")
        else:
            unsupported.append(name)
    return NativeTranslation(
        tuple(stack),
        tuple(compositor_nodes),
        tuple(supported),
        tuple(unsupported),
        tuple(notes),
        tuple(_dedupe_pairs(color_management)),
    )


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


def grayworld_to_blender_stack(**_unused: str) -> BlenderStack:
    return (
        ("WHITE_BALANCE", {"white_value": (1.0, 1.0, 1.0)}),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.lift": (1.0, 1.0, 1.0),
                "color_balance.gamma": (1.0, 1.0, 1.0),
                "color_balance.gain": (1.0, 1.0, 1.0),
            },
        ),
    )


def greyedge_to_blender_stack(
    *,
    difford: str | int = 1,
    minknorm: str | float = 1.0,
    sigma: str | float = 1.0,
    **_unused: str,
) -> BlenderStack:
    edge_order = _clamp(_float(difford, 1.0), 0.0, 2.0)
    minkowski = _clamp(_float(minknorm, 1.0), 0.0, 20.0)
    blur_sigma = _clamp(_float(sigma, 1.0), 0.0, 20.0)
    edge_strength = _clamp(0.035 + edge_order * 0.035 + minkowski * 0.006 + blur_sigma * 0.004, 0.035, 0.24)
    return (
        ("WHITE_BALANCE", {"white_value": (1.0, 1.0, 1.0)}),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.lift": _preserve_average((1.0 + edge_strength * 0.18, 1.0, 1.0 - edge_strength * 0.12)),
                "color_balance.gamma": _preserve_average((1.0 + edge_strength * 0.08, 1.0, 1.0 - edge_strength * 0.08)),
                "color_balance.gain": _preserve_average((1.0 + edge_strength * 0.10, 1.0, 1.0 - edge_strength * 0.06)),
            },
        ),
        (
            "CURVES",
            {
                "__curve_points__": {
                    0: [
                        (0.0, 0.0),
                        (0.25, _clamp(0.25 - edge_strength * 0.20, 0.0, 1.0)),
                        (0.50, 0.50),
                        (0.75, _clamp(0.75 + edge_strength * 0.20, 0.0, 1.0)),
                        (1.0, 1.0),
                    ]
                }
            },
        ),
    )


def negate_to_blender_stack(
    *,
    components: str = "y+u+v+r+g+b",
    negate_alpha: str | int | bool = False,
    **_unused: str,
) -> BlenderStack:
    curve_points: dict[int, list[tuple[float, float]]] = {}
    component_set = {part.strip().lower() for part in str(components or "").replace("|", "+").split("+") if part.strip()}
    if not component_set:
        component_set = {"y", "u", "v", "r", "g", "b"}
    invert = [(0.0, 1.0), (1.0, 0.0)]
    if component_set & {"y", "u", "v"}:
        curve_points[0] = invert
    if "r" in component_set:
        curve_points[1] = invert
    if "g" in component_set:
        curve_points[2] = invert
    if "b" in component_set:
        curve_points[3] = invert
    if _truthy(negate_alpha):
        curve_points[0] = invert
    if not curve_points:
        curve_points[0] = invert
    return (("CURVES", {"__curve_points__": curve_points}),)


def colorhold_to_blender_stack(
    *,
    color: str = "black",
    similarity: str | float = 0.01,
    blend: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    hue = _rgb_to_hue(_parse_color(color, (0.0, 0.0, 0.0)))
    return (
        (
            "HUE_CORRECT",
            {"__curve_points__": {1: _hold_saturation_curve_points(hue, _float(similarity, 0.01), _float(blend, 0.0))}},
        ),
    )


def hsvhold_to_blender_stack(
    *,
    hue: str | float = 0.0,
    sat: str | float = 0.0,
    val: str | float = 0.0,
    similarity: str | float = 0.01,
    blend: str | float = 0.0,
    **_unused: str,
) -> BlenderStack:
    hue_value = (_float(hue, 0.0) % 360.0) / 360.0
    saturation_points = _hold_saturation_curve_points(hue_value, _float(similarity, 0.01), _float(blend, 0.0))
    value_points = [
        (x, _clamp(y + _float(val, 0.0) * 0.08 + _float(sat, 0.0) * 0.04, 0.0, 1.0))
        for x, y in saturation_points
    ]
    return (("HUE_CORRECT", {"__curve_points__": {1: saturation_points, 2: value_points}}),)


def chromakey_to_blender_compositor(
    *,
    color: str = "black",
    similarity: str | float = 0.01,
    blend: str | float = 0.0,
    yuv: str | int = 0,
    **_unused: str,
) -> CompositorStack:
    key_color = _parse_color(color, (0.0, 0.0, 0.0))
    similarity_value = _clamp(_float(similarity, 0.01), 0.0, 1.0)
    blend_value = _clamp(_float(blend, 0.0), 0.0, 1.0)
    return (
        (
            "CHROMA_MATTE",
            {
                "key_color": key_color,
                "minimum": _clamp(similarity_value * 0.55, 0.0, 1.0),
                "maximum": _clamp(similarity_value + blend_value * 0.35, 0.0, 1.0),
                "falloff": _clamp(blend_value, 0.0, 1.0),
                "space": "YUV" if _truthy(yuv) else "RGB",
            },
        ),
    )


def colorkey_to_blender_compositor(
    *,
    color: str = "black",
    similarity: str | float = 0.01,
    blend: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    similarity_value = _clamp(_float(similarity, 0.01), 0.0, 1.0)
    blend_value = _clamp(_float(blend, 0.0), 0.0, 1.0)
    tolerance = _clamp(similarity_value + blend_value * 0.25, 0.0, 1.0)
    return (
        (
            "COLOR_MATTE",
            {
                "key_color": _parse_color(color, (0.0, 0.0, 0.0)),
                "hue": tolerance,
                "saturation": _clamp(tolerance + 0.02, 0.0, 1.0),
                "value": _clamp(tolerance + 0.02, 0.0, 1.0),
            },
        ),
    )


def hsvkey_to_blender_compositor(
    *,
    hue: str | float = 0.0,
    sat: str | float = 0.0,
    val: str | float = 0.0,
    similarity: str | float = 0.01,
    blend: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    hue_value = _float(hue, 0.0) % 360.0
    sat_value = _clamp(_float(sat, 0.0), 0.0, 1.0)
    val_value = _clamp(_float(val, 0.0), 0.0, 1.0)
    similarity_value = _clamp(_float(similarity, 0.01), 0.0, 1.0)
    blend_value = _clamp(_float(blend, 0.0), 0.0, 1.0)
    tolerance = _clamp(similarity_value + blend_value * 0.25, 0.0, 1.0)
    return (
        (
            "COLOR_MATTE",
            {
                "key_color": _hsv_to_rgb(hue_value, sat_value or 1.0, val_value or 1.0),
                "hue": tolerance,
                "saturation": _clamp(tolerance + max(sat_value, 0.05) * 0.08, 0.0, 1.0),
                "value": _clamp(tolerance + max(val_value, 0.05) * 0.08, 0.0, 1.0),
            },
        ),
    )


def lumakey_to_blender_compositor(
    *,
    threshold: str | float = 0.0,
    tolerance: str | float = 0.01,
    softness: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    threshold_value = _clamp(_float(threshold, 0.0), 0.0, 1.0)
    tolerance_value = _clamp(_float(tolerance, 0.01) + _float(softness, 0.0) * 0.5, 0.0, 1.0)
    return (
        (
            "LUMA_MATTE",
            {
                "minimum": _clamp(threshold_value - tolerance_value, 0.0, 1.0),
                "maximum": _clamp(threshold_value + tolerance_value, 0.0, 1.0),
            },
        ),
    )


def rgbashift_to_blender_compositor(
    *,
    rh: str | float = 0.0,
    rv: str | float = 0.0,
    gh: str | float = 0.0,
    gv: str | float = 0.0,
    bh: str | float = 0.0,
    bv: str | float = 0.0,
    ah: str | float = 0.0,
    av: str | float = 0.0,
    edge: str | int = "smear",
    **_unused: str,
) -> CompositorStack:
    return (
        (
            "CHANNEL_SHIFT",
            {
                "offsets": {
                    "red": (_shift_pixels(rh), _shift_pixels(rv)),
                    "green": (_shift_pixels(gh), _shift_pixels(gv)),
                    "blue": (_shift_pixels(bh), _shift_pixels(bv)),
                    "alpha": (_shift_pixels(ah), _shift_pixels(av)),
                },
                "edge": str(edge).lower(),
            },
        ),
    )


def chromashift_to_blender_compositor(
    *,
    cbh: str | float = 0.0,
    cbv: str | float = 0.0,
    crh: str | float = 0.0,
    crv: str | float = 0.0,
    edge: str | int = "smear",
    **_unused: str,
) -> CompositorStack:
    return (
        (
            "CHANNEL_SHIFT",
            {
                "offsets": {
                    "red": (_shift_pixels(crh), _shift_pixels(crv)),
                    "green": (0.0, 0.0),
                    "blue": (_shift_pixels(cbh), _shift_pixels(cbv)),
                    "alpha": (0.0, 0.0),
                },
                "edge": str(edge).lower(),
                "approximation": "YUV chroma offsets are approximated as red/blue RGB channel offsets.",
            },
        ),
    )


def alphaextract_to_blender_compositor(**_unused: str) -> CompositorStack:
    return (("PLANE_EXTRACT", {"plane": "alpha", "source": "alphaextract"}),)


def extractplanes_to_blender_compositor(
    *,
    planes: str = "",
    preset: str = "",
    **_unused: str,
) -> CompositorStack:
    return (("PLANE_EXTRACT", {"plane": _extract_plane_name(planes or preset or "r"), "source": "extractplanes"}),)


def premultiply_to_blender_compositor(**_unused: str) -> CompositorStack:
    return (("PREMUL_KEY", {"mode": "To Premultiplied", "source": "premultiply"}),)


def unpremultiply_to_blender_compositor(**_unused: str) -> CompositorStack:
    return (("PREMUL_KEY", {"mode": "To Straight", "source": "unpremultiply"}),)


def pseudocolor_to_blender_stack(
    *,
    preset: str | int = "turbo",
    opacity: str | float = 1.0,
    index: str | int = 0,
    **_unused: str,
) -> BlenderStack:
    opacity_value = _clamp(_float(opacity, 1.0), 0.0, 1.0)
    key = str(preset).strip().lower()
    palettes = {
        "magma": (285.0, 0.76, 0.42),
        "inferno": (35.0, 0.82, 0.48),
        "plasma": (300.0, 0.72, 0.52),
        "viridis": (150.0, 0.56, 0.48),
        "turbo": (215.0, 0.74, 0.50),
        "cividis": (215.0, 0.36, 0.52),
        "range1": (30.0, 0.70, 0.50),
        "range2": (210.0, 0.70, 0.50),
        "shadows": (225.0, 0.55, 0.36),
        "highlights": (45.0, 0.62, 0.62),
    }
    base_hue, saturation, lightness = palettes.get(key, palettes["turbo"])
    if str(index).strip() not in {"", "0"}:
        base_hue = (base_hue + _float(index, 0.0) * 23.0) % 360.0
    tint = _hsl_to_rgb(base_hue, saturation, lightness)
    strength = opacity_value
    hue_points = [
        (0.0, _hue_shift_to_curve_y(base_hue - 120.0 * strength)),
        (0.33, _hue_shift_to_curve_y(base_hue - 20.0 * strength)),
        (0.66, _hue_shift_to_curve_y(base_hue + 75.0 * strength)),
        (1.0, _hue_shift_to_curve_y(base_hue + 140.0 * strength)),
    ]
    saturation_points = [
        (0.0, _saturation_to_curve_y(_clamp(0.35 + saturation * strength, 0.0, 2.0))),
        (0.50, _saturation_to_curve_y(_clamp(0.70 + saturation * strength * 0.65, 0.0, 2.0))),
        (1.0, _saturation_to_curve_y(_clamp(0.45 + saturation * strength, 0.0, 2.0))),
    ]
    value_points = [
        (0.0, _value_to_curve_y(_clamp(0.82 + (lightness - 0.5) * strength, 0.3, 1.4))),
        (0.50, _value_to_curve_y(_clamp(1.0 + (lightness - 0.5) * strength * 0.5, 0.3, 1.4))),
        (1.0, _value_to_curve_y(_clamp(1.08 + (lightness - 0.5) * strength, 0.3, 1.4))),
    ]
    white_value = tuple(_clamp(_mix(1.0, channel, strength * 0.50), 0.45, 1.55) for channel in tint)
    return (
        ("HUE_CORRECT", {"__curve_points__": {0: hue_points, 1: saturation_points, 2: value_points}}),
        (
            "CURVES",
            {
                "__curve_points__": {
                    0: [
                        (0.0, _clamp(0.02 * strength, 0.0, 0.12)),
                        (0.35, _clamp(0.28 + strength * 0.08, 0.0, 1.0)),
                        (0.70, _clamp(0.78 - strength * 0.04, 0.0, 1.0)),
                        (1.0, 1.0),
                    ]
                }
            },
        ),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.gamma": white_value,
                "color_balance.gain": white_value,
                "color_multiply": _clamp(1.0 + saturation * strength * 0.06, 0.8, 1.25),
            },
        ),
    )


def lut_to_blender_stack(
    *,
    c0: str = "clipval",
    c1: str = "clipval",
    c2: str = "clipval",
    y: str = "",
    r: str = "",
    g: str = "",
    b: str = "",
    **_unused: str,
) -> BlenderStack:
    curves: dict[int, list[tuple[float, float]]] = {}
    master = _simple_lut_expression_curve(y)
    if master:
        curves[0] = master
    for index, expression in ((1, r or c0), (2, g or c1), (3, b or c2)):
        points = _simple_lut_expression_curve(expression)
        if points:
            curves[index] = points
    identity = [(0.0, 0.0), (1.0, 1.0)]
    curves = {index: points for index, points in curves.items() if points != identity}
    return (("CURVES", {"__curve_points__": curves}),) if curves else ()


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


def selectivecolor_to_blender_stack(
    *,
    correction_method: str | int = "absolute",
    reds: str = "",
    yellows: str = "",
    greens: str = "",
    cyans: str = "",
    blues: str = "",
    magentas: str = "",
    whites: str = "",
    neutrals: str = "",
    blacks: str = "",
    **_unused: str,
) -> BlenderStack:
    relative = str(correction_method).lower() in {"1", "relative"}
    scale = 0.72 if relative else 1.0
    zone_values = {
        "reds": _parse_cmyk_adjustment(reds),
        "yellows": _parse_cmyk_adjustment(yellows),
        "greens": _parse_cmyk_adjustment(greens),
        "cyans": _parse_cmyk_adjustment(cyans),
        "blues": _parse_cmyk_adjustment(blues),
        "magentas": _parse_cmyk_adjustment(magentas),
    }
    tonal_values = {
        "blacks": _parse_cmyk_adjustment(blacks),
        "neutrals": _parse_cmyk_adjustment(neutrals),
        "whites": _parse_cmyk_adjustment(whites),
    }
    stack: list[tuple[str, dict[str, Any]]] = []
    if any(any(abs(channel) > 1e-6 for channel in value) for value in zone_values.values()):
        stack.append(("HUE_CORRECT", {"__curve_points__": _selective_hue_curve_points(zone_values, scale)}))
    if any(any(abs(channel) > 1e-6 for channel in value) for value in tonal_values.values()):
        stack.append(
            (
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.lift": _cmyk_to_rgb_balance(tonal_values["blacks"], scale=0.26 * scale),
                    "color_balance.gamma": _cmyk_to_rgb_balance(tonal_values["neutrals"], scale=0.22 * scale),
                    "color_balance.gain": _cmyk_to_rgb_balance(tonal_values["whites"], scale=0.30 * scale),
                    "color_multiply": _clamp(1.0 - tonal_values["neutrals"][3] * 0.06 * scale, 0.75, 1.25),
                },
            )
        )
    if not stack:
        stack.append(("HUE_CORRECT", {"__hue_correct__": {"saturation": 0.5, "value": 0.5}}))
    return tuple(stack)


def colorspace_to_blender_color_management(
    *,
    all: str | int = "",
    space: str | int = "",
    range: str | int = "",
    primaries: str | int = "",
    trc: str | int = "",
    iall: str | int = "",
    ispace: str | int = "",
    irange: str | int = "",
    iprimaries: str | int = "",
    itrc: str | int = "",
    **_unused: str,
) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    input_space = _first_color_value(iall, ispace, iprimaries, itrc)
    output_space = _first_color_value(all, space, primaries, trc)
    if input_space:
        pairs.append(("sequencer_input", input_space))
    elif output_space:
        pairs.append(("sequencer_input", output_space))
    for key, value in (
        ("input_matrix", ispace or iall),
        ("output_matrix", space or all),
        ("input_primaries", iprimaries or iall),
        ("output_primaries", primaries or all),
        ("input_transfer", itrc or iall),
        ("output_transfer", trc or all),
    ):
        normalized = _normalize_color_value(value)
        if normalized:
            pairs.append((key, normalized))
    for key, value in (("input_range", irange), ("output_range", range)):
        normalized = _normalize_range_value(value)
        if normalized:
            pairs.append((key, normalized))
    return tuple(_dedupe_pairs(pairs))


def colormatrix_to_blender_color_management(
    *,
    src: str | int = "",
    dst: str | int = "",
    preset: str | int = "",
    **_unused: str,
) -> tuple[tuple[str, str], ...]:
    source = _normalize_color_value(src or preset)
    destination = _normalize_color_value(dst)
    pairs: list[tuple[str, str]] = []
    if source:
        pairs.append(("sequencer_input", source))
        pairs.append(("input_matrix", source))
    if destination:
        pairs.append(("output_matrix", destination))
    return tuple(pairs)


def setparams_to_blender_color_management(
    *,
    range: str | int = "",
    color_primaries: str | int = "",
    color_trc: str | int = "",
    colorspace: str | int = "",
    **_unused: str,
) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    space = _first_color_value(colorspace, color_primaries, color_trc)
    if space:
        pairs.append(("sequencer_input", space))
    for key, value in (
        ("output_primaries", color_primaries),
        ("output_transfer", color_trc),
        ("output_matrix", colorspace),
    ):
        normalized = _normalize_color_value(value)
        if normalized:
            pairs.append((key, normalized))
    normalized_range = _normalize_range_value(range)
    if normalized_range:
        pairs.append(("output_range", normalized_range))
    return tuple(_dedupe_pairs(pairs))


def setrange_to_blender_color_management(
    *,
    range: str | int = "",
    preset: str | int = "",
    **_unused: str,
) -> tuple[tuple[str, str], ...]:
    normalized = _normalize_range_value(range or preset)
    return (("output_range", normalized),) if normalized else ()


def zscale_to_blender_color_management(**args: str | int) -> tuple[tuple[str, str], ...]:
    input_primaries = _first_arg(args, "primariesin", "pin", "iprimaries")
    output_primaries = _first_arg(args, "primaries", "p", "primariesout")
    input_transfer = _first_arg(args, "transferin", "tin", "itrc")
    output_transfer = _first_arg(args, "transfer", "t", "trc")
    input_matrix = _first_arg(args, "matrixin", "min", "ispace")
    output_matrix = _first_arg(args, "matrix", "m", "space")
    input_range = _first_arg(args, "rangein", "rin", "irange")
    output_range = _first_arg(args, "range", "r")

    pairs: list[tuple[str, str]] = []
    sequencer_input = _first_color_value(input_primaries, input_transfer, input_matrix, output_primaries, output_transfer, output_matrix)
    if sequencer_input:
        pairs.append(("sequencer_input", sequencer_input))
    for key, value in (
        ("input_matrix", input_matrix),
        ("output_matrix", output_matrix),
        ("input_primaries", input_primaries),
        ("output_primaries", output_primaries),
        ("input_transfer", input_transfer),
        ("output_transfer", output_transfer),
    ):
        normalized = _normalize_color_value(value)
        if normalized:
            pairs.append((key, normalized))
    for key, value in (("input_range", input_range), ("output_range", output_range)):
        normalized = _normalize_range_value(value)
        if normalized:
            pairs.append((key, normalized))
    return tuple(_dedupe_pairs(pairs))


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


def _first_color_value(*values: str | int) -> str:
    for value in values:
        normalized = _normalize_color_value(value)
        if normalized:
            return normalized
    return ""


def _first_arg(args: dict[str, str | int], *keys: str) -> str | int:
    for key in keys:
        value = args.get(key)
        if value not in (None, ""):
            return value
    return ""


def _normalize_color_value(value: str | int | None) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text in {"auto", "unknown", "unspecified", "-1", "0"}:
        return ""
    aliases = {
        "bt601": "smpte170m",
        "bt470": "bt470bg",
        "bt2020nc": "bt2020",
        "bt2020ncl": "bt2020",
        "iec61966-2-1": "srgb",
        "gamma22": "bt470m",
        "gamma28": "bt470bg",
        "arib-std-b67": "hlg",
        "smpte2084": "pq",
    }
    if text.isdigit():
        return ""
    return aliases.get(text, text)


def _normalize_range_value(value: str | int | None) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text in {"auto", "unknown", "unspecified", "-1", "0"}:
        return ""
    if text in {"1", "limited", "tv", "mpeg"}:
        return "limited"
    if text in {"2", "full", "pc", "jpeg"}:
        return "full"
    return text


def _dedupe_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key, value in pairs:
        if not value:
            continue
        item = (key, value)
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _parse_cmyk_adjustment(value: str) -> tuple[float, float, float, float]:
    parts = str(value or "").replace("/", " ").replace(",", " ").split()
    channels = [_float_percent(part) for part in parts[:4]]
    while len(channels) < 4:
        channels.append(0.0)
    return tuple(_clamp(channel, -1.0, 1.0) for channel in channels[:4])


def _selective_hue_curve_points(
    zone_values: dict[str, tuple[float, float, float, float]],
    scale: float,
) -> dict[int, list[tuple[float, float]]]:
    anchors = (
        (0.0, "reds"),
        (1.0 / 6.0, "yellows"),
        (2.0 / 6.0, "greens"),
        (3.0 / 6.0, "cyans"),
        (4.0 / 6.0, "blues"),
        (5.0 / 6.0, "magentas"),
        (1.0, "reds"),
    )
    hue_points: list[tuple[float, float]] = []
    saturation_points: list[tuple[float, float]] = []
    value_points: list[tuple[float, float]] = []
    for x, name in anchors:
        cyan, magenta, yellow, black = zone_values[name]
        hue_delta = _clamp((magenta - yellow + cyan * 0.45) * 0.035 * scale, -0.16, 0.16)
        saturation_delta = _clamp((abs(cyan) + abs(magenta) + abs(yellow)) * 0.055 * scale - black * 0.025 * scale, -0.22, 0.22)
        value_delta = _clamp((-black * 0.12 - (cyan + magenta + yellow) * 0.018) * scale, -0.24, 0.24)
        hue_points.append((x, _clamp(0.5 + hue_delta, 0.0, 1.0)))
        saturation_points.append((x, _clamp(0.5 + saturation_delta, 0.0, 1.0)))
        value_points.append((x, _clamp(0.5 + value_delta, 0.0, 1.0)))
    return {0: hue_points, 1: saturation_points, 2: value_points}


def _cmyk_to_rgb_balance(value: tuple[float, float, float, float], *, scale: float) -> tuple[float, float, float]:
    cyan, magenta, yellow, black = value
    return (
        _clamp(1.0 - cyan * scale - black * scale * 0.45, 0.35, 1.85),
        _clamp(1.0 - magenta * scale - black * scale * 0.45, 0.35, 1.85),
        _clamp(1.0 - yellow * scale - black * scale * 0.45, 0.35, 1.85),
    )


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


def _rgb_to_hue(color: tuple[float, float, float]) -> float:
    red, green, blue = color
    maximum = max(color)
    minimum = min(color)
    delta = maximum - minimum
    if delta <= 1e-9:
        return 0.0
    if maximum == red:
        hue = ((green - blue) / delta) % 6.0
    elif maximum == green:
        hue = ((blue - red) / delta) + 2.0
    else:
        hue = ((red - green) / delta) + 4.0
    return (hue / 6.0) % 1.0


def _hold_saturation_curve_points(hue: float, similarity: float, blend: float) -> list[tuple[float, float]]:
    hue = hue % 1.0
    width = _clamp(similarity, 1e-5, 1.0) * 0.35
    outside = _clamp(0.5 * _clamp(blend, 0.0, 1.0), 0.0, 0.5)
    points: list[tuple[float, float]] = []
    for index in range(25):
        x = index / 24.0
        distance = abs(x - hue)
        distance = min(distance, 1.0 - distance)
        edge = _clamp((distance - width) / max(width, 1e-5), 0.0, 1.0)
        points.append((x, _mix(0.5, outside, edge)))
    return points


def _simple_lut_expression_curve(expression: str | None) -> list[tuple[float, float]]:
    text = str(expression or "clipval").strip().lower().replace(" ", "")
    if text in {"", "clipval", "val", "clip(val)", "clipval*1", "1*clipval"}:
        return [(0.0, 0.0), (1.0, 1.0)]
    if text in {"negval", "maxval-val", "255-val", "1-val"}:
        return [(0.0, 1.0), (1.0, 0.0)]
    for token in ("clipval", "val"):
        if text.startswith(f"{token}*"):
            return _linear_curve(_float(text.split("*", 1)[1], 1.0), 0.0)
        if text.endswith(f"*{token}"):
            return _linear_curve(_float(text.rsplit("*", 1)[0], 1.0), 0.0)
        if text.startswith(f"{token}+"):
            return _linear_curve(1.0, _lut_offset(text.split("+", 1)[1]))
        if text.startswith(f"{token}-"):
            return _linear_curve(1.0, -_lut_offset(text.split("-", 1)[1]))
    return []


def _linear_curve(scale: float, offset: float) -> list[tuple[float, float]]:
    return [
        (0.0, _clamp(offset, 0.0, 1.0)),
        (0.5, _clamp(0.5 * scale + offset, 0.0, 1.0)),
        (1.0, _clamp(scale + offset, 0.0, 1.0)),
    ]


def _lut_offset(value: str) -> float:
    parsed = _float(value, 0.0)
    if abs(parsed) > 1.0:
        return parsed / 255.0
    return parsed


def _shift_pixels(value: str | float | int | None) -> float:
    return _clamp(_float(value, 0.0), -512.0, 512.0)


def _extract_plane_name(value: str | int | None) -> str:
    text = str(value or "r").strip().lower()
    aliases = {
        "0": "y",
        "1": "u",
        "2": "v",
        "3": "alpha",
        "a": "alpha",
        "alpha": "alpha",
        "luma": "y",
        "lum": "y",
        "gray": "y",
        "grey": "y",
    }
    for part in text.replace("|", "+").replace(",", "+").split("+"):
        key = part.strip()
        if not key:
            continue
        if key in aliases:
            return aliases[key]
        if key in {"y", "u", "v", "r", "g", "b"}:
            return key
    return "r"


def _truthy(value: str | int | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


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


def _hsv_to_rgb(hue: float, saturation: float, value: float) -> tuple[float, float, float]:
    hue = (hue % 360.0) / 60.0
    saturation = _clamp(saturation, 0.0, 1.0)
    value = _clamp(value, 0.0, 1.0)
    chroma = value * saturation
    x = chroma * (1.0 - abs(hue % 2.0 - 1.0))
    match = value - chroma
    if hue < 1.0:
        red, green, blue = chroma, x, 0.0
    elif hue < 2.0:
        red, green, blue = x, chroma, 0.0
    elif hue < 3.0:
        red, green, blue = 0.0, chroma, x
    elif hue < 4.0:
        red, green, blue = 0.0, x, chroma
    elif hue < 5.0:
        red, green, blue = x, 0.0, chroma
    else:
        red, green, blue = chroma, 0.0, x
    return (red + match, green + match, blue + match)


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


def _float_percent(value: str | float | int | None) -> float:
    if isinstance(value, str) and value.strip().endswith("%"):
        return _float(value.strip()[:-1], 0.0) / 100.0
    return _float(value, 0.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
