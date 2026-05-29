"""Persist controller fingerprints to detect repeat connections."""
from __future__ import annotations

import json
from pathlib import Path
from .paths import user_data_dir


def _history_path() -> Path:
    """Where seen controller fingerprints live."""
    return user_data_dir() / "seen_controllers.json"


def seen_controllers() -> set[str]:
    """Load the set of previously-seen controller names."""
    path = _history_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("controllers", []))
    except Exception:
        return set()


def mark_seen(name: str) -> None:
    """Add a controller name to the seen list (idempotent)."""
    path = _history_path()
    seen = seen_controllers()
    if name not in seen:
        seen.add(name)
        try:
            path.write_text(
                json.dumps({"controllers": sorted(seen)}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


def was_seen(name: str) -> bool:
    """Check if a controller name has been seen before."""
    return name in seen_controllers()
