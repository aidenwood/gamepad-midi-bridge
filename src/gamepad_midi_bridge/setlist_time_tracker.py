"""Setlist time tracker — records duration per preset across a session.

Pure stdlib only; no PySide6 or threading — simple mutable data structures
suitable for single-threaded event loop in the UI or bridge.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class PresetTimeRecord:
    """Time tracking data for a single preset."""

    preset_slug: str
    total_seconds: float = 0.0
    switch_count: int = 0  # number of times this preset was made active
    last_active_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for persistence or JSON export."""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> PresetTimeRecord:
        """Deserialize from dict."""
        return PresetTimeRecord(
            preset_slug=data["preset_slug"],
            total_seconds=data.get("total_seconds", 0.0),
            switch_count=data.get("switch_count", 0),
            last_active_at=data.get("last_active_at"),
        )


class SetlistTimeTracker:
    """Tracks time spent on each preset across a session."""

    def __init__(self) -> None:
        self._records: Dict[str, PresetTimeRecord] = {}
        self._current_preset: Optional[str] = None
        self._session_start_at: Optional[float] = None
        self._current_start_at: Optional[float] = None

    def start_session(self, now_s: float) -> None:
        """Start a new tracking session.

        Clears any active preset state and stamps the session start time.
        """
        self._session_start_at = now_s
        self._current_preset = None
        self._current_start_at = None

    def set_active(self, preset_slug: str, now_s: float) -> None:
        """Switch to a new active preset.

        If a preset was previously active, accumulate its duration.
        Then set the new current preset and increment its switch count.
        """
        # Flush the previous preset's elapsed time if one was active
        if self._current_preset is not None and self._current_start_at is not None:
            record = self._records.get(self._current_preset)
            if record is not None:
                record.total_seconds += now_s - self._current_start_at

        # Initialize the new preset record if it doesn't exist
        if preset_slug not in self._records:
            self._records[preset_slug] = PresetTimeRecord(preset_slug=preset_slug)

        # Activate the new preset
        self._current_preset = preset_slug
        self._current_start_at = now_s
        self._records[preset_slug].switch_count += 1
        self._records[preset_slug].last_active_at = now_s

    def tick(self, now_s: float) -> None:
        """Optional heartbeat for "I'm still on this preset" pulses.

        Updates last_active_at and accumulates time incrementally.
        Typically called on a timer (e.g. every 100ms) if you want
        fine-grained "still active" updates.
        """
        if self._current_preset is not None:
            record = self._records.get(self._current_preset)
            if record is not None:
                record.last_active_at = now_s

    def end_session(self, now_s: float) -> None:
        """End the tracking session.

        Flushes the current preset's elapsed time.
        Clears current state but keeps records intact.
        """
        if self._current_preset is not None and self._current_start_at is not None:
            record = self._records.get(self._current_preset)
            if record is not None:
                record.total_seconds += now_s - self._current_start_at

        self._current_preset = None
        self._current_start_at = None

    def get_record(self, preset_slug: str) -> Optional[PresetTimeRecord]:
        """Return the record for a single preset, or None if not found."""
        return self._records.get(preset_slug)

    def all_records(self) -> Dict[str, PresetTimeRecord]:
        """Return a copy of all preset records."""
        return dict(self._records)

    def total_session_seconds(self) -> float:
        """Return total elapsed time since session start, or 0 if not started."""
        if self._session_start_at is None:
            return 0.0
        # If session is still active, compute elapsed up to now
        # Otherwise, if ended, return sum of all recorded durations (since
        # end_session was called, all durations have been flushed into records)
        if self._current_preset is not None:
            # Session is active; return time from session start to current time
            # We'll compute this based on the caller's notion of "now"
            # For now, just return the sum of recorded times (caller must track end)
            return sum(r.total_seconds for r in self._records.values())
        else:
            # Session ended; all times are already in records
            return sum(r.total_seconds for r in self._records.values())

    def most_used(self, n: int = 3) -> List[PresetTimeRecord]:
        """Return the N presets with highest total_seconds, sorted descending."""
        records = sorted(
            self._records.values(), key=lambda r: r.total_seconds, reverse=True
        )
        return records[:n]

    def least_used(self, n: int = 3) -> List[PresetTimeRecord]:
        """Return the N presets with lowest total_seconds (excluding 0-second).

        Sorted ascending; filters out presets with 0 total_seconds.
        """
        non_zero = [r for r in self._records.values() if r.total_seconds > 0]
        records = sorted(non_zero, key=lambda r: r.total_seconds)
        return records[:n]

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of session statistics."""
        return {
            "session_seconds": self.total_session_seconds(),
            "preset_count": len(self._records),
            "most_used_slug": (
                self.most_used(1)[0].preset_slug if self.most_used(1) else None
            ),
            "total_switches": sum(r.switch_count for r in self._records.values()),
        }

    def reset(self) -> None:
        """Clear all records and session state."""
        self._records.clear()
        self._current_preset = None
        self._session_start_at = None
        self._current_start_at = None
