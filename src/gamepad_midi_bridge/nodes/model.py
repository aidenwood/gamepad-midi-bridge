"""Core data model for the node-graph input layer.

Phase 1 backend only — no UI here. The visualiser will read these structures
in Phase 2 to render the TouchDesigner-style canvas, but every value below
is fully usable without a Qt loop attached.

Architecture in one paragraph:
    Raw controller state (left stick XY, R1 button, L2 trigger, etc.) feeds
    into the graph at named ControllerSource pins. Values flow through Nodes
    along Connections. Each Connection can optionally apply an InlineTransform
    before delivering the value to the next node — that's the "circular menu
    on the wire" UX. Values exit the graph at SymbolicSink pins, where each
    sink describes WHAT to send (e.g. "resolume.layer_1.opacity") rather than
    HOW (CC 7 ch 1). A Resolver in the connectors module turns symbols into
    raw MIDI bindings at bind time, so the user never has to think in CCs.

Why a graph and not a chain:
    A single R1 press fanning out to "Resolume / Frosted Glass / on" + "Resolume
    / Blur / amount" + "Sustain CC 64" is the headline use case. A linear chain
    can't express that without duplicating the source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Param metadata — drives the hover-tooltip popovers (TouchDesigner style).
# Each NodeSpec declares its params with these descriptors; the UI in Phase 2
# reads them to render the right widget + tooltip.
# ---------------------------------------------------------------------------

ParamType = Literal["float", "int", "bool", "string", "choice", "midi_target"]


@dataclass(frozen=True)
class ParamSpec:
    """Static description of one node parameter.

    Frozen because specs are class-level constants on NodeSpec subclasses and
    must hash for the registry. Runtime values live in Node.params separately.
    """
    name: str
    kind: ParamType
    default: Any
    description: str
    # For "choice" params only — the allowed values, in display order.
    choices: Optional[Tuple[str, ...]] = None
    # For "float" / "int" params only — UI-visible range. Math may extrapolate
    # beyond, but the widget clamps to these bounds.
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    # Display unit shown next to the widget (e.g. "Hz", "ms", "semitones").
    unit: Optional[str] = None


# ---------------------------------------------------------------------------
# Pin = a named input or output slot on a node.
# Sources / sinks expose pins too (they're just nodes with no logic).
# ---------------------------------------------------------------------------

PinDirection = Literal["in", "out"]

# Value carried along a wire. Scalars for axes/CCs, bool for buttons, tuple for
# 2D things like sticks-in-XY-mode. Nodes coerce inputs to whatever they need.
PinValue = Optional[Union[float, int, bool, Tuple[float, ...]]]


@dataclass(frozen=True)
class PinSpec:
    """Static description of one input or output pin on a node spec."""
    name: str
    direction: PinDirection
    description: str
    # Hint to the UI for wire-colour + auto-coercion. Not enforced at runtime
    # (nodes are responsible for being defensive about their inputs).
    expected: Literal["scalar", "bool", "vec2"] = "scalar"


# ---------------------------------------------------------------------------
# NodeSpec = the class-level "what this node is". Singleton per node type.
# Node = a runtime instance with params + position on the canvas.
# ---------------------------------------------------------------------------

NodeCategory = Literal[
    "input",       # controller-side sources (read by the bridge each tick)
    "gate",        # conditional firing — edge / hold / combination
    "shape",       # 1-D scalar reshape (range, curve, sign, clamp)
    "spatial",     # multi-axis transforms (polar, axis pick)
    "modulator",   # time-driven generators + samplers (lfo, sample_hold)
    "logic",       # multi-input boolean operators (chord, and/or/not)
    "music",       # note-aware operators (scale quantize, chord build) — reserved
    "output",      # MIDI / OSC destinations
]


@dataclass(frozen=True)
class CategoryMeta:
    """Display metadata for a node category.

    Drives the Phase-2 node-picker UI: categories appear in `sort_priority`
    order, each header shows `label` + `description`, and the canvas-side
    card border picks up `color_token` (a name from tokens.py, resolved at
    render time so token changes propagate automatically).
    """
    kind: str               # matches NodeCategory literal
    label: str              # e.g. "Gate", "Shape"
    description: str        # one-liner for the picker header
    color_token: str        # token name from ui/tokens.py
    sort_priority: int      # lower = earlier in the picker


# The canonical list. Phase-2 node picker iterates this in priority order;
# any new category added must also appear here for the UI to know about it.
CATEGORIES: Tuple[CategoryMeta, ...] = (
    CategoryMeta(
        kind="input", label="Input",
        description="Controller surfaces — sticks, buttons, triggers, dpad, touchpad.",
        color_token="ACCENT_TEAL", sort_priority=0,
    ),
    CategoryMeta(
        kind="gate", label="Gate",
        description="Conditional firing — hold a button, edge a stick, count taps.",
        color_token="ACCENT_AMBER", sort_priority=10,
    ),
    CategoryMeta(
        kind="shape", label="Shape",
        description="Reshape a scalar — range remap, response curve, sign, clamp.",
        color_token="ACCENT_TEAL", sort_priority=20,
    ),
    CategoryMeta(
        kind="spatial", label="Spatial",
        description="Multi-axis transforms — polar, axis pick, vec math.",
        color_token="FOCUS_RING", sort_priority=30,
    ),
    CategoryMeta(
        kind="modulator", label="Modulator",
        description="Auto-generators and samplers — LFOs, sample-and-hold.",
        color_token="ACCENT_CORAL", sort_priority=40,
    ),
    CategoryMeta(
        kind="logic", label="Logic",
        description="Multi-input boolean — chord detect, and/or/not, comparison.",
        color_token="ACCENT_AMBER", sort_priority=50,
    ),
    CategoryMeta(
        kind="music", label="Music",
        description="Note-aware operators — scale quantize, chord build, transpose.",
        color_token="ACCENT_TEAL", sort_priority=60,
    ),
    CategoryMeta(
        kind="output", label="Output",
        description="MIDI and OSC destinations — symbolic targets resolved at bind time.",
        color_token="ACCENT_CORAL", sort_priority=70,
    ),
)


def category_meta(kind: str) -> Optional[CategoryMeta]:
    """Look up the CategoryMeta for a category kind string. None if unknown."""
    for c in CATEGORIES:
        if c.kind == kind:
            return c
    return None


@dataclass(frozen=True)
class NodeSpec:
    """Static description of a node type. One instance per registered type.

    The registry holds these; Node instances on the graph reference them by
    kind. Spec carries everything the UI needs to render the node card:
    name, hover description, params, pins, category colour, and the wire-mode
    eligibility flag.
    """
    kind: str                   # stable identifier, e.g. "polar", "live_gate"
    label: str                  # display name, e.g. "Polar (XY → angle + magnitude)"
    category: NodeCategory
    description: str            # multi-sentence; shown in the node-picker
    short_description: str      # one-liner; shown in the pin tooltip
    params: Tuple[ParamSpec, ...] = ()
    inputs: Tuple[PinSpec, ...] = ()
    outputs: Tuple[PinSpec, ...] = ()
    # If True, this node can also run inline on a Connection (no card on the
    # canvas). Restricted to 1-in / 1-out nodes — the registry will refuse to
    # set this for anything else.
    wire_eligible: bool = False
    # Implementation callable. Signature:
    #   apply(params: dict, inputs: dict[pin_name, PinValue], state: dict | None)
    #       -> dict[pin_name, PinValue]
    # `state` is an evaluator-owned mutable dict keyed to THIS node instance.
    # Stateless nodes accept the arg and ignore it. Stateful nodes (tap-vs-
    # hold, latch, multi-tap counters, LFOs with phase) read + mutate it.
    # No other side effects allowed — no IO, no shared globals, no time.time
    # outside what the state dict captured from a prior tick.
    apply: Callable[..., Dict[str, PinValue]] = field(
        default=lambda p, i, s=None: {}
    )

    def default_params(self) -> Dict[str, Any]:
        """Fresh dict of every param's default. Each new Node instance copies this."""
        return {p.name: p.default for p in self.params}


# ---------------------------------------------------------------------------
# Node = one box on the canvas.
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """A live node placed on the graph.

    `id` is the stable handle for connections — generate with uuid4 hex at
    construction. `kind` looks up the NodeSpec in the registry. `params`
    starts from NodeSpec.default_params() and is mutated by UI edits.
    `position` is Phase-2 UI metadata, stored here so it survives serialise
    round-trips even though Phase 1 doesn't read it.
    """
    id: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)
    position: Tuple[float, float] = (0.0, 0.0)


# ---------------------------------------------------------------------------
# InlineTransform = the circular ⚙ menu on a wire.
# Reuses the same registry as Node — see NodeSpec.wire_eligible. Carrying
# the kind string + a params dict is enough for the evaluator to apply it.
# ---------------------------------------------------------------------------

@dataclass
class InlineTransform:
    kind: str                     # must reference a wire_eligible NodeSpec
    params: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Connection = a wire on the canvas.
# ---------------------------------------------------------------------------

@dataclass
class Connection:
    """One bezier wire between (from_node.from_pin) → (to_node.to_pin).

    `inline_transform` is the ⚙-menu transform applied to the value AS IT
    TRAVELS along the wire. None = pass-through.
    """
    from_node: str
    from_pin: str
    to_node: str
    to_pin: str
    inline_transform: Optional[InlineTransform] = None


# ---------------------------------------------------------------------------
# ControllerSource + SymbolicSink — the graph's I/O boundaries.
# Sources are exposed by the bridge per tick (left_stick.xy, r1.pressed, ...).
# Sinks are symbolic destinations resolved to MIDI by the connectors module.
# ---------------------------------------------------------------------------

SourceKind = Literal[
    "stick_xy",   # vec2  — emits (-1..1, -1..1)
    "axis",       # scalar — single axis 0..5 (sticks 0-3, triggers 4-5)
    "button",     # bool   — momentary button state
    "trigger",    # scalar — 0..1 trigger position (alias for axis 4/5)
    "dpad",       # int    — 0..7 sector or -1 if centre
    "touchpad",   # vec2   — DualSense touchpad XY (-1..1)
    "battery",    # scalar — 0..1 controller battery
]


@dataclass
class ControllerSource:
    """A graph entry point that reads from the live controller."""
    id: str                              # node id used in Connection.from_node
    kind: SourceKind
    index: int = 0                       # axis index / button index / etc.
    label: str = ""                      # human label for the canvas: "Left Stick"
    position: Tuple[float, float] = (0.0, 0.0)


@dataclass
class SymbolicSink:
    """A graph exit point. The symbol string is resolved by a connector.

    Examples:
        "resolume.layer:1.effect:Frosted Glass.opacity"
        "ableton.track:Bass.send:A"
        "midi.cc:7@ch:1"                — raw fallback

    The raw form is regex-enforced in sinks.py as ``midi.cc:N@ch:C`` and
    ``midi.note:N@ch:C``. This example previously read ``midi.cc:7.ch:1``,
    which does not parse — anyone copying it got a sink that silently
    resolved to nothing.
    """
    id: str
    symbol: str                          # connector-routable destination
    label: str = ""                      # display label on the canvas
    position: Tuple[float, float] = (0.0, 0.0)


# ---------------------------------------------------------------------------
# NodeGraph = the whole picture.
# ---------------------------------------------------------------------------

@dataclass
class NodeGraph:
    """One node graph. Owned by a Mapping; one per controller-input layer.

    Sources and sinks live in their own dicts (separate from `nodes`) because
    they have no NodeSpec to look up — they ARE the boundaries.
    """
    nodes: Dict[str, Node] = field(default_factory=dict)
    connections: List[Connection] = field(default_factory=list)
    sources: Dict[str, ControllerSource] = field(default_factory=dict)
    sinks: Dict[str, SymbolicSink] = field(default_factory=dict)

    # Convenience — every endpoint id is unique across nodes/sources/sinks.
    # The evaluator walks all four pools to find a Connection's endpoints.
    def find_endpoint(self, endpoint_id: str) -> Optional[object]:
        return (
            self.nodes.get(endpoint_id)
            or self.sources.get(endpoint_id)
            or self.sinks.get(endpoint_id)
        )

    def is_empty(self) -> bool:
        return not self.nodes and not self.connections and not self.sources and not self.sinks
