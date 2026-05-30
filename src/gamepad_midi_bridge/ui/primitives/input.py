"""UIInput, UISpinBox, UIDoubleSpinBox — self-contained input primitives.

Each sets its own complete stylesheet so the Qt CSS cascade dying under
WA_TranslucentBackground ancestors can never break them. All values from tokens.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit, QSpinBox, QWidget

from gamepad_midi_bridge.ui.tokens import (
    BG_ELEVATED,
    BORDER_SUBTLE,
    FOCUS_RING,
    R_M,
    TEXT_DISABLED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    FS_M,
    FW_REG,
    S_M,
    S_S,
)

_SHARED_SS = f"""
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: {R_M}px;
    padding: {S_S}px {S_M}px;
    font-size: {FS_M}px;
    font-weight: {FW_REG};
    selection-background-color: {FOCUS_RING};
    selection-color: #06070a;
"""

_FOCUS_SS = f"""
    border: 1px solid {FOCUS_RING};
    outline: none;
"""

_DISABLED_SS = f"""
    background-color: {BG_ELEVATED};
    color: {TEXT_DISABLED};
    border: 1px solid {BORDER_SUBTLE};
"""


class UIInput(QLineEdit):
    """Self-styling QLineEdit primitive."""

    def __init__(
        self,
        placeholder: str = "",
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self.setStyleSheet(f"""
            QLineEdit {{
                {_SHARED_SS}
            }}
            QLineEdit:focus {{
                {_FOCUS_SS}
            }}
            QLineEdit:disabled {{
                {_DISABLED_SS}
            }}
            QLineEdit::placeholder {{
                color: {TEXT_SECONDARY};
            }}
        """)


class UISpinBox(QSpinBox):
    """Self-styling QSpinBox primitive."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QSpinBox {{
                {_SHARED_SS}
            }}
            QSpinBox:focus {{
                {_FOCUS_SS}
            }}
            QSpinBox:disabled {{
                {_DISABLED_SS}
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {BG_ELEVATED};
                border: none;
                width: 16px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: #2a2d36;
            }}
        """)


class UIDoubleSpinBox(QDoubleSpinBox):
    """Self-styling QDoubleSpinBox primitive."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QDoubleSpinBox {{
                {_SHARED_SS}
            }}
            QDoubleSpinBox:focus {{
                {_FOCUS_SS}
            }}
            QDoubleSpinBox:disabled {{
                {_DISABLED_SS}
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: {BG_ELEVATED};
                border: none;
                width: 16px;
            }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: #2a2d36;
            }}
        """)
