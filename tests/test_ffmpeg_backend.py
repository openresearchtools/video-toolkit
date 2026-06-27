import shutil
import subprocess
from pathlib import Path

import pytest

from video_toolkit.catalog import get_tool
from video_toolkit.ffmpeg_backend import (
    build_ffmpeg_command,
    build_vidstab_detect_command,
    probe_video,
    process_video,
)


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required for video processing tests",
)


def _make_real_mp4(path: Path, *, duration: float = 1.0, size: str = "96x64") -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate=12:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


def test_probe_video_reads_real_mp4(tmp_path):
    source = _make_real_mp4(tmp_path / "source.mp4")
    info = probe_video(source)
    assert info.width == 96
    assert info.height == 64
    assert info.duration and info.duration > 0
    assert info.codec == "h264"


def test_build_ffmpeg_command_uses_selected_filter(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    tool = get_tool("deflicker_normalize")
    command = build_ffmpeg_command(source, output, tool, crf=23, preset="veryfast")
    assert "-vf" in command
    assert tool.ffmpeg_filter in command
    assert command[-1] == str(output)


def test_build_vidstab_detect_command_points_to_transform_file(tmp_path):
    command = build_vidstab_detect_command(tmp_path / "source.mp4", tmp_path / "motion.trf")
    assert any("vidstabdetect" in part for part in command)
    assert any("motion.trf" in part for part in command)


@pytest.mark.parametrize(
    "tool_id",
    ["deflicker_normalize", "denoise_light", "deinterlace", "quick_deshake"],
)
def test_process_fast_filters_on_real_mp4(tmp_path, tool_id):
    source = _make_real_mp4(tmp_path / f"{tool_id}_source.mp4", duration=0.75)
    output = tmp_path / f"{tool_id}_output.mp4"
    process_video(tool_id, source, output, crf=30, preset="veryfast")
    info = probe_video(output)
    assert output.exists()
    assert info.width == 96
    assert info.height == 64


def test_process_two_pass_stabilize_on_real_mp4(tmp_path):
    source = _make_real_mp4(tmp_path / "stabilize_source.mp4", duration=0.75)
    output = tmp_path / "stabilize_output.mp4"
    process_video("stabilize", source, output, crf=30, preset="veryfast", work_dir=tmp_path)
    assert output.exists()
    assert (tmp_path / "stabilize_output.trf").exists()
    info = probe_video(output)
    assert info.width == 96
    assert info.height == 64
