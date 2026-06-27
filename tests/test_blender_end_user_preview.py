import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))


@pytest.mark.skipif(not BLENDER.exists(), reason="local Blender build is required for end-user preview test")
def test_end_user_blender_preview_pixels_change_on_real_video():
    subprocess.run(
        ["python3", "scripts/end_user_blender_preview_test.py"],
        cwd=ROOT,
        check=True,
    )

