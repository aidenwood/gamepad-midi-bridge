"""OctaveShift — add N octaves (multiples of 12 semitones) to a note value.

Wire-eligible note operator. Distinct from Transpose because the param
unit (octaves) makes intent obvious — easier to spot in a graph than a
±12/±24 semitone count.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    octaves = int(params.get("octaves", 0))
    return {"out": max(0.0, min(127.0, v + 12 * octaves))}


SPEC = NodeSpec(
    kind="octave_shift",
    label="Octave Shift",
    category="music",
    description=(
        "Shift a MIDI note value by whole octaves (multiples of 12 "
        "semitones). Clamped to 0..127 so extreme shifts won't blow "
        "past the protocol. Use when 'an octave up' reads cleaner in "
        "the graph than the equivalent transpose semitones value."
    ),
    short_description="Shift MIDI note by N octaves.",
    params=(
        ParamSpec("octaves", "int", 0,
                  "Number of octaves to add. -3..+3 covers most real use.",
                  minimum=-5, maximum=5),
    ),
    inputs=(PinSpec("in", "in", "MIDI note value.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Octave-shifted note, clamped 0..127.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
