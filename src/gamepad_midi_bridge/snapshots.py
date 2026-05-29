"""Named mapping snapshots — user-labelled save points distinct from auto-backups."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .mapping import Mapping
from .paths import user_data_dir


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------

def _snapshots_dir() -> Path:
    """Directory for named snapshots. Created on first access."""
    d = user_data_dir() / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Convert a human-readable name to a safe filename slug.

    Lowercases, replaces non-alphanum runs with hyphens, strips leading/
    trailing hyphens. Returns at least "snapshot" if the result is empty.

    >>> slugify("Live set v1")
    'live-set-v1'
    >>> slugify("  Studio / version!  ")
    'studio-version'
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "snapshot"


# ---------------------------------------------------------------------------
# SnapshotInfo
# ---------------------------------------------------------------------------

@dataclass
class SnapshotInfo:
    slug: str
    name: str
    mtime: float   # seconds since epoch
    size: int      # bytes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_snapshot(mapping: Mapping, name: str) -> Path:
    """Write *mapping* as a named snapshot.

    The snapshot carries the human-readable *name* embedded in its JSON so it
    can be recovered without the filename. Atomic write (`.tmp` + rename).
    Returns the path written.
    """
    slug = slugify(name)
    path = _snapshots_dir() / f"{slug}.json"
    tmp_path = path.with_suffix(".json.tmp")

    payload = mapping.to_dict()
    payload["_snapshot_name"] = name  # preserve original casing

    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return path


def list_snapshots() -> List[SnapshotInfo]:
    """Return all snapshots sorted by mtime descending (newest first)."""
    d = _snapshots_dir()
    infos: List[SnapshotInfo] = []
    for p in d.glob("*.json"):
        try:
            stat = p.stat()
            raw = json.loads(p.read_text(encoding="utf-8"))
            human_name = raw.get("_snapshot_name") or raw.get("name") or p.stem
            infos.append(SnapshotInfo(
                slug=p.stem,
                name=human_name,
                mtime=stat.st_mtime,
                size=stat.st_size,
            ))
        except (OSError, json.JSONDecodeError):
            continue
    infos.sort(key=lambda s: s.mtime, reverse=True)
    return infos


def load_snapshot(slug: str) -> Optional[Mapping]:
    """Load and return the mapping for *slug*, or None on missing/parse error."""
    path = _snapshots_dir() / f"{slug}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Strip our private meta key before handing to Mapping.from_dict
        data.pop("_snapshot_name", None)
        return Mapping.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None


def delete_snapshot(slug: str) -> bool:
    """Delete the snapshot file for *slug*. Returns True if deleted."""
    path = _snapshots_dir() / f"{slug}.json"
    if path.exists():
        path.unlink()
        return True
    return False
