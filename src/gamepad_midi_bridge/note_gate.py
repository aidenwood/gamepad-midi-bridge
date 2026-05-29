"""Fixed-duration note gate — fire notes that auto-release after a configurable time.

Users can press a button and have the note release automatically after a fixed
duration (e.g., 100 ms for 16th-note stabs), instead of holding until button
release. Three modes control the release behaviour:

- "fixed": Always release after duration_ms, regardless of button state.
  on_release() is ignored.
- "min_hold": Hold at least duration_ms, then release when button is released
  after that minimum has elapsed.
- "max_hold": Release at duration_ms OR button-release, whichever comes first.

This is a pure-stdlib, non-Qt module. Time is measured in seconds (float) to
integrate with typical event-loop timestamps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NoteGateConfig:
    """Configuration for fixed-duration note gates."""

    enabled: bool = False
    duration_ms: int = 100
    mode: str = "fixed"

    def __post_init__(self) -> None:
        """Clamp duration_ms to valid range and normalize mode."""
        if self.duration_ms < 1:
            self.duration_ms = 1
        elif self.duration_ms > 10000:
            self.duration_ms = 10000

        if self.mode not in ("fixed", "min_hold", "max_hold"):
            self.mode = "fixed"

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to a dict."""
        return {
            "enabled": self.enabled,
            "duration_ms": self.duration_ms,
            "mode": self.mode,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> NoteGateConfig:
        """Deserialize config from a dict, with safe defaults."""
        return NoteGateConfig(
            enabled=d.get("enabled", False),
            duration_ms=d.get("duration_ms", 100),
            mode=d.get("mode", "fixed"),
        )


class NoteGate:
    """Manages fixed-duration note releases across multiple simultaneous notes."""

    def __init__(self, cfg: NoteGateConfig) -> None:
        """Initialize the gate with the given config.

        Args:
            cfg: NoteGateConfig instance.
        """
        self.cfg = cfg
        # Map of note -> start_time_s (float). Only tracks notes actively
        # registered with on_press() and not yet released/timed-out.
        self._active_notes: dict[int, float] = {}

    def on_press(self, note: int, now_s: float) -> None:
        """Register a note press at the given timestamp.

        Args:
            note: MIDI note number (0..127).
            now_s: Timestamp in seconds (as a float).
        """
        self._active_notes[note] = now_s

    def on_release(self, note: int, now_s: float) -> bool:
        """Handle a note release, return whether the note should be released NOW.

        Behaviour depends on the mode:
        - "fixed": Always returns False (the gate ignores releases; use tick()).
        - "min_hold": Returns True if (now_s - start_time) >= duration_s,
                      False otherwise (caller should wait).
        - "max_hold": Always returns True (release immediately).

        Args:
            note: MIDI note number.
            now_s: Timestamp in seconds.

        Returns:
            True if the caller should release the note now, False otherwise.
        """
        if note not in self._active_notes:
            return True  # Note wasn't active; no-op release is a "yes".

        if self.cfg.mode == "fixed":
            return False

        start_s = self._active_notes[note]
        duration_s = self.cfg.duration_ms / 1000.0

        if self.cfg.mode == "min_hold":
            if (now_s - start_s) >= duration_s:
                return True
            return False

        if self.cfg.mode == "max_hold":
            return True

        # Should never reach here due to NoteGateConfig.__post_init__ normalization,
        # but be defensive.
        return True

    def tick(self, now_s: float) -> list[int]:
        """Tick the gate and return notes that should be released due to timeout.

        Notes are released if (now_s - start_time) >= duration_ms for the
        relevant modes ("fixed" and "max_hold"). After a note is returned, it is
        removed from the active set.

        For "min_hold" mode, this method returns an empty list (release is
        driven by on_release()).

        Args:
            now_s: Current timestamp in seconds.

        Returns:
            List of MIDI note numbers that have exceeded their duration
            and should be released by the caller.
        """
        if self.cfg.mode == "min_hold":
            # min_hold doesn't auto-release; only on_release() controls it.
            return []

        duration_s = self.cfg.duration_ms / 1000.0
        released = []

        for note, start_s in list(self._active_notes.items()):
            if (now_s - start_s) >= duration_s:
                released.append(note)
                del self._active_notes[note]

        return released

    def active_count(self) -> int:
        """Return the number of currently active (pressed, not-yet-released) notes."""
        return len(self._active_notes)

    def clear(self) -> None:
        """Clear all active notes. Useful for reset or cleanup."""
        self._active_notes.clear()
