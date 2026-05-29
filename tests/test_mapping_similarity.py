"""Test suite for mapping_similarity module."""

import pytest
from gamepad_midi_bridge.mapping_similarity import (
    jaccard,
    note_set,
    cc_set,
    feature_flags,
    compute_similarity,
    similarity_breakdown,
    most_similar,
    is_clone,
)


class TestJaccard:
    """Test Jaccard similarity computation."""

    def test_jaccard_identical_sets(self):
        """Test that identical sets have similarity 1.0."""
        a = {1, 2, 3}
        b = {1, 2, 3}
        assert jaccard(a, b) == 1.0

    def test_jaccard_empty_sets(self):
        """Test that both empty sets have similarity 1.0."""
        assert jaccard(set(), set()) == 1.0

    def test_jaccard_disjoint_sets(self):
        """Test that completely different sets have similarity 0.0."""
        a = {1, 2}
        b = {3, 4}
        assert jaccard(a, b) == 0.0

    def test_jaccard_partial_overlap(self):
        """Test partial overlap: {1,2,3} and {2,3,4} → 0.5."""
        a = {1, 2, 3}
        b = {2, 3, 4}
        # Intersection: {2, 3} = 2
        # Union: {1, 2, 3, 4} = 4
        # Result: 2/4 = 0.5
        assert jaccard(a, b) == 0.5

    def test_jaccard_one_subset_of_other(self):
        """Test when one set is subset of another."""
        a = {1, 2}
        b = {1, 2, 3, 4}
        # Intersection: {1, 2} = 2
        # Union: {1, 2, 3, 4} = 4
        # Result: 2/4 = 0.5
        assert jaccard(a, b) == 0.5

    def test_jaccard_one_empty_one_not(self):
        """Test when one set is empty and one has elements."""
        a = set()
        b = {1, 2, 3}
        assert jaccard(a, b) == 0.0


class TestNoteSet:
    """Test note_set extraction."""

    def test_note_set_single_button(self):
        """Test extracting notes from a single button."""
        mapping = {"buttons": {0: {"note": 60, "channel": 0}}}
        result = note_set(mapping)
        assert result == {(0, 60, 0)}

    def test_note_set_multiple_buttons(self):
        """Test extracting notes from multiple buttons."""
        mapping = {
            "buttons": {
                0: {"note": 60, "channel": 0},
                1: {"note": 61, "channel": 0},
                2: {"note": 62, "channel": 1},
            }
        }
        result = note_set(mapping)
        assert result == {(0, 60, 0), (1, 61, 0), (2, 62, 1)}

    def test_note_set_string_button_indices(self):
        """Test that string button indices are converted to int."""
        mapping = {"buttons": {"0": {"note": 60, "channel": 0}}}
        result = note_set(mapping)
        assert result == {(0, 60, 0)}

    def test_note_set_ignores_buttons_without_notes(self):
        """Test that buttons without note field are ignored."""
        mapping = {
            "buttons": {
                0: {"note": 60, "channel": 0},
                1: {"velocity": 100},  # No note
            }
        }
        result = note_set(mapping)
        assert result == {(0, 60, 0)}

    def test_note_set_default_channel(self):
        """Test that missing channel defaults to 0."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = note_set(mapping)
        assert result == {(0, 60, 0)}

    def test_note_set_empty_buttons(self):
        """Test empty buttons section."""
        mapping = {"buttons": {}}
        result = note_set(mapping)
        assert result == set()

    def test_note_set_no_buttons_section(self):
        """Test mapping with no buttons section."""
        mapping = {"axes": {}}
        result = note_set(mapping)
        assert result == set()


class TestCcSet:
    """Test CC set extraction."""

    def test_cc_set_single_axis(self):
        """Test extracting CC from a single axis."""
        mapping = {"axes": {0: {"cc": 7, "channel": 0}}}
        result = cc_set(mapping)
        assert result == {(0, 7, 0)}

    def test_cc_set_multiple_axes(self):
        """Test extracting CCs from multiple axes."""
        mapping = {
            "axes": {
                0: {"cc": 7, "channel": 0},
                1: {"cc": 8, "channel": 0},
                2: {"cc": 9, "channel": 1},
            }
        }
        result = cc_set(mapping)
        assert result == {(0, 7, 0), (1, 8, 0), (2, 9, 1)}

    def test_cc_set_with_triggers(self):
        """Test extracting CCs from trigger section."""
        mapping = {
            "axes": {},
            "triggers": {
                "L2": {"cc": 11, "channel": 0},
                "R2": {"cc": 12, "channel": 0},
            },
        }
        result = cc_set(mapping)
        assert result == {("L2", 11, 0), ("R2", 12, 0)}

    def test_cc_set_axes_and_triggers(self):
        """Test extracting CCs from both axes and triggers."""
        mapping = {
            "axes": {0: {"cc": 7, "channel": 0}},
            "triggers": {"L2": {"cc": 11, "channel": 0}},
        }
        result = cc_set(mapping)
        assert result == {(0, 7, 0), ("L2", 11, 0)}

    def test_cc_set_string_axis_indices(self):
        """Test that string axis indices are converted to int when possible."""
        mapping = {"axes": {"0": {"cc": 7, "channel": 0}}}
        result = cc_set(mapping)
        assert result == {(0, 7, 0)}

    def test_cc_set_ignores_without_cc(self):
        """Test that axes without CC field are ignored."""
        mapping = {
            "axes": {
                0: {"cc": 7, "channel": 0},
                1: {"range": [0, 127]},  # No CC
            }
        }
        result = cc_set(mapping)
        assert result == {(0, 7, 0)}

    def test_cc_set_default_channel(self):
        """Test that missing channel defaults to 0."""
        mapping = {"axes": {0: {"cc": 7}}}
        result = cc_set(mapping)
        assert result == {(0, 7, 0)}

    def test_cc_set_empty_axes_and_triggers(self):
        """Test empty axes and triggers."""
        mapping = {"axes": {}, "triggers": {}}
        result = cc_set(mapping)
        assert result == set()

    def test_cc_set_no_axes_or_triggers(self):
        """Test mapping with no axes or triggers sections."""
        mapping = {"buttons": {}}
        result = cc_set(mapping)
        assert result == set()


class TestFeatureFlags:
    """Test feature flag extraction."""

    def test_feature_flags_shift_layer_enabled(self):
        """Test shift_layer feature detection."""
        mapping = {"shift_layer": {"enabled": True}}
        result = feature_flags(mapping)
        assert "shift_layer" in result

    def test_feature_flags_shift_layer_disabled(self):
        """Test shift_layer not included when disabled."""
        mapping = {"shift_layer": {"enabled": False}}
        result = feature_flags(mapping)
        assert "shift_layer" not in result

    def test_feature_flags_left_stick_corners(self):
        """Test left_stick_corners feature."""
        mapping = {"left_stick_corners": {"enabled": True}}
        result = feature_flags(mapping)
        assert "left_stick_corners" in result

    def test_feature_flags_right_stick_corners(self):
        """Test right_stick_corners feature."""
        mapping = {"right_stick_corners": {"enabled": True}}
        result = feature_flags(mapping)
        assert "right_stick_corners" in result

    def test_feature_flags_touchpad(self):
        """Test touchpad feature."""
        mapping = {"touchpad": {"enabled": True}}
        result = feature_flags(mapping)
        assert "touchpad" in result

    def test_feature_flags_osc_enabled(self):
        """Test OSC feature when enabled."""
        mapping = {"osc": {"enabled": True}}
        result = feature_flags(mapping)
        assert "osc" in result

    def test_feature_flags_osc_listen(self):
        """Test OSC feature when listen_enabled."""
        mapping = {"osc": {"enabled": False, "listen_enabled": True}}
        result = feature_flags(mapping)
        assert "osc" in result

    def test_feature_flags_stick_chord_left(self):
        """Test stick_chord_left feature."""
        mapping = {"left_stick": {"chord_enabled": True}}
        result = feature_flags(mapping)
        assert "stick_chord_left" in result

    def test_feature_flags_stick_chord_right(self):
        """Test stick_chord_right feature."""
        mapping = {"right_stick": {"chord_enabled": True}}
        result = feature_flags(mapping)
        assert "stick_chord_right" in result

    def test_feature_flags_stick_lfo_left(self):
        """Test stick_lfo_left feature."""
        mapping = {"left_stick": {"lfo": {"enabled": True}}}
        result = feature_flags(mapping)
        assert "stick_lfo_left" in result

    def test_feature_flags_stick_lfo_right(self):
        """Test stick_lfo_right feature."""
        mapping = {"right_stick": {"lfo": {"enabled": True}}}
        result = feature_flags(mapping)
        assert "stick_lfo_right" in result

    def test_feature_flags_trigger_crossfade_l2(self):
        """Test trigger_crossfade_L2 feature."""
        mapping = {"triggers": {"L2": {"crossfade_enabled": True}}}
        result = feature_flags(mapping)
        assert "trigger_crossfade_L2" in result

    def test_feature_flags_trigger_crossfade_r2(self):
        """Test trigger_crossfade_R2 feature."""
        mapping = {"triggers": {"R2": {"crossfade_enabled": True}}}
        result = feature_flags(mapping)
        assert "trigger_crossfade_R2" in result

    def test_feature_flags_macros(self):
        """Test macros feature."""
        mapping = {"macros": {"macro1": {}}}
        result = feature_flags(mapping)
        assert "macros" in result

    def test_feature_flags_macros_empty(self):
        """Test macros not included when empty."""
        mapping = {"macros": {}}
        result = feature_flags(mapping)
        assert "macros" not in result

    def test_feature_flags_haptic_input(self):
        """Test haptic_input feature."""
        mapping = {"haptic_input": [{"trigger": "L2"}]}
        result = feature_flags(mapping)
        assert "haptic_input" in result

    def test_feature_flags_haptic_input_empty(self):
        """Test haptic_input not included when empty."""
        mapping = {"haptic_input": []}
        result = feature_flags(mapping)
        assert "haptic_input" not in result

    def test_feature_flags_multiple_enabled(self):
        """Test multiple features enabled at once."""
        mapping = {
            "shift_layer": {"enabled": True},
            "osc": {"enabled": True},
            "left_stick": {"chord_enabled": True},
        }
        result = feature_flags(mapping)
        assert "shift_layer" in result
        assert "osc" in result
        assert "stick_chord_left" in result
        assert len(result) == 3

    def test_feature_flags_empty_mapping(self):
        """Test with empty mapping."""
        result = feature_flags({})
        assert isinstance(result, set)
        assert len(result) == 0


class TestComputeSimilarity:
    """Test overall similarity computation."""

    def test_compute_similarity_identical_mappings(self):
        """Test identical mappings have similarity 1.0."""
        mapping = {"buttons": {0: {"note": 60, "channel": 0}}}
        assert compute_similarity(mapping, mapping) == 1.0

    def test_compute_similarity_completely_different(self):
        """Test completely different mappings have similarity 0.0."""
        a = {"buttons": {0: {"note": 60, "channel": 0}}}
        b = {"buttons": {0: {"note": 64, "channel": 0}}}
        # Different notes, same structure → some overlap but not 1.0
        score = compute_similarity(a, b)
        assert 0.0 <= score <= 1.0
        # Different notes should give lower score
        assert score < 1.0

    def test_compute_similarity_empty_mappings(self):
        """Test two empty mappings have similarity 1.0."""
        a = {}
        b = {}
        assert compute_similarity(a, b) == 1.0

    def test_compute_similarity_with_custom_weights(self):
        """Test that custom weights affect result."""
        a = {
            "buttons": {0: {"note": 60, "channel": 0}},
            "axes": {0: {"cc": 7, "channel": 0}},
        }
        b = {
            "buttons": {0: {"note": 60, "channel": 0}},
            "axes": {0: {"cc": 8, "channel": 0}},  # Different CC
        }

        # With equal weights
        score1 = compute_similarity(a, b, weights={"notes": 1.0, "ccs": 1.0, "features": 0})
        # With notes-only weight
        score2 = compute_similarity(a, b, weights={"notes": 1.0, "ccs": 0, "features": 0})

        # Notes match perfectly, CCs differ → score1 should be lower than score2
        assert score2 > score1

    def test_compute_similarity_returns_0_to_1(self):
        """Test that similarity is always in [0, 1]."""
        a = {"buttons": {i: {"note": 60 + i, "channel": 0} for i in range(5)}}
        b = {"buttons": {i: {"note": 65 + i, "channel": 0} for i in range(5)}}

        score = compute_similarity(a, b)
        assert 0.0 <= score <= 1.0


class TestSimilarityBreakdown:
    """Test similarity breakdown by component."""

    def test_similarity_breakdown_returns_dict(self):
        """Test that breakdown returns a dict."""
        mapping = {"buttons": {0: {"note": 60, "channel": 0}}}
        result = similarity_breakdown(mapping, mapping)
        assert isinstance(result, dict)

    def test_similarity_breakdown_has_required_keys(self):
        """Test that breakdown includes all required keys."""
        a = {"buttons": {0: {"note": 60, "channel": 0}}}
        b = {"buttons": {0: {"note": 61, "channel": 0}}}
        result = similarity_breakdown(a, b)

        assert "notes" in result
        assert "ccs" in result
        assert "features" in result
        assert "overall" in result

    def test_similarity_breakdown_identical_mapping(self):
        """Test breakdown for identical mappings."""
        mapping = {
            "buttons": {0: {"note": 60, "channel": 0}},
            "axes": {0: {"cc": 7, "channel": 0}},
            "shift_layer": {"enabled": True},
        }
        result = similarity_breakdown(mapping, mapping)

        assert result["notes"] == 1.0
        assert result["ccs"] == 1.0
        assert result["features"] == 1.0
        assert result["overall"] == 1.0

    def test_similarity_breakdown_completely_different(self):
        """Test breakdown for completely different mappings."""
        a = {"buttons": {0: {"note": 60, "channel": 0}}}
        b = {"buttons": {1: {"note": 64, "channel": 0}}}
        result = similarity_breakdown(a, b)

        # Completely different buttons
        assert result["notes"] == 0.0
        assert result["ccs"] == 1.0  # Both have no CCs
        assert result["features"] == 1.0  # Both have no features
        # Overall should be weighted average
        assert result["overall"] < 1.0

    def test_similarity_breakdown_values_in_range(self):
        """Test that all values are in [0, 1]."""
        a = {"buttons": {0: {"note": 60, "channel": 0}}}
        b = {"axes": {0: {"cc": 7, "channel": 0}}}
        result = similarity_breakdown(a, b)

        for key in ["notes", "ccs", "features", "overall"]:
            assert 0.0 <= result[key] <= 1.0


class TestMostSimilar:
    """Test most_similar ranking."""

    def test_most_similar_returns_list(self):
        """Test that most_similar returns a list."""
        target = {"buttons": {0: {"note": 60, "channel": 0}}}
        candidates = [("c1", {"buttons": {0: {"note": 60, "channel": 0}}})]
        result = most_similar(target, candidates)
        assert isinstance(result, list)

    def test_most_similar_returns_tuples(self):
        """Test that results are (slug, score) tuples."""
        target = {"buttons": {0: {"note": 60, "channel": 0}}}
        candidates = [("c1", {"buttons": {0: {"note": 60, "channel": 0}}})]
        result = most_similar(target, candidates)
        assert len(result) == 1
        assert isinstance(result[0], tuple)
        assert len(result[0]) == 2

    def test_most_similar_sorted_descending(self):
        """Test that results are sorted by score descending."""
        target = {"buttons": {0: {"note": 60, "channel": 0}}}
        candidates = [
            ("c1", {"buttons": {0: {"note": 61, "channel": 0}}}),
            ("c2", {"buttons": {0: {"note": 60, "channel": 0}}}),  # Identical
            ("c3", {"buttons": {0: {"note": 64, "channel": 0}}}),
        ]
        result = most_similar(target, candidates, top_n=3)

        # c2 should be first (identical)
        assert result[0][0] == "c2"
        assert result[0][1] == 1.0

        # Remaining should be descending
        for i in range(len(result) - 1):
            assert result[i][1] >= result[i + 1][1]

    def test_most_similar_respects_top_n(self):
        """Test that top_n parameter limits results."""
        target = {"buttons": {0: {"note": 60, "channel": 0}}}
        candidates = [
            (f"c{i}", {"buttons": {i: {"note": 60 + i, "channel": 0}}})
            for i in range(10)
        ]
        result = most_similar(target, candidates, top_n=3)
        assert len(result) == 3

    def test_most_similar_top_n_default_5(self):
        """Test that default top_n is 5."""
        target = {"buttons": {0: {"note": 60, "channel": 0}}}
        candidates = [
            (f"c{i}", {"buttons": {0: {"note": 60 + i, "channel": 0}}})
            for i in range(10)
        ]
        result = most_similar(target, candidates)
        assert len(result) == 5

    def test_most_similar_fewer_candidates_than_top_n(self):
        """Test when fewer candidates than top_n."""
        target = {"buttons": {0: {"note": 60, "channel": 0}}}
        candidates = [
            ("c1", {"buttons": {0: {"note": 60, "channel": 0}}}),
            ("c2", {"buttons": {0: {"note": 61, "channel": 0}}}),
        ]
        result = most_similar(target, candidates, top_n=5)
        assert len(result) == 2

    def test_most_similar_empty_candidates(self):
        """Test with no candidates."""
        target = {"buttons": {0: {"note": 60, "channel": 0}}}
        result = most_similar(target, [])
        assert result == []


class TestIsClone:
    """Test clone detection."""

    def test_is_clone_identical_mapping(self):
        """Test that identical mapping is a clone."""
        mapping = {"buttons": {0: {"note": 60, "channel": 0}}}
        assert is_clone(mapping, mapping) is True

    def test_is_clone_above_threshold(self):
        """Test that mapping above threshold is a clone."""
        a = {"buttons": {0: {"note": 60, "channel": 0}}}
        b = {"buttons": {0: {"note": 60, "channel": 0}}}
        assert is_clone(a, b, threshold=0.85) is True

    def test_is_clone_below_threshold(self):
        """Test that mapping below threshold is not a clone."""
        a = {"buttons": {0: {"note": 60, "channel": 0}}}
        b = {"buttons": {0: {"note": 64, "channel": 0}}}
        # Different note
        assert is_clone(a, b, threshold=0.95) is False

    def test_is_clone_custom_threshold(self):
        """Test custom threshold value."""
        a = {
            "buttons": {0: {"note": 60, "channel": 0}},
            "axes": {0: {"cc": 7, "channel": 0}},
        }
        b = {
            "buttons": {0: {"note": 60, "channel": 0}},
            "axes": {0: {"cc": 7, "channel": 0}},
        }

        # Identical → should pass any threshold
        assert is_clone(a, b, threshold=0.5) is True
        assert is_clone(a, b, threshold=0.99) is True

    def test_is_clone_returns_boolean(self):
        """Test that is_clone returns a boolean."""
        a = {"buttons": {0: {"note": 60, "channel": 0}}}
        b = {"buttons": {0: {"note": 61, "channel": 0}}}
        result = is_clone(a, b)
        assert isinstance(result, bool)


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_workflow_identical_presets(self):
        """Test identifying identical presets as clones."""
        preset_a = {
            "name": "Synth Map",
            "buttons": {
                0: {"note": 60, "channel": 0},
                1: {"note": 61, "channel": 0},
            },
            "axes": {0: {"cc": 7, "channel": 0}},
            "shift_layer": {"enabled": True},
        }
        preset_b = dict(preset_a)

        # Should be 1.0 similarity
        score = compute_similarity(preset_a, preset_b)
        assert score == 1.0

        # Should be detected as clone
        assert is_clone(preset_a, preset_b) is True

        # Breakdown should confirm
        breakdown = similarity_breakdown(preset_a, preset_b)
        assert breakdown["overall"] == 1.0

    def test_workflow_similar_presets(self):
        """Test finding similar but not identical presets."""
        preset_a = {
            "buttons": {
                0: {"note": 60, "channel": 0},
                1: {"note": 61, "channel": 0},
                2: {"note": 62, "channel": 0},
            },
            "axes": {0: {"cc": 7, "channel": 0}},
        }
        preset_b = {
            "buttons": {
                0: {"note": 60, "channel": 0},
                1: {"note": 61, "channel": 0},
                3: {"note": 63, "channel": 0},  # Different button
            },
            "axes": {0: {"cc": 7, "channel": 0}},
        }

        # Similar but not identical
        score = compute_similarity(preset_a, preset_b)
        assert 0.0 < score < 1.0

        # Should not be detected as clone (above 0.85)
        assert is_clone(preset_a, preset_b, threshold=0.85) is False

    def test_workflow_completely_different_presets(self):
        """Test that completely different presets score lower."""
        preset_a = {
            "buttons": {
                0: {"note": 60, "channel": 0},
                1: {"note": 61, "channel": 0},
            },
            "axes": {0: {"cc": 7, "channel": 0}},
        }
        preset_b = {
            "buttons": {
                10: {"note": 100, "channel": 1},
                11: {"note": 101, "channel": 1},
            },
            "axes": {5: {"cc": 15, "channel": 1}},
        }

        score = compute_similarity(preset_a, preset_b)
        # Both have empty features (1.0 match), but notes and CCs differ → ~0.3
        assert score < 0.4
        assert is_clone(preset_a, preset_b) is False

    def test_workflow_marketplace_recommendations(self):
        """Test finding similar presets in a marketplace."""
        user_preset = {
            "buttons": {
                0: {"note": 60, "channel": 0},
                1: {"note": 61, "channel": 0},
            },
            "axes": {0: {"cc": 7, "channel": 0}},
        }

        library = [
            ("preset-piano", {
                "buttons": {
                    0: {"note": 60, "channel": 0},
                    1: {"note": 61, "channel": 0},
                },
                "axes": {0: {"cc": 7, "channel": 0}},
            }),
            ("preset-keys", {
                "buttons": {
                    0: {"note": 60, "channel": 0},
                    1: {"note": 61, "channel": 0},
                },
                "axes": {1: {"cc": 8, "channel": 0}},
            }),
            ("preset-drums", {
                "buttons": {
                    0: {"note": 36, "channel": 9},
                    1: {"note": 38, "channel": 9},
                },
                "axes": {0: {"cc": 11, "channel": 0}},
            }),
        ]

        top_3 = most_similar(user_preset, library, top_n=3)

        # Should have 3 results
        assert len(top_3) == 3

        # First should be identical (piano)
        assert top_3[0][0] == "preset-piano"
        assert top_3[0][1] == 1.0

        # Results should be descending
        for i in range(len(top_3) - 1):
            assert top_3[i][1] >= top_3[i + 1][1]
