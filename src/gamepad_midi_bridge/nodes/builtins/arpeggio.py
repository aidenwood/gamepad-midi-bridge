"""Arpeggio — while a button is held, fire repeated boolean pulses at a
fixed interval. One press → many downstream events.

Each pulse is True for exactly one tick (matches what destinations
expect for "press" events). Pulse rate independent of the bridge's
poll rate — uses wall-clock to stay accurate even under jitter.

Stateful: tracks last-fire time + held state. Resets on release.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    held = bool(inputs.get("in"))
    interval_ms = max(20, int(params.get("interval_ms", 200)))
    interval_s = interval_ms / 1000.0
    if state is None:
        state = {}
    now = time.perf_counter()
    prev_held = state.get("prev_held", False)
    last_fire = state.get("last_fire")
    out = False

    if held and not prev_held:
        # press edge — fire immediately (matches typical key-repeat UX).
        out = True
        last_fire = now
    elif held and last_fire is not None:
        if now - last_fire >= interval_s:
            out = True
            last_fire = now
    elif not held:
        last_fire = None

    state["prev_held"] = held
    state["last_fire"] = last_fire
    return {"out": out}


SPEC = NodeSpec(
    kind="arpeggio",
    label="Arpeggio (repeat-while-held)",
    category="modulator",
    description=(
        "Hold a button and the output fires a True pulse every "
        "`interval_ms`. First fire is immediate on the press edge, "
        "subsequent fires repeat until release. Classic key-repeat / "
        "arpeggio behaviour — one physical press becomes many downstream "
        "events. Pair with a chromatic note generator for an instant "
        "arpeggiator from a single button."
    ),
    short_description="One press → repeating pulses while held.",
    params=(
        ParamSpec(
            name="interval_ms", kind="int", default=200,
            description=(
                "Time between repeat pulses. 100 ms ≈ 10 fires/sec, 60 ms "
                "≈ 16th notes at 156 BPM, 250 ms ≈ comfortable arpeggiator."
            ),
            minimum=20, maximum=2000, unit="ms",
        ),
    ),
    inputs=(PinSpec("in", "in", "Button held state (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "True for one tick per repeat interval while held.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
