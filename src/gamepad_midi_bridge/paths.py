"""Platform-correct user data directories. No external deps (no platformdirs)
so PyInstaller bundles stay lean.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def user_data_dir() -> Path:
    """Where presets, license keys, and config live."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def presets_dir() -> Path:
    d = user_data_dir() / "presets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def license_path() -> Path:
    return user_data_dir() / "license.key"


def config_path() -> Path:
    return user_data_dir() / "config.json"


def last_mapping_path() -> Path:
    """Where the in-memory mapping is persisted between launches."""
    return user_data_dir() / "last_mapping.json"
