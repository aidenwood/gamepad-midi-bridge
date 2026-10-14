"""NoiseRandom — emit a new random value at a fixed rate.

Free-running noise generator. Value stays constant between rolls;
``rate_hz`` controls how often a new random value is picked. Pair into
a downstream sink to drive 'controlled chaos' modulation that doesn't
flicker frame-to-frame.
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    rate = max(0.01, float(params.get("rate_hz", 1.0)))
    now = time.perf_counter()
    next_at = state.get("next_at", 0.0)
    val = state.get("value", random.random())
    if now >= next_at:
        val = random.random()
        next_at = now + (1.0 / rate)
        state["next_at"] = next_at
        state["value"] = val
    return {"out": val}


SPEC = NodeSpec(
    kind="noise_random",
    label="Random Noise",
    category="modulator",
    description=(
        "Free-running random generator. Picks a new value in [0..1] "
        "every `1/rate_hz` seconds; output holds steady between rolls. "
        "Pair with a smooth_lerp downstream for soft chaos modulation, "
        "or feed straight into a CC sink for sample-and-hold randomness."
    ),
    short_description="New random 0..1 at a fixed rate.",
    params=(
        ParamSpec("rate_hz", "float", 1.0,
                  "Rolls per second. 0.5 = once every 2 s, 10 = ten times a second.",
                  minimum=0.01, maximum=60.0, unit="Hz"),
    ),
    inputs=(),
    outputs=(PinSpec("out", "out", "Current random value 0..1.", expected="scalar"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
