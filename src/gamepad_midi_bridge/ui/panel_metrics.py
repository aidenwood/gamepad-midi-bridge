"""Font-aware sizing for the bottom dock panel headers.

The console + MIDI-activity headers used to be ``setFixedHeight(36)`` with a
matching hardcoded ``_COLLAPSED_PANEL_PX = 36`` in MainWindow. 36 px is only
correct at the default font size: the A+/A- buttons rescale every
``font-size: Npx`` in the stylesheet AND the app font, but a frozen pixel
height cannot follow. At >=1.4x scale (two A+ presses, or a Windows box at
150% display scaling) the header text needs 39-41 px inside a 36 px bar, so
"CONSOLE" and "MIDI ACTIVITY" render vertically clipped — which is what a
Windows user's screen recording showed.

Size from the title label, which is the only child that grows with the font
(the Clear / toggle buttons are setFixedHeight(26), so they never drive it).
Note we deliberately do NOT use the header QLayout's own sizeHint(): before
the widget is polished and shown that returns a stale 36, which is the trap
this module exists to avoid.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLayout

# Never go below the original 36 px — at default scale the header also has to
# fit a 26 px button, and shrinking it would change the look on every box that
# was already rendering correctly.
HEADER_MIN_PX = 36


def header_height_for(title: QLabel, layout: QLayout) -> int:
    """Height a panel header needs so `title` is never vertically clipped."""
    if title is None:
        return HEADER_MIN_PX
    padding = 0
    if layout is not None:
        m = layout.contentsMargins()
        padding = m.top() + m.bottom()
    return max(HEADER_MIN_PX, title.sizeHint().height() + padding)
