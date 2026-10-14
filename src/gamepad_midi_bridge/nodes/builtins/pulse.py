"""Pulse — emit True for a fixed duration on each rising edge of the input.

One-shot timed pulse. Press releases a `duration_ms` square pulse
downstream regardless of how long the button is held. Pair to fire a
sample for an exact length, or to gate an effect for a fixed window.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    duration_s = max(0.001, float(params.get("duration_ms", 100)) / 1000.0)
    if state is None:
        state = {}
    now = time.perf_counter()
    prev = state.get("prev_pressed", False)
    pulse_until = state.get("pulse_until", 0.0)
    if pressed and not prev:
        pulse_until = now + duration_s
    state["prev_pressed"] = pressed
    state["pulse_until"] = pulse_until
    return {"out": now < pulse_until}


SPEC = NodeSpec(
    kind="pulse",
    label="Pulse (timed one-shot)",
    category="gate",
    description=(
        "Emit True for exactly `duration_ms` milliseconds on each rising "
        "edge of the input. Duration is independent of how long the "
        "button is held — even a quick tap produces a full-length pulse. "
        "Use for fixed-length sample triggers, effect gates, or timed cues."
    ),
    short_description="Press → fixed-length True pulse.",
    params=(
        ParamSpec("duration_ms", "int", 100,
                  "Pulse length in milliseconds.",
                  minimum=1, maximum=10000, unit="ms"),
    ),
    inputs=(PinSpec("in", "in", "Trigger (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "True during the active pulse window.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
