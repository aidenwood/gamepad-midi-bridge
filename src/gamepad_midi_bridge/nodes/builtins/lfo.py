"""LFO — auto-modulating value generator.

A free-running low-frequency oscillator. Drops onto any wire to give a
downstream parameter constant evolution without manual stick motion.
Reuses the project's existing waveform math (`lfo_waveforms.evaluate`)
so the output shape matches the rest of the modulator system.

Stateful — needs to advance `phase` each tick by `rate / sample_rate`,
where `sample_rate` is the bridge's poll rate (default 100 Hz). We track
real wall-clock time instead of tick count to stay frequency-accurate
even when the bridge loop has variable jitter:

    "last_tick":  float  — perf_counter of previous evaluation
    "phase":      float  — 0..1, advanced each tick

Output is always 0..1 (matches the waveform math). Pair with a downstream
range_remap node if you want a different range.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue
from ...lfo_waveforms import evaluate as _lfo_evaluate


_SHAPES = ("sine", "triangle", "ramp_up", "ramp_down", "square")


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    rate = max(0.001, float(params.get("rate_hz", 1.0)))
    shape = str(params.get("shape", "sine"))
    duty = max(0.05, min(0.95, float(params.get("duty", 0.5))))
    if state is None:
        state = {}
    now = time.perf_counter()
    last = state.get("last_tick", now)
    dt = max(0.0, now - last)
    phase = (state.get("phase", 0.0) + dt * rate) % 1.0
    state["last_tick"] = now
    state["phase"] = phase
    return {"out": float(_lfo_evaluate(shape, phase, duty))}


SPEC = NodeSpec(
    kind="lfo",
    label="LFO (free-running)",
    category="modulator",
    description=(
        "A free-running low-frequency oscillator. Drops onto any wire to "
        "give a downstream parameter constant evolution without manual "
        "stick motion. Pick a `shape` (sine, triangle, ramp_up, ramp_down, "
        "square) and a `rate_hz` (cycles per second). Output is 0..1 — "
        "pair with a range_remap downstream if you need a different range. "
        "Phase advances in real wall-clock time so the LFO stays frequency-"
        "accurate even if the bridge poll loop has variable jitter."
    ),
    short_description="Free-running 0..1 oscillator.",
    params=(
        ParamSpec(
            name="rate_hz", kind="float", default=1.0,
            description=(
                "Cycles per second. 1 Hz = one full waveform every second. "
                "Useful for slow auto-pans (0.1–0.5 Hz) up to audio-rate "
                "modulation (5–20 Hz — interesting visual flicker, not "
                "audible since this is MIDI control, not audio)."
            ),
            minimum=0.01, maximum=30.0, unit="Hz",
        ),
        ParamSpec(
            name="shape", kind="choice", default="sine",
            description=(
                "Waveform. `sine` for organic motion, `triangle` for "
                "linear sweep-and-return, `ramp_up`/`ramp_down` for "
                "sawtooth (sharp reset), `square` for hard on/off."
            ),
            choices=_SHAPES,
        ),
        ParamSpec(
            name="duty", kind="float", default=0.5,
            description=(
                "Duty cycle for the `square` shape — 0.5 = symmetric, "
                ">0.5 = wider 'high' phase. Ignored for other shapes."
            ),
            minimum=0.05, maximum=0.95,
        ),
    ),
    inputs=(),  # free-running — no inputs to react to
    outputs=(PinSpec("out", "out", "0..1 waveform value at the current phase.", expected="scalar"),),
    wire_eligible=False,    # 0-in 1-out — not strictly 1-in, can't sit on a wire
    apply=_apply,
)

NODES = [SPEC]
