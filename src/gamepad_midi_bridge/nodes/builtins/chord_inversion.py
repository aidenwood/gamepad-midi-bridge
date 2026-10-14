"""ChordInversion — rotate chord-tone notes by N positions.

Three-input variant designed to be chained after chord_build: takes the
three note pins, shifts each up by 12 semitones if it would otherwise
appear below the chord's "inverted" root.

Inversion=0 = root position. =1 = 1st inversion (root moves up an
octave). =2 = 2nd inversion (root + third both move up). Goes through
the standard pop / jazz voicing convention.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _shift_up(note: float | int | None) -> float:
    if note is None:
        return 0.0
    try:
        return max(0.0, min(127.0, float(note) + 12.0))
    except (TypeError, ValueError):
        return 0.0


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    n1 = inputs.get("note1")
    n2 = inputs.get("note2")
    n3 = inputs.get("note3")
    inv = max(0, min(2, int(params.get("inversion", 0))))
    if inv >= 1:
        n1 = _shift_up(n1)
    if inv >= 2:
        n2 = _shift_up(n2)
    return {"note1": n1, "note2": n2, "note3": n3}


SPEC = NodeSpec(
    kind="chord_inversion",
    label="Chord Inversion",
    category="music",
    description=(
        "Rotate chord-tone notes by N inversions. Chain after "
        "chord_build to voice a triad in 1st or 2nd inversion. "
        "0 = root position, 1 = root moves up an octave, "
        "2 = root + third both move up. Higher voicings stay within "
        "MIDI's 0..127 range."
    ),
    short_description="Rotate triad notes by inversion.",
    params=(
        ParamSpec("inversion", "int", 0,
                  "0 = root position. 1 = first inversion. 2 = second inversion.",
                  minimum=0, maximum=2),
    ),
    inputs=(
        PinSpec("note1", "in", "Root note (will move up at inv=1+).", expected="scalar"),
        PinSpec("note2", "in", "Third (will move up at inv=2).", expected="scalar"),
        PinSpec("note3", "in", "Fifth (or 7th in 7-chord modes).", expected="scalar"),
    ),
    outputs=(
        PinSpec("note1", "out", "Inverted note 1.", expected="scalar"),
        PinSpec("note2", "out", "Inverted note 2.", expected="scalar"),
        PinSpec("note3", "out", "Inverted note 3.", expected="scalar"),
    ),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
