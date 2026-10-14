"""SmoothLerp — exponential smoothing (1st-order low-pass).

Maps a noisy input stream to a smoother output that lags by ~1/alpha
ticks behind the source. TouchDesigner's Lag CHOP equivalent. Use
between a noisy stick reading and a CC sink to take the jitter out of
hand-held controllers, or to give an LFO a soft "ease" rather than a
linear ramp.

Stateful: keeps the previous output so each tick's smoothed value is
``out = out_prev + alpha * (in - out_prev)``. Reset on first tick.
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
    alpha = max(0.001, min(1.0, float(params.get("alpha", 0.15))))
    prev = state.get("out_prev")
    if prev is None:
        prev = v          # seed on first tick so we don't ramp from 0
    out = prev + alpha * (v - prev)
    state["out_prev"] = out
    return {"out": out}


SPEC = NodeSpec(
    kind="smooth_lerp",
    label="Smooth (lerp)",
    category="shape",
    description=(
        "Exponential smoothing — each tick the output moves a fraction "
        "`alpha` of the way toward the input. Low alpha = very smooth + "
        "slow to react, high alpha = barely smoothed. Cheap first-order "
        "low-pass; great for taking hand-jitter out of a stick before "
        "sending into a continuous CC."
    ),
    short_description="Exponential low-pass smoothing.",
    params=(
        ParamSpec(
            name="alpha", kind="float", default=0.15,
            description=(
                "Smoothing weight per tick. 1.0 = passthrough, 0.5 = ~2-tick "
                "lag, 0.1 = ~10-tick lag, 0.02 = very smooth. Bridge default "
                "poll rate is 100 Hz so the tick is 10 ms."
            ),
            minimum=0.001, maximum=1.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar to smooth.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Smoothed scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
