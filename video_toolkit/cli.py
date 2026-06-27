"""Command line access to the Video Toolkit processing catalog."""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import categories, get_tool, all_tools
from .ffmpeg_backend import FFmpegError, process_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video-toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available one-click video tools.")

    apply_parser = subparsers.add_parser("apply", help="Apply an FFmpeg-backed tool to a video.")
    apply_parser.add_argument("tool_id", help="Tool id from `video-toolkit list`.")
    apply_parser.add_argument("input", type=Path, help="Input video.")
    apply_parser.add_argument("output", type=Path, help="Output video.")
    apply_parser.add_argument("--crf", type=int, default=18, help="x264 CRF, lower is higher quality.")
    apply_parser.add_argument("--preset", default="medium", help="x264 preset.")
    apply_parser.add_argument("--no-audio", action="store_true", help="Drop audio from output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        _print_tools()
        return 0
    if args.command == "apply":
        try:
            tool = get_tool(args.tool_id)
            if not tool.is_ffmpeg:
                parser.error(f"{args.tool_id} is a Blender VSE modifier and must be used inside Blender")
            process_video(
                args.tool_id,
                args.input,
                args.output,
                crf=args.crf,
                preset=args.preset,
                keep_audio=not args.no_audio,
            )
        except (KeyError, FFmpegError) as exc:
            parser.exit(2, f"video-toolkit: {exc}\n")
        print(args.output)
        return 0
    parser.error("unknown command")
    return 2


def _print_tools() -> None:
    tools = all_tools()
    for category in categories(tools):
        print(f"{category}:")
        for tool in tools:
            if tool.category != category:
                continue
            engine = "Blender" if tool.is_blender_modifier else "FFmpeg"
            slow = " slow" if tool.slow else ""
            print(f"  {tool.id:<22} {engine}{slow:<6} {tool.label}")


if __name__ == "__main__":
    raise SystemExit(main())

