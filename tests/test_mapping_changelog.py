"""Tests for MappingChangelog — append-only history with undo/redo."""
from __future__ import annotations

import copy
import time

import pytest

from gamepad_midi_bridge.mapping_changelog import (
    MappingChangelog,
    MutationEntry,
    ChangelogConfig,
)


class TestMutationEntry:
    """MutationEntry dataclass and round-trip serialization."""

    def test_mutation_entry_creation(self):
        """Basic construction of MutationEntry."""
        entry = MutationEntry(
            timestamp_s=123.45,
            path="buttons.0.note",
            old_value=60,
            new_value=64,
            description="changed middle C",
        )
        assert entry.timestamp_s == 123.45
        assert entry.path == "buttons.0.note"
        assert entry.old_value == 60
        assert entry.new_value == 64
        assert entry.description == "changed middle C"

    def test_mutation_entry_default_description(self):
        """Description defaults to empty string."""
        entry = MutationEntry(
            timestamp_s=123.45,
            path="buttons.0.note",
            old_value=60,
            new_value=64,
        )
        assert entry.description == ""

    def test_mutation_entry_to_dict(self):
        """to_dict() produces a JSON-serializable dict."""
        entry = MutationEntry(
            timestamp_s=123.45,
            path="buttons.0.note",
            old_value=60,
            new_value=64,
            description="test",
        )
        d = entry.to_dict()
        assert d["timestamp_s"] == 123.45
        assert d["path"] == "buttons.0.note"
        assert d["old_value"] == 60
        assert d["new_value"] == 64
        assert d["description"] == "test"

    def test_mutation_entry_from_dict(self):
        """from_dict() reconstructs from a dict."""
        d = {
            "timestamp_s": 123.45,
            "path": "buttons.0.note",
            "old_value": 60,
            "new_value": 64,
            "description": "test",
        }
        entry = MutationEntry.from_dict(d)
        assert entry.timestamp_s == 123.45
        assert entry.path == "buttons.0.note"
        assert entry.old_value == 60
        assert entry.new_value == 64
        assert entry.description == "test"

    def test_mutation_entry_round_trip(self):
        """to_dict() and from_dict() are inverses."""
        original = MutationEntry(
            timestamp_s=999.999,
            path="complex.nested.path",
            old_value={"a": [1, 2, 3]},
            new_value={"b": [4, 5, 6]},
            description="complex",
        )
        d = original.to_dict()
        reconstructed = MutationEntry.from_dict(d)
        assert reconstructed.timestamp_s == original.timestamp_s
        assert reconstructed.path == original.path
        assert reconstructed.old_value == original.old_value
        assert reconstructed.new_value == original.new_value
        assert reconstructed.description == original.description


class TestChangelogConfig:
    """ChangelogConfig dataclass and clamping."""

    def test_config_defaults(self):
        """Default config has max_entries=200."""
        cfg = ChangelogConfig()
        assert cfg.max_entries == 200

    def test_config_custom_max_entries(self):
        """Can set custom max_entries."""
        cfg = ChangelogConfig(max_entries=500)
        assert cfg.max_entries == 500

    def test_config_clamps_too_small(self):
        """max_entries < 10 is clamped to 10."""
        cfg = ChangelogConfig(max_entries=5)
        assert cfg.max_entries == 10

    def test_config_clamps_too_large(self):
        """max_entries > 100000 is clamped to 100000."""
        cfg = ChangelogConfig(max_entries=999999)
        assert cfg.max_entries == 100000

    def test_config_to_dict(self):
        """to_dict() serializes config."""
        cfg = ChangelogConfig(max_entries=300)
        d = cfg.to_dict()
        assert d["max_entries"] == 300

    def test_config_from_dict(self):
        """from_dict() reconstructs config."""
        d = {"max_entries": 300}
        cfg = ChangelogConfig.from_dict(d)
        assert cfg.max_entries == 300

    def test_config_round_trip(self):
        """to_dict() and from_dict() are inverses."""
        original = ChangelogConfig(max_entries=250)
        d = original.to_dict()
        reconstructed = ChangelogConfig.from_dict(d)
        assert reconstructed.max_entries == original.max_entries


class TestChangelogEmpty:
    """Changelog in empty state."""

    def test_empty_changelog_cannot_undo(self):
        """can_undo() is False when empty."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        assert changelog.can_undo() is False

    def test_empty_changelog_cannot_redo(self):
        """can_redo() is False when empty."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        assert changelog.can_redo() is False

    def test_empty_changelog_undo_returns_none(self):
        """undo() returns None when empty."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        assert changelog.undo() is None

    def test_empty_changelog_redo_returns_none(self):
        """redo() returns None when empty."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        assert changelog.redo() is None

    def test_empty_changelog_entries(self):
        """entries() returns empty list."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        assert changelog.entries() == []

    def test_empty_changelog_recent(self):
        """recent() returns empty list."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        assert changelog.recent(5) == []

    def test_empty_changelog_summary(self):
        """summary() shows zeros for empty."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        summary = changelog.summary()
        assert summary["total"] == 0
        assert summary["undone"] == 0
        assert summary["can_undo"] == 0
        assert summary["can_redo"] == 0


class TestChangelogRecording:
    """Recording mutations."""

    def test_record_single_entry(self):
        """record() appends one entry."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        entry = changelog.record("buttons.0.note", 60, 64, now)
        assert entry.path == "buttons.0.note"
        assert entry.old_value == 60
        assert entry.new_value == 64
        assert changelog.entries() == [entry]

    def test_record_returns_mutation_entry(self):
        """record() returns the MutationEntry it creates."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        returned = changelog.record("test", None, 42, now)
        assert isinstance(returned, MutationEntry)
        assert returned.new_value == 42

    def test_record_multiple_entries(self):
        """record() appends multiple entries in order."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("buttons.0.note", 60, 64, now)
        e2 = changelog.record("buttons.1.note", 65, 67, now + 1)
        entries = changelog.entries()
        assert len(entries) == 2
        assert entries[0] == e1
        assert entries[1] == e2

    def test_record_with_description(self):
        """record() preserves description."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        entry = changelog.record(
            "buttons.0.note",
            60,
            64,
            now,
            description="changed middle C to E",
        )
        assert entry.description == "changed middle C to E"

    def test_record_deep_copies_values(self):
        """record() deep-copies old and new values."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        old_dict = {"a": 1}
        new_dict = {"b": 2}
        changelog.record("test", old_dict, new_dict, now)
        # Mutate originals
        old_dict["a"] = 999
        new_dict["b"] = 999
        # Check that stored values are unchanged
        entries = changelog.entries()
        assert entries[0].old_value == {"a": 1}
        assert entries[0].new_value == {"b": 2}

    def test_record_updates_undo_pointer(self):
        """record() sets _undo_pointer to len(_entries)."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test.1", 1, 2, now)
        assert changelog.can_undo() is True
        assert changelog.can_redo() is False


class TestChangelogUndoRedo:
    """Undo and redo operations."""

    def test_undo_returns_last_entry(self):
        """undo() returns the last recorded entry."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("buttons.0.note", 60, 64, now)
        e2 = changelog.record("buttons.1.note", 65, 67, now + 1)
        undone = changelog.undo()
        assert undone == e2

    def test_undo_decrements_pointer(self):
        """undo() decrements _undo_pointer."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("buttons.0.note", 60, 64, now)
        changelog.record("buttons.1.note", 65, 67, now + 1)
        assert changelog.can_undo() is True
        assert changelog.can_redo() is False
        changelog.undo()
        assert changelog.can_undo() is True
        assert changelog.can_redo() is True

    def test_undo_multiple_times(self):
        """undo() can be called multiple times."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("test.1", 1, 2, now)
        e2 = changelog.record("test.2", 2, 3, now + 1)
        e3 = changelog.record("test.3", 3, 4, now + 2)
        undone_3 = changelog.undo()
        undone_2 = changelog.undo()
        undone_1 = changelog.undo()
        assert undone_3 == e3
        assert undone_2 == e2
        assert undone_1 == e1
        assert changelog.can_undo() is False

    def test_redo_returns_next_entry(self):
        """redo() returns the next entry to re-apply."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("buttons.0.note", 60, 64, now)
        e2 = changelog.record("buttons.1.note", 65, 67, now + 1)
        changelog.undo()
        changelog.undo()
        redone_1 = changelog.redo()
        assert redone_1 == e1

    def test_redo_increments_pointer(self):
        """redo() increments _undo_pointer."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test.1", 1, 2, now)
        changelog.undo()
        assert changelog.can_redo() is True
        changelog.redo()
        assert changelog.can_redo() is False

    def test_undo_redo_cycle(self):
        """Undo and redo cycle works correctly."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("test.1", 1, 2, now)
        changelog.undo()
        assert changelog.can_undo() is False
        assert changelog.can_redo() is True
        changelog.redo()
        assert changelog.can_undo() is True
        assert changelog.can_redo() is False


class TestChangelogApplyMutations:
    """apply_undo and apply_redo on mapping dicts."""

    def test_apply_undo_simple_dict(self):
        """apply_undo() reverses a simple dict value."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        mapping = {"buttons": {"note": 64}}
        changelog.record("buttons.note", 64, 72, now)
        result = changelog.apply_undo(mapping)
        assert result["buttons"]["note"] == 64
        # Original unchanged
        assert mapping["buttons"]["note"] == 64

    def test_apply_undo_returns_new_dict(self):
        """apply_undo() returns a new dict, not mutated original."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        mapping = {"a": 1}
        changelog.record("a", 1, 2, now)
        result = changelog.apply_undo(mapping)
        assert result is not mapping
        assert result["a"] == 1
        assert mapping["a"] == 1

    def test_apply_undo_nested_path(self):
        """apply_undo() handles nested dotted paths."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        mapping = {"buttons": [{"note": 72}]}
        changelog.record("buttons.0.note", 72, 64, now)
        result = changelog.apply_undo(mapping)
        assert result["buttons"][0]["note"] == 72

    def test_apply_undo_when_cannot_undo(self):
        """apply_undo() returns copy when can_undo is False."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        mapping = {"a": 1}
        result = changelog.apply_undo(mapping)
        assert result == mapping
        assert result is not mapping

    def test_apply_redo_simple_dict(self):
        """apply_redo() re-applies a simple dict value."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        mapping = {"buttons": {"note": 64}}
        changelog.record("buttons.note", 64, 72, now)
        changelog.undo()
        result = changelog.apply_redo(mapping)
        assert result["buttons"]["note"] == 72

    def test_apply_redo_returns_new_dict(self):
        """apply_redo() returns a new dict."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        mapping = {"a": 1}
        changelog.record("a", 1, 2, now)
        changelog.undo()
        result = changelog.apply_redo(mapping)
        assert result is not mapping
        assert result["a"] == 2

    def test_apply_redo_when_cannot_redo(self):
        """apply_redo() returns copy when can_redo is False."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        mapping = {"a": 1}
        result = changelog.apply_redo(mapping)
        assert result == mapping
        assert result is not mapping


class TestChangelogMaxEntries:
    """FIFO eviction when max_entries is exceeded."""

    def test_fifo_eviction_on_record(self):
        """record() enforces max_entries by evicting oldest entry."""
        cfg = ChangelogConfig(max_entries=13)  # Clamped to 13
        changelog = MappingChangelog(cfg)
        now = time.time()
        # Record 13 entries, then one more => first should be evicted
        for i in range(13):
            changelog.record(f"test.{i}", i, i + 1, now + i)
        assert len(changelog.entries()) == 13
        # Now add one more; first entry should be evicted
        changelog.record("test.13", 13, 14, now + 13)
        entries = changelog.entries()
        assert len(entries) == 13
        assert entries[0].path == "test.1"
        assert entries[-1].path == "test.13"

    def test_fifo_eviction_adjusts_undo_pointer(self):
        """FIFO eviction adjusts _undo_pointer correctly when at capacity."""
        cfg = ChangelogConfig(max_entries=10)  # Clamped to 10
        changelog = MappingChangelog(cfg)
        now = time.time()
        for i in range(10):
            changelog.record(f"test.{i}", i, i + 1, now + i)
        # pointer is 10, len is 10
        old_pointer = changelog._undo_pointer
        changelog.record("test.10", 10, 11, now + 10)
        # one entry evicted, pointer should be decremented
        assert changelog._undo_pointer == old_pointer
        assert len(changelog.entries()) == 10


class TestChangelogUndoThenRecord:
    """Recording after undo truncates future entries."""

    def test_record_after_undo_truncates_redo_entries(self):
        """record() after undo() deletes entries after undo_pointer."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("test.1", 1, 2, now)
        e2 = changelog.record("test.2", 2, 3, now + 1)
        e3 = changelog.record("test.3", 3, 4, now + 2)
        changelog.undo()
        changelog.undo()
        # pointer is now 1, redo entries are e2 and e3
        e2_new = changelog.record("test.2.alt", 2, 5, now + 1.5, description="alternative")
        entries = changelog.entries()
        assert len(entries) == 2
        assert entries[0] == e1
        assert entries[1] == e2_new
        assert changelog.can_redo() is False


class TestChangelogClear:
    """clear() resets everything."""

    def test_clear_empties_entries(self):
        """clear() empties all entries."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test", 1, 2, now)
        changelog.clear()
        assert changelog.entries() == []

    def test_clear_resets_pointer(self):
        """clear() resets _undo_pointer to 0."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test", 1, 2, now)
        changelog.undo()
        changelog.clear()
        assert changelog.can_undo() is False
        assert changelog.can_redo() is False


class TestChangelogSummary:
    """summary() returns diagnostic info."""

    def test_summary_empty(self):
        """summary() for empty changelog."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        summary = changelog.summary()
        assert summary["total"] == 0
        assert summary["undone"] == 0
        assert summary["can_undo"] == 0
        assert summary["can_redo"] == 0

    def test_summary_with_entries(self):
        """summary() with recorded entries."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test.1", 1, 2, now)
        changelog.record("test.2", 2, 3, now + 1)
        summary = changelog.summary()
        assert summary["total"] == 2
        assert summary["undone"] == 0
        assert summary["can_undo"] == 1
        assert summary["can_redo"] == 0

    def test_summary_after_undo(self):
        """summary() reflects undo state."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test.1", 1, 2, now)
        changelog.record("test.2", 2, 3, now + 1)
        changelog.undo()
        summary = changelog.summary()
        assert summary["total"] == 2
        assert summary["undone"] == 1
        assert summary["can_undo"] == 1
        assert summary["can_redo"] == 1

    def test_summary_booleans_are_01(self):
        """summary() returns 0/1 for booleans, not True/False."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test", 1, 2, now)
        summary = changelog.summary()
        assert isinstance(summary["can_undo"], int)
        assert isinstance(summary["can_redo"], int)
        assert summary["can_undo"] == 1
        assert summary["can_redo"] == 0


class TestChangelogRecent:
    """recent(n) returns last n entries."""

    def test_recent_less_than_total(self):
        """recent(n) returns last n when n < total."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("test.1", 1, 2, now)
        e2 = changelog.record("test.2", 2, 3, now + 1)
        e3 = changelog.record("test.3", 3, 4, now + 2)
        recent = changelog.recent(2)
        assert recent == [e2, e3]

    def test_recent_more_than_total(self):
        """recent(n) returns all when n > total."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        e1 = changelog.record("test.1", 1, 2, now)
        e2 = changelog.record("test.2", 2, 3, now + 1)
        recent = changelog.recent(10)
        assert recent == [e1, e2]

    def test_recent_returns_copy(self):
        """recent() returns a deep copy, not references."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("test", {"a": 1}, {"b": 2}, now)
        recent = changelog.recent(1)
        recent[0].path = "modified"
        entries = changelog.entries()
        assert entries[0].path == "test"


class TestChangelogIntegration:
    """End-to-end workflows."""

    def test_typical_undo_redo_workflow(self):
        """Typical user workflow: record, undo, redo."""
        cfg = ChangelogConfig(max_entries=100)
        changelog = MappingChangelog(cfg)
        now = time.time()
        # Record two changes
        changelog.record("buttons.0.note", 60, 64, now)
        changelog.record("buttons.1.note", 65, 67, now + 1)
        assert changelog.can_undo() is True
        # Undo last change
        last = changelog.undo()
        assert last.path == "buttons.1.note"
        assert changelog.can_undo() is True
        assert changelog.can_redo() is True
        # Redo
        redone = changelog.redo()
        assert redone.path == "buttons.1.note"
        assert changelog.can_undo() is True
        assert changelog.can_redo() is False

    def test_command_line_verify(self):
        """Verify the example from the docstring works."""
        cfg = ChangelogConfig()
        changelog = MappingChangelog(cfg)
        now = time.time()
        changelog.record("buttons.0.note", 60, 64, now)
        changelog.record("buttons.1.note", 65, 67, now + 1)
        assert changelog.can_undo() is True
        entry = changelog.undo()
        assert entry.path == "buttons.1.note"
        assert changelog.can_redo() is True
