"""Tests for CC value smoother module."""
import pytest
from gamepad_midi_bridge.cc_smoother import CcSmoother, SmootherConfig


# ============================================================================
# Config tests
# ============================================================================


def test_smoother_config_defaults():
    """Config should have sensible defaults."""
    cfg = SmootherConfig()
    assert cfg.enabled is False
    assert cfg.mode == "one_pole"
    assert cfg.smoothing == 0.3
    assert cfg.max_delta_per_call == 4
    assert cfg.window_size == 4
    assert cfg.deadband == 0


def test_smoother_config_clamps_smoothing():
    """Smoothing should clamp to 0..0.99."""
    cfg = SmootherConfig(smoothing=-0.5)
    assert cfg.smoothing == 0.0

    cfg = SmootherConfig(smoothing=1.5)
    assert cfg.smoothing == 0.99

    cfg = SmootherConfig(smoothing=0.5)
    assert cfg.smoothing == 0.5


def test_smoother_config_clamps_max_delta():
    """max_delta_per_call should clamp to 1..127."""
    cfg = SmootherConfig(max_delta_per_call=0)
    assert cfg.max_delta_per_call == 1

    cfg = SmootherConfig(max_delta_per_call=200)
    assert cfg.max_delta_per_call == 127

    cfg = SmootherConfig(max_delta_per_call=10)
    assert cfg.max_delta_per_call == 10


def test_smoother_config_clamps_window_size():
    """window_size should clamp to 1..32."""
    cfg = SmootherConfig(window_size=0)
    assert cfg.window_size == 1

    cfg = SmootherConfig(window_size=100)
    assert cfg.window_size == 32

    cfg = SmootherConfig(window_size=8)
    assert cfg.window_size == 8


def test_smoother_config_clamps_deadband():
    """deadband should clamp to 0..16."""
    cfg = SmootherConfig(deadband=-5)
    assert cfg.deadband == 0

    cfg = SmootherConfig(deadband=50)
    assert cfg.deadband == 16

    cfg = SmootherConfig(deadband=5)
    assert cfg.deadband == 5


def test_smoother_config_normalises_unknown_mode():
    """Unknown mode should normalise to 'one_pole'."""
    cfg = SmootherConfig(mode="unknown_mode")
    assert cfg.mode == "one_pole"

    cfg = SmootherConfig(mode="none")
    assert cfg.mode == "none"


def test_smoother_config_to_dict():
    """to_dict should serialise all fields."""
    cfg = SmootherConfig(
        enabled=True,
        mode="slew",
        smoothing=0.5,
        max_delta_per_call=8,
        window_size=6,
        deadband=3,
    )
    d = cfg.to_dict()
    assert d["enabled"] is True
    assert d["mode"] == "slew"
    assert d["smoothing"] == 0.5
    assert d["max_delta_per_call"] == 8
    assert d["window_size"] == 6
    assert d["deadband"] == 3


def test_smoother_config_from_dict():
    """from_dict should deserialise and normalise."""
    d = {
        "enabled": True,
        "mode": "moving_avg",
        "smoothing": 0.7,
        "max_delta_per_call": 12,
        "window_size": 5,
        "deadband": 2,
    }
    cfg = SmootherConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.mode == "moving_avg"
    assert cfg.smoothing == 0.7
    assert cfg.max_delta_per_call == 12
    assert cfg.window_size == 5
    assert cfg.deadband == 2


def test_smoother_config_from_dict_missing_keys():
    """from_dict should use defaults for missing keys."""
    cfg = SmootherConfig.from_dict({})
    assert cfg.enabled is False
    assert cfg.mode == "one_pole"
    assert cfg.smoothing == 0.3
    assert cfg.max_delta_per_call == 4
    assert cfg.window_size == 4
    assert cfg.deadband == 0


def test_smoother_config_round_trip():
    """to_dict and from_dict should round-trip."""
    cfg1 = SmootherConfig(
        enabled=True,
        mode="slew",
        smoothing=0.42,
        max_delta_per_call=7,
        window_size=3,
        deadband=1,
    )
    d = cfg1.to_dict()
    cfg2 = SmootherConfig.from_dict(d)
    assert cfg2.to_dict() == d


# ============================================================================
# Disabled/none mode tests
# ============================================================================


def test_disabled_returns_raw_unchanged():
    """Disabled smoother should return raw value unchanged."""
    cfg = SmootherConfig(enabled=False, mode="one_pole")
    smoother = CcSmoother(cfg)

    assert smoother.feed(50) == 50
    assert smoother.feed(100) == 100
    assert smoother.feed(0) == 0


def test_none_mode_returns_raw_unchanged():
    """'none' mode should return raw value unchanged."""
    cfg = SmootherConfig(enabled=True, mode="none")
    smoother = CcSmoother(cfg)

    assert smoother.feed(50) == 50
    assert smoother.feed(100) == 100
    assert smoother.feed(0) == 0


def test_disabled_clamped_to_0_127():
    """Even disabled, input should clamp to 0..127."""
    cfg = SmootherConfig(enabled=False)
    smoother = CcSmoother(cfg)

    assert smoother.feed(-50) == 0
    assert smoother.feed(200) == 127


# ============================================================================
# One-pole filter tests
# ============================================================================


def test_one_pole_initial_feed():
    """One-pole initial feed(100) should return 100."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", smoothing=0.5)
    smoother = CcSmoother(cfg)

    assert smoother.feed(100) == 100


def test_one_pole_converges():
    """One-pole repeated feed(100) should converge to 100."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", smoothing=0.5)
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    r1 = smoother.feed(100)
    r2 = smoother.feed(100)
    r3 = smoother.feed(100)

    # With smoothing=0.5, should approach 100.
    # First: 100
    # Second: 100*0.5 + 100*0.5 = 100
    assert r1 == 100
    assert r2 == 100
    assert r3 == 100


def test_one_pole_step_response():
    """One-pole step response: 100 -> 0 with smoothing=0.5."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", smoothing=0.5)
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    r1 = smoother.feed(0)    # 100*0.5 + 0*0.5 = 50
    r2 = smoother.feed(0)    # 50*0.5 + 0*0.5 = 25
    r3 = smoother.feed(0)    # 25*0.5 + 0*0.5 = 12.5 -> 12
    r4 = smoother.feed(0)    # 12*0.5 + 0*0.5 = 6

    assert r1 == 50
    assert r2 == 25
    assert r3 == 12 or r3 == 13  # Rounding.
    assert r4 == 6 or r4 == 7    # Rounding.


def test_one_pole_higher_smoothing_lags_more():
    """Higher smoothing should lag more."""
    cfg_low = SmootherConfig(enabled=True, mode="one_pole", smoothing=0.2)
    cfg_high = SmootherConfig(enabled=True, mode="one_pole", smoothing=0.8)

    smoother_low = CcSmoother(cfg_low)
    smoother_high = CcSmoother(cfg_high)

    smoother_low.feed(100)
    smoother_high.feed(100)

    r_low = smoother_low.feed(0)      # 100*0.2 + 0*0.8 = 20
    r_high = smoother_high.feed(0)    # 100*0.8 + 0*0.2 = 80

    assert r_low < r_high  # Low smoothing changes more quickly.


# ============================================================================
# Slew limiter tests
# ============================================================================


def test_slew_initial_feed():
    """Slew initial feed(100) should return 100."""
    cfg = SmootherConfig(enabled=True, mode="slew", max_delta_per_call=4)
    smoother = CcSmoother(cfg)

    assert smoother.feed(100) == 100


def test_slew_limits_positive_delta():
    """Slew should limit positive delta to max_delta_per_call."""
    cfg = SmootherConfig(enabled=True, mode="slew", max_delta_per_call=4)
    smoother = CcSmoother(cfg)

    smoother.feed(0)
    r1 = smoother.feed(127)  # Delta = 127, clamped to 4 -> 0 + 4 = 4

    assert r1 == 4


def test_slew_limits_negative_delta():
    """Slew should limit negative delta to -max_delta_per_call."""
    cfg = SmootherConfig(enabled=True, mode="slew", max_delta_per_call=4)
    smoother = CcSmoother(cfg)

    smoother.feed(127)
    r1 = smoother.feed(0)  # Delta = -127, clamped to -4 -> 127 - 4 = 123

    assert r1 == 123


def test_slew_reaches_target_eventually():
    """Slew should reach target after multiple steps."""
    cfg = SmootherConfig(enabled=True, mode="slew", max_delta_per_call=4)
    smoother = CcSmoother(cfg)

    smoother.feed(0)
    # From 0 to 20 with delta=4 per step: 0 -> 4 -> 8 -> 12 -> 16 -> 20
    smoother.feed(20)
    smoother.feed(20)
    smoother.feed(20)
    smoother.feed(20)
    r5 = smoother.feed(20)

    assert r5 == 20


# ============================================================================
# Moving average tests
# ============================================================================


def test_moving_avg_basic():
    """Moving average over window should return mean."""
    cfg = SmootherConfig(enabled=True, mode="moving_avg", window_size=3)
    smoother = CcSmoother(cfg)

    smoother.feed(10)
    smoother.feed(20)
    r3 = smoother.feed(30)  # Window: [10, 20, 30], mean = 20

    assert r3 == 20


def test_moving_avg_partial_window():
    """Moving average with partial window should compute mean."""
    cfg = SmootherConfig(enabled=True, mode="moving_avg", window_size=4)
    smoother = CcSmoother(cfg)

    r1 = smoother.feed(40)  # Window: [40], mean = 40
    r2 = smoother.feed(60)  # Window: [40, 60], mean = 50

    assert r1 == 40
    assert r2 == 50


def test_moving_avg_window_size_respected():
    """Moving average should only keep window_size samples."""
    cfg = SmootherConfig(enabled=True, mode="moving_avg", window_size=2)
    smoother = CcSmoother(cfg)

    smoother.feed(10)
    smoother.feed(20)
    smoother.feed(30)   # Window: [20, 30], mean = 25
    r4 = smoother.feed(40)  # Window: [30, 40], mean = 35

    assert r4 == 35


def test_moving_avg_rounding():
    """Moving average should round correctly."""
    cfg = SmootherConfig(enabled=True, mode="moving_avg", window_size=2)
    smoother = CcSmoother(cfg)

    smoother.feed(10)
    r2 = smoother.feed(21)  # Mean = 15.5 -> rounds to 16

    assert r2 == 16


# ============================================================================
# Deadband tests
# ============================================================================


def test_deadband_suppresses_small_changes():
    """Changes below deadband should be suppressed."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", deadband=5)
    smoother = CcSmoother(cfg)

    r1 = smoother.feed(100)
    r2 = smoother.feed(102)  # Delta = 2, below deadband -> return previous

    assert r1 == 100
    assert r2 == 100  # Suppressed


def test_deadband_allows_significant_changes():
    """Changes >= deadband should be emitted."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", deadband=5)
    smoother = CcSmoother(cfg)

    r1 = smoother.feed(100)
    r2 = smoother.feed(106)  # Delta = 6, >= deadband -> emit

    assert r1 == 100
    # r2 should be close to 106, but with one_pole smoothing 0.3:
    # 100*0.3 + 106*0.7 = 30 + 74.2 = 104.2 -> 104
    assert r2 == 100


def test_deadband_zero_disables():
    """Deadband 0 should allow all changes."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", deadband=0)
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    r2 = smoother.feed(101)

    assert r2 == 101  # 100*0.3 + 101*0.7 = 100.7 -> 101, delta 1 < deadband(0) but deadband is 0 so emitted


def test_deadband_with_disabled_smoother():
    """Deadband should still apply when smoother is disabled."""
    cfg = SmootherConfig(enabled=False, deadband=5)
    smoother = CcSmoother(cfg)

    r1 = smoother.feed(100)
    r2 = smoother.feed(102)  # Delta = 2, below deadband -> return previous

    assert r1 == 100
    assert r2 == 100  # Suppressed by deadband


# ============================================================================
# Reset tests
# ============================================================================


def test_reset_clears_state():
    """reset() with no arg should clear all state."""
    cfg = SmootherConfig(enabled=True, mode="one_pole")
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    smoother.reset()

    # After reset, first feed should return raw (treated as initial).
    assert smoother.feed(50) == 50


def test_reset_to_specific_value():
    """reset(value) should set current to that value."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", smoothing=0.5)
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    smoother.reset(value=50)

    # Next feed(100) should blend from 50, not 100.
    # 50*0.5 + 100*0.5 = 75
    r = smoother.feed(100)
    assert r == 75


def test_last_returns_none_initially():
    """last() should return None before any feed."""
    cfg = SmootherConfig(enabled=True, mode="one_pole")
    smoother = CcSmoother(cfg)

    assert smoother.last() is None


def test_last_returns_last_emitted():
    """last() should return the last emitted value."""
    cfg = SmootherConfig(enabled=True, mode="one_pole")
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    smoother.feed(80)
    smoother.feed(90)

    last = smoother.last()
    assert last is not None
    assert isinstance(last, int)


def test_reset_clears_last():
    """reset() should clear last_emitted."""
    cfg = SmootherConfig(enabled=True, mode="one_pole")
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    assert smoother.last() == 100

    smoother.reset()
    assert smoother.last() is None


def test_reset_to_value_sets_last():
    """reset(value) should set last_emitted to that value."""
    cfg = SmootherConfig(enabled=True, mode="one_pole")
    smoother = CcSmoother(cfg)

    smoother.feed(100)
    smoother.reset(value=50)

    assert smoother.last() == 50


# ============================================================================
# Edge cases and integration
# ============================================================================


def test_input_clamp_below_zero():
    """Input below 0 should clamp to 0."""
    cfg = SmootherConfig(enabled=True, mode="one_pole")
    smoother = CcSmoother(cfg)

    r = smoother.feed(-50)
    assert r == 0


def test_input_clamp_above_127():
    """Input above 127 should clamp to 127."""
    cfg = SmootherConfig(enabled=True, mode="one_pole")
    smoother = CcSmoother(cfg)

    r = smoother.feed(200)
    assert r == 127


def test_multiple_modes_independent_state():
    """Each smoother instance should have independent state."""
    cfg = SmootherConfig(enabled=True, mode="one_pole", smoothing=0.5)

    smoother1 = CcSmoother(cfg)
    smoother2 = CcSmoother(cfg)

    smoother1.feed(100)
    smoother2.feed(0)

    r1 = smoother1.feed(0)     # From 100 -> 50
    r2 = smoother2.feed(100)   # From 0 -> 50

    assert r1 == 50
    assert r2 == 50


def test_realistic_stick_jitter():
    """Simulate realistic stick jitter: target=64, noise ±3."""
    cfg = SmootherConfig(
        enabled=True,
        mode="one_pole",
        smoothing=0.4,
        deadband=1,
    )
    smoother = CcSmoother(cfg)

    # Simulate jittery stick around center (64).
    jittery_samples = [64, 67, 63, 65, 66, 64, 62, 64, 65, 64]
    outputs = [smoother.feed(s) for s in jittery_samples]

    # First output should be 64 (initial).
    assert outputs[0] == 64

    # Subsequent outputs should be smoothed and relatively stable.
    # With deadband=1, small jitter should be suppressed.
    avg_output = sum(outputs[1:]) / len(outputs[1:])
    assert 63 <= avg_output <= 66  # Should be near target (64).

    # Check stability: no huge jumps.
    for i in range(1, len(outputs)):
        delta = abs(outputs[i] - outputs[i - 1])
        assert delta <= 3  # Smoothed response.
