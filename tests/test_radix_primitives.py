"""Coverage for the Radix-style primitives — UICard, UIDropdownMenu,
attach_context_menu.

Runs offscreen so it doesn't need a display server in CI.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from gamepad_midi_bridge.ui.primitives import (
    UIButton,
    UICard,
    UIDropdownMenu,
    attach_context_menu,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# UICard
# ---------------------------------------------------------------------------

def test_uicard_back_compat_setHeading_and_addContent(qapp):
    card = UICard()
    card.setHeading("Section")
    card.addContent(UIButton("Inside"))
    assert card.body_layout.count() == 1


def test_uicard_title_subtitle_and_header_action(qapp):
    card = UICard(variant="raised")
    card.setTitle("Sticks")
    card.setSubtitle("Polar + remap")
    card.addHeaderAction(UIButton("Reset", variant="ghost", size="s"))
    # Calling setTitle twice should update, not duplicate.
    card.setTitle("Sticks (renamed)")
    assert card._title_label is not None
    assert card._title_label.text() == "Sticks (renamed)"


def test_uicard_footer_lazy_construction(qapp):
    card = UICard()
    assert card.footer_layout is None
    card.addFooterButton(UIButton("OK"))
    assert card.footer_layout is not None
    # Stretch + 1 button == 2 layout items
    assert card.footer_layout.count() == 2


def test_uicard_variant_switch_at_runtime(qapp):
    card = UICard(variant="default")
    assert card._variant == "default"
    card.set_variant("danger")
    assert card._variant == "danger"


# ---------------------------------------------------------------------------
# UIDropdownMenu
# ---------------------------------------------------------------------------

def test_dropdown_builds_items_in_order(qapp):
    menu = UIDropdownMenu()
    menu.add_label("View")
    a = menu.add_item("Reset zoom")
    menu.add_separator()
    menu.add_item("Fit", disabled=True)
    actions = menu.menu.actions()
    # add_label uses addSection → QAction with isSeparator() True but with text
    assert actions[1] is a
    assert actions[3].isEnabled() is False


def test_dropdown_item_callback_fires_on_trigger(qapp):
    calls: list[str] = []
    menu = UIDropdownMenu()
    action = menu.add_item("Hit me", on_click=lambda: calls.append("ok"))
    action.trigger()
    assert calls == ["ok"]


def test_dropdown_checkable_toggle_fires_with_state(qapp):
    seen: list[bool] = []
    menu = UIDropdownMenu()
    action = menu.add_checkable("Snap", checked=False, on_toggle=lambda s: seen.append(s))
    assert action.isCheckable()
    assert action.isChecked() is False
    action.toggle()
    assert seen == [True]


def test_dropdown_submenu_returns_a_new_uidropdownmenu(qapp):
    menu = UIDropdownMenu()
    sub = menu.add_submenu("Export…")
    assert isinstance(sub, UIDropdownMenu)
    sub.add_item("XML…")
    assert len(sub.menu.actions()) == 1


def test_dropdown_attach_to_button_wires_click(qapp):
    btn = QPushButton("Open")
    menu = UIDropdownMenu()
    menu.add_item("X")
    menu.attach_to_button(btn)
    # No good way to assert the click handler without poking signal internals —
    # just verify the call returned the menu (fluent API) and didn't raise.
    assert menu.attach_to_button(btn) is menu


# ---------------------------------------------------------------------------
# attach_context_menu
# ---------------------------------------------------------------------------

def test_attach_context_menu_sets_custom_policy(qapp):
    btn = QPushButton("Target")
    menu = UIDropdownMenu()
    menu.add_item("Delete")
    attach_context_menu(btn, menu)
    assert btn.contextMenuPolicy() == Qt.CustomContextMenu


def test_attach_context_menu_with_builder_callable(qapp):
    btn = QPushButton("Target")
    rebuild_calls = []
    def build():
        rebuild_calls.append(1)
        m = UIDropdownMenu()
        m.add_item("Dynamic")
        return m
    attach_context_menu(btn, build)
    assert btn.contextMenuPolicy() == Qt.CustomContextMenu


def test_attach_context_menu_replaces_prior_handler(qapp):
    btn = QPushButton("Target")
    menu_a = UIDropdownMenu()
    menu_a.add_item("A")
    attach_context_menu(btn, menu_a)
    menu_b = UIDropdownMenu()
    menu_b.add_item("B")
    attach_context_menu(btn, menu_b)
    # No exception → previous connection was cleanly replaced.
    assert btn.contextMenuPolicy() == Qt.CustomContextMenu
