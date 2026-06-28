from pathlib import Path
import json
import subprocess

import pytest

from video_toolkit.catalog import blender_modifier_tools


BLENDER = Path(".local/blender/blender")
REPORT = Path("tests/output/full_ui_matrix/report.json")
MARKDOWN_REPORT = Path("tests/output/full_ui_matrix/report.md")


def _passed_results(report, group):
    return [
        result
        for result in report["results"]
        if result["group"] == group and result["status"] == "passed"
    ]


def _assert_selected_target(evidence, target_strip):
    assert evidence["selected_strip"] == target_strip
    assert evidence["active_strip"] == target_strip
    assert evidence["target_strip_selected"] is True
    assert target_strip in evidence["selected_strips"]
    assert Path(evidence["real_video_filepath"]).exists()


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
    assert report["target_strip"] == "UI MATRIX TARGET REAL VIDEO"
    assert report["reference_strip"] == "UI MATRIX REFERENCE REAL VIDEO"
    assert Path(report["target_filepath"]).exists()
    assert report["sidecar_apply_checked_tools"] == report["total_catalog_tools"]
    assert report["sidecar_apply_checked_tools"] == sum(
        1 for result in report["results"] if result["group"] == "sidecar_apply_tool"
    )
    assert report["live_preview_checked_tools"] == len(blender_modifier_tools())
    assert report["live_preview_checked_tools"] == sum(
        1 for result in report["results"] if result["group"] == "catalog_live_preview_pixels"
    )
    assert report["live_preview_pixel_tools"] > 0
    assert report["live_preview_structural_tools"] > 0
    assert "# Open Research Video Toolkit Full UI Matrix" in markdown
    assert "Real Sequencer Strip Proof" in markdown
    assert "Sidecar Every Tool Proof" in markdown
    assert "Translated Color Workflow" in markdown
    assert "Preview Pixel Proof" in markdown
    assert "Live Tool Preview Pixel Proof" in markdown

    target_strip = report["target_strip"]

    catalog_apply = _passed_results(report, "catalog_apply_filter")
    assert len(catalog_apply) == report["total_catalog_tools"]
    for result in catalog_apply:
        evidence = result["evidence"]
        _assert_selected_target(evidence, target_strip)
        if evidence.get("output"):
            assert Path(evidence["output"]).exists()
            assert evidence["bytes"] > 0
        elif evidence.get("modifier_count"):
            assert evidence["modifier_count"] > 0
            assert evidence["live_sequencer_strip"] == target_strip
        else:
            assert evidence["node_count"] > 0
            assert evidence["node_types"]

    sidecar_apply = _passed_results(report, "sidecar_apply_tool")
    assert len(sidecar_apply) == report["total_catalog_tools"]
    for result in sidecar_apply:
        evidence = result["evidence"]
        _assert_selected_target(evidence, target_strip)
        assert evidence["sidecar_tool"] == evidence["tool_id"]
        assert evidence["applied_via"] == "video_toolkit.apply_sidecar_tool"
        if evidence.get("output"):
            assert Path(evidence["output"]).exists()
            assert evidence["bytes"] > 0
        elif evidence.get("modifier_count"):
            assert evidence["modifier_count"] > 0
            assert evidence["live_sequencer_strip"] == target_strip
        else:
            assert evidence["node_count"] > 0
            assert evidence["node_types"]

    live_previews = _passed_results(report, "catalog_live_preview_pixels")
    assert len(live_previews) == report["live_preview_checked_tools"]
    for result in live_previews:
        evidence = result["evidence"]
        _assert_selected_target(evidence, target_strip)
        assert evidence["sidecar_tool"] == evidence["tool_id"]
        assert evidence["applied_via"] == "video_toolkit.apply_sidecar_tool"
        assert evidence["modifier_count"] > 0
        assert Path(evidence["baseline_png"]).exists()
        assert Path(evidence["after_png"]).exists()
        assert evidence["after"]["pixels"] > 0
        if evidence["visual_requirement"] == "pixel_delta":
            assert evidence["max_channel_delta"] > 0.00002 or evidence["rgb_delta"] > 0.00005
        else:
            assert evidence["visual_requirement"] == "structural_only"

    catalog_nodes = _passed_results(report, "catalog_tool_nodes")
    assert len(catalog_nodes) == report["compositor_compatible_catalog_tools"]
    for result in catalog_nodes:
        evidence = result["evidence"]
        _assert_selected_target(evidence, target_strip)
        assert evidence["count"] > 0
        assert evidence["types"]

    for group in ("sidecar_apply", "sidecar_nodes", "preview_pixels", "compositor_stack_operators"):
        for result in _passed_results(report, group):
            evidence = result["evidence"]
            _assert_selected_target(evidence, target_strip)

    for result in _passed_results(report, "workflow_operators"):
        if result["name"] == "write_catalog_coverage_report":
            continue
        _assert_selected_target(result["evidence"], target_strip)

    assert report["selected_strip_evidence_checks"] >= (
        len(catalog_apply)
        + len(sidecar_apply)
        + len(live_previews)
        + len(catalog_nodes)
        + len(_passed_results(report, "sidecar_apply"))
        + len(_passed_results(report, "sidecar_nodes"))
        + len(_passed_results(report, "preview_pixels"))
    )
