"""LatchValue — pass `value` while `gate` is held, freeze on release.

Different from sample_hold (which is edge-triggered): this is LEVEL-
gated. Output tracks `value` while `gate` is True; freezes at the last-
seen value the moment `gate` goes False.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    gate = bool(inputs.get("gate"))
    if gate:
        state["held"] = inputs.get("value")
    return {"out": state.get("held", 0.0)}


SPEC = NodeSpec(
    kind="latch_value",
    label="Latch Value (gated track)",
    category="gate",
    description=(
        "Track `value` while `gate` is held; freeze at the last-tracked "
        "value when `gate` releases. Level-gated alternative to "
        "sample_hold (which captures only on the trigger edge). Useful "
        "for 'hold to record current stick position' interactions."
    ),
    short_description="Track value while gate held, freeze on release.",
    inputs=(
        PinSpec("value", "in", "Signal to track.", expected="scalar"),
        PinSpec("gate", "in", "While True, output tracks value.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "Tracked or last-frozen value.", expected="scalar"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
