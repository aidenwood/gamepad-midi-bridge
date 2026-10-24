"""No single tab page may set the floor for how narrow the window can get.

The window advertises a 380 px minimum. That is only true if every tab page
can live inside it — one page with a 549 px floor silently raises the whole
window's minimum, and the user simply cannot drag it narrower.

Two things used to break it, both fixed here:

* a word-wrapped ``UILabel`` still reported the UNWRAPPED width as its
  minimum, so a one-sentence subheading pinned its page (Marketplace: 437 px)
* a ``QHBoxLayout`` of buttons reports the SUM of its buttons as a minimum,
  so the Bluetooth tab's three-button action row demanded 509 px

Both now re-flow instead: the label wraps, the row wraps.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GMB_DEMO", "1")
os.environ.setdefault("GMB_UI_SMOKE", "1")

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

# The window's advertised floor. Pages must fit inside it with room to spare
# for the scroll area's own chrome.
WINDOW_FLOOR = 380


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _settle(app, passes: int = 8) -> None:
    for _ in range(passes):
        app.processEvents()


# ------------------------------------------------------------------ labels

def test_wrapping_label_reports_no_width_floor(app):
    from gamepad_midi_bridge.ui.primitives.label import UILabel
    long_text = ("Community presets — built by other players, free and paid, "
                 "installable in one click from inside the app.")
    for variant in ("body", "caption", "heading", "subheading"):
        label = UILabel(long_text, variant=variant)
        assert label.wordWrap(), f"{variant} should wrap"
        assert label.minimumSizeHint().width() == 0, (
            f"{variant} label pins its container to "
            f"{label.minimumSizeHint().width()}px")


def test_chip_label_still_stays_on_one_line(app):
    """A pill badge that wraps stops reading as a pill."""
    from gamepad_midi_bridge.ui.primitives.label import UILabel
    chip = UILabel("PRO", variant="chip")
    assert not chip.wordWrap()
    assert chip.minimumSizeHint().width() > 0


def test_wrapping_label_still_reserves_height_for_its_lines(app):
    """Dropping the width floor must not clip the second line."""
    from gamepad_midi_bridge.ui.primitives.label import UILabel
    label = UILabel("one two three four five six seven eight nine ten "
                    "eleven twelve thirteen fourteen", variant="body")
    label.resize(120, 10)
    _settle(app)
    assert label.minimumSizeHint().height() >= label.heightForWidth(120)
    assert label.heightForWidth(120) > label.heightForWidth(600)


# ------------------------------------------------------------- flow layout

def test_flow_layout_floor_is_its_widest_item_not_the_sum(app):
    from gamepad_midi_bridge.ui.primitives.flow_layout import FlowLayout
    host = QWidget()
    flow = FlowLayout(host, h_space=8, v_space=8)
    widest = 0
    total = 0
    for text in ("Open system Bluetooth settings", "Re-scan",
                 "\U0001F4D6 Connection guide"):
        btn = QPushButton(text)
        flow.addWidget(btn)
        widest = max(widest, btn.sizeHint().width())
        total += btn.sizeHint().width()
    _settle(app)
    floor = flow.minimumSize().width()
    assert floor <= widest + 2, f"floor {floor} should be the widest item {widest}"
    assert floor < total, "a flow layout must not demand the sum of its items"


def test_flow_layout_gets_taller_as_it_narrows(app):
    """Wrapping has to be reported upwards or the extra rows get clipped."""
    from gamepad_midi_bridge.ui.primitives.flow_layout import FlowLayout
    host = QWidget()
    flow = FlowLayout(host)
    for text in ("Open system Bluetooth settings", "Re-scan",
                 "\U0001F4D6 Connection guide"):
        flow.addWidget(QPushButton(text))
    _settle(app)
    assert flow.hasHeightForWidth()
    assert flow.heightForWidth(240) > flow.heightForWidth(900)


def test_flow_layout_places_every_item(app):
    from gamepad_midi_bridge.ui.primitives.flow_layout import FlowLayout
    host = QWidget()
    flow = FlowLayout(host)
    buttons = [QPushButton(f"button {i}") for i in range(5)]
    for b in buttons:
        flow.addWidget(b)
    flow.setGeometry(QRect(0, 0, 200, 400))
    _settle(app)
    assert flow.count() == 5
    assert all(b.size() != QSize(0, 0) for b in buttons)


# ------------------------------------------------------------------- pages

def test_no_tab_page_pins_the_window_above_its_floor(app, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))
    monkeypatch.setattr(QDialog, "exec", lambda self, *a, **k: 0)
    from gamepad_midi_bridge.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.resize(WINDOW_FLOOR, 820)
    _settle(app)
    try:
        tabs = win._workspace_a
        offenders = []
        for i in range(tabs.count()):
            page = tabs.widget(i)
            floor = page.minimumSizeHint().width()
            if floor > WINDOW_FLOOR:
                offenders.append((tabs.tabText(i), floor))
        assert not offenders, (
            f"these pages are wider than the {WINDOW_FLOOR}px window floor: "
            f"{offenders}")
    finally:
        win.close()
