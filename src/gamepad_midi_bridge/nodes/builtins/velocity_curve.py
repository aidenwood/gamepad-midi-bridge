"""VelocityCurve — shape note velocity for expressive note dynamics.

Input: velocity in 0..127. Output: re-shaped velocity. Different from
the generic ``curve`` node because the I/O assumes MIDI's 0..127
integer range, with curve presets chosen for keyboard-velocity feel.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    v = max(0.0, min(127.0, v))
    norm = v / 127.0
    shape = str(params.get("shape", "linear"))
    floor_v = int(params.get("floor", 0))
    ceil_v = int(params.get("ceil", 127))
    if shape == "soft":      # ease-in (lighter touch reads quieter)
        norm = norm * norm
    elif shape == "hard":    # ease-out (lighter touch already loud)
        norm = 1 - (1 - norm) * (1 - norm)
    elif shape == "fixed":   # ignore input — emit ceil
        norm = 1.0
    # else: linear (no shape applied)
    out = floor_v + norm * (ceil_v - floor_v)
    return {"out": max(0.0, min(127.0, out))}


SPEC = NodeSpec(
    kind="velocity_curve",
    label="Velocity Curve",
    category="music",
    description=(
        "Shape MIDI velocity (0..127) for expressive note dynamics. "
        "`soft` makes light taps quieter (more dynamic range); `hard` "
        "compresses so even light taps land loud; `fixed` ignores the "
        "input and emits the ceiling. floor/ceil constrain the output "
        "range so a velocity-sensitive trigger never goes silent or "
        "fully blown."
    ),
    short_description="Reshape MIDI velocity 0..127.",
    params=(
        ParamSpec("shape", "choice", "linear",
                  "Velocity curve. `soft` rewards harder taps; `hard` compresses; `fixed` is a constant velocity.",
                  choices=("linear", "soft", "hard", "fixed")),
        ParamSpec("floor", "int", 0,
                  "Minimum output velocity (even at input=0).",
                  minimum=0, maximum=127),
        ParamSpec("ceil", "int", 127,
                  "Maximum output velocity (input=127 maps here, or `fixed` mode locks here).",
                  minimum=0, maximum=127),
    ),
    inputs=(PinSpec("in", "in", "MIDI velocity 0..127.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Shaped velocity, clamped 0..127.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
