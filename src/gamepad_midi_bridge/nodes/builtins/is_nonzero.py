"""IsNonzero — scalar → bool. True iff |x| > threshold."""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": False}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": False}
    threshold = float(params.get("threshold", 1e-6))
    return {"out": abs(v) > threshold}


SPEC = NodeSpec(
    kind="is_nonzero",
    label="Is Non-zero",
    category="logic",
    description=(
        "Output True iff the absolute input is past `threshold`. Default "
        "threshold is tiny — distinguishes 'literally zero' from 'has "
        "any value'. Raise threshold to filter out near-zero stick drift "
        "or quiet LFO output."
    ),
    short_description="True iff |input| > threshold.",
    params=(
        ParamSpec("threshold", "float", 1e-6,
                  "Absolute value above which input is considered non-zero.",
                  minimum=0.0, maximum=1.0),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "True iff |input| > threshold.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
