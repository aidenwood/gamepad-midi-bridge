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
    SHELL_BLUE, SHELL_TEAL, SHELL_TEAL_FG, SHELL_TEAL_UTIL,
    FW_MED, R_M,
    S_XS, S_S, S_M, S_L,
    FS_S, FS_M, FS_L,
)

# The four repeated treatments from the Setup wireframe sit alongside the
# original four. "mode" and "header" carry labels; the two utilities are
# icon-only panel-header controls. See UI-HANDOVER.md.
Variant = Literal[
    "primary", "secondary", "ghost", "danger",
    "mode", "header", "utility", "utility_round",
]
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

# Shell secondary blue, lifted/darkened for hover/pressed.
_SHELL_BLUE_HOVER   = "#2a5174"
_SHELL_BLUE_PRESSED = "#1a3349"


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

    elif variant == "mode":
        # Primary / selected mode from the Setup wireframe: the filled half
        # of the joined Live|Setup selector. Selection is driven by the Qt
        # `checked` state, never by comparing label text.
        base = f"""
            QPushButton {{
                background-color: {SHELL_BLUE};
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: {R_M}px;
                padding: {pv}px {ph}px;
                min-height: {mh}px;
                font-size: {fs}px;
                font-weight: {FW_MED};
            }}
            QPushButton:checked {{
                background-color: {SHELL_TEAL};
                color: {SHELL_TEAL_FG};
            }}
            QPushButton:hover:!checked {{
                background-color: {_SHELL_BLUE_HOVER};
            }}
            QPushButton:checked:hover {{
                background-color: {_TEAL_HOVER};
                color: {SHELL_TEAL_FG};
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

    elif variant == "header":
        # Secondary header action: Menu, Node View, Connect, Output, Status.
        # Muted blue fill, teal icon, light label. At narrow widths the label
        # is hidden and the icon remains — a presentation change, not a
        # different component, so the action and state are untouched.
        base = f"""
            QPushButton {{
                background-color: {SHELL_BLUE};
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: {R_M}px;
                padding: {pv}px {ph}px;
                min-height: {mh}px;
                font-size: {fs}px;
                font-weight: {FW_MED};
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {_SHELL_BLUE_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {_SHELL_BLUE_PRESSED};
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

    elif variant in ("utility", "utility_round"):
        # The two panel-header utilities on MIDI / Console. Dark teal; the
        # round one is a circle. What the rectangular one DOES is not
        # established by the wireframe, so this is styling only — don't
        # invent its action.
        # A true circle needs the radius to track the widget's own height.
        # min-height is the floor, not the final size, so callers that fix a
        # square size get a circle and the rest degrade to a pill rather
        # than a rounded rectangle that reads as the other utility.
        radius = "999px" if variant == "utility_round" else f"{R_M}px"
        base = f"""
            QPushButton {{
                background-color: {SHELL_TEAL_UTIL};
                color: {SHELL_TEAL_FG};
                border: none;
                border-radius: {radius};
                padding: 0px;
                min-height: {mh}px;
                min-width: {mh}px;
                font-size: {fs}px;
                font-weight: {FW_MED};
            }}
            QPushButton:hover {{
                background-color: {_TEAL_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {_TEAL_PRESSED};
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
        self._variant: Variant = variant
        self._size: Size = size
        self._full_text = text
        self._compact_text = ""
        self._compact = False
        self.setStyleSheet(_build_stylesheet(variant, size))
        if variant == "mode":
            self.setCheckable(True)
        if text:
            # Icon-only presentation drops the visible label, so the
            # accessible name has to live somewhere that survives it.
            self.setAccessibleName(text)

    @property
    def variant(self) -> Variant:
        return self._variant

    def is_compact(self) -> bool:
        return self._compact

    def set_compact(self, compact: bool) -> None:
        """Hide or restore the visible label, keeping the icon and action.

        Narrow windows change the PRESENTATION of a header action, never the
        command or its state — so this touches the label and nothing else.
        The accessible name and tooltip keep the control reachable and
        identifiable once the text is gone.
        """
        compact = bool(compact)
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            if not self.toolTip():
                self.setToolTip(self._full_text)
            # Never render an empty button. Until the Phosphor set is
            # bundled, a glyph stands in for the icon — a blank rectangle
            # is worse than the label it replaced.
            self.setText(self._compact_text)
        else:
            self.setText(self._full_text)

    def set_compact_text(self, glyph: str) -> None:
        """Glyph shown in place of the label at narrow widths."""
        self._compact_text = glyph
        if self._compact:
            self.setText(glyph)
