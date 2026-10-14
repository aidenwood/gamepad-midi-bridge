"""Coverage for the Phase 2.0 node-graph canvas.

Verifies the read-only render path: scene populates correctly from a NodeGraph,
clears on reset, pin lookups resolve, and wire endpoints attach to real pins.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from gamepad_midi_bridge.mapping import Mapping
from gamepad_midi_bridge.nodes import (
    Connection,
    ControllerSource,
    Node,
    NodeGraph,
    NodeRegistry,
    SymbolicSink,
)
from gamepad_midi_bridge.ui.nodes_canvas import (
    BoundaryItem,
    NodeGraphScene,
    NodeGraphView,
    NodeItem,
    WireChipItem,
    WireItem,
    build_add_node_menu,
    build_node_menu,
    build_sink_menu,
    build_wire_menu,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def registry():
    r = NodeRegistry()
    r.load_builtins()
    return r


def _simple_graph() -> NodeGraph:
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="stick_xy", label="L Stick",
                                         position=(0, 0))
    g.nodes["polar"] = Node(id="polar", kind="polar", position=(220, 0))
    g.sinks["mod"] = SymbolicSink(id="mod", symbol="midi.cc:1@ch:1", label="Mod",
                                   position=(440, 0))
    g.connections = [
        Connection("src", "out", "polar", "xy"),
        Connection("polar", "magnitude", "mod", "in"),
    ]
    return g


# ---------------------------------------------------------------------------
# Scene rendering
# ---------------------------------------------------------------------------

def test_scene_populates_from_simple_graph(qapp, registry):
    scene = NodeGraphScene()
    scene.load_graph(_simple_graph(), registry)
    nodes = [i for i in scene.items() if isinstance(i, NodeItem)]
    boundaries = [i for i in scene.items() if isinstance(i, BoundaryItem)]
    wires = [i for i in scene.items() if isinstance(i, WireItem)]
    assert len(nodes) == 1
    assert len(boundaries) == 2          # one source + one sink
    assert len(wires) == 2


def test_scene_clears_between_loads(qapp, registry):
    scene = NodeGraphScene()
    scene.load_graph(_simple_graph(), registry)
    assert len(scene.items()) > 0
    scene.load_graph(NodeGraph(), registry)
    assert len(scene.items()) == 0


def test_pin_resolution_for_connections(qapp, registry):
    scene = NodeGraphScene()
    scene.load_graph(_simple_graph(), registry)
    # Source's "out" pin and the node's "xy" input both exist on the scene.
    src_pin = scene._resolve_out_pin("src", "out")
    polar_xy = scene._resolve_in_pin("polar", "xy")
    polar_mag = scene._resolve_out_pin("polar", "magnitude")
    sink_in = scene._resolve_in_pin("mod", "in")
    assert src_pin is not None
    assert polar_xy is not None
    assert polar_mag is not None
    assert sink_in is not None


def test_unknown_node_kind_is_dropped_gracefully(qapp, registry):
    """If a preset references a node kind the registry doesn't know about,
    the canvas should skip it rather than crash."""
    g = NodeGraph()
    g.nodes["mystery"] = Node(id="mystery", kind="not_a_real_kind")
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    assert sum(1 for i in scene.items() if isinstance(i, NodeItem)) == 0


def test_view_fit_does_not_crash_on_empty_scene(qapp):
    view = NodeGraphView()
    view.fit_to_graph()    # Empty itemsBoundingRect — must early-return cleanly.


def test_node_drag_writes_position_back_to_model(qapp, registry):
    """Moving a NodeItem on the canvas must update Node.position so a
    save → load round-trip preserves the user's layout."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    polar = scene._node_items["polar"]
    polar.setPos(QPointF(311.0, 42.0))
    assert g.nodes["polar"].position == (311.0, 42.0)


def test_node_drag_repaths_attached_wires(qapp, registry):
    """Dragging a node should change the bezier paths of every wire that
    anchors on it — the scene's reverse index needs to find them."""
    from PySide6.QtCore import QPointF
    scene = NodeGraphScene()
    scene.load_graph(_simple_graph(), registry)
    wires = [i for i in scene.items() if isinstance(i, WireItem)]
    before = [w.path().length() for w in wires]
    scene._node_items["polar"].setPos(QPointF(500, 200))
    after = [w.path().length() for w in wires]
    # At least one wire's length changed — both wires anchor on polar so
    # both should actually move, but a single change is enough to prove
    # the reverse-index lookup works.
    assert any(abs(a - b) > 0.1 for a, b in zip(before, after))


def test_boundary_drag_writes_position_back(qapp, registry):
    """ControllerSource and SymbolicSink positions also round-trip on drag."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    sink_item = scene._boundary_items["mod"]
    sink_item.setPos(QPointF(700, 50))
    assert g.sinks["mod"].position == (700.0, 50.0)


def test_add_node_menu_groups_by_category(qapp, registry):
    """Add-node picker surfaces every populated node category + the
    Controller Input + MIDI Output sink pickers."""
    from PySide6.QtCore import QPointF
    scene = NodeGraphScene()
    scene.load_graph(_simple_graph(), registry)
    menu = build_add_node_menu(scene, QPointF(100, 100))
    submenus = [a for a in menu.menu.actions() if a.menu() is not None]
    labels = [s.text() for s in submenus]
    # Spot-check the buckets we expect to be present.
    for name in ("Gate", "Shape", "Spatial", "Modulator", "Logic", "Music"):
        assert name in labels, f"category {name!r} missing from picker"
    assert any("Controller Input" in l for l in labels)
    assert any("MIDI Output" in l for l in labels)
    # Sanity floor: at least the 6 categories + 2 boundary pickers.
    assert len(submenus) >= 8


def test_add_source_appends_to_graph(qapp, registry):
    from PySide6.QtCore import QPointF
    g = NodeGraph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    item = scene.add_source("button", 5, "R1", QPointF(60, 100))
    assert item is not None
    assert len(g.sources) == 1
    src = next(iter(g.sources.values()))
    assert src.kind == "button" and src.index == 5 and src.label == "R1"
    assert src.position == (60.0, 100.0)


def test_add_input_submenu_entries(qapp, registry):
    """Add Input submenu surfaces all standard controller surfaces."""
    from PySide6.QtCore import QPointF
    scene = NodeGraphScene()
    scene.load_graph(_simple_graph(), registry)
    menu = build_add_node_menu(scene, QPointF(0, 0))
    input_sub = next(a for a in menu.menu.actions()
                     if a.menu() is not None and "Controller Input" in a.text())
    labels = [a.text() for a in input_sub.menu().actions()]
    assert any("Left Stick" in l for l in labels)
    assert any("L2 Trigger" in l for l in labels)
    assert any("Touchpad" in l for l in labels)
    assert any("Battery" in l for l in labels)
    # Nested Button submenu
    btn_sub = next(a for a in input_sub.menu().actions()
                   if a.menu() is not None and "Button" in a.text())
    btn_labels = [a.text() for a in btn_sub.menu().actions()]
    assert any("Cross" in l for l in btn_labels)
    assert any("L1" in l for l in btn_labels)


def test_node_param_editor_dialog_builds_widgets_per_kind(qapp, registry):
    """Param editor builds the right widget per ParamSpec.kind and reads
    back the default value through the reader closure."""
    from gamepad_midi_bridge.ui.node_param_editor import NodeParamEditor
    spec = registry.require("curve")
    node = Node(id="n", kind="curve", params=spec.default_params())
    dlg = NodeParamEditor(node=node, spec=spec)
    # curve has: kind (choice), k (float), deadzone (float) — 3 readers
    assert set(dlg._readers) == {"kind", "k", "deadzone"}
    assert dlg._readers["kind"]() == "linear"
    assert dlg._readers["k"]() == 2.0


def test_node_param_editor_handles_empty_param_spec(qapp, registry):
    """Polar has no params — dialog still builds without crashing."""
    from gamepad_midi_bridge.ui.node_param_editor import NodeParamEditor
    spec = registry.require("polar")
    node = Node(id="n", kind="polar", params={})
    dlg = NodeParamEditor(node=node, spec=spec)
    assert dlg._readers == {}


def test_add_node_inserts_into_graph_and_scene(qapp, registry):
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    before_nodes = len(g.nodes)
    item = scene.add_node("range_remap", QPointF(330, 60))
    assert item is not None
    assert len(g.nodes) == before_nodes + 1
    # The new NodeItem has the requested position.
    new_id = next(nid for nid in g.nodes if g.nodes[nid].kind == "range_remap")
    assert g.nodes[new_id].position == (330.0, 60.0)


def test_add_node_unknown_kind_is_no_op(qapp, registry):
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    before_nodes = len(g.nodes)
    item = scene.add_node("not_a_real_kind", QPointF(0, 0))
    assert item is None
    assert len(g.nodes) == before_nodes


def test_wire_menu_includes_delete_and_inline_transform_picker(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    wire = scene._wires[0]
    menu = build_wire_menu(wire, scene)
    actions = menu.menu.actions()
    # Label + Delete + separator + submenu = 4 entries
    assert len(actions) >= 4
    # One submenu — the inline-transform picker.
    submenus = [a for a in actions if a.menu() is not None]
    assert len(submenus) == 1
    # That submenu has "(none)" + every wire-eligible NodeSpec.
    inline_picker_actions = submenus[0].menu().actions()
    labels = [a.text() for a in inline_picker_actions]
    assert "(none)" in labels


def test_delete_wire_drops_connection_from_graph(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    before = len(g.connections)
    scene.delete_wire(scene._wires[0])
    assert len(g.connections) == before - 1


def test_set_wire_inline_transform_round_trip(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    src_wire = scene._wires[0]
    scene.set_wire_inline_transform(src_wire, "axis_pick", {"axis": "x"})
    # Find which connection the wire maps to and verify
    from_id = scene._endpoint_id(src_wire._from)
    to_id = scene._endpoint_id(src_wire._to)
    matched = [
        c for c in g.connections
        if c.from_node == from_id and c.to_node == to_id
    ]
    assert len(matched) == 1
    assert matched[0].inline_transform is not None
    assert matched[0].inline_transform.kind == "axis_pick"
    assert matched[0].inline_transform.params == {"axis": "x"}
    # Clearing it.
    scene.set_wire_inline_transform(src_wire, None)
    assert matched[0].inline_transform is None


def test_node_menu_has_delete_and_reset(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    polar = scene._node_items["polar"]
    menu = build_node_menu(polar, scene)
    labels = [a.text() for a in menu.menu.actions()]
    # Title label + reset + separator + delete = 4 entries minimum
    assert any("Reset" in l for l in labels)
    assert any("Delete" in l for l in labels)


def test_delete_node_removes_node_and_connections(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    # The 'polar' node has 2 connections — deleting it should drop them.
    assert len(g.connections) == 2
    scene.delete_node("polar")
    assert "polar" not in g.nodes
    assert len(g.connections) == 0      # both connections touched polar
    assert "polar" not in scene._node_items


def test_delete_node_unknown_id_is_no_op(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    before_nodes = len(g.nodes)
    scene.delete_node("doesnt_exist")
    assert len(g.nodes) == before_nodes


def test_reset_node_params_to_defaults(qapp, registry):
    g = _simple_graph()
    # Add a curve node and mutate one param.
    from PySide6.QtCore import QPointF
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    item = scene.add_node("curve", QPointF(100, 100))
    assert item is not None
    new_id = next(nid for nid, n in g.nodes.items() if n.kind == "curve")
    # Mutate
    g.nodes[new_id].params["kind"] = "exp"
    g.nodes[new_id].params["k"] = 3.5
    # Reset
    scene.reset_node_params(new_id)
    spec = registry.require("curve")
    assert g.nodes[new_id].params == spec.default_params()


def test_drag_to_connect_creates_new_connection(qapp, registry):
    """End-to-end drag: output pin → input pin → Connection appended."""
    from PySide6.QtCore import QPointF
    # Fresh graph with no polar→mod wire yet — the drag will create it.
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="stick_xy", position=(0, 0))
    g.nodes["polar"] = Node(id="polar", kind="polar", position=(220, 0))
    g.sinks["mod"] = SymbolicSink(id="mod", symbol="midi.cc:1@ch:1",
                                   position=(440, 0))
    g.connections = []          # nothing wired yet
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    polar_mag = scene._node_items["polar"].output_pin("magnitude")
    sink_in = scene._boundary_items["mod"].pin
    scene._begin_wire_drag(polar_mag, polar_mag.scenePos())
    scene._update_wire_drag(QPointF(420, 0))
    scene._end_wire_drag(sink_in.scenePos())
    assert len(g.connections) == 1
    new = g.connections[-1]
    assert new.from_node == "polar" and new.from_pin == "magnitude"
    assert new.to_node == "mod" and new.to_pin == "in"


def test_drag_to_connect_refuses_self_loop(qapp, registry):
    """Wire from a node back to itself is rejected at draw time, even
    though the evaluator would also reject cycles at run time."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    polar_mag = scene._node_items["polar"].output_pin("magnitude")
    polar_xy = scene._node_items["polar"].input_pin("xy")
    before = len(g.connections)
    scene._begin_wire_drag(polar_mag, polar_mag.scenePos())
    scene._end_wire_drag(polar_xy.scenePos())
    assert len(g.connections) == before


def test_drag_to_connect_refuses_duplicate(qapp, registry):
    """Dragging the same output→input pair twice doesn't create a 2nd wire."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    polar_mag = scene._node_items["polar"].output_pin("magnitude")
    sink_in = scene._boundary_items["mod"].pin
    scene._begin_wire_drag(polar_mag, polar_mag.scenePos())
    scene._end_wire_drag(sink_in.scenePos())
    before = len(g.connections)
    scene._begin_wire_drag(polar_mag, polar_mag.scenePos())
    scene._end_wire_drag(sink_in.scenePos())
    assert len(g.connections) == before


def test_click_to_click_cancel_via_scene_helper(qapp, registry):
    """_cancel_wire_drag clears pending state without committing."""
    from PySide6.QtCore import QPointF
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="stick_xy", position=(0, 0))
    g.nodes["polar"] = Node(id="polar", kind="polar", position=(220, 0))
    g.connections = []
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    src_pin = scene._boundary_items["src"].pin
    scene._begin_wire_drag(src_pin, src_pin.scenePos())
    assert scene._pending_source is src_pin
    assert scene._pending_wire is not None
    scene._cancel_wire_drag()
    assert scene._pending_source is None
    assert scene._pending_wire is None
    assert len(g.connections) == 0


def test_click_to_click_reanchor_replaces_source(qapp, registry):
    """Starting a new wire drag while one is pending swaps the source —
    the previous temp wire is cleaned up, not leaked."""
    from PySide6.QtCore import QPointF
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="stick_xy", position=(0, 0))
    g.nodes["polar"] = Node(id="polar", kind="polar", position=(220, 0))
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    src_pin = scene._boundary_items["src"].pin
    polar_mag = scene._node_items["polar"].output_pin("magnitude")
    scene._begin_wire_drag(src_pin, src_pin.scenePos())
    first_wire = scene._pending_wire
    scene._begin_wire_drag(polar_mag, polar_mag.scenePos())
    assert scene._pending_source is polar_mag
    assert scene._pending_wire is not first_wire   # old temp got cleaned up


def test_drag_to_connect_empty_space_is_no_op(qapp, registry):
    """Releasing the drag away from any input pin discards the temp wire
    and leaves the graph untouched."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    polar_mag = scene._node_items["polar"].output_pin("magnitude")
    before = len(g.connections)
    scene._begin_wire_drag(polar_mag, polar_mag.scenePos())
    scene._end_wire_drag(QPointF(9999, 9999))
    assert len(g.connections) == before
    assert scene._pending_source is None
    assert scene._pending_wire is None


def test_add_sink_appends_to_graph_and_scene(qapp, registry):
    """add_sink helper creates a SymbolicSink in the graph + a BoundaryItem
    on the canvas at the requested position."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    before = len(g.sinks)
    item = scene.add_sink("midi.cc:7@ch:1", QPointF(700, 80), "Volume")
    assert item is not None
    assert len(g.sinks) == before + 1
    new_id = next(sid for sid, s in g.sinks.items() if s.symbol == "midi.cc:7@ch:1")
    assert g.sinks[new_id].position == (700.0, 80.0)
    assert g.sinks[new_id].label == "Volume"


def test_add_output_picker_in_add_node_menu(qapp, registry):
    """The empty-canvas right-click menu surfaces an 'Add Output' label
    and a 'MIDI Output…' submenu with at least the quick-add entries."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    menu = build_add_node_menu(scene, QPointF(0, 0))
    titles = [a.text() for a in menu.menu.actions()]
    assert any("Output" in t for t in titles)
    midi_sub = next((a for a in menu.menu.actions() if a.menu() is not None
                     and "MIDI" in a.text()), None)
    assert midi_sub is not None
    sub_labels = [a.text() for a in midi_sub.menu().actions()]
    assert any("Mod Wheel" in l for l in sub_labels)
    assert any("Sustain" in l for l in sub_labels)
    assert any("Note" in l for l in sub_labels)


def test_edit_sink_updates_symbol_and_label(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    scene.edit_sink("mod", symbol="midi.cc:42@ch:5", label="Custom")
    assert g.sinks["mod"].symbol == "midi.cc:42@ch:5"
    assert g.sinks["mod"].label == "Custom"


def test_delete_sink_removes_sink_and_touching_connections(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    # _simple_graph has polar.magnitude → mod.in already wired.
    assert any(c.to_node == "mod" for c in g.connections)
    scene.delete_sink("mod")
    assert "mod" not in g.sinks
    assert not any(c.to_node == "mod" for c in g.connections)


def test_sink_menu_has_edit_rename_delete(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    menu = build_sink_menu(scene._boundary_items["mod"], scene)
    labels = [a.text() for a in menu.menu.actions()]
    assert any("Edit target" in l for l in labels)
    assert any("Rename" in l for l in labels)
    assert any("Delete output" in l for l in labels)


def test_wire_chip_hidden_when_no_inline_transform(qapp, registry):
    """A wire with no inline_transform starts with its midpoint chip hidden —
    chip only surfaces on hover or when a transform is applied."""
    from gamepad_midi_bridge.nodes import InlineTransform
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    for w in scene._wires:
        assert isinstance(w._chip, WireChipItem)
        assert w._chip.isVisible() is False


def test_wire_chip_visible_when_inline_transform_present(qapp, registry):
    """A wire that already carries an inline_transform on load_graph
    shows its chip from the start — read as 'this wire is doing something'."""
    from gamepad_midi_bridge.nodes import InlineTransform
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="stick_xy", position=(0, 0))
    g.nodes["polar"] = Node(id="polar", kind="polar", position=(220, 0))
    g.sinks["mod"] = SymbolicSink(id="mod", symbol="midi.cc:1@ch:1", position=(440, 0))
    g.connections = [
        Connection("polar", "magnitude", "mod", "in",
                   inline_transform=InlineTransform(kind="axis_pick", params={"axis": "x"})),
    ]
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    assert scene._wires[0]._chip.isVisible() is True


def test_wire_chip_toggles_with_inline_transform_mutation(qapp, registry):
    """set_wire_inline_transform must refresh the chip's visibility so the
    canvas reads correctly after a menu-driven edit."""
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    wire = scene._wires[0]
    assert wire._chip.isVisible() is False
    scene.set_wire_inline_transform(wire, "invert", {"mode": "sign"})
    assert wire._chip.isVisible() is True
    scene.set_wire_inline_transform(wire, None)
    assert wire._chip.isVisible() is False


def test_wire_chip_sits_at_bezier_midpoint(qapp, registry):
    """Chip position tracks pointAtPercent(0.5) on the wire's path so it
    follows node moves — a quick property test on the freshly-built scene."""
    from PySide6.QtCore import QPointF
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    wire = scene._wires[0]
    expected = wire.path().pointAtPercent(0.5)
    actual = wire._chip.pos()
    assert abs(expected.x() - actual.x()) < 0.5
    assert abs(expected.y() - actual.y()) < 0.5


def test_scene_emits_graph_changed_on_add_node(qapp, registry):
    from PySide6.QtCore import QPointF
    g = NodeGraph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    seen = []
    scene.graph_changed.connect(lambda: seen.append(1))
    scene.add_node("polar", QPointF(0, 0))
    assert seen == [1]


def test_scene_emits_graph_changed_on_add_sink(qapp, registry):
    from PySide6.QtCore import QPointF
    g = NodeGraph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    seen = []
    scene.graph_changed.connect(lambda: seen.append(1))
    scene.add_sink("midi.cc:7@ch:1", QPointF(0, 0))
    assert seen == [1]


def test_scene_emits_graph_changed_on_delete_node(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    seen = []
    scene.graph_changed.connect(lambda: seen.append(1))
    scene.delete_node("polar")
    assert seen == [1]


def test_scene_emits_graph_changed_on_set_inline_transform(qapp, registry):
    g = _simple_graph()
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    seen = []
    scene.graph_changed.connect(lambda: seen.append(1))
    scene.set_wire_inline_transform(scene._wires[0], "invert", {"mode": "sign"})
    assert seen == [1]


def test_scene_does_not_emit_on_load_graph(qapp, registry):
    """Loading the graph shouldn't trigger a save — we'd re-save what we
    just read on every preset switch."""
    g = _simple_graph()
    scene = NodeGraphScene()
    seen = []
    scene.graph_changed.connect(lambda: seen.append(1))
    scene.load_graph(g, registry)
    assert seen == []


def test_set_active_sources_propagates_through_chain(qapp, registry):
    """An active source lights every wire downstream — wires beyond a
    node also light up so the user sees the full signal chain."""
    g = NodeGraph()
    g.sources["src"] = ControllerSource(id="src", kind="stick_xy", index=0)
    g.nodes["polar"] = Node(id="polar", kind="polar")
    g.sinks["mod"] = SymbolicSink(id="mod", symbol="midi.cc:1@ch:1")
    g.connections = [
        Connection("src", "out", "polar", "xy"),
        Connection("polar", "magnitude", "mod", "in"),
    ]
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    assert sum(1 for w in scene._wires if w._active) == 0
    scene.set_active_sources({"src"})
    assert sum(1 for w in scene._wires if w._active) == 2
    scene.set_active_sources(set())
    assert sum(1 for w in scene._wires if w._active) == 0


def test_set_active_sources_isolates_chains(qapp, registry):
    """Two independent chains: lighting one source only activates its own."""
    g = NodeGraph()
    g.sources["a"] = ControllerSource(id="a", kind="stick_xy", index=0)
    g.sources["b"] = ControllerSource(id="b", kind="stick_xy", index=1)
    g.nodes["polar_a"] = Node(id="polar_a", kind="polar")
    g.nodes["polar_b"] = Node(id="polar_b", kind="polar")
    g.sinks["ka"] = SymbolicSink(id="ka", symbol="midi.cc:1@ch:1")
    g.sinks["kb"] = SymbolicSink(id="kb", symbol="midi.cc:2@ch:1")
    g.connections = [
        Connection("a", "out", "polar_a", "xy"),
        Connection("polar_a", "magnitude", "ka", "in"),
        Connection("b", "out", "polar_b", "xy"),
        Connection("polar_b", "magnitude", "kb", "in"),
    ]
    scene = NodeGraphScene()
    scene.load_graph(g, registry)
    scene.set_active_sources({"a"})
    assert sum(1 for w in scene._wires if w._active) == 2


def test_view_loads_demo_preset_end_to_end(qapp, registry):
    """The shipped demo preset round-trips through Mapping.from_dict and
    renders without error — confirms the JSON shape + canvas + registry stay
    aligned as more nodes are added."""
    preset = Path("src/gamepad_midi_bridge/resources/presets/Node Graph Demo (Phase 1).json")
    if not preset.exists():
        pytest.skip("demo preset not shipped in this repo state")
    m = Mapping.from_dict(json.loads(preset.read_text()))
    view = NodeGraphView()
    view.load_graph(m.node_graph, registry)
    scene = view.scene_view()
    node_count = sum(1 for i in scene.items() if isinstance(i, NodeItem))
    wire_count = sum(1 for i in scene.items() if isinstance(i, WireItem))
    assert node_count == len(m.node_graph.nodes)
    assert wire_count == len(m.node_graph.connections)
