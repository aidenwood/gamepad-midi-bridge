"""Pad-layout auto-assigner: takes N buttons + a scale, returns ergonomic note assignments.

Pure stdlib only. No Qt, no global state. Reuses scales.notes_in_scale for scale logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from gamepad_midi_bridge.scales import notes_in_scale


LAYOUT_MODES = ["sequential", "spread", "thirds", "chromatic", "doubled"]


@dataclass
class PadLayoutConfig:
    """Configuration for pad layout assignment."""

    button_count: int = 8  # clamp 1..32
    root: int = 60  # clamp 0..127
    scale: str = "major"
    mode: str = "sequential"  # validate against LAYOUT_MODES; unknown → "sequential"
    start_octave: int = 4
    octave_span: int = 2  # clamp 1..6; how many octaves to spread across

    def __post_init__(self):
        """Validate and clamp all fields to legal ranges."""
        self.button_count = max(1, min(32, int(self.button_count)))
        self.root = max(0, min(127, int(self.root)))
        self.scale = str(self.scale)
        self.start_octave = int(self.start_octave)
        self.octave_span = max(1, min(6, int(self.octave_span)))

        # Validate mode; fall back to "sequential" if unknown.
        if self.mode not in LAYOUT_MODES:
            self.mode = "sequential"
        else:
            self.mode = str(self.mode)

    def to_dict(self) -> dict:
        """Round-trip serialization to dict."""
        return {
            "button_count": self.button_count,
            "root": self.root,
            "scale": self.scale,
            "mode": self.mode,
            "start_octave": self.start_octave,
            "octave_span": self.octave_span,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> PadLayoutConfig:
        """Deserialize from dict; missing keys use defaults."""
        if data is None:
            return cls()
        return cls(
            button_count=data.get("button_count", 8),
            root=data.get("root", 60),
            scale=data.get("scale", "major"),
            mode=data.get("mode", "sequential"),
            start_octave=data.get("start_octave", 4),
            octave_span=data.get("octave_span", 2),
        )


def build_layout(cfg: PadLayoutConfig) -> list[int]:
    """Build pad layout given a configuration.

    Args:
        cfg: PadLayoutConfig with mode, button_count, root, scale, octaves.

    Returns:
        List of MIDI notes (0..127), one per button, using the specified mode.
    """
    if cfg.mode == "sequential":
        return _sequential(cfg)
    elif cfg.mode == "spread":
        return _spread(cfg)
    elif cfg.mode == "thirds":
        return _thirds(cfg)
    elif cfg.mode == "chromatic":
        return _chromatic(cfg)
    elif cfg.mode == "doubled":
        return _doubled(cfg)
    else:
        # Fallback (should not happen due to __post_init__ validation)
        return _sequential(cfg)


def _get_scale_notes(cfg: PadLayoutConfig) -> list[int]:
    """Helper to get scale notes, converting MIDI root to pitch class."""
    # root is a MIDI note (0..127); convert to pitch class (0..11)
    pitch_class = cfg.root % 12
    return notes_in_scale(pitch_class, cfg.scale, cfg.octave_span, cfg.start_octave)


def _sequential(cfg: PadLayoutConfig) -> list[int]:
    """Fill buttons with scale notes in ascending order."""
    scale_notes = _get_scale_notes(cfg)
    # Take first button_count notes, pad with last note if not enough
    layout = []
    for i in range(cfg.button_count):
        if i < len(scale_notes):
            layout.append(scale_notes[i])
        else:
            # Pad with the last note
            layout.append(scale_notes[-1] if scale_notes else cfg.root)
    return layout


def _spread(cfg: PadLayoutConfig) -> list[int]:
    """Evenly distribute scale notes across button slots."""
    scale_notes = _get_scale_notes(cfg)
    if not scale_notes:
        return [cfg.root] * cfg.button_count

    layout = []
    scale_count = len(scale_notes)
    step = scale_count / cfg.button_count  # May be fractional

    for i in range(cfg.button_count):
        idx = min(int(i * step), scale_count - 1)
        layout.append(scale_notes[idx])

    return layout


def _thirds(cfg: PadLayoutConfig) -> list[int]:
    """Take every 3rd scale note (broken-thirds pattern)."""
    scale_notes = _get_scale_notes(cfg)
    if not scale_notes:
        return [cfg.root] * cfg.button_count

    layout = []
    for i in range(cfg.button_count):
        idx = (i * 3) % len(scale_notes)
        layout.append(scale_notes[idx])

    return layout


def _chromatic(cfg: PadLayoutConfig) -> list[int]:
    """Ignore scale, return button_count chromatic notes ascending from root."""
    layout = []
    for i in range(cfg.button_count):
        note = cfg.root + i
        # Clamp to 0..127
        note = max(0, min(127, note))
        layout.append(note)
    return layout


def _doubled(cfg: PadLayoutConfig) -> list[int]:
    """Each pair of buttons holds the same note + octave-up.

    e.g. button[0]=60, [1]=72, [2]=62, [3]=74, ...
    """
    scale_notes = _get_scale_notes(cfg)
    if not scale_notes:
        scale_notes = [cfg.root]

    layout = []
    note_idx = 0

    for button_idx in range(cfg.button_count):
        if button_idx % 2 == 0:
            # Even index: use the scale note as-is
            note = scale_notes[note_idx % len(scale_notes)]
        else:
            # Odd index: use the same note + octave (12 semitones)
            note = scale_notes[note_idx % len(scale_notes)] + 12
            note_idx += 1  # Move to next scale note for the next pair

        # Clamp to 0..127
        note = max(0, min(127, note))
        layout.append(note)

    return layout


def notes_per_button(layout: list[int]) -> dict[int, int]:
    """Return a dict mapping button index → MIDI note."""
    return {i: note for i, note in enumerate(layout)}


def inverse_lookup(note: int, layout: list[int]) -> Optional[int]:
    """Return the button index for a given MIDI note, or None if not found."""
    try:
        return layout.index(note)
    except ValueError:
        return None


def available_modes() -> list[str]:
    """Return a copy of the available layout modes."""
    return LAYOUT_MODES.copy()
