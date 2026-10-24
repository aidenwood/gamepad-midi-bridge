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

from PySide6.QtCore import QSize
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


class ReflowFrame(QFrame):
    """QFrame that reports a width floor of zero.

    For containers whose children are re-arranged on every resize. Without
    this there is a deadlock: Qt refuses to make the window narrower than
    the CURRENT arrangement's minimum, so the resize that would trigger the
    narrower arrangement can never happen. The header sat at a 716 px floor
    for exactly this reason — it could not get narrow enough to wrap, so it
    overflowed instead.

    The owner is responsible for re-arranging on ``resizeEvent``; this only
    removes the floor that stops the event from ever arriving.
    """

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, super().minimumSizeHint().height())


class ReflowWidget(QWidget):
    """Plain-QWidget twin of :class:`ReflowFrame`. Same reasoning."""

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, super().minimumSizeHint().height())
