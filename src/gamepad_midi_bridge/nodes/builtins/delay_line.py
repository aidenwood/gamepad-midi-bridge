"""DelayLine — output the value from N ticks ago.

Stateful ring buffer of recent inputs. Used to delay a signal by an
exact number of bridge poll ticks (default 100 Hz so delay_ticks=50 ≈
500 ms). Pair with a sample_hold or smooth_lerp for richer time-based
sculpting (echo-style modulation, late LFOs).

Buffer size is capped at MAX_BUFFER ticks to bound memory.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


MAX_BUFFER = 1024


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    v = inputs.get("in")
    delay_ticks = max(0, min(MAX_BUFFER, int(params.get("delay_ticks", 10))))
    buf = state.get("buf")
    if buf is None or buf.maxlen != delay_ticks + 1:
        # (Re-)build the buffer when the delay length changes.
        old = list(buf) if buf is not None else []
        buf = deque(old, maxlen=delay_ticks + 1)
        # Pre-fill so early ticks emit None rather than empty.
        while len(buf) < buf.maxlen:
            buf.appendleft(None)
        state["buf"] = buf
    buf.append(v)
    return {"out": buf[0]}


SPEC = NodeSpec(
    kind="delay_line",
    label="Delay Line",
    category="modulator",
    description=(
        "Emit the value from `delay_ticks` ago. Bridge polls at 100 Hz so "
        "delay_ticks=50 ≈ 500 ms latency. Useful for tap-delay-style "
        "effects on continuous CC or for staggering parallel destinations "
        "(send to one CC instantly, send to another 200 ms later)."
    ),
    short_description="Value from N ticks ago.",
    params=(
        ParamSpec(
            name="delay_ticks", kind="int", default=10,
            description="Tick delay. 100 ticks ≈ 1 s at the default 100 Hz poll rate.",
            minimum=0, maximum=MAX_BUFFER, unit="ticks",
        ),
    ),
    inputs=(PinSpec("in", "in", "Value to delay.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Value from N ticks ago.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
