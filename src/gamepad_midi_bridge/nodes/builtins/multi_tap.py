"""MultiTap — count rapid press edges within a window, emit the count.

Press the button N times within `window_ms` of the most-recent press to
emit `count = N`. The count fires ONCE, on the trailing edge of the
window (i.e. after `window_ms` elapses without another press). Pair with
downstream gates to route "single tap → A, double tap → B, triple → C".

Stateful — needs to remember the running tap count, the last-press time,
and whether the trailing-edge fire has been emitted yet:

    "count":       int      — taps accumulated in the current window
    "last_press":  float    — perf_counter of last press edge
    "prev_pressed": bool    — to detect edges
    "fired":       bool     — has the trailing-edge count been emitted?
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    window_s = float(params.get("window_ms", 350)) / 1000.0
    now = time.perf_counter()
    if state is None:
        state = {}

    prev = state.get("prev_pressed", False)
    count = int(state.get("count", 0))
    last_press = state.get("last_press")
    fired = bool(state.get("fired", False))

    emitted: int = 0

    if pressed and not prev:
        # press edge
        count += 1
        last_press = now
        fired = False
    elif last_press is not None and not fired and (now - last_press) >= window_s:
        # trailing edge of the window — emit the count once, then reset
        emitted = count
        count = 0
        last_press = None
        fired = True

    state["prev_pressed"] = pressed
    state["count"] = count
    state["last_press"] = last_press
    state["fired"] = fired
    return {"count": emitted}


SPEC = NodeSpec(
    kind="multi_tap",
    label="Multi-Tap Counter",
    category="gate",
    description=(
        "Count rapid presses within a sliding window and emit the count on "
        "the trailing edge — when `window_ms` elapses without another tap. "
        "Single, double, triple, … taps all route through one output. Pair "
        "with downstream comparison gates to fan out: single = scene A, "
        "double = scene B, triple = scene C. The count is emitted ONCE per "
        "burst; subsequent ticks emit 0 until the next press starts a new "
        "burst."
    ),
    short_description="Counts taps within a window; emits count once.",
    params=(
        ParamSpec(
            name="window_ms",
            kind="int",
            default=350,
            description=(
                "Time the counter waits for another tap before committing. "
                "Lower = strict (only very fast double-taps register as 2); "
                "higher = forgiving but slower to fire single-tap actions."
            ),
            minimum=80,
            maximum=1500,
            unit="ms",
        ),
    ),
    inputs=(PinSpec("in", "in", "Button pressed state (bool).", expected="bool"),),
    outputs=(PinSpec("count", "out", "Tap count, fired once per burst.", expected="scalar"),),
    wire_eligible=True,    # 1-in / 1-out
    apply=_apply,
)

NODES = [SPEC]
