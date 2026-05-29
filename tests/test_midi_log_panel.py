"""Tests for the MIDI Activity Log Panel."""
import pytest
from PySide6.QtWidgets import QApplication

from gamepad_midi_bridge.ui.midi_log_panel import MidiLogPanel, MidiFilter


@pytest.fixture
def app():
    """Create a QApplication for widget tests."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    """Create a fresh MidiLogPanel for each test."""
    return MidiLogPanel()


def test_append_sent_adds_row(panel):
    """Test that append_sent adds a row to the list."""
    assert panel._list.count() == 0
    panel.append_sent(channel=0, status_label="NOTE-ON C4", data1=60, data2=100)
    assert panel._list.count() == 1
    assert "NOTE-ON C4" in panel._list.item(0).text()


def test_append_received_adds_row(panel):
    """Test that append_received adds a row with teal colour."""
    assert panel._list.count() == 0
    panel.append_received(channel=1, status_label="CC#1", data1=1, data2=87)
    assert panel._list.count() == 1
    assert "CC#1" in panel._list.item(0).text()
    assert "▼" in panel._list.item(0).text()


def test_append_sent_includes_channel_and_data(panel):
    """Test that sent rows include channel and data values."""
    panel.append_sent(channel=3, status_label="NOTE-ON", data1=72, data2=64, value_meta="C5")
    text = panel._list.item(0).text()
    assert "ch3" in text
    assert "d1= 72" in text
    assert "d2= 64" in text
    assert "(C5)" in text


def test_clear_all_empties_list(panel):
    """Test that clear button empties the list."""
    panel.append_sent(0, "NOTE-ON", 60, 100)
    panel.append_sent(0, "NOTE-OFF", 60, 0)
    assert panel._list.count() == 2
    panel._clear_all()
    assert panel._list.count() == 0
    assert len(panel._all_rows) == 0


def test_500_row_cap_drops_oldest(panel):
    """Test that rows beyond MAX_ROWS are dropped."""
    # Add MAX_ROWS + 10 rows
    for i in range(panel.MAX_ROWS + 10):
        panel.append_sent(0, f"NOTE-ON#{i:03d}", i % 128, i % 128)
    # Should only have MAX_ROWS rows stored
    assert len(panel._all_rows) == panel.MAX_ROWS
    assert panel._list.count() == panel.MAX_ROWS
    # First row should be #10 (first 10 dropped)
    assert "#010" in panel._list.item(0).text()


def test_filter_all_shows_all_rows(panel):
    """Test that ALL filter shows both sent and received."""
    panel.append_sent(0, "NOTE-ON", 60, 100)
    panel.append_received(0, "CC#1", 1, 87)
    panel.append_sent(1, "CC#2", 2, 50)
    # Change to ALL filter
    panel._filter_combo.setCurrentIndex(0)
    assert panel._filter_combo.currentData() == MidiFilter.ALL
    assert panel._list.count() == 3


def test_filter_sent_only(panel):
    """Test that SENT-only filter hides received rows."""
    panel.append_sent(0, "NOTE-ON", 60, 100)
    panel.append_received(0, "CC#1", 1, 87)
    panel.append_sent(1, "NOTE-OFF", 60, 0)
    # Find and select the SENT-only filter
    for i in range(panel._filter_combo.count()):
        if panel._filter_combo.itemData(i) == MidiFilter.SENT:
            panel._filter_combo.setCurrentIndex(i)
            break
    # Should only show the 2 sent rows
    assert panel._list.count() == 2
    for i in range(panel._list.count()):
        assert "▲" in panel._list.item(i).text()


def test_filter_received_only(panel):
    """Test that RECEIVED-only filter hides sent rows."""
    panel.append_sent(0, "NOTE-ON", 60, 100)
    panel.append_received(0, "CC#1", 1, 87)
    panel.append_received(1, "NOTE-ON", 61, 120)
    # Find and select the RECEIVED-only filter
    for i in range(panel._filter_combo.count()):
        if panel._filter_combo.itemData(i) == MidiFilter.RECEIVED:
            panel._filter_combo.setCurrentIndex(i)
            break
    # Should only show the 2 received rows
    assert panel._list.count() == 2
    for i in range(panel._list.count()):
        assert "▼" in panel._list.item(i).text()


def test_filter_change_rebuilds_list(panel):
    """Test that changing filter triggers a rebuild."""
    panel.append_sent(0, "NOTE-ON", 60, 100)
    panel.append_received(0, "CC#1", 1, 87)
    panel.append_sent(1, "NOTE-OFF", 60, 0)
    # Start with all
    assert panel._list.count() == 3
    # Switch to sent only
    for i in range(panel._filter_combo.count()):
        if panel._filter_combo.itemData(i) == MidiFilter.SENT:
            panel._filter_combo.setCurrentIndex(i)
            break
    # Should now show only 2 rows
    assert panel._list.count() == 2


def test_timestamp_in_row_text(panel):
    """Test that each row includes a timestamp."""
    panel.append_sent(0, "NOTE-ON", 60, 100)
    text = panel._list.item(0).text()
    # Should contain HH:MM:SS.mmm format (at least HH:MM:SS)
    assert ":" in text  # has colons for time
    parts = text.split()
    assert len(parts[0]) >= 8  # HH:MM:SS at minimum


def test_vertical_scrollbar_tracks_user_scroll(panel):
    """Test that _user_scrolled flag reflects manual scrolling."""
    # Add many rows to ensure scrollbar appears
    for i in range(30):
        panel.append_sent(0, f"NOTE#{i:02d}", i, i)
    # Initially, _user_scrolled should be False
    assert not panel._user_scrolled
    # Simulate user scrolling away from bottom by setting scrollbar value
    sb = panel._list.verticalScrollBar()
    sb.setValue(0)
    # _on_scroll_changed should be triggered, setting _user_scrolled
    assert panel._user_scrolled
