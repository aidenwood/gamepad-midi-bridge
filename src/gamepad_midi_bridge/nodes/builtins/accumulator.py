"""Accumulator — integrate the input value over time.

Each tick, ``out += input * rate``. Clamped to [min..max] so it can't
run away. Reset to ``reset_value`` on the rising edge of an optional
``reset`` boolean input.

Useful for drift-style controls — push a stick to ramp a parameter up
or down, release to hold its current value. Or chain after a button to
build a "press to count up" interaction.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    raw = inputs.get("in")
    delta = 0.0
    if raw is not None and not isinstance(raw, tuple):
        try:
            delta = float(raw)
        except (TypeError, ValueError):
            delta = 0.0
    rate = float(params.get("rate", 0.01))
    lo = float(params.get("min", 0.0))
    hi = float(params.get("max", 1.0))
    if lo > hi:
        lo, hi = hi, lo
    reset_value = float(params.get("reset_value", 0.0))

    # Reset edge.
    reset_now = bool(inputs.get("reset"))
    prev_reset = state.get("prev_reset", False)
    cur = state.get("value", reset_value)
    if reset_now and not prev_reset:
        cur = reset_value
    state["prev_reset"] = reset_now

    cur = cur + delta * rate
    cur = max(lo, min(hi, cur))
    state["value"] = cur
    return {"out": cur}


SPEC = NodeSpec(
    kind="accumulator",
    label="Accumulator",
    category="modulator",
    description=(
        "Integrate the input over time. Each tick the output gets `input * "
        "rate` added to it, clamped to [min..max]. Push a stick forward to "
        "ramp the output up, push backward to ramp down, release to hold. "
        "The optional `reset` boolean snaps the value back to `reset_value` "
        "on a rising edge — pair with a button to zero the counter on demand."
    ),
    short_description="Integrate over time, clamped.",
    params=(
        ParamSpec(
            name="rate", kind="float", default=0.01,
            description="Multiplier applied to the input each tick before accumulating.",
            minimum=-1.0, maximum=1.0,
        ),
        ParamSpec(
            name="min", kind="float", default=0.0,
            description="Lower clamp. Accumulator never goes below this.",
            minimum=-127.0, maximum=127.0,
        ),
        ParamSpec(
            name="max", kind="float", default=1.0,
            description="Upper clamp. Accumulator never goes above this.",
            minimum=-127.0, maximum=127.0,
        ),
        ParamSpec(
            name="reset_value", kind="float", default=0.0,
            description="Value to snap to when reset's rising edge fires.",
            minimum=-127.0, maximum=127.0,
        ),
    ),
    inputs=(
        PinSpec("in", "in", "Per-tick delta source.", expected="scalar"),
        PinSpec("reset", "in", "Rising edge resets the accumulator.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "Running accumulated value, clamped.", expected="scalar"),),
    wire_eligible=False,    # 2 inputs — can't sit on a wire
    apply=_apply,
)

NODES = [SPEC]
