"""Test suite for mapping_conflict_scanner module."""

import pytest
from gamepad_midi_bridge.mapping_conflict_scanner import (
    Conflict,
    scan,
    scan_notes_only,
    scan_ccs_only,
    count_by_kind,
    format_report,
)


class TestConflictDataclass:
    """Test Conflict dataclass."""

    def test_conflict_initialization(self):
        """Test basic Conflict creation."""
        conflict = Conflict(
            kind="note_collision",
            key="note 60 ch 1",
            paths=["buttons[0]", "buttons[1]"],
            severity="error"
        )
        assert conflict.kind == "note_collision"
        assert conflict.key == "note 60 ch 1"
        assert conflict.paths == ["buttons[0]", "buttons[1]"]
        assert conflict.severity == "error"

    def test_conflict_default_severity(self):
        """Default severity is 'warning'."""
        conflict = Conflict(
            kind="note_collision",
            key="note 60 ch 1",
            paths=["buttons[0]"]
        )
        assert conflict.severity == "warning"

    def test_conflict_to_dict(self):
        """Test to_dict serialization."""
        conflict = Conflict(
            kind="cc_collision",
            key="cc 1 ch 2",
            paths=["axes[0]", "axes[1]"],
            severity="error"
        )
        data = conflict.to_dict()
        assert data["kind"] == "cc_collision"
        assert data["key"] == "cc 1 ch 2"
        assert data["paths"] == ["axes[0]", "axes[1]"]
        assert data["severity"] == "error"

    def test_conflict_from_dict(self):
        """Test from_dict deserialization."""
        data = {
            "kind": "note_collision",
            "key": "note 72 ch 0",
            "paths": ["buttons[5]", "buttons[6]"],
            "severity": "warning"
        }
        conflict = Conflict.from_dict(data)
        assert conflict.kind == "note_collision"
        assert conflict.key == "note 72 ch 0"
        assert conflict.paths == ["buttons[5]", "buttons[6]"]
        assert conflict.severity == "warning"

    def test_conflict_round_trip(self):
        """Test serialization round-trip."""
        original = Conflict(
            kind="cc_collision",
            key="cc 5 ch 3",
            paths=["axes[2]", "l2_trigger"],
            severity="error"
        )
        data = original.to_dict()
        restored = Conflict.from_dict(data)
        assert restored.kind == original.kind
        assert restored.key == original.key
        assert restored.paths == original.paths
        assert restored.severity == original.severity


class TestScanEmpty:
    """Test scan on empty mappings."""

    def test_empty_mapping(self):
        """Empty mapping dict has no conflicts."""
        mapping = {}
        conflicts = scan(mapping)
        assert conflicts == []

    def test_mapping_with_no_buttons(self):
        """Mapping without buttons key has no conflicts."""
        mapping = {"midi_channel": 0}
        conflicts = scan(mapping)
        assert conflicts == []

    def test_mapping_with_empty_buttons(self):
        """Mapping with empty buttons dict has no conflicts."""
        mapping = {"buttons": {}, "midi_channel": 0}
        conflicts = scan(mapping)
        assert conflicts == []

    def test_mapping_with_empty_axes(self):
        """Mapping with empty axes dict has no conflicts."""
        mapping = {"axes": {}, "midi_channel": 0}
        conflicts = scan(mapping)
        assert conflicts == []


class TestNoteCollisions:
    """Test note collision detection."""

    def test_two_buttons_same_note_and_channel(self):
        """Two buttons with same note and channel → 1 collision."""
        mapping = {
            "buttons": {0: 60, 1: 60},
            "midi_channel": 1,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 1
        assert conflicts[0].kind == "note_collision"
        assert conflicts[0].key == "note 60 ch 1"
        assert set(conflicts[0].paths) == {"buttons[0]", "buttons[1]"}

    def test_two_buttons_same_note_different_channel(self):
        """Two buttons same note but different channels → no collision."""
        mapping = {
            "buttons": {0: 60, 1: 60},
            "button_channels": {0: 0, 1: 5},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 0

    def test_three_buttons_same_note(self):
        """Three buttons with same note → 1 collision with all 3 paths."""
        mapping = {
            "buttons": {0: 72, 3: 72, 7: 72},
            "midi_channel": 2,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 1
        assert conflicts[0].kind == "note_collision"
        assert conflicts[0].key == "note 72 ch 2"
        assert sorted(conflicts[0].paths) == ["buttons[0]", "buttons[3]", "buttons[7]"]

    def test_conflict_paths_sorted(self):
        """Conflict paths are sorted alphabetically."""
        mapping = {
            "buttons": {2: 65, 0: 65, 5: 65},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert conflicts[0].paths == ["buttons[0]", "buttons[2]", "buttons[5]"]

    def test_button_with_zero_note_ignored(self):
        """Button with note=0 is unmapped and ignored."""
        mapping = {
            "buttons": {0: 0, 1: 60},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 0

    def test_missing_buttons_key_doesnt_crash(self):
        """Missing 'buttons' key is handled defensively."""
        mapping = {"midi_channel": 0}
        conflicts = scan(mapping)
        assert conflicts == []

    def test_missing_button_channels_key(self):
        """Missing 'button_channels' defaults all buttons to global channel."""
        mapping = {
            "buttons": {0: 60, 1: 60},
            "midi_channel": 3,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 1
        assert conflicts[0].key == "note 60 ch 3"


class TestCCCollisions:
    """Test CC collision detection."""

    def test_two_axes_same_cc_and_channel(self):
        """Two axes with same CC and channel → 1 collision."""
        mapping = {
            "axes": {0: 1, 1: 1},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 1
        assert conflicts[0].kind == "cc_collision"
        assert conflicts[0].key == "cc 1 ch 0"
        assert set(conflicts[0].paths) == {"axes[0]", "axes[1]"}

    def test_two_axes_same_cc_different_channel(self):
        """Two axes same CC but different channels → no collision."""
        mapping = {
            "axes": {0: 5, 1: 5},
            "axis_channels": {0: 0, 1: 7},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 0

    def test_axis_and_trigger_same_cc(self):
        """An axis and a trigger (L2) with same CC → 1 collision."""
        mapping = {
            "axes": {0: 10, 4: 10},  # axis 0 and L2 (axis 4) both CC 10
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        cc_collisions = [c for c in conflicts if c.kind == "cc_collision"]
        assert len(cc_collisions) == 1
        assert cc_collisions[0].key == "cc 10 ch 0"
        assert "axes[0]" in cc_collisions[0].paths

    def test_multiple_cc_collisions(self):
        """Mapping with multiple separate CC collisions."""
        mapping = {
            "axes": {0: 10, 1: 10, 2: 20, 3: 20},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 2
        cc_keys = {c.key for c in conflicts}
        assert "cc 10 ch 0" in cc_keys
        assert "cc 20 ch 0" in cc_keys

    def test_axis_with_zero_cc_ignored(self):
        """Axis with CC=0 is unmapped and ignored."""
        mapping = {
            "axes": {0: 0, 1: 5},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 0

    def test_missing_axes_key_doesnt_crash(self):
        """Missing 'axes' key is handled defensively."""
        mapping = {"midi_channel": 0}
        conflicts = scan(mapping)
        assert conflicts == []


class TestTriggerCollisions:
    """Test trigger-specific collision detection."""

    def test_l2_trigger_alone_no_collision(self):
        """L2 trigger alone (no conflicting axis) → no collision."""
        mapping = {
            "axes": {0: 1, 1: 2, 2: 3, 3: 4, 4: 10, 5: 11},
            "l2_trigger": {"cc": 12},  # L2 trigger uses different CC than axis[4]
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        # L2 trigger uses CC 12, axes[4] uses CC 10 — no collision
        assert len(conflicts) == 0

    def test_l2_r2_both_same_axis_cc_no_collision(self):
        """L2 and R2 with their own axes (4, 5) don't collide."""
        mapping = {
            "axes": {4: 10, 5: 11},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 0

    def test_trigger_and_axis_same_cc_channel(self):
        """Trigger (L2) and axis share same CC and channel → collision."""
        mapping = {
            "axes": {0: 10, 4: 10},  # Both axis 0 and L2 (axis 4) on CC 10
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        cc_collisions = [c for c in conflicts if c.kind == "cc_collision"]
        assert len(cc_collisions) >= 1

    def test_missing_trigger_config_doesnt_crash(self):
        """Missing 'l2_trigger' key is handled defensively."""
        mapping = {
            "axes": {0: 1, 4: 10},
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        # Should still scan axes fine
        assert all(c.kind in ["note_collision", "cc_collision"] for c in conflicts)


class TestScanNotesOnly:
    """Test scan_notes_only filtering."""

    def test_notes_only_returns_note_collisions(self):
        """scan_notes_only includes note_collision only."""
        mapping = {
            "buttons": {0: 60, 1: 60},
            "axes": {0: 1, 1: 1},
            "midi_channel": 0,
        }
        conflicts = scan_notes_only(mapping)
        assert len(conflicts) >= 1
        assert all(c.kind == "note_collision" for c in conflicts)

    def test_notes_only_excludes_cc_collisions(self):
        """scan_notes_only does not return cc_collision."""
        mapping = {
            "buttons": {0: 60, 1: 60},  # note collision
            "axes": {0: 5, 1: 5},        # cc collision
            "midi_channel": 0,
        }
        conflicts = scan_notes_only(mapping)
        kinds = {c.kind for c in conflicts}
        assert "note_collision" in kinds
        assert "cc_collision" not in kinds


class TestScanCcsOnly:
    """Test scan_ccs_only filtering."""

    def test_ccs_only_returns_cc_collisions(self):
        """scan_ccs_only includes cc_collision only."""
        mapping = {
            "axes": {0: 5, 1: 5},
            "midi_channel": 0,
        }
        conflicts = scan_ccs_only(mapping)
        assert len(conflicts) >= 1
        assert all(c.kind == "cc_collision" for c in conflicts)

    def test_ccs_only_excludes_note_collisions(self):
        """scan_ccs_only does not return note_collision."""
        mapping = {
            "buttons": {0: 60, 1: 60},  # note collision
            "axes": {0: 5, 1: 5},        # cc collision
            "midi_channel": 0,
        }
        conflicts = scan_ccs_only(mapping)
        kinds = {c.kind for c in conflicts}
        assert "cc_collision" in kinds
        assert "note_collision" not in kinds


class TestCountByKind:
    """Test count_by_kind utility."""

    def test_empty_list(self):
        """Empty conflicts list returns empty count dict."""
        counts = count_by_kind([])
        assert counts == {}

    def test_single_conflict(self):
        """Single conflict counts correctly."""
        conflicts = [
            Conflict(kind="note_collision", key="note 60 ch 0", paths=["buttons[0]", "buttons[1]"])
        ]
        counts = count_by_kind(conflicts)
        assert counts == {"note_collision": 1}

    def test_multiple_same_kind(self):
        """Multiple conflicts of same kind count correctly."""
        conflicts = [
            Conflict(kind="note_collision", key="note 60 ch 0", paths=["buttons[0]", "buttons[1]"]),
            Conflict(kind="note_collision", key="note 72 ch 1", paths=["buttons[5]", "buttons[6]"]),
        ]
        counts = count_by_kind(conflicts)
        assert counts == {"note_collision": 2}

    def test_multiple_kinds(self):
        """Multiple kinds count separately."""
        conflicts = [
            Conflict(kind="note_collision", key="note 60 ch 0", paths=["buttons[0]", "buttons[1]"]),
            Conflict(kind="cc_collision", key="cc 5 ch 0", paths=["axes[0]", "axes[1]"]),
            Conflict(kind="cc_collision", key="cc 10 ch 1", paths=["axes[2]", "axes[3]"]),
        ]
        counts = count_by_kind(conflicts)
        assert counts == {"note_collision": 1, "cc_collision": 2}


class TestFormatReport:
    """Test format_report output."""

    def test_empty_conflicts_returns_empty_string(self):
        """No conflicts → empty string."""
        report = format_report([])
        assert report == ""

    def test_single_conflict(self):
        """Single conflict formatted correctly."""
        conflicts = [
            Conflict(
                kind="note_collision",
                key="note 60 ch 0",
                paths=["buttons[0]", "buttons[1]"],
                severity="error"
            )
        ]
        report = format_report(conflicts)
        assert "Mapping Conflicts:" in report
        assert "note 60 ch 0" in report
        assert "buttons[0]" in report
        assert "buttons[1]" in report
        assert "ERROR" in report

    def test_multiple_conflicts_all_included(self):
        """All conflicts appear in report."""
        conflicts = [
            Conflict(kind="note_collision", key="note 60 ch 0", paths=["buttons[0]", "buttons[1]"], severity="error"),
            Conflict(kind="cc_collision", key="cc 5 ch 1", paths=["axes[0]", "axes[1]"], severity="error"),
        ]
        report = format_report(conflicts)
        assert "note_collision" in report
        assert "cc_collision" in report
        assert "note 60 ch 0" in report
        assert "cc 5 ch 1" in report

    def test_report_is_multiline(self):
        """Report is multiline."""
        conflicts = [
            Conflict(kind="note_collision", key="note 60 ch 0", paths=["buttons[0]", "buttons[1]"], severity="error"),
        ]
        report = format_report(conflicts)
        lines = report.split("\n")
        assert len(lines) >= 2

    def test_report_sorted_by_kind_then_key(self):
        """Conflicts sorted by kind then key."""
        conflicts = [
            Conflict(kind="cc_collision", key="cc 20 ch 0", paths=["axes[3]"], severity="error"),
            Conflict(kind="note_collision", key="note 60 ch 0", paths=["buttons[0]"], severity="error"),
            Conflict(kind="cc_collision", key="cc 10 ch 0", paths=["axes[2]"], severity="error"),
        ]
        report = format_report(conflicts)
        # cc_collision should come before note_collision (alphabetically)
        # and cc 10 should come before cc 20
        assert report.index("cc 10") < report.index("note 60")


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_complex_mapping_with_mixed_conflicts(self):
        """Complex mapping with both note and CC collisions."""
        mapping = {
            "buttons": {
                0: 60, 1: 60,      # note collision
                2: 64, 3: 65,
                4: 67, 5: 69,
                6: 71, 7: 72,
                8: 74, 9: 76,
                10: 77,
            },
            "axes": {
                0: 1, 1: 1,        # cc collision
                2: 5, 3: 6,
                4: 10, 5: 11,
            },
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        assert len(conflicts) == 2
        kinds = {c.kind for c in conflicts}
        assert "note_collision" in kinds
        assert "cc_collision" in kinds

    def test_full_workflow_scan_count_report(self):
        """Full workflow: scan → count → format."""
        mapping = {
            "buttons": {0: 60, 1: 60, 2: 60},  # 1 note collision with 3 paths
            "axes": {0: 5, 1: 5},              # 1 cc collision with 2 paths
            "midi_channel": 0,
        }
        conflicts = scan(mapping)
        counts = count_by_kind(conflicts)
        report = format_report(conflicts)

        assert len(conflicts) == 2
        assert counts["note_collision"] == 1
        assert counts["cc_collision"] == 1
        assert "buttons[0]" in report
        assert "axes[0]" in report
