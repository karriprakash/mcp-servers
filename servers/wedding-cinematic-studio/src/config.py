"""Paths and settings shared by every module."""
from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path(os.environ.get("WEDDING_STUDIO_HOME", "~/.wedding_studio")).expanduser()
TEMPLATES_DIR = HOME / "templates"
PROJECTS_DIR = HOME / "projects"
OUTPUT_DIR = HOME / "outputs"

# Templates that ship with the repo (read-only); user templates live in TEMPLATES_DIR.
BUILTIN_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

VEO_MODEL = os.environ.get("VEO_MODEL", "veo-3.1-generate-preview")


def ensure_dirs() -> None:
    for d in (TEMPLATES_DIR, PROJECTS_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: dict) -> None:
    """Write via a temp name and rename, so a stopped process never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
