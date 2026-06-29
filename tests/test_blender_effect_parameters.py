import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))


@pytest.mark.skipif(not BLENDER.exists(), reason="local Blender build is required for effect parameter smoke test")
def test_effect_parameters_and_node_section_on_real_video():
    subprocess.run(
        ["python3", "scripts/end_user_effect_parameter_smoke.py"],
        cwd=ROOT,
        check=True,
    )
