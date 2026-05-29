"""Tests for the sustain pedal module — hold a button to emit CC values.

Pure-function tests for momentary and latch modes, threshold handling,
serialization, and state transitions.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.sustain_pedal import (
    SustainPedalConfig,
    SustainPedal,
    PEDAL_PRESETS,
)


# ─────────────────────────────────────────────────────────────────────
# PEDAL_PRESETS
# ─────────────────────────────────────────────────────────────────────


def test_pedal_presets_contains_expected_ccs():
    """Verify all standard MIDI pedal presets are defined."""
    assert "sustain" in PEDAL_PRESETS
    assert "sostenuto" in PEDAL_PRESETS
    assert "soft" in PEDAL_PRESETS
    assert "legato" in PEDAL_PRESETS
    assert "hold2" in PEDAL_PRESETS
    assert "expression" in PEDAL_PRESETS


def test_pedal_presets_values():
    """Check the CC numbers match MIDI spec."""
    assert PEDAL_PRESETS["sustain"] == 64
    assert PEDAL_PRESETS["sostenuto"] == 66
    assert PEDAL_PRESETS["soft"] == 67
    assert PEDAL_PRESETS["legato"] == 68
    assert PEDAL_PRESETS["hold2"] == 69
    assert PEDAL_PRESETS["expression"] == 11


# ─────────────────────────────────────────────────────────────────────
# SustainPedalConfig clamping
# ─────────────────────────────────────────────────────────────────────


def test_config_clamps_cc_to_0_127():
    """CC values are clamped to the valid MIDI range."""
    cfg = SustainPedalConfig(cc=-10)
    assert cfg.cc == 0
    cfg = SustainPedalConfig(cc=200)
    assert cfg.cc == 127


def test_config_clamps_channel_to_1_16():
    """Channel is clamped to 1..16."""
    cfg = SustainPedalConfig(channel=0)
    assert cfg.channel == 1
    cfg = SustainPedalConfig(channel=20)
    assert cfg.channel == 16


def test_config_clamps_pressed_released_values():
    """Pressed and released values are clamped to 0..127."""
    cfg = SustainPedalConfig(pressed_value=200, released_value=-5)
    assert cfg.pressed_value == 127
    assert cfg.released_value == 0


def test_config_clamps_half_pedal_threshold():
    """Half-pedal threshold is clamped to 0..1."""
    cfg = SustainPedalConfig(half_pedal_threshold=-0.5)
    assert cfg.half_pedal_threshold == 0.0
    cfg = SustainPedalConfig(half_pedal_threshold=2.0)
    assert cfg.half_pedal_threshold == 1.0


# ─────────────────────────────────────────────────────────────────────
# SustainPedalConfig serialization
# ─────────────────────────────────────────────────────────────────────


def test_config_to_dict():
    """Config serializes to a dictionary."""
    cfg = SustainPedalConfig(
        enabled=True,
        cc=64,
        channel=5,
        pressed_value=100,
        released_value=10,
        half_pedal_threshold=0.3,
        latch=True,
    )
    d = cfg.to_dict()
    assert d["enabled"] is True
    assert d["cc"] == 64
    assert d["channel"] == 5
    assert d["pressed_value"] == 100
    assert d["released_value"] == 10
    assert d["half_pedal_threshold"] == pytest.approx(0.3)
    assert d["latch"] is True


def test_config_from_dict():
    """Config deserializes from a dictionary."""
    d = {
        "enabled": True,
        "cc": 66,
        "channel": 3,
        "pressed_value": 127,
        "released_value": 0,
        "half_pedal_threshold": 0.5,
        "latch": False,
    }
    cfg = SustainPedalConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.cc == 66
    assert cfg.channel == 3
    assert cfg.pressed_value == 127
    assert cfg.released_value == 0
    assert cfg.half_pedal_threshold == pytest.approx(0.5)
    assert cfg.latch is False


def test_config_round_trip():
    """Config survives a to_dict -> from_dict round trip."""
    original = SustainPedalConfig(
        enabled=True,
        cc=67,
        channel=8,
        pressed_value=120,
        released_value=5,
        half_pedal_threshold=0.7,
        latch=True,
    )
    restored = SustainPedalConfig.from_dict(original.to_dict())
    assert restored.enabled == original.enabled
    assert restored.cc == original.cc
    assert restored.channel == original.channel
    assert restored.pressed_value == original.pressed_value
    assert restored.released_value == original.released_value
    assert restored.half_pedal_threshold == pytest.approx(original.half_pedal_threshold)
    assert restored.latch == original.latch


# ─────────────────────────────────────────────────────────────────────
# Momentary mode (latch=False)
# ─────────────────────────────────────────────────────────────────────


def test_momentary_pressure_0_returns_none_initially():
    """No pressure at start returns None."""
    cfg = SustainPedalConfig(enabled=True, latch=False)
    pedal = SustainPedal(cfg)
    assert pedal.update(0.0) is None


def test_momentary_pressure_1_emits_pressed_value():
    """Transition from 0 to 1 pressure emits pressed_value."""
    cfg = SustainPedalConfig(enabled=True, latch=False, pressed_value=127)
    pedal = SustainPedal(cfg)
    assert pedal.update(0.0) is None
    assert pedal.update(1.0) == 127


def test_momentary_sustained_pressure_returns_none():
    """Holding pressure at 1 returns None (no change)."""
    cfg = SustainPedalConfig(enabled=True, latch=False)
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 127
    assert pedal.update(1.0) is None


def test_momentary_release_emits_released_value():
    """Transition from held to 0 emits released_value."""
    cfg = SustainPedalConfig(enabled=True, latch=False, released_value=0)
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 127
    assert pedal.update(0.0) == 0


def test_momentary_full_cycle():
    """Full pressure cycle: 0 → 1 → 1 → 0."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        pressed_value=127,
        released_value=0,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(0.0) is None  # Initial state
    assert pedal.update(1.0) == 127   # Press
    assert pedal.update(1.0) is None  # Hold
    assert pedal.update(0.0) == 0     # Release


# ─────────────────────────────────────────────────────────────────────
# Latch mode (latch=True)
# ─────────────────────────────────────────────────────────────────────


def test_latch_first_press_emits_pressed_value():
    """First press in latch mode toggles sustain on."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=True,
        pressed_value=127,
        released_value=0,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 127


def test_latch_release_after_press_returns_none():
    """Releasing the button in latch mode returns None (state persists)."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=True,
        pressed_value=127,
        released_value=0,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 127  # First press: toggle on
    assert pedal.update(0.0) is None # Release: sustain stays on


def test_latch_second_press_emits_released_value():
    """Second press in latch mode toggles sustain off."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=True,
        pressed_value=127,
        released_value=0,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 127  # Press 1: on
    assert pedal.update(0.0) is None # Release
    assert pedal.update(1.0) == 0    # Press 2: off


def test_latch_full_cycle():
    """Full latch cycle: press (on) → release → press (off) → release."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=True,
        pressed_value=127,
        released_value=0,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 127  # Press: toggle on
    assert pedal.update(0.0) is None # Release: no output
    assert pedal.update(1.0) == 0    # Press: toggle off
    assert pedal.update(0.0) is None # Release: no output


def test_latch_holding_after_toggle_does_nothing():
    """Holding the button after toggling on returns None."""
    cfg = SustainPedalConfig(enabled=True, latch=True, pressed_value=127)
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 127  # Press: on
    assert pedal.update(1.0) is None # Hold: no output
    assert pedal.update(1.0) is None # Still holding: no output


# ─────────────────────────────────────────────────────────────────────
# Half-pedal threshold
# ─────────────────────────────────────────────────────────────────────


def test_half_pedal_threshold_blocks_low_pressure():
    """Pressure below threshold does not trigger."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        half_pedal_threshold=0.5,
        pressed_value=127,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(0.4) is None  # Below threshold


def test_half_pedal_threshold_allows_high_pressure():
    """Pressure above threshold triggers normally."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        half_pedal_threshold=0.5,
        pressed_value=127,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(0.6) == 127  # Above threshold


def test_half_pedal_threshold_at_exact_boundary():
    """Pressure exactly at threshold is considered not-pressed."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        half_pedal_threshold=0.5,
        pressed_value=127,
    )
    pedal = SustainPedal(cfg)
    # Threshold is 0.5; pressure 0.5 is NOT > 0.5, so should not trigger
    assert pedal.update(0.5) is None


def test_half_pedal_threshold_zero_accepts_any_nonzero():
    """Threshold of 0 (or negative after clamping) treats any non-zero as pressed."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        half_pedal_threshold=0.0,
        pressed_value=127,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(0.01) == 127  # Even tiny pressure


def test_half_pedal_threshold_high_value():
    """High threshold requires very deep press."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        half_pedal_threshold=0.9,
        pressed_value=127,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(0.85) is None  # Below 0.9
    assert pedal.update(0.95) == 127   # Above 0.9


# ─────────────────────────────────────────────────────────────────────
# force_release
# ─────────────────────────────────────────────────────────────────────


def test_force_release_returns_released_value():
    """force_release returns the configured released_value."""
    cfg = SustainPedalConfig(released_value=0)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)  # Press
    assert pedal.force_release() == 0


def test_force_release_clears_held_state():
    """After force_release, the pedal is no longer held."""
    cfg = SustainPedalConfig(enabled=True, latch=False, pressed_value=127)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)  # Press
    pedal.force_release()
    # Next pressure at 0 should return None (no transition)
    assert pedal.update(0.0) is None


def test_force_release_clears_latch_state():
    """After force_release in latch mode, latch is reset."""
    cfg = SustainPedalConfig(enabled=True, latch=True, pressed_value=127)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)  # Press: latch on
    pedal.force_release()
    # Next press should toggle on again (not off)
    assert pedal.update(1.0) == 127


def test_force_release_during_latch_hold():
    """force_release clears latch state even while button is still held."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=True,
        pressed_value=127,
        released_value=0,
    )
    pedal = SustainPedal(cfg)
    pedal.update(1.0)  # Press: latch on
    # Without releasing, force a reset
    assert pedal.force_release() == 0
    # If we release now, nothing happens
    assert pedal.update(0.0) is None
    # Next press should toggle on again
    assert pedal.update(1.0) == 127


# ─────────────────────────────────────────────────────────────────────
# is_active
# ─────────────────────────────────────────────────────────────────────


def test_is_active_momentary_idle():
    """In momentary mode, is_active is False when idle."""
    cfg = SustainPedalConfig(enabled=True, latch=False)
    pedal = SustainPedal(cfg)
    pedal.update(0.0)
    assert pedal.is_active() is False


def test_is_active_momentary_held():
    """In momentary mode, is_active is True when held."""
    cfg = SustainPedalConfig(enabled=True, latch=False)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)
    assert pedal.is_active() is True


def test_is_active_momentary_released():
    """In momentary mode, is_active is False after release."""
    cfg = SustainPedalConfig(enabled=True, latch=False)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)
    pedal.update(0.0)
    assert pedal.is_active() is False


def test_is_active_latch_off():
    """In latch mode, is_active is False when latched off."""
    cfg = SustainPedalConfig(enabled=True, latch=True)
    pedal = SustainPedal(cfg)
    pedal.update(0.0)
    assert pedal.is_active() is False


def test_is_active_latch_on():
    """In latch mode, is_active is True when latched on."""
    cfg = SustainPedalConfig(enabled=True, latch=True)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)  # Press: toggle on
    assert pedal.is_active() is True


def test_is_active_latch_on_after_release():
    """In latch mode, is_active persists even after button release."""
    cfg = SustainPedalConfig(enabled=True, latch=True)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)  # Press: on
    pedal.update(0.0)  # Release
    assert pedal.is_active() is True  # Still on


def test_is_active_latch_toggled_off():
    """In latch mode, is_active is False after second press."""
    cfg = SustainPedalConfig(enabled=True, latch=True)
    pedal = SustainPedal(cfg)
    pedal.update(1.0)  # Press 1: on
    pedal.update(0.0)  # Release
    pedal.update(1.0)  # Press 2: off
    assert pedal.is_active() is False


# ─────────────────────────────────────────────────────────────────────
# Custom values
# ─────────────────────────────────────────────────────────────────────


def test_custom_pressed_released_values():
    """Custom pressed/released values work correctly."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        pressed_value=100,
        released_value=10,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(1.0) == 100
    assert pedal.update(0.0) == 10


def test_custom_cc_channel_in_config():
    """Config correctly stores custom CC and channel."""
    cfg = SustainPedalConfig(cc=67, channel=5)
    assert cfg.cc == 67
    assert cfg.channel == 5


# ─────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────


def test_rapid_pressure_changes():
    """Rapid pressure changes are handled correctly."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        pressed_value=127,
        released_value=0,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(0.0) is None
    assert pedal.update(1.0) == 127   # Press
    assert pedal.update(0.0) == 0     # Release
    assert pedal.update(1.0) == 127   # Press again
    assert pedal.update(0.0) == 0     # Release again


def test_float_precision_in_threshold():
    """Threshold comparison works with typical float precision."""
    cfg = SustainPedalConfig(
        enabled=True,
        latch=False,
        half_pedal_threshold=0.5,
    )
    pedal = SustainPedal(cfg)
    assert pedal.update(0.50001) == 127  # Just above 0.5
    pedal = SustainPedal(cfg)
    assert pedal.update(0.49999) is None  # Just below 0.5
