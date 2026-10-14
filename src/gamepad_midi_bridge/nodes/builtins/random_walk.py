"""RandomWalk — drift a value by small random steps each tick.

Distinct from noise_random (which jumps to fresh random values at a
rate): this one accumulates small deltas so the output is a CONTINUOUS
random walk. Bounded to [0..1] by reflecting off the edges.

Useful for slow organic modulation that never quite repeats — set
``step_size`` low (0.01-ish) for a wandering filter cutoff or pan
position that feels alive but not chaotic.
"""
from __future__ import annotations

import random
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    step = max(0.0001, float(params.get("step_size", 0.01)))
    val = float(state.get("value", 0.5))
    # Symmetric step in [-step, +step], reflect off boundaries.
    val += (random.random() * 2.0 - 1.0) * step
    if val < 0.0:
        val = -val
    if val > 1.0:
        val = 2.0 - val
    val = max(0.0, min(1.0, val))
    state["value"] = val
    return {"out": val}


SPEC = NodeSpec(
    kind="random_walk",
    label="Random Walk",
    category="modulator",
    description=(
        "Drift the output value by a small random step every tick. "
        "Bounded to [0..1] — reflects off the edges instead of clipping. "
        "Different from noise_random because the value evolves "
        "continuously rather than jumping. Tune step_size to dial in "
        "the wandering speed."
    ),
    short_description="Slow continuous random drift in [0..1].",
    params=(
        ParamSpec("step_size", "float", 0.01,
                  "Maximum delta per tick. 0.005 = very slow, 0.05 = jittery.",
                  minimum=0.0001, maximum=0.5),
    ),
    inputs=(),
    outputs=(PinSpec("out", "out", "Current random-walk value 0..1.", expected="scalar"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
