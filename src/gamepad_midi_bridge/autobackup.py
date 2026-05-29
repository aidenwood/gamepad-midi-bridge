"""Auto-backup of active mapping to timestamped snapshots."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .mapping import Mapping
from .paths import user_data_dir


def autosaves_dir() -> Path:
    """Directory for timestamped mapping snapshots. Creates if missing."""
    d = user_data_dir() / "autosaves"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_snapshot(mapping: Mapping) -> Path:
    """Write mapping to autosaves_dir with YYYY-MM-DD-HHMM timestamp.

    Atomic write (write to .tmp, rename). Overwrites if same minute exists.
    Returns the path written.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = f"{timestamp}.json"
    path = autosaves_dir() / filename

    # Atomic write: write to temp first, then rename
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(mapping.to_dict(), indent=2), encoding="utf-8")
    tmp_path.replace(path)

    return path


def prune_old_snapshots(keep: int = 30) -> int:
    """Delete autosave files older than the last `keep` by mtime.

    Returns count of files deleted.
    """
    d = autosaves_dir()
    if not d.exists():
        return 0

    # List all .json files, sorted by mtime descending (newest first)
    json_files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    # Delete everything past index `keep`
    to_delete = json_files[keep:]
    for path in to_delete:
        path.unlink()

    return len(to_delete)
