#!/usr/bin/env python3
"""Download and extract the verified Blender 5.2 Beta build used for smoke tests."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLENDER_URL = os.environ.get(
    "BLENDER_URL",
    "https://cdn.builder.blender.org/download/daily/blender-5.2.0-beta%2Bv52.df95c688b71a-linux.x86_64-release.tar.xz",
)
SHA_URL = os.environ.get("BLENDER_SHA256_URL", f"{BLENDER_URL}.sha256")
CACHE_DIR = ROOT / ".cache" / "blender"
INSTALL_DIR = ROOT / ".local" / "blender"


def main() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive = CACHE_DIR / Path(urllib.parse.urlparse(BLENDER_URL).path).name.replace("%2B", "+")
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    _download(BLENDER_URL, archive)
    _download(SHA_URL, checksum)
    _verify(archive, checksum)
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)
    INSTALL_DIR.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        root_prefix = members[0].name.split("/", 1)[0] + "/"
        for member in members:
            if member.name.startswith(root_prefix):
                member.name = member.name[len(root_prefix) :]
            if member.name:
                tar.extract(member, INSTALL_DIR)
    blender = INSTALL_DIR / "blender"
    subprocess.run([str(blender), "--version"], check=True)
    print(blender)
    return 0


def _download(url: str, target: Path) -> None:
    if target.exists() and target.stat().st_size > 0:
        print(f"Using cached {target}")
        return
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _verify(archive: Path, checksum_file: Path) -> None:
    expected = checksum_file.read_text(encoding="utf-8").strip().split()[0]
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected:
        raise SystemExit(f"Checksum mismatch for {archive}: expected {expected}, got {actual}")


if __name__ == "__main__":
    raise SystemExit(main())
