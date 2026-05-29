"""Tests for stick-freeze latch module."""

import pytest
from gamepad_midi_bridge.stick_freeze import StickFreezeConfig, StickFreeze


class TestStickFreezeConfig:
    """Tests for StickFreezeConfig dataclass."""

    def test_default_config(self):
        """Default config has freeze disabled, no button, toggle mode."""
        cfg = StickFreezeConfig()
        assert cfg.enabled is False
        assert cfg.freeze_button is None
        assert cfg.freeze_mode == "toggle"
        assert cfg.feedback_haptic is True

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = StickFreezeConfig(
            enabled=True,
            freeze_button=5,
            freeze_mode="hold",
            feedback_haptic=False,
        )
        assert cfg.enabled is True
        assert cfg.freeze_button == 5
        assert cfg.freeze_mode == "hold"
        assert cfg.feedback_haptic is False

    def test_unknown_freeze_mode_defaults_to_toggle(self):
        """Unknown freeze_mode is normalised to 'toggle'."""
        cfg = StickFreezeConfig(freeze_mode="unknown_mode")
        assert cfg.freeze_mode == "toggle"

    def test_to_dict(self):
        """to_dict serializes config to dictionary."""
        cfg = StickFreezeConfig(
            enabled=True,
            freeze_button=7,
            freeze_mode="hold",
            feedback_haptic=False,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["freeze_button"] == 7
        assert d["freeze_mode"] == "hold"
        assert d["feedback_haptic"] is False

    def test_from_dict(self):
        """from_dict deserializes config from dictionary."""
        d = {
            "enabled": True,
            "freeze_button": 4,
            "freeze_mode": "toggle",
            "feedback_haptic": True,
        }
        cfg = StickFreezeConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.freeze_button == 4
        assert cfg.freeze_mode == "toggle"
        assert cfg.feedback_haptic is True

    def test_from_dict_round_trip(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = StickFreezeConfig(
            enabled=True,
            freeze_button=3,
            freeze_mode="hold",
            feedback_haptic=False,
        )
        d = original.to_dict()
        restored = StickFreezeConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.freeze_button == original.freeze_button
        assert restored.freeze_mode == original.freeze_mode
        assert restored.feedback_haptic == original.feedback_haptic

    def test_from_dict_partial(self):
        """from_dict fills missing keys with defaults."""
        d = {"enabled": True}
        cfg = StickFreezeConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.freeze_button is None
        assert cfg.freeze_mode == "toggle"
        assert cfg.feedback_haptic is True


class TestStickFreezeToggleMode:
    """Tests for StickFreeze in toggle mode."""

    def test_default_not_frozen(self):
        """StickFreeze starts not frozen."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="toggle")
        sf = StickFreeze(cfg)
        assert sf.is_frozen() is False

    def test_toggle_press_alone_does_not_flip(self):
        """Button press alone (no release) does not flip freeze state."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="toggle")
        sf = StickFreeze(cfg)
        result = sf.update_button(True)
        assert result is False  # No state change
        assert sf.is_frozen() is False

    def test_toggle_press_then_release_flips_freeze_on(self):
        """Button release (press → not pressed) flips freeze on."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="toggle")
        sf = StickFreeze(cfg)
        sf.update_button(True)  # Press
        result = sf.update_button(False)  # Release
        assert result is True  # State changed — haptic feedback
        assert sf.is_frozen() is True

    def test_toggle_second_release_flips_freeze_off(self):
        """Second button release (after freeze is on) flips freeze off."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="toggle")
        sf = StickFreeze(cfg)
        sf.update_button(True)
        sf.update_button(False)  # Freeze on
        assert sf.is_frozen() is True
        sf.update_button(True)
        result = sf.update_button(False)  # Freeze off
        assert result is True
        assert sf.is_frozen() is False

    def test_toggle_multiple_presses_without_release(self):
        """Multiple presses without release do not accumulate toggles."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="toggle")
        sf = StickFreeze(cfg)
        sf.update_button(True)
        sf.update_button(True)  # Still pressed — no change
        sf.update_button(True)
        assert sf.is_frozen() is False


class TestStickFreezeHoldMode:
    """Tests for StickFreeze in hold mode."""

    def test_hold_button_pressed_freezes(self):
        """Button pressed in hold mode sets freeze = True."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="hold")
        sf = StickFreeze(cfg)
        result = sf.update_button(True)
        assert result is True  # State changed
        assert sf.is_frozen() is True

    def test_hold_button_released_unfreezes(self):
        """Button released in hold mode sets freeze = False."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="hold")
        sf = StickFreeze(cfg)
        sf.update_button(True)  # Freeze on
        result = sf.update_button(False)  # Freeze off
        assert result is True  # State changed
        assert sf.is_frozen() is False

    def test_hold_repeated_press_no_change(self):
        """Repeated button presses (no state change) return False."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="hold")
        sf = StickFreeze(cfg)
        sf.update_button(True)  # Freeze on
        result = sf.update_button(True)  # Still pressed — no change
        assert result is False
        assert sf.is_frozen() is True


class TestStickFilteringWhenUnfrozen:
    """Tests for stick filtering when unfrozen."""

    def test_filter_stick_unfrozen_returns_input(self):
        """When unfrozen, filter_stick returns the input."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        result = sf.filter_stick(0.5, 0.3)
        assert result == (0.5, 0.3)

    def test_filter_stick_unfrozen_stashes_value(self):
        """When unfrozen, filter_stick stashes the input for later freeze."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf.filter_stick(0.7, 0.2)
        # Now freeze and check we get the stashed value
        sf._frozen = True
        result = sf.filter_stick(0.9, 0.9)
        assert result == (0.7, 0.2)

    def test_filter_stick_updates_stash_on_each_call_unfrozen(self):
        """Each unfrozen filter_stick call updates the stash."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf.filter_stick(0.1, 0.2)
        sf.filter_stick(0.5, 0.6)
        # Freeze and verify latest stashed value is returned
        sf._frozen = True
        result = sf.filter_stick(0.9, 0.9)
        assert result == (0.5, 0.6)


class TestStickFilteringWhenFrozen:
    """Tests for stick filtering when frozen."""

    def test_filter_stick_frozen_returns_stashed_value(self):
        """When frozen with a stashed value, filter_stick returns that value."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf.filter_stick(0.5, 0.3)
        sf._frozen = True
        result = sf.filter_stick(0.9, 0.9)
        assert result == (0.5, 0.3)

    def test_filter_stick_frozen_ignores_new_input(self):
        """When frozen, filter_stick ignores new input and returns stashed value."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf.filter_stick(0.5, 0.3)
        sf._frozen = True
        # Call multiple times with different inputs
        result1 = sf.filter_stick(0.1, 0.1)
        result2 = sf.filter_stick(0.8, 0.8)
        result3 = sf.filter_stick(-0.5, -0.5)
        assert result1 == (0.5, 0.3)
        assert result2 == (0.5, 0.3)
        assert result3 == (0.5, 0.3)

    def test_filter_stick_frozen_no_stashed_value_stashes_and_returns(self):
        """If frozen but no stashed value, stash the input and return it."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf._frozen = True
        sf._frozen_value = None
        result = sf.filter_stick(0.4, 0.6)
        assert result == (0.4, 0.6)
        assert sf._frozen_value == (0.4, 0.6)


class TestStickFreezeReset:
    """Tests for reset functionality."""

    def test_reset_clears_frozen_state(self):
        """reset() sets _frozen = False."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf._frozen = True
        sf.reset()
        assert sf.is_frozen() is False

    def test_reset_clears_stashed_value(self):
        """reset() clears _frozen_value."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf._frozen_value = (0.5, 0.3)
        sf.reset()
        assert sf._frozen_value is None

    def test_reset_clears_button_state(self):
        """reset() clears _button_was_pressed."""
        cfg = StickFreezeConfig(enabled=True)
        sf = StickFreeze(cfg)
        sf._button_was_pressed = True
        sf.reset()
        assert sf._button_was_pressed is False


class TestStickFreezeIntegration:
    """Integration tests: button + filter combined."""

    def test_toggle_mode_full_cycle(self):
        """Full toggle cycle: press → release → freeze → press → release → unfreeze."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="toggle")
        sf = StickFreeze(cfg)

        # Stash initial value (unfrozen)
        sf.filter_stick(0.5, 0.3)
        assert sf.is_frozen() is False

        # Press and release to freeze
        sf.update_button(True)
        sf.update_button(False)
        assert sf.is_frozen() is True

        # Try to move stick — returns stashed value
        result = sf.filter_stick(0.9, 0.9)
        assert result == (0.5, 0.3)

        # Press and release to unfreeze
        sf.update_button(True)
        sf.update_button(False)
        assert sf.is_frozen() is False

        # Stick updates now reflected
        result = sf.filter_stick(0.7, 0.2)
        assert result == (0.7, 0.2)

    def test_hold_mode_full_cycle(self):
        """Full hold cycle: hold to freeze, release to unfreeze."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="hold")
        sf = StickFreeze(cfg)

        # Stash initial value
        sf.filter_stick(0.5, 0.3)
        assert sf.is_frozen() is False

        # Press to freeze
        sf.update_button(True)
        assert sf.is_frozen() is True
        assert sf.filter_stick(0.9, 0.9) == (0.5, 0.3)

        # Release to unfreeze
        sf.update_button(False)
        assert sf.is_frozen() is False
        assert sf.filter_stick(0.7, 0.2) == (0.7, 0.2)

    def test_haptic_feedback_hints_on_toggle_mode_state_change(self):
        """update_button returns True only on actual state change (toggle mode)."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="toggle")
        sf = StickFreeze(cfg)

        # Press (no change)
        assert sf.update_button(True) is False

        # Release (change — should fire haptic)
        assert sf.update_button(False) is True

        # Press again (no change)
        assert sf.update_button(True) is False

        # Release (change — should fire haptic)
        assert sf.update_button(False) is True

    def test_haptic_feedback_hints_on_hold_mode_state_change(self):
        """update_button returns True only on button state change (hold mode)."""
        cfg = StickFreezeConfig(enabled=True, freeze_mode="hold")
        sf = StickFreeze(cfg)

        # Press (change)
        assert sf.update_button(True) is True

        # Press again (no change)
        assert sf.update_button(True) is False

        # Release (change)
        assert sf.update_button(False) is True

        # Release again (no change)
        assert sf.update_button(False) is False
