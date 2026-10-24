"""Tests for touchpad-as-mouse cursor deltas.

The behaviour that matters is lift-and-replace: a touchpad reports absolute
position, so without explicit handling the cursor teleports every time the
finger is lifted and put down elsewhere.
"""

import pytest

from gamepad_midi_bridge.touchpad_mouse import (
    BASE_TRAVEL_PX,
    JITTER_EPSILON,
    MouseModeConfig,
    TouchpadMouse,
    clamp_sensitivity,
)


class TestMouseModeConfig:
    def test_defaults_are_off_and_safe(self):
        """Never grabs the system cursor without being asked."""
        cfg = MouseModeConfig()
        assert cfg.enabled is False
        assert cfg.toggle_button == 6          # Share on DualSense
        assert cfg.sensitivity == 1.0
        assert cfg.invert_y is False
        assert cfg.suppress_midi is True

    @pytest.mark.parametrize(
        "raw,expected",
        [(0.0, 0.1), (-3, 0.1), (0.05, 0.1), (1.0, 1.0), (5.0, 5.0), (99, 5.0)],
    )
    def test_sensitivity_clamped(self, raw, expected):
        assert clamp_sensitivity(raw) == expected

    @pytest.mark.parametrize("junk", ["fast", None, object()])
    def test_bad_sensitivity_falls_back(self, junk):
        assert clamp_sensitivity(junk) == 1.0


class TestMouseModeToggle:
    def test_starts_inactive_by_default(self):
        assert TouchpadMouse().active is False

    def test_starts_active_when_config_enabled(self):
        assert TouchpadMouse(MouseModeConfig(enabled=True)).active is True

    def test_toggle_flips_and_returns_state(self):
        tm = TouchpadMouse()
        assert tm.toggle() is True
        assert tm.toggle() is False

    def test_share_button_press_toggles(self):
        tm = TouchpadMouse()
        assert tm.handle_button(6, True) is True
        assert tm.active is True

    def test_release_does_not_toggle(self):
        """Only the press edge acts — holding must not thrash the mode."""
        tm = TouchpadMouse()
        tm.handle_button(6, True)
        assert tm.handle_button(6, False) is False
        assert tm.active is True

    def test_other_buttons_ignored(self):
        tm = TouchpadMouse()
        assert tm.handle_button(0, True) is False
        assert tm.active is False

    def test_toggle_button_is_configurable(self):
        tm = TouchpadMouse(MouseModeConfig(toggle_button=10))
        assert tm.handle_button(6, True) is False
        assert tm.handle_button(10, True) is True


class TestCursorDeltas:
    def _on(self, **kw):
        return TouchpadMouse(MouseModeConfig(enabled=True, **kw))

    def test_inactive_emits_nothing(self):
        tm = TouchpadMouse()
        tm.update(True, 0.1, 0.1)
        assert tm.update(True, 0.9, 0.9) == (0.0, 0.0)

    def test_no_contact_emits_nothing(self):
        tm = self._on()
        assert tm.update(False, 0.5, 0.5) == (0.0, 0.0)

    def test_first_contact_sample_emits_nothing(self):
        """Anchors the reference without moving the pointer."""
        tm = self._on()
        assert tm.update(True, 0.5, 0.5) == (0.0, 0.0)

    def test_movement_within_contact_produces_delta(self):
        tm = self._on()
        tm.update(True, 0.5, 0.5)
        dx, dy = tm.update(True, 0.6, 0.5)
        assert dx == pytest.approx(0.1 * BASE_TRAVEL_PX)
        assert dy == pytest.approx(0.0)

    def test_lift_and_replace_does_not_jump(self):
        """The whole point. Finger lifts, lands far away, cursor stays put."""
        tm = self._on()
        tm.update(True, 0.1, 0.1)
        tm.update(True, 0.2, 0.1)          # a real drag
        tm.update(False, 0.2, 0.1)         # lift
        assert tm.update(True, 0.9, 0.9) == (0.0, 0.0)   # re-seeds, no jump

    def test_drag_continues_normally_after_replace(self):
        tm = self._on()
        tm.update(True, 0.1, 0.1)
        tm.update(False, 0.1, 0.1)
        tm.update(True, 0.9, 0.9)          # re-seed
        dx, _ = tm.update(True, 0.8, 0.9)
        assert dx == pytest.approx(-0.1 * BASE_TRAVEL_PX)

    def test_sensitivity_scales_travel(self):
        slow = self._on(sensitivity=0.5)
        fast = self._on(sensitivity=2.0)
        for tm in (slow, fast):
            tm.update(True, 0.5, 0.5)
        slow_dx, _ = slow.update(True, 0.6, 0.5)
        fast_dx, _ = fast.update(True, 0.6, 0.5)
        assert fast_dx == pytest.approx(slow_dx * 4)

    def test_invert_y_flips_vertical_only(self):
        tm = self._on(invert_y=True)
        tm.update(True, 0.5, 0.5)
        dx, dy = tm.update(True, 0.6, 0.6)
        assert dx > 0
        assert dy < 0

    def test_jitter_below_epsilon_is_ignored(self):
        """A resting finger must not creep the cursor."""
        tm = self._on()
        tm.update(True, 0.5, 0.5)
        nudge = JITTER_EPSILON / 2
        assert tm.update(True, 0.5 + nudge, 0.5) == (0.0, 0.0)

    def test_slow_drag_is_not_eaten_by_the_jitter_gate(self):
        """Sub-epsilon steps must accumulate, not be discarded one by one."""
        tm = self._on()
        tm.update(True, 0.5, 0.5)
        step = JITTER_EPSILON / 2
        moved = 0.0
        for i in range(1, 11):
            dx, _ = tm.update(True, 0.5 + step * i, 0.5)
            moved += dx
        assert moved > 0

    def test_toggling_off_mid_drag_then_on_does_not_jump(self):
        tm = self._on()
        tm.update(True, 0.1, 0.1)
        tm.set_active(False)
        tm.set_active(True)
        assert tm.update(True, 0.9, 0.9) == (0.0, 0.0)

    def test_reset_drops_reference_without_changing_mode(self):
        tm = self._on()
        tm.update(True, 0.1, 0.1)
        tm.reset()
        assert tm.active is True
        assert tm.update(True, 0.9, 0.9) == (0.0, 0.0)
