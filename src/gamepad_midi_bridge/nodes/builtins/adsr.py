"""ADSR — full envelope on a boolean trigger.

While input is held: ramp 0 → 1 over attack_ms, then settle to sustain
level over decay_ms, then hold at sustain. On release: ramp current →
0 over release_ms. Classic synth envelope shape on a button.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    held = bool(inputs.get("in"))
    a_s = max(0.001, float(params.get("attack_ms", 50)) / 1000.0)
    d_s = max(0.001, float(params.get("decay_ms", 100)) / 1000.0)
    sustain = max(0.0, min(1.0, float(params.get("sustain", 0.6))))
    r_s = max(0.001, float(params.get("release_ms", 200)) / 1000.0)
    if state is None:
        state = {}
    now = time.perf_counter()
    last = state.get("last_t", now)
    dt = max(0.0, now - last)
    state["last_t"] = now
    phase = state.get("phase", "off")
    out = float(state.get("out", 0.0))
    prev_held = state.get("prev_held", False)

    if held and not prev_held:
        phase = "attack"
    elif not held and prev_held:
        phase = "release"

    if phase == "attack":
        out = min(1.0, out + dt / a_s)
        if out >= 1.0:
            phase = "decay"
    elif phase == "decay":
        if out > sustain:
            out = max(sustain, out - dt / d_s)
        else:
            phase = "sustain"
    elif phase == "sustain":
        out = sustain
    elif phase == "release":
        out = max(0.0, out - dt / r_s)
        if out <= 0.0:
            phase = "off"

    state["phase"] = phase
    state["out"] = out
    state["prev_held"] = held
    return {"out": out}


SPEC = NodeSpec(
    kind="adsr",
    label="ADSR Envelope",
    category="modulator",
    description=(
        "Full Attack-Decay-Sustain-Release envelope driven by a boolean "
        "trigger. Holds at `sustain` level while held; releases on let-"
        "go. Classic synth envelope shape — drives smooth fade-in / "
        "settle / fade-out from a momentary input."
    ),
    short_description="ADSR envelope on a button.",
    params=(
        ParamSpec("attack_ms", "int", 50,
                  "Time to rise from 0 to 1.", minimum=1, maximum=10000, unit="ms"),
        ParamSpec("decay_ms", "int", 100,
                  "Time to fall from 1 to sustain level.", minimum=1, maximum=10000, unit="ms"),
        ParamSpec("sustain", "float", 0.6,
                  "Held level while button stays pressed.", minimum=0.0, maximum=1.0),
        ParamSpec("release_ms", "int", 200,
                  "Time to fall from sustain to 0 after release.", minimum=1, maximum=10000, unit="ms"),
    ),
    inputs=(PinSpec("in", "in", "Trigger (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "Envelope value 0..1.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
