"""ChordDetect — fire only when a set of buttons is held together.

Four boolean inputs (in1..in4). Output is True iff every wired (non-None)
input is True. Unwired pins are treated as "doesn't matter" rather than
"must be False" so the same node spec scales from 2-button to 4-button
chords without separate kinds.

Optional `debounce_ms` — the chord must hold continuously for that many
milliseconds before the output goes True. Stops noisy near-simultaneous
presses from briefly flickering the chord.

Stateful: tracks when the chord first became valid so the debounce can fire.
    "chord_since": float | None — perf_counter when chord first became all-held
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    debounce_s = float(params.get("debounce_ms", 0)) / 1000.0
    wired = [v for v in (inputs.get(f"in{i}") for i in (1, 2, 3, 4)) if v is not None]
    if not wired:
        # Nothing wired — never fire (otherwise the chord would always be
        # "all held" trivially, which is surprising).
        state["chord_since"] = None
        return {"out": False}
    all_held = all(bool(v) for v in wired)
    now = time.perf_counter()
    if not all_held:
        state["chord_since"] = None
        return {"out": False}
    # All held — start or check the debounce window.
    since = state.get("chord_since")
    if since is None:
        state["chord_since"] = now
        return {"out": debounce_s <= 0}  # fire immediately if no debounce
    return {"out": (now - since) >= debounce_s}


SPEC = NodeSpec(
    kind="chord_detect",
    label="Chord Detect (AND)",
    category="logic",
    description=(
        "Fire only when a set of buttons is held together. Wire 2, 3, or 4 "
        "button sources into the in1..in4 pins — unwired pins don't affect "
        "the output. Pair with a downstream gate / mapping to trigger a "
        "scene change on a button combo (e.g. L1 + R1 + Cross). Use the "
        "`debounce_ms` window to suppress flicker from near-simultaneous "
        "presses that should be treated as one event."
    ),
    short_description="True only when all wired buttons are held.",
    params=(
        ParamSpec(
            name="debounce_ms", kind="int", default=0,
            description=(
                "Time the chord must be held continuously before the output "
                "goes True. 0 = fire immediately; 50–100 ms tames noisy "
                "near-simultaneous presses without feeling laggy."
            ),
            minimum=0, maximum=500, unit="ms",
        ),
    ),
    inputs=(
        PinSpec("in1", "in", "First button — required if any pin is wired.", expected="bool"),
        PinSpec("in2", "in", "Second button — leave unwired for 1-button chords.", expected="bool"),
        PinSpec("in3", "in", "Third button — leave unwired for 2-button chords.", expected="bool"),
        PinSpec("in4", "in", "Fourth button — leave unwired for 3-button chords.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "True iff every wired input is held.", expected="bool"),),
    wire_eligible=False,    # multi-input — needs a node card
    apply=_apply,
)

NODES = [SPEC]
