import shutil
import subprocess
from pathlib import Path

import pytest

from video_toolkit.color_analysis import (
    LumaSample,
    ColorTimelineSample,
    build_auto_balance_stack,
    build_color_identity_stack,
    build_color_match_stack,
    build_color_timeline_match_keyframes,
    build_lighting_match_keyframes,
    build_lighting_normalization_keyframes,
    sample_video_color_timeline,
    sample_video_luma_timeline,
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
    assert stats.highlight_count + stats.midtone_count + stats.shadow_count > 0
    assert stats.dominant_rgb
    assert stats.mean_chroma > 0


def test_sample_video_luma_timeline_reads_real_frames(tmp_path):
    red = _make_color_clip(tmp_path / "red_timeline.mp4", "red")
    timeline = sample_video_luma_timeline(red, max_samples=6, sample_grid=8)
    assert len(timeline) > 0
    assert timeline[0].sample_index == 0
    assert all(sample.luma > 0 for sample in timeline)


def test_sample_video_color_timeline_reads_real_frame_rgb(tmp_path):
    red = _make_color_clip(tmp_path / "red_color_timeline.mp4", "red")
    timeline = sample_video_color_timeline(red, max_samples=6, sample_grid=8)
    assert len(timeline) > 0
    assert timeline[0].rgb[0] > timeline[0].rgb[1]
    assert timeline[0].rgb[0] > timeline[0].rgb[2]


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
    curves = dict(stack[3][1])
    assert "__curve_points__" in curves
    hue_correct = dict(stack[4][1])
    assert "__hue_correct__" in hue_correct


def test_color_identity_stack_uses_palette_math(tmp_path):
    warm = sample_video_color(_make_color_clip(tmp_path / "orange.mp4", "orange"), max_samples=6, sample_grid=8)
    cool = sample_video_color(_make_color_clip(tmp_path / "blue.mp4", "blue"), max_samples=6, sample_grid=8)
    assert warm.warm_ratio > warm.cool_ratio
    assert cool.cool_ratio > cool.warm_ratio

    stack = build_color_identity_stack(warm)
    assert [modifier_type for modifier_type, _settings in stack] == [
        "WHITE_BALANCE",
        "COLOR_BALANCE",
        "CURVES",
        "HUE_CORRECT",
        "TONEMAP",
    ]
    white_value = stack[0][1]["white_value"]
    assert white_value[2] > white_value[0]


def test_lighting_normalization_keyframes_follow_smoothed_luma():
    samples = (
        LumaSample(0, 90.0),
        LumaSample(1, 150.0),
        LumaSample(2, 92.0),
        LumaSample(3, 148.0),
        LumaSample(4, 91.0),
    )
    keyframes = build_lighting_normalization_keyframes(samples, smoothing=3, strength=1.0)
    assert len(keyframes) == 5
    corrections = dict(keyframes)
    assert corrections[1] < 0.0
    assert corrections[2] > 0.0


def test_lighting_match_keyframes_follow_reference_luma():
    target = (
        LumaSample(0, 90.0),
        LumaSample(1, 100.0),
        LumaSample(2, 110.0),
        LumaSample(3, 120.0),
    )
    reference = (
        LumaSample(0, 140.0),
        LumaSample(1, 150.0),
    )
    keyframes = build_lighting_match_keyframes(target, reference, smoothing=1, strength=1.0)
    assert len(keyframes) == 4
    assert all(value > 0.0 for _index, value in keyframes)
    assert keyframes[0][1] > keyframes[-1][1]


def test_color_timeline_match_keyframes_follow_reference_rgb():
    target = (
        ColorTimelineSample(0, (180.0, 70.0, 60.0), 95.0, 0.5),
        ColorTimelineSample(1, (170.0, 75.0, 65.0), 96.0, 0.5),
    )
    reference = (
        ColorTimelineSample(0, (70.0, 80.0, 190.0), 92.0, 0.5),
        ColorTimelineSample(1, (75.0, 85.0, 185.0), 94.0, 0.5),
    )
    keyframes = build_color_timeline_match_keyframes(target, reference, smoothing=1, strength=1.0)
    assert len(keyframes) == 2
    assert keyframes[0].gamma[2] > keyframes[0].gamma[0]
    assert keyframes[0].gain[2] > keyframes[0].gain[0]
