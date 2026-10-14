"""DoubleClick — fire only when two presses happen within a window.

Specialised case of multi_tap with N=2 — different node so the picker
reads naturally ("I want double-click" finds it). Output is True for a
single tick after the second press, then False until the next pair.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    window_s = float(params.get("window_ms", 350)) / 1000.0
    if state is None:
        state = {}
    now = time.perf_counter()
    prev = state.get("prev_pressed", False)
    last_press = state.get("last_press")

    out = False
    if pressed and not prev:
        if last_press is not None and (now - last_press) <= window_s:
            out = True
            last_press = None    # reset — next pair needs two fresh presses
        else:
            last_press = now
    elif last_press is not None and (now - last_press) > window_s:
        last_press = None        # window elapsed, drop the first press

    state["prev_pressed"] = pressed
    state["last_press"] = last_press
    return {"out": out}


SPEC = NodeSpec(
    kind="double_click",
    label="Double Click",
    category="gate",
    description=(
        "Fire True for one tick after two presses happen within "
        "`window_ms`. Different from multi_tap because it specialises "
        "on exactly two and reads naturally in the node picker."
    ),
    short_description="Fires on double-click within window.",
    params=(
        ParamSpec("window_ms", "int", 350,
                  "Max gap between the two presses. 200 ms = strict, 500 ms = generous.",
                  minimum=80, maximum=1500, unit="ms"),
    ),
    inputs=(PinSpec("in", "in", "Button (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "True for one tick after each double-click.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
