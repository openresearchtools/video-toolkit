"""Shared filter catalog for Blender UI, CLI, and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .ffmpeg_native import translate_filter_chain


ENGINE_BLENDER_MODIFIER = "blender_modifier"
ENGINE_FFMPEG = "ffmpeg"
ENGINE_COMPOSITOR = "compositor"
BlenderStack = tuple[tuple[str, dict[str, Any]], ...]


@dataclass(frozen=True)
class VideoTool:
    """One-click video tool definition."""

    id: str
    label: str
    category: str
    engine: str
    description: str
    blender_modifier: str | None = None
    blender_settings: dict[str, Any] = field(default_factory=dict)
    blender_stack: tuple[tuple[str, dict[str, Any]], ...] = ()
    compositor_stack: tuple[tuple[str, dict[str, Any]], ...] = ()
    ffmpeg_filter: str | None = None
    ffmpeg_filter_after_stabilize: str | None = None
    two_pass_stabilize: bool = False
    slow: bool = False

    @property
    def is_blender_modifier(self) -> bool:
        return self.engine == ENGINE_BLENDER_MODIFIER

    @property
    def blender_modifiers(self) -> tuple[str, ...]:
        if self.blender_stack:
            return tuple(modifier for modifier, _settings in self.blender_stack)
        return (self.blender_modifier,) if self.blender_modifier else ()

    @property
    def is_ffmpeg(self) -> bool:
        return self.engine == ENGINE_FFMPEG

    @property
    def is_compositor(self) -> bool:
        return self.engine == ENGINE_COMPOSITOR


def _bright_contrast(bright: float = 0.0, contrast: float = 0.0) -> tuple[str, dict[str, Any]]:
    return ("BRIGHT_CONTRAST", {"bright": bright, "contrast": contrast})


def _color_balance(
    *,
    lift: tuple[float, float, float] = (1.0, 1.0, 1.0),
    gamma: tuple[float, float, float] = (1.0, 1.0, 1.0),
    gain: tuple[float, float, float] = (1.0, 1.0, 1.0),
    color_multiply: float = 1.0,
) -> tuple[str, dict[str, Any]]:
    return (
        "COLOR_BALANCE",
        {
            "color_balance.correction_method": "LIFT_GAMMA_GAIN",
            "color_balance.lift": lift,
            "color_balance.gamma": gamma,
            "color_balance.gain": gain,
            "color_multiply": color_multiply,
        },
    )


def _asc_cdl(
    *,
    offset: tuple[float, float, float] = (1.0, 1.0, 1.0),
    power: tuple[float, float, float] = (1.0, 1.0, 1.0),
    slope: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> tuple[str, dict[str, Any]]:
    return (
        "COLOR_BALANCE",
        {
            "color_balance.correction_method": "OFFSET_POWER_SLOPE",
            "color_balance.offset": offset,
            "color_balance.power": power,
            "color_balance.slope": slope,
        },
    )


def _tonemap(
    *,
    tonemap_type: str = "RD_PHOTORECEPTOR",
    intensity: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    key: float | None = None,
    offset: float | None = None,
    adaptation: float | None = None,
    correction: float | None = None,
) -> tuple[str, dict[str, Any]]:
    settings: dict[str, Any] = {
        "tonemap_type": tonemap_type,
        "intensity": intensity,
        "contrast": contrast,
        "gamma": gamma,
    }
    if key is not None:
        settings["key"] = key
    if offset is not None:
        settings["offset"] = offset
    if adaptation is not None:
        settings["adaptation"] = adaptation
    if correction is not None:
        settings["correction"] = correction
    return ("TONEMAP", settings)


def _white_balance(value: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> tuple[str, dict[str, Any]]:
    return ("WHITE_BALANCE", {"white_value": value})


def _curves() -> tuple[str, dict[str, Any]]:
    return ("CURVES", {})


def _hue_correct() -> tuple[str, dict[str, Any]]:
    return ("HUE_CORRECT", {})


def _curve_points(curve_points: dict[int, list[tuple[float, float]]]) -> tuple[str, dict[str, Any]]:
    return ("CURVES", {"__curve_points__": curve_points})


_AUTO_ENHANCE_STACK = translate_filter_chain("eq=contrast=1.08:saturation=1.08:gamma=1.02").stack
_NEUTRAL_GRADE_STACK = translate_filter_chain("eq=contrast=1.04:saturation=1.03:gamma=1.00").stack
_PUNCHY_COLOR_STACK = translate_filter_chain("eq=contrast=1.14:saturation=1.18:gamma=0.98").stack
_SOFT_CONTRAST_STACK = translate_filter_chain("eq=contrast=0.94:saturation=1.03:gamma=1.04").stack
_EXPOSURE_LIFT_STACK = translate_filter_chain("eq=brightness=0.035:contrast=1.03:gamma=1.08:saturation=1.02").stack
_GAMMA_BRIGHTEN_STACK = translate_filter_chain("eq=gamma=1.18:gamma_weight=0.82").stack
_GAMMA_DEEPEN_STACK = translate_filter_chain("eq=gamma=0.88:contrast=1.04").stack
_WARM_BALANCE_STACK = translate_filter_chain("colorchannelmixer=rr=1.04:gg=1.00:bb=0.96,eq=saturation=1.03").stack
_COOL_BALANCE_STACK = translate_filter_chain("colorchannelmixer=rr=0.97:gg=1.00:bb=1.04,eq=saturation=1.02").stack
_SATURATION_BOOST_STACK = translate_filter_chain("hue=s=1.25").stack
_SATURATION_REDUCE_STACK = translate_filter_chain("hue=s=0.75").stack
_MONOCHROME_STACK = translate_filter_chain("hue=s=0").stack
_FADED_FILM_STACK = translate_filter_chain("eq=brightness=0.025:contrast=0.90:gamma=1.08:saturation=0.82").stack
_HIGH_CONTRAST_CURVE_STACK = translate_filter_chain("curves=preset=strong_contrast").stack
_MEDIUM_CONTRAST_CURVE_STACK = translate_filter_chain("curves=preset=medium_contrast").stack
_LEVELS_EXPAND_STACK = translate_filter_chain("colorlevels=rimin=0.02:gimin=0.02:bimin=0.02:rimax=0.98:gimax=0.98:bimax=0.98").stack
_LEVELS_SOFT_CLAMP_STACK = translate_filter_chain("colorlevels=romin=0.03:gomin=0.03:bomin=0.03:romax=0.96:gomax=0.96:bomax=0.96").stack
_SHADOW_HIGHLIGHT_BALANCE_STACK = translate_filter_chain("colorbalance=rs=0.04:gs=0.03:bs=0.06:rm=0.02:gm=0.02:bm=0.04:rh=0.03:gh=0.02:bh=0.00:pl=1").stack
_VIBRANCE_STACK = translate_filter_chain("vibrance=intensity=0.55:rbal=1.05:gbal=1.02:bbal=0.96").stack
_SKIN_SAFE_VIBRANCE_STACK = translate_filter_chain("vibrance=intensity=0.32:rbal=0.96:gbal=1.02:bbal=1.00").stack
_EXPOSURE_PROTECT_STACK = translate_filter_chain("exposure=exposure=0.42:black=0.03").stack
_TEMP_WARM_STACK = translate_filter_chain("colortemperature=temperature=5200:mix=0.75:pl=1").stack
_TEMP_COOL_STACK = translate_filter_chain("colortemperature=temperature=7600:mix=0.75:pl=1").stack
_LEGAL_RANGE_STACK = translate_filter_chain("limiter=min=16:max=235").stack
_HDR_TONE_COMPRESS_STACK = translate_filter_chain("tonemap=tonemap=mobius:param=0.35:desat=0.4:peak=400").stack
_SELECTIVE_COLOR_TRANSLATION = translate_filter_chain(
    "selectivecolor=reds=0.10 -0.04 -0.02 0.00:blues=-0.04 0.02 0.10 0.03:whites=0.02 0.00 -0.08 0.01"
)
_COLORIZE_TRANSLATION = translate_filter_chain("colorize=hue=210:saturation=0.50:lightness=0.55:mix=0.70")
_GREY_EDGE_TRANSLATION = translate_filter_chain("greyedge=difford=2:minknorm=5:sigma=2")
_PSEUDOCOLOR_TRANSLATION = translate_filter_chain("pseudocolor=preset=viridis:opacity=0.85:index=1")
_LUT_INVERT_TRANSLATION = translate_filter_chain("lutrgb=r=negval:g=val*0.9:b=val+24")
_HISTOGRAM_EQUALIZE_TRANSLATION = translate_filter_chain("histeq=strength=0.42:intensity=0.30:antibanding=1")
_COLOR_HOLD_TRANSLATION = translate_filter_chain("colorhold=color=blue:similarity=0.18:blend=0.15")
_HSV_HOLD_TRANSLATION = translate_filter_chain("hsvhold=hue=210:sat=0.75:val=0.85:similarity=0.12:blend=0.08")
_BLACK_POINT_CLEANUP_STACK = (
    _bright_contrast(bright=-0.008, contrast=4.0),
    _curve_points({0: [(0.0, 0.0), (0.08, 0.035), (0.50, 0.50), (1.0, 1.0)]}),
)
_WHITE_POINT_RECOVERY_STACK = (
    _tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.18, contrast=0.04, gamma=0.96),
    _curve_points({0: [(0.0, 0.0), (0.50, 0.50), (0.88, 0.84), (1.0, 0.96)]}),
)
_LUMA_S_CURVE_STACK = (
    _bright_contrast(bright=0.0, contrast=6.0),
    _curve_points({0: [(0.0, 0.0), (0.18, 0.12), (0.50, 0.50), (0.82, 0.90), (1.0, 1.0)]}),
)
_RED_GAMMA_TRIM_STACK = (
    _color_balance(gamma=(1.08, 1.0, 1.0), gain=(1.03, 1.0, 0.99)),
    _white_balance((1.03, 1.0, 0.99)),
)
_GREEN_GAMMA_TRIM_STACK = (
    _color_balance(gamma=(1.0, 1.08, 1.0), gain=(1.0, 1.03, 1.0)),
    _white_balance((1.0, 1.03, 1.0)),
)
_BLUE_GAMMA_TRIM_STACK = (
    _color_balance(gamma=(1.0, 1.0, 1.08), gain=(0.99, 1.0, 1.03)),
    _white_balance((0.99, 1.0, 1.03)),
)
_MAGENTA_GREEN_TINT_STACK = (
    _white_balance((1.02, 0.98, 1.02)),
    _color_balance(gamma=(1.015, 0.985, 1.015), gain=(1.02, 0.98, 1.02)),
)
_GREEN_CAST_REPAIR_STACK = (
    _white_balance((1.03, 0.94, 1.03)),
    _color_balance(lift=(1.01, 0.98, 1.01), gamma=(1.03, 0.96, 1.03), gain=(1.02, 0.98, 1.02)),
)
_SHADOW_COOL_TINT_STACK = (
    _color_balance(lift=(0.98, 1.00, 1.06), gamma=(0.99, 1.00, 1.02), gain=(1.0, 1.0, 1.0)),
    _curve_points({0: [(0.0, 0.02), (0.25, 0.23), (1.0, 1.0)]}),
)
_HIGHLIGHT_WARM_TINT_STACK = (
    _color_balance(lift=(1.0, 1.0, 1.0), gamma=(1.01, 1.0, 0.99), gain=(1.06, 1.02, 0.96)),
    _tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.08, contrast=0.06, gamma=1.0),
)
_SKIN_TONE_ISOLATION_STACK = (
    _color_balance(gamma=(1.035, 1.015, 0.985), gain=(1.025, 1.01, 0.985), color_multiply=1.02),
    ("HUE_CORRECT", {"__hue_correct__": {"saturation": 0.56, "value": 0.52}}),
)
_PRIMARY_COLOR_BOARD_STACK = (
    _bright_contrast(bright=0.0, contrast=6.0),
    _color_balance(
        lift=(0.99, 0.99, 0.99),
        gamma=(1.02, 1.02, 1.02),
        gain=(1.04, 1.04, 1.04),
        color_multiply=1.01,
    ),
    _asc_cdl(offset=(1.0, 1.0, 1.0), power=(0.98, 0.98, 0.98), slope=(1.03, 1.03, 1.03)),
    _curve_points({0: [(0.0, 0.0), (0.18, 0.14), (0.50, 0.50), (0.82, 0.88), (1.0, 1.0)]}),
    _tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.07, contrast=0.08, gamma=1.0),
    _hue_correct(),
)
_LOG_ZONE_COLOR_BOARD_STACK = (
    _color_balance(
        lift=(1.035, 1.025, 1.015),
        gamma=(1.015, 1.015, 1.015),
        gain=(0.985, 0.990, 1.000),
        color_multiply=1.0,
    ),
    _curve_points({0: [(0.0, 0.015), (0.22, 0.19), (0.50, 0.50), (0.78, 0.84), (1.0, 0.985)]}),
    _tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.10, contrast=0.10, gamma=0.99),
)
_ASC_CDL_FINISH_STACK = (
    _asc_cdl(offset=(1.005, 1.000, 0.995), power=(0.985, 0.990, 1.000), slope=(1.045, 1.035, 1.025)),
    _bright_contrast(bright=0.0, contrast=5.0),
    _curve_points({0: [(0.0, 0.0), (0.28, 0.24), (0.72, 0.78), (1.0, 1.0)]}),
    ("HUE_CORRECT", {"__hue_correct__": {"saturation": 0.54, "value": 0.50}}),
)
_SIX_VECTOR_HUE_BOARD_STACK = (
    (
        "HUE_CORRECT",
        {
            "__curve_points__": {
                0: [(0.00, 0.50), (0.08, 0.505), (0.16, 0.497), (0.33, 0.500), (0.50, 0.503), (0.66, 0.498), (0.83, 0.502), (1.0, 0.50)],
                1: [(0.00, 0.53), (0.08, 0.56), (0.16, 0.54), (0.33, 0.51), (0.50, 0.52), (0.66, 0.55), (0.83, 0.53), (1.0, 0.53)],
                2: [(0.00, 0.50), (0.08, 0.515), (0.16, 0.505), (0.33, 0.50), (0.50, 0.505), (0.66, 0.512), (0.83, 0.505), (1.0, 0.50)],
            }
        },
    ),
    _color_balance(gamma=(1.01, 1.0, 1.01), gain=(1.015, 1.0, 1.015), color_multiply=1.02),
)
_SECONDARY_SKIN_VECTOR_STACK = (
    (
        "HUE_CORRECT",
        {
            "__curve_points__": {
                0: [(0.00, 0.50), (0.06, 0.503), (0.10, 0.505), (0.16, 0.502), (0.24, 0.50), (1.0, 0.50)],
                1: [(0.00, 0.50), (0.06, 0.535), (0.10, 0.555), (0.16, 0.535), (0.24, 0.50), (1.0, 0.50)],
                2: [(0.00, 0.50), (0.06, 0.512), (0.10, 0.525), (0.16, 0.512), (0.24, 0.50), (1.0, 0.50)],
            }
        },
    ),
    _color_balance(gamma=(1.025, 1.010, 0.990), gain=(1.020, 1.008, 0.990), color_multiply=1.01),
    _tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.04, contrast=0.04, gamma=1.0),
)
_PALETTE_SEPARATION_BOARD_STACK = (
    (
        "HUE_CORRECT",
        {
            "__curve_points__": {
                1: [(0.00, 0.53), (0.12, 0.55), (0.25, 0.50), (0.38, 0.54), (0.50, 0.52), (0.66, 0.55), (0.80, 0.54), (1.0, 0.53)],
                2: [(0.00, 0.50), (0.12, 0.512), (0.25, 0.495), (0.38, 0.508), (0.50, 0.502), (0.66, 0.512), (0.80, 0.506), (1.0, 0.50)],
            }
        },
    ),
    _curve_points({0: [(0.0, 0.0), (0.20, 0.16), (0.50, 0.50), (0.80, 0.86), (1.0, 1.0)]}),
    _color_balance(lift=(0.995, 1.000, 1.005), gamma=(1.01, 1.00, 1.01), gain=(1.02, 1.01, 1.02), color_multiply=1.02),
)
_BROADCAST_SAFE_FINISH_STACK = (
    _LEGAL_RANGE_STACK[0],
    _tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.12, contrast=0.06, gamma=0.98),
    ("HUE_CORRECT", {"__hue_correct__": {"saturation": 0.49, "value": 0.50}}),
    _curve_points({0: [(0.0, 0.02), (0.05, 0.05), (0.50, 0.50), (0.95, 0.95), (1.0, 0.98)]}),
)
_MATCH_PREP_NEUTRALIZER_STACK = (
    _bright_contrast(bright=0.0, contrast=-4.0),
    _white_balance((1.0, 1.0, 1.0)),
    _color_balance(lift=(1.0, 1.0, 1.0), gamma=(1.0, 1.0, 1.0), gain=(1.0, 1.0, 1.0), color_multiply=0.98),
    _curve_points({0: [(0.0, 0.02), (0.20, 0.20), (0.50, 0.50), (0.80, 0.80), (1.0, 0.98)]}),
    ("HUE_CORRECT", {"__hue_correct__": {"saturation": 0.49, "value": 0.50}}),
)


TOOLS: tuple[VideoTool, ...] = (
    VideoTool(
        id="live_pro_color_stack",
        label="Live Pro Color Stack",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds a live editable Blender stack: Brightness/Contrast, Color Balance, Tone Map, White Balance, Curves, and Hue Correct.",
        blender_stack=(
            ("BRIGHT_CONTRAST", {"bright": 0.01, "contrast": 8.0}),
            (
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.lift": (0.99, 0.99, 1.00),
                    "color_balance.gamma": (1.02, 1.02, 1.02),
                    "color_balance.gain": (1.04, 1.04, 1.04),
                    "color_multiply": 1.0,
                },
            ),
            ("TONEMAP", {"tonemap_type": "RD_PHOTORECEPTOR", "intensity": 0.10, "contrast": 0.14}),
            ("WHITE_BALANCE", {"white_value": (1.0, 1.0, 1.0)}),
            ("CURVES", {}),
            ("HUE_CORRECT", {}),
        ),
    ),
    VideoTool(
        id="live_gamma_grade",
        label="Live Gamma Grade",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live midtone gamma and gentle exposure lift for underexposed clips.",
        blender_stack=(
            ("BRIGHT_CONTRAST", {"bright": 0.025, "contrast": 4.0}),
            (
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.gamma": (1.08, 1.08, 1.08),
                    "color_balance.gain": (1.03, 1.03, 1.03),
                },
            ),
        ),
    ),
    VideoTool(
        id="live_shadow_recovery",
        label="Live Shadow Recovery",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live lift/gamma stack to recover dark footage without rendering.",
        blender_stack=(
            ("BRIGHT_CONTRAST", {"bright": 0.015, "contrast": -3.0}),
            (
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.lift": (1.05, 1.05, 1.05),
                    "color_balance.gamma": (1.06, 1.06, 1.06),
                    "color_balance.gain": (1.01, 1.01, 1.01),
                },
            ),
        ),
    ),
    VideoTool(
        id="live_contrast_pop",
        label="Live Contrast Pop",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live contrast and highlight gain for punchier editorial color.",
        blender_stack=(
            ("BRIGHT_CONTRAST", {"bright": 0.0, "contrast": 14.0}),
            (
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.lift": (0.98, 0.98, 0.98),
                    "color_balance.gain": (1.07, 1.07, 1.07),
                },
            ),
        ),
    ),
    VideoTool(
        id="live_warm_grade",
        label="Live Warm Grade",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live warm color balance using Blender's strip Color Balance modifier.",
        blender_stack=(
            (
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.gamma": (1.04, 1.02, 0.98),
                    "color_balance.gain": (1.06, 1.02, 0.96),
                },
            ),
        ),
    ),
    VideoTool(
        id="live_cool_grade",
        label="Live Cool Grade",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live cool color balance using Blender's strip Color Balance modifier.",
        blender_stack=(
            (
                "COLOR_BALANCE",
                {
                    "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                    "color_balance.gamma": (0.98, 1.01, 1.04),
                    "color_balance.gain": (0.96, 1.01, 1.06),
                },
            ),
        ),
    ),
    VideoTool(
        id="auto_enhance",
        label="Auto Enhance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native Blender live equivalent of FFmpeg eq/normalize intent: contrast, gamma, color balance, tone map, and curves.",
        blender_stack=_AUTO_ENHANCE_STACK + (_curves(),),
    ),
    VideoTool(
        id="neutral_grade",
        label="Neutral Grade",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Clean Blender-native baseline grade with conservative contrast and neutral balance.",
        blender_stack=_NEUTRAL_GRADE_STACK + (_curves(),),
    ),
    VideoTool(
        id="punchy_color",
        label="Punchy Color",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Blender-native contrast, gain, and hue-correct stack for denser editorial color.",
        blender_stack=_PUNCHY_COLOR_STACK,
    ),
    VideoTool(
        id="soft_contrast",
        label="Soft Contrast",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Blender-native softer contrast and lifted midtones.",
        blender_stack=_SOFT_CONTRAST_STACK,
    ),
    VideoTool(
        id="exposure_lift",
        label="Exposure Lift",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live Blender exposure and midtone lift for underexposed clips.",
        blender_stack=_EXPOSURE_LIFT_STACK,
    ),
    VideoTool(
        id="gamma_brighten",
        label="Gamma Brighten",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live Blender gamma lift using Color Balance and Tone Map.",
        blender_stack=_GAMMA_BRIGHTEN_STACK,
    ),
    VideoTool(
        id="gamma_deepen",
        label="Gamma Deepen",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live Blender gamma compression for washed midtones.",
        blender_stack=_GAMMA_DEEPEN_STACK,
    ),
    VideoTool(
        id="warm_balance",
        label="Warm Balance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native Blender channel-balance equivalent of a warm FFmpeg color mixer.",
        blender_stack=_WARM_BALANCE_STACK,
    ),
    VideoTool(
        id="cool_balance",
        label="Cool Balance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native Blender channel-balance equivalent of a cool FFmpeg color mixer.",
        blender_stack=_COOL_BALANCE_STACK,
    ),
    VideoTool(
        id="saturation_boost",
        label="Saturation Boost",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg hue saturation boost as a native Blender Hue Correct curve.",
        blender_stack=_SATURATION_BOOST_STACK,
    ),
    VideoTool(
        id="saturation_reduce",
        label="Saturation Reduce",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg hue saturation reduction as a native Blender Hue Correct curve.",
        blender_stack=_SATURATION_REDUCE_STACK,
    ),
    VideoTool(
        id="monochrome",
        label="Monochrome",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg hue desaturation as a native Blender Hue Correct curve.",
        blender_stack=_MONOCHROME_STACK,
    ),
    VideoTool(
        id="faded_film",
        label="Faded Film",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg brightness/contrast/gamma/saturation recipe as Blender live modifiers.",
        blender_stack=_FADED_FILM_STACK,
    ),
    VideoTool(
        id="high_contrast_curve",
        label="High Contrast Curve",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg curves strong_contrast preset as a native Blender RGB Curves modifier.",
        blender_stack=_HIGH_CONTRAST_CURVE_STACK,
    ),
    VideoTool(
        id="medium_contrast_curve",
        label="Medium Contrast Curve",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg curves medium_contrast preset as a native Blender RGB Curves modifier.",
        blender_stack=_MEDIUM_CONTRAST_CURVE_STACK,
    ),
    VideoTool(
        id="levels_expand",
        label="Levels Expand",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colorlevels black/white point expansion as native Blender RGB Curves.",
        blender_stack=_LEVELS_EXPAND_STACK,
    ),
    VideoTool(
        id="levels_soft_clamp",
        label="Levels Soft Clamp",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colorlevels output clamp as native Blender RGB Curves.",
        blender_stack=_LEVELS_SOFT_CLAMP_STACK,
    ),
    VideoTool(
        id="shadow_highlight_balance",
        label="Shadow/Highlight Balance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colorbalance shadows/midtones/highlights into Blender Lift/Gamma/Gain.",
        blender_stack=_SHADOW_HIGHLIGHT_BALANCE_STACK,
    ),
    VideoTool(
        id="vibrance",
        label="Vibrance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg vibrance into Blender Hue Correct and Color Balance controls.",
        blender_stack=_VIBRANCE_STACK,
    ),
    VideoTool(
        id="skin_safe_vibrance",
        label="Skin-Safe Vibrance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Conservative Blender-native vibrance setup that avoids heavy red/orange saturation shifts.",
        blender_stack=_SKIN_SAFE_VIBRANCE_STACK,
    ),
    VideoTool(
        id="exposure_protect",
        label="Exposure Protect",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg exposure/black controls into Blender Brightness, Curves, and Tone Map.",
        blender_stack=_EXPOSURE_PROTECT_STACK,
    ),
    VideoTool(
        id="temperature_warm",
        label="Temperature Warm",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colortemperature into Blender White Balance and Color Balance.",
        blender_stack=_TEMP_WARM_STACK,
    ),
    VideoTool(
        id="temperature_cool",
        label="Temperature Cool",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colortemperature into Blender White Balance and Color Balance.",
        blender_stack=_TEMP_COOL_STACK,
    ),
    VideoTool(
        id="legal_range_clamp",
        label="Legal Range Clamp",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg limiter 16-235 intent into a Blender RGB Curves clamp.",
        blender_stack=_LEGAL_RANGE_STACK,
    ),
    VideoTool(
        id="hdr_tone_compress",
        label="HDR Tone Compress",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg tonemap intent into Blender Tone Map plus saturation control.",
        blender_stack=_HDR_TONE_COMPRESS_STACK,
    ),
    VideoTool(
        id="black_point_cleanup",
        label="Black Point Cleanup",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native Blender brightness plus RGB curve cleanup for milky blacks and lifted shadows.",
        blender_stack=_BLACK_POINT_CLEANUP_STACK,
    ),
    VideoTool(
        id="white_point_recovery",
        label="White Point Recovery",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native Blender tone map and curve roll-off for hot whites and clipped-looking highlights.",
        blender_stack=_WHITE_POINT_RECOVERY_STACK,
    ),
    VideoTool(
        id="luma_s_curve",
        label="Luma S-Curve",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Editable native RGB curve contrast shape for fast primary color correction.",
        blender_stack=_LUMA_S_CURVE_STACK,
    ),
    VideoTool(
        id="red_gamma_trim",
        label="Red Gamma Trim",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live Blender midtone red-channel gamma trim using Color Balance and White Balance.",
        blender_stack=_RED_GAMMA_TRIM_STACK,
    ),
    VideoTool(
        id="green_gamma_trim",
        label="Green Gamma Trim",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live Blender midtone green-channel gamma trim using Color Balance and White Balance.",
        blender_stack=_GREEN_GAMMA_TRIM_STACK,
    ),
    VideoTool(
        id="blue_gamma_trim",
        label="Blue Gamma Trim",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Live Blender midtone blue-channel gamma trim using Color Balance and White Balance.",
        blender_stack=_BLUE_GAMMA_TRIM_STACK,
    ),
    VideoTool(
        id="magenta_green_tint",
        label="Magenta/Green Tint",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native White Balance and Color Balance tint correction for fluorescent or camera tint shifts.",
        blender_stack=_MAGENTA_GREEN_TINT_STACK,
    ),
    VideoTool(
        id="green_cast_repair",
        label="Green Cast Repair",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="One-click native Blender repair stack for green-biased footage.",
        blender_stack=_GREEN_CAST_REPAIR_STACK,
    ),
    VideoTool(
        id="shadow_cool_tint",
        label="Shadow Cool Tint",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native lift/gamma and curve setup for cooler shadows without changing the whole image.",
        blender_stack=_SHADOW_COOL_TINT_STACK,
    ),
    VideoTool(
        id="highlight_warm_tint",
        label="Highlight Warm Tint",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native gain and tone-map setup for warmer highlights and gentle roll-off.",
        blender_stack=_HIGHLIGHT_WARM_TINT_STACK,
    ),
    VideoTool(
        id="skin_tone_isolation",
        label="Skin Tone Isolation",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Conservative native gamma and Hue Correct stack for warmer skin-tone-like ranges.",
        blender_stack=_SKIN_TONE_ISOLATION_STACK,
    ),
    VideoTool(
        id="primary_color_board",
        label="Primary Color Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Professional primary board built from Blender Brightness/Contrast, Lift/Gamma/Gain, ASC CDL, RGB Curves, Tone Map, and Hue Correct.",
        blender_stack=_PRIMARY_COLOR_BOARD_STACK,
    ),
    VideoTool(
        id="log_zone_color_board",
        label="Log Zone Color Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Shadow, midtone, and highlight board for log-like footage using Blender Lift/Gamma/Gain, curves, and tone mapping.",
        blender_stack=_LOG_ZONE_COLOR_BOARD_STACK,
    ),
    VideoTool(
        id="asc_cdl_finish_board",
        label="ASC CDL Finish Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Offset/Power/Slope finishing board with contrast curve and native Hue Correct saturation trim.",
        blender_stack=_ASC_CDL_FINISH_STACK,
    ),
    VideoTool(
        id="six_vector_hue_board",
        label="Six-Vector Hue Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Secondary color board using Blender Hue Correct curves across red, yellow, green, cyan, blue, and magenta zones.",
        blender_stack=_SIX_VECTOR_HUE_BOARD_STACK,
    ),
    VideoTool(
        id="secondary_skin_vector",
        label="Secondary Skin Vector",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native secondary correction for skin-tone-like hue ranges with Hue Correct, Lift/Gamma/Gain, and gentle tone mapping.",
        blender_stack=_SECONDARY_SKIN_VECTOR_STACK,
    ),
    VideoTool(
        id="palette_separation_board",
        label="Palette Separation Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Palette separation board for sampled color identity work using hue-zone saturation, RGB curves, and color balance.",
        blender_stack=_PALETTE_SEPARATION_BOARD_STACK,
    ),
    VideoTool(
        id="broadcast_safe_finish",
        label="Broadcast-Safe Finish",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Native legal-range, highlight roll-off, saturation restraint, and curve finish for delivery-safe video color.",
        blender_stack=_BROADCAST_SAFE_FINISH_STACK,
    ),
    VideoTool(
        id="match_prep_neutralizer",
        label="Match Prep Neutralizer",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Neutral preparation board before reference matching: soft contrast, neutral white balance, flat curves, and restrained saturation.",
        blender_stack=_MATCH_PREP_NEUTRALIZER_STACK,
    ),
    VideoTool(
        id="selective_color_punch",
        label="Selective Color Punch",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg selectivecolor intent as native Blender Hue Correct, Color Balance, and compositor nodes.",
        blender_stack=_SELECTIVE_COLOR_TRANSLATION.stack,
        compositor_stack=_SELECTIVE_COLOR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="colorize_blue_steel",
        label="Colorize Blue Steel",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colorize intent as native Blender Hue Correct, Color Balance, and White Balance controls.",
        blender_stack=_COLORIZE_TRANSLATION.stack,
        compositor_stack=_COLORIZE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="grey_edge_balance",
        label="Grey Edge Balance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg greyedge white-balance intent as Blender White Balance, Lift/Gamma/Gain, and RGB Curves.",
        blender_stack=_GREY_EDGE_TRANSLATION.stack,
        compositor_stack=_GREY_EDGE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="pseudocolor_viridis",
        label="Pseudocolor Viridis",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg pseudocolor analysis look as native Blender Hue Correct, Curves, and Color Balance.",
        blender_stack=_PSEUDOCOLOR_TRANSLATION.stack,
        compositor_stack=_PSEUDOCOLOR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="lut_invert_curve",
        label="LUT Invert Curve",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg lutrgb curve intent as native editable Blender RGB Curves.",
        blender_stack=_LUT_INVERT_TRANSLATION.stack,
        compositor_stack=_LUT_INVERT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="histogram_equalize",
        label="Histogram Equalize",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg histeq contrast redistribution as Blender RGB Curves and Tone Map.",
        blender_stack=_HISTOGRAM_EQUALIZE_TRANSLATION.stack,
        compositor_stack=_HISTOGRAM_EQUALIZE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="color_hold_blue",
        label="Color Hold Blue",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colorhold intent as a native Blender Hue Correct isolation curve.",
        blender_stack=_COLOR_HOLD_TRANSLATION.stack,
        compositor_stack=_COLOR_HOLD_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="hsv_hold_blue",
        label="HSV Hold Blue",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg hsvhold intent as native Blender Hue Correct saturation/value isolation curves.",
        blender_stack=_HSV_HOLD_TRANSLATION.stack,
        compositor_stack=_HSV_HOLD_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_all_color_tools",
        label="All Native Color Tools",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds every native Blender VSE color primitive as editable live modifiers.",
        blender_stack=(
            _bright_contrast(),
            _color_balance(),
            _asc_cdl(),
            _tonemap(tonemap_type="RD_PHOTORECEPTOR"),
            _tonemap(tonemap_type="RH_SIMPLE", key=0.18, offset=1.0),
            _white_balance(),
            _curves(),
            _hue_correct(),
            ("MASK", {}),
        ),
    ),
    VideoTool(
        id="native_bright_contrast",
        label="Brightness/Contrast",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's Brightness/Contrast modifier.",
        blender_stack=(_bright_contrast(),),
    ),
    VideoTool(
        id="native_lift_gamma_gain",
        label="Lift/Gamma/Gain",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's Color Balance modifier in Lift/Gamma/Gain mode.",
        blender_stack=(_color_balance(),),
    ),
    VideoTool(
        id="native_asc_cdl",
        label="ASC CDL Offset/Power/Slope",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's Color Balance modifier in ASC-CDL Offset/Power/Slope mode.",
        blender_stack=(_asc_cdl(),),
    ),
    VideoTool(
        id="native_rd_tonemap",
        label="R/D Photoreceptor Tone Map",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's R/D Photoreceptor Tone Map modifier.",
        blender_stack=(_tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.08, contrast=0.12),),
    ),
    VideoTool(
        id="native_rh_tonemap",
        label="Rh Simple Tone Map",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's Rh Simple Tone Map modifier.",
        blender_stack=(_tonemap(tonemap_type="RH_SIMPLE", key=0.18, offset=1.0, gamma=1.0),),
    ),
    VideoTool(
        id="native_curves_editor",
        label="Curves Editor",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's RGB Curves modifier.",
        blender_stack=(_curves(),),
    ),
    VideoTool(
        id="native_hue_correct_editor",
        label="Hue Correct Editor",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's Hue Correct curve modifier.",
        blender_stack=(_hue_correct(),),
    ),
    VideoTool(
        id="native_white_balance_editor",
        label="White Balance",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's White Balance modifier.",
        blender_stack=(_white_balance(),),
    ),
    VideoTool(
        id="native_mask_slot",
        label="Mask Slot",
        category="Native Blender Primitives",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's Mask strip modifier for masked color work.",
        blender_stack=(("MASK", {}),),
    ),
    VideoTool(
        id="native_compositor_all_color_primitives",
        label="All Compositor Color Nodes",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender compositor color primitives as one graph: Exposure, Brightness/Contrast, Color Balance, Color Correction, RGB Curves, Hue/Saturation, Hue Correct, Tone Map, Invert, Posterize, and Premul Key.",
        compositor_stack=(
            ("EXPOSURE", {"source": "blender_compositor", "exposure": 0.12, "black": 0.0}),
            ("BRIGHT_CONTRAST", {"source": "blender_compositor", "bright": 0.01, "contrast": 4.0}),
            ("COLOR_BALANCE", {"source": "blender_compositor", "color_balance.gamma": (1.02, 1.02, 1.02), "color_balance.gain": (1.03, 1.03, 1.03)}),
            ("COLOR_CORRECTION", {"source": "blender_compositor", "saturation": 1.04, "shadow_offset": 0.01, "highlight_gain": 1.02}),
            ("CURVE_RGB", {"source": "blender_compositor", "__curve_points__": {0: [(0.0, 0.0), (0.22, 0.18), (0.50, 0.50), (0.80, 0.86), (1.0, 1.0)]}}),
            ("HUE_SAT", {"source": "blender_compositor", "hue": 0.5, "saturation": 1.08, "value": 1.0, "factor": 1.0}),
            ("HUE_CORRECT", {"source": "blender_compositor", "__hue_correct__": {"saturation": 0.53, "value": 0.50}}),
            ("TONEMAP", {"source": "blender_compositor", "tonemap_type": "RD_PHOTORECEPTOR", "intensity": 0.04, "contrast": 0.04, "gamma": 1.0}),
            ("INVERT", {"source": "blender_compositor", "factor": 0.0, "invert_color": True, "invert_alpha": False}),
            ("POSTERIZE", {"source": "blender_compositor", "steps": 48.0}),
            ("PREMUL_KEY", {"source": "blender_compositor", "mode": "To Premultiplied"}),
        ),
    ),
    VideoTool(
        id="native_compositor_exposure",
        label="Compositor Exposure",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Exposure node with viewer and output nodes.",
        compositor_stack=(("EXPOSURE", {"source": "blender_compositor", "exposure": 0.18, "black": 0.0}),),
    ),
    VideoTool(
        id="native_compositor_color_correction",
        label="Compositor Color Correction",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Color Correction node for master, shadows, midtones, and highlights.",
        compositor_stack=(("COLOR_CORRECTION", {"source": "blender_compositor", "saturation": 1.06, "shadow_offset": 0.01, "highlight_gain": 1.03}),),
    ),
    VideoTool(
        id="native_compositor_hue_saturation",
        label="Compositor Hue/Saturation",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Hue/Saturation/Value node.",
        compositor_stack=(("HUE_SAT", {"source": "blender_compositor", "hue": 0.5, "saturation": 1.12, "value": 1.0, "factor": 1.0}),),
    ),
    VideoTool(
        id="native_compositor_invert",
        label="Compositor Invert",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Invert node for color or alpha inversion workflows.",
        compositor_stack=(("INVERT", {"source": "blender_compositor", "factor": 1.0, "invert_color": True, "invert_alpha": False}),),
    ),
    VideoTool(
        id="native_compositor_posterize",
        label="Compositor Posterize",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Posterize node for tonal-step looks and analysis.",
        compositor_stack=(("POSTERIZE", {"source": "blender_compositor", "steps": 12.0}),),
    ),
    VideoTool(
        id="native_compositor_premultiply",
        label="Compositor Premultiply",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Premul Key node for straight/premultiplied alpha conversion.",
        compositor_stack=(("PREMUL_KEY", {"source": "blender_compositor", "mode": "To Premultiplied"}),),
    ),
    VideoTool(
        id="deflicker",
        label="Deflicker",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Removes temporal luminance pulsing with median smoothing.",
        ffmpeg_filter="deflicker=s=12:m=median",
    ),
    VideoTool(
        id="lighting_normalizer",
        label="Lighting Normalizer",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Normalizes black/white points over time to reduce lighting swings.",
        ffmpeg_filter="normalize=smoothing=120:independence=0.25:strength=0.80",
    ),
    VideoTool(
        id="deflicker_normalize",
        label="Deflicker + Normalize",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Combines flicker removal with conservative temporal exposure normalization.",
        ffmpeg_filter=(
            "deflicker=s=10:m=median,"
            "normalize=smoothing=90:independence=0.20:strength=0.55"
        ),
    ),
    VideoTool(
        id="denoise_light",
        label="Denoise Light",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Fast high-quality temporal/spatial denoise for mild grain.",
        ffmpeg_filter="hqdn3d=1.5:1.5:6:6",
    ),
    VideoTool(
        id="denoise_strong",
        label="Denoise Strong",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Slower non-local means denoise for difficult noisy footage.",
        ffmpeg_filter="nlmeans=s=2.5:p=7:r=9",
        slow=True,
    ),
    VideoTool(
        id="restore_sharpness",
        label="Restore Sharpness",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Unsharp mask tuned for video restoration rather than crunchy edges.",
        ffmpeg_filter="unsharp=5:5:0.70:3:3:0.30",
    ),
    VideoTool(
        id="deinterlace",
        label="Deinterlace",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="BWDIF deinterlace for old camcorder, broadcast, and archive footage.",
        ffmpeg_filter="bwdif=mode=send_frame:parity=auto:deint=all",
    ),
    VideoTool(
        id="quick_deshake",
        label="Quick Deshake",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Single-pass deshake for small handheld motion.",
        ffmpeg_filter="deshake=rx=16:ry=16",
    ),
    VideoTool(
        id="stabilize",
        label="Stabilize",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Two-pass vidstab camera stabilization with mild post-sharpening.",
        ffmpeg_filter_after_stabilize="unsharp=5:5:0.35:3:3:0.15",
        two_pass_stabilize=True,
        slow=True,
    ),
    VideoTool(
        id="temporal_smooth",
        label="Temporal Smooth",
        category="Restoration",
        engine=ENGINE_FFMPEG,
        description="Blends neighboring frames to calm minor temporal noise.",
        ffmpeg_filter="tmix=frames=3:weights='1 2 1'",
    ),
    VideoTool(
        id="native_compositor_restore_nodes",
        label="Native Restore Nodes",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Creates a Blender-native compositor restoration graph: Denoise, Despeckle, Bilateral Blur, and Anti-Aliasing.",
        compositor_stack=(
            ("DENOISE", {"source": "blender_compositor", "quality": "Balanced", "prefilter": "Accurate", "strength": 0.65}),
            ("DESPECKLE", {"source": "blender_compositor", "factor": 0.28, "color_threshold": 0.32, "neighbor_threshold": 0.28}),
            ("BILATERAL_BLUR", {"source": "blender_compositor", "size": 2, "threshold": 0.08, "strength": 0.35}),
            ("ANTI_ALIASING", {"source": "blender_compositor", "threshold": 0.16, "contrast_limit": 1.6, "corner_rounding": 0.18}),
        ),
    ),
    VideoTool(
        id="native_compositor_sharpen_cleanup",
        label="Native Sharpen Cleanup Nodes",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Creates a native Blender compositor cleanup graph for soft footage using Filter sharpen, Despeckle, and Anti-Aliasing nodes.",
        compositor_stack=(
            ("FILTER", {"source": "blender_compositor", "filter_type": "Sharpen", "factor": 0.45}),
            ("DESPECKLE", {"source": "blender_compositor", "factor": 0.22, "color_threshold": 0.28, "neighbor_threshold": 0.24}),
            ("ANTI_ALIASING", {"source": "blender_compositor", "threshold": 0.18, "contrast_limit": 1.8, "corner_rounding": 0.2}),
        ),
    ),
    VideoTool(
        id="native_compositor_lens_repair",
        label="Native Lens Repair Nodes",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Creates a native Blender compositor lens cleanup graph with Lens Distortion, overscan scale, and gentle anti-aliasing.",
        compositor_stack=(
            ("LENS_DISTORTION", {"source": "blender_compositor", "distortion": -0.04, "dispersion": 0.0, "fit": True}),
            ("SCALE", {"source": "blender_compositor", "type": "Relative", "x": 1.02, "y": 1.02, "frame_type": "Stretch", "interpolation": "Bicubic"}),
            ("ANTI_ALIASING", {"source": "blender_compositor", "threshold": 0.2, "contrast_limit": 1.6, "corner_rounding": 0.22}),
        ),
    ),
    VideoTool(
        id="upscale_2x",
        label="Upscale 2x",
        category="Resolution & Motion",
        engine=ENGINE_FFMPEG,
        description="Two-times Lanczos upscale with even output dimensions.",
        ffmpeg_filter="scale=trunc(iw*2/2)*2:trunc(ih*2/2)*2:flags=lanczos",
        slow=True,
    ),
    VideoTool(
        id="scale_1080p",
        label="Scale to 1080p",
        category="Resolution & Motion",
        engine=ENGINE_FFMPEG,
        description="Fits footage into 1080p while preserving aspect ratio.",
        ffmpeg_filter="scale=w=-2:h='min(1080,ih)':flags=lanczos",
    ),
    VideoTool(
        id="motion_60fps",
        label="Motion 60 FPS",
        category="Resolution & Motion",
        engine=ENGINE_FFMPEG,
        description="Motion-compensated frame interpolation to 60 fps.",
        ffmpeg_filter="minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
        slow=True,
    ),
    VideoTool(
        id="native_compositor_resize_reframe",
        label="Native Resize/Reframe Nodes",
        category="Resolution & Motion",
        engine=ENGINE_COMPOSITOR,
        description="Creates a Blender-native compositor transform graph with Scale, Crop, and output nodes for non-rendered reframe work.",
        compositor_stack=(
            ("SCALE", {"source": "blender_compositor", "type": "Relative", "x": 1.05, "y": 1.05, "frame_type": "Stretch", "interpolation": "Bicubic"}),
            ("CROP", {"source": "blender_compositor", "x": 0, "y": 0, "width": 1920, "height": 1080, "alpha_crop": False}),
        ),
    ),
    VideoTool(
        id="native_compositor_motion_geometry",
        label="Native Motion Geometry Nodes",
        category="Resolution & Motion",
        engine=ENGINE_COMPOSITOR,
        description="Creates a native Blender compositor geometry graph using Rotate, Directional Blur, and Scale for motion finishing.",
        compositor_stack=(
            ("ROTATE", {"source": "blender_compositor", "angle": 0.012, "interpolation": "Bicubic", "extension_x": "Clip", "extension_y": "Clip"}),
            ("DIRECTIONAL_BLUR", {"source": "blender_compositor", "samples": 8, "rotation": 0.0, "scale": 1.0, "amount": 0.08, "direction": 0.18}),
            ("SCALE", {"source": "blender_compositor", "type": "Relative", "x": 1.0, "y": 1.0, "frame_type": "Stretch", "interpolation": "Bilinear"}),
        ),
    ),
    VideoTool(
        id="vse_bright_contrast",
        label="VSE Brightness/Contrast",
        category="Live Blender Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Brightness/Contrast strip modifier.",
        blender_modifier="BRIGHT_CONTRAST",
        blender_settings={"bright": 0.02, "contrast": 8.0},
    ),
    VideoTool(
        id="vse_color_balance",
        label="VSE Color Balance",
        category="Live Blender Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Color Balance strip modifier with a mild lift/gamma/gain setup.",
        blender_modifier="COLOR_BALANCE",
        blender_settings={
            "color_balance.correction_method": "LIFT_GAMMA_GAIN",
            "color_balance.lift": (0.98, 0.98, 1.00),
            "color_balance.gamma": (1.02, 1.02, 1.02),
            "color_balance.gain": (1.04, 1.04, 1.04),
        },
    ),
    VideoTool(
        id="vse_curves",
        label="VSE Curves",
        category="Live Blender Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Curves strip modifier for manual curve shaping.",
        blender_modifier="CURVES",
    ),
    VideoTool(
        id="vse_hue_correct",
        label="VSE Hue Correct",
        category="Live Blender Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Hue Correct strip modifier for hue-zone corrections.",
        blender_modifier="HUE_CORRECT",
    ),
    VideoTool(
        id="vse_mask",
        label="VSE Mask Slot",
        category="Live Blender Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Mask strip modifier ready for a mask assignment.",
        blender_modifier="MASK",
    ),
    VideoTool(
        id="vse_tonemap",
        label="VSE Tone Map",
        category="Live Blender Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Tone Map strip modifier.",
        blender_modifier="TONEMAP",
        blender_settings={"tonemap_type": "RD_PHOTORECEPTOR", "intensity": 0.12, "contrast": 0.16},
    ),
    VideoTool(
        id="vse_white_balance",
        label="VSE White Balance",
        category="Live Blender Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native White Balance strip modifier.",
        blender_modifier="WHITE_BALANCE",
        blender_settings={"white_value": (1.0, 1.0, 1.0)},
    ),
)


def all_tools() -> tuple[VideoTool, ...]:
    return TOOLS


def ffmpeg_tools() -> tuple[VideoTool, ...]:
    return tuple(tool for tool in TOOLS if tool.is_ffmpeg)


def blender_modifier_tools() -> tuple[VideoTool, ...]:
    return tuple(tool for tool in TOOLS if tool.is_blender_modifier)


def categories(tools: Iterable[VideoTool] | None = None) -> tuple[str, ...]:
    seen: list[str] = []
    for tool in tools or TOOLS:
        if tool.category not in seen:
            seen.append(tool.category)
    return tuple(seen)


def get_tool(tool_id: str) -> VideoTool:
    for tool in TOOLS:
        if tool.id == tool_id:
            return tool
    raise KeyError(f"Unknown video tool: {tool_id}")


def enum_items() -> list[tuple[str, str, str]]:
    return [(tool.id, tool.label, tool.description) for tool in TOOLS]
