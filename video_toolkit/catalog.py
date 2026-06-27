"""Shared filter catalog for Blender UI, CLI, and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .ffmpeg_native import translate_filter_chain


ENGINE_BLENDER_MODIFIER = "blender_modifier"
ENGINE_FFMPEG = "ffmpeg"
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
