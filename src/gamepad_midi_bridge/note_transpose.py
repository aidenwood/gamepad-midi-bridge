"""Global note transposition helper.

Provides a per-button transpose configuration that applies to every outgoing
note, independent of preset. Users can shift the entire rig up or down by
octaves and semitones on the fly without editing the preset.

Pure stdlib + dataclass only; no Qt, no bridge wiring.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class NoteTransposeConfig:
    """Configuration for global note transposition.

    Attributes:
        enabled: Whether transposition is active.
        octave_shift: Octave offset, clamped to -4..+4. Each octave = 12 semitones.
        semitone_shift: Semitone offset within the octave, clamped to -11..+11.
        clamp_to_midi: If True, clamp out-of-range notes to 0..127.
                       If False, drop out-of-range notes (return None).
        apply_to_chords: If True, transpose notes in chord-firing buttons.
                         If False, bypass transposition for chords.
    """
    enabled: bool = False
    octave_shift: int = 0
    semitone_shift: int = 0
    clamp_to_midi: bool = True
    apply_to_chords: bool = True

    def __post_init__(self):
        """Clamp shifts to valid ranges."""
        self.octave_shift = max(-4, min(4, self.octave_shift))
        self.semitone_shift = max(-11, min(11, self.semitone_shift))

    def to_dict(self) -> dict:
        """Serialize to dict for storage."""
        return {
            "enabled": self.enabled,
            "octave_shift": self.octave_shift,
            "semitone_shift": self.semitone_shift,
            "clamp_to_midi": self.clamp_to_midi,
            "apply_to_chords": self.apply_to_chords,
        }

    @staticmethod
    def from_dict(data: dict) -> NoteTransposeConfig:
        """Deserialize from dict."""
        return NoteTransposeConfig(
            enabled=data.get("enabled", False),
            octave_shift=data.get("octave_shift", 0),
            semitone_shift=data.get("semitone_shift", 0),
            clamp_to_midi=data.get("clamp_to_midi", True),
            apply_to_chords=data.get("apply_to_chords", True),
        )


def total_shift(cfg: NoteTransposeConfig) -> int:
    """Return total semitone shift from config, or 0 if disabled.

    Args:
        cfg: NoteTransposeConfig

    Returns:
        Total shift in semitones; 0 if disabled.
    """
    if not cfg.enabled:
        return 0
    return cfg.octave_shift * 12 + cfg.semitone_shift


def apply(note: int, cfg: NoteTransposeConfig) -> Optional[int]:
    """Apply transposition to a single note.

    Args:
        note: MIDI note 0..127.
        cfg: NoteTransposeConfig.

    Returns:
        Transposed note (0..127 if clamped, else None if out of range).
        Returns original note if disabled.
    """
    if not cfg.enabled:
        return note

    transposed = note + total_shift(cfg)

    if cfg.clamp_to_midi:
        return max(0, min(127, transposed))

    if 0 <= transposed <= 127:
        return transposed
    return None


def apply_chord(notes: List[int], cfg: NoteTransposeConfig) -> List[int]:
    """Apply transposition to a list of notes (chord).

    Args:
        notes: List of MIDI notes.
        cfg: NoteTransposeConfig.

    Returns:
        List of transposed notes (filtering out None if clamp_to_midi=False),
        or original notes if apply_to_chords=False or disabled.
    """
    if not cfg.enabled or not cfg.apply_to_chords:
        return notes

    transposed = [apply(note, cfg) for note in notes]
    return [n for n in transposed if n is not None]


def octave_up(cfg: NoteTransposeConfig, by: int = 1) -> NoteTransposeConfig:
    """Return a new config with octave_shift incremented (clamped).

    Args:
        cfg: NoteTransposeConfig.
        by: Number of octaves to shift up (default 1).

    Returns:
        New NoteTransposeConfig with updated octave_shift.
    """
    return NoteTransposeConfig(
        enabled=cfg.enabled,
        octave_shift=cfg.octave_shift + by,
        semitone_shift=cfg.semitone_shift,
        clamp_to_midi=cfg.clamp_to_midi,
        apply_to_chords=cfg.apply_to_chords,
    )


def octave_down(cfg: NoteTransposeConfig, by: int = 1) -> NoteTransposeConfig:
    """Return a new config with octave_shift decremented (clamped).

    Args:
        cfg: NoteTransposeConfig.
        by: Number of octaves to shift down (default 1).

    Returns:
        New NoteTransposeConfig with updated octave_shift.
    """
    return octave_up(cfg, -by)


def semitone_up(cfg: NoteTransposeConfig, by: int = 1) -> NoteTransposeConfig:
    """Return a new config with semitone_shift incremented (clamped).

    Args:
        cfg: NoteTransposeConfig.
        by: Number of semitones to shift up (default 1).

    Returns:
        New NoteTransposeConfig with updated semitone_shift.
    """
    return NoteTransposeConfig(
        enabled=cfg.enabled,
        octave_shift=cfg.octave_shift,
        semitone_shift=cfg.semitone_shift + by,
        clamp_to_midi=cfg.clamp_to_midi,
        apply_to_chords=cfg.apply_to_chords,
    )


def semitone_down(cfg: NoteTransposeConfig, by: int = 1) -> NoteTransposeConfig:
    """Return a new config with semitone_shift decremented (clamped).

    Args:
        cfg: NoteTransposeConfig.
        by: Number of semitones to shift down (default 1).

    Returns:
        New NoteTransposeConfig with updated semitone_shift.
    """
    return semitone_up(cfg, -by)


def reset(cfg: NoteTransposeConfig) -> NoteTransposeConfig:
    """Return a new config with both shifts at 0, preserving enabled state.

    Args:
        cfg: NoteTransposeConfig.

    Returns:
        New NoteTransposeConfig with octave_shift=0, semitone_shift=0.
    """
    return NoteTransposeConfig(
        enabled=cfg.enabled,
        octave_shift=0,
        semitone_shift=0,
        clamp_to_midi=cfg.clamp_to_midi,
        apply_to_chords=cfg.apply_to_chords,
    )
