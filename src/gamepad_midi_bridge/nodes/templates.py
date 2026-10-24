"""Drop-in starter graphs for the node canvas.

The node layer ships 78 transform nodes, but all of them sit behind one
dropdown and a fresh canvas offers only bare controller sources wired to
nothing. Someone opening the Nodes tab for the first time is handed a list of
unfamiliar names — `hysteresis`, `slew_limit`, `radial_sector` — with no way
to tell which three of them combine into something they actually want. The
library being large makes that worse, not better.

A template is a small working sub-graph: source, a couple of nodes, a sink,
already wired. Dropping one gives a canvas that does something immediately,
and a concrete example to pull apart — which is how people learn a node editor
in practice. Each one here is deliberately 2-4 nodes; they are starting points
to modify, not finished rigs.

Pure stdlib, no Qt, in keeping with the rest of `nodes/`. The canvas calls
`instantiate()` and merges the result; nothing here knows a scene exists.

IDs are regenerated on every instantiation, so dropping the same template
twice is safe. Positions are relative to the drop origin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4

from .model import (
    Connection,
    ControllerSource,
    Node,
    NodeGraph,
    SymbolicSink,
)

# Laid out left-to-right in a shallow chain. Roomy enough that labels do not
# collide at default zoom.
_COL = 220.0
_ROW = 120.0


@dataclass(frozen=True)
class TemplatePart:
    """One element of a template, with a position relative to the drop point."""

    local_id: str
    column: int = 0
    row: int = 0


@dataclass(frozen=True)
class TemplateSource(TemplatePart):
    kind: str = "axis"
    index: int = 0
    label: str = ""


@dataclass(frozen=True)
class TemplateNode(TemplatePart):
    kind: str = ""
    params: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TemplateSink(TemplatePart):
    symbol: str = ""
    label: str = ""


@dataclass(frozen=True)
class TemplateWire:
    from_local: str
    from_pin: str
    to_local: str
    to_pin: str


@dataclass(frozen=True)
class GraphTemplate:
    """A named starter sub-graph.

    `category` groups these in the picker the same way NodeSpec.category
    groups single nodes, so the two pickers read alike.
    """

    id: str
    label: str
    category: str
    description: str
    sources: tuple[TemplateSource, ...] = ()
    nodes: tuple[TemplateNode, ...] = ()
    sinks: tuple[TemplateSink, ...] = ()
    wires: tuple[TemplateWire, ...] = ()

    @property
    def node_count(self) -> int:
        """Transform nodes only — what the picker shows as a size hint."""
        return len(self.nodes)


def _cc(number: int, channel: int = 1) -> str:
    """Raw MIDI CC sink symbol.

    Format is regex-enforced in sinks.py as ``midi.cc:N@ch:C``. Built here
    rather than hand-written in each template so a typo cannot ship a sink
    that silently resolves to nothing.
    """
    return f"midi.cc:{number}@ch:{channel}"


def _note(number: int, channel: int = 1) -> str:
    """Raw MIDI note sink symbol — ``midi.note:N@ch:C``."""
    return f"midi.note:{number}@ch:{channel}"


# ── The library ──────────────────────────────────────────────────────────
# Kept small and each one genuinely useful. A long list of near-identical
# templates would reproduce the discovery problem these exist to solve.

TEMPLATES: tuple[GraphTemplate, ...] = (
    GraphTemplate(
        id="trigger_filter_sweep",
        label="Trigger → filter sweep",
        category="shape",
        description=(
            "Right trigger through a response curve to CC 74. The most common "
            "thing people want, and the one to copy when shaping any analog input."
        ),
        sources=(TemplateSource("src", 0, 0, kind="trigger", index=5, label="R2"),),
        nodes=(
            TemplateNode("curve", 1, 0, kind="curve",
                         params={"kind": "exponential", "k": 0.6}),
        ),
        sinks=(TemplateSink("out", 2, 0, symbol=_cc(74), label="CC 74 · Cutoff"),),
        wires=(
            TemplateWire("src", "out", "curve", "in"),
            TemplateWire("curve", "out", "out", "in"),
        ),
    ),
    GraphTemplate(
        id="smoothed_stick_xy",
        label="Stick → smoothed XY",
        category="spatial",
        description=(
            "Left stick with a deadzone and slew limiting into two CCs. Stops a "
            "worn stick leaking an offset and keeps fast flicks from stepping."
        ),
        sources=(TemplateSource("src", 0, 0, kind="stick_xy", index=0, label="Left Stick"),),
        nodes=(
            TemplateNode("dz", 1, 0, kind="dead_zone", params={"dead_zone": 0.08}),
            TemplateNode("slew", 2, 0, kind="slew_limit", params={}),
        ),
        sinks=(
            TemplateSink("x", 3, -1, symbol=_cc(16), label="CC 16 · X"),
            TemplateSink("y", 3, 1, symbol=_cc(17), label="CC 17 · Y"),
        ),
        wires=(
            TemplateWire("src", "out", "dz", "in"),
            TemplateWire("dz", "out", "slew", "in"),
            TemplateWire("slew", "out", "x", "in"),
            TemplateWire("slew", "out", "y", "in"),
        ),
    ),
    GraphTemplate(
        id="scale_locked_notes",
        label="Stick → notes in key",
        category="music",
        description=(
            "Stick position quantised to a scale before it becomes a note, so "
            "nothing you play lands outside the key."
        ),
        sources=(TemplateSource("src", 0, 0, kind="axis", index=1, label="Left Stick Y"),),
        nodes=(
            TemplateNode("quant", 1, 0, kind="scale_quantize",
                         params={"scale": "minor", "key": 0}),
        ),
        sinks=(TemplateSink("out", 2, 0, symbol=_note(60), label="Note · C4"),),
        wires=(
            TemplateWire("src", "out", "quant", "in"),
            TemplateWire("quant", "out", "out", "in"),
        ),
    ),
    GraphTemplate(
        id="lfo_modulation",
        label="LFO → switchable wobble",
        category="modulator",
        description=(
            "A free-running LFO that only reaches the output while a shoulder "
            "button is held, so the wobble is something you play rather than "
            "something that runs all set."
        ),
        sources=(TemplateSource("btn", 0, 1, kind="button", index=5, label="R1 · Engage"),),
        nodes=(
            TemplateNode("lfo", 0, -1, kind="lfo",
                         params={"rate_hz": 2.0, "shape": "sine"}),
            TemplateNode("gate", 1, 0, kind="live_gate", params={}),
        ),
        sinks=(TemplateSink("out", 2, 0, symbol=_cc(1), label="CC 1 · Mod"),),
        wires=(
            TemplateWire("lfo", "out", "gate", "value"),
            TemplateWire("btn", "out", "gate", "gate"),
            TemplateWire("gate", "out", "out", "in"),
        ),
    ),
    GraphTemplate(
        id="hold_to_arm",
        label="Hold a button to arm a control",
        category="gate",
        description=(
            "The stick only sends while a shoulder button is held. Keeps a "
            "parameter from drifting when you put the controller down."
        ),
        sources=(
            TemplateSource("gate", 0, -1, kind="button", index=4, label="L1 · Hold"),
            TemplateSource("val", 0, 1, kind="axis", index=3, label="Right Stick Y"),
        ),
        nodes=(TemplateNode("live", 1, 0, kind="live_gate", params={}),),
        sinks=(TemplateSink("out", 2, 0, symbol=_cc(11), label="CC 11 · Expression"),),
        wires=(
            TemplateWire("val", "out", "live", "value"),
            TemplateWire("gate", "out", "live", "gate"),
            TemplateWire("live", "out", "out", "in"),
        ),
    ),
    GraphTemplate(
        id="touchpad_kaoss",
        label="Touchpad → Kaoss-style XY",
        category="spatial",
        description=(
            "DualSense touchpad straight to two CCs, with the X axis curved so "
            "the middle of the pad is less twitchy than the edges."
        ),
        sources=(TemplateSource("tp", 0, 0, kind="touchpad", index=0, label="Touchpad"),),
        nodes=(
            TemplateNode("curve", 1, -1, kind="curve",
                         params={"kind": "s-curve", "k": 0.5}),
        ),
        sinks=(
            TemplateSink("x", 2, -1, symbol=_cc(16), label="CC 16 · X"),
            TemplateSink("y", 2, 1, symbol=_cc(17), label="CC 17 · Y"),
        ),
        wires=(
            TemplateWire("tp", "out", "curve", "in"),
            TemplateWire("curve", "out", "x", "in"),
            TemplateWire("tp", "out", "y", "in"),
        ),
    ),
)


_BY_ID: dict[str, GraphTemplate] = {t.id: t for t in TEMPLATES}


def get(template_id: str) -> GraphTemplate | None:
    """Look up one template. None when the id is unknown."""
    return _BY_ID.get(template_id)


def by_category() -> dict[str, list[GraphTemplate]]:
    """Templates grouped for the picker, insertion-ordered within a group."""
    grouped: dict[str, list[GraphTemplate]] = {}
    for t in TEMPLATES:
        grouped.setdefault(t.category, []).append(t)
    return grouped


@dataclass
class Instantiated:
    """What a template expands into — merge-ready, all ids already fresh."""

    sources: dict[str, ControllerSource]
    nodes: dict[str, Node]
    sinks: dict[str, SymbolicSink]
    connections: list[Connection]

    @property
    def all_ids(self) -> list[str]:
        return [*self.sources, *self.nodes, *self.sinks]


def instantiate(
    template: GraphTemplate,
    origin: tuple[float, float] = (0.0, 0.0),
    *,
    id_factory: Callable[[], str] = lambda: uuid4().hex,
) -> Instantiated:
    """Expand a template into concrete graph pieces at `origin`.

    Every id is regenerated, so the same template can be dropped repeatedly
    without colliding. `id_factory` is injectable purely so tests can assert
    on stable ids.
    """
    ox, oy = origin
    ids: dict[str, str] = {}

    def pos(part: TemplatePart) -> tuple[float, float]:
        return (ox + part.column * _COL, oy + part.row * _ROW)

    sources: dict[str, ControllerSource] = {}
    for s in template.sources:
        new_id = id_factory()
        ids[s.local_id] = new_id
        sources[new_id] = ControllerSource(
            id=new_id, kind=s.kind, index=s.index, label=s.label, position=pos(s),
        )

    nodes: dict[str, Node] = {}
    for n in template.nodes:
        new_id = id_factory()
        ids[n.local_id] = new_id
        nodes[new_id] = Node(
            id=new_id, kind=n.kind, params=dict(n.params), position=pos(n),
        )

    sinks: dict[str, SymbolicSink] = {}
    for k in template.sinks:
        new_id = id_factory()
        ids[k.local_id] = new_id
        sinks[new_id] = SymbolicSink(
            id=new_id, symbol=k.symbol, label=k.label, position=pos(k),
        )

    connections = [
        Connection(
            from_node=ids[w.from_local], from_pin=w.from_pin,
            to_node=ids[w.to_local], to_pin=w.to_pin,
        )
        for w in template.wires
    ]

    return Instantiated(sources=sources, nodes=nodes, sinks=sinks, connections=connections)


def apply_to(
    graph: NodeGraph,
    template: GraphTemplate,
    origin: tuple[float, float] = (0.0, 0.0),
    *,
    id_factory: Callable[[], str] = lambda: uuid4().hex,
) -> Instantiated:
    """Instantiate and merge into `graph` in place. Returns what was added.

    Additive only — existing nodes, wires and sinks are untouched, so dropping
    a template never disturbs work already on the canvas.
    """
    made = instantiate(template, origin, id_factory=id_factory)
    graph.sources.update(made.sources)
    graph.nodes.update(made.nodes)
    graph.sinks.update(made.sinks)
    graph.connections.extend(made.connections)
    return made


def apply_to_mapping(
    mapping,
    template: GraphTemplate,
    origin: tuple[float, float] = (0.0, 0.0),
    *,
    id_factory: Callable[[], str] = lambda: uuid4().hex,
) -> Instantiated:
    """Drop a template onto a Mapping, creating its graph if there isn't one.

    `Mapping.node_graph` is Optional and starts as None — a mapping that has
    never had a graph omits the key entirely so old presets round-trip
    unchanged. Every caller dropping a template would otherwise need the same
    None check, and the first one to forget it gets an AttributeError on a
    fresh mapping, which is the most likely mapping for someone reaching for
    a starter template in the first place.

    Deliberately untyped on `mapping` to avoid importing Mapping here — that
    would make this module depend on the thing that imports it.
    """
    if getattr(mapping, "node_graph", None) is None:
        mapping.node_graph = NodeGraph()
    return apply_to(mapping.node_graph, template, origin, id_factory=id_factory)
