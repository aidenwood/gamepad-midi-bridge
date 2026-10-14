"""FlickDetect — fire when a stick moves quickly from low magnitude
through a threshold within a short time window.

Stateful: tracks the magnitude trajectory. A "flick" is detected when
the magnitude crosses ``trigger_threshold`` while having risen past
``min_velocity`` (per tick) in the last ``window_ms``. Output is True
for one tick on each detected flick.

Pair with radial_sector + and_gate to detect directional flicks
("flicked east" → trigger).
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if state is None:
        state = {}
    now = time.perf_counter()
    if not isinstance(xy, tuple) or len(xy) != 2:
        state["last_mag"] = 0.0
        state["last_t"] = now
        state["armed"] = True
        return {"out": False}
    x, y = float(xy[0]), float(xy[1])
    mag = math.hypot(x, y)
    threshold = float(params.get("trigger_threshold", 0.7))
    min_vel = float(params.get("min_velocity", 4.0))     # per second
    last_mag = float(state.get("last_mag", 0.0))
    last_t = float(state.get("last_t", now))
    armed = bool(state.get("armed", True))
    dt = max(1e-4, now - last_t)
    velocity = (mag - last_mag) / dt
    fire = False
    if armed and mag >= threshold and velocity >= min_vel:
        fire = True
        armed = False
    elif mag < threshold * 0.5:
        armed = True
    state["last_mag"] = mag
    state["last_t"] = now
    state["armed"] = armed
    return {"out": fire}


SPEC = NodeSpec(
    kind="flick_detect",
    label="Flick Detect",
    category="spatial",
    description=(
        "Fire True for one tick when the stick moves quickly past "
        "`trigger_threshold` with at least `min_velocity` of magnitude "
        "change per second. Re-arms when the stick returns near centre. "
        "Use for gesture triggers — a sharp flick fires a sample, a slow "
        "push doesn't."
    ),
    short_description="Detect sharp stick flicks past threshold.",
    params=(
        ParamSpec("trigger_threshold", "float", 0.7,
                  "Stick magnitude that must be reached to fire.",
                  minimum=0.1, maximum=1.0),
        ParamSpec("min_velocity", "float", 4.0,
                  "Required magnitude change per second. 4 ≈ a deliberate flick; 1 ≈ a slow push.",
                  minimum=0.5, maximum=20.0, unit="/s"),
    ),
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(PinSpec("out", "out", "True for one tick on each detected flick.", expected="bool"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
