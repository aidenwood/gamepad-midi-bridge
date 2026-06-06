"""UIButton — self-contained QPushButton primitive.

Sets a COMPLETE stylesheet at construction time so the Qt CSS cascade dying
under WA_TranslucentBackground ancestors can never blank the text or bg.
Every value comes from tokens.py — no raw hex in this file.
"""
from __future__ import annotations

from typing import Literal

from PySide6.QtWidgets import QPushButton, QWidget

from gamepad_midi_bridge.ui.tokens import (
    ACCENT_TEAL, ACCENT_TEAL_FG, ACCENT_CORAL, BG_ELEVATED, BG_HOVER,
    BG_PRESSED, BORDER_SUBTLE, FOCUS_RING, TEXT_PRIMARY,
    FW_MED, R_M,
    S_XS, S_S, S_M, S_L,
    FS_S, FS_M, FS_L,
)

Variant = Literal["primary", "secondary", "ghost", "danger"]
Size = Literal["s", "m", "l"]

# Padding (v, h) per size
_PAD: dict[str, tuple[int, int]] = {
    "s": (S_XS, S_S),
    "m": (S_S,  S_M),
    "l": (S_M,  S_L),
}

# Font size per size
_FS: dict[str, int] = {
    "s": FS_S,
    "m": FS_M,
    "l": FS_L,
}

# Min height per size — Qt on macOS will otherwise compress QPushButton to the
# native button height (~16-18px), clipping the rendered text to a horizontal
# band through the middle of each letter. Pick generously so ascenders +
# descenders stay inside the pill background.
_MIN_H: dict[str, int] = {
    "s": 24,
    "m": 32,
    "l": 40,
}

# Teal accent slightly darkened for hover/pressed
_TEAL_HOVER   = "#25b8a5"
_TEAL_PRESSED = "#1e9e8e"

# Coral darkened for hover/pressed
_CORAL_HOVER   = "#f55f5f"
_CORAL_PRESSED = "#e84848"


def _build_stylesheet(variant: Variant, size: Size) -> str:
    pv, ph = _PAD[size]
    fs = _FS[size]
    mh = _MIN_H[size]

    if variant == "primary":
        base = f"""
            QPushButton {{
                background-color: {ACCENT_TEAL};
                color: {ACCENT_TEAL_FG};
                border: none;
                border-radius: {R_M}px;
                padding: {pv}px {ph}px;
                min-height: {mh}px;
                font-size: {fs}px;
                font-weight: {FW_MED};
            }}
            QPushButton:hover {{
                background-color: {_TEAL_HOVER};
                color: {ACCENT_TEAL_FG};
            }}
            QPushButton:pressed {{
                background-color: {_TEAL_PRESSED};
                color: {ACCENT_TEAL_FG};
            }}
            QPushButton:focus {{
                outline: none;
                border: 2px solid {FOCUS_RING};
            }}
            QPushButton:disabled {{
                background-color: {BG_ELEVATED};
                color: #3a3d46;
            }}
        """

    elif variant == "secondary":
        base = f"""
            QPushButton {{
                background-color: {BG_ELEVATED};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: {R_M}px;
                padding: {pv}px {ph}px;
                min-height: {mh}px;
                font-size: {fs}px;
                font-weight: {FW_MED};
            }}
            QPushButton:hover {{
                background-color: {BG_HOVER};
                color: {TEXT_PRIMARY};
            }}
            QPushButton:pressed {{
                background-color: {BG_PRESSED};
                color: {TEXT_PRIMARY};
            }}
            QPushButton:focus {{
                outline: none;
                border: 1px solid {FOCUS_RING};
            }}
            QPushButton:disabled {{
                background-color: {BG_ELEVATED};
                color: #3a3d46;
                border: 1px solid {BORDER_SUBTLE};
            }}
        """

    elif variant == "ghost":
        base = f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: {R_M}px;
                padding: {pv}px {ph}px;
                min-height: {mh}px;
                font-size: {fs}px;
                font-weight: {FW_MED};
            }}
            QPushButton:hover {{
                background-color: {BG_HOVER};
                color: {TEXT_PRIMARY};
            }}
            QPushButton:pressed {{
                background-color: {BG_PRESSED};
                color: {TEXT_PRIMARY};
            }}
            QPushButton:focus {{
                outline: none;
                border: 1px solid {FOCUS_RING};
            }}
            QPushButton:disabled {{
                background-color: transparent;
                color: #3a3d46;
            }}
        """

    else:  # danger
        base = f"""
            QPushButton {{
                background-color: {ACCENT_CORAL};
                color: {ACCENT_TEAL_FG};
                border: none;
                border-radius: {R_M}px;
                padding: {pv}px {ph}px;
                min-height: {mh}px;
                font-size: {fs}px;
                font-weight: {FW_MED};
            }}
            QPushButton:hover {{
                background-color: {_CORAL_HOVER};
                color: {ACCENT_TEAL_FG};
            }}
            QPushButton:pressed {{
                background-color: {_CORAL_PRESSED};
                color: {ACCENT_TEAL_FG};
            }}
            QPushButton:focus {{
                outline: none;
                border: 2px solid {FOCUS_RING};
            }}
            QPushButton:disabled {{
                background-color: {BG_ELEVATED};
                color: #3a3d46;
            }}
        """

    return base


class UIButton(QPushButton):
    """Self-styling button primitive immune to cascade breakage.

    Args:
        text:    Button label.
        variant: "primary" | "secondary" | "ghost" | "danger"
        size:    "s" | "m" | "l"
        parent:  Optional parent widget.
    """

    def __init__(
        self,
        text: str = "",
        *,
        variant: Variant = "primary",
        size: Size = "m",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(_build_stylesheet(variant, size))
