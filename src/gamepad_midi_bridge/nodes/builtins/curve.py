"""Curve — non-linear response shaper for analog inputs.

Stateless 1-in / 1-out scalar transform. Reshapes the 0..1 (or -1..1)
input through one of:

    "linear"   y = x                       (identity passthrough)
    "exp"      y = x^k                     (k>1 compresses low, expands high)
    "log"      y = x^(1/k)                 (k>1 expands low, compresses high)
    "s_curve"  smoothstep variant          (compresses both ends, accelerates middle)
    "deadzone" y = 0 in [-dz..dz], remapped linearly outside (stick drift)

Input is treated as a magnitude — sign is preserved, the curve is applied
to |x|. So bipolar inputs (sticks at -1..1) curve symmetrically.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": 0.0}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": 0.0}
    kind = str(params.get("kind", "linear"))
    k = max(0.0001, float(params.get("k", 2.0)))
    dz = max(0.0, min(1.0, float(params.get("deadzone", 0.05))))

    sign = -1.0 if v < 0 else 1.0
    mag = abs(v)
    mag = min(1.0, mag)

    if kind == "linear":
        out = mag
    elif kind == "exp":
        out = mag ** k
    elif kind == "log":
        out = mag ** (1.0 / k)
    elif kind == "s_curve":
        # Smoothstep with a hard centre. 3x^2 - 2x^3 gives gentle ends.
        out = mag * mag * (3.0 - 2.0 * mag)
    elif kind == "deadzone":
        if mag <= dz:
            out = 0.0
        else:
            # remap (dz..1) → (0..1)
            out = (mag - dz) / (1.0 - dz) if dz < 1.0 else 0.0
    else:
        out = mag

    return {"out": sign * out}


SPEC = NodeSpec(
    kind="curve",
    label="Curve Shaper",
    category="shape",
    description=(
        "Reshape an analog input through a response curve. `linear` is a "
        "passthrough; `exp` (k>1) compresses the low end so small stick "
        "movements stay small (precise control near rest); `log` (k>1) "
        "expands the low end so tiny movements register strongly (sensitive "
        "to nudges); `s_curve` is gentle at both ends with an accelerated "
        "middle (cinematic feel); `deadzone` zeroes everything inside a "
        "centre band and remaps the rest linearly (calibration for drift). "
        "Sign is preserved — bipolar stick inputs curve symmetrically."
    ),
    short_description="Non-linear response shaper.",
    params=(
        ParamSpec(
            name="kind", kind="choice", default="linear",
            description=(
                "Shape family. Pick `exp` for precise control near rest, "
                "`log` for high sensitivity, `s_curve` for cinematic feel, "
                "`deadzone` to ignore stick drift below a threshold."
            ),
            choices=("linear", "exp", "log", "s_curve", "deadzone"),
        ),
        ParamSpec(
            name="k", kind="float", default=2.0,
            description=(
                "Curve steepness for `exp` and `log` shapes. Higher = more "
                "extreme curvature. Ignored for other shape kinds."
            ),
            minimum=0.5, maximum=8.0,
        ),
        ParamSpec(
            name="deadzone", kind="float", default=0.05,
            description=(
                "Magnitude under which the output is forced to 0. Used only "
                "by the `deadzone` shape kind. 0.05 is a good drift-suppress "
                "default for an aging analog stick."
            ),
            minimum=0.0, maximum=0.5,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input (any range, signed OK).", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Curve-shaped scalar with original sign preserved.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
