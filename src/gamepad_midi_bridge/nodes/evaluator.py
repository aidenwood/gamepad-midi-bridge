"""Graph evaluator — runs one tick of a NodeGraph and returns Sends.

Call ``evaluate(graph, registry, source_values)`` every bridge tick. It
walks the graph in topological order, applies each node's ``apply``, hops
along Connections (running each Connection's ``inline_transform`` if
present), and accumulates ``(sink_symbol, value)`` pairs at the sinks.

Design choices:
    - Pure function. No state lives in the evaluator between ticks; every
      tick is a fresh pass. State that needs to persist (e.g. note-on/off
      edge detection) belongs in the bridge loop downstream.
    - Cycles refused. A graph with a cycle returns an empty result and the
      bridge loop logs a warning. The UI should prevent cycles at edit time
      anyway, but we defend here too.
    - Missing endpoints are skipped quietly. The graph editor may briefly
      have dangling references during user edits.
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Set, Tuple

from .model import (
    Connection,
    ControllerSource,
    InlineTransform,
    Node,
    NodeGraph,
    PinValue,
    SymbolicSink,
)
from .registry import NodeRegistry

log = logging.getLogger("gamepad_midi_bridge.nodes.evaluator")


@dataclass(frozen=True)
class Send:
    """One MIDI emission destined for a symbolic sink.

    The bridge loop pairs `symbol` with a Resolver (from connectors) to turn
    "resolume.layer:1.effect:Frosted Glass.opacity" into a real MIDI CC at
    bind time. The evaluator never touches MIDI directly.
    """
    symbol: str
    value: PinValue


def evaluate(
    graph: NodeGraph,
    registry: NodeRegistry,
    source_values: Mapping[str, PinValue],
    state_store: Optional[Dict[str, Dict[str, object]]] = None,
) -> List[Send]:
    """Run one tick of the graph.

    `source_values` maps ControllerSource.id → its current value this tick.
    Sources missing from the map evaluate to None and downstream nodes are
    expected to handle that defensively.

    `state_store` is an evaluator-owned dict keyed by node id. Each value is a
    mutable dict that survives across ticks — stateful nodes like tap_vs_hold
    use it to remember when a press started. Pass the same dict every tick to
    persist state; pass None for a stateless one-shot evaluation. The bridge
    loop owns one of these for the lifetime of a session.
    """
    if graph.is_empty():
        return []
    if state_store is None:
        state_store = {}

    # ---- 1. Build adjacency: dst node id → list of incoming Connections.
    incoming: Dict[str, List[Connection]] = defaultdict(list)
    for c in graph.connections:
        incoming[c.to_node].append(c)

    # ---- 2. Topological order over nodes only. Sources have no predecessors
    # (they're the roots); sinks are leaves and don't run apply() — they just
    # collect values. We iterate nodes in dependency order.
    order = _topological_order(graph)
    if order is None:
        log.warning("NodeGraph has a cycle — refusing to evaluate")
        return []

    # ---- 3. Cache every endpoint's output pins, keyed by (endpoint_id, pin).
    # Sources: a single 'out' pin per source carrying the snapshot value.
    # Nodes:   one entry per declared output pin after apply() runs.
    cache: Dict[Tuple[str, str], PinValue] = {}
    for src_id, src in graph.sources.items():
        cache[(src_id, "out")] = source_values.get(src_id)

    # ---- 4. Walk nodes in topological order, computing each one's outputs.
    for node_id in order:
        node = graph.nodes.get(node_id)
        if node is None:
            continue
        spec = registry.get(node.kind)
        if spec is None:
            log.warning("Node %s references unknown kind %r — skipping", node_id, node.kind)
            continue
        # Collect inputs for this node from incoming connections.
        node_inputs: Dict[str, PinValue] = {p.name: None for p in spec.inputs}
        for c in incoming.get(node_id, ()):
            v = cache.get((c.from_node, c.from_pin))
            if c.inline_transform is not None:
                v = _apply_inline(c.inline_transform, v, registry)
            node_inputs[c.to_pin] = v
        # Apply. State dict is allocated on first encounter and reused
        # across ticks — pass the SAME dict every time so apply() can read
        # what it wrote previously.
        per_node_state = state_store.setdefault(node_id, {})
        try:
            outputs = spec.apply(node.params, node_inputs, per_node_state)
        except Exception:
            log.exception("Node %s (kind=%s) apply() crashed; emitting zeros", node_id, node.kind)
            outputs = {p.name: 0.0 for p in spec.outputs}
        for pin_name, value in outputs.items():
            cache[(node_id, pin_name)] = value

    # ---- 5. Collect sends at every sink.
    sends: List[Send] = []
    for sink_id, sink in graph.sinks.items():
        for c in incoming.get(sink_id, ()):
            v = cache.get((c.from_node, c.from_pin))
            if c.inline_transform is not None:
                v = _apply_inline(c.inline_transform, v, registry)
            sends.append(Send(symbol=sink.symbol, value=v))

    return sends


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------

def _apply_inline(
    transform: InlineTransform,
    value: PinValue,
    registry: NodeRegistry,
) -> PinValue:
    """Run a Connection's circular ⚙ menu transform on a single value.

    Inline transforms reuse the same NodeSpec catalog as full node cards —
    `wire_eligible` is the registry-enforced 1-in/1-out contract that makes
    this safe. Inputs go in under the spec's single input pin name; outputs
    come out under the spec's single output pin name.
    """
    spec = registry.get(transform.kind)
    if spec is None:
        log.warning("Inline transform references unknown kind %r — passing value through", transform.kind)
        return value
    if not spec.wire_eligible:
        log.warning("Inline transform %r is not wire_eligible — passing value through", transform.kind)
        return value
    in_pin = spec.inputs[0].name
    out_pin = spec.outputs[0].name
    try:
        # Merge defaults with the transform's overrides — UI may store only
        # the changed keys for compactness. Wire-mode nodes get an ephemeral
        # state dict that doesn't persist across ticks — they're meant to be
        # stateless quick-edits, and persisting state from a wire is too
        # surprising for an inline transform.
        params = {**spec.default_params(), **transform.params}
        outputs = spec.apply(params, {in_pin: value}, {})
    except Exception:
        log.exception("Inline transform %r crashed; passing value through", transform.kind)
        return value
    return outputs.get(out_pin, value)


def _topological_order(graph: NodeGraph) -> Optional[List[str]]:
    """Kahn's algorithm over the Node-only subgraph.

    Sources have no predecessors and don't need to be in the order — we seed
    their values directly into the cache. Sinks have no successors so they
    don't need to be in the order either — we read incoming connections at
    the end. Only the inner Node layer participates here.

    Returns None if the inner subgraph contains a cycle.
    """
    node_ids: Set[str] = set(graph.nodes.keys())
    if not node_ids:
        return []

    indeg: Dict[str, int] = {n: 0 for n in node_ids}
    successors: Dict[str, List[str]] = defaultdict(list)

    for c in graph.connections:
        if c.from_node in node_ids and c.to_node in node_ids:
            indeg[c.to_node] += 1
            successors[c.from_node].append(c.to_node)

    queue: deque = deque([n for n, d in indeg.items() if d == 0])
    order: List[str] = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for s in successors[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)

    if len(order) != len(node_ids):
        return None
    return order
