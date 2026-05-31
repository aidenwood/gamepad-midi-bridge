"""UIChromeFrame — opaque app-chrome QFrame primitive.

Defence-in-depth against the macOS translucent-ancestor paint bug. When a
parent widget has ``WA_TranslucentBackground`` set (which the main window
needs when a 3D background layer sits behind it), Qt stops clearing
descendant pixels before each repaint and text/buttons start ghosting.

A ``UIChromeFrame`` sets ``autoFillBackground`` + an explicit
``background-color`` from tokens at construction, so it always paints onto
cleared pixels regardless of what its ancestors do.

Use this as the outer container for any panel that lives in the app chrome
(status bar, log dock, MIDI activity dock, side panels). All values from
tokens.
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QWidget

from gamepad_midi_bridge.ui.tokens import BG_BASE


class UIChromeFrame(QFrame):
    """Self-styling opaque chrome container.

    Usage::

        frame = UIChromeFrame()
        layout = QVBoxLayout(frame)
        layout.addWidget(...)
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        background: str = BG_BASE,
    ) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            f"QFrame {{ background-color: {background}; }}"
        )
