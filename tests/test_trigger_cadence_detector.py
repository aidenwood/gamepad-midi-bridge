"""Tests for trigger cadence detector module."""
import pytest
from gamepad_midi_bridge.trigger_cadence_detector import (
    TriggerCadenceConfig,
    TriggerCadenceDetector,
)


# ============================================================================
# Config tests
# ============================================================================


def test_trigger_cadence_config_defaults():
    """Config should have sensible defaults."""
    cfg = TriggerCadenceConfig()
    assert cfg.tap_threshold == 0.5
    assert cfg.release_threshold == 0.1
    assert cfg.min_taps == 3
    assert cfg.max_history == 16
    assert cfg.reset_after_ms == 2000
    assert cfg.min_bpm == 30.0
    assert cfg.max_bpm == 300.0


def test_trigger_cadence_config_clamps_tap_threshold():
    """tap_threshold should clamp to 0.1..1.0."""
    cfg = TriggerCadenceConfig(tap_threshold=-0.5)
    assert cfg.tap_threshold == 0.1

    cfg = TriggerCadenceConfig(tap_threshold=1.5)
    assert cfg.tap_threshold == 1.0

    cfg = TriggerCadenceConfig(tap_threshold=0.7)
    assert cfg.tap_threshold == 0.7


def test_trigger_cadence_config_clamps_release_threshold():
    """release_threshold should clamp to 0.0..0.9."""
    cfg = TriggerCadenceConfig(release_threshold=-0.5)
    assert cfg.release_threshold == 0.0

    # Note: release_threshold > tap_threshold gets auto-corrected to be < tap_threshold.
    # So 1.5 clamps to 0.9, but then auto-corrects to < 0.5 (default tap_threshold).
    cfg = TriggerCadenceConfig(release_threshold=1.5)
    assert cfg.release_threshold < cfg.tap_threshold

    cfg = TriggerCadenceConfig(release_threshold=0.2)
    assert cfg.release_threshold == 0.2


def test_trigger_cadence_config_enforces_release_less_than_tap():
    """release_threshold must be < tap_threshold (auto-corrected)."""
    # Release > tap: should auto-fix
    cfg = TriggerCadenceConfig(tap_threshold=0.5, release_threshold=0.6)
    assert cfg.release_threshold < cfg.tap_threshold

    # Release == tap: should auto-fix
    cfg = TriggerCadenceConfig(tap_threshold=0.5, release_threshold=0.5)
    assert cfg.release_threshold < cfg.tap_threshold


def test_trigger_cadence_config_clamps_min_taps():
    """min_taps should clamp to 2..32."""
    cfg = TriggerCadenceConfig(min_taps=0)
    assert cfg.min_taps == 2

    cfg = TriggerCadenceConfig(min_taps=50)
    assert cfg.min_taps == 32

    cfg = TriggerCadenceConfig(min_taps=5)
    assert cfg.min_taps == 5


def test_trigger_cadence_config_clamps_max_history():
    """max_history should clamp to 4..256."""
    cfg = TriggerCadenceConfig(max_history=1)
    assert cfg.max_history == 4

    cfg = TriggerCadenceConfig(max_history=500)
    assert cfg.max_history == 256

    cfg = TriggerCadenceConfig(max_history=32)
    assert cfg.max_history == 32


def test_trigger_cadence_config_clamps_reset_after_ms():
    """reset_after_ms should clamp to 100..30000."""
    cfg = TriggerCadenceConfig(reset_after_ms=50)
    assert cfg.reset_after_ms == 100

    cfg = TriggerCadenceConfig(reset_after_ms=50000)
    assert cfg.reset_after_ms == 30000

    cfg = TriggerCadenceConfig(reset_after_ms=5000)
    assert cfg.reset_after_ms == 5000


def test_trigger_cadence_config_to_dict():
    """Config should serialize to dict."""
    cfg = TriggerCadenceConfig(tap_threshold=0.6, min_taps=4)
    d = cfg.to_dict()
    assert d["tap_threshold"] == 0.6
    assert d["min_taps"] == 4
    assert d["reset_after_ms"] == 2000


def test_trigger_cadence_config_from_dict():
    """Config should deserialize from dict."""
    d = {
        "tap_threshold": 0.7,
        "release_threshold": 0.2,
        "min_taps": 4,
        "max_history": 20,
        "reset_after_ms": 3000,
        "min_bpm": 20.0,
        "max_bpm": 400.0,
    }
    cfg = TriggerCadenceConfig.from_dict(d)
    assert cfg.tap_threshold == 0.7
    assert cfg.release_threshold == 0.2
    assert cfg.min_taps == 4
    assert cfg.max_history == 20
    assert cfg.reset_after_ms == 3000
    assert cfg.min_bpm == 20.0
    assert cfg.max_bpm == 400.0


def test_trigger_cadence_config_round_trip():
    """Config should round-trip through dict serialization."""
    cfg1 = TriggerCadenceConfig(tap_threshold=0.6, min_taps=5)
    d = cfg1.to_dict()
    cfg2 = TriggerCadenceConfig.from_dict(d)
    assert cfg2.tap_threshold == cfg1.tap_threshold
    assert cfg2.min_taps == cfg1.min_taps
    assert cfg2.reset_after_ms == cfg1.reset_after_ms


# ============================================================================
# Basic detection tests
# ============================================================================


def test_detector_single_press_returns_none():
    """First press (without release) should return None (only 1 tap)."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)
    result = detector.feed("L2", pressure=0.8, now_s=0.0)
    assert result is None


def test_detector_three_taps_at_half_second_spacing():
    """3 taps at 0.5s intervals should yield ~120 BPM."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Tap 1: press + release
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)

    # Tap 2: press + release
    detector.feed("L2", pressure=0.8, now_s=0.5)
    detector.feed("L2", pressure=0.0, now_s=0.6)

    # Tap 3: press (should compute BPM)
    result = detector.feed("L2", pressure=0.8, now_s=1.0)

    assert result is not None
    assert abs(result - 120.0) < 1.0  # ~120 BPM


def test_detector_three_taps_at_one_second_spacing():
    """3 taps at 1.0s intervals should yield ~60 BPM."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Tap 1: press + release
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)

    # Tap 2: press + release
    detector.feed("L2", pressure=0.8, now_s=1.0)
    detector.feed("L2", pressure=0.0, now_s=1.1)

    # Tap 3: press
    result = detector.feed("L2", pressure=0.8, now_s=2.0)

    assert result is not None
    assert abs(result - 60.0) < 1.0  # ~60 BPM


# ============================================================================
# State machine tests
# ============================================================================


def test_detector_state_stays_released_until_threshold():
    """State should stay 'released' until pressure > tap_threshold."""
    cfg = TriggerCadenceConfig(tap_threshold=0.5, min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Feed sub-threshold pressure: should stay released.
    detector.feed("L2", pressure=0.4, now_s=0.0)
    assert detector._state["L2"] == "released"

    # Still sub-threshold: should stay released.
    detector.feed("L2", pressure=0.3, now_s=0.05)
    assert detector._state["L2"] == "released"

    # Cross above threshold: should transition to pressed.
    detector.feed("L2", pressure=0.6, now_s=0.1)
    assert detector._state["L2"] == "pressed"


def test_detector_state_stays_pressed_until_release_threshold():
    """State should stay 'pressed' until pressure < release_threshold."""
    cfg = TriggerCadenceConfig(tap_threshold=0.5, release_threshold=0.1, min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Press above tap_threshold.
    detector.feed("L2", pressure=0.8, now_s=0.0)
    assert detector._state["L2"] == "pressed"

    # Release below tap but above release_threshold: should stay pressed.
    detector.feed("L2", pressure=0.3, now_s=0.05)
    assert detector._state["L2"] == "pressed"

    # Cross below release_threshold: should transition to released.
    detector.feed("L2", pressure=0.05, now_s=0.1)
    assert detector._state["L2"] == "released"


def test_detector_partial_pulls_dont_count():
    """2 partial pulls (pressure doesn't exceed tap_threshold) shouldn't count as taps."""
    cfg = TriggerCadenceConfig(tap_threshold=0.5, min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Partial pull 1: stays below threshold.
    detector.feed("L2", pressure=0.3, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)

    # Partial pull 2: stays below threshold.
    detector.feed("L2", pressure=0.4, now_s=0.5)
    detector.feed("L2", pressure=0.0, now_s=0.6)

    # Verify no taps recorded.
    assert detector.tap_count("L2") == 0


# ============================================================================
# History and reset tests
# ============================================================================


def test_detector_reset_after_ms_clears_history():
    """Gap > reset_after_ms should clear tap history before recording new tap."""
    cfg = TriggerCadenceConfig(min_taps=3, reset_after_ms=500)
    detector = TriggerCadenceDetector(cfg)

    # Tap 1 + 2 (at 0s and 0.5s, should stick around).
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)
    detector.feed("L2", pressure=0.8, now_s=0.5)
    detector.feed("L2", pressure=0.0, now_s=0.6)

    # Long gap (1.5s > 0.5s reset threshold).
    detector.feed("L2", pressure=0.8, now_s=2.0)

    # Should have reset history and only recorded 1 tap from the new sequence.
    assert detector.tap_count("L2") == 1


def test_detector_max_history_truncates():
    """Tap history should drop oldest taps when exceeding max_history."""
    cfg = TriggerCadenceConfig(min_taps=2, max_history=4, reset_after_ms=10000)
    detector = TriggerCadenceDetector(cfg)

    # Record 6 taps in quick succession (no reset gaps).
    for i in range(6):
        detector.feed("L2", pressure=0.8, now_s=float(i * 0.5))
        detector.feed("L2", pressure=0.0, now_s=float(i * 0.5 + 0.05))

    # Should have dropped the oldest taps, staying capped at max_history=4.
    # After 4 taps: len=4 (no truncation yet).
    # After 5th tap: len=5 > 4, so pop oldest → len=4.
    # After 6th tap: len=5 > 4, so pop oldest → len=4.
    assert detector.tap_count("L2") == 4
    # Verify that the retained taps are the most recent ones (taps 2, 3, 4, 5).
    assert detector._tap_times["L2"][0] >= 1.0  # Oldest retained tap is from iteration 2 or later


# ============================================================================
# Clear and state reset tests
# ============================================================================


def test_detector_clear_trigger():
    """clear(trigger) should reset only that trigger's history."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Record taps on both L2 and R2.
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)
    detector.feed("L2", pressure=0.8, now_s=0.5)
    detector.feed("L2", pressure=0.0, now_s=0.6)

    detector.feed("R2", pressure=0.8, now_s=0.0)
    detector.feed("R2", pressure=0.0, now_s=0.1)
    detector.feed("R2", pressure=0.8, now_s=0.5)
    detector.feed("R2", pressure=0.0, now_s=0.6)

    # Clear only L2.
    detector.clear("L2")

    assert detector.tap_count("L2") == 0
    assert detector.tap_count("R2") == 2


def test_detector_clear_all():
    """clear(None) should reset both triggers' history."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Record taps on both.
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)
    detector.feed("R2", pressure=0.8, now_s=0.0)
    detector.feed("R2", pressure=0.0, now_s=0.1)

    # Clear all.
    detector.clear(None)

    assert detector.tap_count("L2") == 0
    assert detector.tap_count("R2") == 0


# ============================================================================
# Tap count and BPM query tests
# ============================================================================


def test_detector_tap_count():
    """tap_count should return the number of taps for a trigger."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    detector.feed("L2", pressure=0.8, now_s=0.0)
    assert detector.tap_count("L2") == 1

    detector.feed("L2", pressure=0.0, now_s=0.1)
    assert detector.tap_count("L2") == 1  # Release doesn't increment count

    detector.feed("L2", pressure=0.8, now_s=0.5)
    assert detector.tap_count("L2") == 2

    detector.feed("L2", pressure=0.0, now_s=0.6)
    assert detector.tap_count("L2") == 2  # Release doesn't increment count


def test_detector_current_bpm():
    """current_bpm should return the last computed BPM."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Before min_taps: None.
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)
    detector.feed("L2", pressure=0.8, now_s=0.5)
    detector.feed("L2", pressure=0.0, now_s=0.6)
    assert detector.current_bpm("L2") is None

    # After min_taps: should have a BPM.
    detector.feed("L2", pressure=0.8, now_s=1.0)
    bpm = detector.current_bpm("L2")
    assert bpm is not None
    assert abs(bpm - 120.0) < 5.0


# ============================================================================
# Stability tests
# ============================================================================


def test_detector_stability_with_steady_taps():
    """stability() should return low coefficient for steady taps."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Record 3 taps at steady 0.5s intervals.
    for i in range(3):
        detector.feed("L2", pressure=0.8, now_s=float(i * 0.5))
        detector.feed("L2", pressure=0.0, now_s=float(i * 0.5 + 0.1))

    stab = detector.stability("L2")
    assert stab is not None
    assert stab < 0.1  # Should be very low (steady taps)


def test_detector_stability_with_jittery_taps():
    """stability() should return high coefficient for jittery taps."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Record 3 taps with varying intervals (0.3s, 0.5s, 0.3s, 0.5s).
    times = [0.0, 0.3, 0.8, 1.1]
    for t in times:
        detector.feed("L2", pressure=0.8, now_s=t)
        detector.feed("L2", pressure=0.0, now_s=t + 0.05)

    stab = detector.stability("L2")
    assert stab is not None
    assert stab > 0.2  # Should be higher (jittery taps)


def test_detector_stability_requires_min_taps():
    """stability() should return None if < min_taps."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    # Only 2 taps.
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)
    detector.feed("L2", pressure=0.8, now_s=0.5)
    detector.feed("L2", pressure=0.0, now_s=0.6)

    assert detector.stability("L2") is None


# ============================================================================
# Unknown trigger tests
# ============================================================================


def test_detector_ignores_unknown_trigger():
    """Unknown triggers should be ignored."""
    cfg = TriggerCadenceConfig(min_taps=3)
    detector = TriggerCadenceDetector(cfg)

    result = detector.feed("UNKNOWN", pressure=0.8, now_s=0.0)
    assert result is None

    assert detector.tap_count("UNKNOWN") == 0
    assert detector.current_bpm("UNKNOWN") is None
    assert detector.stability("UNKNOWN") is None


# ============================================================================
# BPM clamping tests
# ============================================================================


def test_detector_clamps_bpm_to_min_max():
    """BPM should be clamped to [min_bpm, max_bpm]."""
    # Very fast tapping (should clamp to max_bpm).
    cfg = TriggerCadenceConfig(min_taps=3, min_bpm=30.0, max_bpm=300.0)
    detector = TriggerCadenceDetector(cfg)

    # Record 3 taps at 0.05s intervals (~1200 BPM, should clamp to 300).
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.01)
    detector.feed("L2", pressure=0.8, now_s=0.05)
    detector.feed("L2", pressure=0.0, now_s=0.06)
    result = detector.feed("L2", pressure=0.8, now_s=0.1)

    assert result is not None
    assert result <= cfg.max_bpm

    # Very slow tapping (should clamp to min_bpm).
    detector.clear("L2")
    detector.feed("L2", pressure=0.8, now_s=0.0)
    detector.feed("L2", pressure=0.0, now_s=0.1)
    detector.feed("L2", pressure=0.8, now_s=2.0)
    detector.feed("L2", pressure=0.0, now_s=2.1)
    result = detector.feed("L2", pressure=0.8, now_s=4.0)

    assert result is not None
    assert result >= cfg.min_bpm
