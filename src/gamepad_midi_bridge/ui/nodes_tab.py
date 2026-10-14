"""Nodes top-level tab — wraps the node-graph canvas and lifecycle logic.

Separated from VisualiseTab so the canvas can be a peer of Visualise in
the main tab bar (not buried inside it). Handles:

    - Lazy-initialising an empty NodeGraph on a mapping that doesn't have one
    - Seeding the standard ControllerSource set so the user has something
      to wire FROM the moment the canvas opens
    - Loading the registry once + passing it to the view

set_mapping(mapping) is the single public entry point — MainWindow calls
it on every preset load + at startup.
"""
from __future__ import annotations

from typing import Optional

import time
from typing import Dict, Set

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..nodes import (
    NodeGraph,
    default_registry,
    seed_default_controller_sources,
)
from .canvas_left_dock import CanvasLeftDock
from .nodes_canvas import NodeGraphView


class NodesTab(QWidget):
    """Top-level Nodes tab — left dock toolbar + node-graph canvas.

    Emits ``mapping_changed`` after the canvas mutates the loaded mapping
    in any way (add/delete/edit/drag-release/param-edit). MainWindow wires
    this signal to its existing _save_last_mapping path so every canvas
    edit hits disk — no "I built a graph and lost it" failure mode.
    """

    mapping_changed = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Figma/Photoshop/Sheets-style tool palette on the left.
        self._dock = CanvasLeftDock()
        outer.addWidget(self._dock)

        # Main canvas — stretches to fill remaining width.
        self._view = NodeGraphView()
        outer.addWidget(self._view, 1)

        # Single shared registry — load builtins on first construction.
        self._registry = default_registry()
        if not self._registry.all():
            self._registry.load_builtins()

        # Wire the dock to the view + scene now that both exist.
        self._dock.bind(self._view, self._view.scene_view())

        # The currently-loaded mapping. Held so graph_changed can emit it
        # back to whoever's listening for persistence.
        self._mapping = None

        # Debounce save emissions — a fast sequence of mutations (e.g.
        # adding 3 nodes in a row) coalesces into one save tick.
        self._save_debounce = QTimer(self)
        self._save_debounce.setInterval(150)
        self._save_debounce.setSingleShot(True)
        self._save_debounce.timeout.connect(self._emit_mapping_changed)

        self._view.scene_view().graph_changed.connect(self._on_graph_changed)

        # Live signal flow tracking — each source id has a "last touched"
        # timestamp; sources whose last touch was within SIGNAL_DECAY_S
        # are considered active. A 30 Hz timer refreshes the canvas with
        # the current active-source set, propagating through the graph.
        self._source_activity: Dict[str, float] = {}
        self._signal_timer = QTimer(self)
        self._signal_timer.setInterval(33)         # ~30 Hz
        self._signal_timer.timeout.connect(self._refresh_signal_activity)
        self._signal_timer.start()

    # ----------------------------------------------------------- public API

    def set_mapping(self, mapping) -> None:
        """Refresh the canvas against ``mapping``.

        - If the mapping has no ``node_graph``, install an empty one in place
          (mutates the mapping, but ``Mapping.to_dict`` drops the key when the
          graph is empty so old-shape presets still round-trip clean).
        - Seed the standard ControllerSource set if the graph has zero
          sources — gives the user something to wire FROM on first open.
        - Load into the view.
        """
        if getattr(mapping, "node_graph", None) is None:
            mapping.node_graph = NodeGraph()
        # Seed sources only when the graph has none — never duplicates.
        seed_default_controller_sources(mapping.node_graph)
        self._mapping = mapping
        self._view.load_graph(mapping.node_graph, self._registry)

    # ----------------------------------------------------------- internal

    def _on_graph_changed(self) -> None:
        """Scene-side mutation — start (or restart) the debounce timer."""
        self._save_debounce.start()

    def _emit_mapping_changed(self) -> None:
        """Debounce window elapsed — push the mapping out for persistence."""
        if self._mapping is not None:
            self.mapping_changed.emit(self._mapping)

    # ============================================================ live signal flow

    SIGNAL_DECAY_S = 0.18
    AXIS_ACTIVITY_THRESHOLD = 0.05    # below this magnitude, axis isn't active

    def attach_bridge_signals(self, worker) -> None:
        """Subscribe to bridge worker signals so the canvas can show live
        signal flow. Called by MainWindow during _wire_signals."""
        worker.axis_value.connect(self._on_axis)
        worker.button_state.connect(self._on_button)
        worker.hat_state.connect(self._on_hat)
        worker.touchpad_xy.connect(self._on_touchpad)

    def _stamp_sources(self, predicate) -> None:
        """Stamp every source matching `predicate(src)` as active right now."""
        if self._mapping is None or self._mapping.node_graph is None:
            return
        now = time.perf_counter()
        for sid, src in self._mapping.node_graph.sources.items():
            if predicate(src):
                self._source_activity[sid] = now

    def _on_axis(self, idx: int, value: float) -> None:
        # Axis idx may map to multiple source kinds:
        #   - "stick_xy": consumes axes (0,1) for left, (2,3) for right
        #   - "axis":      consumes the explicit axis index
        #   - "trigger":   consumes axes 4 (L2) and 5 (R2)
        if abs(value) < self.AXIS_ACTIVITY_THRESHOLD:
            return
        def matches(src) -> bool:
            if src.kind == "stick_xy":
                base = 0 if src.index == 0 else 2
                return idx in (base, base + 1)
            if src.kind == "axis":
                return src.index == idx
            if src.kind == "trigger":
                return idx == (4 + src.index)
            return False
        self._stamp_sources(matches)

    def _on_button(self, idx: int, pressed: bool) -> None:
        if not pressed:
            return
        self._stamp_sources(lambda s: s.kind == "button" and s.index == idx)

    def _on_hat(self, direction: str, pressed: bool) -> None:
        if not pressed:
            return
        self._stamp_sources(lambda s: s.kind == "dpad")

    def _on_touchpad(self, contact: bool, x: float, y: float) -> None:
        if not contact:
            return
        self._stamp_sources(lambda s: s.kind == "touchpad")

    def _refresh_signal_activity(self) -> None:
        """30 Hz tick — drop expired source stamps and push the live set
        to the scene so wires repaint."""
        if not self._source_activity:
            return
        now = time.perf_counter()
        active = {
            sid for sid, t in self._source_activity.items()
            if (now - t) <= self.SIGNAL_DECAY_S
        }
        # Drop stamps that have fully decayed so the dict doesn't grow.
        for sid in list(self._source_activity.keys()):
            if sid not in active:
                self._source_activity.pop(sid, None)
        self._view.scene_view().set_active_sources(active)

    @property
    def view(self) -> NodeGraphView:
        """The underlying NodeGraphView, exposed for direct integration tests."""
        return self._view
