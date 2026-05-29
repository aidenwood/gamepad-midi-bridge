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
    """List all presets (including nested ones in subdirs) as relative slugs.

    Returns paths like "preset_name" for top-level or "folder/preset_name" for nested.
    """
    d = presets_dir()
    presets = []
    # Top-level presets
    for p in d.glob("*.json"):
        presets.append(p.stem)
    # Nested presets in subdirectories
    for subdir in d.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            for p in subdir.glob("*.json"):
                # Return relative path from presets_dir (e.g., "Live/intro")
                rel = p.relative_to(d)
                presets.append(rel.with_suffix("").as_posix())
    return sorted(presets)


def list_categories() -> List[str]:
    """Return top-level folder names in the presets directory."""
    d = presets_dir()
    categories = []
    for subdir in d.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            categories.append(subdir.name)
    return sorted(categories)


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
    """Load preset by name. Supports both top-level and nested paths (e.g., "folder/preset")."""
    d = presets_dir()
    parts = name.split("/")
    path = d / Path(*parts).with_suffix(".json")
    with path.open("r", encoding="utf-8") as f:
        return Mapping.from_dict(json.load(f))


def save_preset(mapping: Mapping) -> Path:
    """Save preset. If mapping.name contains '/', create nested structure."""
    d = presets_dir()
    parts = mapping.name.split("/")
    if len(parts) > 1:
        # Nested preset
        subdir = d / Path(*parts[:-1])
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / f"{parts[-1]}.json"
    else:
        # Top-level preset
        path = d / f"{mapping.name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(mapping.to_dict(), f, indent=2)
    return path


def delete_preset(name: str) -> None:
    """Delete preset. Supports both top-level and nested paths."""
    d = presets_dir()
    parts = name.split("/")
    if len(parts) > 1:
        path = d / Path(*parts).with_suffix(".json")
    else:
        path = d / f"{name}.json"
    if path.exists():
        path.unlink()


def move_preset(name: str, folder: str) -> Path:
    """Move a preset to a folder. folder can be empty string for top-level."""
    d = presets_dir()
    # Get the filename (last part)
    filename = name.split("/")[-1]

    # Source path
    parts = name.split("/")
    src = d / Path(*parts).with_suffix(".json")

    # Target path
    if folder:
        target_dir = d / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / f"{filename}.json"
    else:
        dst = d / f"{filename}.json"

    if src.exists():
        src.rename(dst)

    return dst
