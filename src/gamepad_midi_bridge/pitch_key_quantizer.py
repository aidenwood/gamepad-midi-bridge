"""Pitch-key quantizer — snaps MIDI notes to the nearest in-key note.

Configured with root + scale + direction (nearest/up/down).
Pure stdlib, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass

from gamepad_midi_bridge import scales


@dataclass
class PitchKeyQuantizerConfig:
    """Configuration for pitch key quantization."""

    enabled: bool = False
    root: int = 60  # C4 default; clamped 0..127
    scale: str = "major"  # must match key in scales.SCALES
    direction: str = "nearest"  # "nearest" / "up" / "down"
    bypass_when_in_key: bool = True  # if input already in scale, return unchanged

    def __post_init__(self) -> None:
        """Validate and clamp configuration values."""
        # Clamp root to 0..127
        self.root = max(0, min(127, self.root))

        # Fallback unknown scale to "major"
        if self.scale not in scales.SCALES:
            self.scale = "major"

        # Fallback unknown direction to "nearest"
        if self.direction not in ("nearest", "up", "down"):
            self.direction = "nearest"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "enabled": self.enabled,
            "root": self.root,
            "scale": self.scale,
            "direction": self.direction,
            "bypass_when_in_key": self.bypass_when_in_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PitchKeyQuantizerConfig:
        """Deserialize from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            root=data.get("root", 60),
            scale=data.get("scale", "major"),
            direction=data.get("direction", "nearest"),
            bypass_when_in_key=data.get("bypass_when_in_key", True),
        )


class PitchKeyQuantizer:
    """Quantizes MIDI notes to the nearest note within a configured key."""

    def __init__(self, cfg: PitchKeyQuantizerConfig) -> None:
        """Initialize with config and pre-compute scale notes.

        Args:
            cfg: PitchKeyQuantizerConfig instance.
        """
        self.cfg = cfg
        self._scale_notes: set[int] = set()
        self._rebuild_scale_notes()

    def _rebuild_scale_notes(self) -> None:
        """Rebuild the set of scale notes for the current root/scale."""
        self._scale_notes = set()
        intervals = scales.SCALES.get(self.cfg.scale, scales.SCALES["major"])
        root_pitch_class = self.cfg.root % 12

        for midi_note in range(128):
            pitch_class = midi_note % 12
            interval_from_root = (pitch_class - root_pitch_class) % 12
            if interval_from_root in intervals:
                self._scale_notes.add(midi_note)

    def quantize(self, note: int) -> int:
        """Quantize a MIDI note to the nearest in-key note.

        Args:
            note: MIDI note (0..127).

        Returns:
            Quantized MIDI note (0..127).
        """
        # Clamp input to valid range
        note = max(0, min(127, note))

        # If disabled, return unchanged
        if not self.cfg.enabled:
            return note

        # If already in scale and bypass enabled, return unchanged
        if self.cfg.bypass_when_in_key and note in self._scale_notes:
            return note

        # Quantize based on direction
        if self.cfg.direction == "up":
            return self._quantize_up(note)
        elif self.cfg.direction == "down":
            return self._quantize_down(note)
        else:  # "nearest" (default)
            return self._quantize_nearest(note)

    def _quantize_nearest(self, note: int) -> int:
        """Find nearest in-scale note (ties round up)."""
        if not self._scale_notes:
            return note

        sorted_notes = sorted(self._scale_notes)
        closest = sorted_notes[0]
        min_distance = abs(note - closest)

        for scale_note in sorted_notes:
            distance = abs(note - scale_note)
            # Tie: choose higher note
            if distance < min_distance or (
                distance == min_distance and scale_note > closest
            ):
                closest = scale_note
                min_distance = distance

        return max(0, min(127, closest))

    def _quantize_up(self, note: int) -> int:
        """Find first in-scale note >= note."""
        if not self._scale_notes:
            return note

        sorted_notes = sorted(self._scale_notes)
        for scale_note in sorted_notes:
            if scale_note >= note:
                return max(0, min(127, scale_note))

        # If no note found above, wrap to lowest note
        return max(0, min(127, sorted_notes[0]))

    def _quantize_down(self, note: int) -> int:
        """Find first in-scale note <= note."""
        if not self._scale_notes:
            return note

        sorted_notes = sorted(self._scale_notes)
        for scale_note in reversed(sorted_notes):
            if scale_note <= note:
                return max(0, min(127, scale_note))

        # If no note found below, wrap to highest note
        return max(0, min(127, sorted_notes[-1]))

    def change_key(self, root: int, scale: str) -> None:
        """Change the key and rebuild the scale note cache.

        Args:
            root: New root note (0..127).
            scale: New scale name (must exist in scales.SCALES).
        """
        self.cfg.root = max(0, min(127, root))
        if scale not in scales.SCALES:
            self.cfg.scale = "major"
        else:
            self.cfg.scale = scale
        self._rebuild_scale_notes()

    def in_key(self, note: int) -> bool:
        """Check if a MIDI note is in the configured key.

        Args:
            note: MIDI note (0..127).

        Returns:
            True if note is in the scale, False otherwise.
        """
        return note in self._scale_notes

    def scale_notes(self) -> list[int]:
        """Return sorted list of all scale notes (0..127).

        Returns:
            Sorted list of MIDI notes in the current scale.
        """
        return sorted(self._scale_notes)
