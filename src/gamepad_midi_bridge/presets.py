"""Preset save/load. Pro feature — gated by license.py at the UI layer.

First launch copies a handful of bundled starter presets into the user
presets dir so the Presets tab has something to show on day one.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Optional

from .mapping import Mapping
from .paths import presets_dir


_BUNDLED_DIR = Path(__file__).parent / "resources" / "presets"
_SEED_MARKER = ".seeded"


def seed_user_presets_once() -> int:
    """Copy bundled presets into the user dir on first launch. Idempotent.

    Returns the number of files copied. Marker file prevents re-seeding so
    a user who deletes a starter preset doesn't get it back next launch.
    """
    target = presets_dir()
    marker = target / _SEED_MARKER
    if marker.exists() or not _BUNDLED_DIR.exists():
        return 0
    copied = 0
    for bundled in _BUNDLED_DIR.glob("*.json"):
        dest = target / bundled.name
        if dest.exists():
            continue
        shutil.copy2(bundled, dest)
        copied += 1
    marker.write_text("", encoding="utf-8")
    return copied


def list_presets() -> List[str]:
    d = presets_dir()
    return sorted(p.stem for p in d.glob("*.json"))


def load_preset_by_slug(slug: str) -> Optional[Mapping]:
    """Load a preset by slug (stem of its JSON filename). Returns None if not found."""
    path = presets_dir() / f"{slug}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return Mapping.from_dict(json.load(f))
    except Exception:
        return None


def load_preset(name: str) -> Mapping:
    path = presets_dir() / f"{name}.json"
    with path.open("r", encoding="utf-8") as f:
        return Mapping.from_dict(json.load(f))


def save_preset(mapping: Mapping) -> Path:
    path = presets_dir() / f"{mapping.name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(mapping.to_dict(), f, indent=2)
    return path


def delete_preset(name: str) -> None:
    path = presets_dir() / f"{name}.json"
    if path.exists():
        path.unlink()
