"""Frame sampling and color math used by live Blender color tools."""

from __future__ import annotations

import math
import subprocess
from colorsys import rgb_to_hsv
from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_backend import FFmpegError, probe_video, require_executable


@dataclass(frozen=True)
class LumaSample:
    sample_index: int
    luma: float


@dataclass(frozen=True)
class ColorTimelineSample:
    sample_index: int
    rgb: tuple[float, float, float]
    luma: float
    saturation: float


@dataclass(frozen=True)
class ColorBalanceKeyframe:
    sample_index: int
    gamma: tuple[float, float, float]
    gain: tuple[float, float, float]


@dataclass(frozen=True)
class ColorStats:
    samples: int
    mean_r: float
    mean_g: float
    mean_b: float
    mean_luma: float
    luma_std: float
    luma_p05: float
    luma_p95: float
    shadow_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    midtone_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    highlight_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    shadow_luma: float = 0.0
    midtone_luma: float = 0.0
    highlight_luma: float = 0.0
    shadow_count: int = 0
    midtone_count: int = 0
    highlight_count: int = 0
    dominant_rgb: tuple[tuple[float, float, float], ...] = ()
    warm_ratio: float = 0.0
    cool_ratio: float = 0.0
    skin_ratio: float = 0.0
    mean_saturation: float = 0.0
    mean_chroma: float = 0.0

    @property
    def mean_rgb(self) -> tuple[float, float, float]:
        return (self.mean_r, self.mean_g, self.mean_b)


@dataclass(frozen=True)
class ColorDiagnosis:
    summary: str
    report: str
    findings: tuple[str, ...]
    suggested_tools: tuple[str, ...]
    palette_hex: tuple[str, ...]


def sample_video_color(
    input_path: str | Path,
    *,
    max_samples: int = 240,
    sample_grid: int = 16,
) -> ColorStats:
    """Sample frames through FFmpeg and return RGB/luma statistics.

    FFmpeg scales each sampled frame to a small grid, so the analyzer sees actual
    frame pixels across time without pulling full-resolution frames into Blender.
    """

    path = Path(input_path)
    info = probe_video(path)
    duration = info.duration or 1.0
    max_samples = max(1, int(max_samples))
    sample_grid = max(1, int(sample_grid))
    fps = min(max_samples / max(duration, 0.001), info.frame_rate or 60.0)
    ffmpeg = require_executable("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(path),
        "-an",
        "-vf",
        f"fps={fps:.6f},scale={sample_grid}:{sample_grid}:flags=area,format=rgb24",
        "-frames:v",
        str(max_samples),
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise FFmpegError(message or "ffmpeg color sampling failed")
    frame_size = sample_grid * sample_grid * 3
    usable = len(result.stdout) - (len(result.stdout) % frame_size)
    if usable <= 0:
        raise FFmpegError(f"No sample frames decoded from {path}")
    data = result.stdout[:usable]
    count = len(data) // 3
    rs: list[int] = []
    gs: list[int] = []
    bs: list[int] = []
    lumas: list[float] = []
    for offset in range(0, len(data), 3):
        r = data[offset]
        g = data[offset + 1]
        b = data[offset + 2]
        rs.append(r)
        gs.append(g)
        bs.append(b)
        lumas.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
    shadow_threshold = 85.0
    highlight_threshold = 170.0
    shadow_pixels: list[tuple[int, int, int, float]] = []
    midtone_pixels: list[tuple[int, int, int, float]] = []
    highlight_pixels: list[tuple[int, int, int, float]] = []
    dominant_bins: dict[tuple[int, int, int], list[float]] = {}
    warm_pixels = 0
    cool_pixels = 0
    skin_pixels = 0
    saturation_total = 0.0
    chroma_total = 0.0
    for r, g, b, luma in zip(rs, gs, bs, lumas):
        if luma < shadow_threshold:
            shadow_pixels.append((r, g, b, luma))
        elif luma > highlight_threshold:
            highlight_pixels.append((r, g, b, luma))
        else:
            midtone_pixels.append((r, g, b, luma))
        hue, saturation, value = rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        hue_degrees = hue * 360.0
        saturation_total += saturation
        chroma_total += max(r, g, b) - min(r, g, b)
        if saturation > 0.16 and value > 0.08:
            if 18.0 <= hue_degrees <= 75.0 or hue_degrees >= 330.0:
                warm_pixels += 1
            if 170.0 <= hue_degrees <= 285.0:
                cool_pixels += 1
            if 18.0 <= hue_degrees <= 52.0 and 0.18 <= saturation <= 0.78 and value >= 0.20:
                skin_pixels += 1
        key = (r // 32, g // 32, b // 32)
        bucket = dominant_bins.setdefault(key, [0.0, 0.0, 0.0, 0.0])
        bucket[0] += 1.0
        bucket[1] += r
        bucket[2] += g
        bucket[3] += b
    lumas.sort()
    shadow_rgb, shadow_luma = _pixel_zone_average(shadow_pixels)
    midtone_rgb, midtone_luma = _pixel_zone_average(midtone_pixels)
    highlight_rgb, highlight_luma = _pixel_zone_average(highlight_pixels)
    dominant_rgb = _dominant_swatches(dominant_bins)
    return ColorStats(
        samples=usable // frame_size,
        mean_r=sum(rs) / count,
        mean_g=sum(gs) / count,
        mean_b=sum(bs) / count,
        mean_luma=sum(lumas) / len(lumas),
        luma_std=_stddev(lumas),
        luma_p05=_percentile(lumas, 0.05),
        luma_p95=_percentile(lumas, 0.95),
        shadow_rgb=shadow_rgb,
        midtone_rgb=midtone_rgb,
        highlight_rgb=highlight_rgb,
        shadow_luma=shadow_luma,
        midtone_luma=midtone_luma,
        highlight_luma=highlight_luma,
        shadow_count=len(shadow_pixels),
        midtone_count=len(midtone_pixels),
        highlight_count=len(highlight_pixels),
        dominant_rgb=dominant_rgb,
        warm_ratio=warm_pixels / count,
        cool_ratio=cool_pixels / count,
        skin_ratio=skin_pixels / count,
        mean_saturation=saturation_total / count,
        mean_chroma=chroma_total / count,
    )


def sample_video_luma_timeline(
    input_path: str | Path,
    *,
    max_samples: int = 240,
    sample_grid: int = 12,
) -> tuple[LumaSample, ...]:
    """Sample per-frame luma through time for live keyframed normalization."""

    path = Path(input_path)
    info = probe_video(path)
    duration = info.duration or 1.0
    max_samples = max(2, int(max_samples))
    sample_grid = max(1, int(sample_grid))
    fps = min(max_samples / max(duration, 0.001), info.frame_rate or 60.0)
    ffmpeg = require_executable("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(path),
        "-an",
        "-vf",
        f"fps={fps:.6f},scale={sample_grid}:{sample_grid}:flags=area,format=rgb24",
        "-frames:v",
        str(max_samples),
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise FFmpegError(message or "ffmpeg luma timeline sampling failed")
    frame_size = sample_grid * sample_grid * 3
    usable = len(result.stdout) - (len(result.stdout) % frame_size)
    if usable <= 0:
        raise FFmpegError(f"No sample frames decoded from {path}")
    samples: list[LumaSample] = []
    for sample_index, frame_start in enumerate(range(0, usable, frame_size)):
        frame = result.stdout[frame_start : frame_start + frame_size]
        luma_total = 0.0
        pixel_count = len(frame) // 3
        for offset in range(0, len(frame), 3):
            luma_total += 0.2126 * frame[offset] + 0.7152 * frame[offset + 1] + 0.0722 * frame[offset + 2]
        samples.append(LumaSample(sample_index=sample_index, luma=luma_total / max(pixel_count, 1)))
    return tuple(samples)


def sample_video_color_timeline(
    input_path: str | Path,
    *,
    max_samples: int = 240,
    sample_grid: int = 12,
) -> tuple[ColorTimelineSample, ...]:
    """Sample per-frame RGB/luma through time for live color timeline matching."""

    path = Path(input_path)
    info = probe_video(path)
    duration = info.duration or 1.0
    max_samples = max(2, int(max_samples))
    sample_grid = max(1, int(sample_grid))
    fps = min(max_samples / max(duration, 0.001), info.frame_rate or 60.0)
    ffmpeg = require_executable("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(path),
        "-an",
        "-vf",
        f"fps={fps:.6f},scale={sample_grid}:{sample_grid}:flags=area,format=rgb24",
        "-frames:v",
        str(max_samples),
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise FFmpegError(message or "ffmpeg color timeline sampling failed")
    frame_size = sample_grid * sample_grid * 3
    usable = len(result.stdout) - (len(result.stdout) % frame_size)
    if usable <= 0:
        raise FFmpegError(f"No sample frames decoded from {path}")
    samples: list[ColorTimelineSample] = []
    for sample_index, frame_start in enumerate(range(0, usable, frame_size)):
        frame = result.stdout[frame_start : frame_start + frame_size]
        pixel_count = max(len(frame) // 3, 1)
        red = green = blue = 0.0
        saturation_total = 0.0
        for offset in range(0, len(frame), 3):
            r = frame[offset]
            g = frame[offset + 1]
            b = frame[offset + 2]
            red += r
            green += g
            blue += b
            saturation_total += rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)[1]
        rgb = (red / pixel_count, green / pixel_count, blue / pixel_count)
        samples.append(
            ColorTimelineSample(
                sample_index=sample_index,
                rgb=rgb,
                luma=0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2],
                saturation=saturation_total / pixel_count,
            )
        )
    return tuple(samples)


def build_lighting_normalization_keyframes(
    samples: tuple[LumaSample, ...],
    *,
    smoothing: int = 9,
    strength: float = 0.80,
    max_bright: float = 0.22,
) -> tuple[tuple[int, float], ...]:
    """Convert luma pulses into Blender Brightness/Contrast keyframes.

    The correction follows a moving-average target, so slow exposure changes are
    mostly preserved while frame-to-frame flicker is reduced.
    """

    if not samples:
        return ()
    smoothing = max(1, int(smoothing))
    if smoothing % 2 == 0:
        smoothing += 1
    strength = _clamp(float(strength), 0.0, 1.5)
    max_bright = abs(float(max_bright))
    lumas = [sample.luma for sample in samples]
    smoothed = _moving_average(lumas, smoothing)
    keyframes: list[tuple[int, float]] = []
    for sample, target_luma in zip(samples, smoothed):
        correction = _clamp((target_luma - sample.luma) / 255.0 * strength, -max_bright, max_bright)
        keyframes.append((sample.sample_index, correction))
    return tuple(_reduce_keyframes(keyframes))


def build_color_timeline_match_keyframes(
    target_samples: tuple[ColorTimelineSample, ...],
    reference_samples: tuple[ColorTimelineSample, ...],
    *,
    smoothing: int = 5,
    strength: float = 0.75,
    max_delta: float = 0.24,
) -> tuple[ColorBalanceKeyframe, ...]:
    """Build Color Balance keyframes that match RGB timeline shape to a reference."""

    if not target_samples or not reference_samples:
        return ()
    smoothing = max(1, int(smoothing))
    if smoothing % 2 == 0:
        smoothing += 1
    strength = _clamp(float(strength), 0.0, 1.5)
    max_delta = abs(float(max_delta))
    target_channels = _smooth_rgb_timeline(target_samples, smoothing)
    reference_channels = _smooth_rgb_timeline(reference_samples, smoothing)
    reference_channels = tuple(_resample_values(list(channel), len(target_samples)) for channel in reference_channels)
    keyframes: list[ColorBalanceKeyframe] = []
    for index, sample in enumerate(target_samples):
        raw_ratios = []
        for channel_index in range(3):
            target_value = max(target_channels[channel_index][index], 1.0)
            reference_value = max(reference_channels[channel_index][index], 1.0)
            ratio = 1.0 + ((_safe_ratio(reference_value, target_value) ** 0.45) - 1.0) * strength
            raw_ratios.append(ratio)
        average = sum(raw_ratios) / 3.0
        gamma = tuple(_clamp(value / average, 1.0 - max_delta, 1.0 + max_delta) for value in raw_ratios)
        gain = tuple(_clamp(1.0 + (value - 1.0) * 0.60, 1.0 - max_delta * 0.75, 1.0 + max_delta * 0.75) for value in gamma)
        keyframes.append(ColorBalanceKeyframe(sample.sample_index, gamma, gain))
    return tuple(_reduce_color_keyframes(keyframes))


def build_lighting_match_keyframes(
    target_samples: tuple[LumaSample, ...],
    reference_samples: tuple[LumaSample, ...],
    *,
    smoothing: int = 5,
    strength: float = 0.85,
    max_bright: float = 0.26,
) -> tuple[tuple[int, float], ...]:
    """Build brightness keyframes that match target luma to a reference clip."""

    if not target_samples or not reference_samples:
        return ()
    smoothing = max(1, int(smoothing))
    if smoothing % 2 == 0:
        smoothing += 1
    strength = _clamp(float(strength), 0.0, 1.5)
    max_bright = abs(float(max_bright))
    target_lumas = _moving_average([sample.luma for sample in target_samples], smoothing)
    reference_lumas = _moving_average([sample.luma for sample in reference_samples], smoothing)
    reference_lumas = _resample_values(reference_lumas, len(target_lumas))
    keyframes: list[tuple[int, float]] = []
    for sample, target_luma, reference_luma in zip(target_samples, target_lumas, reference_lumas):
        correction = _clamp((reference_luma - target_luma) / 255.0 * strength, -max_bright, max_bright)
        keyframes.append((sample.sample_index, correction))
    return tuple(_reduce_keyframes(keyframes))


def build_auto_balance_stack(stats: ColorStats) -> tuple[tuple[str, dict[str, object]], ...]:
    reference = ColorStats(
        samples=stats.samples,
        mean_r=118.0,
        mean_g=118.0,
        mean_b=118.0,
        mean_luma=118.0,
        luma_std=54.0,
        luma_p05=24.0,
        luma_p95=224.0,
        shadow_rgb=(38.0, 38.0, 38.0),
        midtone_rgb=(118.0, 118.0, 118.0),
        highlight_rgb=(218.0, 218.0, 218.0),
        shadow_luma=38.0,
        midtone_luma=118.0,
        highlight_luma=218.0,
        dominant_rgb=((118.0, 118.0, 118.0),),
        warm_ratio=0.18,
        cool_ratio=0.18,
        skin_ratio=0.08,
        mean_saturation=0.36,
        mean_chroma=52.0,
    )
    return build_color_match_stack(stats, reference)


def build_color_match_stack(
    target: ColorStats,
    reference: ColorStats,
) -> tuple[tuple[str, dict[str, object]], ...]:
    brightness = _clamp((reference.mean_luma - target.mean_luma) / 255.0, -0.18, 0.18)
    contrast = _clamp((_safe_ratio(reference.luma_std, target.luma_std) - 1.0) * 18.0, -22.0, 22.0)
    lift = _zone_balance(reference.shadow_rgb, target.shadow_rgb, fallback=reference.mean_rgb, power=0.42, low=0.84, high=1.18)
    gamma = _zone_balance(reference.midtone_rgb, target.midtone_rgb, fallback=reference.mean_rgb, power=0.32, low=0.82, high=1.22)
    gain = _zone_balance(reference.highlight_rgb, target.highlight_rgb, fallback=reference.mean_rgb, power=0.55, low=0.80, high=1.25)
    tone_intensity = _clamp((target.luma_p95 - reference.luma_p95) / 255.0, 0.0, 0.20)
    curve_points = _contrast_curve_points(target, reference)
    return (
        ("BRIGHT_CONTRAST", {"bright": brightness, "contrast": contrast}),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.lift": lift,
                "color_balance.gamma": gamma,
                "color_balance.gain": gain,
                "color_multiply": 1.0,
            },
        ),
        (
            "TONEMAP",
            {
                "tonemap_type": "RD_PHOTORECEPTOR",
                "intensity": tone_intensity,
                "contrast": _clamp(abs(contrast) / 80.0, 0.0, 0.24),
                "gamma": _clamp(_safe_ratio(reference.mean_luma, target.mean_luma), 0.80, 1.25),
            },
        ),
        ("CURVES", {"__curve_points__": {0: curve_points}}),
        ("HUE_CORRECT", {"__hue_correct__": {"saturation": _saturation_curve_value(target, reference)}}),
    )


def summarize_stats(stats: ColorStats) -> str:
    palette = ""
    if stats.dominant_rgb:
        palette = ", palette " + " ".join(_rgb_hex(rgb) for rgb in stats.dominant_rgb[:3])
    return (
        f"{stats.samples} frames, RGB "
        f"{stats.mean_r:.1f}/{stats.mean_g:.1f}/{stats.mean_b:.1f}, "
        f"luma {stats.mean_luma:.1f}, spread {stats.luma_std:.1f}, "
        f"zones S/M/H {stats.shadow_count}/{stats.midtone_count}/{stats.highlight_count}, "
        f"warm/cool/skin {stats.warm_ratio:.2f}/{stats.cool_ratio:.2f}/{stats.skin_ratio:.2f}"
        f"{palette}"
    )


def diagnose_color(stats: ColorStats) -> ColorDiagnosis:
    """Turn sampled frame statistics into an editor-facing color diagnosis."""

    findings: list[str] = []
    tools: list[str] = []
    dynamic_range = stats.luma_p95 - stats.luma_p05
    if stats.mean_luma < 92.0:
        findings.append(f"Underexposed average luma ({stats.mean_luma:.1f}); lift exposure and midtones.")
        tools.extend(["Exposure Lift", "Gamma Brighten"])
    elif stats.mean_luma > 176.0 or stats.luma_p95 > 236.0:
        findings.append(f"Bright/highlight-heavy image (p95 {stats.luma_p95:.1f}); protect highlights.")
        tools.extend(["Exposure Protect", "HDR Tone Compress"])
    else:
        findings.append(f"Balanced exposure band (mean luma {stats.mean_luma:.1f}).")
    if dynamic_range < 118.0 or stats.luma_std < 34.0:
        findings.append(f"Low tonal separation (range {dynamic_range:.1f}, spread {stats.luma_std:.1f}); expand levels.")
        tools.extend(["Levels Expand", "Contrast Pop"])
    elif dynamic_range > 222.0:
        findings.append(f"Wide tonal range (range {dynamic_range:.1f}); use tone compression for review.")
        tools.append("HDR Tone Compress")
    else:
        findings.append(f"Usable tonal range (p05/p95 {stats.luma_p05:.1f}/{stats.luma_p95:.1f}).")
    warm_delta = stats.warm_ratio - stats.cool_ratio
    if warm_delta > 0.18:
        findings.append(f"Warm cast detected (warm/cool {stats.warm_ratio:.2f}/{stats.cool_ratio:.2f}).")
        tools.append("Temperature Cool")
    elif warm_delta < -0.18:
        findings.append(f"Cool cast detected (warm/cool {stats.warm_ratio:.2f}/{stats.cool_ratio:.2f}).")
        tools.append("Temperature Warm")
    else:
        findings.append(f"Warm/cool balance is near neutral ({stats.warm_ratio:.2f}/{stats.cool_ratio:.2f}).")
    if stats.mean_saturation < 0.18 or stats.mean_chroma < 28.0:
        findings.append(f"Low chroma/saturation ({stats.mean_chroma:.1f}, {stats.mean_saturation:.2f}); add vibrance.")
        tools.extend(["Vibrance", "Saturation Boost"])
    elif stats.mean_saturation > 0.62:
        findings.append(f"High saturation ({stats.mean_saturation:.2f}); reduce saturation if skin or broadcast range clips.")
        tools.append("Saturation Reduce")
    else:
        findings.append(f"Saturation is in a workable band ({stats.mean_saturation:.2f}).")
    if stats.skin_ratio > 0.10:
        findings.append(f"Skin-tone-like pixels present ({stats.skin_ratio:.2f}); prefer skin-safe vibrance.")
        tools.append("Skin-Safe Vibrance")
    palette_hex = tuple(_rgb_hex(rgb) for rgb in stats.dominant_rgb[:5])
    if not tools:
        tools.extend(["Neutral Grade", "Live Pro Color Stack"])
    suggested_tools = _dedupe_preserve_order(tools)
    summary = f"diagnosis {stats.samples} frames, {len(findings)} findings, tools: {', '.join(suggested_tools[:4])}"
    report_lines = [
        "Video Toolkit Color Diagnostics",
        f"Frames sampled: {stats.samples}",
        f"Mean RGB: {stats.mean_r:.1f}/{stats.mean_g:.1f}/{stats.mean_b:.1f}",
        f"Luma mean/std/p05/p95: {stats.mean_luma:.1f}/{stats.luma_std:.1f}/{stats.luma_p05:.1f}/{stats.luma_p95:.1f}",
        f"Zones shadow/midtone/highlight pixels: {stats.shadow_count}/{stats.midtone_count}/{stats.highlight_count}",
        f"Warm/cool/skin ratios: {stats.warm_ratio:.2f}/{stats.cool_ratio:.2f}/{stats.skin_ratio:.2f}",
        f"Saturation/chroma: {stats.mean_saturation:.2f}/{stats.mean_chroma:.1f}",
        "Palette: " + (" ".join(palette_hex) if palette_hex else "none"),
        "Findings:",
        *[f"- {finding}" for finding in findings],
        "Suggested native Blender tools:",
        *[f"- {tool}" for tool in suggested_tools],
    ]
    return ColorDiagnosis(summary, "\n".join(report_lines), tuple(findings), suggested_tools, palette_hex)


def build_color_identity_stack(stats: ColorStats) -> tuple[tuple[str, dict[str, object]], ...]:
    """Build a live stack from palette, warm/cool, skin, and tonal identity."""

    warm_cool_delta = _clamp(stats.warm_ratio - stats.cool_ratio, -0.55, 0.55)
    red_balance = _clamp(1.0 - warm_cool_delta * 0.16, 0.86, 1.14)
    blue_balance = _clamp(1.0 + warm_cool_delta * 0.18, 0.84, 1.16)
    green_balance = _clamp(1.0 - abs(warm_cool_delta) * 0.03, 0.94, 1.04)
    if stats.skin_ratio > 0.12:
        red_balance = _clamp((red_balance + 1.0) * 0.5, 0.92, 1.08)
        blue_balance = _clamp((blue_balance + 1.0) * 0.5, 0.92, 1.08)
    saturation_target = _palette_saturation_target(stats)
    curve_points = _identity_curve_points(stats)
    return (
        (
            "WHITE_BALANCE",
            {"white_value": (red_balance, green_balance, blue_balance)},
        ),
        (
            "COLOR_BALANCE",
            {
                "color_balance.correction_method": "LIFT_GAMMA_GAIN",
                "color_balance.lift": _identity_lift(stats),
                "color_balance.gamma": (red_balance, green_balance, blue_balance),
                "color_balance.gain": _identity_gain(stats, (red_balance, green_balance, blue_balance)),
                "color_multiply": _clamp(1.0 + (saturation_target - 1.0) * 0.12, 0.85, 1.16),
            },
        ),
        ("CURVES", {"__curve_points__": {0: curve_points}}),
        ("HUE_CORRECT", {"__hue_correct__": {"saturation": _clamp(0.5 * saturation_target, 0.18, 0.82)}}),
        (
            "TONEMAP",
            {
                "tonemap_type": "RD_PHOTORECEPTOR",
                "intensity": _clamp(max(stats.luma_p95 - 218.0, 0.0) / 255.0, 0.0, 0.16),
                "contrast": _clamp(abs(stats.luma_std - 54.0) / 255.0, 0.0, 0.18),
                "gamma": _clamp(118.0 / max(stats.mean_luma, 1.0), 0.82, 1.18),
            },
        ),
    )


def _channel_balance(
    reference_rgb: tuple[float, float, float],
    target_rgb: tuple[float, float, float],
    *,
    power: float,
) -> tuple[float, float, float]:
    ratios = [_safe_ratio(ref, target) ** power for ref, target in zip(reference_rgb, target_rgb)]
    average = sum(ratios) / len(ratios)
    return tuple(_clamp(value / average, 0.82, 1.22) for value in ratios)


def _zone_balance(
    reference_rgb: tuple[float, float, float],
    target_rgb: tuple[float, float, float],
    *,
    fallback: tuple[float, float, float],
    power: float,
    low: float,
    high: float,
) -> tuple[float, float, float]:
    if sum(target_rgb) <= 1.0 or sum(reference_rgb) <= 1.0:
        return _channel_balance(fallback, target_rgb if sum(target_rgb) > 1.0 else fallback, power=power)
    ratios = [_safe_ratio(ref, target) ** power for ref, target in zip(reference_rgb, target_rgb)]
    average = sum(ratios) / len(ratios)
    return tuple(_clamp(value / average, low, high) for value in ratios)


def _pixel_zone_average(pixels: list[tuple[int, int, int, float]]) -> tuple[tuple[float, float, float], float]:
    if not pixels:
        return (0.0, 0.0, 0.0), 0.0
    count = len(pixels)
    return (
        (
            sum(pixel[0] for pixel in pixels) / count,
            sum(pixel[1] for pixel in pixels) / count,
            sum(pixel[2] for pixel in pixels) / count,
        ),
        sum(pixel[3] for pixel in pixels) / count,
    )


def _dominant_swatches(bins: dict[tuple[int, int, int], list[float]]) -> tuple[tuple[float, float, float], ...]:
    swatches: list[tuple[float, float, float, float]] = []
    for count, red, green, blue in bins.values():
        if count <= 0:
            continue
        swatches.append((count, red / count, green / count, blue / count))
    swatches.sort(reverse=True)
    return tuple((red, green, blue) for _count, red, green, blue in swatches[:5])


def _rgb_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{int(_clamp(channel, 0.0, 255.0)):02x}" for channel in rgb)


def _dedupe_preserve_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return tuple(result)


def _moving_average(values: list[float], window: int) -> list[float]:
    half = window // 2
    result: list[float] = []
    for index in range(len(values)):
        start = max(0, index - half)
        end = min(len(values), index + half + 1)
        result.append(sum(values[start:end]) / max(end - start, 1))
    return result


def _smooth_rgb_timeline(samples: tuple[ColorTimelineSample, ...], smoothing: int) -> tuple[list[float], list[float], list[float]]:
    return (
        _moving_average([sample.rgb[0] for sample in samples], smoothing),
        _moving_average([sample.rgb[1] for sample in samples], smoothing),
        _moving_average([sample.rgb[2] for sample in samples], smoothing),
    )


def _resample_values(values: list[float], output_count: int) -> list[float]:
    if output_count <= 0:
        return []
    if not values:
        return [0.0] * output_count
    if len(values) == output_count:
        return values
    if output_count == 1:
        return [values[0]]
    if len(values) == 1:
        return [values[0]] * output_count
    result: list[float] = []
    source_max = len(values) - 1
    target_max = output_count - 1
    for index in range(output_count):
        position = index * source_max / target_max
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            result.append(values[lower])
            continue
        fraction = position - lower
        result.append(values[lower] * (1.0 - fraction) + values[upper] * fraction)
    return result


def _reduce_keyframes(keyframes: list[tuple[int, float]]) -> list[tuple[int, float]]:
    if len(keyframes) <= 2:
        return keyframes
    reduced = [keyframes[0]]
    for previous, current, following in zip(keyframes, keyframes[1:], keyframes[2:]):
        slope_a = current[1] - previous[1]
        slope_b = following[1] - current[1]
        if abs(current[1]) < 0.001 and abs(slope_a) < 0.001 and abs(slope_b) < 0.001:
            continue
        reduced.append(current)
    reduced.append(keyframes[-1])
    return reduced


def _reduce_color_keyframes(keyframes: list[ColorBalanceKeyframe]) -> list[ColorBalanceKeyframe]:
    if len(keyframes) <= 2:
        return keyframes
    reduced = [keyframes[0]]
    for previous, current, following in zip(keyframes, keyframes[1:], keyframes[2:]):
        previous_values = previous.gamma + previous.gain
        current_values = current.gamma + current.gain
        following_values = following.gamma + following.gain
        flat = all(abs(value - 1.0) < 0.001 for value in current_values)
        slope_in = max(abs(current_value - previous_value) for current_value, previous_value in zip(current_values, previous_values))
        slope_out = max(abs(following_value - current_value) for following_value, current_value in zip(following_values, current_values))
        if flat and slope_in < 0.001 and slope_out < 0.001:
            continue
        reduced.append(current)
    reduced.append(keyframes[-1])
    return reduced


def _contrast_curve_points(target: ColorStats, reference: ColorStats) -> list[tuple[float, float]]:
    shadow_delta = _clamp((reference.shadow_luma - target.shadow_luma) / 255.0, -0.12, 0.12)
    mid_delta = _clamp((reference.midtone_luma - target.midtone_luma) / 255.0, -0.10, 0.10)
    highlight_delta = _clamp((reference.highlight_luma - target.highlight_luma) / 255.0, -0.12, 0.12)
    return [
        (0.0, 0.0),
        (0.25, _clamp(0.25 + shadow_delta, 0.02, 0.48)),
        (0.50, _clamp(0.50 + mid_delta, 0.25, 0.75)),
        (0.75, _clamp(0.75 + highlight_delta, 0.52, 0.98)),
        (1.0, 1.0),
    ]


def _identity_curve_points(stats: ColorStats) -> list[tuple[float, float]]:
    black_in = _clamp(stats.luma_p05 / 255.0, 0.01, 0.30)
    white_in = _clamp(stats.luma_p95 / 255.0, 0.55, 1.0)
    if white_in - black_in < 0.20:
        white_in = _clamp(black_in + 0.20, 0.55, 1.0)
    mid_delta = _clamp((118.0 - stats.midtone_luma) / 255.0, -0.08, 0.08)
    return [
        (0.0, 0.0),
        (black_in, 0.02),
        (0.50, _clamp(0.50 + mid_delta, 0.36, 0.64)),
        (white_in, 0.98),
        (1.0, 1.0),
    ]


def _identity_lift(stats: ColorStats) -> tuple[float, float, float]:
    lift_value = _clamp(1.0 + (38.0 - stats.shadow_luma) / 255.0 * 0.26, 0.88, 1.12)
    return (lift_value, lift_value, lift_value)


def _identity_gain(stats: ColorStats, balance: tuple[float, float, float]) -> tuple[float, float, float]:
    gain_value = _clamp(1.0 + (218.0 - stats.highlight_luma) / 255.0 * 0.20, 0.90, 1.14)
    return tuple(_clamp(gain_value * channel, 0.84, 1.20) for channel in balance)


def _palette_saturation_target(stats: ColorStats) -> float:
    chroma_factor = stats.mean_chroma / 255.0
    if stats.skin_ratio > 0.10:
        return _clamp(1.0 + (0.23 - chroma_factor) * 0.55, 0.86, 1.12)
    return _clamp(1.0 + (0.28 - chroma_factor) * 0.70, 0.76, 1.28)


def _saturation_curve_value(target: ColorStats, reference: ColorStats) -> float:
    target_chroma = _rgb_chroma(target.mean_rgb)
    reference_chroma = _rgb_chroma(reference.mean_rgb)
    if target_chroma <= 1e-6:
        return 0.5
    return _clamp(0.5 * _safe_ratio(reference_chroma, target_chroma), 0.15, 0.85)


def _rgb_chroma(rgb: tuple[float, float, float]) -> float:
    return max(rgb) - min(rgb)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / max(denominator, 1e-6)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _stddev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = _clamp((len(values) - 1) * percentile, 0, len(values) - 1)
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return values[lower]
    fraction = index - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction
