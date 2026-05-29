"""Test suite for mapping_cleanup module."""

import pytest
from gamepad_midi_bridge.mapping_cleanup import (
    DEFAULT_BUTTON,
    DEFAULT_AXIS,
    is_default_button,
    is_default_axis,
    remove_default_buttons,
    remove_default_axes,
    remove_empty_sections,
    cleanup,
    size_savings_estimate,
)


class TestIsDefaultButton:
    """Test is_default_button function."""

    def test_is_default_button_empty_dict(self):
        """Test empty dict is NOT default (missing required keys)."""
        assert is_default_button({}) is False

    def test_is_default_button_exact_match(self):
        """Test dict with exact DEFAULT_BUTTON values is default."""
        button = {"note": 0, "channel": 1, "velocity": 100}
        assert is_default_button(button) is True

    def test_is_default_button_note_changed(self):
        """Test button with changed note is not default."""
        button = {"note": 60, "channel": 1, "velocity": 100}
        assert is_default_button(button) is False

    def test_is_default_button_velocity_changed(self):
        """Test button with changed velocity is not default."""
        button = {"note": 0, "channel": 1, "velocity": 64}
        assert is_default_button(button) is False

    def test_is_default_button_channel_changed(self):
        """Test button with changed channel is not default."""
        button = {"note": 0, "channel": 5, "velocity": 100}
        assert is_default_button(button) is False

    def test_is_default_button_with_extra_key_falsy(self):
        """Test button with extra falsy key is still default."""
        button = {"note": 0, "channel": 1, "velocity": 100, "extra": None}
        assert is_default_button(button) is True

    def test_is_default_button_with_extra_key_truthy(self):
        """Test button with extra truthy key is not default."""
        button = {"note": 0, "channel": 1, "velocity": 100, "extra": "value"}
        assert is_default_button(button) is False

    def test_is_default_button_missing_required_key(self):
        """Test button missing a required key is not default."""
        button = {"note": 0, "channel": 1}
        assert is_default_button(button) is False


class TestIsDefaultAxis:
    """Test is_default_axis function."""

    def test_is_default_axis_empty_dict(self):
        """Test empty dict is NOT default (missing required keys)."""
        assert is_default_axis({}) is False

    def test_is_default_axis_exact_match(self):
        """Test dict with exact DEFAULT_AXIS values is default."""
        axis = {"cc": 0, "channel": 1}
        assert is_default_axis(axis) is True

    def test_is_default_axis_cc_changed(self):
        """Test axis with changed cc is not default."""
        axis = {"cc": 7, "channel": 1}
        assert is_default_axis(axis) is False

    def test_is_default_axis_channel_changed(self):
        """Test axis with changed channel is not default."""
        axis = {"cc": 0, "channel": 2}
        assert is_default_axis(axis) is False

    def test_is_default_axis_with_extra_key_falsy(self):
        """Test axis with extra falsy key is still default."""
        axis = {"cc": 0, "channel": 1, "extra": None}
        assert is_default_axis(axis) is True

    def test_is_default_axis_with_extra_key_truthy(self):
        """Test axis with extra truthy key is not default."""
        axis = {"cc": 0, "channel": 1, "extra": "value"}
        assert is_default_axis(axis) is False


class TestRemoveDefaultButtons:
    """Test remove_default_buttons function."""

    def test_remove_default_buttons_empty_mapping(self):
        """Test with mapping containing no buttons."""
        mapping = {}
        result, count = remove_default_buttons(mapping)
        assert result == {}
        assert count == 0

    def test_remove_default_buttons_no_buttons_section(self):
        """Test with mapping having no buttons key."""
        mapping = {"axes": {0: {"cc": 7, "channel": 1}}}
        result, count = remove_default_buttons(mapping)
        assert result == mapping
        assert count == 0

    def test_remove_default_buttons_removes_defaults(self):
        """Test that default buttons are removed."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1, "velocity": 100},
            }
        }
        result, count = remove_default_buttons(mapping)
        assert count == 1
        assert result["buttons"] == {1: {"note": 60, "channel": 1, "velocity": 100}}

    def test_remove_default_buttons_keeps_non_defaults(self):
        """Test that non-default buttons are kept."""
        mapping = {
            "buttons": {
                0: {"note": 60, "channel": 1, "velocity": 100},
                1: {"note": 64, "channel": 2, "velocity": 64},
            }
        }
        result, count = remove_default_buttons(mapping)
        assert count == 0
        assert result["buttons"] == mapping["buttons"]

    def test_remove_default_buttons_all_defaults_removed(self):
        """Test removing all default buttons."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 0, "channel": 1, "velocity": 100},
            }
        }
        result, count = remove_default_buttons(mapping)
        assert count == 2
        assert result["buttons"] == {}

    def test_remove_default_buttons_non_mutating(self):
        """Test that function doesn't mutate input."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1},
            }
        }
        mapping_copy = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1},
            }
        }
        remove_default_buttons(mapping)
        assert mapping == mapping_copy


class TestRemoveDefaultAxes:
    """Test remove_default_axes function."""

    def test_remove_default_axes_empty_mapping(self):
        """Test with mapping containing no axes."""
        mapping = {}
        result, count = remove_default_axes(mapping)
        assert result == {}
        assert count == 0

    def test_remove_default_axes_removes_defaults(self):
        """Test that default axes are removed."""
        mapping = {
            "axes": {
                0: {"cc": 0, "channel": 1},
                1: {"cc": 7, "channel": 1},
            }
        }
        result, count = remove_default_axes(mapping)
        assert count == 1
        assert result["axes"] == {1: {"cc": 7, "channel": 1}}

    def test_remove_default_axes_keeps_non_defaults(self):
        """Test that non-default axes are kept."""
        mapping = {
            "axes": {
                0: {"cc": 7, "channel": 1},
                1: {"cc": 10, "channel": 2},
            }
        }
        result, count = remove_default_axes(mapping)
        assert count == 0
        assert result["axes"] == mapping["axes"]

    def test_remove_default_axes_non_mutating(self):
        """Test that function doesn't mutate input."""
        mapping = {
            "axes": {
                0: {"cc": 0, "channel": 1},
                1: {"cc": 7, "channel": 1},
            }
        }
        mapping_copy = {
            "axes": {
                0: {"cc": 0, "channel": 1},
                1: {"cc": 7, "channel": 1},
            }
        }
        remove_default_axes(mapping)
        assert mapping == mapping_copy


class TestRemoveEmptySections:
    """Test remove_empty_sections function."""

    def test_remove_empty_sections_removes_empty_dicts(self):
        """Test that empty dicts are removed."""
        mapping = {
            "buttons": {},
            "axes": {0: {"cc": 7, "channel": 1}},
            "macros": {},
        }
        result, removed = remove_empty_sections(mapping)
        assert result == {"axes": {0: {"cc": 7, "channel": 1}}}
        assert sorted(removed) == ["buttons", "macros"]

    def test_remove_empty_sections_removes_empty_lists(self):
        """Test that empty lists are removed."""
        mapping = {
            "sequences": [],
            "buttons": {0: {"note": 60, "channel": 1}},
        }
        result, removed = remove_empty_sections(mapping)
        assert result == {"buttons": {0: {"note": 60, "channel": 1}}}
        assert removed == ["sequences"]

    def test_remove_empty_sections_removes_none_values(self):
        """Test that None values are removed."""
        mapping = {
            "buttons": {0: {"note": 60, "channel": 1}},
            "description": None,
        }
        result, removed = remove_empty_sections(mapping)
        assert result == {"buttons": {0: {"note": 60, "channel": 1}}}
        assert removed == ["description"]

    def test_remove_empty_sections_removes_zero_values(self):
        """Test that 0 values are removed."""
        mapping = {
            "buttons": {0: {"note": 60, "channel": 1}},
            "priority": 0,
        }
        result, removed = remove_empty_sections(mapping)
        assert result == {"buttons": {0: {"note": 60, "channel": 1}}}
        assert removed == ["priority"]

    def test_remove_empty_sections_removes_false_values(self):
        """Test that False values are removed (falsy)."""
        mapping = {
            "buttons": {0: {"note": 60, "channel": 1}},
            "priority": 1,  # Truthy
            "enabled": False,  # Falsy — gets removed
        }
        result, removed = remove_empty_sections(mapping)
        assert result == {"buttons": {0: {"note": 60, "channel": 1}}, "priority": 1}
        assert removed == ["enabled"]

    def test_remove_empty_sections_no_removals(self):
        """Test with no empty sections."""
        mapping = {
            "buttons": {0: {"note": 60, "channel": 1}},
            "axes": {0: {"cc": 7, "channel": 1}},
        }
        result, removed = remove_empty_sections(mapping)
        assert result == mapping
        assert removed == []


class TestCleanup:
    """Test cleanup function."""

    def test_cleanup_full_pipeline(self):
        """Test full cleanup pipeline removes defaults and empty sections."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1, "velocity": 100},
            },
            "axes": {
                0: {"cc": 0, "channel": 1},
                1: {"cc": 7, "channel": 1},
            },
            "macros": [],
        }
        result, stats = cleanup(mapping)

        assert stats["buttons_removed"] == 1
        assert stats["axes_removed"] == 1
        assert stats["sections_removed"] == 1
        assert result == {
            "buttons": {1: {"note": 60, "channel": 1, "velocity": 100}},
            "axes": {1: {"cc": 7, "channel": 1}},
        }

    def test_cleanup_remove_defaults_false(self):
        """Test cleanup with remove_defaults=False keeps defaults."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1},
            },
            "macros": [],
        }
        result, stats = cleanup(mapping, remove_defaults=False)

        assert stats["buttons_removed"] == 0
        assert stats["axes_removed"] == 0
        assert stats["sections_removed"] == 1
        assert result == {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1},
            }
        }

    def test_cleanup_remove_empty_false(self):
        """Test cleanup with remove_empty=False keeps empty sections."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
            },
            "macros": [],
        }
        result, stats = cleanup(mapping, remove_empty=False)

        assert stats["buttons_removed"] == 1
        assert stats["sections_removed"] == 0
        assert result == {
            "buttons": {},
            "macros": [],
        }

    def test_cleanup_non_mutating(self):
        """Test that cleanup doesn't mutate input."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1},
            },
            "macros": [],
        }
        mapping_copy = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1},
            },
            "macros": [],
        }
        cleanup(mapping)
        assert mapping == mapping_copy

    def test_cleanup_empty_mapping(self):
        """Test cleanup with empty mapping."""
        mapping = {}
        result, stats = cleanup(mapping)
        assert result == {}
        assert stats["buttons_removed"] == 0
        assert stats["axes_removed"] == 0
        assert stats["sections_removed"] == 0

    def test_cleanup_returns_stats(self):
        """Test that cleanup returns correct stats dict."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1},
            },
            "axes": {
                0: {"cc": 0, "channel": 1},
            },
            "macros": [],
        }
        _, stats = cleanup(mapping)

        assert isinstance(stats, dict)
        assert "buttons_removed" in stats
        assert "axes_removed" in stats
        assert "sections_removed" in stats
        assert stats["buttons_removed"] == 1
        assert stats["axes_removed"] == 1
        assert stats["sections_removed"] == 2  # macros and axes sections removed


class TestSizeSavingsEstimate:
    """Test size_savings_estimate function."""

    def test_size_savings_estimate_positive_savings(self):
        """Test that cleanable mappings return positive savings."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1, "velocity": 100},
            },
            "macros": [],
        }
        savings = size_savings_estimate(mapping)
        assert savings > 0

    def test_size_savings_estimate_no_cleanable_content(self):
        """Test that clean mappings return zero or near-zero savings."""
        mapping = {
            "buttons": {
                0: {"note": 60, "channel": 1, "velocity": 100},
            }
        }
        savings = size_savings_estimate(mapping)
        assert savings >= 0

    def test_size_savings_estimate_returns_int(self):
        """Test that size_savings_estimate returns an integer."""
        mapping = {
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
            },
            "macros": [],
        }
        savings = size_savings_estimate(mapping)
        assert isinstance(savings, int)

    def test_size_savings_estimate_complex_mapping(self):
        """Test size savings on more complex mapping."""
        mapping = {
            "name": "Test Preset",
            "buttons": {
                0: {"note": 0, "channel": 1, "velocity": 100},
                1: {"note": 60, "channel": 1, "velocity": 100},
                2: {"note": 64, "channel": 1, "velocity": 100},
                3: {"note": 67, "channel": 1, "velocity": 100},
            },
            "axes": {
                0: {"cc": 0, "channel": 1},
                1: {"cc": 1, "channel": 1},
                2: {"cc": 7, "channel": 1},
            },
            "macros": [],
            "sequences": [],
        }
        savings = size_savings_estimate(mapping)
        # Should have significant savings from removing 4 default buttons,
        # 2 default axes, and 2 empty sections
        assert savings > 0
