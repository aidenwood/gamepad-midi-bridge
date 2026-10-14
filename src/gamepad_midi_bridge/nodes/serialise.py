"""NodeGraph dict ↔ object converters for Mapping serialisation.

The Mapping dataclass uses ``dataclasses.asdict`` for to_dict already, which
will happily walk NodeGraph since every type in model.py is a dataclass. The
reverse direction needs explicit reconstruction because dataclass-from-dict
isn't in the stdlib — tuples come back as lists, optional fields need
guards, etc.

Kept in its own module so the mapping.py file doesn't get noisier.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .model import (
    Connection,
    ControllerSource,
    InlineTransform,
    Node,
    NodeGraph,
    SymbolicSink,
)


def graph_from_dict(d: Optional[Mapping[str, Any]]) -> Optional[NodeGraph]:
    """Reconstruct a NodeGraph from its asdict form, or None for missing."""
    if d is None:
        return None

    graph = NodeGraph()

    for nid, nd in (d.get("nodes") or {}).items():
        graph.nodes[nid] = Node(
            id=nd.get("id", nid),
            kind=nd["kind"],
            params=dict(nd.get("params") or {}),
            position=_as_xy(nd.get("position")),
        )

    for sid, sd in (d.get("sources") or {}).items():
        graph.sources[sid] = ControllerSource(
            id=sd.get("id", sid),
            kind=sd["kind"],
            index=int(sd.get("index", 0)),
            label=sd.get("label", ""),
            position=_as_xy(sd.get("position")),
        )

    for sid, sd in (d.get("sinks") or {}).items():
        graph.sinks[sid] = SymbolicSink(
            id=sd.get("id", sid),
            symbol=sd["symbol"],
            label=sd.get("label", ""),
            position=_as_xy(sd.get("position")),
        )

    for cd in (d.get("connections") or []):
        it = cd.get("inline_transform")
        graph.connections.append(Connection(
            from_node=cd["from_node"],
            from_pin=cd["from_pin"],
            to_node=cd["to_node"],
            to_pin=cd["to_pin"],
            inline_transform=(
                InlineTransform(kind=it["kind"], params=dict(it.get("params") or {}))
                if it else None
            ),
        ))

    return graph


def _as_xy(value: Any) -> tuple:
    """Coerce a 2-tuple/list/None back to a (float, float) tuple."""
    if value is None:
        return (0.0, 0.0)
    try:
        a, b = value
        return (float(a), float(b))
    except (ValueError, TypeError):
        return (0.0, 0.0)
