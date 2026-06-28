"""Translate FFmpeg-style color intent into Blender-native VSE/compositor tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import pi
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
    "shuffleplanes",
    "elbg",
    "unsharp",
    "sobel",
    "prewitt",
    "kirsch",
    "edgedetect",
    "erosion",
    "dilation",
    "convolution",
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
    """Translate supported FFmpeg filter intent into Blender-native tools.

    This intentionally covers color/tone intent that Blender can preview live
    through VSE modifiers, plus compositor-native matte, channel, restoration,
    blur, and geometry operations. Temporal filters such as deflicker, vidstab,
    and frame interpolation remain render tools when there is no equivalent
    native live Blender operation.
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
            eq_stack = eq_to_blender_stack(**args)
            stack.extend(eq_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(eq_stack, "eq", "EQ"))
            supported.append(name)
        elif name == "hue":
            stack.extend(hue_to_blender_stack(**args))
            compositor_nodes.extend(hue_to_blender_compositor(**args))
            supported.append(name)
        elif name == "huesaturation":
            stack.extend(huesaturation_to_blender_stack(**args))
            compositor_nodes.extend(huesaturation_to_blender_compositor(**args))
            supported.append(name)
        elif name == "colorchannelmixer":
            mixer_stack = colorchannelmixer_to_blender_stack(**args)
            stack.extend(mixer_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(mixer_stack, "colorchannelmixer", "Color Channel Mixer"))
            supported.append(name)
            notes.append("Color channel mixer is approximated with Blender Color Balance and White Balance.")
        elif name == "curves":
            curves_stack = curves_to_blender_stack(**args)
            stack.extend(curves_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(curves_stack, "curves", "Curves"))
            supported.append(name)
        elif name == "colorlevels":
            levels_stack = colorlevels_to_blender_stack(**args)
            stack.extend(levels_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(levels_stack, "colorlevels", "Color Levels"))
            supported.append(name)
        elif name == "colorbalance":
            balance_stack = colorbalance_to_blender_stack(**args)
            stack.extend(balance_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(balance_stack, "colorbalance", "Color Balance"))
            supported.append(name)
        elif name == "vibrance":
            vibrance_stack = vibrance_to_blender_stack(**args)
            stack.extend(vibrance_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(vibrance_stack, "vibrance", "Vibrance"))
            supported.append(name)
            notes.append("Vibrance is approximated with Blender Hue Correct and Color Balance saturation controls.")
        elif name == "exposure":
            stack.extend(exposure_to_blender_stack(**args))
            compositor_nodes.extend(exposure_to_blender_compositor(**args))
            supported.append(name)
        elif name == "colortemperature":
            stack.extend(colortemperature_to_blender_stack(**args))
            compositor_nodes.extend(colortemperature_to_blender_compositor(**args))
            supported.append(name)
        elif name == "limiter":
            stack.extend(limiter_to_blender_stack(**args))
            compositor_nodes.extend(limiter_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Limiter is approximated with Blender RGB curves because VSE has no legal-range clamp modifier.")
        elif name == "tonemap":
            stack.extend(tonemap_to_blender_stack(**args))
            compositor_nodes.extend(tonemap_to_blender_compositor(**args))
            supported.append(name)
        elif name == "normalize":
            normalize_stack = normalize_to_blender_stack(**args)
            stack.extend(normalize_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(normalize_stack, "normalize", "Normalize"))
            supported.append(name)
            notes.append("Normalize is approximated as a live Blender curves/tone-map stack; temporal smoothing is not native VSE.")
        elif name == "colorcorrect":
            stack.extend(colorcorrect_to_blender_stack(**args))
            compositor_nodes.extend(colorcorrect_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Colorcorrect is approximated with Blender Lift/Gamma/Gain plus Hue Correct saturation.")
        elif name == "colorcontrast":
            stack.extend(colorcontrast_to_blender_stack(**args))
            compositor_nodes.extend(colorcontrast_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Colorcontrast is approximated with Blender opponent-channel Color Balance controls.")
        elif name == "selectivecolor":
            selective_stack = selectivecolor_to_blender_stack(**args)
            stack.extend(selective_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(selective_stack, "selectivecolor", "Selective Color"))
            supported.append(name)
            notes.append("Selectivecolor is approximated with Blender Hue Correct hue-zone curves and Color Balance tonal zones.")
        elif name == "monochrome":
            stack.extend(monochrome_to_blender_stack(**args))
            compositor_nodes.extend(monochrome_to_blender_compositor(**args))
            supported.append(name)
        elif name == "colorize":
            stack.extend(colorize_to_blender_stack(**args))
            compositor_nodes.extend(colorize_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Colorize is approximated with Blender Hue Correct and Color Balance tinting.")
        elif name == "grayworld":
            grayworld_stack = grayworld_to_blender_stack(**args)
            stack.extend(grayworld_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(grayworld_stack, "grayworld", "Gray World"))
            supported.append(name)
            notes.append("Grayworld is exposed as editable Blender White Balance/Lift-Gamma-Gain controls; use sampled white balance for frame-measured auto values.")
        elif name == "greyedge":
            greyedge_stack = greyedge_to_blender_stack(**args)
            stack.extend(greyedge_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(greyedge_stack, "greyedge", "Grey Edge"))
            supported.append(name)
            notes.append("Greyedge is approximated with editable Blender White Balance plus edge-weighted contrast curves; use sampled white balance for frame-measured auto values.")
        elif name == "negate":
            stack.extend(negate_to_blender_stack(**args))
            compositor_nodes.extend(negate_to_blender_compositor(**args))
            supported.append(name)
        elif name in {"chromahold", "colorhold"}:
            stack.extend(colorhold_to_blender_stack(**args))
            compositor_nodes.extend(colorhold_to_blender_compositor(name, **args))
            supported.append(name)
            notes.append(f"{name} is approximated with Blender Hue Correct saturation-zone curves.")
        elif name == "hsvhold":
            stack.extend(hsvhold_to_blender_stack(**args))
            compositor_nodes.extend(hsvhold_to_blender_compositor(**args))
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
        elif name == "shuffleplanes":
            compositor_nodes.extend(shuffleplanes_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Shuffleplanes is translated to Blender compositor Separate/Combine channel routing nodes.")
        elif name == "elbg":
            compositor_nodes.extend(elbg_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Elbg posterization is translated to Blender compositor Posterize nodes.")
        elif name == "unsharp":
            compositor_nodes.extend(unsharp_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Unsharp is approximated with Blender compositor Filter sharpen/soften nodes.")
        elif name in {"sobel", "prewitt", "kirsch", "edgedetect"}:
            compositor_nodes.extend(edge_filter_to_blender_compositor(name, **args))
            supported.append(name)
            notes.append(f"{name} is translated to Blender compositor Filter edge-detection nodes.")
        elif name in {"erosion", "dilation"}:
            compositor_nodes.extend(morphology_to_blender_compositor(name, **args))
            supported.append(name)
            notes.append(f"{name} is translated to Blender compositor Dilate/Erode matte cleanup nodes.")
        elif name == "convolution":
            compositor_nodes.extend(convolution_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Convolution is translated to Blender compositor Convolve nodes with generated kernel images.")
        elif name in {"avgblur", "boxblur", "gblur"}:
            compositor_nodes.extend(blur_to_blender_compositor(name, **args))
            supported.append(name)
            notes.append(f"{name} is translated to Blender compositor Blur nodes.")
        elif name in {"smartblur", "sab", "yaepblur"}:
            compositor_nodes.extend(edge_preserving_blur_to_blender_compositor(name, **args))
            supported.append(name)
            notes.append(f"{name} is approximated with Blender compositor Bilateral Blur nodes.")
        elif name == "dblur":
            compositor_nodes.extend(directional_blur_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Dblur is translated to Blender compositor Directional Blur nodes.")
        elif name == "scale":
            compositor_nodes.extend(scale_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Scale is translated to Blender compositor Scale nodes for editable live resize intent.")
        elif name == "crop":
            compositor_nodes.extend(crop_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Crop is translated to Blender compositor Crop nodes.")
        elif name == "rotate":
            compositor_nodes.extend(rotate_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Rotate is translated to Blender compositor Rotate nodes; animated expressions are represented by the initial editable value.")
        elif name == "transpose":
            compositor_nodes.extend(transpose_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Transpose is translated to Blender compositor Rotate/Flip nodes.")
        elif name in {"hflip", "vflip"}:
            compositor_nodes.extend(flip_to_blender_compositor(name))
            supported.append(name)
            notes.append(f"{name} is translated to Blender compositor Flip nodes.")
        elif name == "lenscorrection":
            compositor_nodes.extend(lenscorrection_to_blender_compositor(**args))
            supported.append(name)
            notes.append("Lenscorrection is approximated with Blender compositor Lens Distortion controls.")
        elif name in {"hqdn3d", "nlmeans", "bm3d", "owdenoise", "vaguedenoiser", "atadenoise", "median", "dedot", "deband", "deblock"}:
            compositor_nodes.extend(restoration_filter_to_blender_compositor(name, **args))
            supported.append(name)
            notes.append(f"{name} is translated to Blender compositor restoration nodes; temporal behavior is approximated spatially where Blender has no temporal node.")
        elif name == "pseudocolor":
            pseudocolor_stack = pseudocolor_to_blender_stack(**args)
            stack.extend(pseudocolor_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(pseudocolor_stack, "pseudocolor", "Pseudocolor"))
            supported.append(name)
            notes.append("Pseudocolor is approximated with editable Blender Hue Correct curves, RGB curves, and Color Balance palette tinting.")
        elif name in {"lut", "lutrgb", "lutyuv"}:
            lut_stack = lut_to_blender_stack(**args)
            if lut_stack:
                stack.extend(lut_stack)
                compositor_nodes.extend(_stack_to_compositor_nodes(lut_stack, name, name.upper()))
                supported.append(name)
                notes.append(f"{name} linear/identity/negation expressions are approximated with Blender RGB Curves.")
            else:
                unsupported.append(name)
                notes.append(f"{name} uses expressions that do not map safely to native Blender live curves.")
        elif name == "histeq":
            histeq_stack = histeq_to_blender_stack(**args)
            stack.extend(histeq_stack)
            compositor_nodes.extend(_stack_to_compositor_nodes(histeq_stack, "histeq", "Histogram Equalization"))
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


def hue_to_blender_compositor(
    *,
    h: str | float = 0.0,
    H: str | float | None = None,
    s: str | float = 1.0,
    b: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    hue_degrees = _float(h, 0.0)
    if H is not None:
        hue_degrees = _float(H, 0.0) * 57.29577951308232
    return (
        (
            "HUE_SAT",
            {
                "label": "Hue/Saturation",
                "hue": _hue_shift_to_curve_y(hue_degrees),
                "saturation": _clamp(_float(s, 1.0), 0.0, 4.0),
                "value": _clamp(1.0 + _float(b, 0.0), 0.0, 4.0),
                "factor": 1.0,
                "source": "hue",
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


def huesaturation_to_blender_compositor(
    *,
    hue: str | float = 0.0,
    saturation: str | float = 0.0,
    intensity: str | float = 0.0,
    strength: str | float = 1.0,
    **_unused: str,
) -> CompositorStack:
    strength_value = _clamp(_float(strength, 1.0), 0.0, 100.0) / 100.0 if _float(strength, 1.0) > 1.0 else _clamp(_float(strength, 1.0), 0.0, 1.0)
    return (
        (
            "HUE_SAT",
            {
                "label": "Hue/Saturation/Intensity",
                "hue": _hue_shift_to_curve_y(_float(hue, 0.0) * strength_value),
                "saturation": _clamp(1.0 + _float(saturation, 0.0) * strength_value, 0.0, 4.0),
                "value": _clamp(1.0 + _float(intensity, 0.0) * strength_value, 0.0, 4.0),
                "factor": strength_value,
                "source": "huesaturation",
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


def exposure_to_blender_compositor(
    *,
    exposure: str | float = 0.0,
    black: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    exposure_value = _clamp(_float(exposure, 0.0), -10.0, 10.0)
    return (
        (
            "EXPOSURE",
            {
                "label": "Exposure",
                "exposure": exposure_value,
                "black": _clamp(_float(black, 0.0), -1.0, 1.0),
                "source": "exposure",
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


def colortemperature_to_blender_compositor(
    *,
    temperature: str | float = 6500.0,
    mix: str | float = 1.0,
    pl: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    stack = colortemperature_to_blender_stack(temperature=temperature, mix=mix, pl=pl)
    return _stack_to_compositor_nodes(stack, "colortemperature", "Color Temperature")


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


def limiter_to_blender_compositor(
    *,
    min: str | float = 0.0,
    max: str | float = 1.0,
    **_unused: str,
) -> CompositorStack:
    minimum = _normalize_limiter_value(_float(min, 0.0))
    maximum = _normalize_limiter_value(_float(max, 1.0))
    if maximum <= minimum:
        maximum = 1.0 if minimum + 0.01 > 1.0 else minimum + 0.01
    points = _range_curve_points(minimum, maximum, minimum, maximum)
    return (
        (
            "CURVE_RGB",
            {
                "label": "Limiter / Legal Range",
                "__curve_points__": {0: points},
                "minimum": minimum,
                "maximum": maximum,
                "source": "limiter",
            },
        ),
    )


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


def tonemap_to_blender_compositor(
    *,
    tonemap: str | int = "reinhard",
    param: str | float = 0.0,
    desat: str | float = 0.0,
    peak: str | float = 100.0,
    **_unused: str,
) -> CompositorStack:
    stack = tonemap_to_blender_stack(tonemap=tonemap, param=param, desat=desat, peak=peak)
    return _stack_to_compositor_nodes(stack, "tonemap", "Tone Map")


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


def colorcorrect_to_blender_compositor(
    *,
    rl: str | float = 0.0,
    bl: str | float = 0.0,
    rh: str | float = 0.0,
    bh: str | float = 0.0,
    saturation: str | float = 1.0,
    analyze: str | int = 0,
    **_unused: str,
) -> CompositorStack:
    analyze_strength = 1.0 + (0.10 if str(analyze).lower() not in {"0", "manual"} else 0.0)
    shadow_offset = _clamp((_float(rl, 0.0) + _float(bl, 0.0)) * 0.025 * analyze_strength, -0.25, 0.25)
    highlight_gain = _clamp(1.0 + (_float(rh, 0.0) + _float(bh, 0.0)) * 0.075 * analyze_strength, 0.25, 4.0)
    return (
        (
            "COLOR_CORRECTION",
            {
                "label": "Color Correction",
                "saturation": _clamp(_float(saturation, 1.0), 0.0, 4.0),
                "shadow_offset": shadow_offset,
                "highlight_gain": highlight_gain,
                "red_low": _float(rl, 0.0),
                "blue_low": _float(bl, 0.0),
                "red_high": _float(rh, 0.0),
                "blue_high": _float(bh, 0.0),
                "source": "colorcorrect",
                "approximation": "Blender Color Correction exposes tonal scalar controls; FFmpeg red/blue low/high values are kept as editable metadata and approximated as shadow offset/highlight gain.",
            },
        ),
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


def colorcontrast_to_blender_compositor(
    *,
    rc: str | float = 0.0,
    gm: str | float = 0.0,
    by: str | float = 0.0,
    rcw: str | float = 0.0,
    gmw: str | float = 0.0,
    byw: str | float = 0.0,
    pl: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    stack = colorcontrast_to_blender_stack(rc=rc, gm=gm, by=by, rcw=rcw, gmw=gmw, byw=byw, pl=pl)
    nodes = list(_stack_to_compositor_nodes(stack, "colorcontrast", "Color Contrast"))
    for _node_type, settings in nodes:
        settings["red_cyan"] = _float(rc, 0.0)
        settings["green_magenta"] = _float(gm, 0.0)
        settings["blue_yellow"] = _float(by, 0.0)
    return tuple(nodes)


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


def monochrome_to_blender_compositor(
    *,
    cb: str | float = 0.0,
    cr: str | float = 0.0,
    size: str | float = 1.0,
    high: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    high_value = _clamp(_float(high, 0.0), 0.0, 1.0)
    return (
        (
            "HUE_SAT",
            {
                "label": "Monochrome",
                "hue": _hue_shift_to_curve_y((_float(cr, 0.0) - _float(cb, 0.0)) * 12.0),
                "saturation": 0.0,
                "value": _clamp(1.0 + high_value * 0.12 + (_float(size, 1.0) - 1.0) * 0.025, 0.0, 4.0),
                "factor": 1.0,
                "source": "monochrome",
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


def colorize_to_blender_compositor(
    *,
    hue: str | float = 0.0,
    saturation: str | float = 0.5,
    lightness: str | float = 0.5,
    mix: str | float = 1.0,
    **_unused: str,
) -> CompositorStack:
    stack = colorize_to_blender_stack(hue=hue, saturation=saturation, lightness=lightness, mix=mix)
    nodes = list(_stack_to_compositor_nodes(stack, "colorize", "Colorize"))
    tint = _hsl_to_rgb(_float(hue, 0.0), _clamp(_float(saturation, 0.5), 0.0, 1.0), _clamp(_float(lightness, 0.5), 0.0, 1.0))
    for _node_type, settings in nodes:
        settings["mix"] = _clamp(_float(mix, 1.0), 0.0, 1.0)
        settings["tint"] = tint
    return tuple(nodes)


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


def negate_to_blender_compositor(
    *,
    components: str = "y+u+v+r+g+b",
    negate_alpha: str | int | bool = False,
    **_unused: str,
) -> CompositorStack:
    component_set = {part.strip().lower() for part in str(components or "").replace("|", "+").split("+") if part.strip()}
    invert_color = not component_set or bool(component_set & {"y", "u", "v", "r", "g", "b"})
    return (
        (
            "INVERT",
            {
                "label": "Invert",
                "factor": 1.0,
                "invert_color": invert_color,
                "invert_alpha": _truthy(negate_alpha),
                "components": str(components),
                "source": "negate",
            },
        ),
    )


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


def colorhold_to_blender_compositor(
    source: str = "colorhold",
    *,
    color: str = "black",
    similarity: str | float = 0.01,
    blend: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    hue = _rgb_to_hue(_parse_color(color, (0.0, 0.0, 0.0)))
    return (
        (
            "HUE_CORRECT",
            {
                "label": "Color Hold",
                "__curve_points__": {1: _hold_saturation_curve_points(hue, _float(similarity, 0.01), _float(blend, 0.0))},
                "held_color": _parse_color(color, (0.0, 0.0, 0.0)),
                "similarity": _float(similarity, 0.01),
                "blend": _float(blend, 0.0),
                "source": source,
            },
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


def hsvhold_to_blender_compositor(
    *,
    hue: str | float = 0.0,
    sat: str | float = 0.0,
    val: str | float = 0.0,
    similarity: str | float = 0.01,
    blend: str | float = 0.0,
    **_unused: str,
) -> CompositorStack:
    hue_value = (_float(hue, 0.0) % 360.0) / 360.0
    saturation_points = _hold_saturation_curve_points(hue_value, _float(similarity, 0.01), _float(blend, 0.0))
    value_points = [
        (x, _clamp(y + _float(val, 0.0) * 0.08 + _float(sat, 0.0) * 0.04, 0.0, 1.0))
        for x, y in saturation_points
    ]
    return (
        (
            "HUE_CORRECT",
            {
                "label": "HSV Hold",
                "__curve_points__": {1: saturation_points, 2: value_points},
                "hue_degrees": _float(hue, 0.0) % 360.0,
                "similarity": _float(similarity, 0.01),
                "blend": _float(blend, 0.0),
                "source": "hsvhold",
            },
        ),
    )


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


def shuffleplanes_to_blender_compositor(
    *,
    map0: str | int = 0,
    map1: str | int = 1,
    map2: str | int = 2,
    map3: str | int = 3,
    arg0: str | int | None = None,
    arg1: str | int | None = None,
    arg2: str | int | None = None,
    arg3: str | int | None = None,
    **_unused: str,
) -> CompositorStack:
    maps = (
        map0 if arg0 is None else arg0,
        map1 if arg1 is None else arg1,
        map2 if arg2 is None else arg2,
        map3 if arg3 is None else arg3,
    )
    return (
        (
            "PLANE_SHUFFLE",
            {
                "outputs": {
                    "red": _shuffle_plane_name(maps[0]),
                    "green": _shuffle_plane_name(maps[1]),
                    "blue": _shuffle_plane_name(maps[2]),
                    "alpha": _shuffle_plane_name(maps[3]),
                },
                "source": "shuffleplanes",
            },
        ),
    )


def elbg_to_blender_compositor(
    *,
    codebook_length: str | int = 256,
    l: str | int | None = None,
    nb_steps: str | int = 1,
    n: str | int | None = None,
    seed: str | int = -1,
    s: str | int | None = None,
    pal8: str | int | bool = False,
    use_alpha: str | int | bool = False,
    arg0: str | int | None = None,
    arg1: str | int | None = None,
    arg2: str | int | None = None,
    **_unused: str,
) -> CompositorStack:
    length = codebook_length if l is None else l
    length = length if arg0 is None else arg0
    steps_count = nb_steps if n is None else n
    steps_count = steps_count if arg1 is None else arg1
    seed_value = seed if s is None else s
    seed_value = seed_value if arg2 is None else arg2
    include_alpha = _truthy(use_alpha)
    return (
        (
            "POSTERIZE",
            {
                "steps": _posterize_steps(length, include_alpha),
                "codebook_length": max(1, int(round(_float(length, 256.0)))),
                "nb_steps": max(1, int(round(_float(steps_count, 1.0)))),
                "seed": int(round(_float(seed_value, -1.0))),
                "pal8": _truthy(pal8),
                "use_alpha": include_alpha,
                "source": "elbg",
            },
        ),
    )


def unsharp_to_blender_compositor(
    *,
    luma_msize_x: str | int = 5,
    lx: str | int | None = None,
    luma_msize_y: str | int = 5,
    ly: str | int | None = None,
    luma_amount: str | float = 1.0,
    la: str | float | None = None,
    chroma_msize_x: str | int = 5,
    cx: str | int | None = None,
    chroma_msize_y: str | int = 5,
    cy: str | int | None = None,
    chroma_amount: str | float = 0.0,
    ca: str | float | None = None,
    alpha_msize_x: str | int = 5,
    ax: str | int | None = None,
    alpha_msize_y: str | int = 5,
    ay: str | int | None = None,
    alpha_amount: str | float = 0.0,
    aa: str | float | None = None,
    arg0: str | int | None = None,
    arg1: str | int | None = None,
    arg2: str | float | None = None,
    arg3: str | int | None = None,
    arg4: str | int | None = None,
    arg5: str | float | None = None,
    arg6: str | int | None = None,
    arg7: str | int | None = None,
    arg8: str | float | None = None,
    **_unused: str,
) -> CompositorStack:
    lx_value = _unsharp_size(arg0 if arg0 is not None else (lx if lx is not None else luma_msize_x))
    ly_value = _unsharp_size(arg1 if arg1 is not None else (ly if ly is not None else luma_msize_y))
    la_value = _float(arg2 if arg2 is not None else (la if la is not None else luma_amount), 1.0)
    cx_value = _unsharp_size(arg3 if arg3 is not None else (cx if cx is not None else chroma_msize_x))
    cy_value = _unsharp_size(arg4 if arg4 is not None else (cy if cy is not None else chroma_msize_y))
    ca_value = _float(arg5 if arg5 is not None else (ca if ca is not None else chroma_amount), 0.0)
    ax_value = _unsharp_size(arg6 if arg6 is not None else (ax if ax is not None else alpha_msize_x))
    ay_value = _unsharp_size(arg7 if arg7 is not None else (ay if ay is not None else alpha_msize_y))
    aa_value = _float(arg8 if arg8 is not None else (aa if aa is not None else alpha_amount), 0.0)
    amount = la_value + ca_value * 0.35 + aa_value * 0.15
    if abs(amount) < 1e-6:
        amount = max((la_value, ca_value, aa_value), key=abs)
    matrix_scale = max(0.2, (lx_value + ly_value) / 10.0)
    return (
        (
            "FILTER",
            {
                "filter_type": "Box Sharpen" if amount >= 0.0 else "Soften",
                "factor": _clamp(abs(amount) * matrix_scale, 0.0, 2.0),
                "luma_size": (lx_value, ly_value),
                "luma_amount": la_value,
                "chroma_size": (cx_value, cy_value),
                "chroma_amount": ca_value,
                "alpha_size": (ax_value, ay_value),
                "alpha_amount": aa_value,
                "source": "unsharp",
            },
        ),
    )


def edge_filter_to_blender_compositor(
    source: str,
    *,
    planes: str | int = 15,
    scale: str | float = 1.0,
    delta: str | float = 0.0,
    high: str | float = 0.196078,
    low: str | float = 0.0784314,
    mode: str | int = "wires",
    **_unused: str,
) -> CompositorStack:
    name = str(source).strip().lower()
    filter_type = {
        "sobel": "Sobel",
        "prewitt": "Prewitt",
        "kirsch": "Kirsch",
        "edgedetect": "Sobel",
    }.get(name, "Sobel")
    scale_value = abs(_float(scale, 1.0))
    delta_value = _float(delta, 0.0)
    factor = _clamp(scale_value + abs(delta_value) / 255.0, 0.0, 2.0)
    if name == "edgedetect":
        high_value = _clamp(_float(high, 0.196078), 0.0, 1.0)
        low_value = _clamp(_float(low, 0.0784314), 0.0, 1.0)
        factor = _clamp(0.65 + high_value + low_value * 0.5, 0.1, 2.0)
    return (
        (
            "FILTER",
            {
                "label": "Edge Detect" if name == "edgedetect" else f"{filter_type} Edge",
                "filter_type": filter_type,
                "factor": factor,
                "planes": str(planes),
                "scale": scale_value,
                "delta": delta_value,
                "high": _clamp(_float(high, 0.196078), 0.0, 1.0),
                "low": _clamp(_float(low, 0.0784314), 0.0, 1.0),
                "mode": str(mode),
                "source": name,
            },
        ),
    )


def morphology_to_blender_compositor(
    source: str,
    *,
    coordinates: str | int = 255,
    threshold0: str | int = 65535,
    threshold1: str | int = 65535,
    threshold2: str | int = 65535,
    threshold3: str | int = 65535,
    **_unused: str,
) -> CompositorStack:
    name = str(source).strip().lower()
    coordinate_value = int(_clamp(round(_float(coordinates, 255.0)), 0.0, 255.0))
    threshold_values = tuple(
        int(_clamp(round(_float(value, 65535.0)), 0.0, 65535.0))
        for value in (threshold0, threshold1, threshold2, threshold3)
    )
    active_neighbors = max(1, int(coordinate_value).bit_count())
    size = max(1, min(8, round(active_neighbors / 8.0)))
    if name == "erosion":
        size = -size
    return (
        (
            "DILATE_ERODE",
            {
                "label": "Erode" if name == "erosion" else "Dilate",
                "mode": "Steps",
                "size": size,
                "falloff_size": 0.0,
                "falloff": "Smooth",
                "coordinates": coordinate_value,
                "thresholds": threshold_values,
                "source": name,
            },
        ),
    )


def convolution_to_blender_compositor(**options: str | int | float) -> CompositorStack:
    mode = _convolution_mode(options.get("0mode", options.get("mode", "square")))
    primary_matrix = options.get("arg0", options.get("m", options.get("0m")))
    plane_specs = []
    for plane in range(4):
        matrix = options.get(f"{plane}m", primary_matrix)
        values = _parse_convolution_values(matrix)
        width, height, shaped = _shape_convolution_kernel(values, mode)
        rdiv = _convolution_rdiv(options.get(f"{plane}rdiv", options.get("rdiv", options.get("0rdiv"))), shaped)
        bias = _normalize_convolution_bias(options.get(f"{plane}bias", options.get("bias", options.get("0bias"))))
        plane_specs.append(
            {
                "values": tuple(_clamp(value * rdiv, -64.0, 64.0) for value in shaped),
                "raw_values": tuple(shaped),
                "rdiv": rdiv,
                "bias": bias,
                "width": width,
                "height": height,
            }
        )
    width = int(plane_specs[0]["width"])
    height = int(plane_specs[0]["height"])
    primary_count = width * height
    kernel_channels = {
        "red": tuple(plane_specs[0]["values"][:primary_count]),
        "green": tuple(_fit_convolution_values(plane_specs[1]["values"], primary_count, plane_specs[0]["values"])),
        "blue": tuple(_fit_convolution_values(plane_specs[2]["values"], primary_count, plane_specs[0]["values"])),
        "alpha": tuple(_fit_convolution_values(plane_specs[3]["values"], primary_count, plane_specs[0]["values"])),
    }
    return (
        (
            "CONVOLVE",
            {
                "label": "Convolve",
                "kernel": kernel_channels["red"],
                "kernel_channels": kernel_channels,
                "kernel_size": (width, height),
                "normalize": False,
                "rdiv": plane_specs[0]["rdiv"],
                "bias": plane_specs[0]["bias"],
                "plane_bias": tuple(spec["bias"] for spec in plane_specs),
                "mode": mode,
                "source": "convolution",
            },
        ),
    )


def blur_to_blender_compositor(source: str, **options: str | int | float) -> CompositorStack:
    name = str(source).strip().lower()
    if name == "avgblur":
        size_x = _clamp(_float(_option(options, "sizeX", "sizex", "arg0", default=1), 1.0), 1.0, 1024.0)
        size_y = _clamp(_float(_option(options, "sizeY", "sizey", "arg2", default=0), 0.0), 0.0, 1024.0)
        if size_y <= 0.0:
            size_y = size_x
        blur_type = "Flat"
        samples = 1
    elif name == "boxblur":
        radius = _radius_expression(_option(options, "luma_radius", "lr", "arg0", default=2), 2.0)
        power = _clamp(_float(_option(options, "luma_power", "lp", "arg1", default=2), 2.0), 0.0, 12.0)
        scale = max(1.0, power)
        size_x = _clamp(radius * scale, 0.0, 1024.0)
        size_y = size_x
        blur_type = "Flat"
        samples = int(max(1, round(power)))
    else:
        sigma = _clamp(_float(_option(options, "sigma", "arg0", default=0.5), 0.5), 0.0, 1024.0)
        steps = _clamp(_float(_option(options, "steps", "arg1", default=1), 1.0), 1.0, 6.0)
        sigma_v = _float(_option(options, "sigmaV", "sigmav", "arg3", default=-1), -1.0)
        size_x = _clamp(max(0.0, sigma) * (2.0 + steps * 0.35), 0.0, 1024.0)
        size_y = _clamp((sigma_v if sigma_v >= 0.0 else sigma) * (2.0 + steps * 0.35), 0.0, 1024.0)
        blur_type = "Gaussian"
        samples = int(round(steps))
    return (
        (
            "BLUR",
            {
                "label": {
                    "avgblur": "Average Blur",
                    "boxblur": "Box Blur",
                    "gblur": "Gaussian Blur",
                }.get(name, "Blur"),
                "size": (size_x, size_y),
                "blur_type": blur_type,
                "extend_bounds": False,
                "separable": True,
                "samples": samples,
                "planes": str(_option(options, "planes", "arg1" if name == "avgblur" else "arg2", default=15)),
                "source": name,
            },
        ),
    )


def edge_preserving_blur_to_blender_compositor(source: str, **options: str | int | float) -> CompositorStack:
    name = str(source).strip().lower()
    if name == "smartblur":
        radius = _clamp(_float(_option(options, "luma_radius", "lr", "arg0", default=1), 1.0), 0.1, 5.0)
        strength = _float(_option(options, "luma_strength", "ls", "arg1", default=1), 1.0)
        threshold = abs(_float(_option(options, "luma_threshold", "lt", "arg2", default=0), 0.0)) / 30.0
        size = radius * max(0.25, abs(strength))
        threshold = _clamp(0.05 + threshold * 0.45, 0.0, 1.0)
    elif name == "sab":
        radius = _clamp(_float(_option(options, "luma_radius", "lr", "arg0", default=1), 1.0), 0.1, 4.0)
        pre_radius = _clamp(_float(_option(options, "luma_pre_filter_radius", "lpfr", "arg1", default=1), 1.0), 0.1, 2.0)
        strength = _clamp(_float(_option(options, "luma_strength", "ls", "arg2", default=1), 1.0), 0.1, 100.0)
        size = radius + pre_radius * 0.5
        threshold = _clamp(0.04 + strength / 250.0, 0.0, 1.0)
    else:
        radius = _clamp(_float(_option(options, "radius", "r", "arg0", default=3), 3.0), 0.0, 256.0)
        sigma = _clamp(_float(_option(options, "sigma", "s", "arg2", default=128), 128.0), 1.0, 65535.0)
        strength = sigma / 128.0
        size = radius
        threshold = _clamp(sigma / 512.0, 0.0, 1.0)
    return (
        (
            "BILATERAL_BLUR",
            {
                "label": {
                    "smartblur": "Smart Blur",
                    "sab": "Shape Adaptive Blur",
                    "yaepblur": "Edge Preserving Blur",
                }.get(name, "Bilateral Blur"),
                "size": int(_clamp(round(size), 1.0, 128.0)),
                "threshold": threshold,
                "strength": strength,
                "source": name,
            },
        ),
    )


def directional_blur_to_blender_compositor(
    *,
    angle: str | float = 45.0,
    radius: str | float = 5.0,
    planes: str | int = 15,
    arg0: str | float | None = None,
    arg1: str | float | None = None,
    arg2: str | int | None = None,
    **_unused: str,
) -> CompositorStack:
    angle_value = _float(arg0 if arg0 is not None else angle, 45.0) % 360.0
    radius_value = _clamp(_float(arg1 if arg1 is not None else radius, 5.0), 0.0, 8192.0)
    planes_value = arg2 if arg2 is not None else planes
    return (
        (
            "DIRECTIONAL_BLUR",
            {
                "label": "Directional Blur",
                "samples": int(_clamp(round(radius_value * 2.0), 1.0, 256.0)),
                "center": (0.5, 0.5),
                "rotation": 0.0,
                "scale": 1.0,
                "amount": _clamp(radius_value / 100.0, 0.0, 1.0),
                "direction": angle_value * pi / 180.0,
                "angle": angle_value,
                "radius": radius_value,
                "planes": str(planes_value),
                "source": "dblur",
            },
        ),
    )


def scale_to_blender_compositor(
    *,
    w: str | float | int = "iw",
    width: str | float | int | None = None,
    h: str | float | int = "ih",
    height: str | float | int | None = None,
    size: str | None = None,
    s: str | None = None,
    arg0: str | float | int | None = None,
    arg1: str | float | int | None = None,
    force_original_aspect_ratio: str | int = "disable",
    flags: str = "",
    **_unused: str,
) -> CompositorStack:
    size_w, size_h = _parse_size_pair(size or s)
    x_source = arg0 if arg0 is not None else (width if width is not None else (size_w if size_w is not None else w))
    y_source = arg1 if arg1 is not None else (height if height is not None else (size_h if size_h is not None else h))
    x_value = _dimension_or_default(x_source, 1.0)
    y_value = _dimension_or_default(y_source, 1.0)
    numeric_absolute = _is_plain_positive_number(x_source) and _is_plain_positive_number(y_source)
    scale_type = "Absolute" if numeric_absolute and (x_value > 8.0 or y_value > 8.0) else "Relative"
    return (
        (
            "SCALE",
            {
                "label": "Scale",
                "type": scale_type,
                "x": _clamp(x_value, 0.001, 16384.0),
                "y": _clamp(y_value, 0.001, 16384.0),
                "width_expression": str(x_source),
                "height_expression": str(y_source),
                "force_original_aspect_ratio": str(force_original_aspect_ratio),
                "flags": str(flags),
                "source": "scale",
            },
        ),
    )


def crop_to_blender_compositor(
    *,
    w: str | float | int = "iw",
    out_w: str | float | int | None = None,
    h: str | float | int = "ih",
    out_h: str | float | int | None = None,
    x: str | float | int = 0,
    y: str | float | int = 0,
    arg0: str | float | int | None = None,
    arg1: str | float | int | None = None,
    arg2: str | float | int | None = None,
    arg3: str | float | int | None = None,
    keep_aspect: str | int | bool = False,
    exact: str | int | bool = False,
    **_unused: str,
) -> CompositorStack:
    width_source = arg0 if arg0 is not None else (out_w if out_w is not None else w)
    height_source = arg1 if arg1 is not None else (out_h if out_h is not None else h)
    x_source = arg2 if arg2 is not None else x
    y_source = arg3 if arg3 is not None else y
    return (
        (
            "CROP",
            {
                "label": "Crop",
                "x": int(round(_dimension_or_default(x_source, 0.0))),
                "y": int(round(_dimension_or_default(y_source, 0.0))),
                "width": int(round(_clamp(_dimension_or_default(width_source, 1920.0), 1.0, 16384.0))),
                "height": int(round(_clamp(_dimension_or_default(height_source, 1080.0), 1.0, 16384.0))),
                "width_expression": str(width_source),
                "height_expression": str(height_source),
                "x_expression": str(x_source),
                "y_expression": str(y_source),
                "keep_aspect": _truthy(keep_aspect),
                "exact": _truthy(exact),
                "source": "crop",
            },
        ),
    )


def rotate_to_blender_compositor(
    *,
    angle: str | float | int = 0.0,
    a: str | float | int | None = None,
    arg0: str | float | int | None = None,
    fillcolor: str = "black",
    c: str | None = None,
    bilinear: str | int | bool = True,
    **_unused: str,
) -> CompositorStack:
    angle_source = arg0 if arg0 is not None else (a if a is not None else angle)
    return (
        (
            "ROTATE",
            {
                "label": "Rotate",
                "angle": _radians_expression(angle_source, 0.0),
                "angle_expression": str(angle_source),
                "fillcolor": str(c if c is not None else fillcolor),
                "interpolation": "Bilinear" if _truthy(bilinear) else "Nearest",
                "source": "rotate",
            },
        ),
    )


def transpose_to_blender_compositor(
    *,
    dir: str | int = "cclock_flip",
    arg0: str | int | None = None,
    passthrough: str | int = "none",
    **_unused: str,
) -> CompositorStack:
    direction = _transpose_direction(arg0 if arg0 is not None else dir)
    rotate_angle = {
        "cclock_flip": -pi / 2.0,
        "clock": pi / 2.0,
        "cclock": -pi / 2.0,
        "clock_flip": pi / 2.0,
    }.get(direction, -pi / 2.0)
    nodes: list[tuple[str, dict[str, Any]]] = [
        (
            "ROTATE",
            {
                "label": "Transpose Rotate",
                "angle": rotate_angle,
                "angle_expression": direction,
                "interpolation": "Bilinear",
                "passthrough": str(passthrough),
                "source": "transpose",
            },
        )
    ]
    if direction in {"cclock_flip", "clock_flip"}:
        nodes.append(
            (
                "FLIP",
                {
                    "label": "Transpose Flip",
                    "flip_x": False,
                    "flip_y": True,
                    "passthrough": str(passthrough),
                    "source": "transpose",
                },
            )
        )
    return tuple(nodes)


def flip_to_blender_compositor(source: str) -> CompositorStack:
    return (
        (
            "FLIP",
            {
                "label": "Horizontal Flip" if source == "hflip" else "Vertical Flip",
                "flip_x": source == "hflip",
                "flip_y": source == "vflip",
                "source": source,
            },
        ),
    )


def lenscorrection_to_blender_compositor(
    *,
    cx: str | float = 0.5,
    cy: str | float = 0.5,
    k1: str | float = 0.0,
    k2: str | float = 0.0,
    i: str | int = "nearest",
    fc: str = "black@0",
    **_unused: str,
) -> CompositorStack:
    k1_value = _clamp(_float(k1, 0.0), -1.0, 1.0)
    k2_value = _clamp(_float(k2, 0.0), -1.0, 1.0)
    return (
        (
            "LENS_DISTORTION",
            {
                "label": "Lens Correction",
                "distortion": _clamp(k1_value + k2_value * 0.5, -1.0, 1.0),
                "dispersion": _clamp(abs(k2_value) * 0.05, 0.0, 1.0),
                "fit": True,
                "center": (_clamp(_float(cx, 0.5), 0.0, 1.0), _clamp(_float(cy, 0.5), 0.0, 1.0)),
                "interpolation": str(i),
                "fillcolor": str(fc),
                "source": "lenscorrection",
                "approximation": "Blender Lens Distortion exposes radial distortion/dispersion; FFmpeg center and fill color are tracked as editable metadata.",
            },
        ),
    )


def restoration_filter_to_blender_compositor(source: str, **options: str | int | float) -> CompositorStack:
    name = str(source).strip().lower()
    if name in {"hqdn3d", "nlmeans", "bm3d", "owdenoise", "vaguedenoiser", "atadenoise"}:
        return _denoise_to_blender_compositor(name, options)
    if name in {"median", "dedot"}:
        return _despeckle_to_blender_compositor(name, options)
    if name == "deband":
        return _deband_to_blender_compositor(options)
    if name == "deblock":
        return _deblock_to_blender_compositor(options)
    return ()


def _denoise_to_blender_compositor(source: str, options: dict[str, object]) -> CompositorStack:
    if source == "hqdn3d":
        luma_spatial = _float(_option(options, "luma_spatial", "arg0", default=1.5), 1.5)
        chroma_spatial = _float(_option(options, "chroma_spatial", "arg1", default=luma_spatial), luma_spatial)
        luma_tmp = _float(_option(options, "luma_tmp", "arg2", default=0.0), 0.0)
        chroma_tmp = _float(_option(options, "chroma_tmp", "arg3", default=0.0), 0.0)
        strength = luma_spatial + chroma_spatial * 0.75 + luma_tmp * 0.30 + chroma_tmp * 0.20
    elif source == "nlmeans":
        strength = _float(_option(options, "s", "arg0", default=1.0), 1.0) + _float(_option(options, "p", "arg1", default=7), 7.0) / 12.0 + _float(_option(options, "r", "arg2", default=15), 15.0) / 24.0
    elif source == "bm3d":
        strength = _float(_option(options, "sigma", "arg0", default=1.0), 1.0) + _float(_option(options, "group", default=1), 1.0) / 48.0 + _float(_option(options, "range", default=9), 9.0) / 32.0
    elif source == "owdenoise":
        strength = (_float(_option(options, "luma_strength", "ls", "arg1", default=1.0), 1.0) + _float(_option(options, "chroma_strength", "cs", "arg2", default=1.0), 1.0)) / 2.0
    elif source == "vaguedenoiser":
        threshold = _float(_option(options, "threshold", "arg0", default=2.0), 2.0)
        percent = _float(_option(options, "percent", "arg3", default=85.0), 85.0) / 100.0
        strength = threshold * percent
    else:
        window = _float(_option(options, "s", "arg0", default=9), 9.0)
        sigma = _float(_option(options, "0s", default=32767.0), 32767.0) / 32767.0
        strength = window / 6.0 + sigma
    strength = _clamp(strength, 0.0, 30.0)
    quality = "High" if strength >= 2.5 else "Balanced"
    prefilter = "Accurate" if strength >= 1.0 else "Fast"
    return (
        (
            "DENOISE",
            {
                "label": {
                    "hqdn3d": "High Quality Denoise",
                    "nlmeans": "Non-Local Means Denoise",
                    "bm3d": "BM3D Denoise",
                    "owdenoise": "Wavelet Denoise",
                    "vaguedenoiser": "Wavelet Threshold Denoise",
                    "atadenoise": "Adaptive Temporal Denoise",
                }.get(source, "Denoise"),
                "hdr": strength >= 6.0,
                "prefilter": prefilter,
                "quality": quality,
                "strength": strength,
                "source": source,
                "approximation": "Blender compositor Denoise is spatial; FFmpeg temporal accumulation is represented as editable spatial denoise strength.",
            },
        ),
    )


def _despeckle_to_blender_compositor(source: str, options: dict[str, object]) -> CompositorStack:
    if source == "median":
        radius = _clamp(_float(_option(options, "radius", "arg0", default=1), 1.0), 1.0, 127.0)
        radius_v = _float(_option(options, "radiusV", "radiusv", "arg2", default=0), 0.0)
        percentile = _clamp(_float(_option(options, "percentile", "arg3", default=0.5), 0.5), 0.0, 1.0)
        factor = _clamp((radius + max(radius_v, radius) * 0.5) / 8.0, 0.05, 1.0)
        color_threshold = _clamp(0.15 + abs(percentile - 0.5), 0.0, 1.0)
        neighbor_threshold = _clamp(0.25 + radius / 16.0, 0.0, 1.0)
    else:
        lt = _clamp(_float(_option(options, "lt", "arg1", default=0.079), 0.079), 0.0, 1.0)
        tl = _clamp(_float(_option(options, "tl", "arg2", default=0.079), 0.079), 0.0, 1.0)
        tc = _clamp(_float(_option(options, "tc", "arg3", default=0.058), 0.058), 0.0, 1.0)
        ct = _clamp(_float(_option(options, "ct", "arg4", default=0.019), 0.019), 0.0, 1.0)
        factor = _clamp(0.35 + (lt + tl + tc + ct), 0.0, 1.0)
        color_threshold = _clamp(lt + ct, 0.0, 1.0)
        neighbor_threshold = _clamp(tl + tc, 0.0, 1.0)
    return (
        (
            "DESPECKLE",
            {
                "label": "Median Despeckle" if source == "median" else "Dot Crawl Despeckle",
                "factor": factor,
                "color_threshold": color_threshold,
                "neighbor_threshold": neighbor_threshold,
                "source": source,
            },
        ),
    )


def _deband_to_blender_compositor(options: dict[str, object]) -> CompositorStack:
    thresholds = (
        _float(_option(options, "1thr", default=0.02), 0.02),
        _float(_option(options, "2thr", default=0.02), 0.02),
        _float(_option(options, "3thr", default=0.02), 0.02),
        _float(_option(options, "4thr", default=0.02), 0.02),
    )
    range_value = abs(_float(_option(options, "range", "r", "arg4", default=16), 16.0))
    threshold = _clamp(sum(thresholds) / len(thresholds) * 8.0, 0.0, 1.0)
    return (
        (
            "BILATERAL_BLUR",
            {
                "label": "Deband Smooth",
                "size": int(_clamp(round(range_value / 4.0), 1.0, 128.0)),
                "threshold": threshold,
                "strength": range_value,
                "source": "deband",
            },
        ),
    )


def _deblock_to_blender_compositor(options: dict[str, object]) -> CompositorStack:
    block = _clamp(_float(_option(options, "block", "arg1", default=8), 8.0), 4.0, 512.0)
    alpha = _clamp(_float(_option(options, "alpha", "arg2", default=0.098), 0.098), 0.0, 1.0)
    beta = _clamp(_float(_option(options, "beta", "arg3", default=0.05), 0.05), 0.0, 1.0)
    gamma = _clamp(_float(_option(options, "gamma", "arg4", default=0.05), 0.05), 0.0, 1.0)
    delta = _clamp(_float(_option(options, "delta", "arg5", default=0.05), 0.05), 0.0, 1.0)
    return (
        (
            "ANTI_ALIASING",
            {
                "label": "Deblock Smoothing",
                "threshold": _clamp(alpha + beta * 0.5, 0.0, 1.0),
                "contrast_limit": _clamp(1.0 + block / 8.0, 1.0, 12.0),
                "corner_rounding": _clamp(gamma + delta + block / 256.0, 0.0, 1.0),
                "block": block,
                "source": "deblock",
            },
        ),
    )


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
        positional_index = 0
        for part in arg_text.split(":"):
            if not part:
                continue
            if "=" in part:
                key, value = part.split("=", 1)
                args[key.strip()] = value.strip().strip("'\"")
            else:
                value = part.strip().strip("'\"")
                args.setdefault("preset", value)
                args[f"arg{positional_index}"] = value
                positional_index += 1
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


def _stack_to_compositor_nodes(stack: BlenderStack, source: str, label: str) -> CompositorStack:
    type_map = {
        "BRIGHT_CONTRAST": "BRIGHT_CONTRAST",
        "COLOR_BALANCE": "COLOR_BALANCE",
        "WHITE_BALANCE": "COLOR_BALANCE",
        "CURVES": "CURVE_RGB",
        "HUE_CORRECT": "HUE_CORRECT",
        "TONEMAP": "TONEMAP",
    }
    nodes: list[tuple[str, dict[str, Any]]] = []
    for index, (modifier_type, settings) in enumerate(stack, start=1):
        compositor_type = type_map.get(modifier_type)
        if compositor_type is None:
            continue
        copied = dict(settings)
        copied["source"] = source
        copied.setdefault("label", f"{label} {_modifier_label(modifier_type)}" if len(stack) > 1 else label)
        copied["modifier_type"] = modifier_type
        copied["sequence_index"] = index
        nodes.append((compositor_type, copied))
    return tuple(nodes)


def _modifier_label(modifier_type: str) -> str:
    return modifier_type.replace("_", " ").title()


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


def _shuffle_plane_name(value: str | int | None) -> str:
    text = str(value if value is not None else "0").strip().lower()
    aliases = {
        "0": "red",
        "1": "green",
        "2": "blue",
        "3": "alpha",
        "r": "red",
        "red": "red",
        "g": "green",
        "green": "green",
        "b": "blue",
        "blue": "blue",
        "a": "alpha",
        "alpha": "alpha",
    }
    return aliases.get(text, "red")


def _posterize_steps(codebook_length: str | int | None, use_alpha: bool = False) -> float:
    colors = max(1.0, _float(codebook_length, 256.0))
    channels = 4.0 if use_alpha else 3.0
    return float(_clamp(round(colors ** (1.0 / channels)), 2.0, 256.0))


def _unsharp_size(value: str | int | None) -> int:
    parsed = int(round(_float(value, 5.0)))
    parsed = int(_clamp(float(parsed), 3.0, 23.0))
    return parsed if parsed % 2 == 1 else min(23, parsed + 1)


def _option(options: dict[str, object], *keys: str, default=None):
    for key in keys:
        value = options.get(key)
        if value not in (None, ""):
            return value
    return default


def _parse_size_pair(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return (None, None)
    text = str(value).strip().lower()
    aliases = {
        "hd720": ("1280", "720"),
        "hd1080": ("1920", "1080"),
        "ntsc": ("720", "480"),
        "pal": ("720", "576"),
        "vga": ("640", "480"),
        "qvga": ("320", "240"),
    }
    if text in aliases:
        return aliases[text]
    for separator in ("x", "X"):
        if separator in str(value):
            left, right = str(value).split(separator, 1)
            return (left.strip(), right.strip())
    return (None, None)


def _dimension_or_default(value: str | float | int | None, default: float) -> float:
    parsed = _numeric_expression(value, float("nan"))
    if parsed == parsed and parsed > 0.0:
        return parsed
    text = str(value or "").strip().lower()
    factor = _variable_scale_factor(text)
    if factor == factor and factor > 0.0:
        return factor
    return default


def _is_plain_positive_number(value: str | float | int | None) -> bool:
    parsed = _float(value, float("nan"))
    return parsed == parsed and parsed > 0.0


def _variable_scale_factor(text: str) -> float:
    normalized = text.replace("in_w", "iw").replace("in_h", "ih").replace("out_w", "ow").replace("out_h", "oh")
    for token in ("iw", "ih"):
        if token not in normalized:
            continue
        compact = normalized.replace(" ", "")
        if compact == token:
            return 1.0
        if compact.startswith(f"{token}*"):
            return _numeric_expression(compact.split("*", 1)[1], float("nan"))
        if compact.endswith(f"*{token}"):
            return _numeric_expression(compact.rsplit("*", 1)[0], float("nan"))
        if compact.startswith(f"{token}/"):
            divisor = _numeric_expression(compact.split("/", 1)[1], float("nan"))
            if divisor == divisor and abs(divisor) > 1e-9:
                return 1.0 / divisor
    return float("nan")


def _radians_expression(value: str | float | int | None, default: float) -> float:
    text = str(value or "").strip().lower()
    if text.endswith("deg"):
        return _numeric_expression(text[:-3], 0.0) * pi / 180.0
    return _numeric_expression(value, default)


def _numeric_expression(value: str | float | int | None, default: float) -> float:
    parsed = _float(value, float("nan"))
    if parsed == parsed:
        return parsed
    text = str(value or "").strip().lower()
    if not text:
        return default
    normalized = text.replace("pi", str(pi))
    allowed = set("0123456789.+-*/() e")
    if any(character not in allowed for character in normalized):
        return default
    try:
        return float(eval(normalized, {"__builtins__": {}}, {}))
    except Exception:
        return default


def _transpose_direction(value: str | int | None) -> str:
    text = str(value if value is not None else "cclock_flip").strip().lower()
    aliases = {
        "0": "cclock_flip",
        "cclock_flip": "cclock_flip",
        "ccw_flip": "cclock_flip",
        "1": "clock",
        "clock": "clock",
        "cw": "clock",
        "2": "cclock",
        "cclock": "cclock",
        "ccw": "cclock",
        "3": "clock_flip",
        "clock_flip": "clock_flip",
        "cw_flip": "clock_flip",
    }
    return aliases.get(text, "cclock_flip")


def _radius_expression(value: str | int | float | None, default: float) -> float:
    parsed = _float(value, float("nan"))
    if parsed == parsed:
        return parsed
    text = str(value or "").replace("/", " ").replace("*", " ").replace("+", " ").replace("-", " ")
    for token in text.split():
        parsed = _float(token, float("nan"))
        if parsed == parsed:
            return parsed
    return default


def _parse_convolution_values(value: str | int | float | None) -> tuple[float, ...]:
    text = str(value or "").replace(",", " ").replace(";", " ").replace("|", " ")
    values = tuple(_float(part, 0.0) for part in text.split())
    return values or (0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0)


def _convolution_mode(value: str | int | float | None) -> str:
    text = str(value or "square").strip().lower()
    return {"0": "square", "1": "row", "2": "column"}.get(text, text if text in {"square", "row", "column"} else "square")


def _shape_convolution_kernel(values: tuple[float, ...], mode: str) -> tuple[int, int, tuple[float, ...]]:
    if mode == "row":
        width = max(1, min(31, len(values)))
        return width, 1, _fit_convolution_values(values, width)
    if mode == "column":
        height = max(1, min(31, len(values)))
        return 1, height, _fit_convolution_values(values, height)
    size = int(round(len(values) ** 0.5))
    if size * size != len(values):
        size = 3
    size = int(_clamp(float(size), 1.0, 31.0))
    if size % 2 == 0:
        size = max(1, size - 1)
    return size, size, _fit_convolution_values(values, size * size)


def _fit_convolution_values(
    values: tuple[float, ...],
    count: int,
    fallback: tuple[float, ...] | None = None,
) -> tuple[float, ...]:
    source = values or fallback or ()
    fitted = list(source[:count])
    while len(fitted) < count:
        fitted.append(0.0)
    if not values and count:
        fitted[count // 2] = 1.0
    return tuple(fitted)


def _convolution_rdiv(value: str | int | float | None, kernel: tuple[float, ...]) -> float:
    parsed = _float(value, 0.0)
    if parsed > 0.0:
        return parsed
    total = sum(kernel)
    if abs(total) > 1e-6:
        return 1.0 / total
    return 1.0


def _normalize_convolution_bias(value: str | int | float | None) -> float:
    parsed = _float(value, 0.0)
    if abs(parsed) > 1.0:
        return _clamp(parsed / 255.0, -1.0, 1.0)
    return _clamp(parsed, -1.0, 1.0)


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
