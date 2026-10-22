"""DESCRIPTION panel — the hover-explains-everything window.

From Aiden's Setup wireframe: a small panel pinned over the lower-right of
the workspace with a title bar, a four-arrow move handle, and a body that
explains whatever the cursor is currently over.

Why this and not the existing LearnOverlay: that one follows the cursor,
which means it sits on top of the thing you are trying to read about and
moves while you are reading it. A docked panel stays put, so you can hover
a control, look across, and read — which is the behaviour the wireframe
asks for ("on hover description of any element on screen to help you
understand, plus a basic suggested use example and step 1 > 2 > 3 > 4").

Content comes from the same `learn(widget, title, text)` tags the hover
overlay already uses, so every control annotated for Learn mode works here
with no second registry to keep in sync.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from .icons import load_icon
from .learn_mode import _learn_for
from .tokens import (
    SHELL_DESC_BODY, SHELL_PURPLE, SHELL_TEAL, TEXT_PRIMARY, TEXT_SECONDARY,
)

PANEL_W = 300
PANEL_H = 210
POLL_MS = 140

_PLACEHOLDER = (
    "Hover any control and its explanation appears here.\n\n"
    "You can drag this panel by its title bar if it is covering something."
)


class DescriptionPanel(QFrame):
    """Docked, draggable hover-explainer. Parent it to the workspace."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DescriptionPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(PANEL_W, PANEL_H)
        self.setStyleSheet(f"""
            QFrame#DescriptionPanel {{
                background-color: {SHELL_DESC_BODY};
                border: 1px solid {SHELL_TEAL};
                border-radius: 6px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Title bar: label + move handle ──
        bar = QFrame()
        bar.setObjectName("DescriptionPanelBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setFixedHeight(32)
        bar.setStyleSheet(f"""
            QFrame#DescriptionPanelBar {{
                background-color: {SHELL_PURPLE};
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border-bottom: 1px solid {SHELL_TEAL};
            }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 0, 8, 0)
        h.setSpacing(8)
        self._title = QLabel("DESCRIPTION")
        self._title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 11px; "
            f"letter-spacing: 1.5px; background: transparent;")
        h.addWidget(self._title)
        h.addStretch(1)
        self._grip = QLabel()
        self._grip.setPixmap(load_icon("arrows-out-cardinal", SHELL_TEAL, 16)
                             .pixmap(16, 16))
        self._grip.setStyleSheet("background: transparent;")
        self._grip.setToolTip("Drag the title bar to move this panel")
        h.addWidget(self._grip)
        outer.addWidget(bar)

        # ── Body ──
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(12, 10, 12, 12)
        bv.setSpacing(6)
        self._subject = QLabel("")
        self._subject.setStyleSheet(
            f"color: {SHELL_TEAL}; font-size: 12px; font-weight: 600; "
            f"background: transparent;")
        self._subject.setWordWrap(True)
        bv.addWidget(self._subject)
        self._text = QLabel(_PLACEHOLDER)
        self._text.setWordWrap(True)
        self._text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._text.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent;")
        bv.addWidget(self._text, 1)
        outer.addWidget(body, 1)

        # Dragging is title-bar only, so a click in the body never nudges it.
        self._drag_from: Optional[QPoint] = None
        bar.mousePressEvent = self._bar_press        # type: ignore[assignment]
        bar.mouseMoveEvent = self._bar_move          # type: ignore[assignment]
        bar.mouseReleaseEvent = self._bar_release    # type: ignore[assignment]

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._refresh)
        self.hide()

    # ------------------------------------------------------------- lifecycle

    def set_active(self, active: bool) -> None:
        if active:
            self.place_default()
            self.show()
            self.raise_()
            self._timer.start()
        else:
            self._timer.stop()
            self.hide()

    def place_default(self) -> None:
        """Bottom-right of the parent, inset — where the wireframe puts it.

        Re-placed on every activation rather than once at construction: the
        parent has no useful size until it has been laid out, and the window
        may have been resized while the panel was hidden.
        """
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 18
        x = max(0, parent.width() - self.width() - margin)
        y = max(0, parent.height() - self.height() - margin)
        self.move(x, y)

    # --------------------------------------------------------------- dragging

    def _bar_press(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self.pos()

    def _bar_move(self, event) -> None:
        if self._drag_from is None:
            return
        new = event.globalPosition().toPoint() - self._drag_from
        parent = self.parentWidget()
        if parent is not None:
            # Keep it inside the window — a panel dragged off-screen is gone
            # for good, with no way to get it back.
            new.setX(max(0, min(new.x(), parent.width() - self.width())))
            new.setY(max(0, min(new.y(), parent.height() - self.height())))
        self.move(new)

    def _bar_release(self, _event) -> None:
        self._drag_from = None

    # ---------------------------------------------------------------- content

    def _refresh(self) -> None:
        """Describe whatever is under the cursor, ignoring ourselves."""
        widget = QApplication.widgetAt(QCursor.pos())
        if widget is not None and self.isAncestorOf(widget):
            return                      # hovering the panel: hold the last text
        found = _learn_for(widget)
        if found is None:
            self._subject.setText("")
            self._text.setText(_PLACEHOLDER)
            return
        title, text = found
        self._subject.setText(title)
        self._text.setText(text or "No description written for this yet.")
