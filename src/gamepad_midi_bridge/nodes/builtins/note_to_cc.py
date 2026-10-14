"""NoteToCC — re-scale a MIDI note value into a CC-friendly 0..127 range.

Wire-eligible. Common pattern: a button source emits a note value, but
the destination wants CC. Linear remap from one MIDI range to another
with explicit floor/ceil.
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
    note_lo = float(params.get("note_lo", 36))   # C2
    note_hi = float(params.get("note_hi", 84))   # C6 — common keyboard span
    cc_lo = float(params.get("cc_lo", 0))
    cc_hi = float(params.get("cc_hi", 127))
    if note_hi == note_lo:
        return {"out": cc_lo}
    v = max(note_lo, min(note_hi, v))
    t = (v - note_lo) / (note_hi - note_lo)
    return {"out": cc_lo + t * (cc_hi - cc_lo)}


SPEC = NodeSpec(
    kind="note_to_cc",
    label="Note → CC",
    category="music",
    description=(
        "Linearly remap a MIDI note value into a CC value range. Use "
        "when a downstream destination wants CC but the upstream is "
        "easier to think of in notes (e.g. a stick that sweeps through "
        "octaves can drive a filter cutoff CC instead)."
    ),
    short_description="Linear remap [note_lo..note_hi] → [cc_lo..cc_hi].",
    params=(
        ParamSpec("note_lo", "int", 36,
                  "Lowest input note (default C2 = 36).", minimum=0, maximum=127),
        ParamSpec("note_hi", "int", 84,
                  "Highest input note (default C6 = 84).", minimum=0, maximum=127),
        ParamSpec("cc_lo", "int", 0,
                  "Output value at note_lo.", minimum=0, maximum=127),
        ParamSpec("cc_hi", "int", 127,
                  "Output value at note_hi.", minimum=0, maximum=127),
    ),
    inputs=(PinSpec("in", "in", "MIDI note 0..127.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Remapped CC 0..127.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
