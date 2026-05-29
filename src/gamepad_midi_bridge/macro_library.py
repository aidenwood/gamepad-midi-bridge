"""Macro effects library — named, parametric macro sequences (flam, drumroll, glissando, portamento).

Pure stdlib + math. No Qt. Generates lists of timed MIDI events.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class MacroEvent:
    """A single MIDI event with timing and parameters."""

    offset_ms: float  # Time offset from macro start, in milliseconds
    kind: str  # "note_on", "note_off", or "cc"
    note: int = 0  # MIDI note number (0..127)
    velocity: int = 100  # Note velocity (0..127)
    channel: int = 1  # MIDI channel (1..16)
    cc: int = 0  # CC number (0..127)
    value: int = 0  # CC value (0..127)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "offset_ms": self.offset_ms,
            "kind": self.kind,
            "note": self.note,
            "velocity": self.velocity,
            "channel": self.channel,
            "cc": self.cc,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MacroEvent:
        """Deserialize from dictionary."""
        return cls(
            offset_ms=data.get("offset_ms", 0.0),
            kind=data.get("kind", "note_on"),
            note=data.get("note", 0),
            velocity=data.get("velocity", 100),
            channel=data.get("channel", 1),
            cc=data.get("cc", 0),
            value=data.get("value", 0),
        )


def _clamp(value: int, min_val: int = 0, max_val: int = 127) -> int:
    """Clamp integer to MIDI range."""
    return max(min_val, min(max_val, value))


def flam(
    root_note: int,
    channel: int = 1,
    grace_velocity: int = 60,
    main_velocity: int = 110,
    grace_offset_ms: float = 20.0,
) -> List[MacroEvent]:
    """Flam: grace note + main note in quick succession.

    Args:
        root_note: Main note to flam (0..127).
        channel: MIDI channel (1..16).
        grace_velocity: Velocity of grace note (0..127).
        main_velocity: Velocity of main note (0..127).
        grace_offset_ms: Delay from grace note on to main note on (ms).

    Returns:
        List of 4 MacroEvent: grace_on, grace_off, root_on, root_off.
        Grace note = root - 2 semitones (clamped 0..127).
    """
    root_note = _clamp(root_note)
    grace_note = _clamp(root_note - 2)
    grace_velocity = _clamp(grace_velocity)
    main_velocity = _clamp(main_velocity)

    return [
        MacroEvent(
            offset_ms=0.0,
            kind="note_on",
            note=grace_note,
            velocity=grace_velocity,
            channel=_clamp(channel, 1, 16),
        ),
        MacroEvent(
            offset_ms=30.0,
            kind="note_off",
            note=grace_note,
            velocity=grace_velocity,
            channel=_clamp(channel, 1, 16),
        ),
        MacroEvent(
            offset_ms=grace_offset_ms,
            kind="note_on",
            note=root_note,
            velocity=main_velocity,
            channel=_clamp(channel, 1, 16),
        ),
        MacroEvent(
            offset_ms=grace_offset_ms + 200.0,
            kind="note_off",
            note=root_note,
            velocity=main_velocity,
            channel=_clamp(channel, 1, 16),
        ),
    ]


def drumroll(
    root_note: int,
    channel: int = 1,
    hits: int = 6,
    total_duration_ms: float = 400,
    velocity_start: int = 100,
    velocity_end: int = 60,
) -> List[MacroEvent]:
    """Drumroll: repeated note with velocity ramp.

    Args:
        root_note: Note to repeat (0..127).
        channel: MIDI channel (1..16).
        hits: Number of note hits.
        total_duration_ms: Total time span (ms).
        velocity_start: Starting velocity (0..127).
        velocity_end: Ending velocity (0..127).

    Returns:
        List of hits*2 MacroEvent: alternating note_on/note_off.
    """
    root_note = _clamp(root_note)
    velocity_start = _clamp(velocity_start)
    velocity_end = _clamp(velocity_end)
    channel = _clamp(channel, 1, 16)

    events = []
    if hits <= 0:
        return events

    time_per_hit = total_duration_ms / hits
    half_hit = time_per_hit / 2.0

    for i in range(hits):
        # Linear ramp: velocity_start + (velocity_end - velocity_start) * (i / (hits - 1))
        if hits == 1:
            velocity = velocity_start
        else:
            velocity = int(velocity_start + (velocity_end - velocity_start) * (i / (hits - 1)))
        velocity = _clamp(velocity)

        offset_on = i * time_per_hit
        offset_off = offset_on + half_hit

        events.append(
            MacroEvent(
                offset_ms=offset_on,
                kind="note_on",
                note=root_note,
                velocity=velocity,
                channel=channel,
            )
        )
        events.append(
            MacroEvent(
                offset_ms=offset_off,
                kind="note_off",
                note=root_note,
                velocity=velocity,
                channel=channel,
            )
        )

    return events


def glissando(
    root_note: int,
    target_note: int,
    channel: int = 1,
    duration_ms: float = 300,
    velocity: int = 80,
    step_ms: float = 30,
) -> List[MacroEvent]:
    """Glissando: chromatic run from root to target.

    Args:
        root_note: Starting note (0..127).
        target_note: Ending note (0..127).
        channel: MIDI channel (1..16).
        duration_ms: Total duration (ms).
        velocity: Note velocity (0..127).
        step_ms: Time per step (ms).

    Returns:
        List of MacroEvent: chromatic run with note_on/note_off pairs.
    """
    root_note = _clamp(root_note)
    target_note = _clamp(target_note)
    velocity = _clamp(velocity)
    channel = _clamp(channel, 1, 16)

    events = []
    if root_note == target_note:
        # Single note
        events.append(
            MacroEvent(
                offset_ms=0.0,
                kind="note_on",
                note=root_note,
                velocity=velocity,
                channel=channel,
            )
        )
        events.append(
            MacroEvent(
                offset_ms=duration_ms,
                kind="note_off",
                note=root_note,
                velocity=velocity,
                channel=channel,
            )
        )
        return events

    # Build chromatic run
    direction = 1 if target_note > root_note else -1
    current_note = root_note
    offset = 0.0

    while True:
        # Note on
        events.append(
            MacroEvent(
                offset_ms=offset,
                kind="note_on",
                note=current_note,
                velocity=velocity,
                channel=channel,
            )
        )

        # Check if we've reached the target
        if current_note == target_note:
            # Final note off at duration
            events.append(
                MacroEvent(
                    offset_ms=duration_ms,
                    kind="note_off",
                    note=current_note,
                    velocity=velocity,
                    channel=channel,
                )
            )
            break

        # Next note
        current_note += direction
        offset += step_ms

        # Note off with 5ms gap (overlap-free)
        events.append(
            MacroEvent(
                offset_ms=offset - 5.0,
                kind="note_off",
                note=current_note - direction,
                velocity=velocity,
                channel=channel,
            )
        )

    return events


def portamento_cc(
    start_value: int,
    end_value: int,
    cc: int = 65,
    channel: int = 1,
    duration_ms: float = 500,
    steps: int = 16,
) -> List[MacroEvent]:
    """Portamento CC: smooth CC ramp.

    Args:
        start_value: Starting CC value (0..127).
        end_value: Ending CC value (0..127).
        cc: CC number (0..127).
        channel: MIDI channel (1..16).
        duration_ms: Total duration (ms).
        steps: Number of CC steps.

    Returns:
        List of MacroEvent: CC messages evenly spaced.
    """
    start_value = _clamp(start_value)
    end_value = _clamp(end_value)
    cc = _clamp(cc)
    channel = _clamp(channel, 1, 16)

    events = []
    if steps <= 0:
        return events

    time_per_step = duration_ms / steps

    for i in range(steps):
        # Linear interpolation
        if steps == 1:
            value = start_value
        else:
            value = int(start_value + (end_value - start_value) * (i / (steps - 1)))
        value = _clamp(value)

        offset = i * time_per_step

        events.append(
            MacroEvent(
                offset_ms=offset,
                kind="cc",
                cc=cc,
                value=value,
                channel=channel,
            )
        )

    return events


def chord_strum(
    notes: List[int],
    channel: int = 1,
    velocity: int = 100,
    strum_gap_ms: float = 15,
    hold_ms: float = 600,
) -> List[MacroEvent]:
    """Chord strum: notes in sequence, all release together.

    Args:
        notes: List of MIDI notes to strum.
        channel: MIDI channel (1..16).
        velocity: Note velocity (0..127).
        strum_gap_ms: Time between note ons (ms).
        hold_ms: How long to hold before all release (ms).

    Returns:
        List of MacroEvent: strum pattern.
    """
    velocity = _clamp(velocity)
    channel = _clamp(channel, 1, 16)

    events = []
    clamped_notes = [_clamp(n) for n in notes]

    # Note ons, staggered
    for i, note in enumerate(clamped_notes):
        offset = i * strum_gap_ms
        events.append(
            MacroEvent(
                offset_ms=offset,
                kind="note_on",
                note=note,
                velocity=velocity,
                channel=channel,
            )
        )

    # All note offs at the same time
    for note in clamped_notes:
        events.append(
            MacroEvent(
                offset_ms=hold_ms,
                kind="note_off",
                note=note,
                velocity=velocity,
                channel=channel,
            )
        )

    return events


def tremolo(
    root_note: int,
    channel: int = 1,
    hits: int = 8,
    gap_ms: float = 40,
    velocity: int = 90,
) -> List[MacroEvent]:
    """Tremolo: repeated same note at regular intervals.

    Args:
        root_note: Note to repeat (0..127).
        channel: MIDI channel (1..16).
        hits: Number of hits.
        gap_ms: Time between hits (ms).
        velocity: Note velocity (0..127).

    Returns:
        List of MacroEvent: tremolo pattern.
    """
    root_note = _clamp(root_note)
    velocity = _clamp(velocity)
    channel = _clamp(channel, 1, 16)

    events = []
    half_gap = gap_ms / 2.0

    for i in range(hits):
        offset_on = i * gap_ms
        offset_off = offset_on + half_gap

        events.append(
            MacroEvent(
                offset_ms=offset_on,
                kind="note_on",
                note=root_note,
                velocity=velocity,
                channel=channel,
            )
        )
        events.append(
            MacroEvent(
                offset_ms=offset_off,
                kind="note_off",
                note=root_note,
                velocity=velocity,
                channel=channel,
            )
        )

    return events


MACRO_RECIPES: Dict[str, str] = {
    "flam": "Grace note + main note in quick succession",
    "drumroll": "Repeated note with velocity ramp",
    "glissando": "Chromatic run from note to note",
    "portamento_cc": "Smooth CC value ramp",
    "chord_strum": "Strum chord notes in order",
    "tremolo": "Repeated same note at intervals",
}


def available_macros() -> List[str]:
    """Return sorted list of available macro names."""
    return sorted(MACRO_RECIPES.keys())
