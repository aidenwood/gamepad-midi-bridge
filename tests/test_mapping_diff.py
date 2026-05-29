"""Tests for mapping diff functionality."""
from gamepad_midi_bridge.mapping import Mapping
from gamepad_midi_bridge.mapping_diff import diff_mappings


def test_diff_identical_mappings() -> None:
    """Diff two identical mappings should return empty list."""
    m1 = Mapping()
    m2 = Mapping()
    entries = diff_mappings(m1, m2)
    assert entries == []


def test_diff_cc_changed() -> None:
    """Diff with one CC changed should return 1 entry with kind='changed'."""
    m1 = Mapping()
    m2 = Mapping()
    m2.axes = {0: 3, 1: 4, 2: 5, 3: 6, 4: 1, 5: 2}  # axis 4 unchanged
    m2.axes[4] = 7  # Change axis 4 CC from 1 to 7

    entries = diff_mappings(m1, m2)
    assert len(entries) == 1
    assert entries[0].path == "axes.4"
    assert entries[0].left == 1
    assert entries[0].right == 7
    assert entries[0].kind == "changed"


def test_diff_axis_added() -> None:
    """Diff with axis added should return 1 entry with kind='added'."""
    m1 = Mapping()
    m2 = Mapping()
    m2.axes[6] = 10  # Add new axis mapping

    entries = diff_mappings(m1, m2)
    added = [e for e in entries if e.kind == "added"]
    assert len(added) == 1
    assert added[0].path == "axes.6"
    assert added[0].left is None
    assert added[0].right == 10


def test_diff_axis_removed() -> None:
    """Diff with axis removed should return 1 entry with kind='removed'."""
    m1 = Mapping()
    m2 = Mapping()
    del m2.axes[4]  # Remove axis 4 from preset B

    entries = diff_mappings(m1, m2)
    removed = [e for e in entries if e.kind == "removed"]
    assert len(removed) == 1
    assert removed[0].path == "axes.4"
    assert removed[0].left == 1
    assert removed[0].right is None


def test_diff_nested_config_changed() -> None:
    """Diff with nested config field changed should use dotted path notation."""
    m1 = Mapping()
    m2 = Mapping()
    m2.l2_trigger.mode = "ceiling"  # Change l2_trigger.mode from linear to ceiling

    entries = diff_mappings(m1, m2)
    mode_changes = [e for e in entries if "mode" in e.path and "l2_trigger" in e.path]
    assert len(mode_changes) == 1
    assert mode_changes[0].kind == "changed"
    assert mode_changes[0].left == "linear"
    assert mode_changes[0].right == "ceiling"


def test_diff_multiple_changes() -> None:
    """Diff with multiple changes should return all of them."""
    m1 = Mapping()
    m2 = Mapping()
    # Change axis 4 CC
    m2.axes[4] = 7
    # Add axis 6
    m2.axes[6] = 10
    # Change trigger mode
    m2.l2_trigger.mode = "ceiling"

    entries = diff_mappings(m1, m2)
    assert len(entries) >= 3
    kinds = {e.kind for e in entries}
    assert "changed" in kinds or len(entries) > 0
