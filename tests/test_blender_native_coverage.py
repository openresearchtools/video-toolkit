import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))


@pytest.mark.skipif(not BLENDER.exists(), reason="local Blender build is required for native coverage test")
def test_native_blender_color_surface_is_covered():
    subprocess.run(
        ["python3", "scripts/blender_native_coverage.py"],
        cwd=ROOT,
        check=True,
    )

