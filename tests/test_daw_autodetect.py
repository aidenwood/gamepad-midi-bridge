"""Tests for DAW autodetection from MIDI port names.

Pure stdlib module for scoring MIDI port names against known DAW keywords.
No Qt, no rtmidi.
"""
from __future__ import annotations

import pytest


class TestScoreDaw:
    """score_daw — confidence scoring for a single DAW."""

    def test_score_daw_empty_port_list(self):
        """Empty port list returns (0.0, None)."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("ableton", [])
        assert confidence == 0.0
        assert port is None

    def test_score_daw_exact_match(self):
        """Exact match of port name to keyword → 1.0 confidence."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("ableton", ["ableton"])
        assert confidence == 1.0
        assert port == "ableton"

    def test_score_daw_exact_match_case_insensitive(self):
        """Exact match is case-insensitive."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("ableton", ["ABLETON"])
        assert confidence == 1.0
        assert port == "ABLETON"

    def test_score_daw_substring_match(self):
        """Keyword as substring → 0.8 confidence."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("ableton", ["Ableton Live 12"])
        assert confidence == 0.8
        assert port == "Ableton Live 12"

    def test_score_daw_fl_studio(self):
        """FL Studio detection from port name."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("fl_studio", ["FL Studio Output"])
        assert confidence == 0.8
        assert port == "FL Studio Output"

    def test_score_daw_bitwig(self):
        """Bitwig detection from port name."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("bitwig", ["Bitwig Studio"])
        assert confidence == 0.8
        assert port == "Bitwig Studio"

    def test_score_daw_no_match(self):
        """No keyword match → (0.0, None)."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("ableton", ["Some Random Port"])
        assert confidence == 0.0
        assert port is None

    def test_score_daw_multiple_ports_picks_best(self):
        """Multiple ports: returns best-matching port."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        # "Ableton Live 12" should score 0.8 (substring match)
        # "Some Other Port" should score 0.0
        confidence, port = score_daw("ableton", ["Some Other Port", "Ableton Live 12"])
        assert confidence == 0.8
        assert port == "Ableton Live 12"

    def test_score_daw_logic_iac(self):
        """Logic Pro detection from IAC driver hint."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("logic", ["IAC Driver Bus 1"])
        assert confidence == 0.8
        assert port == "IAC Driver Bus 1"

    def test_score_daw_unknown_slug(self):
        """Unknown DAW slug returns (0.0, None)."""
        from gamepad_midi_bridge.daw_autodetect import score_daw

        confidence, port = score_daw("unknown_daw", ["Some Port"])
        assert confidence == 0.0
        assert port is None


class TestDetect:
    """detect — score all DAWs and return sorted results."""

    def test_detect_empty_ports(self):
        """Empty port list returns empty detection list."""
        from gamepad_midi_bridge.daw_autodetect import detect

        results = detect([])
        assert results == []

    def test_detect_single_daw(self):
        """Single matching DAW in port list."""
        from gamepad_midi_bridge.daw_autodetect import detect

        results = detect(["Ableton Live 12"])
        assert len(results) >= 1
        assert results[0].daw_slug == "ableton"
        assert results[0].confidence == 0.8

    def test_detect_multiple_daws(self):
        """Multiple DAWs in port list: sorted by confidence descending."""
        from gamepad_midi_bridge.daw_autodetect import detect

        results = detect(["Ableton Live 12", "FL Studio Output", "Bitwig Studio"])
        assert len(results) >= 3

        # All three should be present
        slugs = {r.daw_slug for r in results}
        assert "ableton" in slugs
        assert "fl_studio" in slugs
        assert "bitwig" in slugs

        # Sorted by confidence descending
        for i in range(len(results) - 1):
            assert results[i].confidence >= results[i + 1].confidence

    def test_detect_no_match(self):
        """No matching DAWs returns empty list."""
        from gamepad_midi_bridge.daw_autodetect import detect

        results = detect(["Unknown Port 1", "Mystery Port 2"])
        assert results == []

    def test_detect_case_insensitive(self):
        """Detection is case-insensitive."""
        from gamepad_midi_bridge.daw_autodetect import detect

        results = detect(["ableton live 12"])
        assert len(results) >= 1
        assert results[0].daw_slug == "ableton"


class TestBestGuess:
    """best_guess — return top DAW if above confidence threshold."""

    def test_best_guess_high_confidence(self):
        """Single high-confidence match returns DawDetection."""
        from gamepad_midi_bridge.daw_autodetect import best_guess

        result = best_guess(["Ableton Live 12"], min_confidence=0.3)
        assert result is not None
        assert result.daw_slug == "ableton"
        assert result.confidence >= 0.3

    def test_best_guess_below_threshold(self):
        """No match above threshold returns None."""
        from gamepad_midi_bridge.daw_autodetect import best_guess

        result = best_guess(["Some Random Port"], min_confidence=0.5)
        assert result is None

    def test_best_guess_multiple_daws_picks_best(self):
        """Multiple DAWs: returns highest-confidence match."""
        from gamepad_midi_bridge.daw_autodetect import best_guess

        result = best_guess(
            ["Some Port", "Ableton Live 12", "FL Studio"], min_confidence=0.3
        )
        assert result is not None
        # At least Ableton and FL Studio should match
        assert result.daw_slug in {"ableton", "fl_studio"}

    def test_best_guess_min_confidence_clamped(self):
        """min_confidence is clamped to [0.0, 1.0]."""
        from gamepad_midi_bridge.daw_autodetect import best_guess

        # Negative min_confidence clamped to 0.0
        result = best_guess(["Ableton Live 12"], min_confidence=-0.5)
        assert result is not None
        assert result.daw_slug == "ableton"

        # Over 1.0 clamped to 1.0 (should find nothing)
        result = best_guess(["Ableton Live 12"], min_confidence=1.5)
        assert result is None

    def test_best_guess_empty_ports(self):
        """Empty port list returns None."""
        from gamepad_midi_bridge.daw_autodetect import best_guess

        result = best_guess([], min_confidence=0.3)
        assert result is None


class TestDawDisplayName:
    """daw_display_name — get human-readable names for DAW slugs."""

    def test_daw_display_name_ableton(self):
        """Ableton slug → "Ableton Live"."""
        from gamepad_midi_bridge.daw_autodetect import daw_display_name

        assert daw_display_name("ableton") == "Ableton Live"

    def test_daw_display_name_fl_studio(self):
        """FL Studio slug → "FL Studio"."""
        from gamepad_midi_bridge.daw_autodetect import daw_display_name

        assert daw_display_name("fl_studio") == "FL Studio"

    def test_daw_display_name_all_defined(self):
        """All standard DAW slugs have display names."""
        from gamepad_midi_bridge.daw_autodetect import (
            daw_display_name,
            DAW_HINTS,
        )

        for slug in DAW_HINTS:
            name = daw_display_name(slug)
            assert isinstance(name, str)
            assert len(name) > 0
            # Should not be the raw slug uppercased (except for special handling)
            assert name != slug.upper()

    def test_daw_display_name_unknown(self):
        """Unknown slug returns uppercased slug with underscore→space."""
        from gamepad_midi_bridge.daw_autodetect import daw_display_name

        assert daw_display_name("unknown_daw") == "UNKNOWN DAW"


class TestDawDetection:
    """DawDetection — dataclass with serialization."""

    def test_daw_detection_to_dict(self):
        """to_dict() serializes all fields."""
        from gamepad_midi_bridge.daw_autodetect import DawDetection

        detection = DawDetection(
            daw_slug="ableton",
            display_name="Ableton Live",
            confidence=0.8,
            matched_port="Ableton Live 12",
        )
        d = detection.to_dict()
        assert d["daw_slug"] == "ableton"
        assert d["display_name"] == "Ableton Live"
        assert d["confidence"] == 0.8
        assert d["matched_port"] == "Ableton Live 12"

    def test_daw_detection_from_dict(self):
        """from_dict() deserializes correctly."""
        from gamepad_midi_bridge.daw_autodetect import DawDetection

        data = {
            "daw_slug": "ableton",
            "display_name": "Ableton Live",
            "confidence": 0.8,
            "matched_port": "Ableton Live 12",
        }
        detection = DawDetection.from_dict(data)
        assert detection.daw_slug == "ableton"
        assert detection.display_name == "Ableton Live"
        assert detection.confidence == 0.8
        assert detection.matched_port == "Ableton Live 12"

    def test_daw_detection_round_trip(self):
        """Round-trip serialization preserves data."""
        from gamepad_midi_bridge.daw_autodetect import DawDetection

        original = DawDetection(
            daw_slug="fl_studio",
            display_name="FL Studio",
            confidence=0.9,
            matched_port="FL Studio Output",
        )
        serialized = original.to_dict()
        restored = DawDetection.from_dict(serialized)

        assert restored.daw_slug == original.daw_slug
        assert restored.display_name == original.display_name
        assert restored.confidence == original.confidence
        assert restored.matched_port == original.matched_port

    def test_daw_detection_from_dict_missing_fields(self):
        """from_dict() uses sensible defaults for missing fields."""
        from gamepad_midi_bridge.daw_autodetect import DawDetection

        data = {"daw_slug": "ableton"}
        detection = DawDetection.from_dict(data)
        assert detection.daw_slug == "ableton"
        assert detection.display_name == "Unknown"
        assert detection.confidence == 0.0
        assert detection.matched_port is None
