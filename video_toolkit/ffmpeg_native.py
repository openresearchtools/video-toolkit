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
        elif name in {"normalize", "unsharp"}:
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

