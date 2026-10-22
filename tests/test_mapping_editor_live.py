"""Mapping tab: live input feedback, and MIDI cells that actually save.

Two defects from the 2026-10-22 first-use review:

1. The tables were a static list. Nothing showed which row was firing, so
   there was no way to tell which physical control owned which note while
   mapping — "I dont actually see what midi notes im pressing on the midi
   note page."

2. Column 1 was editable (the table has had AllEditTriggers since it was
   written) but no handler existed, so typing a new note number showed it
   in the cell and then silently discarded it on the next refresh while the
   controller kept sending the old one.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import Mapping


def _has_qapp() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


def _editor():
    from PySide6.QtWidgets import QApplication
    from gamepad_midi_bridge.ui.mapping_editor import MappingEditor
    QApplication.instance() or QApplication([])
    return MappingEditor(Mapping())


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestLiveColumn:

    def test_capture_tables_have_a_live_column(self):
        ed = _editor()
        for table in (ed._buttons_table, ed._axes_table, ed._hats_table):
            headers = [table.horizontalHeaderItem(c).text()
                       for c in range(table.columnCount())]
            assert "Live" in headers
            assert headers.index("Live") == 2

    def test_touchpad_table_has_no_live_column(self):
        """It has no capture_kind, so it is not an input table."""
        ed = _editor()
        headers = [ed._touchpad_table.horizontalHeaderItem(c).text()
                   for c in range(ed._touchpad_table.columnCount())]
        assert "Live" not in headers

    def test_row_lookups_cover_every_mapped_control(self):
        ed = _editor()
        m = Mapping()
        assert set(ed._row_for_control["buttons"]) == set(m.buttons)
        assert set(ed._row_for_control["axes"]) == set(m.axes)
        assert set(ed._row_for_control["hats"]) == set(m.hats)

    def test_pressing_a_button_lights_its_row(self):
        ed = _editor()
        idx = sorted(Mapping().buttons)[0]
        ed._on_live_button(idx, True)
        ed._flush_live()
        row = ed._row_for_control["buttons"][idx]
        assert ed._live[("buttons", row)]["lit"] is True

    def test_release_clears_the_row_after_the_hold_window(self):
        ed = _editor()
        idx = sorted(Mapping().buttons)[0]
        row = ed._row_for_control["buttons"][idx]
        ed._on_live_button(idx, True)
        ed._flush_live()
        ed._on_live_button(idx, False)
        # Backdate past _LIVE_HOLD_S rather than sleeping.
        ed._live[("buttons", row)]["hit"] -= 10.0
        ed._flush_live()
        assert ("buttons", row) not in ed._live

    def test_resting_stick_noise_does_not_light_an_axis(self):
        ed = _editor()
        axis = sorted(Mapping().axes)[0]
        ed._on_live_axis(axis, 0.01)
        ed._flush_live()
        row = ed._row_for_control["axes"][axis]
        assert ed._live.get(("axes", row), {}).get("lit") is not True

    def test_note_on_writes_the_real_velocity_byte(self):
        ed = _editor()
        idx, note = sorted(Mapping().buttons.items())[0]
        ed._on_live_midi("sent", 0, 0x90, note, 99, "")
        ed._flush_live()
        row = ed._row_for_control["buttons"][idx]
        assert ed._buttons_table.item(row, 2).text() == "v99"

    def test_received_messages_are_ignored(self):
        """Only what this app SENT belongs in the Live column."""
        ed = _editor()
        idx, note = sorted(Mapping().buttons.items())[0]
        ed._on_live_midi("received", 0, 0x90, note, 99, "")
        ed._flush_live()
        row = ed._row_for_control["buttons"][idx]
        assert ed._buttons_table.item(row, 2).text() == ""

    def test_hiding_the_tab_clears_every_highlight(self):
        ed = _editor()
        idx = sorted(Mapping().buttons)[0]
        ed._on_live_button(idx, True)
        ed._flush_live()
        ed._clear_live()
        assert ed._live == {}

    def test_unknown_control_index_is_dropped_not_raised(self):
        ed = _editor()
        ed._on_live_button(999, True)
        ed._on_live_axis(999, 1.0)
        ed._on_live_hat("sideways", True)
        ed._flush_live()
        assert ed._live == {}


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestEditingAMidiCell:

    def test_typing_a_new_note_persists_into_the_mapping(self):
        ed = _editor()
        idx = sorted(Mapping().buttons)[0]
        row = ed._row_for_control["buttons"][idx]
        ed._buttons_table.item(row, 1).setText("100")
        assert ed._mapping.buttons[idx] == 100

    def test_out_of_range_reverts_instead_of_writing(self):
        ed = _editor()
        idx = sorted(Mapping().buttons)[0]
        row = ed._row_for_control["buttons"][idx]
        before = ed._mapping.buttons[idx]
        ed._buttons_table.item(row, 1).setText("200")
        assert ed._mapping.buttons[idx] == before
        assert ed._buttons_table.item(row, 1).text() == str(before)

    def test_non_numeric_reverts_instead_of_writing(self):
        ed = _editor()
        idx = sorted(Mapping().buttons)[0]
        row = ed._row_for_control["buttons"][idx]
        before = ed._mapping.buttons[idx]
        ed._buttons_table.item(row, 1).setText("banana")
        assert ed._mapping.buttons[idx] == before

    def test_editing_a_cc_persists(self):
        ed = _editor()
        axis = sorted(Mapping().axes)[0]
        row = ed._row_for_control["axes"][axis]
        ed._axes_table.item(row, 1).setText("42")
        assert ed._mapping.axes[axis] == 42

    def test_editing_a_dpad_note_persists_under_its_string_key(self):
        ed = _editor()
        direction = list(Mapping().hats)[0]
        row = ed._row_for_control["hats"][direction]
        ed._hats_table.item(row, 1).setText("90")
        assert ed._mapping.hats[direction] == 90

    def test_refreshing_the_tables_does_not_rewrite_the_mapping(self):
        """_fill fires itemChanged for every cell; the guard must hold."""
        ed = _editor()
        before = dict(ed._mapping.buttons)
        ed._refresh_tables()
        assert ed._mapping.buttons == before

    def test_edit_keeps_the_midi_lookup_in_step(self):
        """Otherwise the live highlight lights whichever row owned the old
        number."""
        ed = _editor()
        idx = sorted(Mapping().buttons)[0]
        row = ed._row_for_control["buttons"][idx]
        ed._buttons_table.item(row, 1).setText("100")
        assert ed._row_for_midi["buttons"][100] == row
