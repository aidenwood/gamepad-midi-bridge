"""AttackRelease — AR envelope on a boolean trigger.

Output ramps from 0 → 1 over `attack_ms` while the input is held,
then ramps from current → 0 over `release_ms` after release. Classic
synth-envelope shape on a controller button. Use to drive a parameter
that should fade in cleanly when a button is pressed, sustain while
held, fade out smoothly on release.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    held = bool(inputs.get("in"))
    attack_s = max(0.001, float(params.get("attack_ms", 100)) / 1000.0)
    release_s = max(0.001, float(params.get("release_ms", 300)) / 1000.0)
    if state is None:
        state = {}
    now = time.perf_counter()
    last_now = state.get("last_now", now)
    dt = max(0.0, now - last_now)
    state["last_now"] = now
    out = float(state.get("out", 0.0))
    if held:
        out = min(1.0, out + dt / attack_s)
    else:
        out = max(0.0, out - dt / release_s)
    state["out"] = out
    return {"out": out}


SPEC = NodeSpec(
    kind="attack_release",
    label="Attack / Release",
    category="modulator",
    description=(
        "AR envelope driven by a boolean trigger. Output ramps 0 → 1 "
        "over `attack_ms` while held, ramps current → 0 over "
        "`release_ms` after release. Classic synth shape on a button — "
        "drives a smooth fade-in / fade-out from a momentary input."
    ),
    short_description="Attack / Release envelope on a button.",
    params=(
        ParamSpec(
            name="attack_ms", kind="int", default=100,
            description="Time to rise from 0 to 1 while held.",
            minimum=1, maximum=10000, unit="ms",
        ),
        ParamSpec(
            name="release_ms", kind="int", default=300,
            description="Time to fall from current to 0 after release.",
            minimum=1, maximum=10000, unit="ms",
        ),
    ),
    inputs=(PinSpec("in", "in", "Trigger (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "Envelope value 0..1.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
