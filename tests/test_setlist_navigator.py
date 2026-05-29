"""Tests for setlist navigator — preset slug list with history and bookmarks.

SetlistNavigator manages a list of SetlistEntry items with navigation
(next, prev, jump, back) and bookmarks. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestSetlistEntry:
    """SetlistEntry dataclass — serialize/deserialize."""

    def test_entry_default_construction(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistEntry
        entry = SetlistEntry()
        assert entry.slug == ""
        assert entry.display_name == ""
        assert entry.notes == ""
        assert entry.bookmarked is False

    def test_entry_with_all_fields(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistEntry
        entry = SetlistEntry(
            slug="lead",
            display_name="Lead Synth",
            notes="12dB boost",
            bookmarked=True,
        )
        assert entry.slug == "lead"
        assert entry.display_name == "Lead Synth"
        assert entry.notes == "12dB boost"
        assert entry.bookmarked is True

    def test_entry_to_dict(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistEntry
        entry = SetlistEntry(
            slug="pad",
            display_name="Pad",
            notes="lush reverb",
            bookmarked=False,
        )
        d = entry.to_dict()
        assert d["slug"] == "pad"
        assert d["display_name"] == "Pad"
        assert d["notes"] == "lush reverb"
        assert d["bookmarked"] is False

    def test_entry_from_dict(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistEntry
        d = {
            "slug": "bass",
            "display_name": "Bass",
            "notes": "sub layer",
            "bookmarked": True,
        }
        entry = SetlistEntry.from_dict(d)
        assert entry.slug == "bass"
        assert entry.display_name == "Bass"
        assert entry.notes == "sub layer"
        assert entry.bookmarked is True

    def test_entry_round_trip(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistEntry
        original = SetlistEntry(
            slug="arp",
            display_name="Arpeggiator",
            notes="16th notes",
            bookmarked=True,
        )
        d = original.to_dict()
        restored = SetlistEntry.from_dict(d)
        assert restored.slug == original.slug
        assert restored.display_name == original.display_name
        assert restored.notes == original.notes
        assert restored.bookmarked == original.bookmarked


class TestSetlistNavigatorConfig:
    """SetlistNavigatorConfig — clamp max_history."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistNavigatorConfig
        cfg = SetlistNavigatorConfig()
        assert cfg.loop is False
        assert cfg.max_history == 50

    def test_config_clamp_max_history_below_5(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistNavigatorConfig
        cfg = SetlistNavigatorConfig(max_history=0)
        assert cfg.max_history == 5
        cfg = SetlistNavigatorConfig(max_history=3)
        assert cfg.max_history == 5

    def test_config_clamp_max_history_above_10000(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistNavigatorConfig
        cfg = SetlistNavigatorConfig(max_history=15000)
        assert cfg.max_history == 10000
        cfg = SetlistNavigatorConfig(max_history=50000)
        assert cfg.max_history == 10000

    def test_config_no_clamp_in_range(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistNavigatorConfig
        cfg = SetlistNavigatorConfig(max_history=100)
        assert cfg.max_history == 100

    def test_config_to_dict(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistNavigatorConfig
        cfg = SetlistNavigatorConfig(loop=True, max_history=75)
        d = cfg.to_dict()
        assert d["loop"] is True
        assert d["max_history"] == 75

    def test_config_from_dict(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistNavigatorConfig
        d = {"loop": True, "max_history": 100}
        cfg = SetlistNavigatorConfig.from_dict(d)
        assert cfg.loop is True
        assert cfg.max_history == 100

    def test_config_round_trip(self):
        from gamepad_midi_bridge.setlist_navigator import SetlistNavigatorConfig
        original = SetlistNavigatorConfig(loop=True, max_history=200)
        d = original.to_dict()
        restored = SetlistNavigatorConfig.from_dict(d)
        assert restored.loop == original.loop
        assert restored.max_history == original.max_history


class TestSetlistNavigatorEmpty:
    """SetlistNavigator with empty entry list."""

    def test_empty_navigator_current_is_none(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
        )
        cfg = SetlistNavigatorConfig()
        nav = SetlistNavigator(cfg)
        assert nav.current() is None

    def test_empty_navigator_next_returns_none(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
        )
        cfg = SetlistNavigatorConfig()
        nav = SetlistNavigator(cfg)
        assert nav.next() is None

    def test_empty_navigator_prev_returns_none(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
        )
        cfg = SetlistNavigatorConfig()
        nav = SetlistNavigator(cfg)
        assert nav.prev() is None

    def test_empty_navigator_progress_is_zero_zero(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
        )
        cfg = SetlistNavigatorConfig()
        nav = SetlistNavigator(cfg)
        assert nav.progress() == (0, 0)


class TestSetlistNavigatorBasic:
    """SetlistNavigator core navigation."""

    def test_three_entry_setlist_current(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.current().slug == "lead"

    def test_next_advances_through_entries(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.current().slug == "lead"
        assert nav.next().slug == "pad"
        assert nav.next().slug == "bass"

    def test_next_at_end_without_loop_stays(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig(loop=False)
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        nav.next()
        nav.next()
        assert nav.current().slug == "bass"
        assert nav.next().slug == "bass"  # stays

    def test_next_at_end_with_loop_wraps(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig(loop=True)
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        nav.next()
        nav.next()
        assert nav.current().slug == "bass"
        assert nav.next().slug == "lead"  # wraps

    def test_prev_decrements(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        nav.next()
        nav.next()
        assert nav.prev().slug == "pad"
        assert nav.prev().slug == "lead"

    def test_prev_at_start_without_loop_stays(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig(loop=False)
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.current().slug == "lead"
        assert nav.prev().slug == "lead"  # stays

    def test_prev_at_start_with_loop_wraps(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig(loop=True)
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.current().slug == "lead"
        assert nav.prev().slug == "bass"  # wraps

    def test_progress_returns_1based_position(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.progress() == (1, 3)
        nav.next()
        assert nav.progress() == (2, 3)
        nav.next()
        assert nav.progress() == (3, 3)


class TestSetlistNavigatorJump:
    """SetlistNavigator jump_to behavior."""

    def test_jump_to_existing_slug(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        result = nav.jump_to("bass")
        assert result is not None
        assert result.slug == "bass"
        assert nav.current().slug == "bass"

    def test_jump_to_non_existent_slug_returns_none(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
        ]
        nav = SetlistNavigator(cfg, entries)
        result = nav.jump_to("nonexistent")
        assert result is None
        assert nav.current().slug == "lead"  # stays at original


class TestSetlistNavigatorHistory:
    """SetlistNavigator history and back() behavior."""

    def test_back_pops_history(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.current().slug == "lead"
        nav.next()
        assert nav.current().slug == "pad"
        result = nav.back()
        assert result is not None
        assert result.slug == "lead"

    def test_back_with_empty_history_returns_none(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [SetlistEntry(slug="lead")]
        nav = SetlistNavigator(cfg, entries)
        result = nav.back()
        assert result is None

    def test_history_records_prior_indices(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        nav.next()  # from 0 to 1, history=[0]
        nav.next()  # from 1 to 2, history=[0, 1]
        nav.jump_to("lead")  # from 2 to 0, history=[0, 1, 2]

        # Back three times: 0 <- 2 <- 1 <- 0
        assert nav.back().slug == "bass"  # back to index 2
        assert nav.back().slug == "pad"  # back to index 1
        assert nav.back().slug == "lead"  # back to index 0

    def test_max_history_caps_history_size(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig(max_history=5)
        entries = [
            SetlistEntry(slug=f"s{i}") for i in range(10)
        ]
        nav = SetlistNavigator(cfg, entries)

        # Make 10 navigations
        for _ in range(10):
            nav.next()

        # History should only contain last 5 indices
        assert len(nav._history) <= 5


class TestSetlistNavigatorBookmarks:
    """SetlistNavigator bookmark functionality."""

    def test_bookmark_current_toggles(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.current().bookmarked is False
        result = nav.bookmark_current()
        assert result is True
        assert nav.current().bookmarked is True
        result = nav.bookmark_current()
        assert result is False
        assert nav.current().bookmarked is False

    def test_bookmarks_returns_only_bookmarked(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead", bookmarked=True),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass", bookmarked=True),
        ]
        nav = SetlistNavigator(cfg, entries)
        bookmarks = nav.bookmarks()
        assert len(bookmarks) == 2
        assert bookmarks[0].slug == "lead"
        assert bookmarks[1].slug == "bass"

    def test_goto_first_bookmark(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad", bookmarked=True),
            SetlistEntry(slug="bass", bookmarked=True),
        ]
        nav = SetlistNavigator(cfg, entries)
        result = nav.goto_first_bookmark()
        assert result is not None
        assert result.slug == "pad"
        assert nav.current().slug == "pad"

    def test_goto_first_bookmark_none_bookmarked_returns_none(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
        ]
        nav = SetlistNavigator(cfg, entries)
        result = nav.goto_first_bookmark()
        assert result is None


class TestSetlistNavigatorListManagement:
    """SetlistNavigator add/remove/clear."""

    def test_add_appends_entry(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        nav = SetlistNavigator(cfg)
        assert len(nav.entries) == 0

        entry = SetlistEntry(slug="lead")
        nav.add(entry)
        assert len(nav.entries) == 1
        assert nav.current().slug == "lead"

    def test_remove_by_slug(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        assert nav.remove("pad") is True
        assert len(nav.entries) == 2
        assert nav.entries[0].slug == "lead"
        assert nav.entries[1].slug == "bass"

    def test_remove_non_existent_returns_false(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [SetlistEntry(slug="lead")]
        nav = SetlistNavigator(cfg, entries)
        assert nav.remove("nonexistent") is False

    def test_remove_adjusts_index_if_needed(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
            SetlistEntry(slug="bass"),
        ]
        nav = SetlistNavigator(cfg, entries)
        nav.next()
        nav.next()  # at index 2 (bass)
        nav.remove("pad")  # index 1
        assert nav._index == 1  # decremented because removed index was before current
        assert nav.current().slug == "bass"

    def test_clear_empties_everything(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        cfg = SetlistNavigatorConfig()
        entries = [
            SetlistEntry(slug="lead"),
            SetlistEntry(slug="pad"),
        ]
        nav = SetlistNavigator(cfg, entries)
        nav.next()
        nav._history.append(99)  # manual history entry for test

        nav.clear()
        assert len(nav.entries) == 0
        assert nav._index == 0
        assert len(nav._history) == 0


class TestSetlistNavigatorIntegration:
    """Integration tests — realistic workflows."""

    def test_realistic_song_navigation_workflow(self):
        from gamepad_midi_bridge.setlist_navigator import (
            SetlistNavigator,
            SetlistNavigatorConfig,
            SetlistEntry,
        )
        # Song setlist with loop enabled
        cfg = SetlistNavigatorConfig(loop=True)
        songs = [
            SetlistEntry(slug="intro", display_name="Intro"),
            SetlistEntry(slug="verse", display_name="Verse"),
            SetlistEntry(slug="chorus", display_name="Chorus"),
            SetlistEntry(slug="bridge", display_name="Bridge"),
            SetlistEntry(slug="outro", display_name="Outro"),
        ]
        nav = SetlistNavigator(cfg, songs)

        # Start at intro
        assert nav.current().slug == "intro"

        # Progress through song
        assert nav.next().slug == "verse"
        assert nav.next().slug == "chorus"

        # Bookmark chorus
        nav.bookmark_current()

        # Continue to bridge and outro
        assert nav.next().slug == "bridge"
        assert nav.next().slug == "outro"

        # Loop back to intro
        assert nav.next().slug == "intro"

        # Jump back to verse, navigate back
        nav.jump_to("verse")
        assert nav.back().slug == "intro"

        # Find and go to bookmarked chorus
        assert nav.goto_first_bookmark().slug == "chorus"

        # Show progress
        assert nav.progress() == (3, 5)
