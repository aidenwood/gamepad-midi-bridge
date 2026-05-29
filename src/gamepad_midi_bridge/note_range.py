"""Note range constraint helper — forces outgoing notes into a configured range.

Transposition, dropping, or clamping strategies to keep MIDI notes within
a target octave or range. Pure stdlib only, no bridge coupling.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class NoteRangeConfig:
    """Configuration for note range constraint."""

    enabled: bool = False
    low_note: int = 0
    high_note: int = 127
    mode: str = "transpose"

    def __post_init__(self) -> None:
        """Clamp and validate fields after construction."""
        # Clamp low/high to MIDI range
        self.low_note = max(0, min(127, self.low_note))
        self.high_note = max(0, min(127, self.high_note))

        # Swap if inverted
        if self.low_note > self.high_note:
            self.low_note, self.high_note = self.high_note, self.low_note

        # Validate mode; unknown → "transpose"
        if self.mode not in ("transpose", "drop", "clamp"):
            self.mode = "transpose"

    def to_dict(self) -> dict:
        """Serialize to dict, safe for JSON or pickling."""
        return {
            "enabled": self.enabled,
            "low_note": self.low_note,
            "high_note": self.high_note,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NoteRangeConfig:
        """Deserialize from dict. Clamps and validates automatically."""
        return cls(
            enabled=bool(data.get("enabled", False)),
            low_note=int(data.get("low_note", 0)),
            high_note=int(data.get("high_note", 127)),
            mode=str(data.get("mode", "transpose")),
        )


def apply_range(note: int, cfg: NoteRangeConfig) -> Optional[int]:
    """Apply note range constraint.

    Args:
        note: MIDI note number (0..127).
        cfg: NoteRangeConfig describing the constraint.

    Returns:
        Constrained note, or None if the note should be dropped.
        If disabled, returns note unchanged.
    """
    if not cfg.enabled:
        return note

    # Already in range → pass through
    if cfg.low_note <= note <= cfg.high_note:
        return note

    # mode="drop": discard the note
    if cfg.mode == "drop":
        return None

    # mode="clamp": clip to boundary
    if cfg.mode == "clamp":
        if note < cfg.low_note:
            return cfg.low_note
        else:
            return cfg.high_note

    # mode="transpose": shift by octaves (±12) until in range
    # If no octave shift fits, return None.
    pitch_class = note % 12

    # Try all octaves from 0 to 10 (covers full 0..127 MIDI range)
    # This includes both upward and downward shifts relative to the original note
    for octave in range(11):
        transposed = pitch_class + (octave * 12)
        if cfg.low_note <= transposed <= cfg.high_note:
            return transposed

    # No octave shift fits → drop
    return None
