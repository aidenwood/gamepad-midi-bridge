"""ArpeggiatorPattern — cycle through chord notes at a fixed rate.

Takes 3 note inputs (designed to chain after chord_build), emits the
notes one at a time on an internal clock. Pattern picks the sequence:
up = 1→2→3→1..., down = 3→2→1→3..., updown = 1→2→3→2→1→2..., random.

Output is the currently-active note. Gate (bool) controls whether the
arp is running; releases freeze on the last note.
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _next_index(pattern: str, current: int, n: int, state: dict) -> int:
    """Return the next note index based on pattern + current position."""
    if n <= 0:
        return 0
    if pattern == "down":
        return (current - 1) % n
    if pattern == "updown":
        direction = state.get("direction", 1)
        nxt = current + direction
        if nxt >= n - 1:
            direction = -1
        elif nxt <= 0:
            direction = 1
        state["direction"] = direction
        return max(0, min(n - 1, nxt))
    if pattern == "random":
        return random.randrange(n)
    # default: "up"
    return (current + 1) % n


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    gate = bool(inputs.get("gate"))
    rate_hz = max(0.1, float(params.get("rate_hz", 4.0)))
    pattern = str(params.get("pattern", "up"))
    notes = [inputs.get("note1"), inputs.get("note2"), inputs.get("note3")]
    notes = [n for n in notes if n is not None]
    if not notes:
        return {"out": 0.0}
    if not gate:
        return {"out": float(state.get("last", notes[0]))}
    now = time.perf_counter()
    last_t = state.get("last_t", 0.0)
    idx = int(state.get("idx", 0))
    if now - last_t >= 1.0 / rate_hz:
        idx = _next_index(pattern, idx, len(notes), state)
        state["last_t"] = now
    state["idx"] = idx
    note = notes[idx]
    state["last"] = note
    return {"out": float(note) if note is not None else 0.0}


SPEC = NodeSpec(
    kind="arpeggiator_pattern",
    label="Arpeggiator Pattern",
    category="music",
    description=(
        "Cycle through chord notes at a fixed rate. Designed to chain "
        "after chord_build: takes the 3 note pins, picks one at a time "
        "in `pattern` order. `gate` controls whether the arp is running "
        "— release freezes on the last-played note."
    ),
    short_description="Cycle chord notes at a rate.",
    params=(
        ParamSpec("rate_hz", "float", 4.0,
                  "Notes per second. 4 ≈ 16th notes at 60 BPM.",
                  minimum=0.5, maximum=30.0, unit="Hz"),
        ParamSpec("pattern", "choice", "up",
                  "Note order: up cycles 1→2→3, down reverses, updown ping-pongs, random picks at random.",
                  choices=("up", "down", "updown", "random")),
    ),
    inputs=(
        PinSpec("note1", "in", "Chord tone 1.", expected="scalar"),
        PinSpec("note2", "in", "Chord tone 2.", expected="scalar"),
        PinSpec("note3", "in", "Chord tone 3.", expected="scalar"),
        PinSpec("gate", "in", "While True, the arp advances; False freezes.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "Currently-active note.", expected="scalar"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
