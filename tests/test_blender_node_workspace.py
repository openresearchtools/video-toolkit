import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))


@pytest.mark.skipif(
    os.environ.get("VIDEO_TOOLKIT_RUN_WINDOW_TEST") != "1" or not BLENDER.exists(),
    reason="requires an interactive Blender window; set VIDEO_TOOLKIT_RUN_WINDOW_TEST=1",
)
def test_node_tools_open_compositing_workspace_for_selected_strip():
    subprocess.run(
        ["python3", "scripts/end_user_node_workspace_smoke.py"],
        cwd=ROOT,
        check=True,
    )
