"""Hysteresis — output only changes when input crosses an open/close band.

Schmitt-trigger style behaviour for scalars: the output sticks to its
previous value until the input crosses either ``open_at`` (rising) or
``close_at`` (falling). Use to remove jitter on a stick that hovers
near a CC threshold — no flicker as the value oscillates inside the
hysteresis band.
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
    if state is None:
        state = {}
    open_at = float(params.get("open_at", 0.6))
    close_at = float(params.get("close_at", 0.4))
    if close_at > open_at:
        open_at, close_at = close_at, open_at      # tolerate swap
    high = bool(state.get("high", False))
    if not high and v >= open_at:
        high = True
    elif high and v <= close_at:
        high = False
    state["high"] = high
    return {"out": 1.0 if high else 0.0}


SPEC = NodeSpec(
    kind="hysteresis",
    label="Hysteresis (Schmitt)",
    category="shape",
    description=(
        "Output is 1 while the input is high, 0 while low — but the "
        "thresholds for going up vs. coming back down are different "
        "(open_at > close_at). Removes flicker when the input hovers "
        "near a boundary. Classic Schmitt-trigger shape; common in "
        "audio gates and stick-threshold detectors."
    ),
    short_description="Schmitt-trigger gate with separate up/down thresholds.",
    params=(
        ParamSpec(
            name="open_at", kind="float", default=0.6,
            description="Threshold for output going 0 → 1 (rising edge).",
            minimum=-1.0, maximum=1.0,
        ),
        ParamSpec(
            name="close_at", kind="float", default=0.4,
            description="Threshold for output going 1 → 0 (falling edge). Must be < open_at.",
            minimum=-1.0, maximum=1.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "0 or 1 based on hysteresis state.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
