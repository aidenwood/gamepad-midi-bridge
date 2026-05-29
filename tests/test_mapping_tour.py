"""Test suite for mapping_tour module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_tour import (
    TourStep,
    build_tour,
    format_step,
    tour_text,
    step_count_estimate,
)


class TestTourStep:
    """Test TourStep dataclass and serialization."""

    def test_tour_step_creation(self):
        """TourStep can be created with required fields."""
        step = TourStep(
            feature="L2 Trigger",
            description="L2 drives two CCs in opposition",
            target_path="l2_trigger.crossfade_enabled",
        )
        assert step.feature == "L2 Trigger"
        assert step.description == "L2 drives two CCs in opposition"
        assert step.target_path == "l2_trigger.crossfade_enabled"
        assert step.priority == 0

    def test_tour_step_with_priority(self):
        """TourStep accepts custom priority."""
        step = TourStep(
            feature="L2 Trigger",
            description="test",
            target_path="l2_trigger",
            priority=90,
        )
        assert step.priority == 90

    def test_tour_step_to_dict(self):
        """TourStep.to_dict() serializes all fields."""
        step = TourStep(
            feature="L2 Trigger",
            description="L2 drives two CCs in opposition",
            target_path="l2_trigger.crossfade_enabled",
            priority=90,
        )
        data = step.to_dict()
        assert data["feature"] == "L2 Trigger"
        assert data["description"] == "L2 drives two CCs in opposition"
        assert data["target_path"] == "l2_trigger.crossfade_enabled"
        assert data["priority"] == 90

    def test_tour_step_from_dict(self):
        """TourStep.from_dict() deserializes correctly."""
        data = {
            "feature": "L2 Trigger",
            "description": "L2 drives two CCs in opposition",
            "target_path": "l2_trigger.crossfade_enabled",
            "priority": 90,
        }
        step = TourStep.from_dict(data)
        assert step.feature == "L2 Trigger"
        assert step.description == "L2 drives two CCs in opposition"
        assert step.target_path == "l2_trigger.crossfade_enabled"
        assert step.priority == 90

    def test_tour_step_round_trip(self):
        """TourStep serialization and deserialization round-trip."""
        original = TourStep(
            feature="Bow Mode",
            description="L2 movement velocity drives expression",
            target_path="l2_trigger.bow_mode",
            priority=85,
        )
        data = original.to_dict()
        restored = TourStep.from_dict(data)
        assert restored.feature == original.feature
        assert restored.description == original.description
        assert restored.target_path == original.target_path
        assert restored.priority == original.priority


class TestBuildTour:
    """Test build_tour function."""

    def test_empty_mapping_returns_empty_list(self):
        """Empty mapping dict returns empty list."""
        result = build_tour({})
        assert result == []

    def test_mapping_with_crossfade_trigger(self):
        """Mapping with L2 crossfade enabled includes L2 Trigger step."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True, "crossfade_cc_b": 11},
        }
        result = build_tour(mapping)
        assert len(result) >= 1
        crossfade_steps = [s for s in result if "Crossfade" in s.feature]
        assert len(crossfade_steps) == 1
        assert crossfade_steps[0].feature == "L2 Trigger Crossfade"

    def test_mapping_with_r2_crossfade_trigger(self):
        """Mapping with R2 crossfade enabled includes R2 Trigger step."""
        mapping = {
            "r2_trigger": {"crossfade_enabled": True, "crossfade_cc_b": 11},
        }
        result = build_tour(mapping)
        crossfade_steps = [s for s in result if "Crossfade" in s.feature]
        assert len(crossfade_steps) == 1
        assert crossfade_steps[0].feature == "R2 Trigger Crossfade"

    def test_mapping_with_bow_mode(self):
        """Mapping with L2 bow mode includes Bow Mode step."""
        mapping = {
            "l2_trigger": {"bow_mode": True, "bow_cc": 11},
        }
        result = build_tour(mapping)
        bow_steps = [s for s in result if "Bow Mode" in s.feature]
        assert len(bow_steps) == 1
        assert "L2" in bow_steps[0].feature

    def test_mapping_with_shift_layer(self):
        """Mapping with shift layer includes Shift Layer step."""
        mapping = {
            "shift_layer": {"shift_button": 7, "buttons": {}},
        }
        result = build_tour(mapping)
        shift_steps = [s for s in result if "Shift Layer" in s.feature]
        assert len(shift_steps) == 1

    def test_mapping_with_macros(self):
        """Mapping with macros includes Macro Bank step."""
        mapping = {
            "macros": {
                "macro_1": {"events": []},
                "macro_2": {"events": []},
            },
        }
        result = build_tour(mapping)
        macro_steps = [s for s in result if "Macro Bank" in s.feature]
        assert len(macro_steps) == 1
        assert "2 macro(s)" in macro_steps[0].description

    def test_mapping_with_all_features(self):
        """Mapping with all features returns multiple steps in priority order."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True},
            "left_stick": {"chord_mode": True},
            "shift_layer": {"shift_button": 7, "buttons": {}},
            "ab_compare_enabled": True,
            "macros": {"m1": {"events": []}},
            "buttons": {0: 60},
        }
        result = build_tour(mapping)
        # Should have: crossfade (90), chord (80), shift (75), ab (70), macros (65), buttons (10)
        assert len(result) >= 4
        # Priority should be descending
        for i in range(len(result) - 1):
            assert result[i].priority >= result[i + 1].priority

    def test_build_tour_respects_limit(self):
        """build_tour caps results at limit."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True},
            "left_stick": {"chord_mode": True},
            "shift_layer": {"shift_button": 7, "buttons": {}},
            "ab_compare_enabled": True,
            "macros": {"m1": {"events": []}},
        }
        result = build_tour(mapping, limit=2)
        assert len(result) <= 2

    def test_tour_steps_sorted_by_priority_descending(self):
        """Tour steps are sorted by priority (highest first)."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True},  # priority 90
            "left_stick": {"chord_mode": True},  # priority 80
            "shift_layer": {"shift_button": 7, "buttons": {}},  # priority 75
        }
        result = build_tour(mapping)
        assert len(result) >= 3
        priorities = [s.priority for s in result]
        assert priorities == sorted(priorities, reverse=True)

    def test_mapping_with_buttons_and_axes(self):
        """Mapping with basic buttons/axes includes Default Mappings step."""
        mapping = {
            "buttons": {0: 60, 1: 62},
            "axes": {0: 3, 1: 4},
        }
        result = build_tour(mapping)
        default_steps = [s for s in result if "Button & Axis Mappings" in s.feature]
        assert len(default_steps) == 1
        assert "2 button(s)" in default_steps[0].description
        assert "2 axis/CC stream(s)" in default_steps[0].description

    def test_mapping_with_stick_chord(self):
        """Mapping with left stick chord mode includes Stick Chord step."""
        mapping = {
            "left_stick": {"chord_mode": True},
        }
        result = build_tour(mapping)
        chord_steps = [s for s in result if "Stick Chord" in s.feature]
        assert len(chord_steps) == 1
        assert "Left Stick" in chord_steps[0].feature

    def test_mapping_with_right_stick_chord(self):
        """Mapping with right stick chord mode includes Stick Chord step."""
        mapping = {
            "right_stick": {"chord_mode": True},
        }
        result = build_tour(mapping)
        chord_steps = [s for s in result if "Stick Chord" in s.feature]
        assert len(chord_steps) == 1
        assert "Right Stick" in chord_steps[0].feature


class TestFormatStep:
    """Test format_step function."""

    def test_format_step_returns_non_empty_string(self):
        """format_step returns a non-empty string."""
        step = TourStep(
            feature="L2 Trigger",
            description="L2 drives two CCs in opposition",
            target_path="l2_trigger",
        )
        result = format_step(step)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_step_includes_feature_and_description(self):
        """format_step includes both feature and description."""
        step = TourStep(
            feature="L2 Trigger",
            description="L2 drives two CCs in opposition",
            target_path="l2_trigger",
        )
        result = format_step(step)
        assert "L2 Trigger" in result
        assert "opposition" in result


class TestTourText:
    """Test tour_text function."""

    def test_tour_text_empty_list(self):
        """tour_text with empty list returns empty string."""
        result = tour_text([])
        assert result == ""

    def test_tour_text_single_step(self):
        """tour_text with single step returns numbered entry."""
        step = TourStep(
            feature="L2 Trigger",
            description="L2 drives two CCs in opposition",
            target_path="l2_trigger",
        )
        result = tour_text([step])
        assert "1." in result
        assert "L2 Trigger" in result

    def test_tour_text_multiple_steps(self):
        """tour_text with multiple steps returns numbered list."""
        steps = [
            TourStep(
                feature="L2 Trigger",
                description="L2 drives two CCs",
                target_path="l2_trigger",
            ),
            TourStep(
                feature="Bow Mode",
                description="L2 movement velocity drives expression",
                target_path="l2_trigger.bow_mode",
            ),
        ]
        result = tour_text(steps)
        assert "1." in result
        assert "2." in result
        assert "L2 Trigger" in result
        assert "Bow Mode" in result

    def test_tour_text_is_multiline(self):
        """tour_text with multiple steps returns multiple lines."""
        steps = [
            TourStep(
                feature="L2 Trigger",
                description="test1",
                target_path="l2",
            ),
            TourStep(
                feature="Bow Mode",
                description="test2",
                target_path="bow",
            ),
        ]
        result = tour_text(steps)
        lines = result.split("\n")
        assert len(lines) == 2


class TestStepCountEstimate:
    """Test step_count_estimate function."""

    def test_empty_mapping_count_estimate(self):
        """Empty mapping returns 0 estimate."""
        result = step_count_estimate({})
        assert result == 0

    def test_count_estimate_single_feature(self):
        """Mapping with one feature returns 1 estimate."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True},
        }
        result = step_count_estimate(mapping)
        assert result == 1

    def test_count_estimate_matches_build_tour_without_cap(self):
        """step_count_estimate matches len(build_tour) when not capped."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True},
            "left_stick": {"chord_mode": True},
            "shift_layer": {"shift_button": 7, "buttons": {}},
            "ab_compare_enabled": True,
            "macros": {"m1": {"events": []}},
            "buttons": {0: 60},
        }
        estimate = step_count_estimate(mapping)
        steps = build_tour(mapping, limit=1000)  # high limit, won't cap
        assert estimate == len(steps)

    def test_count_estimate_with_multiple_features(self):
        """Mapping with multiple features returns correct count."""
        mapping = {
            "l2_trigger": {"bow_mode": True},
            "left_stick": {"chord_mode": True},
            "macros": {"m1": {"events": []}},
            "buttons": {0: 60},
        }
        result = step_count_estimate(mapping)
        # Should count: bow mode (85), chord (80), macros (65), buttons (10) = 4
        assert result == 4

    def test_count_estimate_with_midi_learn(self):
        """step_count_estimate includes MIDI learn bindings."""
        mapping = {
            "midi_learn": {
                "bindings": {
                    "binding_1": {},
                },
            },
        }
        result = step_count_estimate(mapping)
        assert result >= 1


class TestDefensiveAgainstMissingKeys:
    """Test that the module handles missing/unexpected keys gracefully."""

    def test_build_tour_missing_l2_trigger(self):
        """build_tour handles missing l2_trigger gracefully."""
        mapping = {
            "buttons": {0: 60},
        }
        result = build_tour(mapping)
        assert isinstance(result, list)

    def test_build_tour_missing_shift_layer(self):
        """build_tour handles missing shift_layer gracefully."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True},
        }
        result = build_tour(mapping)
        assert len(result) >= 1

    def test_build_tour_null_values(self):
        """build_tour handles None/null values gracefully."""
        mapping = {
            "l2_trigger": None,
            "buttons": None,
        }
        result = build_tour(mapping)
        assert isinstance(result, list)

    def test_step_count_estimate_missing_keys(self):
        """step_count_estimate handles missing keys gracefully."""
        mapping = {
            "l2_trigger": {"crossfade_enabled": True},
            "missing_key": "value",
        }
        result = step_count_estimate(mapping)
        assert isinstance(result, int)
        assert result >= 0


class TestFeatureDetection:
    """Test detection of individual features."""

    def test_detects_left_stick_polar_mode(self):
        """Detection of left stick in polar mode."""
        mapping = {
            "left_stick": {"mode": "polar"},
        }
        result = build_tour(mapping)
        polar_steps = [s for s in result if "Polar" in s.feature]
        assert len(polar_steps) == 1

    def test_detects_right_stick_polar_mode(self):
        """Detection of right stick in polar mode."""
        mapping = {
            "right_stick": {"mode": "polar"},
        }
        result = build_tour(mapping)
        polar_steps = [s for s in result if "Polar" in s.feature]
        assert len(polar_steps) == 1

    def test_detects_velocity_humanize(self):
        """Detection of velocity humanization."""
        mapping = {
            "humanize_enabled": True,
        }
        result = build_tour(mapping)
        humanize_steps = [s for s in result if "Velocity Humanize" in s.feature]
        assert len(humanize_steps) == 1

    def test_detects_lfo_left_stick(self):
        """Detection of left stick LFO."""
        mapping = {
            "left_stick": {"lfo": {"enabled": True}},
        }
        result = build_tour(mapping)
        lfo_steps = [s for s in result if "LFO" in s.feature]
        assert len(lfo_steps) == 1

    def test_detects_lfo_right_stick(self):
        """Detection of right stick LFO."""
        mapping = {
            "right_stick": {"lfo": {"enabled": True}},
        }
        result = build_tour(mapping)
        lfo_steps = [s for s in result if "LFO" in s.feature]
        assert len(lfo_steps) == 1

    def test_detects_note_repeat_buttons(self):
        """Detection of note repeat in button configs."""
        mapping = {
            "button_configs": {
                0: {"note_repeat_enabled": True},
            },
        }
        result = build_tour(mapping)
        repeat_steps = [s for s in result if "Note Repeat" in s.feature]
        assert len(repeat_steps) == 1

    def test_detects_drumroll_buttons(self):
        """Detection of drumroll in button configs."""
        mapping = {
            "button_configs": {
                0: {"drumroll_enabled": True},
            },
        }
        result = build_tour(mapping)
        drumroll_steps = [s for s in result if "Note Repeat" in s.feature]
        assert len(drumroll_steps) == 1

    def test_detects_ab_compare(self):
        """Detection of A/B compare."""
        mapping = {
            "ab_compare_enabled": True,
            "ab_compare_button": 5,
        }
        result = build_tour(mapping)
        ab_steps = [s for s in result if "A/B" in s.feature]
        assert len(ab_steps) == 1
