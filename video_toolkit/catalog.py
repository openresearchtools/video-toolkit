"""Shared filter catalog for Blender UI, CLI, and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .ffmpeg_native import (
    NATIVE_FFMPEG_ADVANCED_FILTERS,
    NATIVE_FFMPEG_EDITING_FILTERS,
    NATIVE_FFMPEG_INTEROP_FILTERS,
    NATIVE_FFMPEG_SOURCE_FILTERS,
    NATIVE_FFMPEG_TIMELINE_FILTERS,
    translate_filter_chain,
)


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
    color_management: tuple[tuple[str, str], ...] = ()
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


def _color_model_board(
    mode: str,
    *,
    label: str,
    ycc_mode: str = "ITUBT709",
    grade_type: str = "HUE_SAT",
    grade: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "COLOR_MODEL_BOARD",
        {
            "label": label,
            "mode": mode,
            "ycc_mode": ycc_mode,
            "grade_type": grade_type,
            "grade": grade or {},
        },
    )


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
_PROCAMP_VAAPI_TRANSLATION = translate_filter_chain("procamp_vaapi=brightness=8:contrast=1.18:saturation=1.14:hue=4")
_TONEMAP_OPENCL_TRANSLATION = translate_filter_chain("tonemap_opencl=tonemap=mobius:param=0.35:desat=0.45:peak=600:transfer=bt709:matrix=bt709:primaries=bt709:range=pc")
_TONEMAP_VAAPI_TRANSLATION = translate_filter_chain("tonemap_vaapi=transfer=bt709:matrix=bt709:primaries=bt709:range=pc")
_COLORSPACE_BT709_FULL_TRANSLATION = translate_filter_chain("colorspace=iall=bt709:all=bt709:irange=tv:range=pc")
_COLORSPACE_BT709_TO_BT2020_TRANSLATION = translate_filter_chain("colorspace=iall=bt709:all=bt2020:irange=tv:range=pc")
_COLORSPACE_SRGB_REVIEW_TRANSLATION = translate_filter_chain("colorspace=iall=bt709:all=srgb:irange=tv:range=pc")
_COLORMATRIX_601_TO_709_TRANSLATION = translate_filter_chain("colormatrix=src=smpte170m:dst=bt709")
_COLORMATRIX_709_TO_2020_TRANSLATION = translate_filter_chain("colormatrix=src=bt709:dst=bt2020")
_SETPARAMS_REC2020_PQ_TRANSLATION = translate_filter_chain("setparams=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc:range=full")
_SETRANGE_FULL_TRANSLATION = translate_filter_chain("setrange=full")
_SETRANGE_LIMITED_TRANSLATION = translate_filter_chain("setrange=limited")
_ZSCALE_709_TO_2020_HDR_TRANSLATION = translate_filter_chain(
    "zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:"
    "primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full"
)
_COLOR_PIPELINE_METADATA_TRANSLATION = translate_filter_chain(
    "colorspace=iall=bt709:all=bt709:irange=tv:range=pc,"
    "colorspace_cuda=range=pc,"
    "colormatrix=src=smpte170m:dst=bt709,"
    "setparams=color_primaries=bt2020:color_trc=bt2020-10:colorspace=bt2020nc:range=full,"
    "setrange=limited,"
    "zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:"
    "primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full"
)
_COLOR_PIPELINE_METADATA_PROFILE = (
    ("sequencer_input", "bt709"),
    ("input_matrix", "bt709"),
    ("input_primaries", "bt709"),
    ("input_transfer", "bt709"),
    ("input_range", "limited"),
    ("output_matrix", "bt2020"),
    ("output_primaries", "bt2020"),
    ("output_transfer", "bt2020-10"),
    ("output_range", "limited"),
)
_SELECTIVE_COLOR_TRANSLATION = translate_filter_chain(
    "selectivecolor=reds=0.10 -0.04 -0.02 0.00:blues=-0.04 0.02 0.10 0.03:whites=0.02 0.00 -0.08 0.01"
)
_COLORIZE_TRANSLATION = translate_filter_chain("colorize=hue=210:saturation=0.50:lightness=0.55:mix=0.70")
_GREY_EDGE_TRANSLATION = translate_filter_chain("greyedge=difford=2:minknorm=5:sigma=2")
_PSEUDOCOLOR_TRANSLATION = translate_filter_chain("pseudocolor=preset=viridis:opacity=0.85:index=1")
_LUT_INVERT_TRANSLATION = translate_filter_chain("lutrgb=r=negval:g=val*0.9:b=val+24")
_LUT1D_FILM_LOOK_TRANSLATION = translate_filter_chain("lut1d=file=warm_print.spi1d:interp=cubic")
_LUT3D_SCENE_LOOK_TRANSLATION = translate_filter_chain("lut3d=file=teal_orange.cube:interp=tetrahedral")
_HALDCLUT_DISPLAY_MATCH_TRANSLATION = translate_filter_chain("haldclut=interp=tetrahedral:clut=all")
_COLORMAP_PALETTE_MATCH_TRANSLATION = translate_filter_chain("colormap=patch_size=64x64:nb_patches=32:type=absolute:kernel=weuclidean")
_PALETTE_GENERATE_TRANSLATION = translate_filter_chain("palettegen=max_colors=96:stats_mode=diff:reserve_transparent=1")
_PALETTE_USE_TRANSLATION = translate_filter_chain("paletteuse=dither=sierra2_4a:diff_mode=rectangle")
_AMPLIFY_COLOR_TRANSLATION = translate_filter_chain("amplify=radius=3:factor=2.6:threshold=12:tolerance=2")
_HISTOGRAM_EQUALIZE_TRANSLATION = translate_filter_chain("histeq=strength=0.42:intensity=0.30:antibanding=1")
_COLOR_HOLD_TRANSLATION = translate_filter_chain("colorhold=color=blue:similarity=0.18:blend=0.15")
_HSV_HOLD_TRANSLATION = translate_filter_chain("hsvhold=hue=210:sat=0.75:val=0.85:similarity=0.12:blend=0.08")
_GEQ_RGB_MATH_TRANSLATION = translate_filter_chain("geq=r='r(X,Y)*1.04':g='g(X,Y)+4':b='b(X,Y)-6'")
_MIDWAY_EQUALIZE_TRANSLATION = translate_filter_chain("midequalizer=planes=7")
_TEMPORAL_MIDWAY_EQUALIZE_TRANSLATION = translate_filter_chain("tmidequalizer=radius=9:sigma=0.55:planes=7")
_RGB_GAMMA_BOARD_TRANSLATION = translate_filter_chain(
    "eq=brightness=0.01:contrast=1.04:saturation=1.04:gamma=1.03:gamma_r=1.09:gamma_g=1.00:gamma_b=0.94:gamma_weight=0.70"
)
_CHANNEL_MIXER_BALANCE_TRANSLATION = translate_filter_chain(
    "colorchannelmixer=rr=1.06:rg=-0.02:rb=-0.01:gr=-0.01:gg=1.04:gb=-0.01:br=-0.04:bg=0.02:bb=1.08"
)
_OPPONENT_COLOR_CONTRAST_TRANSLATION = translate_filter_chain(
    "colorcontrast=rc=0.18:gm=-0.08:by=0.12:rcw=0.70:gmw=0.45:byw=0.55:pl=1"
)
_LOW_HIGH_COLORCORRECT_TRANSLATION = translate_filter_chain(
    "colorcorrect=rl=0.06:bl=-0.04:rh=0.03:bh=-0.03:saturation=1.06"
)
_INDEPENDENT_RGB_NORMALIZE_TRANSLATION = translate_filter_chain(
    "normalize=blackpt=#08080c:whitept=#f4f1e8:smoothing=48:independence=1.0:strength=0.8"
)
_HUE_SAT_INTENSITY_TRANSLATION = translate_filter_chain(
    "huesaturation=hue=3:saturation=0.18:intensity=0.06:strength=0.85"
)
_HIGHLIGHT_DESAT_TONEMAP_TRANSLATION = translate_filter_chain(
    "tonemap=tonemap=mobius:param=0.45:desat=0.55:peak=600"
)
_BROADCAST_GAMMA_GUARD_TRANSLATION = translate_filter_chain(
    "limiter=min=16:max=235,eq=gamma=0.96:contrast=1.03:saturation=0.98"
)
_GRAY_WORLD_NEUTRALIZER_TRANSLATION = translate_filter_chain(
    "grayworld,eq=contrast=1.02:saturation=1.01:gamma=1.0"
)
_RGB_LUT_TRIM_TRANSLATION = translate_filter_chain("lutrgb=r=val*1.04:g=val*1.00:b=val*0.96")
_SELECTIVE_NEUTRAL_BALANCE_TRANSLATION = translate_filter_chain(
    "selectivecolor=reds=-0.04 0.02 0.02 0.00:yellows=0.02 -0.02 -0.04 0.00:"
    "greens=0.00 -0.04 0.02 0.00:cyans=0.02 0.00 -0.03 0.00:"
    "blues=-0.03 0.02 0.05 0.00:magentas=0.03 -0.02 0.00 0.00:"
    "neutrals=0.00 0.00 0.00 0.02"
)
_NATIVE_HISTOGRAM_SCOPE_TRANSLATION = translate_filter_chain("histogram=mode=levels:components=all:intensity=0.75")
_NATIVE_TEMPORAL_HISTOGRAM_SCOPE_TRANSLATION = translate_filter_chain("thistogram=mode=levels:components=all:intensity=0.70")
_NATIVE_WAVEFORM_SCOPE_TRANSLATION = translate_filter_chain("waveform=display=overlay:components=7:intensity=0.75")
_NATIVE_VECTOR_SCOPE_TRANSLATION = translate_filter_chain("vectorscope=mode=color3:components=7:intensity=0.80")
_NATIVE_CIE_SCOPE_TRANSLATION = translate_filter_chain("ciescope=system=rec709:cie=xyy:intensity=0.75")
_NATIVE_DATA_SCOPE_TRANSLATION = translate_filter_chain("datascope=mode=color2:components=all")
_NATIVE_OSCILLOSCOPE_SCOPE_TRANSLATION = translate_filter_chain("oscilloscope=components=7:intensity=0.65")
_NATIVE_PIXEL_SCOPE_TRANSLATION = translate_filter_chain("pixscope=x=0.5:y=0.5:w=9:h=9:o=0.65")
_NATIVE_SHOWPALETTE_TRANSLATION = translate_filter_chain("showpalette=s=30")
_NATIVE_THUMBNAIL_TRANSLATION = translate_filter_chain("thumbnail=n=60")
_CUDA_THUMBNAIL_TRANSLATION = translate_filter_chain("thumbnail_cuda=n=60")
_NATIVE_SIGNAL_STATS_TRANSLATION = translate_filter_chain("signalstats=stat=tout+vrep+brng")
_NATIVE_COLOR_DETECT_TRANSLATION = translate_filter_chain("colordetect=mode=color_range+alpha_mode+all")
_NATIVE_ENTROPY_TRANSLATION = translate_filter_chain("entropy=mode=normal:levels=256")
_NATIVE_BLACK_DETECT_TRANSLATION = translate_filter_chain("blackdetect=d=1.0:pic_th=0.96:pix_th=0.08")
_NATIVE_VULKAN_BLACK_DETECT_TRANSLATION = translate_filter_chain("blackdetect_vulkan=d=1.0:pic_th=0.96:pix_th=0.08")
_NATIVE_BLACK_FRAME_TRANSLATION = translate_filter_chain("blackframe=amount=96:threshold=28")
_NATIVE_BLOCK_DETECT_TRANSLATION = translate_filter_chain("blockdetect=period_min=3:period_max=24:planes=1")
_NATIVE_BLUR_DETECT_TRANSLATION = translate_filter_chain("blurdetect=high=0.12:low=0.06:radius=40:block_pct=80:planes=1")
_NATIVE_CROP_DETECT_TRANSLATION = translate_filter_chain("cropdetect=limit=0.094:round=16:reset=30:skip=2")
_NATIVE_BBOX_DETECT_TRANSLATION = translate_filter_chain("bbox=min_val=16")
_NATIVE_BITPLANE_NOISE_TRANSLATION = translate_filter_chain("bitplanenoise=bitplane=1:filter=1")
_NATIVE_FREEZE_DETECT_TRANSLATION = translate_filter_chain("freezedetect=n=0.001:d=2")
_NATIVE_SCENE_DETECT_TRANSLATION = translate_filter_chain("scdet=threshold=10:sc_pass=0")
_NATIVE_VULKAN_SCENE_DETECT_TRANSLATION = translate_filter_chain("scdet_vulkan=threshold=10:sc_pass=0")
_NATIVE_VFR_DETECT_TRANSLATION = translate_filter_chain("vfrdet")
_NATIVE_INTERLACE_DETECT_TRANSLATION = translate_filter_chain("idet=intl_thres=1.04:prog_thres=1.5:rep_thres=3")
_NATIVE_IDENTITY_COMPARE_TRANSLATION = translate_filter_chain("identity=eof_action=repeat:repeatlast=1:ts_sync_mode=nearest")
_NATIVE_SSIM_COMPARE_TRANSLATION = translate_filter_chain("ssim=stats_file=vtk_ssim.log:eof_action=repeat:repeatlast=1:ts_sync_mode=nearest")
_NATIVE_PSNR_COMPARE_TRANSLATION = translate_filter_chain("psnr=stats_file=vtk_psnr.log:stats_version=2:output_max=1:eof_action=repeat")
_NATIVE_XPSNR_COMPARE_TRANSLATION = translate_filter_chain("xpsnr=stats_file=vtk_xpsnr.log:eof_action=repeat")
_NATIVE_CORR_COMPARE_TRANSLATION = translate_filter_chain("corr=eof_action=repeat:repeatlast=1")
_NATIVE_MSAD_COMPARE_TRANSLATION = translate_filter_chain("msad=eof_action=repeat:repeatlast=1")
_NATIVE_VIF_COMPARE_TRANSLATION = translate_filter_chain("vif=stats_file=vtk_vif.log:eof_action=repeat")
_NATIVE_VMAF_MOTION_TRANSLATION = translate_filter_chain("vmafmotion=stats_file=vtk_vmafmotion.log")
_NATIVE_XCORRELATE_COMPARE_TRANSLATION = translate_filter_chain("xcorrelate=planes=7:secondary=all:eof_action=repeat")
_CHROMA_KEY_MATTE_TRANSLATION = translate_filter_chain("chromakey=color=green:similarity=0.18:blend=0.06")
_CUDA_CHROMA_KEY_MATTE_TRANSLATION = translate_filter_chain("chromakey_cuda=color=green:similarity=0.18:blend=0.06")
_COLOR_KEY_MATTE_TRANSLATION = translate_filter_chain("colorkey=color=blue:similarity=0.16:blend=0.04")
_OPENCL_COLOR_KEY_MATTE_TRANSLATION = translate_filter_chain("colorkey_opencl=color=blue:similarity=0.16:blend=0.04")
_HSV_KEY_MATTE_TRANSLATION = translate_filter_chain("hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.12:blend=0.03")
_LUMA_KEY_MATTE_TRANSLATION = translate_filter_chain("lumakey=threshold=0.20:tolerance=0.10:softness=0.04")
_DESPILL_TRANSLATION = translate_filter_chain("despill=type=green:mix=0.65:expand=0.12:green=-1.0")
_BACKGROUND_KEY_TRANSLATION = translate_filter_chain("backgroundkey=threshold=0.08:similarity=0.12:blend=0.04")
_THRESHOLD_MATTE_TRANSLATION = translate_filter_chain("threshold=planes=7")
_MASKED_THRESHOLD_MATTE_TRANSLATION = translate_filter_chain("maskedthreshold=threshold=2048:planes=7:mode=abs")
_BLEND_OVERLAY_TRANSLATION = translate_filter_chain("blend=all_mode=overlay:all_opacity=0.35")
_VULKAN_BLEND_TRANSLATION = translate_filter_chain("blend_vulkan=all_mode=multiply:all_opacity=0.42")
_TEMPORAL_BLEND_TRANSLATION = translate_filter_chain("tblend=all_mode=average:all_opacity=0.45")
_LUT2_EXPRESSION_MIX_TRANSLATION = translate_filter_chain("lut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x")
_TEMPORAL_LUT2_EXPRESSION_TRANSLATION = translate_filter_chain("tlut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x")
_MASKED_MERGE_TRANSLATION = translate_filter_chain("maskedmerge=planes=15")
_MERGEPLANES_ROUTER_TRANSLATION = translate_filter_chain("mergeplanes=map0p=2:map1p=1:map2p=0:map3p=3")
_RGBA_CHANNEL_SHIFT_TRANSLATION = translate_filter_chain("rgbashift=rh=5:rv=-2:bh=-4:bv=2")
_CHROMA_CHANNEL_SHIFT_TRANSLATION = translate_filter_chain("chromashift=cbh=3:cbv=-1:crh=-3:crv=1")
_CHROMATIC_ABERRATION_TRANSLATION = translate_filter_chain("chromaber_vulkan=dist_x=2.0:dist_y=-1.0")
_LUMA_PLANE_EXTRACT_TRANSLATION = translate_filter_chain("extractplanes=planes=y")
_ALPHA_EXTRACT_TRANSLATION = translate_filter_chain("alphaextract")
_ALPHA_MERGE_TRANSLATION = translate_filter_chain("alphamerge")
_PREMULTIPLY_ALPHA_TRANSLATION = translate_filter_chain("premultiply")
_PLANE_SHUFFLE_BGR_TRANSLATION = translate_filter_chain("shuffleplanes=2:1:0:3")
_STRAIGHT_ALPHA_TRANSLATION = translate_filter_chain("unpremultiply")
_NATIVE_ELBG_POSTERIZE_TRANSLATION = translate_filter_chain("elbg=codebook_length=32:nb_steps=1")
_NATIVE_UNSHARP_TRANSLATION = translate_filter_chain("unsharp=5:5:0.55:3:3:0.20")
_OPENCL_UNSHARP_TRANSLATION = translate_filter_chain("unsharp_opencl=lx=5:ly=5:la=0.55:cx=3:cy=3:ca=0.20")
_NATIVE_CAS_SHARPEN_TRANSLATION = translate_filter_chain("cas=strength=0.45")
_NATIVE_SOBEL_TRANSLATION = translate_filter_chain("sobel=scale=1.2:delta=0.02")
_OPENCL_SOBEL_TRANSLATION = translate_filter_chain("sobel_opencl=scale=1.2:delta=0.02")
_NATIVE_PREWITT_TRANSLATION = translate_filter_chain("prewitt=scale=0.9:delta=0.01")
_OPENCL_PREWITT_TRANSLATION = translate_filter_chain("prewitt_opencl=scale=0.9:delta=0.01")
_NATIVE_ROBERTS_TRANSLATION = translate_filter_chain("roberts=scale=0.9:delta=0.01")
_OPENCL_ROBERTS_TRANSLATION = translate_filter_chain("roberts_opencl=scale=0.9:delta=0.01")
_NATIVE_KIRSCH_TRANSLATION = translate_filter_chain("kirsch=scale=0.8")
_NATIVE_EDGE_DETECT_TRANSLATION = translate_filter_chain("edgedetect=high=0.20:low=0.08:mode=wires")
_NATIVE_EROSION_TRANSLATION = translate_filter_chain(
    "erosion=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000"
)
_OPENCL_EROSION_TRANSLATION = translate_filter_chain(
    "erosion_opencl=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000"
)
_NATIVE_DILATION_TRANSLATION = translate_filter_chain(
    "dilation=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000"
)
_OPENCL_DILATION_TRANSLATION = translate_filter_chain(
    "dilation_opencl=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000"
)
_NATIVE_CONVOLUTION_SHARPEN_TRANSLATION = translate_filter_chain(
    "convolution=0m='0 -1 0 -1 5 -1 0 -1 0':0rdiv=1:0bias=0"
)
_OPENCL_CONVOLUTION_TRANSLATION = translate_filter_chain(
    "convolution_opencl=0m='0 -1 0 -1 5 -1 0 -1 0':0rdiv=1:0bias=0"
)
_NATIVE_AVERAGE_BLUR_TRANSLATION = translate_filter_chain("avgblur=sizeX=4:sizeY=6")
_OPENCL_AVERAGE_BLUR_TRANSLATION = translate_filter_chain("avgblur_opencl=sizeX=4:sizeY=6")
_VULKAN_AVERAGE_BLUR_TRANSLATION = translate_filter_chain("avgblur_vulkan=sizeX=4:sizeY=6")
_NATIVE_BOX_BLUR_TRANSLATION = translate_filter_chain("boxblur=lr=3:lp=2")
_OPENCL_BOX_BLUR_TRANSLATION = translate_filter_chain("boxblur_opencl=lr=3:lp=2")
_NATIVE_GAUSSIAN_BLUR_TRANSLATION = translate_filter_chain("gblur=sigma=1.2:steps=2:sigmaV=0.8")
_VULKAN_GAUSSIAN_BLUR_TRANSLATION = translate_filter_chain("gblur_vulkan=sigma=1.2:steps=2:sigmaV=0.8")
_NATIVE_VARIABLE_BLUR_TRANSLATION = translate_filter_chain("varblur=min_r=1:max_r=9:planes=7")
_NATIVE_BILATERAL_TRANSLATION = translate_filter_chain("bilateral=sigmaS=3:sigmaR=0.12")
_CUDA_BILATERAL_TRANSLATION = translate_filter_chain("bilateral_cuda=sigmaS=3:sigmaR=0.12")
_NATIVE_SMART_BLUR_TRANSLATION = translate_filter_chain("smartblur=lr=2:ls=0.8:lt=8")
_NATIVE_DIRECTIONAL_BLUR_TRANSLATION = translate_filter_chain("dblur=angle=30:radius=12")
_NATIVE_SHAPE_ADAPTIVE_BLUR_TRANSLATION = translate_filter_chain("sab=lr=3:lpfr=1.2:ls=8:cr=2:cs=0.8:ct=6")
_NATIVE_EDGE_PRESERVING_BLUR_TRANSLATION = translate_filter_chain("yaepblur=radius=4:sigma=96")
_NATIVE_HQDN3D_DENOISE_TRANSLATION = translate_filter_chain("hqdn3d=1.5:1.5:6:6")
_NATIVE_NLMEANS_DENOISE_TRANSLATION = translate_filter_chain("nlmeans=s=2.5:p=7:r=9")
_OPENCL_NLMEANS_DENOISE_TRANSLATION = translate_filter_chain("nlmeans_opencl=s=2.5:p=7:r=9")
_VULKAN_NLMEANS_DENOISE_TRANSLATION = translate_filter_chain("nlmeans_vulkan=s=2.5:p=7:r=9")
_NATIVE_BM3D_DENOISE_TRANSLATION = translate_filter_chain("bm3d=sigma=3:block=4:bstep=2:group=1")
_NATIVE_DCT_DENOISE_TRANSLATION = translate_filter_chain("dctdnoiz=sigma=4.5:overlap=0.5")
_NATIVE_WAVELET_DENOISE_TRANSLATION = translate_filter_chain("owdenoise=depth=8:luma_strength=0.8:chroma_strength=0.5")
_NATIVE_VAGUE_DENOISE_TRANSLATION = translate_filter_chain("vaguedenoiser=threshold=1.5:method=garrote:nsteps=6")
_NATIVE_ADAPTIVE_TEMPORAL_DENOISE_TRANSLATION = translate_filter_chain(
    "atadenoise=0a=0.02:0b=0.04:1a=0.02:1b=0.04:2a=0.02:2b=0.04"
)
_NATIVE_MEDIAN_DESPECKLE_TRANSLATION = translate_filter_chain("median=radius=2:planes=15")
_NATIVE_TEMPORAL_MEDIAN_TRANSLATION = translate_filter_chain("tmedian=radius=3:percentile=0.50:planes=15")
_NATIVE_XMEDIAN_TRANSLATION = translate_filter_chain("xmedian=inputs=3:planes=15:percentile=0.50")
_NATIVE_DEDOT_CLEANUP_TRANSLATION = translate_filter_chain("dedot=lt=0.08:tl=0.08")
_NATIVE_DEBAND_TRANSLATION = translate_filter_chain("deband=1thr=0.03:2thr=0.025:3thr=0.02:range=20")
_NATIVE_DEBLOCK_TRANSLATION = translate_filter_chain("deblock=block=16:alpha=0.12:beta=0.08")
_NATIVE_DEFLICKER_TRANSLATION = translate_filter_chain("deflicker=s=12:m=median")
_NATIVE_BWDIF_DEINTERLACE_TRANSLATION = translate_filter_chain("bwdif=mode=send_frame:parity=auto:deint=all")
_CUDA_BWDIF_DEINTERLACE_TRANSLATION = translate_filter_chain("bwdif_cuda=mode=send_frame:parity=auto:deint=all")
_VULKAN_BWDIF_DEINTERLACE_TRANSLATION = translate_filter_chain("bwdif_vulkan=mode=send_frame:parity=auto:deint=all")
_NATIVE_YADIF_DEINTERLACE_TRANSLATION = translate_filter_chain("yadif=mode=send_frame:parity=auto:deint=all")
_CUDA_YADIF_DEINTERLACE_TRANSLATION = translate_filter_chain("yadif_cuda=mode=send_frame:parity=auto:deint=all")
_NATIVE_ESTDIF_DEINTERLACE_TRANSLATION = translate_filter_chain("estdif=mode=send_frame:parity=auto:deint=all")
_NATIVE_W3FDIF_DEINTERLACE_TRANSLATION = translate_filter_chain("w3fdif=mode=send_frame:parity=auto:deint=all")
_QSV_DEINTERLACE_TRANSLATION = translate_filter_chain("deinterlace_qsv=mode=send_frame:parity=auto:deint=all")
_VAAPI_DEINTERLACE_TRANSLATION = translate_filter_chain("deinterlace_vaapi=mode=send_frame:parity=auto:deint=all")
_NATIVE_FIELD_EXTRACT_TRANSLATION = translate_filter_chain("field=type=top")
_NATIVE_FIELD_HINT_TRANSLATION = translate_filter_chain("fieldhint=hint=field.hints:mode=relative")
_NATIVE_FIELD_MATCH_TRANSLATION = translate_filter_chain("fieldmatch=order=auto:mode=pc_n")
_NATIVE_FIELD_ORDER_TRANSLATION = translate_filter_chain("fieldorder=order=tff")
_NATIVE_SET_FIELD_TRANSLATION = translate_filter_chain("setfield=mode=prog")
_NATIVE_SEPARATE_FIELDS_TRANSLATION = translate_filter_chain("separatefields")
_NATIVE_REPEAT_FIELDS_TRANSLATION = translate_filter_chain("repeatfields")
_NATIVE_TELECINE_TRANSLATION = translate_filter_chain("telecine=pattern=23")
_NATIVE_DETELECINE_TRANSLATION = translate_filter_chain("detelecine=pattern=23")
_NATIVE_DECIMATE_TRANSLATION = translate_filter_chain("decimate=cycle=5:dupthresh=1.1:scthresh=15")
_NATIVE_MPDECIMATE_TRANSLATION = translate_filter_chain("mpdecimate=hi=64*12:lo=64*5:frac=0.33")
_NATIVE_MCDEINT_TRANSLATION = translate_filter_chain("mcdeint=mode=fast:parity=auto")
_NATIVE_NNEDI_TRANSLATION = translate_filter_chain("nnedi=weights=nnedi3_weights.bin:deint=all")
_NATIVE_DESHAKE_TRANSLATION = translate_filter_chain("deshake=rx=16:ry=16")
_OPENCL_DESHAKE_TRANSLATION = translate_filter_chain("deshake_opencl=rx=16:ry=16")
_NATIVE_VIDSTAB_DETECT_TRANSLATION = translate_filter_chain("vidstabdetect=shakiness=5:accuracy=15:result=transforms.trf")
_NATIVE_VIDSTAB_TRANSFORM_TRANSLATION = translate_filter_chain("vidstabtransform=input=transforms.trf:smoothing=30:zoom=2")
_NATIVE_TEMPORAL_MIX_TRANSLATION = translate_filter_chain("tmix=frames=3:weights='1 2 1'")
_NATIVE_FPS_RESAMPLE_TRANSLATION = translate_filter_chain("fps=fps=30:round=near")
_NATIVE_FRAMERATE_INTERPOLATION_TRANSLATION = translate_filter_chain("framerate=fps=60:interp_start=15:interp_end=240")
_NATIVE_MINTERPOLATE_TRANSLATION = translate_filter_chain("minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
_NATIVE_CHROMANR_CLEANUP_TRANSLATION = translate_filter_chain("chromanr=thres=24:sizew=5:sizeh=5")
_VAAPI_DENOISE_TRANSLATION = translate_filter_chain("denoise_vaapi=denoise=18")
_NATIVE_FFT_DENOISE_TRANSLATION = translate_filter_chain("fftdnoiz=sigma=1.8:amount=1.0")
_NATIVE_FFT_DETAIL_TRANSLATION = translate_filter_chain("fftfilt=dc_Y=0:weight_Y=1.35")
_NATIVE_GRADFUN_DEBAND_TRANSLATION = translate_filter_chain("gradfun=strength=1.2:radius=12")
_VAAPI_SHARPNESS_TRANSLATION = translate_filter_chain("sharpness_vaapi=sharpness=44")
_NATIVE_XBR_UPSCALE_TRANSLATION = translate_filter_chain("xbr=n=2")
_NATIVE_SCALE_FIT_TRANSLATION = translate_filter_chain("scale=w=1920:h=1080:flags=lanczos")
_CUDA_SCALE_FIT_TRANSLATION = translate_filter_chain("scale_cuda=w=1920:h=1080:flags=lanczos")
_QSV_SCALE_FIT_TRANSLATION = translate_filter_chain("scale_qsv=w=1920:h=1080:flags=lanczos")
_VAAPI_SCALE_FIT_TRANSLATION = translate_filter_chain("scale_vaapi=w=1920:h=1080:flags=lanczos")
_VULKAN_SCALE_FIT_TRANSLATION = translate_filter_chain("scale_vulkan=w=1920:h=1080:flags=lanczos")
_NATIVE_FILLBORDERS_TRANSLATION = translate_filter_chain("fillborders=left=16:right=16:top=10:bottom=10:mode=mirror")
_NATIVE_FLOODFILL_TRANSLATION = translate_filter_chain("floodfill=x=24:y=24:color=black:similarity=0.08")
_NATIVE_UNTILE_TRANSLATION = translate_filter_chain("untile=layout=2x2:index=0")
_NATIVE_V360_TRANSLATION = translate_filter_chain("v360=input=equirect:output=flat:yaw=12:pitch=-4:roll=0:h_fov=110")
_NATIVE_CENTER_CROP_TRANSLATION = translate_filter_chain("crop=w=iw*0.9:h=ih*0.9:x=iw*0.05:y=ih*0.05")
_NATIVE_ROTATE_LEVEL_TRANSLATION = translate_filter_chain("rotate=angle=2*PI/180:fillcolor=black")
_NATIVE_TRANSPOSE_CLOCKWISE_TRANSLATION = translate_filter_chain("transpose=dir=clock")
_OPENCL_TRANSPOSE_CLOCKWISE_TRANSLATION = translate_filter_chain("transpose_opencl=dir=clock")
_VAAPI_TRANSPOSE_CLOCKWISE_TRANSLATION = translate_filter_chain("transpose_vaapi=dir=clock")
_VULKAN_TRANSPOSE_CLOCKWISE_TRANSLATION = translate_filter_chain("transpose_vulkan=dir=clock")
_NATIVE_HORIZONTAL_FLIP_TRANSLATION = translate_filter_chain("hflip")
_VULKAN_HORIZONTAL_FLIP_TRANSLATION = translate_filter_chain("hflip_vulkan")
_NATIVE_VERTICAL_FLIP_TRANSLATION = translate_filter_chain("vflip")
_VULKAN_VERTICAL_FLIP_TRANSLATION = translate_filter_chain("vflip_vulkan")
_VULKAN_BOTH_FLIP_TRANSLATION = translate_filter_chain("flip_vulkan")
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
_MASTER_COLOR_WHEELS_STACK = (
    _bright_contrast(bright=0.0, contrast=2.0),
    _color_balance(
        lift=(0.995, 0.995, 1.000),
        gamma=(1.010, 1.010, 1.010),
        gain=(1.020, 1.020, 1.020),
        color_multiply=1.0,
    ),
    _asc_cdl(offset=(1.000, 1.000, 1.000), power=(0.995, 0.995, 0.995), slope=(1.015, 1.015, 1.015)),
    _white_balance((1.0, 1.0, 1.0)),
    _curve_points({0: [(0.0, 0.0), (0.25, 0.235), (0.50, 0.50), (0.75, 0.775), (1.0, 1.0)]}),
    _tonemap(tonemap_type="RD_PHOTORECEPTOR", intensity=0.03, contrast=0.03, gamma=1.0),
    ("HUE_CORRECT", {"__hue_correct__": {"saturation": 0.515, "value": 0.50}}),
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


_FFMPEG_SOURCE_LABELS = {
    "allrgb": "All RGB Source",
    "allyuv": "All YUV Source",
    "cellauto": "Cellular Automaton Source",
    "color": "Solid Color Source",
    "color_vulkan": "Vulkan Color Source",
    "colorchart": "Color Checker Source",
    "colorspectrum": "Color Spectrum Source",
    "frei0r_src": "Frei0r Source",
    "gradients": "Gradient Source",
    "haldclutsrc": "Hald CLUT Source",
    "life": "Life Source",
    "mandelbrot": "Mandelbrot Source",
    "mptestsrc": "MP Test Source",
    "nullsrc": "Null Source",
    "openclsrc": "OpenCL Source",
    "pal75bars": "PAL 75 Bars Source",
    "pal100bars": "PAL 100 Bars Source",
    "perlin": "Perlin Source",
    "random": "Random Source",
    "rgbtestsrc": "RGB Test Source",
    "sierpinski": "Sierpinski Source",
    "smptebars": "SMPTE Bars Source",
    "smptehdbars": "SMPTE HD Bars Source",
    "testsrc": "Test Source",
    "testsrc2": "Test Source 2",
    "yuvtestsrc": "YUV Test Source",
    "zoneplate": "Zone Plate Source",
}


def _ffmpeg_source_chain(filter_name: str) -> str:
    if filter_name in {"color", "color_vulkan"}:
        return f"{filter_name}=c=gray:s=640x360"
    if filter_name == "nullsrc":
        return f"{filter_name}=s=640x360"
    return f"{filter_name}=s=640x360"


def _ffmpeg_source_tool(filter_name: str) -> VideoTool:
    translation = translate_filter_chain(_ffmpeg_source_chain(filter_name))
    return VideoTool(
        id=f"native_ffmpeg_source_{filter_name}",
        label=_FFMPEG_SOURCE_LABELS.get(filter_name, filter_name.replace("_", " ").title()),
        category="Native Source & Output",
        engine=ENGINE_COMPOSITOR,
        description=(
            f"Translated FFmpeg {filter_name} source/generator intent as editable Blender "
            "Blank Image and Text source overlay graphlets with generator metadata."
        ),
        compositor_stack=translation.compositor_nodes,
    )


_FFMPEG_SOURCE_GENERATOR_TOOLS = tuple(_ffmpeg_source_tool(filter_name) for filter_name in NATIVE_FFMPEG_SOURCE_FILTERS)


_FFMPEG_EDITING_LABELS = {
    "ass": "ASS Subtitle Overlay",
    "drawbox": "Draw Box Overlay",
    "drawgrid": "Draw Grid Overlay",
    "drawtext": "Draw Text Overlay",
    "fade": "Fade In/Out",
    "hstack": "Horizontal Stack",
    "hstack_qsv": "QSV Horizontal Stack",
    "hstack_vaapi": "VAAPI Horizontal Stack",
    "noise": "Noise Grain Preview",
    "overlay": "Overlay Composite",
    "overlay_cuda": "CUDA Overlay Composite",
    "overlay_opencl": "OpenCL Overlay Composite",
    "overlay_qsv": "QSV Overlay Composite",
    "overlay_vaapi": "VAAPI Overlay Composite",
    "overlay_vulkan": "Vulkan Overlay Composite",
    "pad": "Pad Canvas",
    "pad_cuda": "CUDA Pad Canvas",
    "pad_opencl": "OpenCL Pad Canvas",
    "pad_vaapi": "VAAPI Pad Canvas",
    "perspective": "Perspective Corner Pin",
    "pixelize": "Pixelize",
    "scroll": "Scroll Offset",
    "shear": "Shear Transform",
    "subtitles": "Subtitle Overlay",
    "tile": "Tile Layout",
    "vignette": "Vignette",
    "vstack": "Vertical Stack",
    "vstack_qsv": "QSV Vertical Stack",
    "vstack_vaapi": "VAAPI Vertical Stack",
    "xstack": "Grid Stack",
    "xstack_qsv": "QSV Grid Stack",
    "xstack_vaapi": "VAAPI Grid Stack",
    "zoompan": "Zoom/Pan",
}


def _ffmpeg_editing_chain(filter_name: str) -> str:
    if filter_name == "fade":
        return "fade=t=out:st=0:d=1:alpha=1"
    if filter_name == "vignette":
        return "vignette=angle=0.45"
    if filter_name == "noise":
        return "noise=alls=18:allf=t+u"
    if filter_name == "pixelize":
        return "pixelize=block_size=12"
    if filter_name.startswith("overlay"):
        return f"{filter_name}=x=48:y=32:alpha=0.45"
    if filter_name.startswith("pad"):
        return f"{filter_name}=w=iw*1.12:h=ih*1.12:x=iw*0.06:y=ih*0.06:color=black"
    if filter_name.startswith("hstack"):
        return f"{filter_name}=inputs=2"
    if filter_name.startswith("vstack"):
        return f"{filter_name}=inputs=2"
    if filter_name.startswith("xstack"):
        return f"{filter_name}=inputs=4:layout=2x2"
    if filter_name == "tile":
        return "tile=layout=2x2:margin=8:padding=4"
    if filter_name == "perspective":
        return "perspective=x0=0:y0=0:x1=W:y1=20:x2=20:y2=H:x3=W-20:y3=H"
    if filter_name == "shear":
        return "shear=shx=0.08:shy=0.02"
    if filter_name == "scroll":
        return "scroll=horizontal=0.08:vertical=0.02"
    if filter_name == "zoompan":
        return "zoompan=z=1.12:x=12:y=8:d=25"
    if filter_name == "drawbox":
        return "drawbox=x=32:y=32:w=iw-64:h=ih-64:color=yellow:t=4"
    if filter_name == "drawgrid":
        return "drawgrid=width=64:height=64:thickness=2:color=cyan"
    if filter_name == "drawtext":
        return "drawtext=text='VIDEO TOOLKIT':fontsize=42:fontcolor=white:x=32:y=32"
    if filter_name == "subtitles":
        return "subtitles=filename=subtitle-preview.srt"
    if filter_name == "ass":
        return "ass=filename=subtitle-preview.ass"
    return filter_name


def _ffmpeg_editing_tool(filter_name: str) -> VideoTool:
    translation = translate_filter_chain(_ffmpeg_editing_chain(filter_name))
    return VideoTool(
        id=f"native_ffmpeg_edit_{filter_name}",
        label=_FFMPEG_EDITING_LABELS.get(filter_name, filter_name.replace("_", " ").title()),
        category="Native Visual FX Nodes",
        engine=ENGINE_COMPOSITOR,
        description=(
            f"Translated FFmpeg {filter_name} edit/layout/finishing intent as native Blender "
            "compositor graphlets with editable controls and preserved fallback metadata."
        ),
        compositor_stack=translation.compositor_nodes,
    )


_FFMPEG_EDITING_TOOLS = tuple(_ffmpeg_editing_tool(filter_name) for filter_name in NATIVE_FFMPEG_EDITING_FILTERS)


_FFMPEG_TIMELINE_LABELS = {
    "bench": "Benchmark Metadata",
    "copy": "Copy Passthrough",
    "cue": "Cue Sync Metadata",
    "framestep": "Frame Step",
    "freezeframes": "Freeze Frames",
    "fsync": "Frame Sync Metadata",
    "latency": "Latency Monitor",
    "loop": "Loop Preview",
    "metadata": "Metadata Editor",
    "null": "Null Passthrough",
    "perms": "Frame Permissions",
    "realtime": "Realtime Throttle",
    "reverse": "Reverse Preview",
    "segment": "Segment Marker",
    "select": "Frame Select",
    "sendcmd": "Command Metadata",
    "setdar": "Display Aspect",
    "setpts": "Presentation Time",
    "setsar": "Sample Aspect",
    "settb": "Timebase Metadata",
    "showinfo": "Show Info Monitor",
    "shuffleframes": "Shuffle Frames",
    "sidedata": "Side Data Metadata",
    "split": "Split Stream",
    "tpad": "Temporal Pad",
    "trim": "Trim Range",
}


def _ffmpeg_timeline_chain(filter_name: str) -> str:
    defaults = {
        "bench": "bench=start",
        "copy": "copy",
        "cue": "cue=cue=0:preroll=0:buffer=0",
        "framestep": "framestep=step=2",
        "freezeframes": "freezeframes=first=10:last=30:replace=10",
        "fsync": "fsync=file=sync.txt",
        "latency": "latency",
        "loop": "loop=loop=2:size=50:start=0",
        "metadata": "metadata=mode=add:key=video_toolkit:value=preview",
        "null": "null",
        "perms": "perms=mode=random",
        "realtime": "realtime=limit=2",
        "reverse": "reverse",
        "segment": "segment=timestamps=1|2|3",
        "select": "select=expr=n",
        "sendcmd": "sendcmd=commands='0.0 drawtext reinit text=Video Toolkit'",
        "setdar": "setdar=ratio=16/9",
        "setpts": "setpts=PTS-STARTPTS",
        "setsar": "setsar=ratio=1/1",
        "settb": "settb=expr=1/30",
        "showinfo": "showinfo",
        "shuffleframes": "shuffleframes=0 2 1",
        "sidedata": "sidedata=mode=select:type=MOTION_VECTORS",
        "split": "split=outputs=2",
        "tpad": "tpad=start_duration=1:stop_duration=1:color=black",
        "trim": "trim=start_frame=10:end_frame=120",
    }
    return defaults.get(filter_name, filter_name)


def _ffmpeg_timeline_tool(filter_name: str) -> VideoTool:
    translation = translate_filter_chain(_ffmpeg_timeline_chain(filter_name))
    return VideoTool(
        id=f"native_ffmpeg_timeline_{filter_name}",
        label=_FFMPEG_TIMELINE_LABELS.get(filter_name, filter_name.replace("_", " ").title()),
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description=(
            f"Translated FFmpeg {filter_name} timeline/metadata intent as native Blender "
            "Time, Sequencer Strip Info, scope, aspect, or visible metadata preview graphlets."
        ),
        compositor_stack=translation.compositor_nodes,
    )


_FFMPEG_TIMELINE_TOOLS = tuple(_ffmpeg_timeline_tool(filter_name) for filter_name in NATIVE_FFMPEG_TIMELINE_FILTERS)


_FFMPEG_ADVANCED_LABELS = {
    "buffer": "Buffer Endpoint",
    "buffersink": "Buffer Sink Endpoint",
    "codecview": "Codec Vector View",
    "convolve": "Two-Stream Convolve",
    "cover_rect": "Cover Rectangle Repair",
    "deconvolve": "Two-Stream Deconvolve",
    "deflate": "Deflate Matte",
    "dejudder": "Dejudder Preview",
    "delogo": "Delogo Repair",
    "displace": "Displace Map Preview",
    "doubleweave": "Double Weave Preview",
    "drawbox_vaapi": "VAAPI Draw Box",
    "epx": "EPX Pixel Upscale",
    "find_rect": "Find Rectangle Repair",
    "format": "Pixel Format Metadata",
    "framepack": "Frame Pack Preview",
    "fspp": "FSPP Cleanup",
    "guided": "Guided Filter Cleanup",
    "hqx": "HQX Pixel Upscale",
    "hwdownload": "Hardware Download Metadata",
    "hwmap": "Hardware Map Metadata",
    "hwupload": "Hardware Upload Metadata",
    "hwupload_cuda": "CUDA Upload Metadata",
    "hysteresis": "Hysteresis Matte",
    "inflate": "Inflate Matte",
    "interlace": "Interlace Preview",
    "interlace_vulkan": "Vulkan Interlace Preview",
    "kerndeint": "Kernel Deinterlace Preview",
    "lagfun": "Lagfun Persistence",
    "libplacebo": "Libplacebo Postprocess",
    "limitdiff": "Limit Difference Matte",
    "maskedclamp": "Masked Clamp",
    "maskedmax": "Masked Maximum",
    "maskedmin": "Masked Minimum",
    "maskfun": "Mask Function",
    "mestimate": "Motion Estimation Monitor",
    "mix": "Multi-Input Mix",
    "morpho": "Morphology Matte",
    "multiply": "Multiply Composite",
    "noformat": "Noformat Metadata",
    "nullsink": "Null Sink Endpoint",
    "phase": "Field Phase Preview",
    "photosensitivity": "Photosensitivity Guard",
    "pixdesctest": "Pixel Descriptor Test",
    "pp7": "PP7 Cleanup",
    "pullup": "Pullup Preview",
    "qp": "QP Debug Monitor",
    "readeia608": "EIA-608 Reader",
    "readvitc": "VITC Reader",
    "remap": "Remap Preview",
    "remap_opencl": "OpenCL Remap Preview",
    "removegrain": "Remove Grain",
    "removelogo": "Remove Logo Repair",
    "scale2ref": "Scale to Reference",
    "scharr": "Scharr Edge Preview",
    "shufflepixels": "Shuffle Pixels",
    "signature": "Video Signature Monitor",
    "siti": "SI/TI Monitor",
    "spp": "SPP Cleanup",
    "ssim360": "SSIM 360 Monitor",
    "stereo3d": "Stereo 3D Preview",
    "super2xsai": "Super2xSAI Upscale",
    "swaprect": "Swap Rectangle Preview",
    "swapuv": "Swap UV",
    "tiltandshift": "Tilt-Shift Preview",
    "tinterlace": "Temporal Interlace Preview",
    "uspp": "USPP Cleanup",
    "vpp_qsv": "QSV Video Postprocess",
    "weave": "Weave Preview",
    "zmq": "ZMQ Command Metadata",
}


def _ffmpeg_advanced_chain(filter_name: str) -> str:
    defaults = {
        "cover_rect": "cover_rect=x=48:y=32:w=160:h=90",
        "delogo": "delogo=x=48:y=32:w=160:h=90",
        "find_rect": "find_rect=x=48:y=32:w=160:h=90",
        "removelogo": "removelogo=x=48:y=32:w=160:h=90",
        "convolve": "convolve=0m='0 -1 0 -1 5 -1 0 -1 0'",
        "deconvolve": "deconvolve=0m='0 -1 0 -1 5 -1 0 -1 0'",
        "displace": "displace=edge=clip",
        "remap": "remap",
        "remap_opencl": "remap_opencl",
        "deflate": "deflate",
        "inflate": "inflate",
        "hysteresis": "hysteresis",
        "morpho": "morpho",
        "maskfun": "maskfun",
        "maskedclamp": "maskedclamp",
        "maskedmax": "maskedmax",
        "maskedmin": "maskedmin",
        "limitdiff": "limitdiff",
        "mix": "mix=weights=0.45",
        "multiply": "multiply",
        "removegrain": "removegrain=m0=12",
        "pp7": "pp7=qp=2",
        "fspp": "fspp=quality=4",
        "spp": "spp=quality=4",
        "uspp": "uspp=quality=4",
        "guided": "guided=radius=4:eps=0.01",
        "lagfun": "lagfun=decay=0.92",
        "photosensitivity": "photosensitivity=frames=30:threshold=1",
        "hqx": "hqx=n=2",
        "epx": "epx=n=2",
        "super2xsai": "super2xsai",
        "scale2ref": "scale2ref=w=2:h=2",
        "scharr": "scharr=scale=1.0",
        "codecview": "codecview=mv=pf+bf+bb",
        "mestimate": "mestimate=method=esa",
        "dejudder": "dejudder=cycle=4",
        "doubleweave": "doubleweave",
        "interlace": "interlace",
        "interlace_vulkan": "interlace_vulkan",
        "kerndeint": "kerndeint=thresh=10",
        "phase": "phase=mode=A",
        "pullup": "pullup",
        "tinterlace": "tinterlace=mode=merge",
        "weave": "weave",
        "framepack": "framepack=format=sbs",
        "stereo3d": "stereo3d=sbsl:arcd",
        "tiltandshift": "tiltandshift=tilt=0.08",
        "swaprect": "swaprect=w=120:h=80:x1=16:y1=16:x2=120:y2=60",
        "shufflepixels": "shufflepixels=mode=horizontal",
        "swapuv": "swapuv",
        "drawbox_vaapi": "drawbox_vaapi=x=32:y=32:w=320:h=180:color=yellow",
        "libplacebo": "libplacebo=tonemapping=bt.2390",
        "vpp_qsv": "vpp_qsv=procamp=1",
        "format": "format=pix_fmts=yuv420p",
        "noformat": "noformat=pix_fmts=yuv420p",
        "buffer": "buffer",
        "buffersink": "buffersink",
        "nullsink": "nullsink",
        "pixdesctest": "pixdesctest",
        "qp": "qp",
        "readeia608": "readeia608",
        "readvitc": "readvitc",
        "signature": "signature",
        "siti": "siti",
        "ssim360": "ssim360",
        "hwdownload": "hwdownload",
        "hwmap": "hwmap",
        "hwupload": "hwupload",
        "hwupload_cuda": "hwupload_cuda",
        "zmq": "zmq",
    }
    return defaults.get(filter_name, filter_name)


def _ffmpeg_advanced_category(filter_name: str) -> str:
    if filter_name in {"deflate", "inflate", "hysteresis", "morpho", "maskfun", "maskedclamp", "maskedmax", "maskedmin", "limitdiff", "swapuv"}:
        return "Native Matte & Channel"
    if filter_name in {"convolve", "deconvolve", "scharr"}:
        return "Native Filter & Blur"
    if filter_name in {"removegrain", "pp7", "fspp", "spp", "uspp", "guided", "lagfun", "photosensitivity"}:
        return "Native Denoise & Cleanup"
    if filter_name in {"displace", "remap", "remap_opencl", "scale2ref", "tiltandshift"}:
        return "Native Geometry & Lens"
    if filter_name in {"hqx", "epx", "super2xsai", "dejudder", "doubleweave", "interlace", "interlace_vulkan", "kerndeint", "phase", "pullup", "tinterlace", "weave", "framepack", "stereo3d"}:
        return "Resolution & Motion"
    if filter_name in {"delogo", "removelogo", "cover_rect", "find_rect", "drawbox_vaapi", "swaprect", "shufflepixels", "mix", "multiply"}:
        return "Native Visual FX Nodes"
    return "Native Analysis & Utility"


def _ffmpeg_advanced_tool(filter_name: str) -> VideoTool:
    translation = translate_filter_chain(_ffmpeg_advanced_chain(filter_name))
    return VideoTool(
        id=f"native_ffmpeg_advanced_{filter_name}",
        label=_FFMPEG_ADVANCED_LABELS.get(filter_name, filter_name.replace("_", " ").title()),
        category=_ffmpeg_advanced_category(filter_name),
        engine=ENGINE_COMPOSITOR,
        description=(
            f"Translated FFmpeg {filter_name} advanced intent as Blender-native repair, matte, "
            "cleanup, transform, diagnostic, or metadata graphlets for the selected strip."
        ),
        compositor_stack=translation.compositor_nodes,
    )


_FFMPEG_ADVANCED_TOOLS = tuple(_ffmpeg_advanced_tool(filter_name) for filter_name in NATIVE_FFMPEG_ADVANCED_FILTERS)


def _ffmpeg_advanced_tools_for_category(category: str) -> tuple[VideoTool, ...]:
    return tuple(tool for tool in _FFMPEG_ADVANCED_TOOLS if tool.category == category)


_FFMPEG_INTEROP_LABELS = {
    "=": "Filter Expression Marker",
    "a3dscope": "Audio 3D Scope",
    "abitscope": "Audio Bit Scope",
    "addroi": "Region Of Interest",
    "adrawgraph": "Audio Draw Graph",
    "agraphmonitor": "Audio Graph Monitor",
    "ahistogram": "Audio Histogram",
    "avectorscope": "Audio Vectorscope",
    "avsynctest": "Audio/Video Sync Test",
    "ccrepack": "Closed Caption Repack",
    "drawgraph": "Draw Graph Monitor",
    "feedback": "Feedback Stream Preview",
    "frei0r": "Frei0r Plugin Preview",
    "graphmonitor": "Graph Monitor",
    "il": "Interleave Fields",
    "interleave": "Interleave Streams",
    "program_opencl": "OpenCL Program Preview",
    "showcqt": "Constant-Q Spectrum",
    "showcwt": "Wavelet Spectrum",
    "showfreqs": "Frequency Spectrum",
    "showspatial": "Spatial Audio Monitor",
    "showspectrum": "Audio Spectrum",
    "showspectrumpic": "Audio Spectrum Picture",
    "showvolume": "Volume Meter",
    "showwaves": "Waveform Monitor",
    "showwavespic": "Waveform Picture",
    "spectrumsynth": "Spectrum Synth",
    "xfade": "Crossfade Transition",
    "xfade_opencl": "OpenCL Crossfade Transition",
    "xfade_vulkan": "Vulkan Crossfade Transition",
}


def _ffmpeg_interop_tool_id(filter_name: str) -> str:
    safe_name = "equals" if filter_name == "=" else filter_name
    return f"native_ffmpeg_interop_{safe_name}"


def _ffmpeg_interop_chain(filter_name: str) -> str:
    defaults = {
        "=": "=",
        "addroi": "addroi=x=48:y=32:w=192:h=108",
        "adrawgraph": "adrawgraph=m1=lavfi.astats.Overall.RMS_level",
        "agraphmonitor": "agraphmonitor",
        "drawgraph": "drawgraph=m1=lavfi.signalstats.YAVG:min=0:max=255",
        "graphmonitor": "graphmonitor",
        "feedback": "feedback=x=32:y=24:w=160:h=90",
        "frei0r": "frei0r=filter_name=contrast0r",
        "program_opencl": "program_opencl=source=kernel.cl",
        "ccrepack": "ccrepack",
        "il": "il=l=d:c=d",
        "interleave": "interleave=nb_inputs=2",
        "xfade": "xfade=transition=fade:duration=1:offset=0",
        "xfade_opencl": "xfade_opencl=transition=fade:duration=1:offset=0",
        "xfade_vulkan": "xfade_vulkan=transition=fade:duration=1:offset=0",
        "a3dscope": "a3dscope=s=640x360",
        "abitscope": "abitscope=s=640x360",
        "ahistogram": "ahistogram=s=640x360",
        "avectorscope": "avectorscope=s=640x360",
        "avsynctest": "avsynctest",
        "showcqt": "showcqt=s=640x360",
        "showcwt": "showcwt=s=640x360",
        "showfreqs": "showfreqs=s=640x360",
        "showspatial": "showspatial=s=640x360",
        "showspectrum": "showspectrum=s=640x360",
        "showspectrumpic": "showspectrumpic=s=640x360",
        "showvolume": "showvolume",
        "showwaves": "showwaves=s=640x360",
        "showwavespic": "showwavespic=s=640x360",
        "spectrumsynth": "spectrumsynth",
    }
    return defaults.get(filter_name, filter_name)


def _ffmpeg_interop_category(filter_name: str) -> str:
    if filter_name in {"ccrepack", "il"}:
        return "Native Matte & Channel"
    if filter_name in {"addroi", "feedback", "frei0r", "interleave", "program_opencl"}:
        return "Native Visual FX Nodes"
    if filter_name in {"xfade", "xfade_opencl", "xfade_vulkan"}:
        return "Resolution & Motion"
    return "Native Analysis & Utility"


def _ffmpeg_interop_tool(filter_name: str) -> VideoTool:
    translation = translate_filter_chain(_ffmpeg_interop_chain(filter_name))
    return VideoTool(
        id=_ffmpeg_interop_tool_id(filter_name),
        label=_FFMPEG_INTEROP_LABELS.get(filter_name, filter_name.replace("_", " ").title()),
        category=_ffmpeg_interop_category(filter_name),
        engine=ENGINE_COMPOSITOR,
        description=(
            f"Translated FFmpeg {filter_name} interop/monitor/transition intent as Blender-native "
            "scope, overlay, blend, field, or metadata graphlets for the selected strip."
        ),
        compositor_stack=translation.compositor_nodes,
    )


_FFMPEG_INTEROP_TOOLS = tuple(_ffmpeg_interop_tool(filter_name) for filter_name in NATIVE_FFMPEG_INTEROP_FILTERS)


def _ffmpeg_interop_tools_for_category(category: str) -> tuple[VideoTool, ...]:
    return tuple(tool for tool in _FFMPEG_INTEROP_TOOLS if tool.category == category)


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
        id="procamp_vaapi_color_controls",
        label="VAAPI ProcAmp Controls",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg procamp_vaapi brightness, contrast, saturation, and hue into live Blender color controls.",
        blender_stack=_PROCAMP_VAAPI_TRANSLATION.stack,
        compositor_stack=_PROCAMP_VAAPI_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="opencl_tone_map",
        label="OpenCL Tone Map",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg tonemap_opencl HDR/SDR intent into Blender Tone Map, Hue Correct, and color-management metadata.",
        blender_stack=_TONEMAP_OPENCL_TRANSLATION.stack,
        compositor_stack=_TONEMAP_OPENCL_TRANSLATION.compositor_nodes,
        color_management=_TONEMAP_OPENCL_TRANSLATION.color_management,
    ),
    VideoTool(
        id="vaapi_tone_map",
        label="VAAPI Tone Map",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg tonemap_vaapi output color metadata into Blender Tone Map and editable native color-management intent.",
        blender_stack=_TONEMAP_VAAPI_TRANSLATION.stack,
        compositor_stack=_TONEMAP_VAAPI_TRANSLATION.compositor_nodes,
        color_management=_TONEMAP_VAAPI_TRANSLATION.color_management,
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
        id="master_color_wheels",
        label="Master Color Wheels",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Editable primary correction board exposing Blender Brightness/Contrast, Lift/Gamma/Gain, ASC CDL Offset/Power/Slope, White Balance, RGB Curves, Tone Map, and Hue Correct controls.",
        blender_stack=_MASTER_COLOR_WHEELS_STACK,
    ),
    VideoTool(
        id="rgb_gamma_board",
        label="RGB Gamma Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg eq per-channel gamma, gamma-weight, contrast, and saturation as editable Blender live modifiers plus compositor nodes.",
        blender_stack=_RGB_GAMMA_BOARD_TRANSLATION.stack,
        compositor_stack=_RGB_GAMMA_BOARD_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="channel_mixer_balance",
        label="Channel Mixer Balance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colorchannelmixer channel math as Blender Lift/Gamma/Gain and White Balance controls.",
        blender_stack=_CHANNEL_MIXER_BALANCE_TRANSLATION.stack,
        compositor_stack=_CHANNEL_MIXER_BALANCE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="opponent_color_contrast",
        label="Opponent Color Contrast",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg red/cyan, green/magenta, and blue/yellow colorcontrast intent as native Blender color-balance math.",
        blender_stack=_OPPONENT_COLOR_CONTRAST_TRANSLATION.stack,
        compositor_stack=_OPPONENT_COLOR_CONTRAST_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="low_high_colorcorrect",
        label="Low/High Color Correct",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colorcorrect low/high red-blue balance and saturation as Blender tonal color controls.",
        blender_stack=_LOW_HIGH_COLORCORRECT_TRANSLATION.stack,
        compositor_stack=_LOW_HIGH_COLORCORRECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="independent_rgb_normalize",
        label="Independent RGB Normalize",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg normalize with independent RGB black/white points as Blender RGB Curves and Tone Map.",
        blender_stack=_INDEPENDENT_RGB_NORMALIZE_TRANSLATION.stack,
        compositor_stack=_INDEPENDENT_RGB_NORMALIZE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="hue_sat_intensity_board",
        label="Hue/Sat/Value Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg huesaturation hue, saturation, value, and strength controls as Blender Hue Correct and compositor Hue/Saturation nodes.",
        blender_stack=_HUE_SAT_INTENSITY_TRANSLATION.stack,
        compositor_stack=_HUE_SAT_INTENSITY_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="highlight_desat_tonemap",
        label="Highlight Desat Tone Map",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg tonemap highlight compression and desaturation as Blender Tone Map and Hue Correct controls.",
        blender_stack=_HIGHLIGHT_DESAT_TONEMAP_TRANSLATION.stack,
        compositor_stack=_HIGHLIGHT_DESAT_TONEMAP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="broadcast_gamma_guard",
        label="Broadcast Gamma Guard",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg limiter plus eq gamma guard as Blender RGB Curves, Color Balance, Hue Correct, and Tone Map.",
        blender_stack=_BROADCAST_GAMMA_GUARD_TRANSLATION.stack,
        compositor_stack=_BROADCAST_GAMMA_GUARD_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="gray_world_neutralizer",
        label="Gray World Neutralizer",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg grayworld neutral balance with a light native eq finish for editable color-cast cleanup.",
        blender_stack=_GRAY_WORLD_NEUTRALIZER_TRANSLATION.stack,
        compositor_stack=_GRAY_WORLD_NEUTRALIZER_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="rgb_lut_trim",
        label="RGB LUT Trim",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg lutrgb channel trim as editable Blender RGB Curves and matching compositor curves.",
        blender_stack=_RGB_LUT_TRIM_TRANSLATION.stack,
        compositor_stack=_RGB_LUT_TRIM_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="selective_neutral_balance",
        label="Selective Neutral Balance",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg selectivecolor hue-zone and neutral-zone balance as Blender Hue Correct and Lift/Gamma/Gain controls.",
        blender_stack=_SELECTIVE_NEUTRAL_BALANCE_TRANSLATION.stack,
        compositor_stack=_SELECTIVE_NEUTRAL_BALANCE_TRANSLATION.compositor_nodes,
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
        id="lut1d_film_curve",
        label="1D LUT Film Curve",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg lut1d look intent as editable Blender RGB Curves and Lift/Gamma/Gain controls.",
        blender_stack=_LUT1D_FILM_LOOK_TRANSLATION.stack,
        compositor_stack=_LUT1D_FILM_LOOK_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="lut3d_scene_look",
        label="3D LUT Scene Look",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg lut3d look intent as Blender curves, color balance, and tone mapping.",
        blender_stack=_LUT3D_SCENE_LOOK_TRANSLATION.stack,
        compositor_stack=_LUT3D_SCENE_LOOK_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="haldclut_display_match",
        label="Hald CLUT Display Match",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg haldclut display-match intent as live Blender curves, color balance, and tone mapping.",
        blender_stack=_HALDCLUT_DISPLAY_MATCH_TRANSLATION.stack,
        compositor_stack=_HALDCLUT_DISPLAY_MATCH_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="colormap_palette_match",
        label="Colormap Palette Match",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg colormap palette-match intent as Blender Hue Correct, RGB Curves, and Color Balance controls.",
        blender_stack=_COLORMAP_PALETTE_MATCH_TRANSLATION.stack,
        compositor_stack=_COLORMAP_PALETTE_MATCH_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="palette_generate_board",
        label="Palette Generate Board",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg palettegen intent as live Blender hue-zone compression, RGB curves, and palette-separation controls.",
        blender_stack=_PALETTE_GENERATE_TRANSLATION.stack,
        compositor_stack=_PALETTE_GENERATE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="palette_use_match",
        label="Palette Use Match",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg paletteuse intent as editable Blender palette matching, dithering metadata, curves, and color balance.",
        blender_stack=_PALETTE_USE_TRANSLATION.stack,
        compositor_stack=_PALETTE_USE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="temporal_change_amplifier",
        label="Temporal Change Amplifier",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg amplify intent as live Blender contrast, gamma, and chroma emphasis with temporal threshold metadata.",
        blender_stack=_AMPLIFY_COLOR_TRANSLATION.stack,
        compositor_stack=_AMPLIFY_COLOR_TRANSLATION.compositor_nodes,
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
        id="geq_rgb_math",
        label="GEQ RGB Math",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg geq simple per-channel expressions as editable native Blender RGB Curves.",
        blender_stack=_GEQ_RGB_MATH_TRANSLATION.stack,
        compositor_stack=_GEQ_RGB_MATH_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="midway_equalize",
        label="Midway Equalize",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg midequalizer intent as a single-strip Blender curves and tone-map equalization stack.",
        blender_stack=_MIDWAY_EQUALIZE_TRANSLATION.stack,
        compositor_stack=_MIDWAY_EQUALIZE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="temporal_midway_equalize",
        label="Temporal Midway Equalize",
        category="Live Blender Color",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Translated FFmpeg tmidequalizer temporal equalization intent as editable Blender curves and tone mapping.",
        blender_stack=_TEMPORAL_MIDWAY_EQUALIZE_TRANSLATION.stack,
        compositor_stack=_TEMPORAL_MIDWAY_EQUALIZE_TRANSLATION.compositor_nodes,
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
        description="Creates Blender compositor color primitives as one graph: Exposure, Brightness/Contrast, Color Balance, Color Correction Gamma, RGB Curves, Hue/Saturation, Hue Correct, Tone Map, Invert, Posterize, and Premul Key.",
        compositor_stack=(
            ("EXPOSURE", {"source": "blender_compositor", "exposure": 0.12, "black": 0.0}),
            ("BRIGHT_CONTRAST", {"source": "blender_compositor", "bright": 0.01, "contrast": 4.0}),
            ("COLOR_BALANCE", {"source": "blender_compositor", "color_balance.gamma": (1.02, 1.02, 1.02), "color_balance.gain": (1.03, 1.03, 1.03)}),
            ("COLOR_CORRECTION", {"source": "blender_compositor", "saturation": 1.04, "gamma": 1.04, "shadow_offset": 0.01, "highlight_gain": 1.02}),
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
        id="native_compositor_bright_contrast",
        label="Compositor Brightness/Contrast",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Brightness/Contrast node as a one-click editable color primitive.",
        compositor_stack=(("BRIGHT_CONTRAST", {"source": "blender_compositor", "bright": 0.01, "contrast": 4.0}),),
    ),
    VideoTool(
        id="native_compositor_color_balance",
        label="Compositor Color Balance",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Color Balance node for lift/gamma/gain and offset/power/slope-style work.",
        compositor_stack=(("COLOR_BALANCE", {"source": "blender_compositor", "factor": 1.0, "color_balance.gamma": (1.02, 1.02, 1.02), "color_balance.gain": (1.03, 1.03, 1.03)}),),
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
        id="native_compositor_rgb_curves",
        label="Compositor RGB Curves",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor RGB Curves node with an editable contrast curve.",
        compositor_stack=(("CURVE_RGB", {"source": "blender_compositor", "__curve_points__": {0: [(0.0, 0.0), (0.22, 0.18), (0.50, 0.50), (0.80, 0.86), (1.0, 1.0)]}}),),
    ),
    VideoTool(
        id="native_compositor_gamma",
        label="Compositor Gamma Control",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native Color Correction node focused on its gamma control.",
        compositor_stack=(("COLOR_CORRECTION", {"source": "blender_compositor_gamma", "saturation": 1.0, "gamma": 1.06, "shadow_offset": 0.0, "highlight_gain": 1.0}),),
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
        id="native_compositor_hue_correct",
        label="Compositor Hue Correct",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Hue Correct node for editable hue-zone correction curves.",
        compositor_stack=(("HUE_CORRECT", {"source": "blender_compositor", "__hue_correct__": {"saturation": 0.53, "value": 0.50}}),),
    ),
    VideoTool(
        id="native_compositor_tone_map",
        label="Compositor Tone Map",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Tone Map node for editable highlight compression and gamma review.",
        compositor_stack=(("TONEMAP", {"source": "blender_compositor", "tonemap_type": "RD_PHOTORECEPTOR", "intensity": 0.04, "contrast": 0.04, "gamma": 1.0}),),
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
        id="native_compositor_normalize",
        label="Compositor Normalize",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Normalize node for live value-range normalization review.",
        compositor_stack=(_native_node("CompositorNodeNormalize", label="Normalize"),),
    ),
    VideoTool(
        id="native_compositor_rgb_to_bw",
        label="Compositor RGB to BW",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor RGB to BW node for luma review and monochrome analysis.",
        compositor_stack=(_native_node("CompositorNodeRGBToBW", label="RGB to BW"),),
    ),
    VideoTool(
        id="native_compositor_separate_color",
        label="Compositor Separate Color",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Separate Color node as an editable channel-analysis primitive.",
        compositor_stack=(
            _native_node("CompositorNodeSeparateColor", label="Separate Color", properties={"mode": "RGB", "ycc_mode": "ITUBT709"}, passthrough=True),
        ),
    ),
    VideoTool(
        id="native_compositor_combine_color",
        label="Compositor Combine Color",
        category="Native Blender Primitives",
        engine=ENGINE_COMPOSITOR,
        description="Creates Blender's native compositor Combine Color node as an editable channel-combine primitive.",
        compositor_stack=(
            _native_node(
                "CompositorNodeCombineColor",
                label="Combine Color",
                inputs={"Red": 0.50, "Green": 0.50, "Blue": 0.50, "Alpha": 1.0},
                properties={"mode": "RGB", "ycc_mode": "ITUBT709"},
                skip_link_input=True,
                passthrough=True,
            ),
        ),
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
        id="native_colorspace_bt709_full_pipeline",
        label="BT.709 Full-Range Pipeline",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click native Blender pipeline for FFmpeg colorspace=iall=bt709:all=bt709:irange=tv:range=pc metadata.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="BT.709 Input Convert"),
            _native_node("CompositorNodeConvertToDisplay", label="BT.709 Display Review", inputs={"Invert": False}),
        ),
        color_management=_COLORSPACE_BT709_FULL_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_colorspace_bt709_to_bt2020_pipeline",
        label="BT.709 to BT.2020 Pipeline",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender color-management and compositor review graph for FFmpeg BT.709 to BT.2020 colorspace intent.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="BT.709 to BT.2020 Convert"),
            _native_node("CompositorNodeConvertToDisplay", label="BT.2020 Display Review", inputs={"Invert": False}),
        ),
        color_management=_COLORSPACE_BT709_TO_BT2020_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_colorspace_srgb_review_pipeline",
        label="sRGB Review Pipeline",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender review pipeline for FFmpeg colorspace metadata targeting sRGB display review.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="sRGB Review Convert"),
            _native_node("CompositorNodeConvertToDisplay", label="sRGB Display Review", inputs={"Invert": False}),
        ),
        color_management=_COLORSPACE_SRGB_REVIEW_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_colormatrix_601_to_709_pipeline",
        label="Matrix 601 to 709",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender equivalent for FFmpeg colormatrix=src=smpte170m:dst=bt709 intent with YCbCr review nodes.",
        compositor_stack=(
            _color_model_board(
                "YCC",
                label="Matrix 601 to 709 Board",
                ycc_mode="ITUBT601",
                grade_type="COLOR_CORRECTION",
                grade={"saturation": 1.035, "contrast": 1.025, "gamma": 1.0, "gain": 1.012, "offset": 0.0},
            ),
            _native_node("CompositorNodeConvertToDisplay", label="709 Display Review", inputs={"Invert": False}),
        ),
        color_management=_COLORMATRIX_601_TO_709_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_colormatrix_709_to_2020_pipeline",
        label="Matrix 709 to 2020",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender color-matrix metadata pipeline for FFmpeg colormatrix=src=bt709:dst=bt2020 intent.",
        compositor_stack=(
            _color_model_board(
                "YCC",
                label="Matrix 709 to 2020 Board",
                ycc_mode="ITUBT709",
                grade_type="COLOR_CORRECTION",
                grade={"saturation": 1.04, "contrast": 1.03, "gamma": 0.998, "gain": 1.014, "offset": 0.0},
            ),
            _native_node("CompositorNodeConvertToDisplay", label="BT.2020 Display Review", inputs={"Invert": False}),
        ),
        color_management=_COLORMATRIX_709_TO_2020_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_setparams_rec2020_pq_pipeline",
        label="Rec.2020 PQ Metadata",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender color-management metadata pipeline for FFmpeg setparams Rec.2020/PQ/full-range intent.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="Rec.2020 PQ Metadata Convert"),
            _native_node("CompositorNodeConvertToDisplay", label="Rec.2020 PQ Display Review", inputs={"Invert": False}),
        ),
        color_management=_SETPARAMS_REC2020_PQ_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_setrange_full_pipeline",
        label="Full Range Metadata",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender color-management metadata tool for FFmpeg setrange=full intent.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="Full Range Metadata Convert"),
            _native_node("CompositorNodeConvertToDisplay", label="Full Range Display Review", inputs={"Invert": False}),
        ),
        color_management=_SETRANGE_FULL_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_setrange_limited_pipeline",
        label="Limited Range Metadata",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender color-management metadata tool for FFmpeg setrange=limited intent.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="Limited Range Metadata Convert"),
            _native_node("CompositorNodeConvertToDisplay", label="Limited Range Display Review", inputs={"Invert": False}),
        ),
        color_management=_SETRANGE_LIMITED_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_zscale_709_to_2020_hdr_pipeline",
        label="Zscale 709 to 2020 HDR",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender metadata and node-review pipeline for FFmpeg zscale BT.709 limited to BT.2020 full HDR intent.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="Zscale Input Convert"),
            _native_node("CompositorNodeTonemap", label="Zscale HDR Tone Review", inputs={"Type": "RD_PHOTORECEPTOR", "Intensity": 0.10, "Contrast": 0.06, "Gamma": 1.0}),
            _native_node("CompositorNodeConvertToDisplay", label="Zscale Display Review", inputs={"Invert": False}),
        ),
        color_management=_ZSCALE_709_TO_2020_HDR_TRANSLATION.color_management,
    ),
    VideoTool(
        id="native_ffmpeg_color_metadata_pipeline",
        label="FFmpeg Metadata Pipeline",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="One-click Blender sidecar tool covering colorspace, colorspace_cuda, colormatrix, setparams, setrange, and zscale metadata intent.",
        compositor_stack=(
            _native_node("CompositorNodeConvertColorSpace", label="Metadata Input Convert"),
            _color_model_board(
                "YCC",
                label="Metadata Matrix Review",
                ycc_mode="ITUBT709",
                grade_type="COLOR_CORRECTION",
                grade={"saturation": 1.035, "contrast": 1.025, "gamma": 1.0, "gain": 1.012, "offset": 0.0},
            ),
            _native_node("CompositorNodeTonemap", label="Metadata Tone Review", inputs={"Type": "RD_PHOTORECEPTOR", "Intensity": 0.08, "Contrast": 0.05, "Gamma": 1.0}),
            _native_node("CompositorNodeConvertToDisplay", label="Metadata Display Review", inputs={"Invert": False}),
        ),
        color_management=_COLOR_PIPELINE_METADATA_PROFILE,
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
        id="native_rgb_channel_board",
        label="RGB Channel Board",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Splits the selected video through Blender's native RGB Separate/Combine Color nodes, then applies a subtle RGB balance grade.",
        compositor_stack=(
            _color_model_board(
                "RGB",
                label="RGB Channel Board",
                grade_type="COLOR_BALANCE",
                grade={
                    "factor": 1.0,
                    "gamma": (1.035, 1.015, 0.985, 1.0),
                    "gain": (1.045, 1.020, 0.980, 1.0),
                },
            ),
        ),
    ),
    VideoTool(
        id="native_hsv_color_board",
        label="HSV Color Board",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Uses Blender's native HSV Separate/Combine Color mode with Hue/Saturation/Value finishing controls.",
        compositor_stack=(
            _color_model_board(
                "HSV",
                label="HSV Color Board",
                grade={"hue": 0.505, "saturation": 1.14, "value": 1.025, "factor": 1.0},
            ),
        ),
    ),
    VideoTool(
        id="native_hsl_color_board",
        label="HSL Color Board",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Uses Blender's native HSL Separate/Combine Color mode with a restrained saturation and lightness finish.",
        compositor_stack=(
            _color_model_board(
                "HSL",
                label="HSL Color Board",
                grade={"hue": 0.498, "saturation": 1.09, "value": 1.018, "factor": 1.0},
            ),
        ),
    ),
    VideoTool(
        id="native_yuv_video_board",
        label="YUV Video Board",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Uses Blender's native YUV Separate/Combine Color mode with conservative broadcast-style contrast and saturation correction.",
        compositor_stack=(
            _color_model_board(
                "YUV",
                label="YUV Video Board",
                grade_type="COLOR_CORRECTION",
                grade={"saturation": 1.045, "contrast": 1.035, "gamma": 0.995, "gain": 1.015, "offset": 0.0},
            ),
        ),
    ),
    VideoTool(
        id="native_ycc_601_video_board",
        label="YCbCr 601 Board",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Uses Blender's native YCbCr ITU-BT.601 Separate/Combine Color mode for SD/broadcast matrix review and correction.",
        compositor_stack=(
            _color_model_board(
                "YCC",
                label="YCbCr 601 Board",
                ycc_mode="ITUBT601",
                grade_type="COLOR_CORRECTION",
                grade={"saturation": 1.035, "contrast": 1.025, "gamma": 1.0, "gain": 1.012, "offset": 0.0},
            ),
        ),
    ),
    VideoTool(
        id="native_ycc_709_video_board",
        label="YCbCr 709 Board",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Uses Blender's native YCbCr ITU-BT.709 Separate/Combine Color mode for HD video matrix review and correction.",
        compositor_stack=(
            _color_model_board(
                "YCC",
                label="YCbCr 709 Board",
                ycc_mode="ITUBT709",
                grade_type="COLOR_CORRECTION",
                grade={"saturation": 1.04, "contrast": 1.03, "gamma": 0.998, "gain": 1.014, "offset": 0.0},
            ),
        ),
    ),
    VideoTool(
        id="native_ycc_jfif_video_board",
        label="YCbCr JFIF Board",
        category="Native Color & Composite",
        engine=ENGINE_COMPOSITOR,
        description="Uses Blender's native YCbCr JFIF Separate/Combine Color mode for full-range/JPEG-derived video review and correction.",
        compositor_stack=(
            _color_model_board(
                "YCC",
                label="YCbCr JFIF Board",
                ycc_mode="JFIF",
                grade_type="COLOR_CORRECTION",
                grade={"saturation": 1.025, "contrast": 1.02, "gamma": 1.002, "gain": 1.010, "offset": 0.0},
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
        id="native_cuda_chroma_key_matte",
        label="CUDA Chroma Key Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg chromakey_cuda intent as Blender's native Chroma Matte compositor graph without requiring CUDA rendering.",
        compositor_stack=_CUDA_CHROMA_KEY_MATTE_TRANSLATION.compositor_nodes,
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
        id="native_opencl_color_key_matte",
        label="OpenCL Color Key Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg colorkey_opencl intent as Blender's native Color Matte compositor graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_COLOR_KEY_MATTE_TRANSLATION.compositor_nodes,
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
        id="native_despill_color_spill",
        label="Native Despill Color Spill",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg despill intent as Blender's native Color Spill compositor graph for green/blue-screen cleanup.",
        compositor_stack=_DESPILL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_background_key_matte",
        label="Native Background Key Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg backgroundkey intent as a Blender Difference Matte plus Set Alpha graph for static-background transparency cleanup.",
        compositor_stack=_BACKGROUND_KEY_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_threshold_matte",
        label="Native Threshold Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg threshold intent as a native Blender Luma Matte threshold graph.",
        compositor_stack=_THRESHOLD_MATTE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_masked_threshold_matte",
        label="Native Masked Threshold Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg maskedthreshold intent as a native Blender Luma Matte threshold graph for selected-strip matte work.",
        compositor_stack=_MASKED_THRESHOLD_MATTE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_blend_overlay_composite",
        label="Native Blend Overlay Composite",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg blend overlay intent as a native Blender Alpha Over graph with an editable color-processing foreground branch.",
        compositor_stack=_BLEND_OVERLAY_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vulkan_blend_composite",
        label="Vulkan Blend Composite",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg blend_vulkan intent as a native Blender Alpha Over graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_BLEND_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_temporal_blend_ghost",
        label="Native Temporal Blend Ghost",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg tblend intent as a Blender Alpha Over temporal-style composite graph for selected-strip preview work.",
        compositor_stack=_TEMPORAL_BLEND_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_lut2_expression_mix",
        label="Native LUT2 Expression Mix",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg lut2 two-input expression intent as an editable Blender Alpha Over composite graph with expression metadata.",
        compositor_stack=_LUT2_EXPRESSION_MIX_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_tlut2_temporal_expression",
        label="Native Temporal LUT2 Expression",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg tlut2 successive-frame expression intent as an editable Blender Alpha Over composite graph with temporal expression metadata.",
        compositor_stack=_TEMPORAL_LUT2_EXPRESSION_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_masked_merge",
        label="Native Masked Merge",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg maskedmerge intent as a Blender Luma Matte driven Alpha Over composite graph.",
        compositor_stack=_MASKED_MERGE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_mergeplanes_router",
        label="Native Mergeplanes Router",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg mergeplanes channel routing as Blender Separate/Combine Color nodes.",
        compositor_stack=_MERGEPLANES_ROUTER_TRANSLATION.compositor_nodes,
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
        id="native_chromatic_aberration_offset",
        label="Native Chromatic Aberration Offset",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg chromaber_vulkan intent as opposing red/blue Blender Translate channel offsets for chromatic aberration repair or stylized fringing.",
        compositor_stack=_CHROMATIC_ABERRATION_TRANSLATION.compositor_nodes,
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
        id="native_alpha_merge_luma_matte",
        label="Native Alpha Merge Luma Matte",
        category="Native Matte & Channel",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg alphamerge intent as a Blender RGB-to-BW luma matte feeding Set Alpha for editable alpha application.",
        compositor_stack=_ALPHA_MERGE_TRANSLATION.compositor_nodes,
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
        id="native_opencl_unsharp_filter",
        label="OpenCL Unsharp Filter",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg unsharp_opencl intent as Blender's native compositor Filter sharpen graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_UNSHARP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_cas_sharpen",
        label="Native CAS Sharpen",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg cas contrast-adaptive sharpening intent as Blender's native compositor Filter sharpen graph.",
        compositor_stack=_NATIVE_CAS_SHARPEN_TRANSLATION.compositor_nodes,
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
        id="native_opencl_sobel_edges",
        label="OpenCL Sobel Edges",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg sobel_opencl intent as Blender's native compositor Filter graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_SOBEL_TRANSLATION.compositor_nodes,
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
        id="native_opencl_prewitt_edges",
        label="OpenCL Prewitt Edges",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg prewitt_opencl intent as Blender's native compositor Filter graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_PREWITT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_roberts_edges",
        label="Native Roberts Edges",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg roberts edge intent as an editable Blender-native edge preview graph.",
        compositor_stack=_NATIVE_ROBERTS_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_opencl_roberts_edges",
        label="OpenCL Roberts Edges",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg roberts_opencl intent as an editable Blender-native edge preview graph.",
        compositor_stack=_OPENCL_ROBERTS_TRANSLATION.compositor_nodes,
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
        id="native_opencl_erode_matte",
        label="OpenCL Erode Matte",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg erosion_opencl intent as Blender's native Dilate/Erode compositor graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_EROSION_TRANSLATION.compositor_nodes,
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
        id="native_opencl_dilate_matte",
        label="OpenCL Dilate Matte",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg dilation_opencl intent as Blender's native Dilate/Erode compositor graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_DILATION_TRANSLATION.compositor_nodes,
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
        id="native_opencl_convolution_filter",
        label="OpenCL Convolution Filter",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg convolution_opencl kernel intent as Blender's native Convolve compositor graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_CONVOLUTION_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_fftfilt_detail",
        label="Native FFT Detail Filter",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg fftfilt frequency detail intent as Blender's native Filter sharpen/soften graph.",
        compositor_stack=_NATIVE_FFT_DETAIL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vaapi_sharpness",
        label="VAAPI Sharpness Preview",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg sharpness_vaapi intent as Blender's native compositor Filter sharpen graph without requiring VAAPI rendering.",
        compositor_stack=_VAAPI_SHARPNESS_TRANSLATION.compositor_nodes,
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
        id="native_opencl_average_blur",
        label="OpenCL Average Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg avgblur_opencl intent as Blender's native Blur compositor graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_AVERAGE_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vulkan_average_blur",
        label="Vulkan Average Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg avgblur_vulkan intent as Blender's native Blur compositor graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_AVERAGE_BLUR_TRANSLATION.compositor_nodes,
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
        id="native_opencl_box_blur",
        label="OpenCL Box Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg boxblur_opencl intent as Blender's native Blur compositor graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_BOX_BLUR_TRANSLATION.compositor_nodes,
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
        id="native_vulkan_gaussian_blur",
        label="Vulkan Gaussian Blur",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg gblur_vulkan intent as Blender's native Gaussian Blur compositor graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_GAUSSIAN_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_variable_blur",
        label="Native Variable Blur Preview",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg varblur intent as Blender's native Blur graph with min/max radius metadata.",
        compositor_stack=_NATIVE_VARIABLE_BLUR_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_bilateral_filter",
        label="Native Bilateral Filter",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bilateral intent as Blender's native Bilateral Blur compositor graph.",
        compositor_stack=_NATIVE_BILATERAL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_cuda_bilateral_filter",
        label="CUDA Bilateral Filter",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bilateral_cuda intent as Blender's native Bilateral Blur compositor graph without requiring CUDA rendering.",
        compositor_stack=_CUDA_BILATERAL_TRANSLATION.compositor_nodes,
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
        id="native_gradfun_deband",
        label="Native Gradfun Deband",
        category="Native Filter & Blur",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg gradfun anti-banding intent as Blender's native edge-aware Bilateral Blur graph.",
        compositor_stack=_NATIVE_GRADFUN_DEBAND_TRANSLATION.compositor_nodes,
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
    *_FFMPEG_EDITING_TOOLS,
    *_ffmpeg_advanced_tools_for_category("Native Matte & Channel"),
    *_ffmpeg_interop_tools_for_category("Native Matte & Channel"),
    *_ffmpeg_advanced_tools_for_category("Native Filter & Blur"),
    *_ffmpeg_advanced_tools_for_category("Native Visual FX Nodes"),
    *_ffmpeg_interop_tools_for_category("Native Visual FX Nodes"),
    *_ffmpeg_advanced_tools_for_category("Native Analysis & Utility"),
    *_ffmpeg_interop_tools_for_category("Native Analysis & Utility"),
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
    *_FFMPEG_TIMELINE_TOOLS,
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
        id="native_ffmpeg_histogram_scope",
        label="Histogram Scope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg histogram intent as a Blender RGB/luma Levels diagnostic graph for the selected strip.",
        compositor_stack=_NATIVE_HISTOGRAM_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_temporal_histogram_scope",
        label="Temporal Histogram Scope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg thistogram intent as a Blender RGB/luma Levels diagnostic graph for the selected strip.",
        compositor_stack=_NATIVE_TEMPORAL_HISTOGRAM_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_waveform_scope",
        label="Waveform Scope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg waveform intent as a Blender RGB/luma scope monitor graph.",
        compositor_stack=_NATIVE_WAVEFORM_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_vectorscope",
        label="Vectorscope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vectorscope intent as a Blender RGB/luma scope monitor graph with editable metadata.",
        compositor_stack=_NATIVE_VECTOR_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_cie_scope",
        label="CIE Scope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg ciescope intent as a Blender color diagnostic monitor graph.",
        compositor_stack=_NATIVE_CIE_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_datascope",
        label="Data Scope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg datascope intent as Blender Image Info plus RGB/luma Levels monitor nodes.",
        compositor_stack=_NATIVE_DATA_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_oscilloscope",
        label="Oscilloscope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg oscilloscope intent as a Blender RGB/luma scope monitor graph.",
        compositor_stack=_NATIVE_OSCILLOSCOPE_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_pixel_scope",
        label="Pixel Scope",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg pixscope intent as Blender Image Info, RGB/luma Levels, and Viewer monitor nodes with sampled window metadata.",
        compositor_stack=_NATIVE_PIXEL_SCOPE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_showpalette",
        label="Show Palette Monitor",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg showpalette intent as Blender RGB/luma palette-monitor graph metadata for the selected strip.",
        compositor_stack=_NATIVE_SHOWPALETTE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_thumbnail",
        label="Thumbnail Frame Preview",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg thumbnail representative-frame intent as Blender diagnostic monitor nodes with selection-window metadata.",
        compositor_stack=_NATIVE_THUMBNAIL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_cuda_thumbnail",
        label="CUDA Thumbnail Preview",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg thumbnail_cuda intent as Blender diagnostic monitor nodes without requiring CUDA rendering.",
        compositor_stack=_CUDA_THUMBNAIL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_signal_stats",
        label="Signal Stats",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg signalstats intent as Blender Levels and Image Info diagnostic nodes for the selected strip.",
        compositor_stack=_NATIVE_SIGNAL_STATS_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_entropy",
        label="Entropy Detail Monitor",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg entropy detail-analysis intent as Blender RGB/luma monitor nodes with entropy-mode metadata.",
        compositor_stack=_NATIVE_ENTROPY_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_color_detect",
        label="Color Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg colordetect intent as Blender RGB/luma Levels, Separate Color, Image Info, and Viewer diagnostic nodes.",
        compositor_stack=_NATIVE_COLOR_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_black_detect",
        label="Black Segment Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg blackdetect intent as Blender luma/RGB diagnostic monitor nodes with black-duration threshold metadata.",
        compositor_stack=_NATIVE_BLACK_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_vulkan_black_detect",
        label="Vulkan Black Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg blackdetect_vulkan intent as Blender luma/RGB diagnostic monitor nodes without requiring Vulkan rendering.",
        compositor_stack=_NATIVE_VULKAN_BLACK_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_black_frame",
        label="Black Frame Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg blackframe intent as Blender luma/RGB diagnostic monitor nodes with black-pixel threshold metadata.",
        compositor_stack=_NATIVE_BLACK_FRAME_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_block_detect",
        label="Block Artifact Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg blockdetect intent as Blender luma/RGB diagnostic monitor nodes with block-period metadata.",
        compositor_stack=_NATIVE_BLOCK_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_blur_detect",
        label="Blur Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg blurdetect intent as Blender luma/RGB diagnostic monitor nodes with edge-threshold metadata.",
        compositor_stack=_NATIVE_BLUR_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_crop_detect",
        label="Crop Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg cropdetect intent as Blender luma/RGB diagnostic monitor nodes with crop-threshold metadata.",
        compositor_stack=_NATIVE_CROP_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_bbox_detect",
        label="Bounding Box Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bbox intent as Blender luma/RGB diagnostic monitor nodes with minimum-value metadata.",
        compositor_stack=_NATIVE_BBOX_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_bitplane_noise",
        label="Bit Plane Noise Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bitplanenoise intent as Blender luma/RGB diagnostic monitor nodes with bit-plane metadata.",
        compositor_stack=_NATIVE_BITPLANE_NOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_freeze_detect",
        label="Freeze Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg freezedetect intent as Blender luma/RGB diagnostic monitor nodes with noise/duration metadata.",
        compositor_stack=_NATIVE_FREEZE_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_scene_detect",
        label="Scene Change Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scdet intent as Blender luma/RGB diagnostic monitor nodes with scene-change threshold metadata.",
        compositor_stack=_NATIVE_SCENE_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_vulkan_scene_detect",
        label="Vulkan Scene Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scdet_vulkan intent as Blender luma/RGB diagnostic monitor nodes without requiring Vulkan rendering.",
        compositor_stack=_NATIVE_VULKAN_SCENE_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_vfr_detect",
        label="Variable Frame Rate Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vfrdet intent as Blender luma/RGB diagnostic monitor nodes with frame-rate-variation metadata.",
        compositor_stack=_NATIVE_VFR_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_interlace_detect",
        label="Interlace Detect",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg idet intent as Blender luma/RGB diagnostic monitor nodes with interlace threshold metadata.",
        compositor_stack=_NATIVE_INTERLACE_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_identity_compare",
        label="Identity Reference Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg identity two-stream diagnostic intent as a Blender Difference Matte reference-difference overlay graph.",
        compositor_stack=_NATIVE_IDENTITY_COMPARE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_ssim_compare",
        label="SSIM Structure Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg ssim structural similarity intent as a Blender luma/edge Difference Matte overlay graph.",
        compositor_stack=_NATIVE_SSIM_COMPARE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_psnr_compare",
        label="PSNR Error Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg psnr peak-error intent as a Blender luma reference-difference overlay graph with stats metadata.",
        compositor_stack=_NATIVE_PSNR_COMPARE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_xpsnr_compare",
        label="XPSNR Perceptual Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg xpsnr perceptual peak-error intent as a Blender edge-weighted reference-difference overlay graph.",
        compositor_stack=_NATIVE_XPSNR_COMPARE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_corr_compare",
        label="Correlation Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg corr intent as a Blender emphasized luma correlation-difference overlay graph.",
        compositor_stack=_NATIVE_CORR_COMPARE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_msad_compare",
        label="MSAD Difference Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg msad mean-sum-absolute-difference intent as a Blender luma difference overlay graph.",
        compositor_stack=_NATIVE_MSAD_COMPARE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_vif_compare",
        label="VIF Fidelity Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vif visual-information-fidelity intent as a Blender luma/edge reference overlay graph.",
        compositor_stack=_NATIVE_VIF_COMPARE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_vmafmotion_compare",
        label="VMAF Motion Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vmafmotion intent as a Blender motion/edge reference overlay graph with stats metadata.",
        compositor_stack=_NATIVE_VMAF_MOTION_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_ffmpeg_xcorrelate_compare",
        label="Cross-Correlation Compare",
        category="Native Analysis & Utility",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg xcorrelate intent as a Blender luma/edge reference-correlation overlay graph with plane metadata.",
        compositor_stack=_NATIVE_XCORRELATE_COMPARE_TRANSLATION.compositor_nodes,
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
    *_FFMPEG_SOURCE_GENERATOR_TOOLS,
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
    *_ffmpeg_advanced_tools_for_category("Native Denoise & Cleanup"),
    VideoTool(
        id="native_hqdn3d_denoise",
        label="Native HQDN3D Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg hqdn3d intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_HQDN3D_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_chromanr_cleanup",
        label="Native Chroma NR Cleanup",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg chromanr intent as Blender's native edge-preserving Bilateral Blur cleanup graph.",
        compositor_stack=_NATIVE_CHROMANR_CLEANUP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vaapi_denoise",
        label="VAAPI Denoise Preview",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg denoise_vaapi intent as Blender's native compositor Denoise graph without requiring VAAPI rendering.",
        compositor_stack=_VAAPI_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_fft_denoise",
        label="Native FFT Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg fftdnoiz frequency-domain denoise intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_FFT_DENOISE_TRANSLATION.compositor_nodes,
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
        id="native_opencl_nlmeans_denoise",
        label="OpenCL NLMeans Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg nlmeans_opencl intent as Blender's native compositor Denoise graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_NLMEANS_DENOISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vulkan_nlmeans_denoise",
        label="Vulkan NLMeans Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg nlmeans_vulkan intent as Blender's native compositor Denoise graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_NLMEANS_DENOISE_TRANSLATION.compositor_nodes,
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
        id="native_dct_denoise",
        label="Native DCT Denoise",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg dctdnoiz frequency-domain denoise intent as Blender's native compositor Denoise graph.",
        compositor_stack=_NATIVE_DCT_DENOISE_TRANSLATION.compositor_nodes,
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
        id="native_temporal_median_preview",
        label="Native Temporal Median Preview",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg tmedian intent as Blender's native Despeckle preview with temporal median metadata.",
        compositor_stack=_NATIVE_TEMPORAL_MEDIAN_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_xmedian_preview",
        label="Native XMedian Preview",
        category="Native Denoise & Cleanup",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg xmedian multi-input median intent as Blender's native Despeckle preview with cross-input metadata.",
        compositor_stack=_NATIVE_XMEDIAN_TRANSLATION.compositor_nodes,
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
        id="native_deflicker_preview",
        label="Native Deflicker Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg deflicker intent as Blender Tone Map and luma monitor graphlets, with temporal window metadata for rendered fallback parity.",
        compositor_stack=_NATIVE_DEFLICKER_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_bwdif_deinterlace",
        label="Native BWDIF Deinterlace",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bwdif deinterlace intent as Blender Anti-Aliasing plus vertical field-blend preview nodes.",
        compositor_stack=_NATIVE_BWDIF_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_cuda_bwdif_deinterlace",
        label="CUDA BWDIF Deinterlace",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bwdif_cuda intent as Blender Anti-Aliasing plus vertical field-blend preview nodes without requiring CUDA rendering.",
        compositor_stack=_CUDA_BWDIF_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vulkan_bwdif_deinterlace",
        label="Vulkan BWDIF Deinterlace",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg bwdif_vulkan intent as Blender Anti-Aliasing plus vertical field-blend preview nodes without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_BWDIF_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_yadif_deinterlace",
        label="Native YADIF Deinterlace",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg yadif deinterlace intent as Blender Anti-Aliasing plus vertical field-blend preview nodes.",
        compositor_stack=_NATIVE_YADIF_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_cuda_yadif_deinterlace",
        label="CUDA YADIF Deinterlace",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg yadif_cuda intent as Blender Anti-Aliasing plus vertical field-blend preview nodes without requiring CUDA rendering.",
        compositor_stack=_CUDA_YADIF_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_estdif_deinterlace",
        label="Native ESTDIF Deinterlace",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg estdif intent as Blender Anti-Aliasing plus vertical field-blend preview nodes.",
        compositor_stack=_NATIVE_ESTDIF_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_w3fdif_deinterlace",
        label="Native W3FDIF Deinterlace",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg w3fdif intent as Blender Anti-Aliasing plus vertical field-blend preview nodes.",
        compositor_stack=_NATIVE_W3FDIF_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_qsv_deinterlace",
        label="QSV Deinterlace Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg deinterlace_qsv intent as Blender Anti-Aliasing plus vertical field-blend preview nodes without requiring QSV rendering.",
        compositor_stack=_QSV_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vaapi_deinterlace",
        label="VAAPI Deinterlace Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg deinterlace_vaapi intent as Blender Anti-Aliasing plus vertical field-blend preview nodes without requiring VAAPI rendering.",
        compositor_stack=_VAAPI_DEINTERLACE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_field_extract_preview",
        label="Native Field Extract Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg field intent as Blender Anti-Aliasing and field-blend preview nodes with field metadata.",
        compositor_stack=_NATIVE_FIELD_EXTRACT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_field_hint_preview",
        label="Native Field Hint Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg fieldhint intent as Blender field-cadence preview nodes with hint metadata.",
        compositor_stack=_NATIVE_FIELD_HINT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_field_match_preview",
        label="Native Field Match Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg fieldmatch intent as Blender cadence/field-match preview nodes.",
        compositor_stack=_NATIVE_FIELD_MATCH_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_field_order_preview",
        label="Native Field Order Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg fieldorder intent as Blender field-order preview nodes with parity metadata.",
        compositor_stack=_NATIVE_FIELD_ORDER_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_setfield_metadata",
        label="Native Set Field Metadata",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg setfield intent as Blender field metadata plus visible edge-smoothing preview nodes.",
        compositor_stack=_NATIVE_SET_FIELD_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_separate_fields_preview",
        label="Native Separate Fields Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg separatefields intent as Blender vertical field-blend preview nodes.",
        compositor_stack=_NATIVE_SEPARATE_FIELDS_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_repeat_fields_preview",
        label="Native Repeat Fields Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg repeatfields intent as Blender field cadence preview nodes.",
        compositor_stack=_NATIVE_REPEAT_FIELDS_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_telecine_preview",
        label="Native Telecine Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg telecine cadence intent as Blender field-blend preview nodes with pattern metadata.",
        compositor_stack=_NATIVE_TELECINE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_detelecine_preview",
        label="Native Detelecine Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg detelecine cadence intent as Blender field-blend preview nodes with pattern metadata.",
        compositor_stack=_NATIVE_DETELECINE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_decimate_preview",
        label="Native Decimate Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg decimate duplicate-frame intent as Blender luma monitor and motion-preview nodes.",
        compositor_stack=_NATIVE_DECIMATE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_mpdecimate_preview",
        label="Native MPDecimate Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg mpdecimate intent as Blender duplicate-frame monitor and motion-preview nodes.",
        compositor_stack=_NATIVE_MPDECIMATE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_mcdeint_preview",
        label="Native MCDeint Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg mcdeint intent as Blender deinterlace preview nodes with motion-compensation metadata.",
        compositor_stack=_NATIVE_MCDEINT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_nnedi_preview",
        label="Native NNEDI Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg nnedi intent as Blender deinterlace preview nodes with NNEDI metadata.",
        compositor_stack=_NATIVE_NNEDI_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_deshake_stabilize",
        label="Native Deshake Stabilize",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg deshake intent as Blender Stabilize and Transform nodes with rx/ry motion-window metadata.",
        compositor_stack=_NATIVE_DESHAKE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_opencl_deshake_stabilize",
        label="OpenCL Deshake Stabilize",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg deshake_opencl intent as Blender Stabilize and Transform nodes with rx/ry motion-window metadata.",
        compositor_stack=_OPENCL_DESHAKE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vidstab_detect_preview",
        label="Native VidStab Detect Preview",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vidstabdetect analysis intent as Blender Stabilize plus luma motion-monitor nodes with transform-file metadata.",
        compositor_stack=_NATIVE_VIDSTAB_DETECT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vidstab_transform",
        label="Native VidStab Transform",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vidstabtransform intent as Blender Stabilize and Transform crop/zoom preview nodes.",
        compositor_stack=_NATIVE_VIDSTAB_TRANSFORM_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_temporal_mix",
        label="Native Temporal Mix",
        category="Restoration",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg tmix intent as Blender blur and Alpha Over temporal-smoothing preview nodes with frame-weight metadata.",
        compositor_stack=_NATIVE_TEMPORAL_MIX_TRANSLATION.compositor_nodes,
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
    *_ffmpeg_advanced_tools_for_category("Native Geometry & Lens"),
    VideoTool(
        id="native_compositor_scale_fit",
        label="Native Scale Fit",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scale intent as Blender's native compositor Scale graph.",
        compositor_stack=_NATIVE_SCALE_FIT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_cuda_scale_fit",
        label="CUDA Scale Fit",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scale_cuda intent as Blender's native compositor Scale graph without requiring CUDA rendering.",
        compositor_stack=_CUDA_SCALE_FIT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_qsv_scale_fit",
        label="QSV Scale Fit",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scale_qsv intent as Blender's native compositor Scale graph without requiring QSV rendering.",
        compositor_stack=_QSV_SCALE_FIT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vaapi_scale_fit",
        label="VAAPI Scale Fit",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scale_vaapi intent as Blender's native compositor Scale graph without requiring VAAPI rendering.",
        compositor_stack=_VAAPI_SCALE_FIT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vulkan_scale_fit",
        label="Vulkan Scale Fit",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg scale_vulkan intent as Blender's native compositor Scale graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_SCALE_FIT_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_fillborders_repair",
        label="Native Fill Borders Repair",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg fillborders intent as Blender overscan scale and seam-softening preview nodes.",
        compositor_stack=_NATIVE_FILLBORDERS_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_floodfill_repair",
        label="Native Flood Fill Repair",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg floodfill intent as Blender Inpaint and color-overlay preview nodes with seed metadata.",
        compositor_stack=_NATIVE_FLOODFILL_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_untile_extract",
        label="Native Untile Extract",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg untile intent as Blender Scale and Translate graphlets with layout/cell metadata.",
        compositor_stack=_NATIVE_UNTILE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_v360_projection",
        label="Native V360 Projection Preview",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg v360 projection intent as Blender Lens Distortion and Transform preview nodes.",
        compositor_stack=_NATIVE_V360_TRANSLATION.compositor_nodes,
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
        id="native_opencl_transpose_clockwise",
        label="OpenCL Transpose Clockwise",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg transpose_opencl intent as Blender's native Rotate/Flip compositor graph without requiring OpenCL rendering.",
        compositor_stack=_OPENCL_TRANSPOSE_CLOCKWISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vaapi_transpose_clockwise",
        label="VAAPI Transpose Clockwise",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg transpose_vaapi intent as Blender's native Rotate/Flip compositor graph without requiring VAAPI rendering.",
        compositor_stack=_VAAPI_TRANSPOSE_CLOCKWISE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vulkan_transpose_clockwise",
        label="Vulkan Transpose Clockwise",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg transpose_vulkan intent as Blender's native Rotate/Flip compositor graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_TRANSPOSE_CLOCKWISE_TRANSLATION.compositor_nodes,
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
        id="native_vulkan_flip_horizontal",
        label="Vulkan Flip Horizontal",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg hflip_vulkan intent as Blender's native compositor Flip graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_HORIZONTAL_FLIP_TRANSLATION.compositor_nodes,
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
        id="native_vulkan_flip_vertical",
        label="Vulkan Flip Vertical",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg vflip_vulkan intent as Blender's native compositor Flip graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_VERTICAL_FLIP_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_vulkan_flip_both",
        label="Vulkan Flip Both Axes",
        category="Native Geometry & Lens",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg flip_vulkan intent as Blender's native compositor Flip graph without requiring Vulkan rendering.",
        compositor_stack=_VULKAN_BOTH_FLIP_TRANSLATION.compositor_nodes,
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
    *_ffmpeg_advanced_tools_for_category("Resolution & Motion"),
    *_ffmpeg_interop_tools_for_category("Resolution & Motion"),
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
        id="native_xbr_upscale",
        label="Native XBR Upscale",
        category="Resolution & Motion",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg xbr pixel-art upscale intent as Blender's native compositor Scale graph.",
        compositor_stack=_NATIVE_XBR_UPSCALE_TRANSLATION.compositor_nodes,
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
        id="native_fps_resample_preview",
        label="Native FPS Resample Preview",
        category="Resolution & Motion",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg fps intent as a native Blender motion-smear preview graph with target FPS metadata.",
        compositor_stack=_NATIVE_FPS_RESAMPLE_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_framerate_preview",
        label="Native Framerate Preview",
        category="Resolution & Motion",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg framerate interpolation intent as a Blender Directional Blur motion preview with interpolation metadata.",
        compositor_stack=_NATIVE_FRAMERATE_INTERPOLATION_TRANSLATION.compositor_nodes,
    ),
    VideoTool(
        id="native_minterpolate_preview",
        label="Native MInterpolate Preview",
        category="Resolution & Motion",
        engine=ENGINE_COMPOSITOR,
        description="Translated FFmpeg minterpolate intent as a Blender motion-preview graph with target FPS and interpolation-mode metadata.",
        compositor_stack=_NATIVE_MINTERPOLATE_TRANSLATION.compositor_nodes,
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
