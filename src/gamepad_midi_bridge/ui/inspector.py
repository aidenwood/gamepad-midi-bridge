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

from .axis_scope import AxisScope
from .primitives import UIButton, UILabel


INSPECTOR_WIDTH = 320  # Figma's default — used as the minimum width now.
INSPECTOR_MAX_WIDTH = 720  # Inspector can grow horizontally inside its splitter.


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
        # Resizable: 320 min, 720 max — lets text fields breathe when the
        # window is wide. The chrome QSplitter handle is the actual resize
        # point; this just sets the bounds.
        self.setMinimumWidth(INSPECTOR_WIDTH)
        self.setMaximumWidth(INSPECTOR_MAX_WIDTH)
        self.setObjectName("Inspector")

        self._renderers: Dict[str, Callable[[dict], QWidget]] = {}
        self._current_tab: Optional[str] = None
        self._current_payload: Optional[dict] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header strip — label + close button.
        # All visual rules in styles.qss → "INSPECTOR PANEL" section.
        header = QFrame()
        header.setObjectName("InspectorHeader")
        header.setFixedHeight(36)
        hh = QHBoxLayout(header)
        hh.setContentsMargins(14, 0, 6, 0)
        hh.setSpacing(8)
        self._title = QLabel(label)
        self._title.setObjectName("InspectorTitle")
        hh.addWidget(self._title)
        hh.addStretch(1)
        close = QPushButton("×")
        close.setObjectName("InspectorCloseButton")
        close.setFlat(True)
        close.setFixedSize(28, 28)
        close.setToolTip("Close inspector")
        close.clicked.connect(self.hide_panel)
        hh.addWidget(close)
        outer.addWidget(header)

        # Scroll area for the body so long inspector content is reachable.
        scroll = QScrollArea()
        scroll.setObjectName("InspectorScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._body_host = QWidget()
        self._body_host.setObjectName("InspectorBodyHost")
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
        hint = UILabel("Select an item to inspect.", variant="body")
        # Insert before the trailing stretch.
        self._body_layout.insertWidget(0, hint)
        sub = UILabel(
            "Tabs that support inspection: Mapping, Marketplace, Live. "
            "Click a row or card to see its properties here.",
            variant="caption",
        )
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
    title = UILabel(label, variant="subheading")
    v.addWidget(title)

    kind_chip = QLabel(kind.upper())
    kind_chip.setObjectName("InspectorKindChip")
    kind_chip.setAlignment(Qt.AlignCenter)
    kind_chip.setMaximumWidth(80)
    v.addWidget(kind_chip)

    # Key-value rows for every field on the payload aside from kind+label.
    grid_keys = [k for k in payload.keys() if k not in ("kind", "label")]
    for key in grid_keys:
        row = QHBoxLayout()
        k = UILabel(str(key).replace("_", " ").title(), variant="caption")
        k.setMinimumWidth(110)
        val = UILabel(str(payload[key]), variant="body")
        row.addWidget(k)
        row.addWidget(val, 1)
        v.addLayout(row)

    return wrap


def render_marketplace_selection(payload: dict) -> QWidget:
    """Renderer for marketplace preset card selection.

    Accepts a dict shaped like:
      { "kind": "preset", "slug": str, "title": str, "downloads": int,
        "rating": float, "author": str, "description": str, "label": str,
        "json_blob": dict }
    """
    from .controller_preview import ControllerPreview

    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)

    title = UILabel(str(payload.get("label", "Preset")), variant="subheading")
    v.addWidget(title)

    author = QLabel(str(payload.get("author", "Anonymous")))
    author.setObjectName("InspectorAuthor")
    author.setAlignment(Qt.AlignCenter)
    author.setMaximumWidth(150)
    v.addWidget(author)

    # Downloads + rating row
    stats_row = QHBoxLayout()
    downloads = UILabel(f"📥 {payload.get('downloads', 0)} downloads", variant="caption")
    stats_row.addWidget(downloads)
    rating = UILabel(f"⭐ {payload.get('rating', 0):.1f}", variant="caption")
    stats_row.addWidget(rating)
    stats_row.addStretch(1)
    v.addLayout(stats_row)

    # Description
    description = str(payload.get("description", ""))
    if description:
        desc_label = UILabel(description, variant="body")
        v.addWidget(desc_label)

    # Controller preview diagram
    divider = QFrame()
    divider.setFrameShape(QFrame.HLine)
    divider.setObjectName("InspectorDivider")
    v.addWidget(divider)

    preview_label = UILabel("MAPPING PREVIEW", variant="caption")
    v.addWidget(preview_label)

    preview = ControllerPreview()
    json_blob = payload.get("json_blob") or {}
    preview.set_mapping_data(json_blob if isinstance(json_blob, dict) else {})
    v.addWidget(preview, 0, Qt.AlignLeft)

    # Install button (stub)
    install_btn = UIButton("Install Preset", variant="primary")
    install_btn.clicked.connect(lambda: print(f"[stub] Install preset: {payload.get('label')}"))
    v.addWidget(install_btn)

    return wrap


def render_live_selection(payload: dict) -> QWidget:
    """Renderer for live controller selection (axis/button/stick/etc).

    Accepts a dict shaped like:
      { "kind": "button"|"axis"|"stick"|"trigger"|"dpad"|"touchpad",
        "index": int, "value": float, "label": str }

    For axes/sticks/triggers: includes a live oscilloscope strip that receives
    updates via the inspector's _update_live_scope() method (wired by main_window).
    """
    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)

    label = str(payload.get("label", "Control"))
    title = UILabel(label, variant="subheading")
    v.addWidget(title)

    kind = str(payload.get("kind", "")).upper()
    kind_chip = QLabel(kind)
    kind_chip.setObjectName("InspectorKindChip")
    kind_chip.setProperty("variant", "live")
    kind_chip.setAlignment(Qt.AlignCenter)
    kind_chip.setMaximumWidth(100)
    v.addWidget(kind_chip)

    # Live value indicator (mono display, same as oscilloscope top-right)
    value = payload.get("value", 0.0)
    if isinstance(value, (int, float)):
        # Normalize to percentage if in 0..1 range, or -1..1 range
        if -1.0 <= value <= 1.0:
            pct = int((value + 1.0) / 2.0 * 100) if value >= -1.0 else int(value * 100)
        else:
            pct = int(value * 100)
        value_label = UILabel(f"Value: {value:.2f} ({pct}%)", variant="body")
    else:
        value_label = UILabel(f"Value: {value}", variant="body")
    v.addWidget(value_label)

    # Index
    idx = payload.get("index", "—")
    idx_label = UILabel(f"Index: {idx}", variant="caption")
    v.addWidget(idx_label)

    # Oscilloscope for axes/sticks/triggers only (not buttons/dpad/touchpad).
    kind_lower = str(payload.get("kind", "")).lower()
    if kind_lower in ("axis", "stick", "trigger"):
        axis_idx = payload.get("index", -1)
        if isinstance(axis_idx, int) and axis_idx >= 0:
            scope_label = str(payload.get("label", "Axis"))
            scope = AxisScope(axis_idx, scope_label)
            scope.setObjectName(f"LiveScope_{axis_idx}")  # For main_window to find + update
            v.addWidget(scope)

    v.addStretch(1)
    return wrap


def render_connector_selection(payload: dict) -> QWidget:
    """Renderer for connector (host application) selection.

    Accepts a dict shaped like:
      { "kind": "connector", "name": str, "target": str, "installed": bool,
        "description": str, "label": str }
    """
    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)

    name = str(payload.get("name", "Connector"))
    title = UILabel(name, variant="subheading")
    v.addWidget(title)

    installed = payload.get("installed", False)
    status_text = "Installed" if installed else "Not installed"
    status_chip = QLabel(status_text)
    status_chip.setObjectName("InspectorStatusChip")
    status_chip.setProperty("state", "installed" if installed else "missing")
    status_chip.setAlignment(Qt.AlignCenter)
    status_chip.setMaximumWidth(120)
    v.addWidget(status_chip)

    # Description
    description = str(payload.get("description", ""))
    if description:
        desc_label = UILabel(description, variant="body")
        v.addWidget(desc_label)

    # Target path (mono)
    target = str(payload.get("target", ""))
    if target:
        path_label = UILabel(target, variant="caption")
        v.addWidget(path_label)

    # Action buttons
    v.addSpacing(4)
    action_btn = UIButton("Install" if not installed else "Reinstall", variant="primary")
    action_btn.clicked.connect(lambda: print(f"[stub] Install {payload.get('name')}"))
    v.addWidget(action_btn)

    if installed:
        uninstall_btn = UIButton("Uninstall", variant="secondary")
        uninstall_btn.clicked.connect(lambda: print(f"[stub] Uninstall {payload.get('name')}"))
        v.addWidget(uninstall_btn)

    v.addStretch(1)
    return wrap


def render_preset_file_selection(payload: dict) -> QWidget:
    """Renderer for preset file selection.

    Accepts a dict shaped like:
      { "kind": "preset_file", "slug": str, "name": str, "mtime": str,
        "size": str, "label": str }
    """
    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)

    name = str(payload.get("name", "Preset"))
    title = UILabel(name, variant="subheading")
    v.addWidget(title)

    slug = str(payload.get("slug", ""))
    slug_label = UILabel(slug, variant="caption")
    v.addWidget(slug_label)

    # Metadata row
    meta_row = QHBoxLayout()
    mtime_str = str(payload.get("mtime", ""))
    if mtime_str:
        mtime_label = UILabel(f"Modified: {mtime_str}", variant="caption")
        meta_row.addWidget(mtime_label)
    meta_row.addStretch(1)
    v.addLayout(meta_row)

    size_str = str(payload.get("size", ""))
    if size_str:
        size_label = UILabel(f"Size: {size_str}", variant="caption")
        v.addWidget(size_label)

    # Action buttons
    v.addSpacing(4)
    load_btn = UIButton("Load", variant="primary")
    load_btn.clicked.connect(lambda: print(f"[stub] Load preset: {payload.get('name')}"))
    v.addWidget(load_btn)

    delete_btn = UIButton("Delete", variant="secondary")
    delete_btn.clicked.connect(lambda: print(f"[stub] Delete preset: {payload.get('name')}"))
    v.addWidget(delete_btn)

    export_btn = UIButton("Export cheat sheet", variant="ghost")
    export_btn.clicked.connect(lambda: print(f"[stub] Export cheat sheet: {payload.get('name')}"))
    v.addWidget(export_btn)

    v.addStretch(1)
    return wrap
