"""Vec2Swap — swap X and Y of a 2D input. Identity for scalars."""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if isinstance(xy, tuple) and len(xy) == 2:
        return {"out": (float(xy[1]), float(xy[0]))}
    return {"out": xy}


SPEC = NodeSpec(
    kind="vec2_swap",
    label="Vec2 Swap (X↔Y)",
    category="spatial",
    description=(
        "Swap the X and Y components of a stick input. (a, b) → (b, a). "
        "Useful when you've wired up a stick but want vertical motion to "
        "drive what horizontal would have."
    ),
    short_description="(x, y) → (y, x).",
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(PinSpec("out", "out", "Swapped vec2.", expected="vec2"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
