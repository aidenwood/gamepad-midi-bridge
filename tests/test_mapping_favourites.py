"""Tests for MappingFavourites."""

import pytest
from gamepad_midi_bridge.mapping_favourites import (
    FavouriteEntry,
    FavouritesConfig,
    MappingFavourites,
)


class TestFavouriteEntry:
    """Tests for FavouriteEntry dataclass."""

    def test_entry_defaults(self):
        """Entry creates with sensible defaults."""
        entry = FavouriteEntry(preset_slug="test")
        assert entry.preset_slug == "test"
        assert entry.stars == 0
        assert entry.pinned is False
        assert entry.last_played_at is None
        assert entry.play_count == 0
        assert entry.tags == []
        assert entry.notes == ""

    def test_entry_clamp_stars_high(self):
        """Entry clamps stars > 5 to 5."""
        entry = FavouriteEntry(preset_slug="test", stars=10)
        assert entry.stars == 5

    def test_entry_clamp_stars_low(self):
        """Entry clamps stars < 0 to 0."""
        entry = FavouriteEntry(preset_slug="test", stars=-3)
        assert entry.stars == 0

    def test_entry_to_dict(self):
        """Entry.to_dict() serializes all fields."""
        entry = FavouriteEntry(
            preset_slug="test",
            stars=4,
            pinned=True,
            play_count=5,
            tags=["fast", "electronic"],
            notes="Good one",
        )
        d = entry.to_dict()
        assert d["preset_slug"] == "test"
        assert d["stars"] == 4
        assert d["pinned"] is True
        assert d["play_count"] == 5
        assert d["tags"] == ["fast", "electronic"]
        assert d["notes"] == "Good one"

    def test_entry_from_dict(self):
        """FavouriteEntry.from_dict() deserializes correctly."""
        d = {
            "preset_slug": "test",
            "stars": 3,
            "pinned": False,
            "last_played_at": 123.45,
            "play_count": 2,
            "tags": ["synth"],
            "notes": "Nice",
        }
        entry = FavouriteEntry.from_dict(d)
        assert entry.preset_slug == "test"
        assert entry.stars == 3
        assert entry.pinned is False
        assert entry.last_played_at == 123.45
        assert entry.play_count == 2
        assert entry.tags == ["synth"]
        assert entry.notes == "Nice"


class TestFavouritesConfig:
    """Tests for FavouritesConfig dataclass."""

    def test_config_defaults(self):
        """Config uses sensible defaults."""
        cfg = FavouritesConfig()
        assert cfg.max_entries == 500
        assert cfg.max_recently_played == 20

    def test_config_clamp_max_entries_low(self):
        """Config clamps max_entries < 10 to 10."""
        cfg = FavouritesConfig(max_entries=5)
        assert cfg.max_entries == 10

    def test_config_clamp_max_entries_high(self):
        """Config clamps max_entries > 100000 to 100000."""
        cfg = FavouritesConfig(max_entries=200000)
        assert cfg.max_entries == 100000

    def test_config_clamp_max_recently_played_low(self):
        """Config clamps max_recently_played < 1 to 1."""
        cfg = FavouritesConfig(max_recently_played=0)
        assert cfg.max_recently_played == 1

    def test_config_clamp_max_recently_played_high(self):
        """Config clamps max_recently_played > 1000 to 1000."""
        cfg = FavouritesConfig(max_recently_played=2000)
        assert cfg.max_recently_played == 1000

    def test_config_to_dict(self):
        """Config.to_dict() serializes all fields."""
        cfg = FavouritesConfig(max_entries=100, max_recently_played=30)
        d = cfg.to_dict()
        assert d["max_entries"] == 100
        assert d["max_recently_played"] == 30

    def test_config_from_dict(self):
        """FavouritesConfig.from_dict() deserializes correctly."""
        d = {"max_entries": 1000, "max_recently_played": 50}
        cfg = FavouritesConfig.from_dict(d)
        assert cfg.max_entries == 1000
        assert cfg.max_recently_played == 50


class TestMappingFavourites:
    """Tests for MappingFavourites manager."""

    def test_empty_get_returns_none(self):
        """get() returns None for missing entry."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        assert fav.get("missing") is None

    def test_set_stars_clamp_high(self):
        """set_stars clamps to 0..5 (high)."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        entry = fav.set_stars("test", 10)
        assert entry.stars == 5

    def test_set_stars_clamp_low(self):
        """set_stars clamps to 0..5 (low)."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        entry = fav.set_stars("test", -2)
        assert entry.stars == 0

    def test_set_stars_valid(self):
        """set_stars sets valid rating."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        entry = fav.set_stars("test", 3)
        assert entry.stars == 3

    def test_set_stars_creates_entry(self):
        """set_stars creates entry if missing."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        entry = fav.set_stars("new", 4)
        assert fav.get("new") is not None
        assert fav.get("new").stars == 4

    def test_pin_sets_true(self):
        """pin() sets pinned=True."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        entry = fav.pin("test")
        assert entry.pinned is True

    def test_pin_creates_entry(self):
        """pin() creates entry if missing."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.pin("new")
        assert fav.get("new") is not None
        assert fav.get("new").pinned is True

    def test_unpin_sets_false(self):
        """unpin() sets pinned=False."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.pin("test")
        entry = fav.unpin("test")
        assert entry.pinned is False

    def test_unpin_creates_entry(self):
        """unpin() creates entry if missing."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.unpin("new")
        assert fav.get("new") is not None
        assert fav.get("new").pinned is False

    def test_mark_played_increments(self):
        """mark_played increments play_count."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.mark_played("test", 100.0)
        fav.mark_played("test", 101.0)
        entry = fav.get("test")
        assert entry.play_count == 2

    def test_mark_played_updates_timestamp(self):
        """mark_played updates last_played_at."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.mark_played("test", 100.0)
        assert fav.get("test").last_played_at == 100.0
        fav.mark_played("test", 200.0)
        assert fav.get("test").last_played_at == 200.0

    def test_mark_played_creates_entry(self):
        """mark_played creates entry if missing."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.mark_played("new", 100.0)
        entry = fav.get("new")
        assert entry is not None
        assert entry.play_count == 1
        assert entry.last_played_at == 100.0

    def test_pinned_list_empty(self):
        """pinned_list returns empty when no pins."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("a", 5)
        fav.set_stars("b", 3)
        assert fav.pinned_list() == []

    def test_pinned_list_only_pinned(self):
        """pinned_list returns only pinned entries."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.pin("a")
        fav.set_stars("b", 5)
        fav.pin("c")
        pinned = fav.pinned_list()
        assert len(pinned) == 2
        slugs = {e.preset_slug for e in pinned}
        assert slugs == {"a", "c"}

    def test_top_starred_filters_min_stars(self):
        """top_starred filters by min_stars."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("a", 5)
        fav.set_stars("b", 4)
        fav.set_stars("c", 3)
        fav.set_stars("d", 2)
        results = fav.top_starred(min_stars=4)
        assert len(results) == 2
        assert {e.preset_slug for e in results} == {"a", "b"}

    def test_top_starred_sorts_desc(self):
        """top_starred sorts by stars descending."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("a", 3)
        fav.set_stars("b", 5)
        fav.set_stars("c", 4)
        results = fav.top_starred(min_stars=3)
        assert [e.stars for e in results] == [5, 4, 3]

    def test_recently_played_sorts_desc(self):
        """recently_played sorts by last_played_at descending."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.mark_played("a", 100.0)
        fav.mark_played("b", 300.0)
        fav.mark_played("c", 200.0)
        results = fav.recently_played(n=10)
        assert [e.preset_slug for e in results] == ["b", "c", "a"]

    def test_recently_played_excludes_unplayed(self):
        """recently_played excludes entries with no last_played_at."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.mark_played("a", 100.0)
        fav.set_stars("b", 5)  # No last_played_at
        fav.mark_played("c", 200.0)
        results = fav.recently_played(n=10)
        assert {e.preset_slug for e in results} == {"a", "c"}

    def test_recently_played_caps_at_max_recently_played(self):
        """recently_played caps at max_recently_played."""
        cfg = FavouritesConfig(max_recently_played=3)
        fav = MappingFavourites(cfg)
        for i in range(10):
            fav.mark_played(f"test_{i}", float(i))
        results = fav.recently_played(n=100)
        assert len(results) == 3

    def test_most_played_sorts_desc(self):
        """most_played sorts by play_count descending."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.mark_played("a", 100.0)
        fav.mark_played("a", 101.0)
        fav.mark_played("a", 102.0)
        fav.mark_played("b", 100.0)
        fav.mark_played("b", 101.0)
        fav.mark_played("c", 100.0)
        results = fav.most_played(n=10)
        assert [e.play_count for e in results] == [3, 2, 1]

    def test_most_played_excludes_unplayed(self):
        """most_played excludes entries with play_count=0."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("a", 5)  # play_count=0
        fav.mark_played("b", 100.0)
        results = fav.most_played(n=10)
        assert {e.preset_slug for e in results} == {"b"}

    def test_remove_returns_true(self):
        """remove returns True when entry exists."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("test", 5)
        assert fav.remove("test") is True

    def test_remove_deletes(self):
        """remove deletes the entry."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("test", 5)
        fav.remove("test")
        assert fav.get("test") is None

    def test_remove_returns_false(self):
        """remove returns False when entry missing."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        assert fav.remove("missing") is False

    def test_clear_empties(self):
        """clear removes all entries."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("a", 5)
        fav.set_stars("b", 3)
        fav.clear()
        assert fav.get("a") is None
        assert fav.get("b") is None

    def test_add_tag_dedupes(self):
        """add_tag returns False if tag already exists."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        assert fav.add_tag("test", "synth") is True
        assert fav.add_tag("test", "synth") is False

    def test_add_tag_creates_entry(self):
        """add_tag creates entry if missing."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.add_tag("new", "drums")
        assert fav.get("new") is not None
        assert "drums" in fav.get("new").tags

    def test_remove_tag_returns_true(self):
        """remove_tag returns True when tag exists."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.add_tag("test", "synth")
        assert fav.remove_tag("test", "synth") is True

    def test_remove_tag_removes(self):
        """remove_tag removes the tag."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.add_tag("test", "synth")
        fav.add_tag("test", "fast")
        fav.remove_tag("test", "synth")
        assert "synth" not in fav.get("test").tags
        assert "fast" in fav.get("test").tags

    def test_remove_tag_returns_false(self):
        """remove_tag returns False when tag missing."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.set_stars("test", 5)
        assert fav.remove_tag("test", "missing") is False

    def test_find_by_tag_returns_matching(self):
        """find_by_tag returns all entries with tag."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.add_tag("a", "drums")
        fav.add_tag("b", "drums")
        fav.add_tag("c", "synth")
        results = fav.find_by_tag("drums")
        assert {e.preset_slug for e in results} == {"a", "b"}

    def test_find_by_tag_empty(self):
        """find_by_tag returns empty when no matches."""
        cfg = FavouritesConfig()
        fav = MappingFavourites(cfg)
        fav.add_tag("a", "drums")
        results = fav.find_by_tag("missing")
        assert results == []
