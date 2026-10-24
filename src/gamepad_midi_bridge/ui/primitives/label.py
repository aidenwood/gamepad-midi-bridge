"""UILabel — self-contained QLabel primitive with semantic variants.

Sets its own complete stylesheet so the Qt CSS cascade dying under
WA_TranslucentBackground ancestors can never blank the text.
All values from tokens.
"""
from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QWidget

from gamepad_midi_bridge.ui.tokens import (
    ACCENT_TEAL,
    ACCENT_TEAL_FG,
    BG_ELEVATED,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    FS_L,
    FS_M,
    FS_S,
    FS_XL,
    FS_XS,
    FW_BOLD,
    FW_MED,
    FW_REG,
    R_PILL,
    S_S,
    S_XS,
)

Variant = Literal["heading", "subheading", "body", "caption", "chip"]


def _build_stylesheet(variant: Variant) -> str:
    if variant == "heading":
        return f"""
            QLabel {{
                font-size: {FS_XL}px;
                font-weight: {FW_BOLD};
                color: {TEXT_PRIMARY};
                background-color: transparent;
            }}
        """

    elif variant == "subheading":
        return f"""
            QLabel {{
                font-size: {FS_L}px;
                font-weight: {FW_MED};
                color: {TEXT_PRIMARY};
                background-color: transparent;
            }}
        """

    elif variant == "body":
        return f"""
            QLabel {{
                font-size: {FS_M}px;
                font-weight: {FW_REG};
                color: {TEXT_SECONDARY};
                background-color: transparent;
            }}
        """

    elif variant == "caption":
        return f"""
            QLabel {{
                font-size: {FS_S}px;
                font-weight: {FW_REG};
                color: {TEXT_MUTED};
                background-color: transparent;
            }}
        """

    else:  # chip
        return f"""
            QLabel {{
                font-size: {FS_XS}px;
                font-weight: {FW_BOLD};
                color: {ACCENT_TEAL_FG};
                background-color: {ACCENT_TEAL};
                border-radius: {R_PILL}px;
                padding: {S_XS}px {S_S}px;
                letter-spacing: 0.5px;
            }}
        """


class UILabel(QLabel):
    """Self-styling label primitive immune to cascade breakage.

    Args:
        text:    Label text.
        variant: "heading" | "subheading" | "body" | "caption" | "chip"
        parent:  Optional parent widget.
    """

    def __init__(
        self,
        text: str = "",
        *,
        variant: Variant = "body",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        # body and caption word-wrap by default; heading/subheading/chip don't
        if variant in ("body", "caption"):
            self.setWordWrap(True)
        self.setStyleSheet(_build_stylesheet(variant))


class ElidingLabel(QLabel):
    """QLabel that shortens its text with an ellipsis instead of clipping it.

    A plain QLabel in a cramped row renders "Plug in a cont" — a sentence cut
    mid-word, which reads as a rendering bug rather than as truncation. This
    keeps the full string and paints as much of it as fits, with "…".

    ``text()`` deliberately returns the FULL string, not the elided one: the
    STATUS dropdown copies the status line into a menu item, and a menu that
    says "Plug in a cont…" would be the same bug one layer down.
    """

    def __init__(
        self,
        text: str = "",
        *,
        mode: Qt.TextElideMode = Qt.ElideRight,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._full_text = text
        self._mode = mode
        # Never let the full string set the widget's width floor — that is
        # precisely what stops a parent row from getting narrower.
        self.setMinimumWidth(0)
        super().setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text or ""
        self._apply_elide()

    def text(self) -> str:
        return self._full_text

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        available = max(0, self.width())
        if available <= 0:
            super().setText(self._full_text)
            return
        super().setText(
            self.fontMetrics().elidedText(self._full_text, self._mode, available)
        )
