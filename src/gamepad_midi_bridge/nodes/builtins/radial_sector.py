"""RadialSector — convert a stick angle into a discrete sector index.

8-way directional output common in fighting-game inputs. The stick's
angle (atan2 from x, y) is divided into N equal wedges; output is the
sector index 0..N-1 (or -1 if magnitude is below the threshold).

Pair with comparator + and_gate to detect specific directions
("North-east only") for gesture-style triggers.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if not isinstance(xy, tuple) or len(xy) != 2:
        return {"sector": -1.0, "active": False}
    x, y = float(xy[0]), float(xy[1])
    mag = math.hypot(x, y)
    threshold = float(params.get("threshold", 0.3))
    sectors = max(2, int(params.get("sectors", 8)))
    if mag < threshold:
        return {"sector": -1.0, "active": False}
    # atan2 returns -pi..pi. Shift so 0° = North (up), then mod by 2π.
    angle = math.atan2(x, -y)        # +X right, +Y up (Qt's coords are flipped)
    if angle < 0:
        angle += 2 * math.pi
    sector = int((angle / (2 * math.pi)) * sectors) % sectors
    return {"sector": float(sector), "active": True}


SPEC = NodeSpec(
    kind="radial_sector",
    label="Radial Sector",
    category="spatial",
    description=(
        "Divide the stick's circular range into N equal wedges and emit "
        "the active sector index. 8 sectors = N/NE/E/SE/S/SW/W/NW. "
        "Threshold gates output — small wiggles near centre return -1 "
        "so the sector indicator doesn't strobe."
    ),
    short_description="Stick angle → sector 0..N-1.",
    params=(
        ParamSpec("sectors", "int", 8,
                  "Number of equal wedges around the stick's full revolution.",
                  minimum=2, maximum=16),
        ParamSpec("threshold", "float", 0.3,
                  "Magnitude below which no sector fires (output = -1).",
                  minimum=0.0, maximum=1.0),
    ),
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(
        PinSpec("sector", "out", "Active sector index 0..N-1, or -1.", expected="scalar"),
        PinSpec("active", "out", "True iff magnitude past threshold.", expected="bool"),
    ),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
