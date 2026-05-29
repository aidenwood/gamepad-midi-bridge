"""Note hold stack — build chords one note at a time. Pure stdlib, no Qt."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


HoldMode = Literal["add", "toggle", "additive"]


@dataclass
class NoteHoldStackConfig:
    """Configuration for note hold stack."""

    enabled: bool = False
    mode: str = "add"  # one of "add", "toggle", "additive"; unknown → "add"
    max_notes: int = 16  # clamp 1..32; cap on simultaneous held notes
    auto_release_on_overflow: bool = True  # when max_notes hit, oldest note is released

    def to_dict(self) -> dict:
        """Round-trip to dict (for JSON serialization)."""
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "max_notes": self.max_notes,
            "auto_release_on_overflow": self.auto_release_on_overflow,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NoteHoldStackConfig:
        """Deserialize from dict, clamping and normalizing values."""
        enabled = data.get("enabled", False)
        mode = data.get("mode", "add")
        # Validate mode; unknown modes default to "add"
        if mode not in ("add", "toggle", "additive"):
            mode = "add"
        max_notes = max(1, min(32, int(data.get("max_notes", 16))))
        auto_release_on_overflow = data.get("auto_release_on_overflow", True)

        return cls(
            enabled=enabled,
            mode=mode,
            max_notes=max_notes,
            auto_release_on_overflow=auto_release_on_overflow,
        )


class NoteHoldStack:
    """Hold notes as a stack; press adds/toggles, panic clears all."""

    def __init__(self, cfg: NoteHoldStackConfig):
        """Initialize with config."""
        self.cfg = cfg
        self._held: list[tuple[int, int]] = []  # ordered list of (note, channel) for oldest-first eviction

    def press(
        self, note: int, channel: int = 1, now_s: float = 0.0
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """
        Press a note. Returns (newly_pressed_notes, newly_released_notes).

        Modes:
        - "add" / "toggle": if (note, channel) already held → remove it (release). Else add it (press).
        - "additive": always add (no release on duplicate).

        If add would exceed max_notes and auto_release_on_overflow:
            pop oldest and include in released list.

        Args:
            note: MIDI note number (0..127)
            channel: MIDI channel (1..16), default 1
            now_s: timestamp (unused, for future use)

        Returns:
            Tuple of (pressed_list, released_list), each a list of (note, channel) tuples.
        """
        pressed = []
        released = []

        note_ch = (note, channel)

        # Check if already held
        is_held = note_ch in self._held

        if self.cfg.mode == "additive":
            # Always add; no removal via press
            if not is_held:
                # Check overflow before adding
                if len(self._held) >= self.cfg.max_notes:
                    if self.cfg.auto_release_on_overflow:
                        oldest = self._held.pop(0)
                        released.append(oldest)
                    else:
                        # Overflow rejected, return empty pressed list
                        return ([], [])

                self._held.append(note_ch)
                pressed.append(note_ch)
            # else: already held, no-op
        else:
            # "add" or "toggle" mode (or unknown, treated as "add")
            if is_held:
                # Remove it (release)
                self._held.remove(note_ch)
                released.append(note_ch)
            else:
                # Add it (press)
                # Check overflow before adding
                if len(self._held) >= self.cfg.max_notes:
                    if self.cfg.auto_release_on_overflow:
                        oldest = self._held.pop(0)
                        released.append(oldest)
                    else:
                        # Overflow rejected, return empty pressed list
                        return ([], [])

                self._held.append(note_ch)
                pressed.append(note_ch)

        return (pressed, released)

    def clear(self) -> list[tuple[int, int]]:
        """Release all held notes. Returns list of released notes."""
        released = self._held.copy()
        self._held = []
        return released

    def held(self) -> list[tuple[int, int]]:
        """Return a copy of currently held notes."""
        return self._held.copy()

    def count(self) -> int:
        """Return count of currently held notes."""
        return len(self._held)

    def is_held(self, note: int, channel: int = 1) -> bool:
        """Check if a specific note on channel is currently held."""
        return (note, channel) in self._held
