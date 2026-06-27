import shutil
import subprocess
from pathlib import Path

import pytest

from video_toolkit.color_analysis import (
    build_auto_balance_stack,
    build_color_match_stack,
    sample_video_color,
)


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required for color analysis tests",
)


def _make_color_clip(path: Path, color: str) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:size=64x48:rate=12:duration=0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


def test_sample_video_color_reads_real_pixels(tmp_path):
    red = _make_color_clip(tmp_path / "red.mp4", "red")
    stats = sample_video_color(red, max_samples=6, sample_grid=8)
    assert stats.samples > 0
    assert stats.mean_r > stats.mean_g
    assert stats.mean_r > stats.mean_b


def test_auto_balance_builds_live_blender_stack(tmp_path):
    source = _make_color_clip(tmp_path / "blue.mp4", "blue")
    stats = sample_video_color(source, max_samples=6, sample_grid=8)
    stack = build_auto_balance_stack(stats)
    modifier_types = [modifier_type for modifier_type, _settings in stack]
    assert modifier_types[:3] == ["BRIGHT_CONTRAST", "COLOR_BALANCE", "TONEMAP"]


def test_color_match_uses_reference_statistics(tmp_path):
    target = sample_video_color(_make_color_clip(tmp_path / "red.mp4", "red"), max_samples=6, sample_grid=8)
    reference = sample_video_color(_make_color_clip(tmp_path / "blue.mp4", "blue"), max_samples=6, sample_grid=8)
    stack = build_color_match_stack(target, reference)
    color_balance = dict(stack[1][1])
    gain = color_balance["color_balance.gain"]
    assert gain[2] > gain[0]

