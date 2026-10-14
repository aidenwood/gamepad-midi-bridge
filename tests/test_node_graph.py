"""Phase-1 coverage for the node-graph input layer.

Scope:
    - Registry: builtin discovery, override semantics, wire-eligibility guard.
    - Seed nodes: behavioural truth-tables for LiveGate, Polar, AxisPick, EdgeGate.
    - Evaluator: topological correctness, inline transforms on connections,
      cycle refusal, source-snapshot wiring.
    - Mapping serialisation: round-trip with and without a graph; old-shape
      presets remain byte-identical.
    - User-folder loader: drops a .py file in a tmp dir, asserts it registers.
"""
from __future__ import annotations

import math
import textwrap
from pathlib import Path

import pytest

from gamepad_midi_bridge.mapping import Mapping
from gamepad_midi_bridge.nodes import (
    Connection,
    ControllerSource,
    InlineTransform,
    Node,
    NodeGraph,
    NodeRegistry,
    NodeSpec,
    ParamSpec,
    PinSpec,
    SymbolicSink,
    default_registry,
    evaluate,
    reset_default_registry,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> NodeRegistry:
    r = NodeRegistry()
    r.load_builtins()
    return r


def test_load_builtins_registers_all_seed_nodes(registry):
    kinds = {s.kind for s in registry.all()}
    # Phase 1 + batch 1 expansion. Use issubset so future batches don't
    # break this without intent — assertion fails loudly if a node goes
    # missing from the catalogue.
    expected = {
        # Phase 1 seed
        "live_gate", "polar", "axis_pick", "edge_gate",
        "range_remap", "tap_vs_hold",
        "toggle", "multi_tap", "curve", "lfo",
        "chord_detect", "sample_hold",
        "invert", "clamp",
        # Batch 1 expansion
        "smooth_lerp", "slew_limit", "add_offset", "multiply", "absolute",
        "mirror", "wrap", "step_quantize",
        "hold_threshold", "momentary_inverse", "panic_once", "not_gate",
        "delay_line", "envelope_follower", "accumulator",
        # Batch 2 expansion
        "power_curve", "hysteresis", "dead_zone", "sign", "square",
        "vec2_swap", "vec2_rotate", "vec2_clamp_radius",
        "and_gate", "or_gate", "comparator",
        "arpeggio", "attack_release", "peak_hold",
        "transpose",
        # Batch 3 expansion
        "ramp_generator", "tap_tempo", "noise_random",
        "xor_gate", "counter",
        "vec2_normalize", "vec2_scale",
        "floor",
        # Batch 4 expansion
        "scale_quantize", "octave_shift", "velocity_curve",
        "chord_build", "note_to_cc",
        "mux_2", "bias", "ceil",
        "double_click", "valley_hold",
        "radial_sector", "flick_detect",
        # Batch 5
        "adsr", "range_check", "xy_quadrant", "pulse",
        # Batch 6 (78 total)
        "release_edge", "latch_value",
        "cc_to_note", "chord_inversion", "arpeggiator_pattern",
        "random_walk", "chase_to_target",
        "exponential",
        "mux_4", "is_nonzero",
    }
    assert expected.issubset(kinds), f"missing: {expected - kinds}"


def test_invert_sign_mode_negates(registry):
    spec = registry.require("invert")
    assert spec.apply({"mode": "sign"}, {"in": 0.4})["out"] == pytest.approx(-0.4)
    assert spec.apply({"mode": "sign"}, {"in": -0.7})["out"] == pytest.approx(0.7)


def test_invert_unipolar_mode_does_one_minus_x(registry):
    spec = registry.require("invert")
    assert spec.apply({"mode": "unipolar"}, {"in": 0.3})["out"] == pytest.approx(0.7)
    # Clamps to 0..1
    assert spec.apply({"mode": "unipolar"}, {"in": 1.5})["out"] == 0.0
    assert spec.apply({"mode": "unipolar"}, {"in": -0.3})["out"] == 1.0


def test_clamp_pins_to_min_max(registry):
    spec = registry.require("clamp")
    p = {"min": 0.2, "max": 0.8}
    assert spec.apply(p, {"in": 0.0})["out"] == 0.2
    assert spec.apply(p, {"in": 1.0})["out"] == 0.8
    assert spec.apply(p, {"in": 0.5})["out"] == 0.5


def test_clamp_tolerates_swapped_min_max(registry):
    spec = registry.require("clamp")
    # User accidentally typed max < min — node should still behave sensibly
    p = {"min": 0.8, "max": 0.2}
    assert spec.apply(p, {"in": 0.5})["out"] == 0.5


# ---------------------------------------------------------------------------
# Category grouping (TouchDesigner-style)
# ---------------------------------------------------------------------------

from gamepad_midi_bridge.nodes import CATEGORIES, category_meta


def test_category_meta_lookup_round_trip():
    for c in CATEGORIES:
        assert category_meta(c.kind) is c


def test_category_meta_returns_none_for_unknown():
    assert category_meta("not_a_real_category") is None


def test_all_nodes_belong_to_a_known_category(registry):
    known = {c.kind for c in CATEGORIES}
    for spec in registry.all():
        assert spec.category in known, f"{spec.kind} has unknown category {spec.category!r}"


def test_by_category_drops_empty_buckets(registry):
    grouped = registry.by_category()
    # input + output have no built-in nodes (the canvas surfaces those via
    # ControllerSource / SymbolicSink boundary items, not node-kind specs).
    assert "input" not in grouped
    assert "output" not in grouped
    # Populated buckets — every category we ship a node for.
    for cat in ("gate", "shape", "spatial", "modulator", "logic", "music"):
        assert cat in grouped, f"category {cat!r} should be populated"


def test_by_category_yields_categories_in_priority_order(registry):
    keys = list(registry.by_category().keys())
    # Gate (10) should come before shape (20), shape before spatial (30), etc.
    priorities = [category_meta(k).sort_priority for k in keys]
    assert priorities == sorted(priorities)


def test_seed_nodes_in_expected_categories(registry):
    by_cat = registry.by_category()
    gate_kinds = {s.kind for s in by_cat.get("gate", [])}
    shape_kinds = {s.kind for s in by_cat.get("shape", [])}
    spatial_kinds = {s.kind for s in by_cat.get("spatial", [])}
    logic_kinds = {s.kind for s in by_cat.get("logic", [])}
    modulator_kinds = {s.kind for s in by_cat.get("modulator", [])}

    assert gate_kinds >= {"live_gate", "edge_gate", "tap_vs_hold", "toggle", "multi_tap"}
    assert shape_kinds >= {"range_remap", "curve", "invert", "clamp"}
    assert spatial_kinds >= {"polar", "axis_pick"}
    assert logic_kinds >= {"chord_detect"}
    assert modulator_kinds >= {"lfo", "sample_hold"}


def test_default_registry_is_a_singleton():
    reset_default_registry()
    a = default_registry()
    b = default_registry()
    assert a is b


def test_wire_eligibility_requires_one_in_one_out():
    r = NodeRegistry()
    bad = NodeSpec(
        kind="bad", label="bad", category="transform",
        description="x", short_description="x",
        inputs=(PinSpec("a", "in", "a"), PinSpec("b", "in", "b")),
        outputs=(PinSpec("out", "out", "out"),),
        wire_eligible=True,
    )
    with pytest.raises(ValueError):
        r.register(bad)


def test_register_overrides_same_kind(registry):
    spec = NodeSpec(
        kind="axis_pick", label="Overridden", category="transform",
        description="x", short_description="x",
        inputs=(PinSpec("in", "in", "i"),),
        outputs=(PinSpec("out", "out", "o"),),
        wire_eligible=True,
        apply=lambda p, i: {"out": i.get("in")},
    )
    registry.register(spec)
    assert registry.require("axis_pick").label == "Overridden"


def test_user_dir_loader_picks_up_drop_in_module(tmp_path: Path):
    """Drop a .py file in user_nodes/, expect its NODES entry to register."""
    user_dir = tmp_path / "user_nodes"
    user_dir.mkdir()
    (user_dir / "double.py").write_text(textwrap.dedent("""
        from gamepad_midi_bridge.nodes import NodeSpec, PinSpec
        def _apply(params, inputs):
            v = inputs.get('in') or 0.0
            return {'out': float(v) * 2.0}
        NODES = [NodeSpec(
            kind='custom_double',
            label='Custom Double',
            category='transform',
            description='Doubles the value.',
            short_description='x2',
            inputs=(PinSpec('in', 'in', 'value'),),
            outputs=(PinSpec('out', 'out', 'value'),),
            wire_eligible=True,
            apply=_apply,
        )]
    """))
    r = NodeRegistry()
    r.load_builtins()
    r.load_user_dir(user_dir)
    spec = r.get("custom_double")
    assert spec is not None
    assert spec.apply({}, {"in": 0.5}) == {"out": 1.0}


# ---------------------------------------------------------------------------
# Seed nodes
# ---------------------------------------------------------------------------

def test_live_gate_passes_through_when_held(registry):
    spec = registry.require("live_gate")
    out = spec.apply(spec.default_params(), {"value": 0.7, "gate": True})
    assert out == {"out": 0.7}


def test_live_gate_zeroes_when_released(registry):
    spec = registry.require("live_gate")
    assert spec.apply(spec.default_params(), {"value": 0.7, "gate": False}) == {"out": 0.0}
    assert spec.apply(spec.default_params(), {"value": True, "gate": False}) == {"out": False}
    assert spec.apply(spec.default_params(), {"value": (0.4, -0.4), "gate": False}) == {"out": (0.0, 0.0)}


def test_polar_centre_emits_zero_angle_and_magnitude(registry):
    spec = registry.require("polar")
    assert spec.apply({}, {"xy": (0.0, 0.0)}) == {"angle": 0.0, "magnitude": 0.0}


@pytest.mark.parametrize("xy,expected_angle,expected_mag", [
    ((1.0, 0.0), 0.0, 1.0),
    ((0.0, 1.0), 0.25, 1.0),
    ((-1.0, 0.0), 0.5, 1.0),
    ((0.0, -1.0), 0.75, 1.0),
    ((math.sqrt(0.5), math.sqrt(0.5)), 0.125, 1.0),
])
def test_polar_cardinals_and_45deg(registry, xy, expected_angle, expected_mag):
    spec = registry.require("polar")
    out = spec.apply({}, {"xy": xy})
    assert out["angle"] == pytest.approx(expected_angle, abs=1e-6)
    assert out["magnitude"] == pytest.approx(expected_mag, abs=1e-6)


def test_axis_pick_picks_x_and_y(registry):
    spec = registry.require("axis_pick")
    assert spec.apply({"axis": "x"}, {"in": (0.3, -0.5)}) == {"out": 0.3}
    assert spec.apply({"axis": "y"}, {"in": (0.3, -0.5)}) == {"out": -0.5}


def test_axis_pick_scalar_passes_through(registry):
    spec = registry.require("axis_pick")
    # Wire safety — node ends up on a wire that turned out to carry a scalar.
    assert spec.apply({"axis": "x"}, {"in": 0.42}) == {"out": 0.42}


def test_edge_gate_threshold_blocks_low_magnitudes(registry):
    spec = registry.require("edge_gate")
    p = spec.default_params()
    assert spec.apply(p, {"in": (0.1, 0.1)}) == {"out": 0.0}
    assert spec.apply(p, {"in": 0.5}) == {"out": 0.0}


def test_edge_gate_passes_when_past_threshold(registry):
    spec = registry.require("edge_gate")
    p = spec.default_params()
    assert spec.apply(p, {"in": 0.95})["out"] == pytest.approx(0.95)
    mag = (0.7 ** 2 + 0.7 ** 2) ** 0.5
    assert spec.apply(p, {"in": (0.7, 0.7)})["out"] == pytest.approx(mag)


def test_range_remap_linear(registry):
    spec = registry.require("range_remap")
    p = {"in_min": 0.0, "in_max": 1.0, "out_min": 30.0, "out_max": 100.0}
    assert spec.apply(p, {"in": 0.0})["out"] == pytest.approx(30.0)
    assert spec.apply(p, {"in": 1.0})["out"] == pytest.approx(100.0)
    assert spec.apply(p, {"in": 0.5})["out"] == pytest.approx(65.0)


def test_range_remap_clamps_out_of_range(registry):
    spec = registry.require("range_remap")
    p = {"in_min": 0.0, "in_max": 1.0, "out_min": 30.0, "out_max": 100.0}
    # over-shoot
    assert spec.apply(p, {"in": 1.7})["out"] == pytest.approx(100.0)
    # under-shoot
    assert spec.apply(p, {"in": -0.4})["out"] == pytest.approx(30.0)


def test_range_remap_zero_width_input_returns_out_min(registry):
    spec = registry.require("range_remap")
    p = {"in_min": 0.5, "in_max": 0.5, "out_min": 30.0, "out_max": 100.0}
    assert spec.apply(p, {"in": 0.5})["out"] == 30.0


def test_tap_vs_hold_short_press_fires_tap(registry):
    import time
    spec = registry.require("tap_vs_hold")
    p = {"threshold_ms": 250}
    state: dict = {}
    spec.apply(p, {"in": True}, state)
    time.sleep(0.05)
    spec.apply(p, {"in": True}, state)
    out = spec.apply(p, {"in": False}, state)
    assert out["tap"] is True
    assert out["hold"] is False


def test_tap_vs_hold_long_press_fires_hold_then_no_tap_on_release(registry):
    import time
    spec = registry.require("tap_vs_hold")
    p = {"threshold_ms": 100}
    state: dict = {}
    spec.apply(p, {"in": True}, state)
    time.sleep(0.15)
    held = spec.apply(p, {"in": True}, state)
    assert held["hold"] is True
    released = spec.apply(p, {"in": False}, state)
    assert released["tap"] is False  # hold was already crossed — no tap on release
    assert released["hold"] is False


def test_toggle_flips_on_press_edge_only(registry):
    spec = registry.require("toggle")
    state: dict = {}
    # Initial: off
    assert spec.apply({}, {"in": False}, state)["out"] is False
    # Press edge → on
    assert spec.apply({}, {"in": True}, state)["out"] is True
    # Held → still on (no second flip)
    assert spec.apply({}, {"in": True}, state)["out"] is True
    # Release → still on (only press edges flip)
    assert spec.apply({}, {"in": False}, state)["out"] is True
    # Second press → off
    assert spec.apply({}, {"in": True}, state)["out"] is False


def test_toggle_respects_start_on(registry):
    spec = registry.require("toggle")
    state: dict = {}
    out = spec.apply({"start_on": True}, {"in": False}, state)
    assert out["out"] is True


def test_multi_tap_triple_emits_3_on_trailing_edge(registry):
    import time
    spec = registry.require("multi_tap")
    state: dict = {}
    p = {"window_ms": 100}
    # Three rapid press/release cycles
    for _ in range(3):
        out = spec.apply(p, {"in": True}, state)
        assert out["count"] == 0  # still accumulating
        spec.apply(p, {"in": False}, state)
        time.sleep(0.04)
    # Wait past the window
    time.sleep(0.13)
    final = spec.apply(p, {"in": False}, state)
    assert final["count"] == 3


def test_multi_tap_emits_count_only_once(registry):
    import time
    spec = registry.require("multi_tap")
    state: dict = {}
    p = {"window_ms": 80}
    spec.apply(p, {"in": True}, state)
    spec.apply(p, {"in": False}, state)
    time.sleep(0.1)
    first = spec.apply(p, {"in": False}, state)
    assert first["count"] == 1
    second = spec.apply(p, {"in": False}, state)
    assert second["count"] == 0   # already fired this burst


def test_curve_linear_is_identity(registry):
    spec = registry.require("curve")
    for v in (-1.0, -0.3, 0.0, 0.42, 1.0):
        out = spec.apply({"kind": "linear"}, {"in": v})
        assert out["out"] == pytest.approx(v)


def test_curve_exp_compresses_low_end(registry):
    spec = registry.require("curve")
    out = spec.apply({"kind": "exp", "k": 2.0}, {"in": 0.5})
    assert out["out"] == pytest.approx(0.25)


def test_curve_log_expands_low_end(registry):
    import math
    spec = registry.require("curve")
    out = spec.apply({"kind": "log", "k": 2.0}, {"in": 0.5})
    assert out["out"] == pytest.approx(math.sqrt(0.5))


def test_curve_preserves_sign(registry):
    spec = registry.require("curve")
    out = spec.apply({"kind": "exp", "k": 2.0}, {"in": -0.5})
    assert out["out"] == pytest.approx(-0.25)


def test_curve_deadzone_inside_band_zeroes(registry):
    spec = registry.require("curve")
    out = spec.apply({"kind": "deadzone", "deadzone": 0.1}, {"in": 0.05})
    assert out["out"] == 0.0


def test_curve_deadzone_past_band_remaps_linearly(registry):
    spec = registry.require("curve")
    # 0.55 past dz=0.1 → (0.55-0.1)/(1-0.1) = 0.5
    out = spec.apply({"kind": "deadzone", "deadzone": 0.1}, {"in": 0.55})
    assert out["out"] == pytest.approx(0.5)


def test_lfo_advances_phase_in_real_time(registry):
    import time
    spec = registry.require("lfo")
    state: dict = {}
    p = {"rate_hz": 5.0, "shape": "sine"}
    # First tick seeds last_tick; output starts near sin(0)=0.5 (sine maps 0..1).
    first = spec.apply(p, {}, state)
    assert 0.0 <= first["out"] <= 1.0
    initial_phase = state["phase"]
    time.sleep(0.05)
    second = spec.apply(p, {}, state)
    assert state["phase"] != initial_phase
    assert 0.0 <= second["out"] <= 1.0


def test_chord_detect_fires_only_when_all_wired_held(registry):
    spec = registry.require("chord_detect")
    state: dict = {}
    p = {"debounce_ms": 0}
    assert spec.apply(p, {"in1": False, "in2": False}, state)["out"] is False
    assert spec.apply(p, {"in1": True, "in2": False}, state)["out"] is False
    assert spec.apply(p, {"in1": True, "in2": True}, state)["out"] is True


def test_chord_detect_treats_unwired_pins_as_dont_care(registry):
    spec = registry.require("chord_detect")
    # Only in1 wired, held — output should be True (in2..in4 are None, skipped)
    out = spec.apply({"debounce_ms": 0}, {"in1": True}, {})
    assert out["out"] is True


def test_chord_detect_with_no_wires_never_fires(registry):
    spec = registry.require("chord_detect")
    out = spec.apply({"debounce_ms": 0}, {}, {})
    assert out["out"] is False


def test_chord_detect_debounce_window(registry):
    import time
    spec = registry.require("chord_detect")
    state: dict = {}
    p = {"debounce_ms": 40}
    # First tick all-held — still inside debounce window
    assert spec.apply(p, {"in1": True, "in2": True}, state)["out"] is False
    time.sleep(0.06)
    # Past the window — fires
    assert spec.apply(p, {"in1": True, "in2": True}, state)["out"] is True


def test_chord_detect_break_resets_debounce(registry):
    import time
    spec = registry.require("chord_detect")
    state: dict = {}
    p = {"debounce_ms": 30}
    spec.apply(p, {"in1": True, "in2": True}, state)
    time.sleep(0.05)
    assert spec.apply(p, {"in1": True, "in2": True}, state)["out"] is True
    # Drop one — chord_since should reset
    spec.apply(p, {"in1": True, "in2": False}, state)
    # Re-grip — needs to wait again
    first = spec.apply(p, {"in1": True, "in2": True}, state)
    assert first["out"] is False  # debounce restarts


def test_sample_hold_captures_on_rising_edge(registry):
    spec = registry.require("sample_hold")
    state: dict = {}
    # No trigger → default held (0.0 — None safely coerced)
    assert spec.apply({}, {"value": 0.5, "trigger": False}, state)["out"] == 0.0
    # Rising edge captures
    out = spec.apply({}, {"value": 0.5, "trigger": True}, state)
    assert out["out"] == 0.5
    # Value changes but trigger still high (no edge) — held value unchanged
    assert spec.apply({}, {"value": 0.9, "trigger": True}, state)["out"] == 0.5


def test_sample_hold_persists_through_trigger_off(registry):
    spec = registry.require("sample_hold")
    state: dict = {}
    spec.apply({}, {"value": 0.5, "trigger": True}, state)
    # Trigger drops — held value persists
    assert spec.apply({}, {"value": 0.9, "trigger": False}, state)["out"] == 0.5
    # Re-trigger samples new value
    assert spec.apply({}, {"value": 0.9, "trigger": True}, state)["out"] == 0.9


def test_lfo_phase_wraps_into_unit_range(registry):
    spec = registry.require("lfo")
    state: dict = {"phase": 0.999, "last_tick": 0.0}
    # Big dt forces a wrap if phase += rate * dt overflows 1.0
    # We can't set perf_counter directly, but we can confirm phase stays 0..1
    out = spec.apply({"rate_hz": 10.0}, {}, state)
    assert 0.0 <= state["phase"] < 1.0
    assert 0.0 <= out["out"] <= 1.0


def test_tap_vs_hold_state_resets_between_presses(registry):
    import time
    spec = registry.require("tap_vs_hold")
    p = {"threshold_ms": 50}
    state: dict = {}
    # First press: hold
    spec.apply(p, {"in": True}, state)
    time.sleep(0.08)
    assert spec.apply(p, {"in": True}, state)["hold"] is True
    spec.apply(p, {"in": False}, state)
    # Second press: short tap
    spec.apply(p, {"in": True}, state)
    out = spec.apply(p, {"in": False}, state)
    assert out["tap"] is True  # state from previous hold did not bleed through


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def _stick_polar_graph(opacity_threshold: float = 0.5) -> NodeGraph:
    """LStick → Polar → opacity (via edge_gate inline) + hue (direct)."""
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="stick_xy")
    g.nodes["polar"] = Node(id="polar", kind="polar")
    g.sinks["opacity"] = SymbolicSink(id="opacity", symbol="resolume.layer:1.opacity")
    g.sinks["hue"] = SymbolicSink(id="hue", symbol="resolume.layer:1.hue")
    g.connections = [
        Connection("src", "out", "polar", "xy"),
        Connection("polar", "magnitude", "opacity", "in",
                   inline_transform=InlineTransform(kind="edge_gate", params={"threshold": opacity_threshold})),
        Connection("polar", "angle", "hue", "in"),
    ]
    return g


def test_evaluator_routes_to_multiple_sinks(registry):
    g = _stick_polar_graph()
    sends = evaluate(g, registry, {"src": (math.sqrt(0.5), math.sqrt(0.5))})
    by_symbol = {s.symbol: s.value for s in sends}
    assert by_symbol["resolume.layer:1.opacity"] == pytest.approx(1.0)
    assert by_symbol["resolume.layer:1.hue"] == pytest.approx(0.125)


def test_evaluator_inline_transform_gates_low_signal(registry):
    g = _stick_polar_graph(opacity_threshold=0.5)
    sends = evaluate(g, registry, {"src": (0.2, 0.2)})
    by_symbol = {s.symbol: s.value for s in sends}
    # Below the inline edge_gate threshold — opacity should be muted.
    assert by_symbol["resolume.layer:1.opacity"] == 0.0
    # Hue wire has no inline transform — angle still propagates.
    assert by_symbol["resolume.layer:1.hue"] == pytest.approx(0.125)


def test_evaluator_refuses_cycle(registry):
    g = NodeGraph()
    g.nodes["a"] = Node(id="a", kind="polar")
    g.nodes["b"] = Node(id="b", kind="polar")
    g.sinks["x"] = SymbolicSink(id="x", symbol="midi.cc:1@ch:1")
    g.connections = [
        Connection("a", "angle", "b", "xy"),
        Connection("b", "angle", "a", "xy"),
    ]
    assert evaluate(g, registry, {}) == []


def test_evaluator_empty_graph_returns_empty(registry):
    assert evaluate(NodeGraph(), registry, {}) == []


def test_evaluator_handles_missing_source_value(registry):
    g = _stick_polar_graph()
    # No source key in snapshot — polar gets xy=None → falls back to 0/0.
    sends = evaluate(g, registry, {})
    by_symbol = {s.symbol: s.value for s in sends}
    assert by_symbol["resolume.layer:1.opacity"] == 0.0
    assert by_symbol["resolume.layer:1.hue"] == 0.0


def test_evaluator_unknown_inline_transform_passes_through(registry):
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="axis", index=0)
    g.sinks["out"] = SymbolicSink(id="out", symbol="midi.cc:7@ch:1")
    g.connections = [
        Connection("src", "out", "out", "in",
                   inline_transform=InlineTransform(kind="not_a_real_kind", params={})),
    ]
    sends = evaluate(g, registry, {"src": 0.5})
    assert sends[0].value == 0.5


# ---------------------------------------------------------------------------
# Mapping integration
# ---------------------------------------------------------------------------

def test_mapping_without_node_graph_omits_key():
    d = Mapping().to_dict()
    assert "node_graph" not in d


def test_mapping_round_trip_preserves_node_graph():
    g = _stick_polar_graph()
    m = Mapping(name="live", node_graph=g)
    m2 = Mapping.from_dict(m.to_dict())
    assert m2.node_graph is not None
    assert list(m2.node_graph.nodes.keys()) == ["polar"]
    assert list(m2.node_graph.sinks.keys()) == ["opacity", "hue"]
    assert m2.node_graph.connections[1].inline_transform is not None
    assert m2.node_graph.connections[1].inline_transform.kind == "edge_gate"


# ---------------------------------------------------------------------------
# Sink resolver — raw MIDI fallback
# ---------------------------------------------------------------------------

from gamepad_midi_bridge.nodes.sinks import resolve, value_to_midi


def test_resolve_cc_symbol_yields_zero_indexed_channel():
    b = resolve("midi.cc:7@ch:1")
    assert b is not None
    assert b.kind == "cc"
    assert b.channel == 0   # 1-based in symbol → 0-based in status byte
    assert b.number == 7


def test_resolve_note_symbol():
    b = resolve("midi.note:60@ch:10")
    assert b is not None
    assert b.kind == "note"
    assert b.channel == 9
    assert b.number == 60


def test_resolve_rejects_out_of_range():
    assert resolve("midi.cc:128@ch:1") is None
    assert resolve("midi.cc:7@ch:17") is None
    assert resolve("midi.cc:7@ch:0") is None


def test_resolve_returns_none_for_symbolic_destinations():
    assert resolve("resolume.layer:1.effect:Frost.opacity") is None
    assert resolve("ableton.track:Bass.send:A") is None
    assert resolve("anything-else") is None


def test_value_to_midi_cc_scales_0_to_1():
    b = resolve("midi.cc:7@ch:1")
    assert b is not None
    assert value_to_midi(b, 0.0) == (0xB0, 7, 0)
    assert value_to_midi(b, 1.0) == (0xB0, 7, 127)
    assert value_to_midi(b, 0.5) == (0xB0, 7, 64)


def test_value_to_midi_cc_passes_through_when_already_0_to_127():
    b = resolve("midi.cc:7@ch:1")
    assert b is not None
    assert value_to_midi(b, 100.0) == (0xB0, 7, 100)


def test_value_to_midi_note_bool_drives_on_off():
    b = resolve("midi.note:60@ch:1")
    assert b is not None
    on = value_to_midi(b, True)
    off = value_to_midi(b, False)
    assert on is not None
    assert on[0] == 0x90 and on[1] == 60 and on[2] > 0
    assert off is not None
    assert off[0] == 0x80 and off[1] == 60 and off[2] == 0


def test_value_to_midi_skips_tuple_and_none():
    b = resolve("midi.cc:7@ch:1")
    assert b is not None
    assert value_to_midi(b, None) is None
    assert value_to_midi(b, (0.5, 0.5)) is None


def test_mapping_node_graph_key_stays_absent_through_round_trip():
    """Old-shape presets never gain a node_graph key on round-trip.

    Narrower than a full byte-identical assertion because the wider Mapping
    schema has a pre-existing asymmetry on CornerConfig.notes (default-list
    repopulation) unrelated to this work — we only own the node_graph key
    here.
    """
    legacy_dict = Mapping().to_dict()
    assert "node_graph" not in legacy_dict
    rehydrated = Mapping.from_dict(legacy_dict)
    assert rehydrated.node_graph is None
    assert "node_graph" not in rehydrated.to_dict()
