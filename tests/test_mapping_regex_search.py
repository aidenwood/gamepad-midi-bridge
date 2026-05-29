"""Tests for mapping_regex_search module — regex-based value and key search."""

from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_regex_search import (
    RegexMatch,
    compile_safe,
    replace,
    search,
    search_keys,
    search_values_only,
)


class TestRegexMatchRoundTrip:
    """RegexMatch serialization and deserialization."""

    def test_regex_match_to_dict(self):
        """RegexMatch serializes to dict."""
        match = RegexMatch(
            path="description",
            value="Punchy Drum Kit",
            matched_text="Drum"
        )
        d = match.to_dict()
        assert d["path"] == "description"
        assert d["value"] == "Punchy Drum Kit"
        assert d["matched_text"] == "Drum"

    def test_regex_match_from_dict(self):
        """RegexMatch deserializes from dict."""
        d = {
            "path": "name",
            "value": "Lead Synth",
            "matched_text": "Lead"
        }
        match = RegexMatch.from_dict(d)
        assert match.path == "name"
        assert match.value == "Lead Synth"
        assert match.matched_text == "Lead"

    def test_regex_match_round_trip(self):
        """RegexMatch round-trips through dict."""
        original = RegexMatch(
            path="buttons.5",
            value=60,
            matched_text="60"
        )
        restored = RegexMatch.from_dict(original.to_dict())
        assert restored.path == original.path
        assert restored.value == original.value
        assert restored.matched_text == original.matched_text


class TestCompileSafe:
    """compile_safe function."""

    def test_compile_safe_valid_pattern(self):
        """compile_safe returns compiled Pattern on valid pattern."""
        pattern = compile_safe(r"drum")
        assert pattern is not None
        assert pattern.search("drumkit") is not None

    def test_compile_safe_invalid_pattern(self):
        """compile_safe returns None on invalid pattern."""
        pattern = compile_safe(r"[invalid(")
        assert pattern is None

    def test_compile_safe_complex_pattern(self):
        """compile_safe handles complex patterns."""
        pattern = compile_safe(r"(cc|note|channel)")
        assert pattern is not None
        assert pattern.search("cc74") is not None


class TestSearch:
    """search function — find all values matching pattern."""

    def test_search_simple_string_pattern(self):
        """search finds string values matching pattern."""
        mapping = {
            "name": "Lead Drums",
            "description": "punchy drum kit"
        }
        matches = search(mapping, r"drum")
        assert len(matches) == 2
        matched_paths = [m.path for m in matches]
        assert "name" in matched_paths
        assert "description" in matched_paths

    def test_search_numeric_pattern(self):
        """search finds numeric values matching pattern."""
        mapping = {
            "buttons": {
                "0": 60,
                "1": 72,
                "2": 120
            }
        }
        matches = search(mapping, r"^6")
        assert len(matches) == 1
        assert matches[0].path == "buttons.0"
        assert matches[0].value == 60

    def test_search_ignore_case_true(self):
        """search with ignore_case=True matches case-insensitively."""
        mapping = {"name": "DRUMS", "note": "Drum Kit"}
        matches = search(mapping, r"drum", ignore_case=True)
        assert len(matches) == 2

    def test_search_ignore_case_false(self):
        """search with ignore_case=False matches exactly."""
        mapping = {"name": "DRUMS", "note": "Drums Kit"}
        matches = search(mapping, r"Drums", ignore_case=False)
        assert len(matches) == 1
        assert matches[0].path == "note"

    def test_search_complex_nested(self):
        """search finds values in nested structures."""
        mapping = {
            "buttons": {
                "0": 60,
                "1": 62
            },
            "axes": {
                "0": 7,
                "1": 8
            }
        }
        matches = search(mapping, r"^7$")
        assert len(matches) == 1
        assert matches[0].path == "axes.0"

    def test_search_empty_mapping(self):
        """search on empty mapping returns empty list."""
        matches = search({}, r"anything")
        assert matches == []

    def test_search_invalid_pattern_raises(self):
        """search raises re.error on invalid pattern."""
        mapping = {"name": "Test"}
        with pytest.raises(Exception):  # re.error
            search(mapping, r"[invalid(")

    def test_search_matched_text_captured(self):
        """search captures the matched text."""
        mapping = {"description": "CC74 modulation wheel"}
        matches = search(mapping, r"CC\d+")
        assert len(matches) == 1
        assert matches[0].matched_text == "CC74"

    def test_search_list_values(self):
        """search finds values in lists."""
        mapping = {
            "notes": [60, 62, 64]
        }
        matches = search(mapping, r"62")
        assert len(matches) == 1
        assert matches[0].path == "notes[1]"
        assert matches[0].value == 62


class TestSearchKeys:
    """search_keys function — find paths whose leaf key matches pattern."""

    def test_search_keys_simple_match(self):
        """search_keys finds matching key names."""
        mapping = {
            "name": "Lead",
            "description": "description text",
            "midi_channel": 0,
            "midi_note": 60
        }
        matches = search_keys(mapping, r"midi")
        assert len(matches) == 2
        assert "midi_channel" in matches
        assert "midi_note" in matches

    def test_search_keys_nested(self):
        """search_keys finds matching keys in nested structures."""
        mapping = {
            "buttons": {
                "0": 60,
                "1": 62
            },
            "axes": {
                "0": 7
            }
        }
        matches = search_keys(mapping, r"^0$")
        assert len(matches) == 2
        matched_text = sorted(matches)
        assert "buttons.0" in matched_text
        assert "axes.0" in matched_text

    def test_search_keys_list_index(self):
        """search_keys handles list indices."""
        mapping = {
            "notes": [60, 62, 64]
        }
        matches = search_keys(mapping, r"notes")
        assert len(matches) == 3
        # Each element has path like "notes[0]", "notes[1]", etc.
        # But key_filter extracts final key before [, which is "notes"
        assert all("notes" in m for m in matches)

    def test_search_keys_ignore_case(self):
        """search_keys respects ignore_case."""
        mapping = {
            "NAME": "Test",
            "description": "Test"
        }
        matches_case_insensitive = search_keys(mapping, r"name", ignore_case=True)
        assert len(matches_case_insensitive) == 1
        assert "NAME" in matches_case_insensitive

        matches_case_sensitive = search_keys(mapping, r"name", ignore_case=False)
        assert len(matches_case_sensitive) == 0

    def test_search_keys_empty_mapping(self):
        """search_keys on empty mapping returns empty list."""
        matches = search_keys({}, r"anything")
        assert matches == []


class TestSearchValuesOnly:
    """search_values_only function — search values with optional type filter."""

    def test_search_values_only_strings(self):
        """search_values_only with value_type=str filters to strings."""
        mapping = {
            "name": "Drum Kit",
            "velocity": 100,
            "description": "drum sound"
        }
        matches = search_values_only(mapping, r"drum", value_type=str)
        assert len(matches) == 2
        matched_paths = [m.path for m in matches]
        assert "name" in matched_paths
        assert "description" in matched_paths

    def test_search_values_only_ints(self):
        """search_values_only with value_type=int filters to ints."""
        mapping = {
            "name": "Drums",
            "velocity": 100,
            "volume": 127
        }
        matches = search_values_only(mapping, r"^10", value_type=int)
        assert len(matches) == 1
        assert matches[0].path == "velocity"
        assert matches[0].value == 100

    def test_search_values_only_no_type_filter(self):
        """search_values_only without type filter searches all values."""
        mapping = {
            "name": "Drums",
            "note": 60,
            "velocity": 100
        }
        matches = search_values_only(mapping, r"^60|^100")
        assert len(matches) == 2

    def test_search_values_only_empty_mapping(self):
        """search_values_only on empty mapping returns empty list."""
        matches = search_values_only({}, r"anything")
        assert matches == []

    def test_search_values_only_invalid_pattern_raises(self):
        """search_values_only raises re.error on invalid pattern."""
        mapping = {"name": "Test"}
        with pytest.raises(Exception):  # re.error
            search_values_only(mapping, r"[invalid(")


class TestReplace:
    """replace function — replace string values non-mutating."""

    def test_replace_simple_strings(self):
        """replace updates matching string values."""
        mapping = {
            "name": "Lead Drums",
            "description": "punchy drum kit"
        }
        new_mapping, count = replace(mapping, r"[Dd]rums?", "DRUM")
        assert count == 2
        assert new_mapping["name"] == "Lead DRUM"
        assert new_mapping["description"] == "punchy DRUM kit"

    def test_replace_non_mutating(self):
        """replace doesn't mutate input mapping."""
        mapping = {
            "name": "Lead Drums",
            "description": "punchy drum kit"
        }
        original_name = mapping["name"]
        new_mapping, _ = replace(mapping, r"drum", "DRUM")
        assert mapping["name"] == original_name
        assert new_mapping["name"] != original_name

    def test_replace_ignores_non_string_values(self):
        """replace doesn't touch int/float/bool leaves."""
        mapping = {
            "name": "Drums",
            "velocity": 100,
            "enabled": True,
            "pan": 0.5
        }
        new_mapping, count = replace(mapping, r"\d", "X")
        # Only the string "Drums" contains digits (none, actually)
        # But velocity (100) is int, so it's not replaced
        assert new_mapping["velocity"] == 100
        assert new_mapping["enabled"] is True
        assert new_mapping["pan"] == 0.5
        assert count == 0

    def test_replace_with_backreferences(self):
        """replace supports backreferences in replacement."""
        mapping = {
            "name": "CC74",
            "description": "CC7 and CC74"
        }
        new_mapping, count = replace(mapping, r"CC(\d+)", r"CC[\1]")
        assert count == 2  # Two values changed (name and description)
        assert new_mapping["name"] == "CC[74]"

    def test_replace_case_insensitive(self):
        """replace with ignore_case=True."""
        mapping = {
            "name": "DRUM Kit",
            "note": "drum sound"
        }
        new_mapping, count = replace(
            mapping, r"drum", "bass", ignore_case=True
        )
        assert count == 2
        assert new_mapping["name"] == "bass Kit"
        assert new_mapping["note"] == "bass sound"

    def test_replace_case_sensitive(self):
        """replace with ignore_case=False."""
        mapping = {
            "name": "DRUM Kit",
            "note": "drum sound"
        }
        new_mapping, count = replace(
            mapping, r"drum", "bass", ignore_case=False
        )
        assert count == 1
        assert new_mapping["name"] == "DRUM Kit"
        assert new_mapping["note"] == "bass sound"

    def test_replace_nested_structures(self):
        """replace handles nested dicts and lists."""
        mapping = {
            "buttons": {
                "0": "drum 1",
                "1": "drum 2"
            },
            "notes": ["drum 3", "drum 4"]
        }
        new_mapping, count = replace(mapping, r"drum", "kick")
        assert count == 4
        assert new_mapping["buttons"]["0"] == "kick 1"
        assert new_mapping["buttons"]["1"] == "kick 2"
        assert new_mapping["notes"][0] == "kick 3"
        assert new_mapping["notes"][1] == "kick 4"

    def test_replace_returns_count(self):
        """replace returns correct replacement count."""
        mapping = {
            "name": "CC74 CC74",
            "note": "No matches here"
        }
        new_mapping, count = replace(mapping, r"CC74", "CC75")
        assert count == 1  # Only one value changed (name)
        # But name has 2 occurrences of CC74
        assert new_mapping["name"] == "CC75 CC75"

    def test_replace_empty_mapping(self):
        """replace on empty mapping returns empty dict and 0."""
        new_mapping, count = replace({}, r"anything", "replacement")
        assert new_mapping == {}
        assert count == 0

    def test_replace_no_matches(self):
        """replace with no matches returns unchanged copy."""
        mapping = {
            "name": "Lead Synth"
        }
        new_mapping, count = replace(mapping, r"drum", "kick")
        assert count == 0
        assert new_mapping == mapping
        assert new_mapping is not mapping  # Non-mutating

    def test_replace_invalid_pattern_raises(self):
        """replace raises re.error on invalid pattern."""
        mapping = {"name": "Test"}
        with pytest.raises(Exception):  # re.error
            replace(mapping, r"[invalid(", "replacement")


class TestIntegration:
    """Integration tests with realistic mapping structures."""

    def test_marketplace_audit_find_all_cc74(self):
        """Find all macros that touch CC74 (marketplace audit use case)."""
        mapping = {
            "name": "Advanced Kit",
            "description": "Uses CC74 for dynamics",
            "axes": {
                "0": 7,
                "1": 74
            },
            "macros": [
                {"name": "CC74 Swell", "cc": 74},
                {"name": "Velocity Map", "cc": 7},
            ]
        }
        matches = search(mapping, r"74")
        assert len(matches) >= 2
        # Should find: axes.1 (74), macros[0].cc (74), and possibly description text

    def test_user_search_find_chord_progression(self):
        """User search: find all values with 'chord' in key name."""
        mapping = {
            "left_stick": {
                "chord_north": [60, 64, 67],
                "chord_east": [62, 66, 69],
            },
            "right_stick": {
                "chord_north": [65, 69, 72],
            },
            "chords_version": 2
        }
        chord_paths = search_keys(mapping, r"chord")
        assert len(chord_paths) >= 3
        assert any("chord_north" in p for p in chord_paths)
        assert any("chord_east" in p for p in chord_paths)

    def test_bulk_rename_mapping_values(self):
        """Bulk rename: update all "drum" references to "kick"."""
        mapping = {
            "name": "Drum Kit",
            "description": "punchy drum sounds",
            "buttons": {
                "0": "drum 1",
                "1": "drum 2"
            }
        }
        new_mapping, count = replace(mapping, r"[Dd]rum", "kick")
        assert count == 4  # Four values changed (name, description, buttons.0, buttons.1)
        assert "drum" not in new_mapping["name"]
        assert "drum" not in new_mapping["description"]
        assert "drum" not in new_mapping["buttons"]["0"]
