"""TapVsHold — split one button into two outputs based on press duration.

A quick press releases through ``tap`` (single momentary pulse on the release
edge). A long hold fires ``hold`` for the duration the button is held past
the threshold. Lets a single physical button drive a "preset 1 / preset 2"
or a "trigger sample / scrub through sample" split without rebinding.

Stateful: needs to remember when each press started, so it relies on the
evaluator-owned ``state`` dict. Tracks two keys:

    "down_since": float | None    — perf_counter at press start, or None
    "fired_hold": bool            — has this press already crossed the threshold?
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    threshold_ms = float(params.get("threshold_ms", 250))
    threshold_s = threshold_ms / 1000.0
    now = time.perf_counter()

    if state is None:
        state = {}
    down_since = state.get("down_since")
    fired_hold = state.get("fired_hold", False)

    tap = False
    hold = False

    if pressed and down_since is None:
        # press edge
        state["down_since"] = now
        state["fired_hold"] = False
    elif pressed and down_since is not None:
        # still held — once past threshold, hold stays True
        if (now - down_since) >= threshold_s:
            hold = True
            state["fired_hold"] = True
    elif not pressed and down_since is not None:
        # release edge — fire tap iff we never crossed the hold threshold
        held_for = now - down_since
        if held_for < threshold_s and not fired_hold:
            tap = True
        state["down_since"] = None
        state["fired_hold"] = False

    return {"tap": tap, "hold": hold}


SPEC = NodeSpec(
    kind="tap_vs_hold",
    label="Tap vs Hold",
    category="gate",
    description=(
        "Split one button into two outputs based on how long it's held. A "
        "short press releases through `tap` as a single pulse on the release "
        "edge. A press that crosses the `threshold_ms` threshold while still "
        "held emits through `hold` for the duration. Lets one physical "
        "button drive two distinct downstream destinations (e.g. tap to "
        "fire a sample, hold to nudge a loop point)."
    ),
    short_description="Button → tap pulse or sustained hold.",
    params=(
        ParamSpec(
            name="threshold_ms",
            kind="int",
            default=250,
            description=(
                "Press duration that distinguishes a tap from a hold. Anything "
                "shorter fires `tap` on release; anything longer fires `hold` "
                "while held. Defaults to 250 ms — comfortable for finger taps "
                "without being so short that an intentional hold is missed."
            ),
            minimum=50,
            maximum=2000,
            unit="ms",
        ),
    ),
    inputs=(PinSpec("in", "in", "Button pressed state (bool).", expected="bool"),),
    outputs=(
        PinSpec("tap", "out", "True for one tick on release after a short press.", expected="bool"),
        PinSpec("hold", "out", "True while held past the threshold.", expected="bool"),
    ),
    wire_eligible=False,    # 2 outputs — needs a node card
    apply=_apply,
)

NODES = [SPEC]
