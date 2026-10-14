"""UICard — Radix-style card container.

Three structured slots:
    header_layout — title + optional subtitle + right-aligned actions row
    body_layout   — main content (use addContent / .body_layout directly)
    footer_layout — right-aligned button row (use addFooterButton or .footer_layout)

Variants control the surface treatment:
    "default"  — flat surface card on BG_SURFACE
    "raised"   — slight elevation (BG_ELEVATED + stronger border) for stacked layouts
    "bordered" — transparent fill + visible border, for grouping inside a card
    "danger"   — coral-tinted border for destructive sections

Every value comes from tokens.py. Layout is QVBoxLayout outer, with header /
body / footer added in order. Footer + header only render when populated, so
a bare card (no setHeading / addFooterButton) collapses to body-only.

Backwards-compatible with the previous minimal API: ``setHeading`` and
``addContent`` still work; the new richer methods (``setTitle``, ``setSubtitle``,
``addHeaderAction``, ``addFooterButton``, ``set_variant``) live alongside.
"""
from __future__ import annotations

from typing import Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from gamepad_midi_bridge.ui.tokens import (
    ACCENT_CORAL,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER_STRONG,
    BORDER_SUBTLE,
    R_L,
    S_M,
    S_S,
    S_L,
)
from gamepad_midi_bridge.ui.primitives.label import UILabel


Variant = Literal["default", "raised", "bordered", "danger"]


def _build_stylesheet(variant: Variant) -> str:
    if variant == "raised":
        bg, border = BG_ELEVATED, BORDER_STRONG
    elif variant == "bordered":
        bg, border = "transparent", BORDER_SUBTLE
    elif variant == "danger":
        bg, border = BG_SURFACE, ACCENT_CORAL
    else:  # default
        bg, border = BG_SURFACE, BORDER_SUBTLE
    return f"""
        QFrame#UICardRoot {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {R_L}px;
        }}
    """


class UICard(QFrame):
    """Self-styling card container with structured slots.

    Backwards-compatible quick API::

        card = UICard()
        card.setHeading("Section title")
        card.addContent(some_widget)

    Richer Radix-style API::

        card = UICard(variant="raised")
        card.setTitle("Sticks")
        card.setSubtitle("Polar transform + range remap")
        card.addHeaderAction(UIButton("Reset", variant="ghost", size="s"))
        card.addContent(graph_view)
        card.addFooterButton(UIButton("Apply", variant="primary"))
    """

    def __init__(
        self,
        *,
        variant: Variant = "default",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("UICardRoot")
        self._variant: Variant = variant
        self.setStyleSheet(_build_stylesheet(variant))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(S_L, S_L, S_L, S_L)
        outer.setSpacing(S_M)

        # Header row — built lazily so a bare card stays compact.
        self._header_row: Optional[QHBoxLayout] = None
        self._title_col_layout: Optional[QVBoxLayout] = None
        self._title_label: Optional[UILabel] = None
        self._subtitle_label: Optional[UILabel] = None

        # Body — always present; addContent appends here.
        self.body_layout = QVBoxLayout()
        self.body_layout.setSpacing(S_M)
        outer.addLayout(self.body_layout)

        # Footer — built lazily on first addFooterButton.
        self.footer_layout: Optional[QHBoxLayout] = None
        self._outer = outer

    # -------------------------------------------------- variant

    def set_variant(self, variant: Variant) -> None:
        """Re-style after construction. Useful for state-driven cards
        (e.g. flipping to ``"danger"`` when validation fails)."""
        self._variant = variant
        self.setStyleSheet(_build_stylesheet(variant))

    # -------------------------------------------------- header API

    def setTitle(self, text: str) -> None:
        """Set or replace the card's title. Creates the header row lazily."""
        self._ensure_header()
        if self._title_label is None:
            self._title_label = UILabel(text, variant="subheading")
            assert self._title_col_layout is not None
            self._title_col_layout.addWidget(self._title_label)
        else:
            self._title_label.setText(text)

    def setSubtitle(self, text: str) -> None:
        """Set or replace the card's subtitle below the title."""
        self._ensure_header()
        if self._subtitle_label is None:
            self._subtitle_label = UILabel(text, variant="caption")
            assert self._title_col_layout is not None
            self._title_col_layout.addWidget(self._subtitle_label)
        else:
            self._subtitle_label.setText(text)

    def addHeaderAction(self, widget: QWidget) -> None:
        """Add a widget (usually a small UIButton) to the right side of the
        header row. Multiple actions stack right-to-left in insertion order."""
        self._ensure_header()
        assert self._header_row is not None
        self._header_row.addWidget(widget, 0, Qt.AlignVCenter)

    def setHeading(self, text: str) -> None:
        """Back-compat alias — treats ``text`` as the title."""
        self.setTitle(text)

    # -------------------------------------------------- body API

    def addContent(self, widget: QWidget) -> None:
        """Append a widget to the body. Same as ``self.body_layout.addWidget``."""
        self.body_layout.addWidget(widget)

    # -------------------------------------------------- footer API

    def addFooterButton(self, widget: QWidget) -> None:
        """Append a widget (usually a UIButton) to the footer row.

        Footer is right-aligned and only renders when at least one button
        has been added — bare cards stay compact.
        """
        if self.footer_layout is None:
            self.footer_layout = QHBoxLayout()
            self.footer_layout.setSpacing(S_S)
            self.footer_layout.addStretch(1)
            self._outer.addLayout(self.footer_layout)
        self.footer_layout.addWidget(widget)

    # -------------------------------------------------- internals

    def _ensure_header(self) -> None:
        """Build the header row + title column on first use."""
        if self._header_row is not None:
            return
        self._header_row = QHBoxLayout()
        self._header_row.setSpacing(S_M)
        self._title_col_layout = QVBoxLayout()
        self._title_col_layout.setSpacing(2)
        self._header_row.addLayout(self._title_col_layout, 1)
        self._outer.insertLayout(0, self._header_row)
