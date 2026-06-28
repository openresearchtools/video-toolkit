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


def _native_node(
    node_type: str,
    *,
    label: str,
    image_input: str | None = None,
    image_output: str | None = None,
    inputs: dict[str, Any] | None = None,
    properties: dict[str, Any] | None = None,
    assign_source_clip: bool = False,
    skip_link_input: bool = False,
    passthrough: bool = False,
    note: str | None = None,
) -> tuple[str, dict[str, Any]]:
    settings: dict[str, Any] = {
        "node_type": node_type,
        "label": label,
        "inputs": inputs or {},
        "properties": properties or {},
        "assign_source_clip": assign_source_clip,
    }
    if image_input:
        settings["__image_input__"] = image_input
    if image_output:
        settings["__image_output__"] = image_output
    if skip_link_input:
        settings["__skip_link_input__"] = True
    if passthrough:
        settings["__passthrough__"] = True
    if note:
        settings["note"] = note
    return ("NATIVE_NODE", settings)


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
_CHROMA_KEY_MATTE_TRANSLATION = translate_filter_chain("chromakey=color=green:similarity=0.18:blend=0.06")
_COLOR_KEY_MATTE_TRANSLATION = translate_filter_chain("colorkey=color=blue:similarity=0.16:blend=0.04")
_HSV_KEY_MATTE_TRANSLATION = translate_filter_chain("hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.12:blend=0.03")
_LUMA_KEY_MATTE_TRANSLATION = translate_filter_chain("lumakey=threshold=0.20:tolerance=0.10:softness=0.04")
_RGBA_CHANNEL_SHIFT_TRANSLATION = translate_filter_chain("rgbashift=rh=5:rv=-2:bh=-4:bv=2")
_CHROMA_CHANNEL_SHIFT_TRANSLATION = translate_filter_chain("chromashift=cbh=3:cbv=-1:crh=-3:crv=1")
_LUMA_PLANE_EXTRACT_TRANSLATION = translate_filter_chain("extractplanes=planes=y")
_ALPHA_EXTRACT_TRANSLATION = translate_filter_chain("alphaextract")
_PREMULTIPLY_ALPHA_TRANSLATION = translate_filter_chain("premultiply")
_PLANE_SHUFFLE_BGR_TRANSLATION = translate_filter_chain("shuffleplanes=2:1:0:3")
_STRAIGHT_ALPHA_TRANSLATION = translate_filter_chain("unpremultiply")
_NATIVE_ELBG_POSTERIZE_TRANSLATION = translate_filter_chain("elbg=codebook_length=32:nb_steps=1")
_NATIVE_UNSHARP_TRANSLATION = translate_filter_chain("unsharp=5:5:0.55:3:3:0.20")
_NATIVE_SOBEL_TRANSLATION = translate_filter_chain("sobel=scale=1.2:delta=0.02")
_NATIVE_PREWITT_TRANSLATION = translate_filter_chain("prewitt=scale=0.9:delta=0.01")
_NATIVE_KIRSCH_TRANSLATION = translate_filter_chain("kirsch=scale=0.8")
_NATIVE_EDGE_DETECT_TRANSLATION = translate_filter_chain("edgedetect=high=0.20:low=0.08:mode=wires")
_NATIVE_EROSION_TRANSLATION = translate_filter_chain(
    "erosion=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000"
)
_NATIVE_DILATION_TRANSLATION = translate_filter_chain(
    "dilation=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000"
)
_NATIVE_CONVOLUTION_SHARPEN_TRANSLATION = translate_filter_chain(
    "convolution=0m='0 -1 0 -1 5 -1 0 -1 0':0rdiv=1:0bias=0"
)
_NATIVE_AVERAGE_BLUR_TRANSLATION = translate_filter_chain("avgblur=sizeX=4:sizeY=6")
_NATIVE_BOX_BLUR_TRANSLATION = translate_filter_chain("boxblur=lr=3:lp=2")
_NATIVE_GAUSSIAN_BLUR_TRANSLATION = translate_filter_chain("gblur=sigma=1.2:steps=2:sigmaV=0.8")
_NATIVE_SMART_BLUR_TRANSLATION = translate_filter_chain("smartblur=lr=2:ls=0.8:lt=8")
_NATIVE_DIRECTIONAL_BLUR_TRANSLATION = translate_filter_chain("dblur=angle=30:radius=12")
_NATIVE_SHAPE_ADAPTIVE_BLUR_TRANSLATION = translate_filter_chain("sab=lr=3:lpfr=1.2:ls=8:cr=2:cs=0.8:ct=6")
_NATIVE_EDGE_PRESERVING_BLUR_TRANSLATION = translate_filter_chain("yaepblur=radius=4:sigma=96")
_NATIVE_HQDN3D_DENOISE_TRANSLATION = translate_filter_chain("hqdn3d=1.5:1.5:6:6")
_NATIVE_NLMEANS_DENOISE_TRANSLATION = translate_filter_chain("nlmeans=s=2.5:p=7:r=9")
_NATIVE_BM3D_DENOISE_TRANSLATION = translate_filter_chain("bm3d=sigma=3:block=4:bstep=2:group=1")
_NATIVE_WAVELET_DENOISE_TRANSLATION = translate_filter_chain("owdenoise=depth=8:luma_strength=0.8:chroma_strength=0.5")
_NATIVE_VAGUE_DENOISE_TRANSLATION = translate_filter_chain("vaguedenoiser=threshold=1.5:method=garrote:nsteps=6")
_NATIVE_ADAPTIVE_TEMPORAL_DENOISE_TRANSLATION = translate_filter_chain(
    "atadenoise=0a=0.02:0b=0.04:1a=0.02:1b=0.04:2a=0.02:2b=0.04"
)
_NATIVE_MEDIAN_DESPECKLE_TRANSLATION = translate_filter_chain("median=radius=2:planes=15")
_NATIVE_DEDOT_CLEANUP_TRANSLATION = translate_filter_chain("dedot=lt=0.08:tl=0.08")
_NATIVE_DEBAND_TRANSLATION = translate_filter_chain("deband=1thr=0.03:2thr=0.025:3thr=0.02:range=20")
_NATIVE_DEBLOCK_TRANSLATION = translate_filter_chain("deblock=block=16:alpha=0.12:beta=0.08")
_NATIVE_SCALE_FIT_TRANSLATION = translate_filter_chain("scale=w=1920:h=1080:flags=lanczos")
_NATIVE_CENTER_CROP_TRANSLATION = translate_filter_chain("crop=w=iw*0.9:h=ih*0.9:x=iw*0.05:y=ih*0.05")
_NATIVE_ROTATE_LEVEL_TRANSLATION = translate_filter_chain("rotate=angle=2*PI/180:fillcolor=black")
_NATIVE_TRANSPOSE_CLOCKWISE_TRANSLATION = translate_filter_chain("transpose=dir=clock")
_NATIVE_HORIZONTAL_FLIP_TRANSLATION = translate_filter_chain("hflip")
_NATIVE_VERTICAL_FLIP_TRANSLATION = translate_filter_chain("vflip")
_NATIVE_LENS_CORRECTION_TRANSLATION = translate_filter_chain("lenscorrection=cx=0.5:cy=0.5:k1=-0.04:k2=0.01")
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
        id="native_compositor_color_space_convert",
        label="Convert Color Space",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Convert Color Space node for selected-strip color pipeline work.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="Convert Color Space"),
        ),
    ),
    VideoTool(
        id="native_compositor_display_convert",
        label="Convert to Display",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Convert to Display node for display-referred review graphs.",
        compositor_stack=(
            _native_node("CompositorNodeConvertToDisplay", label="Convert to Display", inputs={"Invert": False}),
        ),
    ),
    VideoTool(
        id="native_compositor_set_alpha",
        label="Set Alpha",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Set Alpha node for opacity and matte finishing.",
        compositor_stack=(
            _native_node("CompositorNodeSetAlpha", label="Set Alpha", inputs={"Alpha": 0.85, "Type": "Apply Mask"}),
        ),
    ),
    VideoTool(
        id="native_compositor_alpha_over",
        label="Alpha Over",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Alpha Over node for selected-strip compositing.",
        compositor_stack=(
            _native_node(
                "CompositorNodeAlphaOver",
                label="Alpha Over",
                image_input="Background",
                inputs={"Factor": 1.0, "Type": "Straight", "Straight Alpha": True},
            ),
        ),
    ),
    VideoTool(
        id="native_chroma_key_matte",
        label="Native Chroma Key Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg chromakey intent as Blender's native Chroma Matte compositor graph.",
        compositor_stack=_CHROMA_KEY_MATTE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_color_key_matte",
        label="Native Color Key Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg colorkey intent as Blender's native Color Matte compositor graph.",
        compositor_stack=_COLOR_KEY_MATTE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_hsv_key_matte",
        label="Native HSV Key Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg hsvkey intent as a native Blender HSV color matte graph.",
        compositor_stack=_HSV_KEY_MATTE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_luma_key_matte",
        label="Native Luma Key Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg lumakey intent as Blender's native Luma Matte compositor graph.",
        compositor_stack=_LUMA_KEY_MATTE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_rgba_channel_shift",
        label="Native RGBA Channel Shift",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg rgbashift intent as native Separate/Translate/Combine compositor channel nodes.",
        compositor_stack=_RGBA_CHANNEL_SHIFT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_chroma_channel_shift",
        label="Native Chroma Channel Shift",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg chromashift intent as native red/blue channel offset compositor nodes.",
        compositor_stack=_CHROMA_CHANNEL_SHIFT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_luma_plane_extract",
        label="Native Luma Plane Extract",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg extractplanes luma intent as Blender RGB-to-BW and Combine Color compositor nodes.",
        compositor_stack=_LUMA_PLANE_EXTRACT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_alpha_extract",
        label="Native Alpha Extract",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg alphaextract intent as native Separate/Combine compositor channel nodes.",
        compositor_stack=_ALPHA_EXTRACT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_premultiply_alpha",
        label="Native Premultiply Alpha",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg premultiply intent as Blender's native Premul Key alpha conversion graph.",
        compositor_stack=_PREMULTIPLY_ALPHA_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_plane_shuffle_bgr",
        label="Native Plane Shuffle BGR",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg shuffleplanes BGR intent as native Separate/Combine compositor channel remapping.",
        compositor_stack=_PLANE_SHUFFLE_BGR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_straight_alpha",
        label="Native Straight Alpha",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg unpremultiply intent as Blender's native Premul Key straight-alpha conversion graph.",
        compositor_stack=_STRAIGHT_ALPHA_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_channel_matte",
        label="Channel Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Channel Matte node for channel-key matte work.",
        compositor_stack=(
            _native_node("CompositorNodeChannelMatte", label="Channel Matte", inputs={"Minimum": 0.08, "Maximum": 0.92}),
        ),
    ),
    VideoTool(
        id="native_compositor_difference_matte",
        label="Difference Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Difference Matte node for plate-difference keying.",
        compositor_stack=(
            _native_node(
                "CompositorNodeDiffMatte",
                label="Difference Matte",
                image_input="Image 1",
                inputs={"Tolerance": 0.12, "Falloff": 0.04},
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_distance_matte",
        label="Distance Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Distance Matte node for color-distance keying.",
        compositor_stack=(
            _native_node(
                "CompositorNodeDistanceMatte",
                label="Distance Matte",
                inputs={"Key Color": (0.0, 1.0, 0.0, 1.0), "Tolerance": 0.16, "Falloff": 0.05},
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_keying",
        label="Keying",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Keying node for full green-screen keying controls.",
        compositor_stack=(
            _native_node(
                "CompositorNodeKeying",
                label="Keying",
                inputs={"Key Color": (0.0, 1.0, 0.0, 1.0), "Blur Size": 1.0, "Black Level": 0.02, "White Level": 0.95},
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_color_spill",
        label="Color Spill Suppression",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Color Spill node for key cleanup.",
        compositor_stack=(
            _native_node("CompositorNodeColorSpill", label="Color Spill", inputs={"Factor": 1.0, "Strength": 0.6}),
        ),
    ),
    VideoTool(
        id="native_compositor_box_mask_alpha",
        label="Box Mask Alpha",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native Box Mask and Set Alpha nodes as an editable selected-strip mask graph.",
        compositor_stack=(
            (
                "BOX_MASK_ALPHA",
                {
                    "label": "Box Mask Alpha",
                    "mask_inputs": {"Value": 1.0, "Position": (0.5, 0.5), "Size": (0.72, 0.72), "Rotation": 0.0},
                },
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_ellipse_mask_alpha",
        label="Ellipse Mask Alpha",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native Ellipse Mask and Set Alpha nodes as an editable selected-strip mask graph.",
        compositor_stack=(
            (
                "ELLIPSE_MASK_ALPHA",
                {
                    "label": "Ellipse Mask Alpha",
                    "mask_inputs": {"Value": 1.0, "Position": (0.5, 0.5), "Size": (0.66, 0.66), "Rotation": 0.0},
                },
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_double_edge_mask_alpha",
        label="Double Edge Mask Alpha",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native Double Edge Mask graph with generated outer/inner masks and Set Alpha output.",
        compositor_stack=(
            (
                "DOUBLE_EDGE_MASK_ALPHA",
                {
                    "label": "Double Edge Mask Alpha",
                    "outer_inputs": {"Value": 1.0, "Position": (0.5, 0.5), "Size": (0.82, 0.82)},
                    "inner_inputs": {"Value": 1.0, "Position": (0.5, 0.5), "Size": (0.50, 0.50)},
                    "only_inside_outer": True,
                },
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_mask_to_sdf_alpha",
        label="Mask to SDF Alpha",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native Mask to SDF node from a generated Box Mask and applies it as selected-strip alpha.",
        compositor_stack=(
            (
                "MASK_TO_SDF_ALPHA",
                {
                    "label": "Mask to SDF Alpha",
                    "mask_inputs": {"Value": 1.0, "Position": (0.5, 0.5), "Size": (0.72, 0.72)},
                },
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_blender_mask_source",
        label="Blender Mask Source",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Mask source node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeMask", label="Mask Source", skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_keying_screen",
        label="Keying Screen",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Keying Screen node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeKeyingScreen", label="Keying Screen", inputs={"Smoothness": 0.2}, skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_id_mask",
        label="ID Mask",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor ID Mask node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeIDMask", label="ID Mask", inputs={"ID value": 1.0, "Index": 1.0, "Anti-Alias": True}, skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_unsharp_filter",
        label="Native Unsharp Filter",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg unsharp intent as Blender's native compositor Filter sharpen graph.",
        compositor_stack=_NATIVE_UNSHARP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_elbg_posterize",
        label="Native ELBG Posterize",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg elbg quantization intent as Blender's native compositor Posterize graph.",
        compositor_stack=_NATIVE_ELBG_POSTERIZE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_sobel_edges",
        label="Native Sobel Edges",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg sobel edge intent as Blender's native compositor Filter graph.",
        compositor_stack=_NATIVE_SOBEL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_prewitt_edges",
        label="Native Prewitt Edges",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg prewitt edge intent as Blender's native compositor Filter graph.",
        compositor_stack=_NATIVE_PREWITT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_kirsch_edges",
        label="Native Kirsch Edges",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg kirsch edge intent as Blender's native compositor Filter graph.",
        compositor_stack=_NATIVE_KIRSCH_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_edge_detect",
        label="Native Edge Detect",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg edgedetect intent as Blender's native compositor Filter graph.",
        compositor_stack=_NATIVE_EDGE_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_erode_matte",
        label="Native Erode Matte",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg erosion intent as Blender's native Dilate/Erode compositor graph.",
        compositor_stack=_NATIVE_EROSION_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_dilate_matte",
        label="Native Dilate Matte",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg dilation intent as Blender's native Dilate/Erode compositor graph.",
        compositor_stack=_NATIVE_DILATION_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_convolution_sharpen",
        label="Native Convolution Sharpen",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg convolution sharpen kernel as Blender's native Convolve compositor graph.",
        compositor_stack=_NATIVE_CONVOLUTION_SHARPEN_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_average_blur",
        label="Native Average Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg avgblur intent as Blender's native Blur compositor graph.",
        compositor_stack=_NATIVE_AVERAGE_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_box_blur",
        label="Native Box Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg boxblur intent as Blender's native Blur compositor graph.",
        compositor_stack=_NATIVE_BOX_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_gaussian_blur",
        label="Native Gaussian Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg gblur intent as Blender's native Gaussian Blur compositor graph.",
        compositor_stack=_NATIVE_GAUSSIAN_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_smart_blur",
        label="Native Smart Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg smartblur intent as Blender's native Bilateral Blur compositor graph.",
        compositor_stack=_NATIVE_SMART_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_shape_adaptive_blur",
        label="Native Shape-Adaptive Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg sab intent as Blender's native Bilateral Blur compositor graph.",
        compositor_stack=_NATIVE_SHAPE_ADAPTIVE_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_edge_preserving_blur",
        label="Native Edge-Preserving Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg yaepblur intent as Blender's native Bilateral Blur compositor graph.",
        compositor_stack=_NATIVE_EDGE_PRESERVING_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_directional_blur",
        label="Native Directional Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg dblur intent as Blender's native Directional Blur compositor graph.",
        compositor_stack=_NATIVE_DIRECTIONAL_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_deband_cleanup",
        label="Native Deband Cleanup",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg deband cleanup intent as Blender's native edge-aware Bilateral Blur graph.",
        compositor_stack=_NATIVE_DEBAND_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_deblock_cleanup",
        label="Native Deblock Cleanup",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg deblock cleanup intent as Blender's native Anti-Aliasing compositor graph.",
        compositor_stack=_NATIVE_DEBLOCK_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_bokeh_blur",
        label="Bokeh Blur",
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Bokeh Blur node for stylized video blur.",
        compositor_stack=(
            _native_node("CompositorNodeBokehBlur", label="Bokeh Blur", inputs={"Size": 4.0, "Extend Bounds": False}),
        ),
    ),
    VideoTool(
        id="native_compositor_defocus",
        label="Defocus",
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Defocus node for depth-style softening.",
        compositor_stack=(
            _native_node("CompositorNodeDefocus", label="Defocus", inputs={"Z": 1.0}),
        ),
    ),
    VideoTool(
        id="native_compositor_glare",
        label="Glare",
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Glare node for highlight glow and streak finishing.",
        compositor_stack=(
            _native_node(
                "CompositorNodeGlare",
                label="Glare",
                inputs={"Type": "Fog Glow", "Quality": "Medium", "Threshold": 0.8, "Size": 6.0},
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_inpaint",
        label="Inpaint",
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Inpaint node for filling transparent or missing pixels.",
        compositor_stack=(
            _native_node("CompositorNodeInpaint", label="Inpaint", inputs={"Size": 3.0}),
        ),
    ),
    VideoTool(
        id="native_compositor_kuwahara",
        label="Kuwahara",
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Kuwahara node for edge-preserving stylized smoothing.",
        compositor_stack=(
            _native_node("CompositorNodeKuwahara", label="Kuwahara", inputs={"Size": 3.0}),
        ),
    ),
    VideoTool(
        id="native_compositor_pixelate",
        label="Pixelate",
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Pixelate node for pixel-grid finishing.",
        compositor_stack=(
            _native_node("CompositorNodePixelate", label="Pixelate", image_input="Color", image_output="Color", inputs={"Size": 6.0}),
        ),
    ),
    VideoTool(
        id="native_compositor_vector_blur",
        label="Vector Blur",
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Vector Blur node for motion-blur finishing graphs.",
        compositor_stack=(
            _native_node("CompositorNodeVecBlur", label="Vector Blur", inputs={"Samples": 8.0, "Shutter": 0.35}),
        ),
    ),
    VideoTool(
        id="native_compositor_levels_monitor",
        label="Levels Monitor",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Levels node as a selected-strip analysis monitor while preserving image output.",
        compositor_stack=(
            _native_node("CompositorNodeLevels", label="Levels Monitor", passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_image_info",
        label="Image Info Monitor",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Image Info node from the selected strip while preserving image output.",
        compositor_stack=(
            _native_node("CompositorNodeImageInfo", label="Image Info", passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_split_compare",
        label="Split Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Split node for before/after comparison graph work.",
        compositor_stack=(
            _native_node("CompositorNodeSplit", label="Split Compare", inputs={"Position": 0.5, "Rotation": 0.0}),
        ),
    ),
    VideoTool(
        id="native_compositor_switch_compare",
        label="Switch Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Switch node for toggling selected-strip image branches.",
        compositor_stack=(
            _native_node("CompositorNodeSwitch", label="Switch Compare", image_input="On", inputs={"Switch": True}),
        ),
    ),
    VideoTool(
        id="native_compositor_cryptomatte",
        label="Cryptomatte",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Cryptomatte node for matte extraction workflows.",
        compositor_stack=(
            _native_node("CompositorNodeCryptomatte", label="Cryptomatte"),
        ),
    ),
    VideoTool(
        id="native_compositor_cryptomatte_v2",
        label="Cryptomatte V2",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Cryptomatte V2 node for modern matte extraction workflows.",
        compositor_stack=(
            _native_node("CompositorNodeCryptomatteV2", label="Cryptomatte V2"),
        ),
    ),
    VideoTool(
        id="native_compositor_map_uv",
        label="Map UV",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Map UV node for UV-based image remapping graphs.",
        compositor_stack=(
            _native_node("CompositorNodeMapUV", label="Map UV", inputs={"Interpolation": "Bilinear"}),
        ),
    ),
    VideoTool(
        id="native_compositor_plane_track_deform",
        label="Plane Track Deform",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Plane Track Deform node for tracked-plane finishing graphs.",
        compositor_stack=(
            _native_node("CompositorNodePlaneTrackDeform", label="Plane Track Deform", inputs={"Motion Blur": False, "Samples": 8.0, "Shutter": 0.5}),
        ),
    ),
    VideoTool(
        id="native_compositor_z_combine",
        label="Z Combine",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Z Combine node for depth-compositing workflows.",
        compositor_stack=(
            _native_node("CompositorNodeZcombine", label="Z Combine", image_input="A", image_output="Result", inputs={"Use Alpha": True, "Anti-Alias": True}),
        ),
    ),
    VideoTool(
        id="native_compositor_sequencer_strip_info",
        label="Sequencer Strip Info",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Sequencer Strip Info node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeSequencerStripInfo", label="Sequencer Strip Info", skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_scene_time",
        label="Scene Time",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Scene Time node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeSceneTime", label="Scene Time", skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_time",
        label="Time",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Time node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeTime", label="Time", inputs={"Start Frame": 1.0, "End Frame": 120.0}, skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_track_position",
        label="Track Position",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Track Position node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeTrackPos", label="Track Position", inputs={"Frame": 1.0}, assign_source_clip=True, skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_normalize_luma",
        label="Normalize Luma",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender RGB-to-BW, Normalize, and Combine Color nodes to normalize selected-strip luminance.",
        compositor_stack=(
            ("NORMALIZE_LUMA", {"label": "Normalize Luma"}),
        ),
    ),
    VideoTool(
        id="native_compositor_image_coordinates",
        label="Image Coordinates",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Image Coordinates node as a selected-strip coordinate monitor.",
        compositor_stack=(
            _native_node("CompositorNodeImageCoordinates", label="Image Coordinates", passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_relative_to_pixel",
        label="Relative to Pixel",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Relative to Pixel node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeRelativeToPixel", label="Relative to Pixel", passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_movie_clip_source",
        label="Movie Clip Source",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates a second Blender Movie Clip source node assigned to the selected video strip.",
        compositor_stack=(
            _native_node("CompositorNodeMovieClip", label="Movie Clip Source", assign_source_clip=True, skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_viewer_tap",
        label="Viewer Tap",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Viewer node as a selected-strip tap.",
        compositor_stack=(
            _native_node("CompositorNodeViewer", label="Viewer Tap", passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_output_file_tap",
        label="Output File Tap",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Output File node as a selected-strip output tap.",
        compositor_stack=(
            _native_node("CompositorNodeOutputFile", label="Output File Tap", passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_image_source",
        label="Image Source",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Image source node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeImage", label="Image Source", skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_render_layers_source",
        label="Render Layers Source",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Render Layers source node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeRLayers", label="Render Layers Source", skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_normal_source",
        label="Normal Source",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Normal source node beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeNormal", label="Normal Source", skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_node_group_placeholder",
        label="Node Group Placeholder",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Group node placeholder beside the selected-strip graph.",
        compositor_stack=(
            _native_node("CompositorNodeGroup", label="Node Group", skip_link_input=True, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_rgb_overlay",
        label="RGB Overlay",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender RGB and Alpha Over nodes to overlay an editable generated color on the selected strip.",
        compositor_stack=(
            ("RGB_OVERLAY", {"label": "RGB Overlay", "outputs": {"Color": (1.0, 1.0, 1.0, 1.0)}, "factor": 0.18}),
        ),
    ),
    VideoTool(
        id="native_compositor_blank_image_overlay",
        label="Blank Image Overlay",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender Blank Image and Alpha Over nodes to overlay a generated image on the selected strip.",
        compositor_stack=(
            ("BLANK_IMAGE_OVERLAY", {"label": "Blank Image Overlay", "inputs": {"Color": (0.0, 0.0, 0.0, 1.0), "Size": (640, 360)}, "factor": 0.15}),
        ),
    ),
    VideoTool(
        id="native_compositor_text_overlay",
        label="Text Overlay",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender String to Image and Alpha Over nodes to overlay editable text on the selected strip.",
        compositor_stack=(
            ("TEXT_OVERLAY", {"label": "Text Overlay", "inputs": {"String": "VIDEO TOOLKIT", "Size": 48.0}, "factor": 0.35}),
        ),
    ),
    VideoTool(
        id="native_compositor_bokeh_image_blur",
        label="Bokeh Image Blur",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender Bokeh Image and Bokeh Blur nodes to blur the selected strip with an editable bokeh kernel.",
        compositor_stack=(
            ("BOKEH_IMAGE_BLUR", {"label": "Bokeh Image Blur", "bokeh_inputs": {"Flaps": 6.0, "Angle": 0.0, "Roundness": 0.5}, "blur_inputs": {"Size": 4.0, "Extend Bounds": False}}),
        ),
    ),
    VideoTool(
        id="native_compositor_switch_view",
        label="Switch View",
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Switch View node using the selected strip as the left view input.",
        compositor_stack=(
            _native_node("CompositorNodeSwitchView", label="Switch View", image_input="left"),
        ),
    ),
    VideoTool(
        id="native_hqdn3d_denoise",
        label="Native HQDN3D Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg hqdn3d intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_HQDN3D_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_nlmeans_denoise",
        label="Native NLMeans Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg nlmeans intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_NLMEANS_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_bm3d_denoise",
        label="Native BM3D Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bm3d intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_BM3D_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_wavelet_denoise",
        label="Native Wavelet Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg owdenoise intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_WAVELET_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vague_denoise",
        label="Native Vague Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vaguedenoiser intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_VAGUE_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_adaptive_temporal_denoise",
        label="Native Adaptive Temporal Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg atadenoise intent as Blender's native compositor Denoise graph, with temporal behavior represented as editable spatial strength.",
        compositor_stack=_NATIVE_ADAPTIVE_TEMPORAL_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_median_despeckle",
        label="Native Median Despeckle",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg median cleanup intent as Blender's native compositor Despeckle graph.",
        compositor_stack=_NATIVE_MEDIAN_DESPECKLE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_dedot_cleanup",
        label="Native Dedot Cleanup",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg dedot cleanup intent as Blender's native compositor Despeckle graph.",
        compositor_stack=_NATIVE_DEDOT_CLEANUP_TRANSLATION.compositor_nodes,
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
        id="native_compositor_scale_fit",
        label="Native Scale Fit",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scale intent as Blender's native compositor Scale graph.",
        compositor_stack=_NATIVE_SCALE_FIT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_center_crop",
        label="Native Center Crop",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg crop intent as Blender's native compositor Crop graph.",
        compositor_stack=_NATIVE_CENTER_CROP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_rotate_level",
        label="Native Rotate Level",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg rotate intent as Blender's native compositor Rotate graph.",
        compositor_stack=_NATIVE_ROTATE_LEVEL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_transpose_clockwise",
        label="Native Transpose Clockwise",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg transpose intent as Blender's native Rotate/Flip compositor graph.",
        compositor_stack=_NATIVE_TRANSPOSE_CLOCKWISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_flip_horizontal",
        label="Native Flip Horizontal",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg hflip intent as Blender's native compositor Flip graph.",
        compositor_stack=_NATIVE_HORIZONTAL_FLIP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_flip_vertical",
        label="Native Flip Vertical",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vflip intent as Blender's native compositor Flip graph.",
        compositor_stack=_NATIVE_VERTICAL_FLIP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_lens_correction",
        label="Native Lens Correction",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg lenscorrection intent as Blender's native Lens Distortion compositor graph.",
        compositor_stack=_NATIVE_LENS_CORRECTION_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_compositor_stabilize_node",
        label="Native Stabilize Node",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Stabilize node and assigns the selected movie strip as its clip source.",
        compositor_stack=(
            _native_node(
                "CompositorNodeStabilize",
                label="Stabilize",
                assign_source_clip=True,
                inputs={"Frame": 1.0, "Invert": False, "Interpolation": "Bilinear"},
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_movie_distortion_node",
        label="Native Movie Distortion",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Movie Distortion node and assigns the selected movie strip as its clip source.",
        compositor_stack=(
            _native_node("CompositorNodeMovieDistortion", label="Movie Distortion", assign_source_clip=True, inputs={"Type": "Undistort"}),
        ),
    ),
    VideoTool(
        id="native_compositor_corner_pin",
        label="Corner Pin",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Corner Pin node for perspective placement work.",
        compositor_stack=(
            _native_node(
                "CompositorNodeCornerPin",
                label="Corner Pin",
                inputs={
                    "Upper Left": (0.0, 1.0),
                    "Upper Right": (1.0, 1.0),
                    "Lower Left": (0.0, 0.0),
                    "Lower Right": (1.0, 0.0),
                    "Interpolation": "Bilinear",
                },
            ),
        ),
    ),
    VideoTool(
        id="native_compositor_displace",
        label="Displace",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Displace node for pixel displacement graphs.",
        compositor_stack=(
            _native_node("CompositorNodeDisplace", label="Displace", inputs={"Interpolation": "Bilinear"}),
        ),
    ),
    VideoTool(
        id="native_compositor_transform",
        label="Transform",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Transform node for translation, rotation, and scale.",
        compositor_stack=(
            _native_node("CompositorNodeTransform", label="Transform", inputs={"X": 12.0, "Y": 0.0, "Angle": 0.0, "Scale": 1.0}),
        ),
    ),
    VideoTool(
        id="native_compositor_translate",
        label="Translate",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Translate node for pixel-offset finishing.",
        compositor_stack=(
            _native_node("CompositorNodeTranslate", label="Translate", inputs={"X": 12.0, "Y": 0.0, "Interpolation": "Bilinear"}),
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
