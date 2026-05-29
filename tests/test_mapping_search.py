"""Tests for mapping_search module — finding notes / CCs / channels in mappings."""

from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_search import (
    SearchHit,
    find_channel,
    find_cc,
    find_note,
    summary,
    walk_paths,
)


class TestSearchHitRoundTrip:
    """SearchHit serialization and deserialization."""

    def test_search_hit_to_dict(self):
        """SearchHit serializes to dict."""
        hit = SearchHit(
            path="buttons.5.note",
            value=60,
            context="button index 5"
        )
        d = hit.to_dict()
        assert d["path"] == "buttons.5.note"
        assert d["value"] == 60
        assert d["context"] == "button index 5"

    def test_search_hit_from_dict(self):
        """SearchHit deserializes from dict."""
        d = {
            "path": "axes.2.cc",
            "value": 7,
            "context": "axis 2 / R-stick X"
        }
        hit = SearchHit.from_dict(d)
        assert hit.path == "axes.2.cc"
        assert hit.value == 7
        assert hit.context == "axis 2 / R-stick X"

    def test_search_hit_round_trip(self):
        """SearchHit round-trips through dict."""
        original = SearchHit(
            path="left_stick.chord_north[0]",
            value=72,
            context="left stick / chord north"
        )
        restored = SearchHit.from_dict(original.to_dict())
        assert restored.path == original.path
        assert restored.value == original.value
        assert restored.context == original.context


class TestWalkPaths:
    """walk_paths generator function."""

    def test_walk_paths_simple_dict(self):
        """walk_paths yields leaves from a simple dict."""
        d = {"a": 1, "b": 2}
        paths = list(walk_paths(d))
        # Should get ('a', 1) and ('b', 2)
        assert len(paths) == 2
        assert ("a", 1) in paths
        assert ("b", 2) in paths

    def test_walk_paths_nested_dict(self):
        """walk_paths yields leaves from nested dict."""
        d = {"buttons": {0: 60, 1: 62}, "axes": {0: 7}}
        paths = list(walk_paths(d))
        # Should get buttons.0, buttons.1, axes.0
        assert len(paths) == 3
        assert ("buttons.0", 60) in paths
        assert ("buttons.1", 62) in paths
        assert ("axes.0", 7) in paths

    def test_walk_paths_with_list(self):
        """walk_paths yields leaves from lists."""
        d = {"chord": [60, 62, 64]}
        paths = list(walk_paths(d))
        assert ("chord[0]", 60) in paths
        assert ("chord[1]", 62) in paths
        assert ("chord[2]", 64) in paths

    def test_walk_paths_deeply_nested(self):
        """walk_paths handles deeply nested structures."""
        d = {"left_stick": {"chord_north": [60, 62]}}
        paths = list(walk_paths(d))
        assert ("left_stick.chord_north[0]", 60) in paths
        assert ("left_stick.chord_north[1]", 62) in paths

    def test_walk_paths_with_key_filter(self):
        """walk_paths filters by key when key_filter provided."""
        d = {"buttons": {0: 60, 1: 62}, "axes": {0: 7}}
        paths = list(walk_paths(d, key_filter="0"))
        # Should only get leaves whose final key == "0"
        # buttons.0 and axes.0 both end with .0
        assert len(paths) == 2
        assert ("buttons.0", 60) in paths
        assert ("axes.0", 7) in paths

    def test_walk_paths_empty_dict(self):
        """walk_paths on empty dict yields nothing."""
        paths = list(walk_paths({}))
        assert len(paths) == 0

    def test_walk_paths_none_input(self):
        """walk_paths handles None gracefully."""
        paths = list(walk_paths(None))
        assert len(paths) == 0


class TestFindNote:
    """find_note function."""

    def test_find_note_in_buttons(self):
        """find_note finds notes in buttons dict."""
        m = {"buttons": {0: 60, 1: 62, 2: 64}}
        hits = find_note(m, 60)
        assert len(hits) == 1
        assert hits[0].path == "buttons.0"
        assert hits[0].value == 60

    def test_find_note_multiple_matches(self):
        """find_note returns all occurrences."""
        m = {
            "buttons": {0: 60, 1: 60, 2: 64},
            "hats": {"up": 60}
        }
        hits = find_note(m, 60)
        assert len(hits) == 3
        paths = {h.path for h in hits}
        assert "buttons.0" in paths
        assert "buttons.1" in paths
        assert "hats.up" in paths

    def test_find_note_in_chord_north(self):
        """find_note finds notes in chord_north list."""
        m = {"left_stick": {"chord_north": [60, 62, 64]}}
        hits = find_note(m, 62)
        assert len(hits) == 1
        assert "chord_north" in hits[0].path
        assert hits[0].value == 62

    def test_find_note_in_multiple_chords(self):
        """find_note finds note in all chord directions."""
        m = {
            "left_stick": {
                "chord_north": [60, 62],
                "chord_east": [64],
                "chord_south": [60],
            }
        }
        hits = find_note(m, 60)
        # Should find in chord_north[0] and chord_south[0]
        assert len(hits) == 2

    def test_find_note_in_corners(self):
        """find_note finds notes in corner configs."""
        m = {
            "left_stick_corners": {"notes": [60, 62, 64, 65, 67, 69, 71, 72]},
            "right_stick_corners": {"notes": [36, 38, 40]}
        }
        hits = find_note(m, 62)
        assert len(hits) == 1
        assert "corner" in hits[0].path or "notes" in hits[0].path

    def test_find_note_in_gestures(self):
        """find_note finds notes in swipe/pinch gesture configs."""
        m = {
            "swipe_up_note": 60,
            "swipe_down_note": 61,
            "pinch_in_note": 60
        }
        hits = find_note(m, 60)
        assert len(hits) == 2
        paths = {h.path for h in hits}
        assert "swipe_up_note" in paths
        assert "pinch_in_note" in paths

    def test_find_note_unused_returns_empty(self):
        """find_note returns empty list for unused note."""
        m = {"buttons": {0: 60, 1: 62}, "hats": {"up": 90}}
        hits = find_note(m, 100)
        assert len(hits) == 0

    def test_find_note_none_input(self):
        """find_note handles None gracefully."""
        hits = find_note(None, 60)
        assert len(hits) == 0

    def test_find_note_empty_mapping(self):
        """find_note handles empty mapping."""
        hits = find_note({}, 60)
        assert len(hits) == 0


class TestFindCC:
    """find_cc function."""

    def test_find_cc_in_axes(self):
        """find_cc finds CCs in axes dict."""
        m = {"axes": {0: 7, 1: 8, 2: 7}}
        hits = find_cc(m, 7)
        assert len(hits) == 2
        paths = {h.path for h in hits}
        assert "axes.0" in paths
        assert "axes.2" in paths

    def test_find_cc_in_triggers(self):
        """find_cc finds CCs in trigger configs."""
        m = {
            "triggers": {
                "L2": {"cc": 1},
                "R2": {"cc": 2}
            }
        }
        hits = find_cc(m, 1)
        assert len(hits) == 1
        assert "L2" in hits[0].path

    def test_find_cc_in_crossfade(self):
        """find_cc finds CCs in crossfade_cc_b."""
        m = {
            "triggers": {
                "L2": {"cc": 7, "crossfade_cc_b": 8},
                "R2": {"cc": 9, "crossfade_cc_b": 8}
            }
        }
        hits = find_cc(m, 8)
        assert len(hits) == 2
        assert all("crossfade_cc_b" in h.path for h in hits)

    def test_find_cc_in_stick_polar(self):
        """find_cc finds CCs in stick polar configs."""
        m = {
            "left_stick": {
                "polar_angle_cc": 20,
                "polar_mag_cc": 21
            }
        }
        hits = find_cc(m, 20)
        assert len(hits) == 1
        assert "polar_angle_cc" in hits[0].path

    def test_find_cc_in_bow_mode(self):
        """find_cc finds CCs in bow_mode configs."""
        m = {
            "triggers": {
                "L2": {"bow_mode": True, "bow_cc": 11},
                "R2": {"bow_cc": 11}
            }
        }
        hits = find_cc(m, 11)
        assert len(hits) == 2

    def test_find_cc_in_random_mod(self):
        """find_cc finds CCs in random_mod configs."""
        m = {
            "left_stick": {"random_mod_enabled": True, "random_mod_cc": 16},
            "right_stick": {"random_mod_cc": 17}
        }
        hits = find_cc(m, 16)
        assert len(hits) == 1
        assert "random_mod_cc" in hits[0].path

    def test_find_cc_in_touchpad(self):
        """find_cc finds CCs in touchpad config."""
        m = {
            "touchpad": {
                "enabled": True,
                "x_cc": 20,
                "y_cc": 21
            }
        }
        hits = find_cc(m, 20)
        assert len(hits) == 1
        assert "touchpad" in hits[0].path

    def test_find_cc_unused_returns_empty(self):
        """find_cc returns empty list for unused CC."""
        m = {"axes": {0: 7, 1: 8}}
        hits = find_cc(m, 50)
        assert len(hits) == 0

    def test_find_cc_none_input(self):
        """find_cc handles None gracefully."""
        hits = find_cc(None, 7)
        assert len(hits) == 0

    def test_find_cc_empty_mapping(self):
        """find_cc handles empty mapping."""
        hits = find_cc({}, 7)
        assert len(hits) == 0


class TestFindChannel:
    """find_channel function."""

    def test_find_channel_global(self):
        """find_channel finds global MIDI channel."""
        m = {"midi_channel": 5}
        hits = find_channel(m, 5)
        assert len(hits) == 1
        assert hits[0].path == "midi_channel"
        assert hits[0].context == "global MIDI channel"

    def test_find_channel_in_button_overrides(self):
        """find_channel finds channel overrides in buttons."""
        m = {"button_channels": {0: 5, 1: 5, 2: 3}}
        hits = find_channel(m, 5)
        assert len(hits) == 2
        assert all("button_channels" in h.path for h in hits)

    def test_find_channel_in_axis_overrides(self):
        """find_channel finds channel overrides in axes."""
        m = {"axis_channels": {0: 2, 1: 2}}
        hits = find_channel(m, 2)
        assert len(hits) == 2

    def test_find_channel_in_hat_overrides(self):
        """find_channel finds channel overrides in hats."""
        m = {"hat_channels": {"up": 3, "down": 3}}
        hits = find_channel(m, 3)
        assert len(hits) == 2

    def test_find_channel_in_stick_chord(self):
        """find_channel finds channel overrides in stick chord configs."""
        m = {
            "left_stick": {"chord_channel": 5},
            "right_stick": {"chord_channel": 5}
        }
        hits = find_channel(m, 5)
        assert len(hits) == 2
        assert all("stick" in h.path for h in hits)

    def test_find_channel_in_trigger_override(self):
        """find_channel finds channel_override in triggers."""
        m = {
            "triggers": {
                "L2": {"channel_override": 2},
                "R2": {"channel_override": 2}
            }
        }
        hits = find_channel(m, 2)
        assert len(hits) == 2

    def test_find_channel_in_trigger_aftertouch(self):
        """find_channel finds channel_override in aftertouch."""
        m = {
            "triggers": {
                "L2": {"aftertouch": {"channel_override": 3}}
            }
        }
        hits = find_channel(m, 3)
        assert len(hits) == 1

    def test_find_channel_in_battery_alert(self):
        """find_channel finds channel_override in battery_alert."""
        m = {
            "battery_alert": {"enabled": True, "channel_override": 4}
        }
        hits = find_channel(m, 4)
        assert len(hits) == 1

    def test_find_channel_ignores_negative_one(self):
        """find_channel ignores -1 (unset) channel markers."""
        m = {"triggers": {"L2": {"channel_override": -1}}}
        hits = find_channel(m, -1)
        assert len(hits) == 0

    def test_find_channel_multiple_sources(self):
        """find_channel finds same channel across different configs."""
        m = {
            "midi_channel": 5,
            "button_channels": {0: 5},
            "left_stick": {"chord_channel": 5}
        }
        hits = find_channel(m, 5)
        assert len(hits) == 3

    def test_find_channel_unused_returns_empty(self):
        """find_channel returns empty list for unused channel."""
        m = {"midi_channel": 0, "button_channels": {0: 1}}
        hits = find_channel(m, 10)
        assert len(hits) == 0

    def test_find_channel_none_input(self):
        """find_channel handles None gracefully."""
        hits = find_channel(None, 5)
        assert len(hits) == 0

    def test_find_channel_empty_mapping(self):
        """find_channel handles empty mapping."""
        hits = find_channel({}, 0)
        assert len(hits) == 0


class TestSummary:
    """summary function."""

    def test_summary_empty_mapping(self):
        """summary returns zeros for empty mapping."""
        result = summary({})
        assert result["unique_notes"] == 0
        assert result["unique_ccs"] == 0
        assert result["channels_in_use"] == 0
        assert result["total_controls"] == 0

    def test_summary_simple_mapping(self):
        """summary counts controls in simple mapping."""
        m = {
            "buttons": {0: 60, 1: 62, 2: 64},
            "axes": {0: 7, 1: 8}
        }
        result = summary(m)
        assert result["unique_notes"] == 3  # 60, 62, 64
        assert result["unique_ccs"] == 2    # 7, 8
        assert result["total_controls"] == 5

    def test_summary_with_global_channel(self):
        """summary counts global channel."""
        m = {"midi_channel": 3}
        result = summary(m)
        assert result["channels_in_use"] == 1

    def test_summary_with_channel_overrides(self):
        """summary counts all unique channels."""
        m = {
            "midi_channel": 0,
            "button_channels": {0: 1, 1: 2},
            "axis_channels": {0: 1}
        }
        result = summary(m)
        assert result["channels_in_use"] == 3  # 0, 1, 2

    def test_summary_with_chords(self):
        """summary includes notes from chords."""
        m = {
            "buttons": {0: 60},
            "left_stick": {"chord_north": [60, 62, 64]}
        }
        result = summary(m)
        # 60 appears twice, but should deduplicate
        assert result["unique_notes"] == 3  # 60, 62, 64

    def test_summary_skips_zero_controls(self):
        """summary ignores zero-valued controls."""
        m = {
            "buttons": {0: 60, 1: 0, 2: 62},
            "axes": {0: 0, 1: 7}
        }
        result = summary(m)
        assert result["total_controls"] == 3  # 60, 62, 7

    def test_summary_with_multiple_ccs(self):
        """summary counts multiple CC types."""
        m = {
            "axes": {0: 7},
            "left_stick": {"polar_angle_cc": 20, "random_mod_cc": 16},
            "triggers": {"L2": {"bow_cc": 11}}
        }
        result = summary(m)
        assert result["unique_ccs"] == 4  # 7, 20, 16, 11

    def test_summary_none_input(self):
        """summary handles None gracefully."""
        result = summary(None)
        assert result["unique_notes"] == 0
        assert result["unique_ccs"] == 0
        assert result["channels_in_use"] == 0
        assert result["total_controls"] == 0


class TestIntegration:
    """Integration tests with realistic mapping structures."""

    def test_find_and_summary_realistic(self):
        """Test find functions and summary on a realistic mapping."""
        m = {
            "name": "Test Mapping",
            "midi_channel": 0,
            "schema_version": 4,
            "buttons": {
                0: 60, 1: 62, 2: 64, 3: 65,
                4: 67, 5: 69,
                6: 71, 7: 72,
            },
            "axes": {
                0: 3, 1: 4, 2: 5, 3: 6,
                4: 1, 5: 2,
            },
            "hats": {"up": 78, "down": 79, "left": 80, "right": 81},
            "button_channels": {0: 0},
            "left_stick": {
                "chord_enabled": True,
                "chord_north": [60, 62],
                "chord_east": [64, 65],
            },
            "triggers": {
                "L2": {"cc": 1, "crossfade_cc_b": 11},
                "R2": {"cc": 2}
            }
        }

        # Test find_note
        hits = find_note(m, 60)
        assert len(hits) >= 2  # in buttons.0 and chord_north

        # Test find_cc
        hits = find_cc(m, 3)
        assert len(hits) == 1
        assert "axes.0" in hits[0].path

        # Test find_channel
        hits = find_channel(m, 0)
        assert len(hits) >= 1

        # Test summary
        s = summary(m)
        assert s["unique_notes"] > 8
        assert s["unique_ccs"] > 5
        assert s["channels_in_use"] > 0
        assert s["total_controls"] > 10

    def test_deeply_nested_structures(self):
        """Test walk_paths with deeply nested dict/list combinations."""
        m = {
            "a": {
                "b": {
                    "c": {
                        "d": [1, 2, [3, 4]]
                    }
                }
            }
        }
        paths = list(walk_paths(m))
        # walk_paths should navigate nested lists
        assert len(paths) > 0
        values = [v for _, v in paths]
        assert 1 in values
        assert 2 in values
