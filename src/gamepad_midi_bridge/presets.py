"""Preset save/load. Pro feature — gated by license.py at the UI layer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .mapping import Mapping
from .paths import presets_dir


def list_presets() -> List[str]:
    d = presets_dir()
    return sorted(p.stem for p in d.glob("*.json"))


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
