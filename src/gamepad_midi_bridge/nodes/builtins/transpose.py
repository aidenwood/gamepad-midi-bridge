"""Transpose — shift a MIDI note value by N semitones.

Wire-eligible note operator. Pair upstream of a midi.note: sink to
shift the entire mapping up/down at runtime without rewriting note
numbers everywhere.
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
    semitones = int(params.get("semitones", 0))
    return {"out": max(0.0, min(127.0, v + semitones))}


SPEC = NodeSpec(
    kind="transpose",
    label="Transpose",
    category="music",
    description=(
        "Add a fixed number of semitones to a MIDI note value (0..127). "
        "Clamped to the MIDI note range so extreme shifts won't blow "
        "past the protocol. Pair upstream of a midi.note: sink to shift "
        "an entire patch up/down a key without rewiring."
    ),
    short_description="Shift MIDI note by N semitones.",
    params=(
        ParamSpec(
            name="semitones", kind="int", default=0,
            description="Pitch shift in semitones. 12 = up an octave, -7 = down a fifth.",
            minimum=-48, maximum=48,
        ),
    ),
    inputs=(PinSpec("in", "in", "MIDI note value 0..127.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Transposed note, clamped 0..127.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
