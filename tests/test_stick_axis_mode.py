"""Tests for per-stick single-axis slider mode.

Collapses a stick to a vertical ("y_only") or horizontal ("x_only") fader
without disturbing its CC assignments, so flipping back restores the same
mapping. Default stays "xy" — the legacy behaviour.
"""

import pytest

from gamepad_midi_bridge.mapping import (
    STICK_AXIS_MODES,
    Mapping,
    StickConfig,
    stick_axis_is_muted,
)


class TestStickAxisModeConfig:
    """The field itself and how it round-trips."""

    def test_default_is_xy(self):
        """Default preserves legacy both-axes-live behaviour."""
        assert StickConfig().axis_mode == "xy"

    def test_known_modes(self):
        """The whitelist is exactly the three supported modes."""
        assert STICK_AXIS_MODES == {"xy", "y_only", "x_only"}

    def test_round_trips_through_dict(self):
        """A mapping saved with a mode reloads with it intact."""
        m = Mapping()
        m.left_stick.axis_mode = "y_only"
        m.right_stick.axis_mode = "x_only"
        restored = Mapping.from_dict(m.to_dict())
        assert restored.left_stick.axis_mode == "y_only"
        assert restored.right_stick.axis_mode == "x_only"

    def test_legacy_preset_without_the_field_loads_as_xy(self):
        """Presets written before this field existed must load unchanged."""
        m = Mapping()
        d = m.to_dict()
        d["left_stick"].pop("axis_mode", None)
        restored = Mapping.from_dict(d)
        assert restored.left_stick.axis_mode == "xy"

    def test_garbage_mode_degrades_to_xy(self):
        """A bad value must not produce a silently dead stick on stage."""
        m = Mapping()
        d = m.to_dict()
        d["left_stick"]["axis_mode"] = "diagonal_only"
        restored = Mapping.from_dict(d)
        assert restored.left_stick.axis_mode == "xy"


class TestStickAxisIsMuted:
    """Which axis each mode silences.

    Left stick is axes 0 (X) and 1 (Y); right stick is 2 (X) and 3 (Y).
    """

    def test_xy_mutes_nothing(self):
        for axis in (0, 1, 2, 3):
            assert stick_axis_is_muted(axis, "xy") is False

    def test_y_only_mutes_x_on_both_sticks(self):
        assert stick_axis_is_muted(0, "y_only") is True    # left X
        assert stick_axis_is_muted(1, "y_only") is False   # left Y survives
        assert stick_axis_is_muted(2, "y_only") is True    # right X
        assert stick_axis_is_muted(3, "y_only") is False   # right Y survives

    def test_x_only_mutes_y_on_both_sticks(self):
        assert stick_axis_is_muted(0, "x_only") is False
        assert stick_axis_is_muted(1, "x_only") is True
        assert stick_axis_is_muted(2, "x_only") is False
        assert stick_axis_is_muted(3, "x_only") is True

    @pytest.mark.parametrize("bad", ["", "XY", "y-only", "nonsense", None])
    def test_unknown_mode_never_mutes(self, bad):
        """Fail open: an unrecognised mode behaves as full XY."""
        for axis in (0, 1, 2, 3):
            assert stick_axis_is_muted(axis, bad) is False

    def test_the_two_sticks_are_independent(self):
        """Setting one stick to a slider must not touch the other."""
        m = Mapping()
        m.left_stick.axis_mode = "y_only"
        assert stick_axis_is_muted(0, m.left_stick.axis_mode) is True
        assert stick_axis_is_muted(2, m.right_stick.axis_mode) is False

    def test_cc_assignments_are_untouched_by_the_mode(self):
        """Flipping to a slider and back must restore the same mapping."""
        m = Mapping()
        before = dict(m.axes)
        m.left_stick.axis_mode = "y_only"
        m.left_stick.axis_mode = "xy"
        assert m.axes == before
