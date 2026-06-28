#!/usr/bin/env python3
"""Build before/after visual review pages from real-video matrix evidence."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-report", type=Path, required=True)
    parser.add_argument("--compositor-report", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    matrix_report = json.loads(args.matrix_report.read_text(encoding="utf-8"))
    output_dir = args.output_dir or (args.matrix_report.parent / "visual_inspection")
    output_dir.mkdir(parents=True, exist_ok=True)

    font = _font(13)
    small = _font(11)
    source_png = output_dir / "source_frame.png"
    _extract_frame(Path(matrix_report["source_video"]), source_png)

    summary: list[str] = []
    summary.append("# Visual Inspection Evidence")
    summary.append("")
    summary.append(f"- Matrix report: `{args.matrix_report.resolve()}`")
    summary.append(f"- Source video: `{matrix_report['source_video']}`")

    live_pages = _build_live_pages(matrix_report, source_png, output_dir, font, small)
    summary.append(f"- Live sidecar before/after pages: `{len(live_pages)}`")
    for page in live_pages:
        summary.append(f"  - `{page}`")

    rendered_pages = _build_rendered_pages(matrix_report, source_png, output_dir, font, small)
    summary.append(f"- Rendered restoration before/after pages: `{len(rendered_pages)}`")
    for page in rendered_pages:
        summary.append(f"  - `{page}`")

    if args.compositor_report and args.compositor_report.exists():
        compositor_report = json.loads(args.compositor_report.read_text(encoding="utf-8"))
        compositor_pages = _build_compositor_pages(compositor_report, source_png, output_dir, font, small)
        compositor_notes = [
            result for result in compositor_report["results"]
            if result.get("group") == "compositor_visual_snapshot" and result.get("status") == "noted"
        ]
        summary.append(f"- Compositor node output before/after pages: `{len(compositor_pages)}`")
        summary.append(f"- Compositor snapshots rendered: `{compositor_report['passed']}`")
        summary.append(f"- Compositor graph-only notes: `{len(compositor_notes)}`")
        for result in compositor_notes:
            evidence = result.get("evidence") or {}
            summary.append(f"  - `{evidence.get('tool_id')}`: {evidence.get('reason')}")
        for page in compositor_pages:
            summary.append(f"  - `{page}`")
    else:
        summary.append("- Compositor node output before/after pages: `0`")

    summary_path = output_dir / "visual_inspection.md"
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(summary_path)
    return 0


def _font(size: int):
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _extract_frame(video: Path, output: Path) -> None:
    if output.exists() and output.stat().st_size > 0:
        return
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to extract rendered video frames")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-ss",
            "0.5",
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _build_live_pages(report: dict, source_png: Path, output_dir: Path, font, small) -> list[str]:
    results = [
        result for result in report["results"]
        if result.get("group") == "catalog_live_preview_pixels" and result.get("status") == "passed"
    ]
    rows = []
    for result in results:
        evidence = result["evidence"]
        rows.append(
            {
                "tool": evidence["tool_id"],
                "category": evidence["category"],
                "before": Path(evidence["baseline_png"]),
                "after": Path(evidence["after_png"]),
                "meta": f"delta rgb={evidence.get('rgb_delta', 0):.4f} max={evidence.get('max_channel_delta', 0):.4f}",
            }
        )
    return _write_pages(rows, output_dir, "live_sidecar", "Live sidecar VSE modifier output", font, small)


def _build_rendered_pages(report: dict, source_png: Path, output_dir: Path, font, small) -> list[str]:
    frame_dir = output_dir / "rendered_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for result in report["results"]:
        evidence = result.get("evidence") or {}
        if result.get("group") != "catalog_apply_filter" or result.get("status") != "passed" or not evidence.get("output"):
            continue
        frame = frame_dir / f"{evidence['tool_id']}.png"
        _extract_frame(Path(evidence["output"]), frame)
        rows.append(
            {
                "tool": evidence["tool_id"],
                "category": evidence["category"],
                "before": source_png,
                "after": frame,
                "meta": f"bytes={evidence.get('bytes', 0)}",
            }
        )
    return _write_pages(rows, output_dir, "rendered_restoration", "Rendered restoration/video output", font, small)


def _build_compositor_pages(report: dict, source_png: Path, output_dir: Path, font, small) -> list[str]:
    rows = []
    for result in report["results"]:
        evidence = result.get("evidence") or {}
        if result.get("group") != "compositor_visual_snapshot" or result.get("status") != "passed":
            continue
        png = Path(evidence["png"])
        rows.append(
            {
                "tool": evidence["tool_id"],
                "category": evidence["category"],
                "before": source_png,
                "after": png,
                "meta": f"nodes={evidence.get('node_count', 0)} delta={_image_delta(source_png, png):.4f}",
            }
        )
    return _write_pages(rows, output_dir, "compositor_nodes", "Compositor node rendered output", font, small)


def _write_pages(rows: list[dict], output_dir: Path, stem: str, title: str, font, small) -> list[str]:
    if not rows:
        return []
    pages: list[str] = []
    per_page = 12
    thumb = (160, 90)
    label_h = 52
    gutter = 18
    block_w = thumb[0] * 2 + gutter
    block_h = thumb[1] + label_h + 16
    cols = 2
    header_h = 44
    page_w = cols * block_w + (cols + 1) * gutter
    page_h = header_h + math.ceil(per_page / cols) * block_h + gutter

    for page_index, start in enumerate(range(0, len(rows), per_page), start=1):
        page_rows = rows[start:start + per_page]
        canvas = Image.new("RGB", (page_w, page_h), (245, 246, 248))
        draw = ImageDraw.Draw(canvas)
        draw.text((gutter, 14), f"{title} - page {page_index}", fill=(20, 24, 31), font=font)
        for local_index, row in enumerate(page_rows):
            col = local_index % cols
            row_i = local_index // cols
            x = gutter + col * (block_w + gutter)
            y = header_h + row_i * block_h
            before = _thumb(row["before"], thumb)
            after = _thumb(row["after"], thumb)
            canvas.paste(before, (x, y))
            canvas.paste(after, (x + thumb[0] + gutter, y))
            draw.rectangle((x, y, x + thumb[0] - 1, y + thumb[1] - 1), outline=(124, 132, 145))
            draw.rectangle(
                (x + thumb[0] + gutter, y, x + thumb[0] * 2 + gutter - 1, y + thumb[1] - 1),
                outline=(124, 132, 145),
            )
            draw.text((x, y + thumb[1] + 4), _clip(row["tool"], 42), fill=(16, 20, 28), font=font)
            draw.text((x, y + thumb[1] + 22), _clip(row["category"], 46), fill=(72, 80, 94), font=small)
            draw.text((x, y + thumb[1] + 38), _clip(row["meta"], 56), fill=(72, 80, 94), font=small)
            draw.text((x, y - 14), "before", fill=(72, 80, 94), font=small)
            draw.text((x + thumb[0] + gutter, y - 14), "after", fill=(72, 80, 94), font=small)
        path = output_dir / f"{stem}_page_{page_index:02d}.png"
        canvas.save(path)
        pages.append(str(path))
    return pages


def _thumb(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (0, 0, 0))
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def _clip(value: object, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _image_delta(before: Path, after: Path) -> float:
    left = Image.open(before).convert("RGB").resize((160, 90))
    right = Image.open(after).convert("RGB").resize((160, 90))
    diff = ImageStat.Stat(Image.blend(left, right, 0.5))
    a = ImageStat.Stat(left).mean
    b = ImageStat.Stat(right).mean
    _ = diff
    return sum(abs(x - y) for x, y in zip(a, b)) / (255.0 * 3.0)


if __name__ == "__main__":
    raise SystemExit(main())
