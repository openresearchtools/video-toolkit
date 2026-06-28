import shutil
import subprocess
from pathlib import Path

import pytest

from video_toolkit.color_analysis import (
    ColorStats,
    LumaSample,
    ColorTimelineSample,
    build_auto_balance_stack,
    build_color_identity_stack,
    build_color_match_stack,
    build_sampled_color_management,
    build_sampled_color_board_stack,
    build_sampled_compositor_grade,
    build_sampled_hue_chroma_stack,
    build_sampled_levels_gamma_stack,
    build_sampled_pro_grade_stack,
    build_sampled_white_balance_stack,
    build_color_timeline_match_keyframes,
    build_lighting_match_keyframes,
    build_lighting_normalization_keyframes,
    diagnose_color,
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


def test_sampled_white_balance_stack_neutralizes_measured_cast(tmp_path):
    warm = sample_video_color(_make_color_clip(tmp_path / "warm_balance.mp4", "orange"), max_samples=6, sample_grid=8)
    stack = build_sampled_white_balance_stack(warm)
    assert [modifier_type for modifier_type, _settings in stack] == [
        "WHITE_BALANCE",
        "COLOR_BALANCE",
        "BRIGHT_CONTRAST",
        "CURVES",
        "HUE_CORRECT",
    ]
    white_value = stack[0][1]["white_value"]
    assert white_value[2] > white_value[0]
    color_balance = stack[1][1]
    assert color_balance["color_balance.gamma"][2] > color_balance["color_balance.gamma"][0]
    assert "__curve_points__" in stack[3][1]
    assert "__hue_correct__" in stack[4][1]


def test_sampled_levels_gamma_stack_normalizes_luma_percentiles():
    stats = ColorStats(
        samples=12,
        mean_r=104.0,
        mean_g=106.0,
        mean_b=108.0,
        mean_luma=106.0,
        luma_std=12.0,
        luma_p05=64.0,
        luma_p95=156.0,
        shadow_rgb=(52.0, 52.0, 54.0),
        midtone_rgb=(94.0, 96.0, 98.0),
        highlight_rgb=(152.0, 154.0, 158.0),
        shadow_luma=52.0,
        midtone_luma=96.0,
        highlight_luma=154.0,
        shadow_count=100,
        midtone_count=200,
        highlight_count=100,
        mean_saturation=0.12,
        mean_chroma=12.0,
    )
    stack = build_sampled_levels_gamma_stack(stats)
    assert [modifier_type for modifier_type, _settings in stack] == [
        "CURVES",
        "COLOR_BALANCE",
        "BRIGHT_CONTRAST",
        "TONEMAP",
        "HUE_CORRECT",
    ]
    curve_points = stack[0][1]["__curve_points__"][0]
    assert curve_points[1][0] < curve_points[2][0] < curve_points[3][0]
    color_balance = stack[1][1]
    assert color_balance["color_balance.gamma"][0] > 1.0
    assert stack[2][1]["contrast"] > 0.0


def test_sampled_hue_chroma_stack_builds_hue_zone_curves():
    stats = ColorStats(
        samples=12,
        mean_r=170.0,
        mean_g=72.0,
        mean_b=54.0,
        mean_luma=95.0,
        luma_std=38.0,
        luma_p05=30.0,
        luma_p95=190.0,
        dominant_rgb=((210.0, 44.0, 38.0), (40.0, 90.0, 215.0), (224.0, 180.0, 52.0)),
        warm_ratio=0.46,
        cool_ratio=0.16,
        skin_ratio=0.12,
        mean_saturation=0.58,
        mean_chroma=116.0,
    )
    stack = build_sampled_hue_chroma_stack(stats)
    assert [modifier_type for modifier_type, _settings in stack] == [
        "HUE_CORRECT",
        "COLOR_BALANCE",
        "CURVES",
    ]
    hue_points = stack[0][1]["__curve_points__"]
    assert set(hue_points) == {0, 1, 2}
    assert hue_points[1][0][1] < 0.5
    color_balance = stack[1][1]
    assert color_balance["color_balance.gamma"][2] > color_balance["color_balance.gamma"][0]


def test_sampled_pro_grade_combines_sampled_native_stacks():
    stats = ColorStats(
        samples=24,
        mean_r=148.0,
        mean_g=122.0,
        mean_b=96.0,
        mean_luma=126.0,
        luma_std=31.0,
        luma_p05=42.0,
        luma_p95=204.0,
        shadow_rgb=(38.0, 34.0, 30.0),
        midtone_rgb=(126.0, 116.0, 100.0),
        highlight_rgb=(206.0, 188.0, 160.0),
        shadow_luma=35.0,
        midtone_luma=116.0,
        highlight_luma=188.0,
        dominant_rgb=((190.0, 96.0, 42.0), (42.0, 88.0, 170.0)),
        warm_ratio=0.36,
        cool_ratio=0.18,
        skin_ratio=0.09,
        mean_saturation=0.44,
        mean_chroma=72.0,
    )
    stack = build_sampled_pro_grade_stack(stats)
    assert [modifier_type for modifier_type, _settings in stack] == [
        "WHITE_BALANCE",
        "COLOR_BALANCE",
        "CURVES",
        "COLOR_BALANCE",
        "BRIGHT_CONTRAST",
        "TONEMAP",
        "HUE_CORRECT",
        "COLOR_BALANCE",
        "CURVES",
        "HUE_CORRECT",
    ]
    assert stack[0][1]["white_value"][2] > stack[0][1]["white_value"][0]
    assert "__curve_points__" in stack[6][1]


def test_sampled_color_board_uses_primary_secondary_and_cdl_controls():
    stats = ColorStats(
        samples=48,
        mean_r=178.0,
        mean_g=188.0,
        mean_b=206.0,
        mean_luma=188.0,
        luma_std=24.0,
        luma_p05=122.0,
        luma_p95=238.0,
        shadow_rgb=(118.0, 126.0, 142.0),
        midtone_rgb=(178.0, 186.0, 202.0),
        highlight_rgb=(232.0, 232.0, 228.0),
        shadow_luma=126.0,
        midtone_luma=186.0,
        highlight_luma=231.0,
        dominant_rgb=((204.0, 210.0, 236.0), (214.0, 190.0, 162.0)),
        warm_ratio=0.08,
        cool_ratio=0.34,
        skin_ratio=0.04,
        mean_saturation=0.16,
        mean_chroma=34.0,
    )
    stack = build_sampled_color_board_stack(stats)
    assert [modifier_type for modifier_type, _settings in stack] == [
        "WHITE_BALANCE",
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "COLOR_BALANCE",
        "CURVES",
        "HUE_CORRECT",
        "TONEMAP",
        "CURVES",
        "HUE_CORRECT",
    ]
    assert stack[3][1]["color_balance.correction_method"] == "OFFSET_POWER_SLOPE"
    assert "__curve_points__" in stack[5][1]
    assert stack[6][1]["intensity"] > 0.0
    assert stack[8][1]["__hue_correct__"]["saturation"] >= 0.45


def test_sampled_color_management_builds_scene_view_profile():
    stats = ColorStats(
        samples=24,
        mean_r=150.0,
        mean_g=165.0,
        mean_b=192.0,
        mean_luma=170.0,
        luma_std=22.0,
        luma_p05=132.0,
        luma_p95=224.0,
        shadow_rgb=(104.0, 116.0, 140.0),
        midtone_rgb=(152.0, 166.0, 192.0),
        highlight_rgb=(214.0, 224.0, 238.0),
        shadow_luma=118.0,
        midtone_luma=168.0,
        highlight_luma=226.0,
        shadow_count=64,
        midtone_count=320,
        highlight_count=128,
        dominant_rgb=((120.0, 150.0, 220.0), (180.0, 190.0, 204.0)),
        warm_ratio=0.08,
        cool_ratio=0.36,
        skin_ratio=0.02,
        mean_saturation=0.22,
        mean_chroma=42.0,
    )
    profile = build_sampled_color_management(stats)
    assert profile.summary.startswith("sampled color management")
    assert profile.view_transform_candidates[0] == "AgX"
    assert "Medium High Contrast" in profile.look_candidates
    assert profile.exposure < 0.0
    assert 0.88 <= profile.gamma <= 1.16
    assert profile.white_balance_temperature > 6500.0
    assert len(profile.curve_points) == 5
    assert profile.curve_points[2][1] < 0.50
    assert profile.sequencer_input == "bt709"


def test_sampled_compositor_grade_builds_node_values():
    stats = ColorStats(
        samples=24,
        mean_r=148.0,
        mean_g=122.0,
        mean_b=96.0,
        mean_luma=126.0,
        luma_std=31.0,
        luma_p05=42.0,
        luma_p95=204.0,
        shadow_rgb=(38.0, 34.0, 30.0),
        midtone_rgb=(126.0, 116.0, 100.0),
        highlight_rgb=(206.0, 188.0, 160.0),
        shadow_luma=35.0,
        midtone_luma=116.0,
        highlight_luma=188.0,
        shadow_count=100,
        midtone_count=320,
        highlight_count=92,
        dominant_rgb=((190.0, 96.0, 42.0), (42.0, 88.0, 170.0)),
        warm_ratio=0.36,
        cool_ratio=0.18,
        skin_ratio=0.09,
        mean_saturation=0.44,
        mean_chroma=72.0,
    )
    profile = build_sampled_compositor_grade(stats)
    assert profile.summary.startswith("sampled compositor grade")
    assert profile.exposure < 0.0
    assert profile.contrast > 0.0
    assert profile.gamma[2] > profile.gamma[0]
    assert 0.78 <= profile.saturation <= 1.18
    assert len(profile.curve_points) == 5
    assert set(profile.hue_curve_points) == {0, 1, 2}
    assert profile.tonemap_gamma > 0.0


def test_color_diagnosis_reports_palette_and_suggested_tools(tmp_path):
    orange = sample_video_color(_make_color_clip(tmp_path / "diagnose_orange.mp4", "orange"), max_samples=6, sample_grid=8)
    diagnosis = diagnose_color(orange)

    assert diagnosis.palette_hex
    assert "Video Toolkit Color Diagnostics" in diagnosis.report
    assert "Suggested native Blender tools" in diagnosis.report
    assert "Temperature Cool" in diagnosis.suggested_tools
    assert diagnosis.summary.startswith("diagnosis")


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
