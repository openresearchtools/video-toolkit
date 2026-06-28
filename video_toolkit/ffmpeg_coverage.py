"""Coverage helpers for locally installed FFmpeg filters."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from shutil import which


@dataclass(frozen=True)
class FFmpegFilterInfo:
    name: str
    inputs: str
    outputs: str
    description: str

    @property
    def is_video(self) -> bool:
        return "V" in self.inputs or "V" in self.outputs


@dataclass(frozen=True)
class FFmpegVideoCoverage:
    installed_video_filters: tuple[str, ...]
    covered_video_filters: tuple[str, ...]
    missing_video_filters: tuple[str, ...]
    unavailable_reason: str = ""

    @property
    def available(self) -> bool:
        return not self.unavailable_reason

    @property
    def total_video_filters(self) -> int:
        return len(self.installed_video_filters)


def parse_ffmpeg_filters_table(output: str) -> tuple[FFmpegFilterInfo, ...]:
    """Parse `ffmpeg -filters` output across two- and three-flag builds."""

    filters: list[FFmpegFilterInfo] = []
    for line in output.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        flags, name, route = parts[:3]
        if not flags or any(char not in ".TSC" for char in flags):
            continue
        if "->" not in route:
            continue
        inputs, outputs = route.split("->", 1)
        description = parts[3] if len(parts) > 3 else ""
        filters.append(FFmpegFilterInfo(name=name, inputs=inputs, outputs=outputs, description=description))
    return tuple(filters)


def installed_ffmpeg_filters(ffmpeg: str = "ffmpeg") -> tuple[FFmpegFilterInfo, ...]:
    """Return the filters reported by a local FFmpeg binary."""

    executable = which(ffmpeg) or ffmpeg
    result = subprocess.run(
        [executable, "-hide_banner", "-filters"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise RuntimeError(message or f"{ffmpeg} -filters failed")
    return parse_ffmpeg_filters_table(result.stdout + "\n" + result.stderr)


def installed_ffmpeg_video_filter_coverage(
    covered_filters: tuple[str, ...] | set[str],
    *,
    ffmpeg: str = "ffmpeg",
) -> FFmpegVideoCoverage:
    """Compare local FFmpeg video filters with the toolkit's covered filter ids."""

    try:
        filters = installed_ffmpeg_filters(ffmpeg)
    except Exception as exc:  # pragma: no cover - depends on host install
        return FFmpegVideoCoverage((), (), (), str(exc))
    installed = tuple(sorted({info.name for info in filters if info.is_video}))
    covered = set(covered_filters)
    covered_installed = tuple(name for name in installed if name in covered)
    missing = tuple(name for name in installed if name not in covered)
    return FFmpegVideoCoverage(installed, covered_installed, missing)
