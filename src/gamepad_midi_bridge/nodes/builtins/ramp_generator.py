"""RampGenerator — single press → a timed curve from 0 → 1 → 0.

The shape the user asked for: one button press triggers a customisable
ramp envelope. Different from attack_release in that the ramp plays out
on its own once triggered — you don't have to keep the button held.

Three phases: attack (0 → 1 over ``attack_ms``), sustain (hold at 1
for ``sustain_ms``), release (1 → 0 over ``release_ms``). Triggered on
the rising edge of the input. Re-triggering mid-ramp restarts from 0.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    if state is None:
        state = {}
    a_s = max(0.001, float(params.get("attack_ms", 100)) / 1000.0)
    s_s = max(0.0, float(params.get("sustain_ms", 200)) / 1000.0)
    r_s = max(0.001, float(params.get("release_ms", 400)) / 1000.0)
    now = time.perf_counter()
    prev = state.get("prev_pressed", False)
    start = state.get("start")

    if pressed and not prev:
        start = now      # press edge → fire
    state["prev_pressed"] = pressed
    state["start"] = start

    if start is None:
        return {"out": 0.0}
    elapsed = now - start
    if elapsed < a_s:
        return {"out": elapsed / a_s}
    if elapsed < a_s + s_s:
        return {"out": 1.0}
    if elapsed < a_s + s_s + r_s:
        return {"out": max(0.0, 1.0 - (elapsed - a_s - s_s) / r_s)}
    # Ramp done — auto-reset so the next press fires cleanly.
    state["start"] = None
    return {"out": 0.0}


SPEC = NodeSpec(
    kind="ramp_generator",
    label="Ramp Generator (one-shot envelope)",
    category="modulator",
    description=(
        "One button press triggers a timed curve from 0 → 1 → 0 that "
        "plays out on its own — you don't keep the button held. Three "
        "phases: attack (rise), sustain (hold at 1), release (fall). "
        "Use to fire a smooth automated sweep from a single tap — fade-"
        "in / hold / fade-out without manual envelope-riding."
    ),
    short_description="One press → AR envelope plays through.",
    params=(
        ParamSpec("attack_ms", "int", 100,
                  "Time to rise from 0 to 1 after press.", minimum=1, maximum=10000, unit="ms"),
        ParamSpec("sustain_ms", "int", 200,
                  "Time to hold at 1 before falling. 0 = instant peak → release.",
                  minimum=0, maximum=10000, unit="ms"),
        ParamSpec("release_ms", "int", 400,
                  "Time to fall from 1 back to 0.", minimum=1, maximum=10000, unit="ms"),
    ),
    inputs=(PinSpec("in", "in", "Trigger (bool). Rising edge fires the ramp.", expected="bool"),),
    outputs=(PinSpec("out", "out", "Envelope value 0..1 over time.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
