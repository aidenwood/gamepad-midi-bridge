"""Tests for MappingPinnedHistory."""

import pytest
from gamepad_midi_bridge.mapping_pinned_history import (
    HistoryEntry,
    PinnedHistoryConfig,
    MappingPinnedHistory,
)


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""

    def test_entry_defaults(self):
        """Entry creates with sensible defaults."""
        entry = HistoryEntry(preset_slug="lead", opened_at_s=100.0)
        assert entry.preset_slug == "lead"
        assert entry.opened_at_s == 100.0
        assert entry.pinned is False

    def test_entry_to_dict(self):
        """Entry.to_dict() serializes all fields."""
        entry = HistoryEntry(preset_slug="pad", opened_at_s=200.5, pinned=True)
        d = entry.to_dict()
        assert d["preset_slug"] == "pad"
        assert d["opened_at_s"] == 200.5
        assert d["pinned"] is True

    def test_entry_from_dict(self):
        """HistoryEntry.from_dict() deserializes correctly."""
        d = {
            "preset_slug": "synth",
            "opened_at_s": 150.0,
            "pinned": False,
        }
        entry = HistoryEntry.from_dict(d)
        assert entry.preset_slug == "synth"
        assert entry.opened_at_s == 150.0
        assert entry.pinned is False

    def test_entry_from_dict_missing_pinned(self):
        """HistoryEntry.from_dict() defaults pinned to False."""
        d = {
            "preset_slug": "bass",
            "opened_at_s": 250.0,
        }
        entry = HistoryEntry.from_dict(d)
        assert entry.preset_slug == "bass"
        assert entry.opened_at_s == 250.0
        assert entry.pinned is False


class TestPinnedHistoryConfig:
    """Tests for PinnedHistoryConfig dataclass."""

    def test_config_defaults(self):
        """Config uses sensible defaults."""
        cfg = PinnedHistoryConfig()
        assert cfg.max_recent == 20
        assert cfg.max_pinned == 10

    def test_config_clamp_max_recent_low(self):
        """Config clamps max_recent < 1 to 1."""
        cfg = PinnedHistoryConfig(max_recent=0)
        assert cfg.max_recent == 1

    def test_config_clamp_max_recent_high(self):
        """Config clamps max_recent > 1000 to 1000."""
        cfg = PinnedHistoryConfig(max_recent=2000)
        assert cfg.max_recent == 1000

    def test_config_clamp_max_pinned_low(self):
        """Config clamps max_pinned < 1 to 1."""
        cfg = PinnedHistoryConfig(max_pinned=0)
        assert cfg.max_pinned == 1

    def test_config_clamp_max_pinned_high(self):
        """Config clamps max_pinned > 100 to 100."""
        cfg = PinnedHistoryConfig(max_pinned=200)
        assert cfg.max_pinned == 100

    def test_config_to_dict(self):
        """Config.to_dict() serializes all fields."""
        cfg = PinnedHistoryConfig(max_recent=15, max_pinned=5)
        d = cfg.to_dict()
        assert d["max_recent"] == 15
        assert d["max_pinned"] == 5

    def test_config_from_dict(self):
        """PinnedHistoryConfig.from_dict() deserializes correctly."""
        d = {"max_recent": 25, "max_pinned": 8}
        cfg = PinnedHistoryConfig.from_dict(d)
        assert cfg.max_recent == 25
        assert cfg.max_pinned == 8

    def test_config_from_dict_missing_values(self):
        """PinnedHistoryConfig.from_dict() uses defaults for missing keys."""
        d = {}
        cfg = PinnedHistoryConfig.from_dict(d)
        assert cfg.max_recent == 20
        assert cfg.max_pinned == 10


class TestMappingPinnedHistory:
    """Tests for MappingPinnedHistory."""

    def test_empty_recent(self):
        """Empty history returns empty recent list."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        assert history.recent() == []

    def test_empty_pinned_list(self):
        """Empty history returns empty pinned list."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        assert history.pinned_list() == []

    def test_empty_combined_view(self):
        """Empty history returns empty combined view."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        assert history.combined_view() == []

    def test_record_open_adds_entry(self):
        """record_open creates a new entry."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        entry = history.record_open("lead", 100.0)
        assert entry.preset_slug == "lead"
        assert entry.opened_at_s == 100.0
        assert entry.pinned is False

    def test_record_open_same_slug_updates_timestamp(self):
        """record_open with same slug updates opened_at_s."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        entry = history.record_open("lead", 200.0)
        assert entry.preset_slug == "lead"
        assert entry.opened_at_s == 200.0

    def test_record_open_multiple(self):
        """record_open with different slugs creates multiple entries."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.record_open("bass", 120.0)
        assert history.recent_count() == 3

    def test_pin_sets_pinned_true(self):
        """pin sets pinned=True on existing entry."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        result = history.pin("lead")
        assert result is True
        entry = history.pinned_list()[0]
        assert entry.preset_slug == "lead"
        assert entry.pinned is True

    def test_pin_not_found_returns_false(self):
        """pin returns False if entry not found."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        result = history.pin("nonexistent")
        assert result is False

    def test_pin_already_pinned_returns_false(self):
        """pin returns False if already pinned."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.pin("lead")
        result = history.pin("lead")
        assert result is False

    def test_pin_max_pinned_cap_enforced(self):
        """pin enforces max_pinned cap."""
        cfg = PinnedHistoryConfig(max_pinned=2)
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.record_open("bass", 120.0)
        assert history.pin("lead") is True
        assert history.pin("pad") is True
        assert history.pin("bass") is False  # At max
        assert history.pin_count() == 2

    def test_unpin_clears_pinned(self):
        """unpin sets pinned=False."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.pin("lead")
        result = history.unpin("lead")
        assert result is True
        assert history.pin_count() == 0

    def test_unpin_not_found_returns_false(self):
        """unpin returns False if entry not found."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        result = history.unpin("nonexistent")
        assert result is False

    def test_unpin_not_pinned_returns_false(self):
        """unpin returns False if not pinned."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        result = history.unpin("lead")
        assert result is False

    def test_recent_sorted_by_time_descending(self):
        """recent returns entries sorted by opened_at_s descending."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.record_open("bass", 105.0)
        recent = history.recent()
        assert [e.preset_slug for e in recent] == ["pad", "bass", "lead"]

    def test_recent_excludes_pinned(self):
        """recent excludes pinned entries."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.pin("lead")
        recent = history.recent()
        assert len(recent) == 1
        assert recent[0].preset_slug == "pad"

    def test_recent_respects_limit(self):
        """recent respects n parameter."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        for i in range(10):
            history.record_open(f"preset_{i}", 100.0 + i)
        recent = history.recent(n=3)
        assert len(recent) == 3
        assert recent[0].preset_slug == "preset_9"

    def test_pinned_list_sorted_by_time_descending(self):
        """pinned_list returns pinned entries sorted by opened_at_s descending."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.record_open("bass", 105.0)
        history.pin("lead")
        history.pin("bass")
        pinned = history.pinned_list()
        # Pinned: bass (105.0) and lead (100.0), sorted desc by opened_at_s
        assert [e.preset_slug for e in pinned] == ["bass", "lead"]

    def test_combined_view_pinned_first(self):
        """combined_view returns pinned first, then recent."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.record_open("bass", 105.0)
        history.pin("lead")
        combined = history.combined_view()
        slugs = [e.preset_slug for e in combined]
        # pinned: ["lead"] (only one pinned)
        # recent: ["pad", "bass"] (most recent first)
        assert slugs == ["lead", "pad", "bass"]

    def test_combined_view_deduplicates(self):
        """combined_view doesn't double-list pinned entries."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.pin("lead")
        combined = history.combined_view()
        slugs = [e.preset_slug for e in combined]
        assert slugs.count("lead") == 1

    def test_pin_count(self):
        """pin_count returns number of pinned entries."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.record_open("bass", 105.0)
        assert history.pin_count() == 0
        history.pin("lead")
        assert history.pin_count() == 1
        history.pin("bass")
        assert history.pin_count() == 2
        history.unpin("lead")
        assert history.pin_count() == 1

    def test_recent_count(self):
        """recent_count returns total entries."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        assert history.recent_count() == 0
        history.record_open("lead", 100.0)
        assert history.recent_count() == 1
        history.record_open("pad", 110.0)
        assert history.recent_count() == 2
        history.pin("lead")
        assert history.recent_count() == 2  # Still 2, pinning doesn't add

    def test_remove_deletes_entry(self):
        """remove deletes an entry."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        assert history.recent_count() == 1
        result = history.remove("lead")
        assert result is True
        assert history.recent_count() == 0

    def test_remove_not_found_returns_false(self):
        """remove returns False if not found."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        result = history.remove("nonexistent")
        assert result is False

    def test_clear_empties_all(self):
        """clear removes all entries."""
        cfg = PinnedHistoryConfig()
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.record_open("bass", 105.0)
        assert history.recent_count() == 3
        history.clear()
        assert history.recent_count() == 0
        assert history.recent() == []
        assert history.pinned_list() == []

    def test_max_recent_fifo_eviction(self):
        """Entries beyond max_recent are evicted (oldest unpinned first)."""
        cfg = PinnedHistoryConfig(max_recent=3)
        history = MappingPinnedHistory(cfg)
        history.record_open("a", 100.0)
        history.record_open("b", 101.0)
        history.record_open("c", 102.0)
        assert history.recent_count() == 3
        # Adding 4th should evict oldest (a)
        history.record_open("d", 103.0)
        assert history.recent_count() == 3
        slugs = [e.preset_slug for e in history.recent()]
        assert "a" not in slugs
        assert set(slugs) == {"b", "c", "d"}

    def test_max_recent_eviction_preserves_pinned(self):
        """max_recent eviction doesn't remove pinned entries."""
        cfg = PinnedHistoryConfig(max_recent=2)
        history = MappingPinnedHistory(cfg)
        history.record_open("a", 100.0)
        history.record_open("b", 101.0)
        history.pin("a")  # Pin oldest
        history.record_open("c", 102.0)
        assert history.recent_count() == 3
        # Pin "a" is preserved even though it would be evicted
        assert history.pin_count() == 1
        recent = history.recent()
        assert len(recent) == 2
        # b and c should be in recent (a is pinned, not in recent list)
        assert set(e.preset_slug for e in recent) == {"b", "c"}

    def test_round_trip_serialization(self):
        """Entries can be serialized and deserialized."""
        cfg = PinnedHistoryConfig(max_recent=5, max_pinned=3)
        history = MappingPinnedHistory(cfg)
        history.record_open("lead", 100.0)
        history.record_open("pad", 110.0)
        history.pin("lead")

        # Serialize
        cfg_dict = cfg.to_dict()
        entries_dict = {
            slug: entry.to_dict() for slug, entry in history._entries.items()
        }

        # Deserialize into new instance
        cfg2 = PinnedHistoryConfig.from_dict(cfg_dict)
        history2 = MappingPinnedHistory(cfg2)
        for slug, entry_dict in entries_dict.items():
            entry = HistoryEntry.from_dict(entry_dict)
            history2._entries[slug] = entry

        # Verify match
        assert history2.recent_count() == history.recent_count()
        assert history2.pin_count() == history.pin_count()
        assert len(history2.pinned_list()) == 1
        assert history2.pinned_list()[0].preset_slug == "lead"
