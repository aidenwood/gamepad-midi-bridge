"""Canvas left dock — Figma / Photoshop / Sheets-inspired tool palette.

Lives inside the Nodes tab as a thin vertical column to the left of the
canvas. Hosts:

    - Canvas tools: Fit to view, Reset zoom, Pan toggle
    - Radix-style dropdowns: Add Node ▾, Add Output ▾
    - (Future) Layout presets, View toggles

Designed to be cheap to extend — each section is its own `_section_*`
builder, the constructor stitches them together with separators. Adding
a new section is one method + one call in __init__.

Background colour: ``BG_SURFACE`` — sits slightly above the canvas's
``BG_BASE`` so the column reads as chrome, not content.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .primitives import UIButton, UIDropdownMenu


# Visual constants — tuned for the Sheets/Figma "tight chrome" look.
_DOCK_WIDTH = 64                 # collapsed (icon-only) width
_BUTTON_SIZE = 44                # square icon buttons
_SECTION_GAP = 10                # vertical pad between sections


class CanvasLeftDock(QWidget):
    """Thin left-side tool palette for the Nodes tab canvas.

    Construction order: build the dock first, then call ``bind(view, scene)``
    once the canvas + scene are alive so the buttons + dropdowns can wire
    their click handlers to view methods and scene mutators.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CanvasLeftDock")
        self.setFixedWidth(_DOCK_WIDTH)
        # Owns its full stylesheet so the WA_TranslucentBackground cascade
        # can't blank it — matches the UIButton / UICard approach.
        self.setStyleSheet("""
            QWidget#CanvasLeftDock {
                background-color: #15171d;
                border-right: 1px solid #24262d;
            }
            QPushButton#DockButton {
                background-color: transparent;
                color: #c2c6cc;
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 10px;
                font-weight: 600;
                padding: 0;
            }
            QPushButton#DockButton:hover {
                background-color: #22242c;
                color: #f5f7fa;
                border-color: #2c313b;
            }
            QPushButton#DockButton:pressed {
                background-color: #2a2d36;
            }
            QFrame#DockSep {
                background-color: #24262d;
                max-height: 1px;
                min-height: 1px;
                margin: 2px 8px;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 10, 8, 10)
        outer.setSpacing(4)

        # Section 1 — canvas view tools
        self.btn_fit = self._dock_button("FIT", tooltip="Fit graph to viewport (F)")
        self.btn_reset = self._dock_button("100%", tooltip="Reset zoom (1)")
        outer.addWidget(self.btn_fit)
        outer.addWidget(self.btn_reset)
        outer.addWidget(self._separator())

        # Section 2 — Add menus (Radix dropdowns)
        self.btn_add_input = self._dock_button("+ IN", tooltip="Add a controller input source…")
        self.btn_add_node = self._dock_button("+ NODE", tooltip="Add a transform node…")
        # Templates sit above single nodes deliberately: on an empty canvas a
        # starter sub-graph is almost always the better first move, and the
        # node list means nothing until you have seen one wired up.
        self.btn_add_template = self._dock_button(
            "+ START", tooltip="Drop a starter template — a small working sub-graph…",
        )
        self.btn_add_output = self._dock_button("+ OUT", tooltip="Add a MIDI output…")
        outer.addWidget(self.btn_add_template)
        outer.addWidget(self.btn_add_input)
        outer.addWidget(self.btn_add_node)
        outer.addWidget(self.btn_add_output)
        outer.addWidget(self._separator())

        # Section 3 — Quick clear / cancel
        self.btn_cancel = self._dock_button("ESC", tooltip="Cancel pending wire (Esc)")
        outer.addWidget(self.btn_cancel)

        outer.addStretch(1)

        # Held until bind() wires them. None means "not yet attached".
        self._view = None
        self._scene = None
        # Keep dropdown menus alive across button clicks.
        self._add_node_menu: Optional[UIDropdownMenu] = None
        self._add_template_menu: Optional[UIDropdownMenu] = None
        self._add_output_menu: Optional[UIDropdownMenu] = None

    # ----------------------------------------------------------- public API

    def bind(self, view, scene) -> None:
        """Hook button clicks to the live view + scene.

        Done after construction because the dock sits at the same widget
        layer as the view inside NodesTab — neither knows about the other
        at __init__ time.
        """
        self._view = view
        self._scene = scene

        self.btn_fit.clicked.connect(view.fit_to_graph)
        self.btn_reset.clicked.connect(view.resetTransform)
        self.btn_cancel.clicked.connect(scene._cancel_wire_drag)

        # Rebuild the dropdowns on every open so they reflect the current
        # node registry + always drop new items at the centre of the view.
        self.btn_add_input.clicked.connect(self._popup_add_input)
        self.btn_add_node.clicked.connect(self._popup_add_node)
        self.btn_add_template.clicked.connect(self._popup_add_template)
        self.btn_add_output.clicked.connect(self._popup_add_output)

    # ----------------------------------------------------------- internals

    def _dock_button(self, text: str, *, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("DockButton")
        btn.setFixedSize(_BUTTON_SIZE + 4, _BUTTON_SIZE - 6)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setObjectName("DockSep")
        sep.setFrameShape(QFrame.HLine)
        return sep

    # ----------------------------------------------------------- menu popups

    def _viewport_centre_scene_pos(self):
        """Pick a sensible scene position for a newly-added item: the
        centre of the currently-visible viewport."""
        if self._view is None:
            from PySide6.QtCore import QPointF
            return QPointF(0, 0)
        vp = self._view.viewport().rect()
        return self._view.mapToScene(vp.center())

    def _popup_add_node(self) -> None:
        if self._scene is None:
            return
        from .nodes_canvas import build_add_node_menu
        self._add_node_menu = build_add_node_menu(
            self._scene, self._viewport_centre_scene_pos(),
        )
        # Pop the menu just below the button so the user can scan it like
        # a Sheets-style ribbon dropdown.
        pos = self.btn_add_node.mapToGlobal(self.btn_add_node.rect().bottomRight())
        self._add_node_menu.popup_at_global(pos)

    def _popup_add_template(self) -> None:
        if self._scene is None:
            return
        from .nodes_canvas import build_template_menu
        self._add_template_menu = build_template_menu(
            self._scene, self._viewport_centre_scene_pos(),
        )
        pos = self.btn_add_template.mapToGlobal(
            self.btn_add_template.rect().bottomRight(),
        )
        self._add_template_menu.popup_at_global(pos)

    def _popup_add_input(self) -> None:
        if self._scene is None:
            return
        # Reuse the right-click menu's Add Input submenu directly so the
        # entries stay in lockstep — one source of truth for source picker.
        from .nodes_canvas import build_add_node_menu
        full = build_add_node_menu(self._scene, self._viewport_centre_scene_pos())
        for action in full.menu.actions():
            if action.menu() is not None and "Controller Input" in (action.text() or ""):
                pos = self.btn_add_input.mapToGlobal(self.btn_add_input.rect().bottomRight())
                action.menu().popup(pos)
                self._add_input_menu = full      # pin parent alive
                return
        pos = self.btn_add_input.mapToGlobal(self.btn_add_input.rect().bottomRight())
        full.popup_at_global(pos)
        self._add_input_menu = full

    def _popup_add_output(self) -> None:
        if self._scene is None:
            return
        # Use the Add Output submenu directly — pulled out of the bigger
        # Add Node menu via the existing builder.
        from .nodes_canvas import build_add_node_menu
        full = build_add_node_menu(self._scene, self._viewport_centre_scene_pos())
        # Find the "MIDI Output…" sub-action and pop its submenu directly.
        for action in full.menu.actions():
            if action.menu() is not None and "MIDI" in (action.text() or ""):
                pos = self.btn_add_output.mapToGlobal(self.btn_add_output.rect().bottomRight())
                action.menu().popup(pos)
                self._add_output_menu = full       # pin parent alive
                return
        # Fall back: just open the full menu if the sub couldn't be found.
        pos = self.btn_add_output.mapToGlobal(self.btn_add_output.rect().bottomRight())
        full.popup_at_global(pos)
        self._add_output_menu = full
