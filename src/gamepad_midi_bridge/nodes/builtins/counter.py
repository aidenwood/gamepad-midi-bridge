"""Counter — increment by step on each press edge. Wraps at max.

Output is a normalised 0..1 representation of the current count so the
node plays cleanly with CC sinks. Internal step is fixed-int; the
fractional output is `count / max_count`.

Use to cycle through N values from a single button (e.g. tap to step
through 8 scenes, wraps back to 0 on the 9th press).
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    if state is None:
        state = {}
    max_n = max(1, int(params.get("max_count", 8)))
    prev = state.get("prev_pressed", False)
    count = int(state.get("count", 0))
    if pressed and not prev:
        count = (count + 1) % max_n
    if bool(inputs.get("reset")):
        count = 0
    state["prev_pressed"] = pressed
    state["count"] = count
    return {"out": count / max(1, max_n - 1) if max_n > 1 else 0.0,
            "count": count}


SPEC = NodeSpec(
    kind="counter",
    label="Counter",
    category="logic",
    description=(
        "Increment by 1 on every press edge, wraps at `max_count`. "
        "Outputs both a normalised 0..1 fraction (CC-friendly) and the "
        "raw integer count. Pair with a step_quantize downstream to "
        "cycle through N preset values per button press."
    ),
    short_description="Press → count, wraps at max.",
    params=(
        ParamSpec("max_count", "int", 8,
                  "Wrap point. After this many presses, counter resets to 0.",
                  minimum=2, maximum=128),
    ),
    inputs=(
        PinSpec("in", "in", "Trigger (bool). Rising edges increment.", expected="bool"),
        PinSpec("reset", "in", "While True, count holds at 0.", expected="bool"),
    ),
    outputs=(
        PinSpec("out", "out", "Normalised 0..1 fraction of the count.", expected="scalar"),
        PinSpec("count", "out", "Raw integer count.", expected="scalar"),
    ),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
