"""Test suite for mapping_validator module."""

import pytest
from gamepad_midi_bridge.mapping_validator import (
    ValidationIssue,
    validate_mapping,
    is_valid,
    count_by_severity,
    format_issues,
)


class TestValidationIssueDataclass:
    """Test ValidationIssue dataclass."""

    def test_issue_initialization(self):
        """Test basic issue creation."""
        issue = ValidationIssue(
            severity="error",
            path="buttons.5.note",
            message="note out of range",
        )
        assert issue.severity == "error"
        assert issue.path == "buttons.5.note"
        assert issue.message == "note out of range"

    def test_issue_to_dict(self):
        """Test serialization to dict."""
        issue = ValidationIssue(
            severity="warning",
            path="schema_version",
            message="missing schema_version",
        )
        data = issue.to_dict()
        assert data["severity"] == "warning"
        assert data["path"] == "schema_version"
        assert data["message"] == "missing schema_version"

    def test_issue_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "severity": "info",
            "path": "buttons.0",
            "message": "button mapped",
        }
        issue = ValidationIssue.from_dict(data)
        assert issue.severity == "info"
        assert issue.path == "buttons.0"
        assert issue.message == "button mapped"

    def test_issue_round_trip(self):
        """Test to_dict/from_dict round-trip."""
        original = ValidationIssue(
            severity="error",
            path="axes.2.cc",
            message="cc out of range (0..127): 200",
        )
        data = original.to_dict()
        restored = ValidationIssue.from_dict(data)
        assert restored.severity == original.severity
        assert restored.path == original.path
        assert restored.message == original.message


class TestValidateMapping:
    """Test validate_mapping function."""

    def test_empty_dict_missing_schema_version(self):
        """Empty dict returns warning about missing schema_version."""
        issues = validate_mapping({})
        assert len(issues) >= 1
        assert any(
            issue.severity == "warning" and "schema_version" in issue.path
            for issue in issues
        )

    def test_valid_mapping_with_schema_version(self):
        """Mapping with schema_version=5 has no schema warnings."""
        mapping = {"schema_version": 5}
        issues = validate_mapping(mapping)
        schema_issues = [
            issue for issue in issues
            if issue.severity == "warning" and "schema_version" in issue.path
        ]
        assert len(schema_issues) == 0

    def test_schema_version_non_integer(self):
        """schema_version as string triggers error."""
        mapping = {"schema_version": "five"}
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and issue.path == "schema_version"
            for issue in issues
        )

    def test_button_note_out_of_range_high(self):
        """Button with note=200 triggers error."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": 200, "channel": 1}}
        }
        issues = validate_mapping(mapping)
        note_errors = [
            issue for issue in issues
            if issue.severity == "error" and "buttons.0.note" in issue.path
        ]
        assert len(note_errors) >= 1
        assert any("out of range" in issue.message for issue in note_errors)

    def test_button_note_out_of_range_low(self):
        """Button with note=-1 triggers error."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": -1}}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "buttons.0.note" in issue.path
            for issue in issues
        )

    def test_button_channel_zero(self):
        """Button with channel=0 triggers error (must be 1..16)."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": 60, "channel": 0}}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "buttons.0.channel" in issue.path
            for issue in issues
        )

    def test_button_channel_out_of_range_high(self):
        """Button with channel=17 triggers error."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": 60, "channel": 17}}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "buttons.0.channel" in issue.path
            for issue in issues
        )

    def test_button_velocity_out_of_range(self):
        """Button with velocity=128 triggers error."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": 60, "velocity": 128}}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "buttons.0.velocity" in issue.path
            for issue in issues
        )

    def test_button_velocity_zero(self):
        """Button with velocity=0 triggers error (must be 1..127)."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": 60, "velocity": 0}}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "buttons.0.velocity" in issue.path
            for issue in issues
        )

    def test_axes_cc_out_of_range(self):
        """Axis with cc=-5 triggers error."""
        mapping = {
            "schema_version": 5,
            "axes": {0: {"cc": -5}}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "axes.0.cc" in issue.path
            for issue in issues
        )

    def test_axes_cc_valid_range(self):
        """Axis with cc=0..127 all valid."""
        for cc_val in [0, 1, 64, 127]:
            mapping = {
                "schema_version": 5,
                "axes": {0: {"cc": cc_val}}
            }
            issues = validate_mapping(mapping)
            cc_errors = [
                i for i in issues
                if i.severity == "error" and "axes.0.cc" in i.path
            ]
            assert len(cc_errors) == 0

    def test_trigger_crossfade_cc_b_out_of_range(self):
        """Trigger with crossfade_cc_b=300 triggers error."""
        mapping = {
            "schema_version": 5,
            "triggers": {
                "L2": {"cc": 11, "crossfade_cc_b": 300}
            }
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "triggers.L2.crossfade_cc_b" in issue.path
            for issue in issues
        )

    def test_stick_chord_threshold_out_of_range_high(self):
        """Stick with chord_threshold=2.0 triggers error."""
        mapping = {
            "schema_version": 5,
            "left_stick": {"chord_threshold": 2.0}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "left_stick.chord_threshold" in issue.path
            for issue in issues
        )

    def test_stick_chord_threshold_valid_range(self):
        """Stick with chord_threshold=0..1 all valid."""
        for threshold in [0.0, 0.5, 1.0]:
            mapping = {
                "schema_version": 5,
                "left_stick": {"chord_threshold": threshold}
            }
            issues = validate_mapping(mapping)
            threshold_errors = [
                i for i in issues
                if i.severity == "error" and "left_stick.chord_threshold" in i.path
            ]
            assert len(threshold_errors) == 0

    def test_stick_chord_velocity_negative(self):
        """Stick with chord_velocity=-1 triggers error."""
        mapping = {
            "schema_version": 5,
            "right_stick": {"chord_velocity": -1}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "right_stick.chord_velocity" in issue.path
            for issue in issues
        )

    def test_stick_chord_velocity_zero(self):
        """Stick with chord_velocity=0 triggers error (must be 1..127)."""
        mapping = {
            "schema_version": 5,
            "right_stick": {"chord_velocity": 0}
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "right_stick.chord_velocity" in issue.path
            for issue in issues
        )

    def test_macros_missing_name(self):
        """Macro without 'name' field triggers error."""
        mapping = {
            "schema_version": 5,
            "macros": [{"events": []}]
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "macros.0.name" in issue.path
            for issue in issues
        )

    def test_macros_missing_events(self):
        """Macro without 'events' field triggers error."""
        mapping = {
            "schema_version": 5,
            "macros": [{"name": "test"}]
        }
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and "macros.0.events" in issue.path
            for issue in issues
        )

    def test_macros_valid(self):
        """Valid macro with name and events."""
        mapping = {
            "schema_version": 5,
            "macros": [{"name": "test", "events": []}]
        }
        issues = validate_mapping(mapping)
        macro_errors = [
            i for i in issues
            if i.severity == "error" and i.path.startswith("macros.")
        ]
        assert len(macro_errors) == 0

    def test_valid_minimal_mapping(self):
        """Valid minimal mapping with just schema_version."""
        mapping = {"schema_version": 5}
        issues = validate_mapping(mapping)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_valid_mapping_with_buttons_and_axes(self):
        """Valid mapping with proper buttons and axes."""
        mapping = {
            "schema_version": 5,
            "buttons": {
                0: {"note": 60, "channel": 1, "velocity": 100},
                1: {"note": 62, "channel": 1, "velocity": 100},
            },
            "axes": {
                0: {"cc": 11, "channel": 1},
                1: {"cc": 12, "channel": 1},
            }
        }
        issues = validate_mapping(mapping)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_non_dict_input(self):
        """Non-dict input triggers error."""
        issues = validate_mapping("not a dict")
        assert len(issues) >= 1
        assert any(
            issue.severity == "error" and issue.path == "<root>"
            for issue in issues
        )

    def test_buttons_non_dict(self):
        """buttons as non-dict triggers error."""
        mapping = {"schema_version": 5, "buttons": [1, 2, 3]}
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and issue.path == "buttons"
            for issue in issues
        )

    def test_axes_non_dict(self):
        """axes as non-dict triggers error."""
        mapping = {"schema_version": 5, "axes": "not a dict"}
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and issue.path == "axes"
            for issue in issues
        )

    def test_triggers_non_dict(self):
        """triggers as non-dict triggers error."""
        mapping = {"schema_version": 5, "triggers": 123}
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and issue.path == "triggers"
            for issue in issues
        )

    def test_macros_non_list(self):
        """macros as non-list triggers error."""
        mapping = {"schema_version": 5, "macros": {"not": "a list"}}
        issues = validate_mapping(mapping)
        assert any(
            issue.severity == "error" and issue.path == "macros"
            for issue in issues
        )

    def test_tolerates_missing_nested_keys(self):
        """Missing nested keys don't crash validator (uses .get defensively)."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {}},  # Empty, no note/channel/velocity
            "axes": {0: {}},     # Empty
            "triggers": {},      # Empty
            "left_stick": {},    # Empty
        }
        # Should not raise, just return empty or minimal issues
        issues = validate_mapping(mapping)
        assert isinstance(issues, list)


class TestIsValid:
    """Test is_valid function."""

    def test_is_valid_with_no_errors(self):
        """is_valid returns True when no errors present."""
        mapping = {"schema_version": 5}
        assert is_valid(mapping) is True

    def test_is_valid_with_warnings_only(self):
        """is_valid returns True even with warnings (errors only fail)."""
        mapping = {}  # Missing schema_version = warning
        assert is_valid(mapping) is True

    def test_is_valid_with_one_error(self):
        """is_valid returns False when one error present."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": 200}}  # note out of range
        }
        assert is_valid(mapping) is False

    def test_is_valid_with_multiple_errors(self):
        """is_valid returns False with multiple errors."""
        mapping = {
            "schema_version": 5,
            "buttons": {0: {"note": 200, "channel": 0}},
            "axes": {0: {"cc": -5}}
        }
        assert is_valid(mapping) is False


class TestCountBySeverity:
    """Test count_by_severity function."""

    def test_count_empty_list(self):
        """Empty list returns all zeros."""
        issues = []
        counts = count_by_severity(issues)
        assert counts == {"error": 0, "warning": 0, "info": 0}

    def test_count_mixed_severities(self):
        """Counts issues by severity."""
        issues = [
            ValidationIssue("error", "buttons.0", "note out of range"),
            ValidationIssue("error", "buttons.1", "channel out of range"),
            ValidationIssue("warning", "schema_version", "missing"),
            ValidationIssue("info", "buttons.2", "mapped"),
        ]
        counts = count_by_severity(issues)
        assert counts == {"error": 2, "warning": 1, "info": 1}

    def test_count_only_errors(self):
        """Count with only errors."""
        issues = [
            ValidationIssue("error", "path1", "msg1"),
            ValidationIssue("error", "path2", "msg2"),
        ]
        counts = count_by_severity(issues)
        assert counts == {"error": 2, "warning": 0, "info": 0}

    def test_count_only_warnings(self):
        """Count with only warnings."""
        issues = [ValidationIssue("warning", "path", "msg")]
        counts = count_by_severity(issues)
        assert counts == {"error": 0, "warning": 1, "info": 0}


class TestFormatIssues:
    """Test format_issues function."""

    def test_format_empty_list(self):
        """Empty list returns empty string."""
        result = format_issues([])
        assert result == ""

    def test_format_single_issue(self):
        """Single issue formats correctly."""
        issues = [ValidationIssue("error", "buttons.0.note", "out of range (0..127): 200")]
        result = format_issues(issues)
        assert "[ERROR]" in result
        assert "buttons.0.note" in result
        assert "out of range" in result

    def test_format_multiple_issues(self):
        """Multiple issues format as newline-separated lines."""
        issues = [
            ValidationIssue("error", "buttons.0.note", "out of range"),
            ValidationIssue("warning", "schema_version", "missing"),
            ValidationIssue("info", "buttons.1", "valid"),
        ]
        result = format_issues(issues)
        lines = result.split("\n")
        assert len(lines) == 3
        assert any("[ERROR]" in line for line in lines)
        assert any("[WARNING]" in line for line in lines)
        assert any("[INFO]" in line for line in lines)

    def test_format_includes_all_fields(self):
        """Formatted output includes severity, path, and message."""
        issues = [
            ValidationIssue("error", "axes.2.cc", "cc out of range (0..127): 200")
        ]
        result = format_issues(issues)
        assert "[ERROR]" in result
        assert "axes.2.cc" in result
        assert "cc out of range" in result


class TestValidateComplex:
    """Integration tests for complex/realistic mappings."""

    def test_realistic_valid_mapping(self):
        """Validate a realistic complete mapping."""
        mapping = {
            "schema_version": 5,
            "buttons": {
                0: {"note": 60, "channel": 1, "velocity": 100},
                1: {"note": 62, "channel": 1, "velocity": 100},
                2: {"note": 64, "channel": 1, "velocity": 100},
            },
            "axes": {
                0: {"cc": 1, "channel": 1},
                1: {"cc": 2, "channel": 1},
                4: {"cc": 7, "channel": 1},
            },
            "triggers": {
                "L2": {"cc": 11, "channel": 1},
                "R2": {"cc": 7, "channel": 1},
            },
            "left_stick": {
                "chord_threshold": 0.5,
                "chord_velocity": 100,
            },
            "right_stick": {
                "chord_threshold": 0.6,
                "chord_velocity": 110,
            },
            "macros": [
                {"name": "macro1", "events": []},
                {"name": "macro2", "events": []},
            ]
        }
        issues = validate_mapping(mapping)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_marketplace_download_with_errors(self):
        """Validate a marketplace download with multiple errors."""
        mapping = {
            "schema_version": "invalid",  # Error: not an int
            "buttons": {
                0: {"note": 200},  # Error: note out of range
                1: {"channel": 0},  # Error: channel out of range
            },
            "axes": {
                0: {"cc": 999},  # Error: cc out of range
            },
        }
        issues = validate_mapping(mapping)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 4
        assert is_valid(mapping) is False

    def test_partial_mapping_missing_optional_sections(self):
        """Mapping with only some sections present."""
        mapping = {
            "schema_version": 4,
            "buttons": {
                0: {"note": 60},
            },
        }
        issues = validate_mapping(mapping)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0
