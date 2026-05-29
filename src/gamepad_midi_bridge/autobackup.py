"""Auto-backup of active mapping to timestamped snapshots."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .mapping import Mapping
from .paths import user_data_dir


def autosaves_dir() -> Path:
    """Directory for timestamped mapping snapshots. Creates if missing."""
    d = user_data_dir() / "autosaves"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clean_shutdown_flag() -> Path:
    """Path to session clean-shutdown marker file."""
    return user_data_dir() / "session_clean.flag"


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


def mark_clean_shutdown() -> None:
    """Write clean-shutdown marker file on graceful app exit."""
    try:
        _clean_shutdown_flag().write_text("", encoding="utf-8")
    except Exception:
        pass


def mark_unclean_startup() -> None:
    """Delete clean-shutdown marker on app launch."""
    try:
        _clean_shutdown_flag().unlink(missing_ok=True)
    except Exception:
        pass


def was_clean_shutdown() -> bool:
    """Check if the previous session exited cleanly."""
    try:
        return _clean_shutdown_flag().exists()
    except Exception:
        return True  # Assume clean if check fails


def latest_autosave() -> Optional[Path]:
    """Return the most recently modified autosave file, or None if no files exist."""
    d = autosaves_dir()
    if not d.exists():
        return None
    json_files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return json_files[0] if json_files else None


def load_latest_autosave() -> Optional[Mapping]:
    """Load and return the latest autosave as a Mapping, or None if load fails."""
    path = latest_autosave()
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Mapping.from_dict(data)
    except Exception:
        return None
