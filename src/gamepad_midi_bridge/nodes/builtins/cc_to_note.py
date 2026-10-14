"""CcToNote — linearly remap a CC value into a MIDI note range."""
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
    cc_lo = float(params.get("cc_lo", 0))
    cc_hi = float(params.get("cc_hi", 127))
    note_lo = float(params.get("note_lo", 36))
    note_hi = float(params.get("note_hi", 84))
    if cc_hi == cc_lo:
        return {"out": note_lo}
    v = max(cc_lo, min(cc_hi, v))
    t = (v - cc_lo) / (cc_hi - cc_lo)
    return {"out": note_lo + t * (note_hi - note_lo)}


SPEC = NodeSpec(
    kind="cc_to_note",
    label="CC → Note",
    category="music",
    description=(
        "Remap a CC value (0..127) into a MIDI note range. Inverse of "
        "note_to_cc — use when a stick-driven CC should pick a note "
        "value to feed into a downstream music op (scale_quantize, "
        "chord_build, transpose)."
    ),
    short_description="Linear remap [cc_lo..cc_hi] → [note_lo..note_hi].",
    params=(
        ParamSpec("cc_lo", "int", 0, "Lowest input CC value.", minimum=0, maximum=127),
        ParamSpec("cc_hi", "int", 127, "Highest input CC value.", minimum=0, maximum=127),
        ParamSpec("note_lo", "int", 36, "Output note at cc_lo. Default C2.", minimum=0, maximum=127),
        ParamSpec("note_hi", "int", 84, "Output note at cc_hi. Default C6.", minimum=0, maximum=127),
    ),
    inputs=(PinSpec("in", "in", "CC value 0..127.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Remapped MIDI note.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
