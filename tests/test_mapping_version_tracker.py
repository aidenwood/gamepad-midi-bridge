"""Tests for mapping version tracker."""

import time
from gamepad_midi_bridge.mapping_version_tracker import (
    MappingVersion,
    MappingVersionTracker,
    VersionTrackerConfig,
)


class TestMappingVersion:
    """Test MappingVersion dataclass."""

    def test_mapping_version_basic(self) -> None:
        """MappingVersion should store all fields."""
        mapping = {"a": 1, "b": 2}
        v = MappingVersion(
            id="v_abc123_001",
            timestamp_s=1000.0,
            mapping_snapshot=mapping,
            note="test version",
            parent_id="v_xyz789_000",
        )
        assert v.id == "v_abc123_001"
        assert v.timestamp_s == 1000.0
        assert v.mapping_snapshot == {"a": 1, "b": 2}
        assert v.note == "test version"
        assert v.parent_id == "v_xyz789_000"

    def test_mapping_version_default_note(self) -> None:
        """MappingVersion note should default to empty string."""
        v = MappingVersion(
            id="v_123",
            timestamp_s=0.0,
            mapping_snapshot={},
        )
        assert v.note == ""

    def test_mapping_version_default_parent_id(self) -> None:
        """MappingVersion parent_id should default to None."""
        v = MappingVersion(
            id="v_123",
            timestamp_s=0.0,
            mapping_snapshot={},
        )
        assert v.parent_id is None

    def test_mapping_version_to_dict(self) -> None:
        """MappingVersion.to_dict() should produce a plain dict."""
        v = MappingVersion(
            id="v_123",
            timestamp_s=1000.0,
            mapping_snapshot={"a": 1},
            note="test",
            parent_id="v_parent",
        )
        d = v.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "v_123"
        assert d["timestamp_s"] == 1000.0
        assert d["mapping_snapshot"] == {"a": 1}
        assert d["note"] == "test"
        assert d["parent_id"] == "v_parent"

    def test_mapping_version_from_dict(self) -> None:
        """MappingVersion.from_dict() should reconstruct."""
        d = {
            "id": "v_456",
            "timestamp_s": 2000.0,
            "mapping_snapshot": {"x": 10},
            "note": "restored",
            "parent_id": "v_parent",
        }
        v = MappingVersion.from_dict(d)
        assert v.id == "v_456"
        assert v.timestamp_s == 2000.0
        assert v.mapping_snapshot == {"x": 10}
        assert v.note == "restored"
        assert v.parent_id == "v_parent"

    def test_mapping_version_round_trip(self) -> None:
        """Round-trip to_dict -> from_dict should preserve data."""
        original = MappingVersion(
            id="v_789",
            timestamp_s=3000.0,
            mapping_snapshot={"p": 100, "q": 200},
            note="round trip test",
            parent_id="v_ancestor",
        )
        d = original.to_dict()
        restored = MappingVersion.from_dict(d)
        assert restored.id == original.id
        assert restored.timestamp_s == original.timestamp_s
        assert restored.mapping_snapshot == original.mapping_snapshot
        assert restored.note == original.note
        assert restored.parent_id == original.parent_id


class TestVersionTrackerConfig:
    """Test VersionTrackerConfig dataclass."""

    def test_config_default_values(self) -> None:
        """Config should have sensible defaults."""
        cfg = VersionTrackerConfig()
        assert cfg.max_versions == 50
        assert cfg.auto_prune_oldest is True

    def test_config_clamps_max_versions_low(self) -> None:
        """max_versions should be clamped to minimum 5."""
        cfg = VersionTrackerConfig(max_versions=2)
        assert cfg.max_versions == 5

    def test_config_clamps_max_versions_high(self) -> None:
        """max_versions should be clamped to maximum 10000."""
        cfg = VersionTrackerConfig(max_versions=50000)
        assert cfg.max_versions == 10000

    def test_config_allows_valid_max_versions(self) -> None:
        """Valid max_versions should not be changed."""
        cfg = VersionTrackerConfig(max_versions=100)
        assert cfg.max_versions == 100

    def test_config_to_dict(self) -> None:
        """Config.to_dict() should produce a plain dict."""
        cfg = VersionTrackerConfig(max_versions=75, auto_prune_oldest=False)
        d = cfg.to_dict()
        assert isinstance(d, dict)
        assert d["max_versions"] == 75
        assert d["auto_prune_oldest"] is False

    def test_config_from_dict(self) -> None:
        """Config.from_dict() should reconstruct."""
        d = {"max_versions": 100, "auto_prune_oldest": True}
        cfg = VersionTrackerConfig.from_dict(d)
        assert cfg.max_versions == 100
        assert cfg.auto_prune_oldest is True

    def test_config_round_trip(self) -> None:
        """Round-trip to_dict -> from_dict should preserve data."""
        original = VersionTrackerConfig(max_versions=75, auto_prune_oldest=False)
        d = original.to_dict()
        restored = VersionTrackerConfig.from_dict(d)
        assert restored.max_versions == original.max_versions
        assert restored.auto_prune_oldest == original.auto_prune_oldest


class TestMappingVersionTracker:
    """Test MappingVersionTracker core functionality."""

    def test_tracker_empty_on_init(self) -> None:
        """New tracker should be empty."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        assert tracker.current() is None
        assert tracker.version_count() == 0

    def test_tracker_commit_single(self) -> None:
        """Committing one version should set it as current."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        mapping = {"a": 1}
        v = tracker.commit(mapping, 1000.0, "first version")
        assert v.id is not None
        assert v.timestamp_s == 1000.0
        assert v.mapping_snapshot == {"a": 1}
        assert v.note == "first version"
        assert tracker.current() == v
        assert tracker.version_count() == 1

    def test_tracker_commit_deep_copies(self) -> None:
        """Commit should deep-copy the mapping, not reference it."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        mapping = {"nested": {"value": 42}}
        v = tracker.commit(mapping, 1000.0)
        # Modify original
        mapping["nested"]["value"] = 999
        # Snapshot should be unchanged
        assert v.mapping_snapshot["nested"]["value"] == 42

    def test_tracker_commit_sets_parent_id(self) -> None:
        """Second commit should have parent_id pointing to first."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        assert v1.parent_id is None
        assert v2.parent_id == v1.id

    def test_tracker_previous(self) -> None:
        """previous() should return the version before current."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        # Current is v2, previous should be v1
        assert tracker.previous() == v1

    def test_tracker_next_version(self) -> None:
        """next_version() should return the version after current."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        tracker.rollback()  # Move back to v1
        # Next after v1 should be v2
        assert tracker.next_version() == v2

    def test_tracker_rollback(self) -> None:
        """rollback() should move index back."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        # Current is v2, rollback should give v1
        rolled = tracker.rollback()
        assert rolled == v1
        assert tracker.current() == v1

    def test_tracker_rollback_at_start(self) -> None:
        """rollback() at start should return None."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        tracker.commit({"a": 1}, 1000.0)
        tracker.rollback()
        # Already at start, rollback again should return None
        result = tracker.rollback()
        assert result is None

    def test_tracker_forward(self) -> None:
        """forward() should move index forward."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        tracker.rollback()  # Back to v1
        # Forward should give v2
        moved = tracker.forward()
        assert moved == v2
        assert tracker.current() == v2

    def test_tracker_forward_at_end(self) -> None:
        """forward() at the end should return None."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        tracker.commit({"a": 1}, 1000.0)
        tracker.commit({"a": 2}, 2000.0)
        # Already at end, forward should return None
        result = tracker.forward()
        assert result is None

    def test_tracker_goto(self) -> None:
        """goto() should jump to a specific version by ID."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        v3 = tracker.commit({"a": 3}, 3000.0)
        # Jump back to v1
        result = tracker.goto(v1.id)
        assert result == v1
        assert tracker.current() == v1

    def test_tracker_goto_invalid_id(self) -> None:
        """goto() with invalid ID should return None and not change current."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        # Try to goto nonexistent ID
        result = tracker.goto("nonexistent")
        assert result is None
        assert tracker.current() == v2  # Current unchanged

    def test_tracker_find(self) -> None:
        """find() should locate a version without changing current."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        v3 = tracker.commit({"a": 3}, 3000.0)
        # Find v1, current should still be v3
        found = tracker.find(v1.id)
        assert found == v1
        assert tracker.current() == v3

    def test_tracker_find_not_found(self) -> None:
        """find() with invalid ID should return None."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        tracker.commit({"a": 1}, 1000.0)
        result = tracker.find("nonexistent")
        assert result is None

    def test_tracker_versions(self) -> None:
        """versions() should return a copy of all versions."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        versions = tracker.versions()
        assert len(versions) == 2
        assert versions[0].id == v1.id
        assert versions[1].id == v2.id

    def test_tracker_versions_is_deep_copy(self) -> None:
        """versions() should return a deep copy, not references."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        tracker.commit({"a": 1}, 1000.0)
        versions1 = tracker.versions()
        versions2 = tracker.versions()
        # Lists should be separate objects
        assert versions1 is not versions2
        # Dicts should be separate objects
        assert versions1[0] is not versions2[0]

    def test_tracker_version_count(self) -> None:
        """version_count() should return the number of versions."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        assert tracker.version_count() == 0
        tracker.commit({"a": 1}, 1000.0)
        assert tracker.version_count() == 1
        tracker.commit({"a": 2}, 2000.0)
        assert tracker.version_count() == 2

    def test_tracker_max_versions_auto_prune(self) -> None:
        """When exceeding max_versions with auto_prune, oldest should be removed."""
        cfg = VersionTrackerConfig(max_versions=5, auto_prune_oldest=True)
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1}, 1000.0)
        v2 = tracker.commit({"a": 2}, 2000.0)
        v3 = tracker.commit({"a": 3}, 3000.0)
        v4 = tracker.commit({"a": 4}, 4000.0)
        v5 = tracker.commit({"a": 5}, 5000.0)
        # Now at max (5)
        assert tracker.version_count() == 5
        # One more should trigger prune
        v6 = tracker.commit({"a": 6}, 6000.0)
        assert tracker.version_count() == 5
        # v1 should be gone
        assert tracker.find(v1.id) is None
        # v2-v6 should still exist
        assert tracker.find(v2.id) is not None
        assert tracker.find(v3.id) is not None
        assert tracker.find(v4.id) is not None
        assert tracker.find(v5.id) is not None
        assert tracker.find(v6.id) is not None

    def test_tracker_max_versions_no_auto_prune(self) -> None:
        """With auto_prune disabled, max_versions can be exceeded."""
        cfg = VersionTrackerConfig(max_versions=5, auto_prune_oldest=False)
        tracker = MappingVersionTracker(cfg)
        for i in range(10):
            tracker.commit({"a": i}, float(1000 + i * 1000))
        # All 10 should exist (max not enforced)
        assert tracker.version_count() == 10

    def test_tracker_diff_to(self) -> None:
        """diff_to() should return differences between versions."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"a": 1, "b": 2}, 1000.0)
        v2 = tracker.commit({"a": 10, "b": 2, "c": 3}, 2000.0)
        # Diff v2 against v1
        diffs = tracker.diff_to(v1.id)
        assert diffs is not None
        # Should have changes (a changed, c added)
        paths = [d[0] for d in diffs]
        assert "a" in paths  # a changed from 1 to 10
        # c is in v2 but not v1, so should be recorded

    def test_tracker_diff_to_unknown_version(self) -> None:
        """diff_to() with unknown version ID should return None."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        tracker.commit({"a": 1}, 1000.0)
        result = tracker.diff_to("nonexistent")
        assert result is None

    def test_tracker_clear(self) -> None:
        """clear() should remove all versions."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        tracker.commit({"a": 1}, 1000.0)
        tracker.commit({"a": 2}, 2000.0)
        assert tracker.version_count() == 2
        tracker.clear()
        assert tracker.version_count() == 0
        assert tracker.current() is None

    def test_tracker_complex_navigation_sequence(self) -> None:
        """Complex sequence of commits, rollbacks, and forwards."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"buttons": [60, 61, 62]}, 1000.0, "base mapping")
        v2 = tracker.commit({"buttons": [60, 61, 64]}, 2000.0, "adjust middle")
        v3 = tracker.commit({"buttons": [60, 61, 64], "axes": [0, 1]}, 3000.0, "add axes")

        # Navigate: v3 -> v1 -> v3 -> v2 -> v3
        assert tracker.current() == v3
        assert tracker.rollback() == v2
        assert tracker.rollback() == v1
        assert tracker.forward() == v2
        assert tracker.forward() == v3
        assert tracker.goto(v2.id) == v2
        assert tracker.next_version() == v3

    def test_tracker_version_snapshot_independence(self) -> None:
        """Each version snapshot should be independent."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        shared_mapping = {"state": {"value": 1}}
        v1 = tracker.commit(shared_mapping, 1000.0)
        v2 = tracker.commit(shared_mapping, 2000.0)
        # Change v1's snapshot
        v1.mapping_snapshot["state"]["value"] = 999
        # v2's snapshot should be unchanged
        assert v2.mapping_snapshot["state"]["value"] == 1


class TestMappingVersionTrackerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_tracker_empty_mapping(self) -> None:
        """Tracker should handle empty mapping dicts."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v = tracker.commit({}, 1000.0)
        assert v.mapping_snapshot == {}
        assert tracker.current() == v

    def test_tracker_deeply_nested_mapping(self) -> None:
        """Tracker should handle deeply nested structures."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        deep = {"a": {"b": {"c": {"d": {"e": 42}}}}}
        v = tracker.commit(deep, 1000.0)
        assert v.mapping_snapshot["a"]["b"]["c"]["d"]["e"] == 42

    def test_tracker_special_values(self) -> None:
        """Tracker should handle special values (None, 0, False, empty string)."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        mapping = {"none": None, "zero": 0, "false": False, "empty": ""}
        v = tracker.commit(mapping, 1000.0)
        assert v.mapping_snapshot["none"] is None
        assert v.mapping_snapshot["zero"] == 0
        assert v.mapping_snapshot["false"] is False
        assert v.mapping_snapshot["empty"] == ""

    def test_tracker_float_timestamp_precision(self) -> None:
        """Tracker should preserve float timestamp precision."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        ts = time.time()  # Get current time with precision
        v = tracker.commit({"a": 1}, ts)
        assert v.timestamp_s == ts

    def test_tracker_version_id_uniqueness(self) -> None:
        """Version IDs should be reasonably unique even for similar mappings."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v1 = tracker.commit({"value": 1}, 1000.0)
        v2 = tracker.commit({"value": 2}, 1000.1)  # Slightly different time
        # IDs should be different
        assert v1.id != v2.id

    def test_tracker_version_id_format(self) -> None:
        """Version ID should follow expected format: v_<hash>_<timestamp>."""
        cfg = VersionTrackerConfig()
        tracker = MappingVersionTracker(cfg)
        v = tracker.commit({"a": 1}, 1000.0)
        # Should start with 'v_' and have two underscore separators
        assert v.id.startswith("v_")
        parts = v.id.split("_")
        assert len(parts) == 3  # v, hash, timestamp
