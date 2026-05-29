"""Usage statistics tracker — per-control press counts for the usage heatmap.

Pure stdlib + threading; no PySide6 dependency so it can be imported from
the bridge worker thread without GUI complications.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Union


@dataclass
class UsageRecord:
    kind: str                    # "button", "axis", "hat", "corner"
    index: Union[int, str]       # button/axis index or hat direction string
    count: int
    last_used_ms: int            # epoch ms


class UsageTracker:
    """Thread-safe in-memory tracker for per-control usage counts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key: (kind, index) → [count, last_used_ms]
        self._data: Dict[tuple, List[int]] = {}

    def record(self, kind: str, index: Union[int, str]) -> None:
        """Increment the press count for (kind, index) and stamp the time."""
        key = (kind, index)
        now_ms = int(time.time() * 1000)
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._data[key] = [1, now_ms]
            else:
                entry[0] += 1
                entry[1] = now_ms

    def snapshot(self) -> List[UsageRecord]:
        """Return a copy of all records sorted by count descending."""
        with self._lock:
            records = [
                UsageRecord(kind=k, index=i, count=v[0], last_used_ms=v[1])
                for (k, i), v in self._data.items()
            ]
        records.sort(key=lambda r: r.count, reverse=True)
        return records

    def top_n(self, n: int = 5) -> List[UsageRecord]:
        """Return the N most-used controls."""
        return self.snapshot()[:n]

    def reset(self) -> None:
        """Clear all recorded data."""
        with self._lock:
            self._data.clear()


# Module-level singleton — bridge and UI both import from here.
_tracker: UsageTracker = UsageTracker()


def tracker() -> UsageTracker:
    """Return the global UsageTracker singleton."""
    return _tracker
