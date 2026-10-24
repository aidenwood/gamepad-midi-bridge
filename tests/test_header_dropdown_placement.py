"""A header dropdown must not hang outside the window it belongs to.

THE BUG, seen in the v3 screen recording at a 954px-wide window: the header
triggers are right-aligned and STATUS is the last one, but `_popup` anchored
every menu's LEFT edge under the button's left edge. The STATUS menu is wider
than the gap between that button and the right edge, so it grew straight out of
the window and its longest lines — "Plug in a controller, then open Connect."
and "Test controller inputs…" — were cut mid-word.

Nothing raised, because Qt keeps a popup on SCREEN and the screen is far wider
than the window. On a maximised window the bug is invisible; it only shows up
at the narrow sizes a laptop user actually runs.

These tests drive the real `_popup` with a stub menu whose width we control, so
they assert the placement arithmetic rather than a screenshot.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QMenu, QPushButton, QWidget


class _StubMenu(QMenu):
    """A menu with a width we dictate, and that records where it was put."""

    def __init__(self, width: int, parent=None):
        super().__init__(parent)
        self._w = width
        self.popped_at = None

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        return QSize(self._w, 200)

    def popup(self, pos, action=None):  # noqa: D102
        self.popped_at = pos
        # Deliberately not calling super() — showing a real popup in a test
        # run grabs the mouse and leaves a window behind.


@pytest.fixture()
def shell(qapp):
    """A minimal stand-in carrying just the geometry `_popup` reads."""
    from gamepad_midi_bridge.ui.main_window import MainWindow

    host = QWidget()
    host.setGeometry(0, 0, 954, 1348)

    # Bind the real method to a lightweight object — constructing a full
    # MainWindow here would start a bridge, open MIDI ports and poll hardware.
    class _Shell(QWidget):
        _popup = MainWindow._popup
        _style_menu = MainWindow._style_menu
        _MENU_CSS = MainWindow._MENU_CSS

    shell = _Shell()
    shell.setGeometry(0, 0, 954, 1348)
    return shell


def _button_at(parent: QWidget, x: int, width: int = 120) -> QPushButton:
    btn = QPushButton(parent)
    btn.setGeometry(x, 40, width, 36)
    return btn


class TestDropdownStaysInsideTheWindow:
    def test_right_edge_trigger_does_not_overflow(self, shell):
        """The STATUS case: last button, wide menu."""
        btn = _button_at(shell, x=790, width=150)   # right-aligned trigger
        menu = _StubMenu(width=320, parent=shell)

        shell._popup(menu, btn)

        left = menu.popped_at.x()
        window_right = shell.mapToGlobal(shell.rect().bottomRight()).x()
        assert left + 320 <= window_right, (
            "menu runs past the window's right edge — its longest items will "
            "be cut mid-word"
        )

    def test_right_edge_trigger_is_right_aligned_to_its_button(self, shell):
        """Not merely clamped — it should share the button's right edge."""
        btn = _button_at(shell, x=790, width=150)
        menu = _StubMenu(width=320, parent=shell)

        shell._popup(menu, btn)

        expected = btn.mapToGlobal(btn.rect().bottomRight()).x() - 320
        assert menu.popped_at.x() == expected

    def test_left_trigger_keeps_the_natural_left_anchor(self, shell):
        """Menus that already fit must not move — this is the common case."""
        btn = _button_at(shell, x=20, width=120)
        menu = _StubMenu(width=260, parent=shell)

        shell._popup(menu, btn)

        assert menu.popped_at.x() == btn.mapToGlobal(btn.rect().bottomLeft()).x()

    def test_menu_wider_than_the_window_clamps_to_the_left_edge(self, shell):
        """Degenerate case: right-aligning would push it off the LEFT edge."""
        btn = _button_at(shell, x=820, width=120)
        menu = _StubMenu(width=1400, parent=shell)   # wider than 954

        shell._popup(menu, btn)

        assert menu.popped_at.x() >= shell.mapToGlobal(shell.rect().topLeft()).x()

    def test_vertical_anchor_is_still_under_the_button(self, shell):
        """Horizontal placement must not disturb the drop-down position."""
        btn = _button_at(shell, x=790, width=150)
        menu = _StubMenu(width=320, parent=shell)

        shell._popup(menu, btn)

        assert menu.popped_at.y() == btn.mapToGlobal(btn.rect().bottomLeft()).y()

    def test_the_menu_is_held_so_it_is_not_collected(self, shell):
        """Pre-existing contract — a dropped reference closes the menu."""
        btn = _button_at(shell, x=20)
        menu = _StubMenu(width=200, parent=shell)

        shell._popup(menu, btn)

        assert shell._open_dropdown is menu
