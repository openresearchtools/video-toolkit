from pathlib import Path
import json
import subprocess

import pytest

from video_toolkit.catalog import blender_modifier_tools


BLENDER = Path(".local/blender/blender")
REPORT = Path("tests/output/full_ui_matrix/report.json")
MARKDOWN_REPORT = Path("tests/output/full_ui_matrix/report.md")


@pytest.mark.skipif(not BLENDER.exists(), reason="local Blender build is required for full UI operator matrix")
def test_full_ui_operator_matrix_on_real_video():
    subprocess.run(
        ["python3", "scripts/end_user_full_ui_operator_matrix.py"],
        check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    markdown = MARKDOWN_REPORT.read_text(encoding="utf-8")

    assert report["failed"] == 0
    assert report["passed"] > 0
    assert report["markdown_report"] == str(MARKDOWN_REPORT.resolve())
    assert report["live_preview_checked_tools"] == len(blender_modifier_tools())
    assert report["live_preview_checked_tools"] == sum(
        1 for result in report["results"] if result["group"] == "catalog_live_preview_pixels"
    )
    assert report["live_preview_pixel_tools"] > 0
    assert report["live_preview_structural_tools"] > 0
    assert "# Open Research Video Toolkit Full UI Matrix" in markdown
    assert "Translated Color Workflow" in markdown
    assert "Preview Pixel Proof" in markdown
    assert "Live Tool Preview Pixel Proof" in markdown
