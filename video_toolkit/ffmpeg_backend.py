"""FFmpeg command construction and execution for rendered video tools."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .catalog import VideoTool, get_tool


class FFmpegError(RuntimeError):
    """Raised when FFmpeg or FFprobe fails."""


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: float | None
    frame_rate: float | None
    codec: str | None


def require_executable(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise FFmpegError(f"{name} was not found on PATH")
    return executable


def probe_video(input_path: str | Path) -> VideoInfo:
    ffprobe = require_executable("ffprobe")
    path = Path(input_path)
    if not path.exists():
        raise FFmpegError(f"Input video does not exist: {path}")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,codec_name,avg_frame_rate:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(result.stderr.strip() or "ffprobe failed")
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise FFmpegError(f"No video stream found in {path}")
    stream = streams[0]
    duration_text = (data.get("format") or {}).get("duration")
    frame_rate_text = stream.get("avg_frame_rate")
    return VideoInfo(
        width=int(stream["width"]),
        height=int(stream["height"]),
        duration=float(duration_text) if duration_text else None,
        frame_rate=_parse_frame_rate(frame_rate_text),
        codec=stream.get("codec_name"),
    )


def _parse_frame_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        denominator = float(den)
        if denominator == 0:
            return None
        return float(num) / denominator
    return float(value)


def build_filter_chain(tool: VideoTool, transforms_path: Path | None = None) -> str:
    if tool.two_pass_stabilize:
        if transforms_path is None:
            raise FFmpegError("A transforms path is required for stabilization")
        chain = (
            f"vidstabtransform=input={_escape_filter_path(transforms_path)}:"
            "smoothing=30:zoom=5:optzoom=2:interpol=bicubic"
        )
        if tool.ffmpeg_filter_after_stabilize:
            chain = f"{chain},{tool.ffmpeg_filter_after_stabilize}"
        return chain
    if not tool.ffmpeg_filter:
        raise FFmpegError(f"Tool {tool.id} does not define an FFmpeg filter")
    return tool.ffmpeg_filter


def build_ffmpeg_command(
    input_path: str | Path,
    output_path: str | Path,
    tool: VideoTool,
    *,
    crf: int = 18,
    preset: str = "medium",
    keep_audio: bool = True,
    transforms_path: Path | None = None,
) -> list[str]:
    ffmpeg = require_executable("ffmpeg")
    input_path = Path(input_path)
    output_path = Path(output_path)
    filter_chain = build_filter_chain(tool, transforms_path)
    command = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
    ]
    if keep_audio:
        command += ["-map", "0:a?"]
    command += [
        "-vf",
        filter_chain,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(crf),
        "-preset",
        preset,
    ]
    if keep_audio:
        command += ["-c:a", "aac", "-b:a", "192k"]
    command += ["-movflags", "+faststart", str(output_path)]
    return command


def build_vidstab_detect_command(
    input_path: str | Path,
    transforms_path: str | Path,
    *,
    shakiness: int = 5,
    accuracy: int = 15,
) -> list[str]:
    ffmpeg = require_executable("ffmpeg")
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        (
            f"vidstabdetect=shakiness={shakiness}:accuracy={accuracy}:"
            f"result={_escape_filter_path(Path(transforms_path))}"
        ),
        "-f",
        "null",
        "-",
    ]


def process_video(
    tool_id: str | VideoTool,
    input_path: str | Path,
    output_path: str | Path,
    *,
    crf: int = 18,
    preset: str = "medium",
    keep_audio: bool = True,
    work_dir: str | Path | None = None,
) -> Path:
    tool = tool_id if isinstance(tool_id, VideoTool) else get_tool(tool_id)
    if not tool.is_ffmpeg:
        raise FFmpegError(f"{tool.label} is a Blender VSE modifier, not an FFmpeg render tool")
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    probe_video(input_path)
    transforms_path: Path | None = None
    if tool.two_pass_stabilize:
        work_root = Path(work_dir) if work_dir else output_path.parent
        work_root.mkdir(parents=True, exist_ok=True)
        transforms_path = work_root / f"{output_path.stem}.trf"
        _run(build_vidstab_detect_command(input_path, transforms_path))
    _run(
        build_ffmpeg_command(
            input_path,
            output_path,
            tool,
            crf=crf,
            preset=preset,
            keep_audio=keep_audio,
            transforms_path=transforms_path,
        )
    )
    probe_video(output_path)
    return output_path


def _run(command: list[str]) -> None:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "FFmpeg command failed"
        raise FFmpegError(message)


def _escape_filter_path(path: Path) -> str:
    value = str(path)
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
