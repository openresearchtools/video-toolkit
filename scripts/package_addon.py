#!/usr/bin/env python3
"""Build a Blender-installable add-on zip."""

from __future__ import annotations

import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> int:
    DIST.mkdir(exist_ok=True)
    target = DIST / "open_research_video_toolkit.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "video_toolkit").rglob("*.py")):
            archive.write(path, path.relative_to(ROOT))
        for name in ("blender_manifest.toml", "README.md", "LICENSE"):
            archive.write(ROOT / name, name)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

