"""Test suite for mapping_merge module."""

import pytest
from gamepad_midi_bridge.mapping_merge import (
    merge_dicts,
    find_conflicts,
    pick_keys,
    omit_keys,
    merge_mapping_subsection,
)


class TestMergeDicts:
    """Test merge_dicts with various strategies."""

    def test_merge_dicts_overlay_non_overlapping(self):
        """Test overlay strategy with non-overlapping keys returns union."""
        base = {"a": 1, "b": 2}
        overlay = {"c": 3, "d": 4}
        result = merge_dicts(base, overlay, "overlay")
        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_merge_dicts_overlay_scalar_conflict_overlay_wins(self):
        """Test overlay strategy with overlapping scalar keys — overlay wins."""
        base = {"a": 1, "b": 2}
        overlay = {"b": 20, "c": 3}
        result = merge_dicts(base, overlay, "overlay")
        assert result == {"a": 1, "b": 20, "c": 3}

    def test_merge_dicts_overlay_deep_merge_nested(self):
        """Test overlay strategy deep-merges nested dicts."""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        overlay = {"a": 10, "b": {"c": 20}}
        result = merge_dicts(base, overlay, "overlay")
        assert result == {"a": 10, "b": {"c": 20, "d": 3}}

    def test_merge_dicts_overlay_list_replacement(self):
        """Test overlay strategy replaces base list entirely."""
        base = {"a": [1, 2, 3], "b": 2}
        overlay = {"a": [10, 20], "c": 3}
        result = merge_dicts(base, overlay, "overlay")
        assert result == {"a": [10, 20], "b": 2, "c": 3}

    def test_merge_dicts_prefer_base_scalar_conflict_base_wins(self):
        """Test prefer_base strategy with overlapping scalar keys — base wins, new keys added."""
        base = {"a": 1, "b": 2}
        overlay = {"b": 20, "c": 3}
        result = merge_dicts(base, overlay, "prefer_base")
        # prefer_base: existing keys keep base value, missing keys from overlay are added
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_merge_dicts_prefer_base_fills_missing_keys(self):
        """Test prefer_base strategy fills in keys absent from base."""
        base = {"a": 1}
        overlay = {"a": 10, "b": 2, "c": 3}
        result = merge_dicts(base, overlay, "prefer_base")
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_merge_dicts_union_list_concat_dedup(self):
        """Test union strategy concatenates and deduplicates lists."""
        base = {"a": [1, 2, 3]}
        overlay = {"a": [3, 4, 5]}
        result = merge_dicts(base, overlay, "union")
        assert result == {"a": [1, 2, 3, 4, 5]}

    def test_merge_dicts_union_scalar_conflict_overlay_wins(self):
        """Test union strategy scalar conflict — overlay wins."""
        base = {"a": 1, "b": 2}
        overlay = {"b": 20, "c": 3}
        result = merge_dicts(base, overlay, "union")
        assert result == {"a": 1, "b": 20, "c": 3}

    def test_merge_dicts_unknown_strategy_defaults_to_overlay(self):
        """Test unknown strategy defaults to overlay behavior."""
        base = {"a": 1}
        overlay = {"a": 10, "b": 2}
        result = merge_dicts(base, overlay, "unknown_strategy")
        assert result == {"a": 10, "b": 2}

    def test_merge_dicts_non_mutating(self):
        """Test merge_dicts doesn't mutate input dicts."""
        base = {"a": 1, "b": {"c": 2}}
        overlay = {"b": {"c": 20, "d": 30}}
        base_copy = dict(base)
        overlay_copy = dict(overlay)

        merge_dicts(base, overlay, "overlay")

        assert base == base_copy
        assert overlay == overlay_copy

    def test_merge_dicts_empty_inputs(self):
        """Test merge_dicts with empty dicts."""
        assert merge_dicts({}, {"a": 1}) == {"a": 1}
        assert merge_dicts({"a": 1}, {}) == {"a": 1}
        assert merge_dicts({}, {}) == {}

    def test_merge_dicts_three_level_nesting(self):
        """Test merge_dicts with three levels of nesting."""
        base = {"x": {"y": {"z": 1}}}
        overlay = {"x": {"y": {"z": 10, "w": 2}}}
        result = merge_dicts(base, overlay, "overlay")
        assert result == {"x": {"y": {"z": 10, "w": 2}}}


class TestFindConflicts:
    """Test find_conflicts to detect leaf-key differences."""

    def test_find_conflicts_identical_dicts_no_conflicts(self):
        """Test identical dicts yield no conflicts."""
        base = {"a": 1, "b": 2}
        overlay = {"a": 1, "b": 2}
        conflicts = find_conflicts(base, overlay)
        assert conflicts == []

    def test_find_conflicts_finds_scalar_difference(self):
        """Test find_conflicts detects scalar value differences."""
        base = {"a": 1, "b": 2}
        overlay = {"a": 1, "b": 99}
        conflicts = find_conflicts(base, overlay)
        assert ("b", 2, 99) in conflicts

    def test_find_conflicts_nested_difference(self):
        """Test find_conflicts detects nested differences with dotted paths."""
        base = {"x": {"y": 1, "z": 2}}
        overlay = {"x": {"y": 1, "z": 99}}
        conflicts = find_conflicts(base, overlay)
        assert ("x.z", 2, 99) in conflicts

    def test_find_conflicts_returns_dotted_paths(self):
        """Test find_conflicts returns dotted paths for nested conflicts."""
        base = {"a": {"b": {"c": 1}}}
        overlay = {"a": {"b": {"c": 10}}}
        conflicts = find_conflicts(base, overlay)
        assert ("a.b.c", 1, 10) in conflicts

    def test_find_conflicts_excludes_keys_only_in_one_side(self):
        """Test find_conflicts only reports overlapping keys."""
        base = {"a": 1, "b": 2}
        overlay = {"a": 1, "c": 3}
        conflicts = find_conflicts(base, overlay)
        assert conflicts == []

    def test_find_conflicts_list_comparison(self):
        """Test find_conflicts compares lists as whole objects."""
        base = {"a": [1, 2]}
        overlay = {"a": [1, 3]}
        conflicts = find_conflicts(base, overlay)
        assert ("a", [1, 2], [1, 3]) in conflicts

    def test_find_conflicts_multiple_conflicts(self):
        """Test find_conflicts returns multiple conflicts."""
        base = {"a": 1, "b": 2, "c": 3}
        overlay = {"a": 10, "b": 2, "c": 30}
        conflicts = find_conflicts(base, overlay)
        assert len(conflicts) == 2
        assert ("a", 1, 10) in conflicts
        assert ("c", 3, 30) in conflicts

    def test_find_conflicts_deep_nesting(self):
        """Test find_conflicts with deeply nested structures."""
        base = {"w": {"x": {"y": {"z": 1}}}}
        overlay = {"w": {"x": {"y": {"z": 10}}}}
        conflicts = find_conflicts(base, overlay)
        assert ("w.x.y.z", 1, 10) in conflicts

    def test_find_conflicts_empty_dicts(self):
        """Test find_conflicts with empty inputs."""
        assert find_conflicts({}, {}) == []
        assert find_conflicts({"a": 1}, {}) == []
        assert find_conflicts({}, {"a": 1}) == []


class TestPickKeys:
    """Test pick_keys to extract subsets."""

    def test_pick_keys_basic_subset(self):
        """Test pick_keys extracts specified keys."""
        source = {"a": 1, "b": 2, "c": 3}
        result = pick_keys(source, ["a", "c"])
        assert result == {"a": 1, "c": 3}

    def test_pick_keys_missing_keys_ignored(self):
        """Test pick_keys ignores keys not in source."""
        source = {"a": 1, "b": 2}
        result = pick_keys(source, ["a", "c", "d"])
        assert result == {"a": 1}

    def test_pick_keys_empty_key_list(self):
        """Test pick_keys with empty key list returns empty dict."""
        source = {"a": 1, "b": 2}
        result = pick_keys(source, [])
        assert result == {}

    def test_pick_keys_preserves_values(self):
        """Test pick_keys preserves original values (including nested dicts)."""
        source = {"a": {"nested": 1}, "b": [1, 2, 3]}
        result = pick_keys(source, ["a", "b"])
        assert result == {"a": {"nested": 1}, "b": [1, 2, 3]}

    def test_pick_keys_non_mutating(self):
        """Test pick_keys doesn't mutate source."""
        source = {"a": 1, "b": 2}
        source_copy = dict(source)
        pick_keys(source, ["a"])
        assert source == source_copy


class TestOmitKeys:
    """Test omit_keys to exclude keys."""

    def test_omit_keys_removes_specified(self):
        """Test omit_keys removes specified keys."""
        source = {"a": 1, "b": 2, "c": 3}
        result = omit_keys(source, ["b"])
        assert result == {"a": 1, "c": 3}

    def test_omit_keys_multiple_removals(self):
        """Test omit_keys removes multiple keys."""
        source = {"a": 1, "b": 2, "c": 3, "d": 4}
        result = omit_keys(source, ["a", "c"])
        assert result == {"b": 2, "d": 4}

    def test_omit_keys_missing_keys_ignored(self):
        """Test omit_keys gracefully handles keys not in source."""
        source = {"a": 1, "b": 2}
        result = omit_keys(source, ["b", "c", "d"])
        assert result == {"a": 1}

    def test_omit_keys_empty_omit_list(self):
        """Test omit_keys with empty omit list returns full dict."""
        source = {"a": 1, "b": 2}
        result = omit_keys(source, [])
        assert result == {"a": 1, "b": 2}

    def test_omit_keys_omit_all(self):
        """Test omit_keys with all keys returns empty dict."""
        source = {"a": 1, "b": 2}
        result = omit_keys(source, ["a", "b"])
        assert result == {}

    def test_omit_keys_non_mutating(self):
        """Test omit_keys doesn't mutate source."""
        source = {"a": 1, "b": 2}
        source_copy = dict(source)
        omit_keys(source, ["a"])
        assert source == source_copy


class TestMergeMappingSubsection:
    """Test merge_mapping_subsection for targeted updates."""

    def test_merge_mapping_subsection_basic(self):
        """Test merge_mapping_subsection updates named section."""
        mapping = {
            "name": "Test Mapping",
            "buttons": {"0": 60, "1": 61},
            "axes": {"0": 100},
        }
        new_buttons = {"1": 70, "2": 72}
        result = merge_mapping_subsection(mapping, "buttons", new_buttons, "overlay")
        assert result["buttons"] == {"0": 60, "1": 70, "2": 72}
        assert result["axes"] == {"0": 100}
        assert result["name"] == "Test Mapping"

    def test_merge_mapping_subsection_new_section(self):
        """Test merge_mapping_subsection adds new section if not present."""
        mapping = {"name": "Test", "buttons": {"0": 60}}
        new_triggers = {"mode": "linear"}
        result = merge_mapping_subsection(mapping, "l2_trigger", new_triggers, "overlay")
        assert result["l2_trigger"] == {"mode": "linear"}
        assert result["buttons"] == {"0": 60}

    def test_merge_mapping_subsection_prefer_base_strategy(self):
        """Test merge_mapping_subsection respects prefer_base strategy."""
        mapping = {
            "buttons": {"0": 60, "1": 61},
        }
        overlay = {"0": 99, "2": 62}
        result = merge_mapping_subsection(mapping, "buttons", overlay, "prefer_base")
        # prefer_base: base values stay, missing keys from overlay are added
        assert result["buttons"] == {"0": 60, "1": 61, "2": 62}

    def test_merge_mapping_subsection_union_strategy(self):
        """Test merge_mapping_subsection respects union strategy on dicts."""
        mapping = {
            "buttons": {"0": 60, "1": 61},
        }
        overlay = {
            "1": 70,
            "2": 72,
        }
        result = merge_mapping_subsection(mapping, "buttons", overlay, "union")
        # union on dicts: overlay wins for scalar conflicts
        assert result["buttons"] == {"0": 60, "1": 70, "2": 72}

    def test_merge_mapping_subsection_non_mutating(self):
        """Test merge_mapping_subsection doesn't mutate input."""
        mapping = {"name": "Test", "buttons": {"0": 60}}
        mapping_copy = dict(mapping)
        overlay = {"1": 61}
        merge_mapping_subsection(mapping, "buttons", overlay, "overlay")
        assert mapping == mapping_copy

    def test_merge_mapping_subsection_complex_nested(self):
        """Test merge_mapping_subsection with complex nested sections."""
        mapping = {
            "name": "Test",
            "left_stick": {
                "deadzone": 0.1,
                "chord": {"enabled": False},
            },
        }
        overlay_stick = {
            "chord": {"enabled": True, "chord_notes": [60, 64]},
        }
        result = merge_mapping_subsection(
            mapping, "left_stick", overlay_stick, "overlay"
        )
        assert result["left_stick"]["deadzone"] == 0.1
        assert result["left_stick"]["chord"]["enabled"] is True
        assert result["left_stick"]["chord"]["chord_notes"] == [60, 64]


class TestIntegrationScenarios:
    """Integration tests for realistic mapping merge scenarios."""

    def test_merge_two_button_mappings(self):
        """Test merging two button mapping dicts."""
        base = {
            "buttons": {"0": 60, "1": 61, "2": 62},
            "name": "Base Mapping",
        }
        overlay = {
            "buttons": {"1": 70, "3": 63},
            "name": "Overlay Mapping",
        }
        result = merge_dicts(base, overlay)
        assert result["buttons"] == {"0": 60, "1": 70, "2": 62, "3": 63}
        assert result["name"] == "Overlay Mapping"

    def test_merge_trigger_configs(self):
        """Test merging trigger configuration sections."""
        base = {
            "l2_trigger": {
                "mode": "linear",
                "ceiling": 127,
            },
        }
        overlay = {
            "l2_trigger": {
                "mode": "ceiling",
            },
        }
        result = merge_dicts(base, overlay)
        assert result["l2_trigger"]["mode"] == "ceiling"
        assert result["l2_trigger"]["ceiling"] == 127

    def test_conflict_detection_complex_mapping(self):
        """Test conflict detection on realistic mapping dicts."""
        base = {
            "midi_channel": 0,
            "buttons": {"0": 60, "1": 61},
            "l2_trigger": {"mode": "linear", "ceiling": 127},
        }
        overlay = {
            "midi_channel": 0,
            "buttons": {"0": 60, "1": 70},
            "l2_trigger": {"mode": "ceiling"},
        }
        conflicts = find_conflicts(base, overlay)
        # Should find the button 1 conflict but not the trigger (missing key doesn't conflict)
        conflict_paths = [c[0] for c in conflicts]
        assert "buttons.1" in conflict_paths or "buttons" in conflict_paths
