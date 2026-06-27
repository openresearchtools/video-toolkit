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
    lumas.sort()
    return ColorStats(
        samples=usable // frame_size,
        mean_r=sum(rs) / count,
        mean_g=sum(gs) / count,
        mean_b=sum(bs) / count,
        mean_luma=sum(lumas) / len(lumas),
        luma_std=_stddev(lumas),
        luma_p05=_percentile(lumas, 0.05),
        luma_p95=_percentile(lumas, 0.95),
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
    )
    return build_color_match_stack(stats, reference)


def build_color_match_stack(
    target: ColorStats,
    reference: ColorStats,
) -> tuple[tuple[str, dict[str, object]], ...]:
    brightness = _clamp((reference.mean_luma - target.mean_luma) / 255.0, -0.18, 0.18)
    contrast = _clamp((_safe_ratio(reference.luma_std, target.luma_std) - 1.0) * 18.0, -22.0, 22.0)
    gain = _channel_balance(reference.mean_rgb, target.mean_rgb, power=0.60)
    gamma = _channel_balance(reference.mean_rgb, target.mean_rgb, power=0.28)
    lift_delta = _clamp((reference.luma_p05 - target.luma_p05) / 255.0, -0.08, 0.08)
    lift = tuple(_clamp(1.0 + lift_delta, 0.88, 1.12) for _ in range(3))
    tone_intensity = _clamp((target.luma_p95 - reference.luma_p95) / 255.0, 0.0, 0.20)
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
        ("CURVES", {}),
        ("HUE_CORRECT", {}),
    )


def summarize_stats(stats: ColorStats) -> str:
    return (
        f"{stats.samples} frames, RGB "
        f"{stats.mean_r:.1f}/{stats.mean_g:.1f}/{stats.mean_b:.1f}, "
        f"luma {stats.mean_luma:.1f}, spread {stats.luma_std:.1f}"
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

