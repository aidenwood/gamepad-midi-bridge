"""LiveGate — inverse-panic gate.

The controller is muted by default. While the gate button is held, the input
value passes through; the moment it releases, the output zeroes out and any
downstream sinks emit a "release" message (note-off for buttons, 0 for axes).

Designed for stage use: pocket the controller, hold the gate button (default
D-pad down) on cue to push signal, release to mute again. Inverse of a
classic panic button.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    held = bool(inputs.get("gate"))
    value = inputs.get("value")
    return {"out": value if held else _zero_of(value)}


def _zero_of(v: PinValue) -> PinValue:
    """Same shape as `v`, but zeroed. Lets the wire-type stay consistent."""
    if isinstance(v, bool):
        return False
    if isinstance(v, tuple):
        return tuple(0.0 for _ in v)
    if v is None:
        return None
    return 0.0


SPEC = NodeSpec(
    kind="live_gate",
    label="Live Gate (hold to send)",
    category="gate",
    description=(
        "Pass `value` through ONLY while `gate` is held. Designed as the "
        "inverse of a panic button — the controller sits muted in your "
        "pocket, and holding the gate (default: D-pad down) lights it up "
        "for a cue. On release, downstream sinks get a zero/note-off so "
        "nothing stays stuck."
    ),
    short_description="Pass through only while the gate button is held.",
    params=(
        ParamSpec(
            name="hold_to_release_ms",
            kind="int",
            default=0,
            description=(
                "If > 0, the gate stays open for this many milliseconds after "
                "the button is released — useful for short cues where you want "
                "to tap and let it ride out. 0 = strict momentary."
            ),
            minimum=0,
            maximum=2000,
            unit="ms",
        ),
    ),
    inputs=(
        PinSpec("value", "in", "Signal to gate.", expected="scalar"),
        PinSpec("gate", "in", "Boolean — true while the gate button is held.", expected="bool"),
    ),
    outputs=(
        PinSpec("out", "out", "Same as `value` while held, otherwise zero/false.", expected="scalar"),
    ),
    wire_eligible=False,   # 2 inputs — can't live on a wire
    apply=_apply,
)

NODES = [SPEC]
