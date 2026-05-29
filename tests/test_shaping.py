"""Tests for the shaping module — pure-function input transforms.

Trigger modes (linear / ceiling / inverted / latch) plus the curve, stick,
polar, and touchpad helpers all live here. Bridge integration is not tested
at this layer; this file proves the math is correct in isolation.
"""
from __future__ import annotations

import math

import pytest

from gamepad_midi_bridge import shaping


# ─────────────────────────────────────────────────────────────────────
# Trigger normalisation
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (-1.0, 0.0),     # DInput rest position
    (-0.5, 0.25),    # mid-press, DInput-style report
    (0.0, 0.0),      # XInput rest, OR DInput mid-press both map to 0 cleanly
    (0.5, 0.5),      # mid-press, XInput-style report
    (1.0, 1.0),      # full press
    (-2.0, 0.0),     # out of range below
    (2.0, 1.0),      # out of range above
])
def test_normalise_trigger_pressure(raw, expected):
    assert shaping.normalise_trigger_pressure(raw) == pytest.approx(expected, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────
# Trigger shaping — linear (default)
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pressure,expected_cc", [
    (0.0, 0),
    (0.5, 64),
    (1.0, 127),
])
def test_trigger_linear(pressure, expected_cc):
    assert shaping.apply_trigger(pressure, mode="linear") == expected_cc


def test_trigger_default_mode_is_linear():
    """No mode argument should match `linear` behaviour exactly."""
    for p in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert shaping.apply_trigger(p) == shaping.apply_trigger(p, mode="linear")


# ─────────────────────────────────────────────────────────────────────
# Trigger shaping — ceiling
# ─────────────────────────────────────────────────────────────────────

def test_trigger_ceiling_clamps_full_press():
    """At pressure=1, ceiling-mode output should equal the ceiling value."""
    for ceiling in (32, 64, 100, 127):
        assert shaping.apply_trigger(1.0, mode="ceiling", ceiling=ceiling) == ceiling


def test_trigger_ceiling_scales_linearly():
    """Half-press at ceiling=80 should give 40."""
    assert shaping.apply_trigger(0.5, mode="ceiling", ceiling=80) == 40


def test_trigger_ceiling_zero_press_is_zero():
    """No matter the ceiling, rest position is 0."""
    assert shaping.apply_trigger(0.0, mode="ceiling", ceiling=64) == 0


def test_trigger_ceiling_out_of_range_clamped():
    """Cap arg outside 0..127 is silently clamped to the legal range."""
    assert shaping.apply_trigger(1.0, mode="ceiling", ceiling=200) == 127
    assert shaping.apply_trigger(1.0, mode="ceiling", ceiling=-10) == 0


# ─────────────────────────────────────────────────────────────────────
# Trigger shaping — inverted
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pressure,expected_cc", [
    (0.0, 127),      # rest = max
    (0.5, 64),       # mid-press = mid-CC
    (1.0, 0),        # full press = 0
])
def test_trigger_inverted(pressure, expected_cc):
    assert shaping.apply_trigger(pressure, mode="inverted") == expected_cc


# ─────────────────────────────────────────────────────────────────────
# Trigger shaping — latch (the only stateful mode)
# ─────────────────────────────────────────────────────────────────────

def test_trigger_latch_toggles_on_threshold_crossing():
    state = shaping.TriggerState()
    # Below threshold → off.
    assert shaping.apply_trigger(0.2, mode="latch", state=state) == 0
    # Cross above threshold → latches on.
    assert shaping.apply_trigger(0.8, mode="latch", state=state) == 127
    assert state.latched_on is True
    # Releasing back below threshold → unlatches.
    assert shaping.apply_trigger(0.1, mode="latch", state=state) == 0
    assert state.latched_on is False


def test_trigger_latch_holds_through_partial_release():
    """Once latched on, dropping pressure into the lower hysteresis band
    (within ±0.025 of the threshold) keeps the latch on. Dropping past it
    flips off — that's a separate test."""
    state = shaping.TriggerState()
    shaping.apply_trigger(0.9, mode="latch", state=state)
    # Default threshold is 0.5, lower hysteresis band ends at 0.475.
    # Drop pressure to 0.48 — inside the band, should stay latched.
    assert shaping.apply_trigger(0.48, mode="latch", state=state) == 127
    assert state.latched_on is True


def test_trigger_latch_hysteresis_prevents_chatter():
    """Pressure held right at the threshold shouldn't flip-flop the latch."""
    state = shaping.TriggerState()
    threshold = 0.5
    # Right at threshold but not quite above: stays off.
    assert shaping.apply_trigger(threshold + 0.02, mode="latch",
                                  latch_threshold=threshold, state=state) == 0
    # Past the upper hysteresis band: latches on.
    assert shaping.apply_trigger(threshold + 0.05, mode="latch",
                                  latch_threshold=threshold, state=state) == 127
    # Slight release inside the lower hysteresis band: STAYS on.
    assert shaping.apply_trigger(threshold - 0.02, mode="latch",
                                  latch_threshold=threshold, state=state) == 127
    # Past the lower hysteresis band: latches off.
    assert shaping.apply_trigger(threshold - 0.05, mode="latch",
                                  latch_threshold=threshold, state=state) == 0


def test_trigger_latch_handles_missing_state():
    """A latch call without a state arg shouldn't crash — uses an ephemeral one."""
    result = shaping.apply_trigger(0.9, mode="latch")
    assert result == 127


# ─────────────────────────────────────────────────────────────────────
# Modifier gate — pure-function "should this trigger emit?" decision
# ─────────────────────────────────────────────────────────────────────

def test_gate_held_emits_normally():
    """When the gate button is held, the trigger emits its current value."""
    should_emit, send_release = shaping.gate_decision(gate_held=True, was_held=True)
    assert should_emit is True
    assert send_release is False


def test_gate_press_edge_emits():
    """When the user FIRST presses the gate (was off, now on), emit immediately."""
    should_emit, send_release = shaping.gate_decision(gate_held=True, was_held=False)
    assert should_emit is True
    assert send_release is False


def test_gate_release_edge_emits_rest_value():
    """When the gate releases (was on, now off), emit ONCE with the rest value
    so the receiver isn't left stuck on the last trigger value forever."""
    should_emit, send_release = shaping.gate_decision(gate_held=False, was_held=True)
    assert should_emit is True
    assert send_release is True


def test_gate_silent_when_never_held():
    """No gate press at all (was off, still off) means no emit — input ignored."""
    should_emit, send_release = shaping.gate_decision(gate_held=False, was_held=False)
    assert should_emit is False
    assert send_release is False


def test_gate_release_only_fires_once():
    """Simulate two ticks of no-hold: first releases (emit once), second is silent."""
    # Tick 1: gate just released.
    e1, r1 = shaping.gate_decision(gate_held=False, was_held=True)
    # Tick 2: still ungated, no longer "was held".
    e2, r2 = shaping.gate_decision(gate_held=False, was_held=False)
    assert (e1, r1) == (True, True)
    assert (e2, r2) == (False, False)


# ─────────────────────────────────────────────────────────────────────
# Curves — linear / exp / log / s-curve all preserve endpoints
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("curve", ["linear", "exponential", "logarithmic", "s-curve"])
def test_curve_preserves_endpoints(curve):
    assert shaping.apply_curve(0.0, curve) == pytest.approx(0.0, abs=1e-3)
    assert shaping.apply_curve(1.0, curve) == pytest.approx(1.0, abs=1e-3)


def test_exponential_curve_is_below_linear_mid_range():
    """Exponential bend: slow near rest, sharp near full → mid-input < linear."""
    assert shaping.apply_curve(0.5, "exponential", amount=1.0) < 0.5


def test_logarithmic_curve_is_above_linear_mid_range():
    """Logarithmic bend: sharp near rest, slow near full → mid-input > linear."""
    assert shaping.apply_curve(0.5, "logarithmic", amount=1.0) > 0.5


# ─────────────────────────────────────────────────────────────────────
# Stick shaping — deadzone, outer clamp, curves
# ─────────────────────────────────────────────────────────────────────

def test_stick_inner_deadzone_snaps_to_zero():
    assert shaping.apply_stick_shape(0.03, inner_deadzone=0.05) == 0.0
    assert shaping.apply_stick_shape(-0.03, inner_deadzone=0.05) == 0.0


def test_stick_outside_deadzone_restretches():
    """Just past the deadzone should give a near-zero magnitude, not the raw value."""
    result = shaping.apply_stick_shape(0.10, inner_deadzone=0.05)
    assert 0.0 < result < 0.10


def test_stick_outer_clamp_pegs_to_full():
    """Top 10% of travel should saturate to ±1."""
    assert shaping.apply_stick_shape(0.91, inner_deadzone=0.0, outer_clamp=0.1) == 1.0
    assert shaping.apply_stick_shape(-0.91, inner_deadzone=0.0, outer_clamp=0.1) == -1.0


def test_stick_sign_preserved_through_curve():
    """Curves apply to magnitude; sign stays."""
    assert shaping.apply_stick_shape(-0.7, curve="exponential", curve_amount=0.8) < 0


# ─────────────────────────────────────────────────────────────────────
# Polar — angle + magnitude from X/Y
# ─────────────────────────────────────────────────────────────────────

def test_polar_centre_is_zero_magnitude():
    angle, mag = shaping.apply_polar(0.0, 0.0)
    assert mag == 0.0


def test_polar_full_right_is_angle_zero():
    angle, mag = shaping.apply_polar(1.0, 0.0, deadzone=0.0)
    assert angle == pytest.approx(0.0, abs=1e-3)
    assert mag == pytest.approx(1.0, abs=1e-3)


def test_polar_full_up_is_angle_quarter():
    """+Y goes counter-clockwise from +X → quarter turn = 0.25 of the unit circle."""
    angle, mag = shaping.apply_polar(0.0, 1.0, deadzone=0.0)
    assert angle == pytest.approx(0.25, abs=1e-3)
    assert mag == pytest.approx(1.0, abs=1e-3)


def test_polar_deadzone_holds_angle_centre():
    """Inside the deadzone, angle should be a safe 0.5 (not snapping to 0)."""
    angle, mag = shaping.apply_polar(0.01, 0.01, deadzone=0.05)
    assert mag == 0.0
    assert angle == 0.5


# ─────────────────────────────────────────────────────────────────────
# Touchpad axis — absolute vs relative
# ─────────────────────────────────────────────────────────────────────

def test_touchpad_absolute_passes_through():
    assert shaping.apply_touchpad_axis(0.3, mode="absolute") == pytest.approx(0.3, abs=1e-3)


def test_touchpad_relative_nudges_prev_value():
    """Finger to the right of centre should nudge prev_value upward."""
    new_v = shaping.apply_touchpad_axis(0.8, mode="relative", prev_value=0.5)
    assert new_v > 0.5


def test_touchpad_relative_left_nudges_down():
    new_v = shaping.apply_touchpad_axis(0.2, mode="relative", prev_value=0.5)
    assert new_v < 0.5


def test_touchpad_relative_clamps_at_bounds():
    """Repeated nudges shouldn't push past 0..1."""
    v = 0.99
    for _ in range(100):
        v = shaping.apply_touchpad_axis(1.0, mode="relative", prev_value=v)
    assert v <= 1.0
    v = 0.01
    for _ in range(100):
        v = shaping.apply_touchpad_axis(0.0, mode="relative", prev_value=v)
    assert v >= 0.0


def test_touchpad_centre_deadzone_snaps():
    """In absolute mode with a centre deadzone, values near 0.5 lock to 0.5."""
    assert shaping.apply_touchpad_axis(0.51, mode="absolute",
                                        inner_deadzone=0.05) == 0.5
    assert shaping.apply_touchpad_axis(0.49, mode="absolute",
                                        inner_deadzone=0.05) == 0.5


# ─────────────────────────────────────────────────────────────────────
# Trigger crossfade — opposing CC pair from single trigger
# ─────────────────────────────────────────────────────────────────────

def test_trigger_crossfade_linear_rest_is_zero_max():
    """At pressure=0 with linear curve, cc_a=0, cc_b=127."""
    cc_a, cc_b = shaping.apply_trigger_crossfade(0.0, curve=1.0)
    assert cc_a == 0
    assert cc_b == 127


def test_trigger_crossfade_linear_full_press_is_max_zero():
    """At pressure=1 with linear curve, cc_a=127, cc_b=0."""
    cc_a, cc_b = shaping.apply_trigger_crossfade(1.0, curve=1.0)
    assert cc_a == 127
    assert cc_b == 0


def test_trigger_crossfade_linear_midpoint():
    """At pressure=0.5 with linear curve, cc_a and cc_b should sum to 127."""
    cc_a, cc_b = shaping.apply_trigger_crossfade(0.5, curve=1.0)
    assert cc_a + cc_b == 127
    # Near 64/63 split
    assert 63 <= cc_a <= 65
    assert 62 <= cc_b <= 64


def test_trigger_crossfade_sum_always_127():
    """For any pressure and curve, cc_a + cc_b should equal 127."""
    for p in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0):
        for curve in (0.5, 1.0, 2.0):
            cc_a, cc_b = shaping.apply_trigger_crossfade(p, curve=curve)
            assert cc_a + cc_b == 127, f"Failed for pressure={p}, curve={curve}"


def test_trigger_crossfade_exponential_biases_low():
    """Curve=2.0 (exponential) should bias cc_a toward low initially."""
    cc_a_linear, _ = shaping.apply_trigger_crossfade(0.5, curve=1.0)
    cc_a_exp, _ = shaping.apply_trigger_crossfade(0.5, curve=2.0)
    # Exponential should be lower than linear at mid-range
    assert cc_a_exp < cc_a_linear


def test_trigger_crossfade_logarithmic_biases_high():
    """Curve=0.5 (logarithmic) should bias cc_a toward high initially."""
    cc_a_linear, _ = shaping.apply_trigger_crossfade(0.5, curve=1.0)
    cc_a_log, _ = shaping.apply_trigger_crossfade(0.5, curve=0.5)
    # Logarithmic should be higher than linear at mid-range
    assert cc_a_log > cc_a_linear


def test_trigger_crossfade_curve_clamps():
    """Out-of-range curve values should be clamped to 0.1..4.0."""
    # Curve too low should act like 0.1
    cc_a_low, _ = shaping.apply_trigger_crossfade(0.5, curve=-1.0)
    cc_a_min, _ = shaping.apply_trigger_crossfade(0.5, curve=0.1)
    assert cc_a_low == cc_a_min

    # Curve too high should act like 4.0
    cc_a_high, _ = shaping.apply_trigger_crossfade(0.5, curve=10.0)
    cc_a_max, _ = shaping.apply_trigger_crossfade(0.5, curve=4.0)
    assert cc_a_high == cc_a_max


def test_trigger_crossfade_pressure_clamps():
    """Pressure outside 0..1 should be clamped."""
    cc_a_neg, cc_b_neg = shaping.apply_trigger_crossfade(-0.5, curve=1.0)
    cc_a_zero, cc_b_zero = shaping.apply_trigger_crossfade(0.0, curve=1.0)
    assert (cc_a_neg, cc_b_neg) == (cc_a_zero, cc_b_zero)

    cc_a_high, cc_b_high = shaping.apply_trigger_crossfade(2.0, curve=1.0)
    cc_a_one, cc_b_one = shaping.apply_trigger_crossfade(1.0, curve=1.0)
    assert (cc_a_high, cc_b_high) == (cc_a_one, cc_b_one)


def test_trigger_crossfade_values_in_range():
    """Both cc_a and cc_b should always be in 0..127."""
    import random
    random.seed(42)
    for _ in range(100):
        p = random.random()
        curve = random.uniform(0.1, 4.0)
        cc_a, cc_b = shaping.apply_trigger_crossfade(p, curve=curve)
        assert 0 <= cc_a <= 127, f"cc_a={cc_a} out of range for p={p}, curve={curve}"
        assert 0 <= cc_b <= 127, f"cc_b={cc_b} out of range for p={p}, curve={curve}"
