"""Every in-app menu must opt into the dropdown styling.

`styles.qss` styles `QMenu#UIDropdownMenu` — scoped by objectName on purpose,
so the app's dark surface does not leak into native menus we do not own. Five
in-app menus were built as bare `QMenu(self)` and never set that name, so none
of that rule reached them: they fell back to the global `QWidget` background
and rendered as a flat #0e0f12 box instead of the intended #1d2028 elevated
card with its border, radius, item padding and hover states.

Nothing caught it because a stylesheet selector that matches nothing is not an
error. It is silent, and the fallback still looks plausible.

SCOPE — this is cosmetic consistency, not a legibility bug. Rendering both
offscreen against the real stylesheet gives #1d2028 styled and #0e0f12 bare,
both fully opaque. The see-through menu in the v3 screen recording is a
crossfade frame between the menu closing and the Connectors tab opening; the
frames either side show it painting solidly. Do not cite that frame here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

UI_DIR = Path(__file__).resolve().parents[1] / "src" / "gamepad_midi_bridge" / "ui"

#: The tray menu is deliberately native — see the QMenu block in styles.qss.
NATIVE_BY_DESIGN = {"tray.py"}


def _ui_sources() -> list[Path]:
    return [p for p in UI_DIR.rglob("*.py") if p.name != "dropdown.py"]


class TestEveryInAppMenuIsStyled:
    def test_every_menu_gets_a_look_from_somewhere(self):
        """A raw `QMenu(...)` that nothing ever styles falls back to the bare
        `QWidget` background and does not look like this app.

        Two ways to be styled, and both are legitimate:

        * ``style_as_dropdown(...)`` — opts into the global Radix-ish
          ``QMenu#UIDropdownMenu`` card.
        * an explicit ``setStyleSheet`` on the menu — ``MainWindow._style_menu``
          does this for the header dropdowns, giving them the purple/teal shell
          look on purpose ("one look for every header dropdown"). An inline
          stylesheet beats the application one, so adding the objectName there
          would only blend two design languages.

        So this checks a menu is styled, not *how*.
        """
        offenders: list[str] = []
        for path in _ui_sources():
            if path.name in NATIVE_BY_DESIGN:
                continue
            text = path.read_text()
            styles_its_menus = "_style_menu" in text or "setStyleSheet" in text
            for lineno, line in enumerate(text.splitlines(), 1):
                if not re.search(r"=\s*QMenu\(", line):
                    continue
                if "style_as_dropdown" in line or styles_its_menus:
                    continue
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        assert not offenders, (
            "These menus are never styled and will render as a plain "
            "#0e0f12 box. Wrap them in style_as_dropdown():\n  "
            + "\n  ".join(offenders)
        )

    def test_the_stylesheet_selector_still_matches_the_name(self):
        """If the QSS selector is renamed, the helper must follow it.

        These are two halves of one contract in two files; nothing else
        connects them, so a rename on either side silently unstyles every menu.
        """
        from gamepad_midi_bridge.ui.primitives.dropdown import DROPDOWN_OBJECT_NAME

        qss = (UI_DIR / "styles.qss").read_text()
        assert f"QMenu#{DROPDOWN_OBJECT_NAME}" in qss
        assert f"QMenu#{DROPDOWN_OBJECT_NAME} {{" in qss

    def test_the_styled_rule_sets_an_opaque_background(self):
        """A matching selector with a transparent fill would fix nothing."""
        qss = (UI_DIR / "styles.qss").read_text()
        block = qss.split("QMenu#UIDropdownMenu {", 1)[1].split("}", 1)[0]
        match = re.search(r"background-color:\s*(\S+?);", block)
        assert match, "the dropdown rule must set a background-color"
        colour = match.group(1).lower()
        assert colour not in {"transparent", "none"}
        # Reject rgba()/hex forms that carry a non-opaque alpha channel.
        assert not re.match(r"rgba\([^)]*,\s*0?\.\d+\s*\)$", colour)
        assert not re.match(r"^#[0-9a-f]{8}$", colour) or colour.endswith("ff")


class TestHelperBehaviour:
    @pytest.fixture(autouse=True)
    def _app(self, qapp):
        return qapp

    def test_sets_the_name_the_qss_targets(self):
        from PySide6.QtWidgets import QMenu

        from gamepad_midi_bridge.ui.primitives.dropdown import (
            DROPDOWN_OBJECT_NAME,
            style_as_dropdown,
        )

        assert style_as_dropdown(QMenu()).objectName() == DROPDOWN_OBJECT_NAME

    def test_returns_the_menu_for_inline_use(self):
        from PySide6.QtWidgets import QMenu

        from gamepad_midi_bridge.ui.primitives.dropdown import style_as_dropdown

        menu = QMenu()
        assert style_as_dropdown(menu) is menu

    def test_separators_are_not_collapsed(self):
        from PySide6.QtWidgets import QMenu

        from gamepad_midi_bridge.ui.primitives.dropdown import style_as_dropdown

        assert style_as_dropdown(QMenu()).separatorsCollapsible() is False

    def test_the_primitive_and_the_helper_agree(self):
        """UIDropdownMenu must not configure itself a second, different way."""
        from gamepad_midi_bridge.ui.primitives.dropdown import (
            DROPDOWN_OBJECT_NAME,
            UIDropdownMenu,
        )

        menu = UIDropdownMenu().menu
        assert menu.objectName() == DROPDOWN_OBJECT_NAME
        assert menu.separatorsCollapsible() is False
