"""Tests for drop-in node-graph templates.

The important ones here are the validation tests: a template that references
a node kind that does not exist, or wires to a pin that is not on that node,
would look fine in the picker and produce a dead sub-graph on the canvas.
These check every template against the real registry rather than trusting the
literals in templates.py.
"""

import pytest

from gamepad_midi_bridge.nodes import templates as T
from gamepad_midi_bridge.nodes.model import NodeGraph
from gamepad_midi_bridge.nodes.registry import NodeRegistry
from gamepad_midi_bridge.nodes.sinks import resolve


@pytest.fixture(scope="module")
def registry():
    r = NodeRegistry()
    r.load_builtins()
    return r


def _specs_by_kind(registry):
    out = {}
    for specs in registry.by_category().values():
        for spec in specs:
            out[spec.kind] = spec
    return out


class TestLibraryShape:
    def test_there_are_templates(self):
        assert len(T.TEMPLATES) >= 5

    def test_ids_are_unique(self):
        ids = [t.id for t in T.TEMPLATES]
        assert len(ids) == len(set(ids))

    def test_every_template_is_described(self):
        for t in T.TEMPLATES:
            assert t.label.strip()
            assert t.description.strip()
            assert t.category.strip()

    def test_get_returns_none_for_unknown(self):
        assert T.get("no_such_template") is None
        assert T.get(T.TEMPLATES[0].id) is T.TEMPLATES[0]

    def test_by_category_covers_everything(self):
        grouped = T.by_category()
        assert sum(len(v) for v in grouped.values()) == len(T.TEMPLATES)

    def test_templates_stay_small(self):
        """These are starting points to modify, not finished rigs."""
        for t in T.TEMPLATES:
            assert 1 <= t.node_count <= 4, f"{t.id} has {t.node_count} nodes"


class TestTemplatesMatchTheRegistry:
    """A wrong kind or pin name ships a template that silently does nothing."""

    def test_every_node_kind_exists(self, registry):
        known = set(_specs_by_kind(registry))
        for t in T.TEMPLATES:
            for n in t.nodes:
                assert n.kind in known, f"{t.id} references unknown node '{n.kind}'"

    def test_every_wire_targets_a_real_pin(self, registry):
        specs = _specs_by_kind(registry)
        for t in T.TEMPLATES:
            local_kinds = {n.local_id: n.kind for n in t.nodes}
            source_ids = {s.local_id for s in t.sources}
            sink_ids = {k.local_id for k in t.sinks}

            for w in t.wires:
                # Outputs
                if w.from_local in local_kinds:
                    outs = {p.name for p in specs[local_kinds[w.from_local]].outputs}
                    assert w.from_pin in outs, (
                        f"{t.id}: '{local_kinds[w.from_local]}' has no output "
                        f"'{w.from_pin}' (has {sorted(outs)})"
                    )
                else:
                    assert w.from_local in source_ids, f"{t.id}: dangling from '{w.from_local}'"
                    assert w.from_pin == "out", f"{t.id}: sources emit on 'out'"

                # Inputs
                if w.to_local in local_kinds:
                    ins = {p.name for p in specs[local_kinds[w.to_local]].inputs}
                    assert w.to_pin in ins, (
                        f"{t.id}: '{local_kinds[w.to_local]}' has no input "
                        f"'{w.to_pin}' (has {sorted(ins)})"
                    )
                else:
                    assert w.to_local in sink_ids, f"{t.id}: dangling to '{w.to_local}'"

    def test_every_node_is_wired(self):
        """A template with an orphan node teaches the wrong thing."""
        for t in T.TEMPLATES:
            touched = {w.from_local for w in t.wires} | {w.to_local for w in t.wires}
            for n in t.nodes:
                assert n.local_id in touched, f"{t.id}: node '{n.local_id}' is orphaned"

    def test_every_sink_symbol_resolves(self):
        """The raw form is regex-enforced; a typo resolves to nothing."""
        for t in T.TEMPLATES:
            for k in t.sinks:
                assert resolve(k.symbol) is not None, (
                    f"{t.id}: sink symbol '{k.symbol}' does not parse"
                )

    def test_params_exist_on_their_node(self, registry):
        specs = _specs_by_kind(registry)
        for t in T.TEMPLATES:
            for n in t.nodes:
                known = {p.name for p in specs[n.kind].params}
                for key in n.params:
                    assert key in known, (
                        f"{t.id}: '{n.kind}' has no param '{key}' (has {sorted(known)})"
                    )


class TestInstantiate:
    def test_ids_are_fresh_each_time(self):
        t = T.TEMPLATES[0]
        a = T.instantiate(t)
        b = T.instantiate(t)
        assert not set(a.all_ids) & set(b.all_ids), "dropping twice must not collide"

    def test_wires_point_at_the_new_ids(self):
        t = T.get("trigger_filter_sweep")
        made = T.instantiate(t)
        valid = set(made.all_ids)
        for c in made.connections:
            assert c.from_node in valid
            assert c.to_node in valid

    def test_origin_offsets_every_piece(self):
        t = T.TEMPLATES[0]
        at_zero = T.instantiate(t, (0.0, 0.0))
        moved = T.instantiate(t, (500.0, 300.0))
        x0 = min(s.position[0] for s in at_zero.sources.values())
        x1 = min(s.position[0] for s in moved.sources.values())
        assert x1 - x0 == pytest.approx(500.0)

    def test_counts_match_the_template(self):
        for t in T.TEMPLATES:
            made = T.instantiate(t)
            assert len(made.sources) == len(t.sources)
            assert len(made.nodes) == len(t.nodes)
            assert len(made.sinks) == len(t.sinks)
            assert len(made.connections) == len(t.wires)

    def test_params_are_copied_not_shared(self):
        """Editing one dropped copy must not change the library."""
        t = T.get("trigger_filter_sweep")
        made = T.instantiate(t)
        node = next(iter(made.nodes.values()))
        node.params["kind"] = "mutated"
        assert t.nodes[0].params["kind"] == "exponential"


class TestApplyTo:
    def test_merges_into_an_empty_graph(self):
        g = NodeGraph()
        t = T.get("smoothed_stick_xy")
        T.apply_to(g, t)
        assert len(g.nodes) == len(t.nodes)
        assert len(g.connections) == len(t.wires)

    def test_is_additive(self):
        """Dropping a template must never disturb work already on the canvas."""
        g = NodeGraph()
        T.apply_to(g, T.get("trigger_filter_sweep"))
        first_nodes = set(g.nodes)
        first_conns = len(g.connections)

        T.apply_to(g, T.get("lfo_modulation"), (400.0, 0.0))
        assert first_nodes <= set(g.nodes), "existing nodes were removed"
        assert len(g.connections) > first_conns

    def test_same_template_twice_coexists(self):
        g = NodeGraph()
        t = T.get("trigger_filter_sweep")
        T.apply_to(g, t)
        T.apply_to(g, t, (0.0, 400.0))
        assert len(g.nodes) == 2 * len(t.nodes)

    def test_apply_to_mapping_creates_a_graph_when_absent(self):
        """A fresh mapping has node_graph=None — the most likely mapping for
        someone reaching for a starter template."""
        from gamepad_midi_bridge.mapping import Mapping

        m = Mapping()
        assert m.node_graph is None
        T.apply_to_mapping(m, T.get("trigger_filter_sweep"))
        assert m.node_graph is not None
        assert len(m.node_graph.nodes) == 1

    def test_round_trips_through_the_mapping(self):
        """A dropped template has to survive save + reload."""
        from gamepad_midi_bridge.mapping import Mapping

        m = Mapping()
        assert m.node_graph is None, "a fresh mapping has no graph"
        T.apply_to_mapping(m, T.get("hold_to_arm"))
        before = len(m.node_graph.nodes)
        restored = Mapping.from_dict(m.to_dict())
        assert len(restored.node_graph.nodes) == before


class TestTemplatesActuallyRun:
    """Pins existing is not proof a template works. These evaluate each one
    through the real evaluator and assert it emits something.

    This is the test that catches a node changing its behaviour underneath a
    template — the sub-graph would still pass every structural check above
    while producing nothing at the sink.
    """

    def _source_value(self, src):
        if src.kind in ("stick_xy", "touchpad"):
            return (0.5, 0.5)
        if src.kind == "button":
            return True
        return 0.5

    @pytest.mark.parametrize("template", T.TEMPLATES, ids=lambda t: t.id)
    def test_template_evaluates_to_a_send(self, registry, template):
        from gamepad_midi_bridge.nodes.evaluator import evaluate

        graph = NodeGraph()
        made = T.apply_to(graph, template)
        values = {sid: self._source_value(src) for sid, src in made.sources.items()}

        sends = evaluate(graph, registry, values, {})
        assert sends, f"{template.id} evaluated to no sends"
        assert len(sends) == len(template.sinks), (
            f"{template.id} has {len(template.sinks)} sinks but emitted {len(sends)}"
        )

    @pytest.mark.parametrize("template", T.TEMPLATES, ids=lambda t: t.id)
    def test_template_survives_a_second_tick(self, registry, template):
        """Stateful nodes (LFO, slew, gates) must not blow up on tick two."""
        from gamepad_midi_bridge.nodes.evaluator import evaluate

        graph = NodeGraph()
        made = T.apply_to(graph, template)
        values = {sid: self._source_value(src) for sid, src in made.sources.items()}
        state: dict = {}

        evaluate(graph, registry, values, state)
        assert evaluate(graph, registry, values, state)
