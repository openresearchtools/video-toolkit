from pathlib import Path
import subprocess

import pytest


BLENDER = Path(".local/blender/blender")


@pytest.mark.skipif(not BLENDER.exists(), reason="local Blender build is required for full UI operator matrix")
def test_full_ui_operator_matrix_on_real_video():
    subprocess.run(
        ["python3", "scripts/end_user_full_ui_operator_matrix.py"],
        check=True,
    )
