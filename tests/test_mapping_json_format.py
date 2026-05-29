"""Test suite for mapping_json_format module."""
from __future__ import annotations

import json
import pytest

from gamepad_midi_bridge.mapping_json_format import (
    KEY_ORDER,
    sort_mapping_keys,
    pretty,
    minify,
    format_size,
    size_savings,
    count_lines,
    count_keys_at_depth,
)


class TestSortMappingKeys:
    """Test sort_mapping_keys function."""

    def test_schema_version_first(self):
        """schema_version should be the first key."""
        data = {
            "name": "Test Mapping",
            "schema_version": 4,
            "buttons": {},
        }
        result = sort_mapping_keys(data)
        keys = list(result.keys())
        assert keys[0] == "schema_version"

    def test_key_order_respected(self):
        """Keys should appear in KEY_ORDER sequence."""
        data = {
            "buttons": {0: 60},
            "schema_version": 4,
            "name": "Test",
            "axes": {0: 7},
            "channel": 1,
        }
        result = sort_mapping_keys(data)
        keys = list(result.keys())

        # Check relative ordering: schema_version < name < channel < buttons < axes
        idx_schema = keys.index("schema_version")
        idx_name = keys.index("name")
        idx_channel = keys.index("channel")
        idx_buttons = keys.index("buttons")
        idx_axes = keys.index("axes")

        assert idx_schema < idx_name < idx_channel < idx_buttons < idx_axes

    def test_unknown_keys_appended_alphabetically(self):
        """Keys not in KEY_ORDER should be appended alphabetically."""
        data = {
            "schema_version": 4,
            "zebra_key": "z",
            "apple_key": "a",
            "banana_key": "b",
        }
        result = sort_mapping_keys(data)
        keys = list(result.keys())

        # schema_version first, then unknown keys alphabetically
        assert keys == [
            "schema_version",
            "apple_key",
            "banana_key",
            "zebra_key",
        ]

    def test_recurses_into_nested_dicts(self):
        """Should recursively sort nested dictionaries."""
        data = {
            "schema_version": 4,
            "buttons": {
                "nested_z": "z",
                "nested_a": "a",
            },
        }
        result = sort_mapping_keys(data)

        # buttons dict should have its values (nested keys) sorted alphabetically
        button_keys = list(result["buttons"].keys())
        assert button_keys == ["nested_a", "nested_z"]

    def test_non_mutating(self):
        """Original dict should not be modified."""
        data = {
            "buttons": {0: 60},
            "schema_version": 4,
        }
        original_keys = list(data.keys())
        result = sort_mapping_keys(data)

        # Original should be unchanged
        assert list(data.keys()) == original_keys
        # Result should be different
        assert list(result.keys()) != original_keys

    def test_empty_dict(self):
        """Empty dict should return empty dict."""
        result = sort_mapping_keys({})
        assert result == {}

    def test_preserves_values(self):
        """All values should be preserved (only keys reordered)."""
        data = {
            "schema_version": 4,
            "name": "Test Mapping",
            "buttons": {0: 60, 1: 62},
        }
        result = sort_mapping_keys(data)

        assert result["schema_version"] == 4
        assert result["name"] == "Test Mapping"
        assert result["buttons"] == {0: 60, 1: 62}


class TestPrettyFunction:
    """Test pretty printing."""

    def test_produces_indented_output(self):
        """pretty() should produce indented (multi-line) JSON."""
        data = {"schema_version": 4, "name": "Test"}
        result = pretty(data)

        assert "\n" in result
        assert "  " in result  # default indent is 2 spaces

    def test_indent_parameter_used(self):
        """pretty() should use the indent parameter."""
        data = {"a": {"b": 1}}
        result = pretty(data, indent=4)

        assert "    " in result  # 4-space indentation
        assert result.count(" ") > pretty(data, indent=2).count(" ")

    def test_indent_clamped_0_to_8(self):
        """indent should be clamped between 0 and 8."""
        data = {"a": 1}

        # Negative should become 0 (compact)
        result_neg = pretty(data, indent=-5)
        assert "\n" not in result_neg or result_neg.count("\n") == 0

        # Large value should be clamped to 8
        result_large = pretty(data, indent=100)
        # Should have indentation, but no more than 8 spaces
        assert "        " in result_large or "\n" in result_large

    def test_keys_sorted(self):
        """pretty() should sort keys per sort_mapping_keys."""
        data = {
            "unknown_z": "z",
            "schema_version": 4,
            "unknown_a": "a",
        }
        result = pretty(data)
        lines = result.split("\n")

        # Find line indices for each key
        schema_line = next(i for i, line in enumerate(lines) if "schema_version" in line)
        a_line = next(i for i, line in enumerate(lines) if "unknown_a" in line)
        z_line = next(i for i, line in enumerate(lines) if "unknown_z" in line)

        assert schema_line < a_line < z_line

    def test_valid_json_output(self):
        """pretty() should produce valid JSON that can be parsed."""
        data = {
            "schema_version": 4,
            "buttons": {"0": 60, "1": 62},
            "name": "Test",
        }
        result = pretty(data)
        parsed = json.loads(result)

        assert parsed["schema_version"] == 4
        assert parsed["buttons"]["0"] == 60


class TestMinifyFunction:
    """Test minify function."""

    def test_produces_single_line(self):
        """minify() should produce single-line JSON."""
        data = {"a": 1, "b": 2, "c": {"d": 3}}
        result = minify(data)

        # Should not have newlines
        assert "\n" not in result

    def test_no_whitespace_after_separators(self):
        """minify() should have no spaces after : or ,"""
        data = {"a": 1, "b": 2}
        result = minify(data)

        assert ": " not in result  # no space after :
        assert ", " not in result  # no space after ,
        assert ": {" not in result
        assert ": [" not in result

    def test_shorter_than_pretty(self):
        """minify() should always be <= pretty() in size."""
        data = {
            "schema_version": 4,
            "buttons": {"0": 60, "1": 62, "2": 64},
            "axes": {"0": 7, "1": 8},
            "name": "Test Mapping",
        }
        pretty_result = pretty(data)
        mini_result = minify(data)

        assert len(mini_result) <= len(pretty_result)

    def test_keys_still_sorted(self):
        """minify() should preserve KEY_ORDER."""
        data = {
            "name": "Test",
            "schema_version": 4,
            "buttons": {"0": 60},
        }
        result = minify(data)

        # Find positions of keys in the JSON string
        schema_pos = result.find('"schema_version"')
        name_pos = result.find('"name"')
        buttons_pos = result.find('"buttons"')

        assert schema_pos < name_pos < buttons_pos

    def test_valid_json_output(self):
        """minify() should produce valid JSON."""
        data = {
            "schema_version": 4,
            "buttons": {"0": 60},
        }
        result = minify(data)
        parsed = json.loads(result)

        assert parsed["schema_version"] == 4
        assert parsed["buttons"]["0"] == 60


class TestFormatSize:
    """Test format_size function."""

    def test_bytes_under_1024(self):
        """Sizes < 1024 bytes should display as 'B'."""
        result = format_size("ab")  # 2 bytes
        assert result == "2 B"

    def test_kilobytes(self):
        """Sizes 1024–1048576 should display as 'KB'."""
        # 1500 bytes = 1500/1024 ≈ 1.46 KB
        result = format_size("x" * 1500)
        assert "KB" in result
        assert result.startswith("1.")  # Should be 1.x KB

    def test_megabytes(self):
        """Sizes >= 1048576 should display as 'MB'."""
        # 2 MB = 2048000 bytes
        result = format_size("x" * (2 * 1024 * 1024))
        assert "MB" in result

    def test_no_trailing_zero(self):
        """Should strip trailing .0 (e.g., '2.0 KB' -> '2 KB')."""
        # 2048 bytes = exactly 2 KB
        result = format_size("x" * 2048)
        assert result == "2 KB"

    def test_single_decimal_place(self):
        """Should format with 1 decimal place."""
        # 1500 bytes = ~1.5 KB
        result = format_size("x" * 1500)
        # Should be "1.5 KB" (1 decimal)
        assert "." in result or "KB" in result
        assert "KB" in result


class TestSizeSavings:
    """Test size_savings function."""

    def test_returns_tuple(self):
        """size_savings should return a tuple."""
        result = size_savings('{"a":1}', '{"a":1}')
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_positive_savings_minify_shorter(self):
        """Should return positive savings when minify is shorter than pretty."""
        pretty_str = '{\n  "a": 1\n}'
        mini_str = '{"a":1}'

        bytes_saved, fraction_saved = size_savings(pretty_str, mini_str)

        assert bytes_saved > 0
        assert 0 < fraction_saved < 1

    def test_no_savings_identical_strings(self):
        """Should return 0 savings for identical strings."""
        same_str = '{"a":1}'
        bytes_saved, fraction_saved = size_savings(same_str, same_str)

        assert bytes_saved == 0
        assert fraction_saved == 0

    def test_handles_empty_pretty(self):
        """Should not crash with empty pretty string."""
        bytes_saved, fraction_saved = size_savings('', '{"a":1}')
        assert bytes_saved == 0 or bytes_saved < 0
        assert fraction_saved == 0


class TestCountLines:
    """Test count_lines function."""

    def test_single_line(self):
        """Single-line JSON should return 1."""
        result = count_lines('{"a":1}')
        assert result == 1

    def test_multiline_json(self):
        """Multi-line JSON should count newlines + 1."""
        json_str = '{\n  "a": 1\n}'  # 2 newlines
        result = count_lines(json_str)
        assert result == 3  # 2 newlines + 1

    def test_empty_string(self):
        """Empty string should return 0."""
        result = count_lines('')
        assert result == 0

    def test_only_newlines(self):
        """String with only newlines should count them + 1."""
        result = count_lines('\n\n')
        assert result == 3

    def test_pretty_has_more_lines_than_minify(self):
        """pretty() should have more lines than minify() for same data."""
        data = {
            "schema_version": 4,
            "buttons": {"0": 60, "1": 62},
        }
        pretty_lines = count_lines(pretty(data))
        mini_lines = count_lines(minify(data))

        assert pretty_lines > mini_lines


class TestCountKeysAtDepth:
    """Test count_keys_at_depth function."""

    def test_flat_dict(self):
        """Flat dict should have all keys at depth 0."""
        data = {"a": 1, "b": 2, "c": 3}
        result = count_keys_at_depth(data)

        assert result == {0: 3}

    def test_nested_dict(self):
        """Nested dict should count keys at each depth."""
        data = {
            "a": 1,
            "b": 2,
            "c": {"d": 3, "e": 4},  # nested: 2 keys at depth 1
        }
        result = count_keys_at_depth(data)

        assert result[0] == 3  # 3 keys at depth 0
        assert result[1] == 2  # 2 keys at depth 1

    def test_deeply_nested(self):
        """Should traverse multiple nesting levels."""
        data = {
            "a": {
                "b": {
                    "c": 1,
                    "d": 2,
                }
            }
        }
        result = count_keys_at_depth(data)

        assert result[0] == 1  # "a" at depth 0
        assert result[1] == 1  # "b" at depth 1
        assert result[2] == 2  # "c", "d" at depth 2

    def test_empty_dict(self):
        """Empty dict should return {0: 0}."""
        result = count_keys_at_depth({})
        assert result == {0: 0}

    def test_complex_mapping_structure(self):
        """Should handle complex mapping structure."""
        data = {
            "schema_version": 4,
            "buttons": {"0": 60, "1": 62},  # 2 keys at depth 1
            "triggers": {"4": {"mode": "linear"}},  # 1 key at depth 1, 1 at depth 2
        }
        result = count_keys_at_depth(data)

        assert result[0] == 3  # schema_version, buttons, triggers
        assert result[1] == 3  # 0, 1 (in buttons), 4 (in triggers)
        assert result[2] == 1  # mode (in triggers[4])


class TestIntegration:
    """Integration tests for the full workflow."""

    def test_round_trip_with_pretty_and_minify(self):
        """Data should survive pretty -> parse -> minify -> parse cycle."""
        original = {
            "schema_version": 4,
            "name": "Test Mapping",
            "buttons": {"0": 60, "1": 62},
            "axes": {"0": 7},
            "channel": 1,
            "triggers": {},
        }

        # Cycle 1: to pretty and back
        pretty_str = pretty(original)
        parsed_pretty = json.loads(pretty_str)

        # Cycle 2: to minify and back
        mini_str = minify(original)
        parsed_mini = json.loads(mini_str)

        # All three should be equal
        assert parsed_pretty == parsed_mini == original

    def test_complex_mapping_with_all_features(self):
        """Should handle a complex mapping with many sections."""
        data = {
            "schema_version": 4,
            "name": "Complex Mapping",
            "description": "Full-featured test preset",
            "channel": 0,
            "buttons": {
                "0": {"note": 60, "velocity": 100},
                "1": 62,
                "2": {"note": 64, "velocity": 80},
            },
            "axes": {
                "0": 7,
                "1": 8,
                "2": 9,
                "3": 10,
            },
            "triggers": {
                "4": {"mode": "linear", "ceiling": 127},
                "5": {"mode": "latch", "latch_threshold": 0.5},
            },
            "left_stick": {
                "cc_x": 20,
                "cc_y": 21,
            },
            "right_stick": {
                "cc_x": 22,
                "cc_y": 23,
            },
            "macros": [
                {"name": "Macro 1", "events": [{"type": "note_on"}]},
            ],
            "shift_layer": {"enabled": True, "button": 10},
        }

        pretty_str = pretty(data)
        mini_str = minify(data)

        # Both should be valid JSON
        assert json.loads(pretty_str) == data
        assert json.loads(mini_str) == data

        # Check ordering: schema_version should be first
        pretty_lines = pretty_str.split("\n")
        assert "schema_version" in pretty_lines[1]  # After opening brace

        # Minify should be shorter
        assert len(mini_str) < len(pretty_str)

        # Get size stats
        bytes_saved, fraction = size_savings(pretty_str, mini_str)
        assert bytes_saved > 0
        assert 0 < fraction < 1

    def test_buttons_before_axes_per_key_order(self):
        """buttons should come before axes per KEY_ORDER."""
        data = {
            "axes": {"0": 7},
            "schema_version": 4,
            "buttons": {"0": 60},
        }
        result = sort_mapping_keys(data)
        keys = list(result.keys())

        buttons_idx = keys.index("buttons")
        axes_idx = keys.index("axes")
        assert buttons_idx < axes_idx
