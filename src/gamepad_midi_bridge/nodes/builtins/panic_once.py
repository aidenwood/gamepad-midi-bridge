"""PanicOnce — fire on press EDGE, then lock out until release.

Prevents accidental double-fires on a noisy controller — once a press
edge has emitted True, the output stays False even if the button keeps
bouncing in the held window. Only the release-then-press cycle re-arms.

Pair with destructive actions (reset, hard cut) where one click means
one event, never two.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    if state is None:
        state = {}
    prev = state.get("prev_pressed", False)
    fired = state.get("fired", False)
    out = False
    if pressed and not prev and not fired:
        # Press edge, not yet fired this cycle — emit.
        out = True
        fired = True
    if not pressed:
        # Release — re-arm.
        fired = False
    state["prev_pressed"] = pressed
    state["fired"] = fired
    return {"out": out}


SPEC = NodeSpec(
    kind="panic_once",
    label="Panic (fire once)",
    category="gate",
    description=(
        "Fire True for exactly one tick on the press EDGE, then stay "
        "False until the button is released. Re-arms on release. Use for "
        "destructive actions (reset, panic, hard cut) where you want one "
        "click to mean one event regardless of how long the button is "
        "held or whether the contact bounces."
    ),
    short_description="One-shot on press edge.",
    inputs=(PinSpec("in", "in", "Button state (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "True for one tick per press edge.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
