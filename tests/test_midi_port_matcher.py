"""
Tests for MIDI port matcher module.
"""

import pytest
from gamepad_midi_bridge.midi_port_matcher import (
    normalize_name,
    score_match,
    find_best_match,
    find_all_matches,
    glob_match,
    PortPreference,
    resolve_port,
)


class TestNormalizeName:
    """Test name normalization."""

    def test_lowercase(self):
        """Should convert to lowercase."""
        assert normalize_name("Ableton Live") == "ableton live"
        assert normalize_name("MIDI CONTROLLER") == "midi controller"

    def test_strip_whitespace(self):
        """Should strip leading and trailing whitespace."""
        assert normalize_name("  Ableton  ") == "ableton"
        assert normalize_name("\t Device \n") == "device"

    def test_remove_port_index_parentheses(self):
        """Should remove port index notation like (0), (1)."""
        assert normalize_name("Ableton Live MIDI (1)") == "ableton live"
        assert normalize_name("Device (0)") == "device"
        assert normalize_name("Some Port (42)") == "some port"

    def test_remove_port_index_space_number(self):
        """Should remove port index notation like ' 1', ' 2'."""
        assert normalize_name("IAC Driver Bus 1") == "iac driver bus"
        assert normalize_name("CME WIDI 2") == "cme widi"

    def test_remove_midi_suffix(self):
        """Should remove 'MIDI' suffix if present at end."""
        assert normalize_name("Controller MIDI") == "controller"
        assert normalize_name("Device MIDI") == "device"
        # But not if it's in the middle
        assert normalize_name("MIDI Controller") == "midi controller"

    def test_collapse_multiple_spaces(self):
        """Should collapse multiple spaces to single space."""
        assert normalize_name("Device  Name   Here") == "device name here"

    def test_combined_normalization(self):
        """Test combined normalization."""
        assert normalize_name("  Ableton Live MIDI (1)  ") == "ableton live"


class TestScoreMatch:
    """Test match scoring."""

    def test_exact_match(self):
        """Exact case-insensitive match should return 1.0."""
        assert score_match("Ableton", "Ableton") == 1.0
        assert score_match("ableton", "ABLETON") == 1.0
        assert score_match("Test", "test") == 1.0

    def test_normalized_exact_match(self):
        """Normalized exact match should return 0.95."""
        assert (
            score_match("Ableton Live (1)", "Ableton Live (2)") == 0.95
        )
        assert score_match("Device 1", "Device 2") == 0.95

    def test_substring_match(self):
        """Substring match should return 0.7."""
        score = score_match("ableton", "Ableton Live 12")
        assert score == 0.7

        score = score_match("Ableton Live 12", "ableton")
        assert score == 0.7

    def test_normalized_substring_match(self):
        """Substring of normalized should return 0.65."""
        # After normalization, "device 1" → "device" and "device interface 2" → "device interface"
        score = score_match("device 1", "device interface 2")
        assert score == 0.65

    def test_token_overlap(self):
        """Token overlap (Jaccard) should return 0.0..0.5."""
        # One token in common out of two union
        score = score_match("device controller", "device interface")
        assert 0.0 <= score <= 0.5

    def test_no_overlap(self):
        """No overlap should return 0.0."""
        assert score_match("xyz", "abc") == 0.0
        assert score_match("apple", "banana") == 0.0


class TestFindBestMatch:
    """Test finding the best-matching candidate."""

    def test_returns_top_candidate(self):
        """Should return the highest-scoring candidate."""
        ports = ["IAC Driver Bus 1", "Ableton Live 12", "CME WIDI Master"]
        best = find_best_match("ableton", ports)
        assert best == "Ableton Live 12"

    def test_returns_none_when_no_match(self):
        """Should return None when all scores below min_score."""
        ports = ["Device A", "Device B"]
        best = find_best_match("xyz", ports, min_score=0.5)
        assert best is None

    def test_respects_min_score_threshold(self):
        """Should respect min_score threshold."""
        ports = ["Test Device", "Another Device"]
        # "test" should match "Test Device" with substring score ~0.7
        best = find_best_match("test", ports, min_score=0.8)
        assert best is None
        # But with lower threshold should find it
        best = find_best_match("test", ports, min_score=0.5)
        assert best == "Test Device"

    def test_empty_candidates(self):
        """Should return None for empty candidate list."""
        assert find_best_match("query", []) is None


class TestFindAllMatches:
    """Test finding all matching candidates."""

    def test_returns_sorted_by_score_descending(self):
        """Results should be sorted by score descending."""
        ports = ["Device", "Device MIDI", "Another"]
        matches = find_all_matches("device", ports, min_score=0.5)
        # First should be highest score
        assert len(matches) >= 1
        if len(matches) > 1:
            assert matches[0][1] >= matches[1][1]

    def test_respects_min_score(self):
        """Should only return candidates above min_score."""
        ports = ["Exact", "Nearly Close", "Completely Different"]
        matches = find_all_matches("exact", ports, min_score=0.95)
        # Only the exact match should be included
        assert len(matches) == 1
        assert matches[0][0] == "Exact"

    def test_includes_score_in_results(self):
        """Results should include (candidate, score) tuples."""
        ports = ["Test Device"]
        matches = find_all_matches("test", ports, min_score=0.5)
        assert len(matches) >= 1
        assert isinstance(matches[0], tuple)
        assert len(matches[0]) == 2
        assert isinstance(matches[0][0], str)
        assert isinstance(matches[0][1], float)


class TestGlobMatch:
    """Test glob pattern matching."""

    def test_glob_match_asterisk(self):
        """Should match glob patterns with asterisks."""
        ports = [
            "IAC Driver Bus 1",
            "Ableton Live 12",
            "CME WIDI Master",
        ]
        matches = glob_match("*ableton*", ports)
        assert "Ableton Live 12" in matches

    def test_glob_match_case_insensitive(self):
        """Glob matching should be case-insensitive."""
        ports = ["Ableton Live 12", "Ableton Live 11"]
        matches = glob_match("*ABLETON*", ports)
        assert len(matches) == 2

    def test_glob_match_no_matches(self):
        """Should return empty list for no matches."""
        ports = ["Device A", "Device B"]
        matches = glob_match("*xyz*", ports)
        assert matches == []

    def test_glob_match_widi(self):
        """Should match WIDI pattern."""
        ports = ["IAC Driver Bus 1", "CME WIDI Master", "Ableton Live"]
        matches = glob_match("*widi*", ports)
        assert matches == ["CME WIDI Master"]


class TestPortPreference:
    """Test PortPreference dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        pref = PortPreference("test")
        assert pref.name_fragment == "test"
        assert pref.min_score == 0.5
        assert pref.fallback_to_default is True

    def test_clamp_min_score_above_1(self):
        """Should clamp min_score to max 1.0."""
        pref = PortPreference("test", min_score=1.5)
        assert pref.min_score == 1.0

    def test_clamp_min_score_below_0(self):
        """Should clamp min_score to min 0.0."""
        pref = PortPreference("test", min_score=-0.5)
        assert pref.min_score == 0.0

    def test_to_dict(self):
        """Should serialize to dict."""
        pref = PortPreference("query", min_score=0.7, fallback_to_default=False)
        d = pref.to_dict()
        assert d["name_fragment"] == "query"
        assert d["min_score"] == 0.7
        assert d["fallback_to_default"] is False

    def test_from_dict(self):
        """Should deserialize from dict."""
        d = {
            "name_fragment": "ableton",
            "min_score": 0.8,
            "fallback_to_default": False,
        }
        pref = PortPreference.from_dict(d)
        assert pref.name_fragment == "ableton"
        assert pref.min_score == 0.8
        assert pref.fallback_to_default is False

    def test_round_trip_serialization(self):
        """Should survive round-trip serialization."""
        original = PortPreference("device", min_score=0.6, fallback_to_default=True)
        d = original.to_dict()
        restored = PortPreference.from_dict(d)
        assert restored.name_fragment == original.name_fragment
        assert restored.min_score == original.min_score
        assert restored.fallback_to_default == original.fallback_to_default


class TestResolvePort:
    """Test port preference resolution."""

    def test_returns_best_match(self):
        """Should return best match for preference."""
        ports = ["IAC Driver Bus 1", "Ableton Live 12", "CME WIDI Master"]
        pref = PortPreference("ableton")
        result = resolve_port(pref, ports)
        assert result == "Ableton Live 12"

    def test_fallback_to_default_enabled(self):
        """When fallback enabled and no match, should return first port."""
        ports = ["Device A", "Device B", "Device C"]
        pref = PortPreference("xyz", fallback_to_default=True)
        result = resolve_port(pref, ports)
        assert result == "Device A"

    def test_fallback_to_default_disabled(self):
        """When fallback disabled and no match, should return None."""
        ports = ["Device A", "Device B"]
        pref = PortPreference("xyz", fallback_to_default=False)
        result = resolve_port(pref, ports)
        assert result is None

    def test_empty_available_ports(self):
        """Should return None for empty available list."""
        pref = PortPreference("test")
        result = resolve_port(pref, [])
        assert result is None

    def test_prefers_match_over_fallback(self):
        """Should prefer actual match even if fallback is enabled."""
        ports = ["First Port", "Ableton Live 12", "Third Port"]
        pref = PortPreference("ableton", fallback_to_default=True)
        result = resolve_port(pref, ports)
        assert result == "Ableton Live 12"
        assert result != "First Port"
