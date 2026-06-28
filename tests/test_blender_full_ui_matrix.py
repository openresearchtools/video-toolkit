from pathlib import Path
import json
import subprocess

import pytest


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
    assert "# Open Research Video Toolkit Full UI Matrix" in markdown
    assert "Translated Color Workflow" in markdown
    assert "Preview Pixel Proof" in markdown
