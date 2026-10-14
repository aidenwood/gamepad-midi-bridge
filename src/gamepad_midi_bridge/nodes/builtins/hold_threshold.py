"""HoldThreshold — fire only when a button is held for at least N ms.

Different from tap_vs_hold: this is a single-output node that gates the
input bool, suppressing the "press" until the hold threshold is reached.
No tap output; just a delayed gate.

Stateful: tracks press-start time so the hold can be measured.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    threshold_s = float(params.get("threshold_ms", 350)) / 1000.0
    if state is None:
        state = {}
    now = time.perf_counter()
    down_since = state.get("down_since")
    if pressed and down_since is None:
        state["down_since"] = now
        return {"out": False}
    if not pressed:
        state["down_since"] = None
        return {"out": False}
    held_for = now - (down_since or now)
    return {"out": held_for >= threshold_s}


SPEC = NodeSpec(
    kind="hold_threshold",
    label="Hold Threshold",
    category="gate",
    description=(
        "Pass through only when the button has been held continuously for "
        "at least `threshold_ms`. Releases the moment the button releases. "
        "Use when accidental quick taps should be ignored — e.g. a panic "
        "button that needs a half-second commitment to fire."
    ),
    short_description="Output True only after holding for N ms.",
    params=(
        ParamSpec(
            name="threshold_ms", kind="int", default=350,
            description=(
                "Required hold duration before the gate opens. 250 ms is "
                "comfortable for an intentional press; 1000 ms feels like "
                "a 'long-hold to confirm' interaction."
            ),
            minimum=50, maximum=5000, unit="ms",
        ),
    ),
    inputs=(PinSpec("in", "in", "Button state (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "True iff held past threshold.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
