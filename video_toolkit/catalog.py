"""Shared filter catalog for Blender UI, CLI, and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


ENGINE_BLENDER_MODIFIER = "blender_modifier"
ENGINE_FFMPEG = "ffmpeg"


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
    ffmpeg_filter: str | None = None
    ffmpeg_filter_after_stabilize: str | None = None
    two_pass_stabilize: bool = False
    slow: bool = False

    @property
    def is_blender_modifier(self) -> bool:
        return self.engine == ENGINE_BLENDER_MODIFIER

    @property
    def is_ffmpeg(self) -> bool:
        return self.engine == ENGINE_FFMPEG


TOOLS: tuple[VideoTool, ...] = (
    VideoTool(
        id="auto_enhance",
        label="Auto Enhance",
        category="Enhance",
        engine=ENGINE_FFMPEG,
        description="Balanced contrast, saturation, gamma, temporal normalization, and light sharpening.",
        ffmpeg_filter=(
            "normalize=smoothing=30:independence=0.55:strength=0.65,"
            "eq=contrast=1.08:saturation=1.08:gamma=1.02,"
            "unsharp=5:5:0.45:3:3:0.20"
        ),
    ),
    VideoTool(
        id="neutral_grade",
        label="Neutral Grade",
        category="Enhance",
        engine=ENGINE_FFMPEG,
        description="Clean baseline grade with conservative contrast and saturation.",
        ffmpeg_filter="eq=contrast=1.04:saturation=1.03:gamma=1.00",
    ),
    VideoTool(
        id="punchy_color",
        label="Punchy Color",
        category="Enhance",
        engine=ENGINE_FFMPEG,
        description="Adds contrast and color density for social/editorial footage.",
        ffmpeg_filter="eq=contrast=1.14:saturation=1.18:gamma=0.98",
    ),
    VideoTool(
        id="soft_contrast",
        label="Soft Contrast",
        category="Enhance",
        engine=ENGINE_FFMPEG,
        description="Gently reduces harsh contrast while preserving color.",
        ffmpeg_filter="eq=contrast=0.94:saturation=1.03:gamma=1.04",
    ),
    VideoTool(
        id="exposure_lift",
        label="Exposure Lift",
        category="Color & Tone",
        engine=ENGINE_FFMPEG,
        description="Brightens underexposed clips without a heavy color cast.",
        ffmpeg_filter="eq=brightness=0.035:contrast=1.03:gamma=1.08:saturation=1.02",
    ),
    VideoTool(
        id="gamma_brighten",
        label="Gamma Brighten",
        category="Color & Tone",
        engine=ENGINE_FFMPEG,
        description="Raises midtones with a gamma correction pass.",
        ffmpeg_filter="eq=gamma=1.18:gamma_weight=0.82",
    ),
    VideoTool(
        id="gamma_deepen",
        label="Gamma Deepen",
        category="Color & Tone",
        engine=ENGINE_FFMPEG,
        description="Deepens washed midtones and lowers perceived haze.",
        ffmpeg_filter="eq=gamma=0.88:contrast=1.04",
    ),
    VideoTool(
        id="warm_balance",
        label="Warm Balance",
        category="Color & Tone",
        engine=ENGINE_FFMPEG,
        description="Warms cool footage with a subtle channel balance.",
        ffmpeg_filter="colorchannelmixer=rr=1.04:gg=1.00:bb=0.96,eq=saturation=1.03",
    ),
    VideoTool(
        id="cool_balance",
        label="Cool Balance",
        category="Color & Tone",
        engine=ENGINE_FFMPEG,
        description="Cools overly warm footage with a subtle channel balance.",
        ffmpeg_filter="colorchannelmixer=rr=0.97:gg=1.00:bb=1.04,eq=saturation=1.02",
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
        category="Blender VSE Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Brightness/Contrast strip modifier.",
        blender_modifier="BRIGHT_CONTRAST",
        blender_settings={"bright": 0.04, "contrast": 1.08},
    ),
    VideoTool(
        id="vse_color_balance",
        label="VSE Color Balance",
        category="Blender VSE Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Color Balance strip modifier with a mild lift/gamma/gain setup.",
        blender_modifier="COLOR_BALANCE",
        blender_settings={
            "color_balance.lift": (0.98, 0.98, 1.00),
            "color_balance.gamma": (1.02, 1.02, 1.02),
            "color_balance.gain": (1.04, 1.04, 1.04),
        },
    ),
    VideoTool(
        id="vse_curves",
        label="VSE Curves",
        category="Blender VSE Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Curves strip modifier for manual curve shaping.",
        blender_modifier="CURVES",
    ),
    VideoTool(
        id="vse_hue_correct",
        label="VSE Hue Correct",
        category="Blender VSE Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Hue Correct strip modifier for hue-zone corrections.",
        blender_modifier="HUE_CORRECT",
    ),
    VideoTool(
        id="vse_mask",
        label="VSE Mask Slot",
        category="Blender VSE Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Mask strip modifier ready for a mask assignment.",
        blender_modifier="MASK",
    ),
    VideoTool(
        id="vse_tonemap",
        label="VSE Tone Map",
        category="Blender VSE Modifiers",
        engine=ENGINE_BLENDER_MODIFIER,
        description="Adds Blender's native Tone Map strip modifier.",
        blender_modifier="TONEMAP",
        blender_settings={"tonemap_type": "RD_PHOTORECEPTOR", "intensity": 0.12, "contrast": 0.16},
    ),
    VideoTool(
        id="vse_white_balance",
        label="VSE White Balance",
        category="Blender VSE Modifiers",
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
