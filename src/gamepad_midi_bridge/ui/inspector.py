"""Right-hand inspector panel — Figma-style context properties pane.

The inspector is a stack of `InspectorPanel` widgets. Each tab in the app
emits a `selection_changed(payload: dict)` signal; the inspector listens
on a tab-name-keyed routing map and renders the matching panel.

Shape of a selection payload (per tab):
    Mapping:    { "kind": "button"|"axis"|"hat", "index": int, "value": int, "label": str }
    Marketplace:{ "kind": "preset", "slug": str, "title": str, ... }
    Live:       { "kind": "axis"|"button", "index": int, "value": float }

The inspector itself is dumb — it just renders whatever metadata it's
told to render. Tab modules build their own `InspectorPanel` subclasses
or supply a render callback.

Design constraints:
- 320px fixed width when open (Figma default — predictable layout)
- Hides entirely when closed (no leftover header strip — gain real estate)
- One instance per "workspace" so split-screen mode can have two
  independent inspectors (each side picks its own selection)
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


INSPECTOR_WIDTH = 320  # Figma's default — fixed for layout predictability.


class Inspector(QWidget):
    """Right-hand context properties pane.

    Tabs push selection payloads via `set_selection(tab_name, payload)`. The
    inspector dispatches to the matching renderer registered via
    `register_renderer(tab_name, fn)`. Unknown tabs fall through to the
    default placeholder ("Select an item to inspect").

    Close button at top-right hides the panel. The parent layout is
    expected to react to the `visibility_changed` signal by adjusting
    sibling widget sizes (e.g. a status-bar toggle button mirrors state).
    """

    visibility_changed = Signal(bool)

    def __init__(self, label: str = "INSPECTOR", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(INSPECTOR_WIDTH)
        self.setObjectName("Inspector")

        self._renderers: Dict[str, Callable[[dict], QWidget]] = {}
        self._current_tab: Optional[str] = None
        self._current_payload: Optional[dict] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header strip — label + close button.
        header = QFrame()
        header.setObjectName("InspectorHeader")
        header.setStyleSheet(
            "QFrame#InspectorHeader { background: #0e0f12; "
            "border-left: 1px solid #24262d; border-bottom: 1px solid #24262d; }"
        )
        header.setFixedHeight(36)
        hh = QHBoxLayout(header)
        hh.setContentsMargins(14, 0, 6, 0)
        hh.setSpacing(8)
        self._title = QLabel(label)
        self._title.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1.4px;"
        )
        hh.addWidget(self._title)
        hh.addStretch(1)
        close = QPushButton("×")
        close.setFlat(True)
        close.setFixedSize(28, 28)
        close.setStyleSheet(
            "QPushButton { color: #8a9099; font-size: 18px; padding: 0; margin: 0; } "
            "QPushButton:hover { color: #f5f7fa; }"
        )
        close.setToolTip("Close inspector")
        close.clicked.connect(self.hide_panel)
        hh.addWidget(close)
        outer.addWidget(header)

        # Scroll area for the body so long inspector content is reachable.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: #0a0b0e; border-left: 1px solid #24262d; }"
        )
        self._body_host = QWidget()
        self._body_host.setStyleSheet("background: #0a0b0e;")
        self._body_layout = QVBoxLayout(self._body_host)
        self._body_layout.setContentsMargins(14, 14, 14, 14)
        self._body_layout.setSpacing(10)
        self._body_layout.addStretch(1)
        scroll.setWidget(self._body_host)
        outer.addWidget(scroll, 1)

        # Default placeholder — replaced when a tab pushes a selection.
        self._render_placeholder()

    # ============================================================== public API

    def register_renderer(
        self,
        tab_name: str,
        renderer: Callable[[dict], QWidget],
    ) -> None:
        """Tab modules register a renderer fn that converts a selection
        payload into a QWidget. Multiple calls overwrite — latest wins."""
        self._renderers[tab_name] = renderer

    def set_selection(self, tab_name: str, payload: Optional[dict]) -> None:
        """Tabs push their current selection here. `payload=None` clears
        back to the placeholder ('select an item to inspect')."""
        self._current_tab = tab_name
        self._current_payload = payload
        self._render_current()

    def show_panel(self) -> None:
        if not self.isVisible():
            self.setVisible(True)
            self.visibility_changed.emit(True)

    def hide_panel(self) -> None:
        if self.isVisible():
            self.setVisible(False)
            self.visibility_changed.emit(False)

    def toggle(self) -> None:
        if self.isVisible():
            self.hide_panel()
        else:
            self.show_panel()

    # ============================================================== rendering

    def _clear_body(self) -> None:
        # Remove all children from the body layout (except the trailing stretch).
        while self._body_layout.count() > 1:
            item = self._body_layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _render_placeholder(self) -> None:
        self._clear_body()
        hint = QLabel("Select an item to inspect.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #5a606b; font-size: 12px; font-style: italic;")
        # Insert before the trailing stretch.
        self._body_layout.insertWidget(0, hint)
        sub = QLabel(
            "Tabs that support inspection: Mapping, Marketplace, Live. "
            "Click a row or card to see its properties here."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #5a606b; font-size: 11px; margin-top: 8px;")
        self._body_layout.insertWidget(1, sub)

    def _render_current(self) -> None:
        if not self._current_tab or not self._current_payload:
            self._render_placeholder()
            return
        renderer = self._renderers.get(self._current_tab)
        if renderer is None:
            self._render_placeholder()
            return
        try:
            widget = renderer(self._current_payload)
        except Exception:
            # Never let an inspector renderer crash the app.
            self._render_placeholder()
            return
        self._clear_body()
        self._body_layout.insertWidget(0, widget)


def render_mapping_selection(payload: dict) -> QWidget:
    """Default renderer for the Mapping tab's selection.

    Accepts a dict shaped like:
      { "kind": "button"|"axis"|"hat", "index": int|str, "midi": int, "label": str }
    """
    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)

    kind = str(payload.get("kind", "control"))
    label = str(payload.get("label", kind.title()))
    title = QLabel(label)
    title.setStyleSheet(
        "color: #f5f7fa; font-size: 16px; font-weight: 600;"
    )
    v.addWidget(title)

    kind_chip = QLabel(kind.upper())
    kind_chip.setAlignment(Qt.AlignCenter)
    kind_chip.setStyleSheet(
        "color: #5eead4; background: rgba(45, 212, 191, 0.12); "
        "border: 1px solid rgba(45, 212, 191, 0.3); border-radius: 999px; "
        "padding: 4px 10px; font-size: 10px; font-weight: 700; "
        "letter-spacing: 1.4px;"
    )
    kind_chip.setMaximumWidth(80)
    v.addWidget(kind_chip)

    # Key-value rows for every field on the payload aside from kind+label.
    grid_keys = [k for k in payload.keys() if k not in ("kind", "label")]
    for key in grid_keys:
        row = QHBoxLayout()
        k = QLabel(str(key).replace("_", " ").title())
        k.setStyleSheet("color: #8a9099; font-size: 11px; font-weight: 500;")
        k.setMinimumWidth(110)
        val = QLabel(str(payload[key]))
        val.setStyleSheet("color: #c2c6cc; font-size: 12px; font-family: ui-monospace, Menlo, monospace;")
        val.setWordWrap(True)
        row.addWidget(k)
        row.addWidget(val, 1)
        v.addLayout(row)

    return wrap
