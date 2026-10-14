"""TapTempo — detect BPM from successive button taps.

Average inter-press interval across the last N taps. Output is BPM
(beats per minute). Use to set a global tempo from a foot-tap on the
controller, then feed into LFO rate / arpeggio interval / etc.

Stateful: holds the timestamps of recent press edges in a small ring.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    if state is None:
        state = {}
    samples = max(2, int(params.get("samples", 4)))
    timeout_s = float(params.get("timeout_ms", 2000)) / 1000.0
    now = time.perf_counter()
    prev = state.get("prev_pressed", False)
    taps = list(state.get("taps", []))

    if pressed and not prev:
        # drop old taps that exceeded the timeout
        if taps and (now - taps[-1]) > timeout_s:
            taps = []
        taps.append(now)
        # keep only the last N
        if len(taps) > samples:
            taps = taps[-samples:]
    state["prev_pressed"] = pressed
    state["taps"] = taps

    if len(taps) < 2:
        return {"out": float(state.get("last_bpm", 0.0))}

    intervals = [taps[i] - taps[i - 1] for i in range(1, len(taps))]
    avg = sum(intervals) / len(intervals)
    bpm = 0.0 if avg == 0 else 60.0 / avg
    state["last_bpm"] = bpm
    return {"out": bpm}


SPEC = NodeSpec(
    kind="tap_tempo",
    label="Tap Tempo",
    category="modulator",
    description=(
        "Tap a button in time to a tempo — outputs BPM averaged over the "
        "last N taps. Idle for `timeout_ms` resets the average so a fresh "
        "tap sequence isn't biased by previous values. Feed into an LFO's "
        "rate or an arpeggiator interval for tempo-synced modulation."
    ),
    short_description="Average BPM from button taps.",
    params=(
        ParamSpec("samples", "int", 4,
                  "Number of taps averaged into the BPM estimate.", minimum=2, maximum=16),
        ParamSpec("timeout_ms", "int", 2000,
                  "Idle window before the tap history resets.",
                  minimum=200, maximum=10000, unit="ms"),
    ),
    inputs=(PinSpec("in", "in", "Button (bool). Rising edges are tapped.", expected="bool"),),
    outputs=(PinSpec("out", "out", "BPM.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
