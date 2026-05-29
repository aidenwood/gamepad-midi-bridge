"""DAW / VJ app detector — pure stdlib, never crashes.

Scans the current platform for known DAW and VJ applications and returns a list
of DetectedApp objects. Results are cached to a JSON file so we don't re-stat
the filesystem on every launch; calling `detect_installed_apps(force=True)` or
`detect_installed_apps()` after the cache is >24 h old triggers a fresh scan.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .paths import user_data_dir

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DetectedApp:
    """One detected host application."""
    name: str               # Human-readable, e.g. "Resolume Arena"
    path: Path              # Detected path to the app / executable
    connector_target: str   # Slug matching the connector registry

    def to_dict(self) -> dict:
        return {"name": self.name, "path": str(self.path),
                "connector_target": self.connector_target}

    @classmethod
    def from_dict(cls, d: dict) -> "DetectedApp":
        return cls(name=d["name"], path=Path(d["path"]),
                   connector_target=d["connector_target"])


# ---------------------------------------------------------------------------
# Platform-specific search tables
# ---------------------------------------------------------------------------

# (glob_pattern, human_name, connector_slug)
_MACOS_APPS: List[tuple[str, str, str]] = [
    ("Ableton Live*.app",   "Ableton Live",      "ableton"),
    ("Resolume Arena.app",  "Resolume Arena",    "resolume"),
    ("Resolume Avenue.app", "Resolume Avenue",   "resolume"),
    ("TouchDesigner.app",   "TouchDesigner",     "touchdesigner"),
    ("REAPER.app",          "REAPER",            "reaper"),
    ("Logic Pro.app",       "Logic Pro",         "ableton"),   # Logic maps to ableton-style MIDI
    ("OBS.app",             "OBS Studio",        "obs"),
    ("MadMapper.app",       "MadMapper",         "madmapper"),
    ("VDMX5.app",           "VDMX5",             "vdmx"),
]

# (folder_name_fragment, human_name, connector_slug) — checked under
# both %ProgramFiles% and %LOCALAPPDATA%\Programs
_WINDOWS_FOLDERS: List[tuple[str, str, str]] = [
    ("Ableton",             "Ableton Live",      "ableton"),
    ("Resolume Arena",      "Resolume Arena",    "resolume"),
    ("Resolume Avenue",     "Resolume Avenue",   "resolume"),
    ("Derivative",          "TouchDesigner",     "touchdesigner"),
    ("REAPER",              "REAPER",            "reaper"),
    ("Logic Pro",           "Logic Pro",         "ableton"),
    ("obs-studio",          "OBS Studio",        "obs"),
    ("MadMapper",           "MadMapper",         "madmapper"),
    ("VDMX",                "VDMX5",             "vdmx"),
]

# (which_name / desktop_keyword, human_name, connector_slug)
_LINUX_WHICH: List[tuple[str, str, str]] = [
    ("ableton",  "Ableton Live",   "ableton"),
    ("reaper",   "REAPER",         "reaper"),
    ("obs",      "OBS Studio",     "obs"),
]
_LINUX_DESKTOP_KEYWORDS: List[tuple[str, str, str]] = [
    ("resolume", "Resolume",       "resolume"),
    ("touchdesigner", "TouchDesigner", "touchdesigner"),
    ("madmapper", "MadMapper",    "madmapper"),
]


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_macos(applications_dir: Optional[Path] = None) -> List[DetectedApp]:
    base = applications_dir or Path("/Applications")
    found: List[DetectedApp] = []
    for glob, name, slug in _MACOS_APPS:
        for match in base.glob(glob):
            if match.exists():
                found.append(DetectedApp(name=name, path=match,
                                         connector_target=slug))
                break  # one entry per app type
    return found


def _detect_windows() -> List[DetectedApp]:
    found: List[DetectedApp] = []
    search_roots: List[Path] = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    search_roots.append(Path(pf))
    search_roots.append(Path(pf86))
    if local:
        search_roots.append(Path(local) / "Programs")

    seen: set[str] = set()
    for root in search_roots:
        if not root.exists():
            continue
        try:
            entries = list(root.iterdir())
        except PermissionError:
            continue
        for fragment, name, slug in _WINDOWS_FOLDERS:
            if name in seen:
                continue
            for entry in entries:
                if fragment.lower() in entry.name.lower() and entry.is_dir():
                    found.append(DetectedApp(name=name, path=entry,
                                             connector_target=slug))
                    seen.add(name)
                    break
    return found


def _detect_linux() -> List[DetectedApp]:
    found: List[DetectedApp] = []

    # which-based check
    for cmd, name, slug in _LINUX_WHICH:
        try:
            result = subprocess.run(
                ["which", cmd], capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                found.append(DetectedApp(name=name,
                                         path=Path(result.stdout.strip()),
                                         connector_target=slug))
        except Exception:
            pass

    # .desktop file scan
    desktop_dir = Path("/usr/share/applications")
    if desktop_dir.exists():
        try:
            desktop_files = list(desktop_dir.glob("*.desktop"))
        except Exception:
            desktop_files = []
        for keyword, name, slug in _LINUX_DESKTOP_KEYWORDS:
            for df in desktop_files:
                if keyword.lower() in df.name.lower():
                    found.append(DetectedApp(name=name, path=df,
                                             connector_target=slug))
                    break

    return found


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CACHE_TTL = timedelta(hours=24)


def _cache_path() -> Path:
    return user_data_dir() / "daw_detector_cache.json"


def _load_cache() -> Optional[List[DetectedApp]]:
    p = _cache_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now() - cached_at > _CACHE_TTL:
            return None
        return [DetectedApp.from_dict(d) for d in data["apps"]]
    except Exception:
        return None


def _save_cache(apps: List[DetectedApp]) -> None:
    try:
        payload = {
            "cached_at": datetime.now().isoformat(),
            "apps": [a.to_dict() for a in apps],
        }
        _cache_path().write_text(json.dumps(payload, indent=2))
    except Exception:
        pass  # cache write failures are non-fatal


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_installed_apps(force: bool = False) -> List[DetectedApp]:
    """Return detected DAW / VJ apps on this machine.

    Results are cached for 24 h. Pass ``force=True`` to bypass the cache.
    Never raises — returns an empty list on any error.
    """
    if not force:
        cached = _load_cache()
        if cached is not None:
            return cached

    try:
        if sys.platform == "darwin":
            apps = _detect_macos()
        elif sys.platform == "win32":
            apps = _detect_windows()
        else:
            apps = _detect_linux()
    except Exception:
        apps = []

    _save_cache(apps)
    return apps
