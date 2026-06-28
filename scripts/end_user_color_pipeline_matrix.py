#!/usr/bin/env python3
"""Verify native color-management pipeline tools on real video in Blender."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

from end_user_blender_preview_test import BLENDER, DEFAULT_VIDEO, ROOT, _ensure_real_video, _probe
from end_user_full_ui_operator_matrix import _make_matrix_source


DEFAULT_OUTPUT = ROOT / "tests" / "output" / "color_pipeline_matrix"
PIPELINE_TOOL_IDS = (
    "native_colorspace_bt709_full_pipeline",
    "native_colorspace_bt709_to_bt2020_pipeline",
    "native_colorspace_srgb_review_pipeline",
    "native_colormatrix_601_to_709_pipeline",
    "native_colormatrix_709_to_2020_pipeline",
    "native_setparams_rec2020_pq_pipeline",
    "native_setrange_full_pipeline",
    "native_setrange_limited_pipeline",
    "native_zscale_709_to_2020_hdr_pipeline",
    "native_ffmpeg_color_metadata_pipeline",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frame", type=int, default=6)
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required for the color pipeline matrix")

    original_video = _ensure_real_video(args.video)
    _probe(original_video)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_video = _make_matrix_source(original_video, output_dir / "matrix_source.mp4")

    script = _blender_script(original_video, matrix_video, output_dir, args.frame)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        result = subprocess.run(
            [str(BLENDER), "--background", "--factory-startup", "--python", str(script_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        blender_output = result.stdout + result.stderr
        if result.returncode != 0 or "Traceback (most recent call last):" in blender_output or "AssertionError" in blender_output:
            return result.returncode or 1
    finally:
        script_path.unlink(missing_ok=True)

    report_path = output_dir / "color_pipeline_report.json"
    _convert_exrs(report_path)
    _build_contact_sheet(report_path, output_dir)
    print(output_dir / "color_pipeline_visual_inspection.md")
    print(report_path)
    return 0


def _blender_script(original_video: Path, video: Path, output_dir: Path, frame: int) -> str:
    template = r'''
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__ROOT__)
ORIGINAL_VIDEO = Path(__ORIGINAL_VIDEO__)
VIDEO = Path(__VIDEO__)
OUTPUT_DIR = Path(__OUTPUT_DIR__)
FRAME = __FRAME__
TOOL_IDS = __TOOL_IDS__
EXR_DIR = OUTPUT_DIR / "color_pipeline_exr"
REPORT_PATH = OUTPUT_DIR / "color_pipeline_report.json"

sys.path.insert(0, str(ROOT))

import bpy
import video_toolkit
from video_toolkit.catalog import get_tool

video_toolkit.register()

EXR_DIR.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.sequence_editor_create()
editor = scene.sequence_editor
scene.frame_start = 1
scene.frame_end = 15
scene.frame_set(FRAME)
scene.render.resolution_x = 160
scene.render.resolution_y = 90
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.use_sequencer = False
if hasattr(scene.render, "use_compositing"):
    scene.render.use_compositing = True

target_strip = editor.strips.new_movie(
    name="COLOR PIPELINE TARGET REAL VIDEO",
    filepath=str(VIDEO),
    channel=1,
    frame_start=1,
)
editor.active_strip = target_strip
target_strip.select = True


def tree_or_none():
    if hasattr(scene, "compositing_node_group") and scene.compositing_node_group is not None:
        return scene.compositing_node_group
    return getattr(scene, "node_tree", None)


def tree():
    current = tree_or_none()
    if current is None:
        raise RuntimeError("This Blender build does not expose a compositor node tree")
    return current


def clear_toolkit_nodes():
    current = tree_or_none()
    if current is None:
        return
    for node in list(current.nodes):
        if getattr(node, "name", "").startswith("VTK "):
            current.nodes.remove(node)


def select_target():
    for candidate in editor.strips_all:
        candidate.select = False
    target_strip.select = True
    editor.active_strip = target_strip
    scene.sequence_editor.active_strip = target_strip


def configure_output_node(current_tree, tool_id):
    output = next(
        (
            node for node in current_tree.nodes
            if node.bl_idname == "CompositorNodeOutputFile"
            and getattr(node, "name", "").startswith("VTK ")
        ),
        None,
    )
    if output is None:
        raise RuntimeError("no VTK Output File node was created")
    source_socket = next((socket.links[0].from_socket for socket in output.inputs if socket.links), None)
    if source_socket is None:
        raise RuntimeError("VTK Output File node has no linked processed input")
    if hasattr(output, "file_output_items"):
        output.file_output_items.clear()
        output.file_output_items.new(socket_type="RGBA", name="Image")
        current_tree.links.new(source_socket, output.inputs[0])
    if hasattr(output, "directory"):
        output.directory = str(EXR_DIR)
    if hasattr(output, "base_path"):
        output.base_path = str(EXR_DIR)
    if hasattr(output, "file_name"):
        output.file_name = tool_id
    if hasattr(output, "save_as_render"):
        output.save_as_render = True
    if hasattr(output, "use_file_extension"):
        output.use_file_extension = True


def render_tool(tool_id):
    configure_output_node(tree(), tool_id)
    scene.render.filepath = str(OUTPUT_DIR / f"{tool_id}.png")
    scene.frame_set(FRAME)
    bpy.ops.render.render(write_still=True)
    direct = EXR_DIR / f"{tool_id}.exr"
    if direct.exists() and direct.stat().st_size > 0:
        return direct
    matches = sorted(EXR_DIR.glob(f"{tool_id}*.exr"))
    if matches:
        return matches[-1]
    raise RuntimeError(f"no compositor EXR emitted for {tool_id}")


def selected_evidence():
    selected = [strip.name for strip in editor.strips_all if strip.select]
    return {
        "selected_strip": target_strip.name,
        "active_strip": editor.active_strip.name if editor.active_strip else None,
        "target_strip_selected": bool(target_strip.select),
        "selected_strips": selected,
        "strip_filepath": target_strip.filepath,
        "real_video_filepath": str(VIDEO),
    }


results = []
failures = []
for tool_id in TOOL_IDS:
    try:
        clear_toolkit_nodes()
        select_target()
        tool = get_tool(tool_id)
        result = bpy.ops.video_toolkit.apply_filter(filter_id=tool_id)
        if result != {"FINISHED"}:
            raise RuntimeError(f"apply_filter returned {result}")
        current_tree = tree()
        nodes = [
            node for node in current_tree.nodes
            if node.get("video_toolkit_filter_id") == tool_id
        ]
        if not nodes:
            raise RuntimeError("no VTK nodes were stamped with the pipeline tool id")
        color_pairs = dict(tool.color_management)
        for key, value in color_pairs.items():
            scene_key = f"video_toolkit_color_management_{key}"
            if scene.get(scene_key) != value:
                raise AssertionError(f"{scene_key}={scene.get(scene_key)!r}, expected {value!r}")
        if color_pairs and not any(node.get("video_toolkit_color_management") for node in nodes):
            raise AssertionError("pipeline nodes were not stamped with color-management metadata")
        exr = render_tool(tool_id)
        evidence = {
            "tool_id": tool.id,
            "label": tool.label,
            "category": tool.category,
            "color_management": tool.color_management,
            "scene_color_management": {key: scene.get(f"video_toolkit_color_management_{key}") for key in color_pairs},
            "last_color_management": scene.video_toolkit_last_color_management,
            "last_compositor_nodes": scene.video_toolkit_last_compositor_nodes,
            "node_count": len(nodes),
            "node_types": sorted({node.bl_idname for node in nodes}),
            "node_color_management": nodes[0].get("video_toolkit_color_management", ""),
            "exr": str(exr),
            "png": str(exr.with_suffix(".png")),
            "frame": FRAME,
            **selected_evidence(),
        }
        results.append({"name": tool_id, "group": "color_pipeline_tool", "status": "passed", "evidence": evidence})
        print(f"PASS color_pipeline_tool: {tool_id}")
    except Exception as exc:
        traceback.print_exc()
        failure = {
            "name": tool_id,
            "group": "color_pipeline_tool",
            "status": "failed",
            "evidence": {"error": str(exc), "traceback": traceback.format_exc(limit=8), **selected_evidence()},
        }
        results.append(failure)
        failures.append(failure)
        print(f"FAIL color_pipeline_tool: {tool_id}: {exc}")

report = {
    "original_video": str(ORIGINAL_VIDEO),
    "source_video": str(VIDEO),
    "target_strip": target_strip.name,
    "target_filepath": str(VIDEO),
    "frame": FRAME,
    "total_tools": len(TOOL_IDS),
    "passed": sum(1 for result in results if result["status"] == "passed"),
    "failed": len(failures),
    "results": results,
    "failures": failures,
}
REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

video_toolkit.unregister()

if failures:
    raise SystemExit(f"{len(failures)} color pipeline failures; see {REPORT_PATH}")
print(json.dumps({"report": str(REPORT_PATH), "passed": report["passed"], "failed": report["failed"]}, indent=2))
'''
    return (
        template.replace("__ROOT__", repr(str(ROOT)))
        .replace("__ORIGINAL_VIDEO__", repr(str(original_video)))
        .replace("__VIDEO__", repr(str(video)))
        .replace("__OUTPUT_DIR__", repr(str(output_dir)))
        .replace("__FRAME__", str(frame))
        .replace("__TOOL_IDS__", repr(tuple(PIPELINE_TOOL_IDS)))
    )


def _convert_exrs(report_path: Path) -> None:
    script = r'''
import json
from pathlib import Path

import OpenEXR
import numpy as np
from PIL import Image

REPORT_PATH = Path(__REPORT_PATH__)
report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
converted = 0
for result in report["results"]:
    if result.get("status") != "passed":
        continue
    evidence = result.get("evidence") or {}
    exr = Path(evidence["exr"])
    png = Path(evidence["png"])
    exr_file = OpenEXR.File(str(exr))
    pixels = exr_file.parts[0].channels["Image"].pixels
    rgb = np.nan_to_num(pixels[..., :3], nan=0.0, posinf=1.0, neginf=0.0)
    rgb = np.clip(rgb, 0.0, 1.0)
    arr = (rgb * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(png)
    evidence["bytes"] = png.stat().st_size
    converted += 1
report["converted_pngs"] = converted
REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"report": str(REPORT_PATH), "converted_pngs": converted}, indent=2))
'''
    converter_python = ROOT / ".venv" / "bin" / "python"
    if not converter_python.exists():
        converter_python = Path(sys.executable)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script.replace("__REPORT_PATH__", repr(str(report_path))))
        script_path = Path(handle.name)
    try:
        subprocess.run([str(converter_python), str(script_path)], cwd=ROOT, check=True)
    finally:
        script_path.unlink(missing_ok=True)


def _build_contact_sheet(report_path: Path, output_dir: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    source_png = output_dir / "source_frame.png"
    _extract_frame(Path(report["source_video"]), source_png)
    rows = []
    for result in report["results"]:
        evidence = result.get("evidence") or {}
        if result.get("status") != "passed":
            continue
        png = Path(evidence["png"])
        rows.append(
            {
                "tool": evidence["tool_id"],
                "before": source_png,
                "after": png,
                "meta": f"nodes={evidence.get('node_count', 0)} delta={_image_delta(source_png, png):.4f}",
            }
        )
    contact = output_dir / "color_pipeline_contact_sheet.png"
    _write_contact_sheet(rows, contact)
    summary = [
        "# Color Pipeline Matrix",
        "",
        f"- Original real video: `{report['original_video']}`",
        f"- Blender matrix source: `{report['source_video']}`",
        f"- JSON evidence: `{report_path.resolve()}`",
        f"- Passed tools: `{report['passed']}`",
        f"- Failed tools: `{report['failed']}`",
        f"- Converted PNGs: `{report.get('converted_pngs', 0)}`",
        f"- Contact sheet: `{contact}`",
    ]
    if report.get("failures"):
        summary.extend(["", "## Failures", ""])
        for failure in report["failures"]:
            summary.append(f"- `{failure['name']}`: {(failure.get('evidence') or {}).get('error')}")
    else:
        summary.extend(["", "## Failures", "", "None."])
    (output_dir / "color_pipeline_visual_inspection.md").write_text("\n".join(summary) + "\n", encoding="utf-8")


def _extract_frame(video: Path, output: Path) -> None:
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


def _write_contact_sheet(rows: list[dict], path: Path) -> None:
    font = _font(13)
    small = _font(11)
    thumb = (176, 99)
    gutter = 18
    label_h = 58
    cols = 2
    block_w = thumb[0] * 2 + gutter
    block_h = thumb[1] + label_h + 16
    header_h = 44
    page_w = cols * block_w + (cols + 1) * gutter
    page_h = header_h + ((len(rows) + cols - 1) // cols) * block_h + gutter
    canvas = Image.new("RGB", (page_w, page_h), (245, 246, 248))
    draw = ImageDraw.Draw(canvas)
    draw.text((gutter, 14), "Native color pipeline tools - real video before/after", fill=(20, 24, 31), font=font)
    for index, row in enumerate(rows):
        col = index % cols
        row_i = index // cols
        x = gutter + col * (block_w + gutter)
        y = header_h + row_i * block_h
        before = _thumb(row["before"], thumb)
        after = _thumb(row["after"], thumb)
        canvas.paste(before, (x, y))
        canvas.paste(after, (x + thumb[0] + gutter, y))
        draw.text((x, y - 14), "before", fill=(72, 80, 94), font=small)
        draw.text((x + thumb[0] + gutter, y - 14), "after", fill=(72, 80, 94), font=small)
        draw.rectangle((x, y, x + thumb[0] - 1, y + thumb[1] - 1), outline=(124, 132, 145))
        draw.rectangle(
            (x + thumb[0] + gutter, y, x + thumb[0] * 2 + gutter - 1, y + thumb[1] - 1),
            outline=(124, 132, 145),
        )
        draw.text((x, y + thumb[1] + 4), _clip(row["tool"], 46), fill=(16, 20, 28), font=font)
        draw.text((x, y + thumb[1] + 24), _clip(row["meta"], 56), fill=(72, 80, 94), font=small)
    canvas.save(path)


def _thumb(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (0, 0, 0))
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def _font(size: int):
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _image_delta(before: Path, after: Path) -> float:
    left = Image.open(before).convert("RGB").resize((160, 90))
    right = Image.open(after).convert("RGB").resize((160, 90))
    a = ImageStat.Stat(left).mean
    b = ImageStat.Stat(right).mean
    return sum(abs(x - y) for x, y in zip(a, b)) / (255.0 * 3.0)


def _clip(value: object, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
