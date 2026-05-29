"""Test suite for mapping_fingerprint module."""

import pytest
from gamepad_midi_bridge.mapping_fingerprint import (
    canonical_json,
    fingerprint,
    short_fingerprint,
    compare,
    fingerprint_components,
    diff_summary,
)


class TestCanonicalJson:
    """Test canonical_json determinism and sorting."""

    def test_canonical_json_sorts_dict_keys(self):
        """Test that dict keys are sorted in canonical form."""
        data = {"z": 1, "a": 2, "m": 3}
        result = canonical_json(data)
        # Should be sorted: a, m, z
        assert result.index('"a"') < result.index('"m"') < result.index('"z"')

    def test_canonical_json_deterministic(self):
        """Test that same input always produces same output."""
        data = {"x": 1, "y": {"nested": [3, 2, 1]}, "z": "test"}
        result1 = canonical_json(data)
        result2 = canonical_json(data)
        assert result1 == result2

    def test_canonical_json_order_invariant(self):
        """Test that dict order doesn't affect canonical form."""
        a = {"a": 1, "b": 2}
        b = {"b": 2, "a": 1}
        assert canonical_json(a) == canonical_json(b)

    def test_canonical_json_different_inputs_different_output(self):
        """Test that different dicts produce different canonical JSON."""
        a = {"a": 1, "b": 2}
        b = {"a": 1, "b": 3}
        assert canonical_json(a) != canonical_json(b)

    def test_canonical_json_no_whitespace(self):
        """Test that canonical JSON contains no spaces or newlines."""
        data = {"a": 1, "b": [2, 3, 4]}
        result = canonical_json(data)
        assert " " not in result
        assert "\n" not in result
        assert "\t" not in result

    def test_canonical_json_nested_dicts_sorted(self):
        """Test that nested dicts also have sorted keys."""
        data = {"outer": {"z": 1, "a": 2}}
        result = canonical_json(data)
        # Should appear as "a" before "z" in nested dict
        outer_start = result.index('"outer"')
        a_idx = result.index('"a"', outer_start)
        z_idx = result.index('"z"', outer_start)
        assert a_idx < z_idx

    def test_canonical_json_preserves_list_order(self):
        """Test that lists preserve insertion order (not sorted)."""
        data = {"items": [3, 1, 2]}
        result = canonical_json(data)
        # Should be "3" then "1" then "2", not "1" then "2" then "3"
        idx_3 = result.index("3")
        idx_1 = result.index("1")
        idx_2 = result.index("2")
        assert idx_3 < idx_1 < idx_2

    def test_canonical_json_sets_converted_to_sorted_lists(self):
        """Test that sets are converted to sorted lists."""
        data = {"tags": {3, 1, 2}}
        result = canonical_json(data)
        # Should contain [1,2,3] not [3,1,2]
        idx_1 = result.index("1")
        idx_2 = result.index("2")
        idx_3 = result.index("3")
        assert idx_1 < idx_2 < idx_3

    def test_canonical_json_float_stability(self):
        """Test that floats use repr() for stable representation."""
        data = {"value": 3.14159}
        result = canonical_json(data)
        # Should use repr format
        assert "3.14159" in result


class TestFingerprint:
    """Test fingerprint generation and properties."""

    def test_fingerprint_length_is_64(self):
        """Test that SHA-256 fingerprint is 64 hex characters."""
        data = {"a": 1}
        result = fingerprint(data)
        assert len(result) == 64
        # All hex characters
        assert all(c in "0123456789abcdef" for c in result)

    def test_fingerprint_same_mapping_same_hash(self):
        """Test that same mapping produces same hash."""
        data = {"buttons": {"btn_cross": 60}, "axes": {}}
        result1 = fingerprint(data)
        result2 = fingerprint(data)
        assert result1 == result2

    def test_fingerprint_different_mappings_different_hash(self):
        """Test that different mappings produce different hashes."""
        a = {"buttons": {"btn_cross": 60}}
        b = {"buttons": {"btn_cross": 61}}
        assert fingerprint(a) != fingerprint(b)

    def test_fingerprint_order_invariant(self):
        """Test that dict key order doesn't affect fingerprint."""
        a = {"buttons": 1, "axes": 2}
        b = {"axes": 2, "buttons": 1}
        assert fingerprint(a) == fingerprint(b)

    def test_fingerprint_with_ignore_keys(self):
        """Test that ignore_keys parameter excludes top-level keys."""
        base = {"buttons": {"btn_cross": 60}, "last_modified": "2026-05-30"}
        without_ts = {"buttons": {"btn_cross": 60}}

        # Fingerprints with last_modified excluded should match
        result = fingerprint(base, ignore_keys=["last_modified"])
        expected = fingerprint(without_ts)
        assert result == expected

    def test_fingerprint_ignore_multiple_keys(self):
        """Test ignoring multiple keys at once."""
        data = {
            "buttons": {"btn_cross": 60},
            "last_modified": "2026-05-30",
            "author": "test",
        }
        clean = {"buttons": {"btn_cross": 60}}

        result = fingerprint(data, ignore_keys=["last_modified", "author"])
        expected = fingerprint(clean)
        assert result == expected

    def test_fingerprint_complex_nested_structure(self):
        """Test fingerprinting complex nested mappings."""
        data = {
            "buttons": {
                "btn_cross": {"note": 60, "channel": 1, "modifiers": [1, 2, 3]},
                "btn_circle": {"note": 61, "channel": 1},
            },
            "axes": {"ax_lx": {"cc": 7, "range": [0, 127]}},
            "triggers": {"L2": {"mode": "cc", "value": 11}},
        }
        result1 = fingerprint(data)
        result2 = fingerprint(data)
        assert result1 == result2
        assert len(result1) == 64


class TestShortFingerprint:
    """Test short fingerprint generation."""

    def test_short_fingerprint_default_length_8(self):
        """Test that short_fingerprint defaults to 8 characters."""
        data = {"a": 1}
        result = short_fingerprint(data)
        assert len(result) == 8

    def test_short_fingerprint_custom_length(self):
        """Test custom length parameter."""
        data = {"a": 1}
        result = short_fingerprint(data, length=16)
        assert len(result) == 16

    def test_short_fingerprint_clamped_min(self):
        """Test that length is clamped to minimum of 4."""
        data = {"a": 1}
        result = short_fingerprint(data, length=2)
        assert len(result) == 4

    def test_short_fingerprint_clamped_max(self):
        """Test that length is clamped to maximum of 64."""
        data = {"a": 1}
        result = short_fingerprint(data, length=100)
        assert len(result) == 64

    def test_short_fingerprint_is_prefix_of_full(self):
        """Test that short fingerprint is a prefix of the full fingerprint."""
        data = {"a": 1, "b": 2}
        full = fingerprint(data)
        short = short_fingerprint(data, length=12)
        assert full.startswith(short)

    def test_short_fingerprint_different_lengths_different_values(self):
        """Test that different lengths can produce different visual fingerprints."""
        data = {"a": 1}
        s8 = short_fingerprint(data, length=8)
        s12 = short_fingerprint(data, length=12)
        # s12 contains s8 as prefix but may differ visually
        assert s12.startswith(s8)


class TestCompare:
    """Test fingerprint comparison."""

    def test_compare_identical_mappings(self):
        """Test that identical mappings return True."""
        data = {"buttons": {"btn_cross": 60}, "axes": {}}
        assert compare(data, data) is True

    def test_compare_different_mappings(self):
        """Test that different mappings return False."""
        a = {"buttons": {"btn_cross": 60}}
        b = {"buttons": {"btn_cross": 61}}
        assert compare(a, b) is False

    def test_compare_order_invariant(self):
        """Test that dict order doesn't affect comparison."""
        a = {"buttons": 1, "axes": 2}
        b = {"axes": 2, "buttons": 1}
        assert compare(a, b) is True

    def test_compare_with_ignore_keys_same_except_metadata(self):
        """Test comparing when only metadata differs."""
        a = {
            "buttons": {"btn_cross": 60},
            "last_modified": "2026-05-30T12:00:00",
            "author": "user1",
        }
        b = {
            "buttons": {"btn_cross": 60},
            "last_modified": "2026-05-30T13:00:00",
            "author": "user2",
        }
        # Without ignoring, they differ
        assert compare(a, b) is False
        # With ignoring metadata, they match
        assert compare(a, b, ignore_keys=["last_modified", "author"]) is True

    def test_compare_with_ignore_keys_still_different(self):
        """Test that ignore_keys doesn't hide actual content differences."""
        a = {"buttons": {"btn_cross": 60}, "modified": "t1"}
        b = {"buttons": {"btn_cross": 61}, "modified": "t2"}
        # Even ignoring modified, the button mapping is different
        assert compare(a, b, ignore_keys=["modified"]) is False


class TestFingerprintComponents:
    """Test per-section fingerprinting."""

    def test_fingerprint_components_returns_dict(self):
        """Test that fingerprint_components returns a dict."""
        data = {"buttons": {"btn_cross": 60}, "axes": {}}
        result = fingerprint_components(data)
        assert isinstance(result, dict)

    def test_fingerprint_components_has_sections(self):
        """Test that components dict has keys for each section."""
        data = {
            "buttons": {"btn_cross": 60},
            "axes": {"ax_lx": {"cc": 7}},
            "triggers": {},
        }
        result = fingerprint_components(data)
        assert "buttons" in result
        assert "axes" in result
        assert "triggers" in result

    def test_fingerprint_components_each_hash_is_64_chars(self):
        """Test that each component hash is a valid SHA-256 hex."""
        data = {
            "buttons": {"btn_cross": 60},
            "axes": {"ax_lx": {"cc": 7}},
        }
        result = fingerprint_components(data)
        for section, hash_val in result.items():
            assert len(hash_val) == 64
            assert all(c in "0123456789abcdef" for c in hash_val)

    def test_fingerprint_components_ignores_null_sections(self):
        """Test that None/null sections are skipped."""
        data = {"buttons": {"btn_cross": 60}, "axes": None, "metadata": "test"}
        result = fingerprint_components(data)
        # Only non-None sections
        assert "buttons" in result
        assert "axes" not in result
        assert "metadata" in result

    def test_fingerprint_components_same_data_same_hashes(self):
        """Test that same section data produces same hashes."""
        data = {"buttons": {"btn_cross": 60}, "axes": {"ax_lx": 7}}
        c1 = fingerprint_components(data)
        c2 = fingerprint_components(data)
        assert c1 == c2

    def test_fingerprint_components_different_sections_different_hashes(self):
        """Test that different section data produces different hashes."""
        a = {"buttons": {"btn_cross": 60}}
        b = {"buttons": {"btn_cross": 61}}
        ca = fingerprint_components(a)
        cb = fingerprint_components(b)
        assert ca["buttons"] != cb["buttons"]


class TestDiffSummary:
    """Test diff summary generation."""

    def test_diff_summary_identical_mappings_empty(self):
        """Test that identical mappings return empty diff."""
        data = {"buttons": {"btn_cross": 60}, "axes": {}}
        result = diff_summary(data, data)
        assert result == []

    def test_diff_summary_different_buttons_lists_buttons(self):
        """Test that button changes are reported."""
        a = {"buttons": {"btn_cross": 60}}
        b = {"buttons": {"btn_cross": 61}}
        result = diff_summary(a, b)
        assert "buttons" in result

    def test_diff_summary_different_axes_lists_axes(self):
        """Test that axes changes are reported."""
        a = {"buttons": {}, "axes": {"ax_lx": 7}}
        b = {"buttons": {}, "axes": {"ax_lx": 8}}
        result = diff_summary(a, b)
        assert "axes" in result

    def test_diff_summary_multiple_sections_changed(self):
        """Test reporting multiple changed sections."""
        a = {
            "buttons": {"btn_cross": 60},
            "axes": {"ax_lx": 7},
            "triggers": {"L2": "cc"},
        }
        b = {
            "buttons": {"btn_cross": 61},
            "axes": {"ax_lx": 7},
            "triggers": {"L2": "note"},
        }
        result = diff_summary(a, b)
        assert "buttons" in result
        assert "triggers" in result
        assert "axes" not in result  # axes unchanged

    def test_diff_summary_new_section(self):
        """Test that adding a section is detected."""
        a = {"buttons": {"btn_cross": 60}}
        b = {"buttons": {"btn_cross": 60}, "axes": {"ax_lx": 7}}
        result = diff_summary(a, b)
        assert "axes" in result

    def test_diff_summary_removed_section(self):
        """Test that removing a section is detected."""
        a = {"buttons": {"btn_cross": 60}, "axes": {"ax_lx": 7}}
        b = {"buttons": {"btn_cross": 60}}
        result = diff_summary(a, b)
        assert "axes" in result

    def test_diff_summary_returns_sorted_list(self):
        """Test that diff_summary returns sorted section names."""
        a = {
            "zebra": 1,
            "apple": 1,
            "monkey": 1,
        }
        b = {
            "zebra": 2,
            "apple": 2,
            "monkey": 2,
        }
        result = diff_summary(a, b)
        # Should be sorted
        assert result == sorted(result)

    def test_diff_summary_doesnt_mutate_inputs(self):
        """Test that diff_summary doesn't modify input dicts."""
        a = {"buttons": {"btn_cross": 60}}
        b = {"buttons": {"btn_cross": 61}}
        a_copy = dict(a)
        b_copy = dict(b)

        diff_summary(a, b)

        assert a == a_copy
        assert b == b_copy

    def test_diff_summary_complex_mapping(self):
        """Test diff_summary on realistic mapping structure."""
        mapping_v1 = {
            "buttons": {
                "btn_cross": {"note": 60, "channel": 1},
                "btn_circle": {"note": 61, "channel": 1},
            },
            "axes": {
                "ax_lx": {"cc": 7, "range": [0, 127]},
            },
            "triggers": {
                "L2": {"mode": "cc", "value": 11},
            },
            "metadata": {
                "name": "Synth Map v1",
                "author": "user",
            },
        }
        mapping_v2 = dict(mapping_v1)
        mapping_v2["triggers"] = {
            "L2": {"mode": "note", "value": 50},  # Changed trigger mode
        }

        result = diff_summary(mapping_v1, mapping_v2)
        assert "triggers" in result
        assert "buttons" not in result
        assert "axes" not in result
        assert "metadata" not in result
