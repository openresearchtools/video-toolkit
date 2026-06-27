"""Frame sampling and color math used by live Blender color tools."""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_backend import FFmpegError, probe_video, require_executable


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

    @property
    def mean_rgb(self) -> tuple[float, float, float]:
        return (self.mean_r, self.mean_g, self.mean_b)


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
    for r, g, b, luma in zip(rs, gs, bs, lumas):
        if luma < shadow_threshold:
            shadow_pixels.append((r, g, b, luma))
        elif luma > highlight_threshold:
            highlight_pixels.append((r, g, b, luma))
        else:
            midtone_pixels.append((r, g, b, luma))
    lumas.sort()
    shadow_rgb, shadow_luma = _pixel_zone_average(shadow_pixels)
    midtone_rgb, midtone_luma = _pixel_zone_average(midtone_pixels)
    highlight_rgb, highlight_luma = _pixel_zone_average(highlight_pixels)
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
    )


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
    return (
        f"{stats.samples} frames, RGB "
        f"{stats.mean_r:.1f}/{stats.mean_g:.1f}/{stats.mean_b:.1f}, "
        f"luma {stats.mean_luma:.1f}, spread {stats.luma_std:.1f}, "
        f"zones S/M/H {stats.shadow_count}/{stats.midtone_count}/{stats.highlight_count}"
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
