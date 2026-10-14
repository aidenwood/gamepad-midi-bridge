"""Default ControllerSource layout for a freshly-created NodeGraph.

When the Visualise tab opens a mapping that doesn't have its own graph
yet, we drop in this standard set of controller sources — sticks,
triggers, dpad, common buttons — laid out down the left edge. Gives the
user something to immediately drag wires off of without having to figure
out how to define a source from scratch.

This is intentionally a sensible default, NOT exhaustive. Sources the
user doesn't end up using sit there harmlessly; if they want more
(touchpad, battery, individual axes) those will come from the node-
picker once the picker gains an Input category populated by sources.
"""
from __future__ import annotations

from typing import List, Tuple

from .model import ControllerSource, NodeGraph


# (id, kind, index, label) — left-edge x is fixed, y is laid out automatically.
_DEFAULT_SOURCES: List[Tuple[str, str, int, str]] = [
    ("src_lstick",   "stick_xy", 0, "Left Stick"),
    ("src_rstick",   "stick_xy", 1, "Right Stick"),
    ("src_l2",       "trigger",  0, "L2 Trigger"),
    ("src_r2",       "trigger",  1, "R2 Trigger"),
    ("src_dpad",     "dpad",     0, "D-Pad"),
    ("src_touchpad", "touchpad", 0, "Touchpad"),
    ("src_cross",    "button",   0, "Cross / A"),
    ("src_circle",   "button",   1, "Circle / B"),
    ("src_square",   "button",   2, "Square / X"),
    ("src_triangle", "button",   3, "Triangle / Y"),
    ("src_l1",       "button",   4, "L1"),
    ("src_r1",       "button",   5, "R1"),
    ("src_share",    "button",   6, "Share / View"),
    ("src_options",  "button",   7, "Options / Menu"),
]

# Layout constants — match the canvas's NODE_WIDTH=200 + comfortable gap.
_LEFT_X = -360.0
_TOP_Y = -200.0
_ROW_HEIGHT = 70.0


def seed_default_controller_sources(graph: NodeGraph) -> int:
    """Populate `graph` with the standard ControllerSource set if empty.

    Returns the number of sources added. Idempotent — calling on a graph
    that already has sources is a no-op so we never duplicate.

    Layout: vertical stack on the left side of the canvas (negative x so
    the user can drop transforms at the natural x=0 anchor).
    """
    if graph.sources:
        return 0
    added = 0
    for i, (sid, kind, idx, label) in enumerate(_DEFAULT_SOURCES):
        graph.sources[sid] = ControllerSource(
            id=sid,
            kind=kind,   # type: ignore[arg-type]
            index=idx,
            label=label,
            position=(_LEFT_X, _TOP_Y + i * _ROW_HEIGHT),
        )
        added += 1
    return added
