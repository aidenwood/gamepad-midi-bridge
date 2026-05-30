"""UICard — self-contained QFrame card primitive.

Sets its own complete stylesheet (bg, border, radius) so the Qt CSS cascade
dying under WA_TranslucentBackground ancestors can never break it.
All values from tokens.
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from gamepad_midi_bridge.ui.tokens import (
    BG_SURFACE,
    BORDER_SUBTLE,
    R_L,
    S_L,
)
from gamepad_midi_bridge.ui.primitives.label import UILabel


class UICard(QFrame):
    """Self-styling card container.

    Usage::

        card = UICard()
        card.setHeading("Section title")
        card.addContent(some_widget)
    """

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: {R_L}px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(S_L, S_L, S_L, S_L)
        self._layout.setSpacing(S_L)

    def setHeading(self, text: str) -> None:
        """Insert a heading UILabel at the top of the card."""
        heading = UILabel(text, variant="heading")
        # Always insert before other content widgets
        self._layout.insertWidget(0, heading)

    def addContent(self, widget: QWidget) -> None:
        """Append a widget to the card's layout."""
        self._layout.addWidget(widget)
