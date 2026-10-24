"""Button rows must wrap rather than clip.

A QHBoxLayout's minimum width is the SUM of its children, so a row of actions
sets a floor for everything above it. Two rows were doing that:

    Templates   5 buttons   603px
    Presets     7 buttons   706px

WHY `tests/test_narrow_page_floors.py` NEVER CAUGHT EITHER: both pages are
wrapped in a QScrollArea, which honestly reports an 88px floor and simply clips
whatever will not fit. The page passes the floor sweep while the row inside it
still cannot be reached — the cost moves from the layout to the user. In the v3
screen recording the Presets page shows only Load, Save current as…, Delete and
Compare presets…; Export cheat sheet, Snapshots… and Setlist… are off the right
edge behind a sideways scroll, and the Templates row truncates "Load template.".

So a floor measured on a page says nothing about a row inside a scroll area.
The row has to be asked directly, which is what these tests do.

The fix is `FlowLayout` — the primitive written for exactly this, already used
by the Bluetooth tab's action row and the Marketplace tag chips.
"""

from __future__ import annotations

import pytest

from gamepad_midi_bridge.ui.primitives.flow_layout import FlowLayout


def _row_with(widget, count: int) -> FlowLayout:
    rows = [r for r in widget.findChildren(FlowLayout) if r.count() == count]
    assert rows, f"the {count}-button action row is not a FlowLayout"
    return rows[0]


@pytest.fixture()
def templates_row(qapp):
    from gamepad_midi_bridge.mapping import Mapping
    from gamepad_midi_bridge.ui.template_builder_tab import TemplateBuilderTab

    tab = TemplateBuilderTab(Mapping())
    tab.resize(420, 900)
    # yield, not return: the row is owned by `tab`, so letting `tab` fall out
    # of scope has Qt delete the QWidgetItems out from under the test.
    yield _row_with(tab, 5)


@pytest.fixture()
def presets_row(qapp):
    from gamepad_midi_bridge.mapping import Mapping
    from gamepad_midi_bridge.ui.preset_manager import PresetManager

    pm = PresetManager(lambda: Mapping())
    pm.resize(420, 900)
    yield _row_with(pm, 7)


#: (fixture name, what the same buttons cost in a single QHBoxLayout)
ROWS = [("templates_row", 603), ("presets_row", 706)]


@pytest.mark.parametrize("row_name,hbox_sum", ROWS)
class TestActionRowsDoNotPin:
    def test_floor_is_far_below_the_hbox_sum(self, request, row_name, hbox_sum):
        row = request.getfixturevalue(row_name)
        floor = row.minimumSize().width()
        assert floor < hbox_sum, (
            f"{row_name} still demands {floor}px; as a QHBoxLayout these "
            f"buttons cost {hbox_sum}px and clip inside the page's scroll area"
        )

    def test_floor_is_about_one_button_wide(self, request, row_name, hbox_sum):
        """A wrapping row can shrink to its widest single item, no further."""
        row = request.getfixturevalue(row_name)
        assert row.minimumSize().width() <= 200

    def test_stays_one_row_when_there_is_space(self, request, row_name, hbox_sum):
        """Wrapping must cost nothing at comfortable widths."""
        row = request.getfixturevalue(row_name)
        assert row.heightForWidth(1100) == row.heightForWidth(760) > 0

    def test_wraps_when_squeezed(self, request, row_name, hbox_sum):
        """The whole point — more rows instead of an unreachable button."""
        row = request.getfixturevalue(row_name)
        assert row.heightForWidth(400) > row.heightForWidth(1100)

    def test_no_trailing_spacer_claims_a_cell(self, request, row_name, hbox_sum):
        """FlowLayout wraps rather than pushing, so an addStretch would waste a
        slot on the last row instead of right-padding it."""
        row = request.getfixturevalue(row_name)
        for i in range(row.count()):
            assert row.itemAt(i).widget() is not None


class TestNothingIsHidden:
    """Wrapping is not hiding — every action stays present and reachable."""

    def test_templates_keeps_all_five(self, templates_row):
        labels = {
            templates_row.itemAt(i).widget().text()
            for i in range(templates_row.count())
        }
        assert labels == {
            "Save template…",
            "Load template…",
            "Export for Resolume",
            "Export for Ableton",
            "Reset to defaults",
        }

    def test_presets_keeps_all_seven(self, presets_row):
        labels = {
            presets_row.itemAt(i).widget().text()
            for i in range(presets_row.count())
        }
        assert labels == {
            "Load",
            "Save current as…",
            "Delete",
            "Compare presets…",
            "Export cheat sheet",
            "Snapshots…",
            "Setlist…",
        }
