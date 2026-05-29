"""Tests for note_duration_stats module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_duration_stats import NoteDurationConfig, NoteDurationStats


# ---------------------------------------------------------------------------
# config: defaults and clamping
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config should have max_samples=5000."""
    cfg = NoteDurationConfig()
    assert cfg.max_samples == 5000


def test_config_clamp_max_samples_min():
    """max_samples < 100 should be clamped to 100."""
    cfg = NoteDurationConfig(max_samples=50)
    assert cfg.max_samples == 100


def test_config_clamp_max_samples_max():
    """max_samples > 200000 should be clamped to 200000."""
    cfg = NoteDurationConfig(max_samples=300000)
    assert cfg.max_samples == 200000


def test_config_to_dict():
    """to_dict should return serializable dict with max_samples."""
    cfg = NoteDurationConfig(max_samples=3000)
    d = cfg.to_dict()
    assert d["max_samples"] == 3000


def test_config_from_dict():
    """from_dict should reconstruct config from dict."""
    d = {"max_samples": 3000}
    cfg = NoteDurationConfig.from_dict(d)
    assert cfg.max_samples == 3000


def test_config_round_trip():
    """to_dict + from_dict should preserve config."""
    cfg1 = NoteDurationConfig(max_samples=2500)
    d = cfg1.to_dict()
    cfg2 = NoteDurationConfig.from_dict(d)
    assert cfg2.max_samples == cfg1.max_samples


# ---------------------------------------------------------------------------
# empty state
# ---------------------------------------------------------------------------


def test_empty_mean():
    """mean should return None on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.mean() is None


def test_empty_median():
    """median should return None on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.median() is None


def test_empty_min():
    """min_duration should return None on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.min_duration() is None


def test_empty_max():
    """max_duration should return None on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.max_duration() is None


def test_empty_percentile():
    """percentile should return None on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.percentile(50) is None


def test_empty_sample_count():
    """sample_count should return 0 on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.sample_count() == 0


def test_empty_open_count():
    """open_count should return 0 on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.open_count() == 0


def test_empty_category():
    """category should return None on empty tracker."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.category() is None


# ---------------------------------------------------------------------------
# single note
# ---------------------------------------------------------------------------


def test_record_single_note():
    """Recording one note-on + note-off should give duration 0.5."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    duration = stats.on_note_off(60, 1, 0.5)
    assert duration == 0.5
    assert stats.sample_count() == 1


def test_single_note_mean():
    """Mean of one sample should equal that sample."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    assert stats.mean() == 0.5


def test_single_note_median():
    """Median of one sample should equal that sample."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    assert stats.median() == 0.5


def test_single_note_min_max():
    """min and max of one sample should equal that sample."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    assert stats.min_duration() == 0.5
    assert stats.max_duration() == 0.5


# ---------------------------------------------------------------------------
# multiple notes
# ---------------------------------------------------------------------------


def test_mean_multiple_notes():
    """Mean of [0.1, 0.2, 0.3] should be ~0.2."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.1)
    stats.on_note_on(61, 1, 0.1)
    stats.on_note_off(61, 1, 0.3)
    stats.on_note_on(62, 1, 0.3)
    stats.on_note_off(62, 1, 0.6)
    expected_mean = (0.1 + 0.2 + 0.3) / 3
    assert abs(stats.mean() - expected_mean) < 0.001


def test_median_odd_count():
    """Median of odd count should return middle value."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    durations = [0.1, 0.2, 0.3]
    for i, dur in enumerate(durations):
        stats.on_note_on(60 + i, 1, 0.0)
        stats.on_note_off(60 + i, 1, dur)
    # Median of sorted [0.1, 0.2, 0.3] should be 0.2
    assert stats.median() == 0.2


def test_median_even_count():
    """Median of even count should return mean of two middle values."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    durations = [0.1, 0.2, 0.3, 0.4]
    for i, dur in enumerate(durations):
        stats.on_note_on(60 + i, 1, 0.0)
        stats.on_note_off(60 + i, 1, dur)
    # Median of sorted [0.1, 0.2, 0.3, 0.4] should be (0.2 + 0.3) / 2 = 0.25
    assert abs(stats.median() - 0.25) < 0.001


def test_min_max_multiple():
    """min and max should track extremes."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    durations = [0.05, 0.5, 0.1, 2.0, 0.3]
    for i, dur in enumerate(durations):
        stats.on_note_on(60 + i, 1, 0.0)
        stats.on_note_off(60 + i, 1, dur)
    assert abs(stats.min_duration() - 0.05) < 0.001
    assert abs(stats.max_duration() - 2.0) < 0.001


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------


def test_percentile_50_is_median():
    """percentile(50) should approximate median."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    durations = [0.1, 0.2, 0.3, 0.4, 0.5]
    for i, dur in enumerate(durations):
        stats.on_note_on(60 + i, 1, 0.0)
        stats.on_note_off(60 + i, 1, dur)
    p50 = stats.percentile(50)
    median = stats.median()
    # Should be very close
    assert abs(p50 - median) < 0.1


def test_percentile_0_is_min():
    """percentile(0) should be minimum."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    durations = [0.1, 0.5, 0.3]
    for i, dur in enumerate(durations):
        stats.on_note_on(60 + i, 1, 0.0)
        stats.on_note_off(60 + i, 1, dur)
    p0 = stats.percentile(0)
    min_dur = stats.min_duration()
    # p0 should equal min
    assert p0 == min_dur


def test_percentile_100_is_max():
    """percentile(100) should be maximum."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    durations = [0.1, 0.5, 0.3]
    for i, dur in enumerate(durations):
        stats.on_note_on(60 + i, 1, 0.0)
        stats.on_note_off(60 + i, 1, dur)
    p100 = stats.percentile(100)
    max_dur = stats.max_duration()
    # p100 should equal max
    assert p100 == max_dur


def test_percentile_clamping():
    """percentile values > 100 and < 0 should be clamped."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    stats.on_note_on(61, 1, 0.1)
    stats.on_note_off(61, 1, 0.3)
    # Should not raise
    p_neg = stats.percentile(-50)
    p_high = stats.percentile(150)
    assert p_neg is not None
    assert p_high is not None


# ---------------------------------------------------------------------------
# note not open
# ---------------------------------------------------------------------------


def test_note_off_unopened_note():
    """note-off for unopened note should return None."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    duration = stats.on_note_off(60, 1, 0.5)
    assert duration is None
    assert stats.sample_count() == 0


def test_note_off_wrong_channel():
    """note-off on different channel should return None."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    duration = stats.on_note_off(60, 2, 0.5)  # Different channel
    assert duration is None
    assert stats.sample_count() == 0
    assert stats.open_count() == 1  # Still open on channel 1


def test_note_off_wrong_note():
    """note-off for different note should return None."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    duration = stats.on_note_off(61, 1, 0.5)  # Different note
    assert duration is None
    assert stats.sample_count() == 0
    assert stats.open_count() == 1  # Still open for note 60


# ---------------------------------------------------------------------------
# retrigger (note-on same note twice)
# ---------------------------------------------------------------------------


def test_note_on_same_note_replaces_start_time():
    """note-on for already-open note should replace start time (retrigger)."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_on(60, 1, 1.0)  # Retrigger at 1.0
    duration = stats.on_note_off(60, 1, 1.2)
    # Should compute from 1.0, not 0.0
    assert abs(duration - 0.2) < 0.001
    assert stats.sample_count() == 1


# ---------------------------------------------------------------------------
# open_count and sample_count
# ---------------------------------------------------------------------------


def test_sample_count_increments():
    """sample_count should increment with each note-off."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.sample_count() == 0
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.1)
    assert stats.sample_count() == 1
    stats.on_note_on(61, 1, 0.1)
    stats.on_note_off(61, 1, 0.3)
    assert stats.sample_count() == 2


def test_open_count_increments_on_note_on():
    """open_count should increment with each note-on."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    assert stats.open_count() == 0
    stats.on_note_on(60, 1, 0.0)
    assert stats.open_count() == 1
    stats.on_note_on(61, 1, 0.0)
    assert stats.open_count() == 2


def test_open_count_decrements_on_note_off():
    """open_count should decrement with each note-off."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_on(61, 1, 0.0)
    assert stats.open_count() == 2
    stats.on_note_off(60, 1, 0.1)
    assert stats.open_count() == 1
    stats.on_note_off(61, 1, 0.2)
    assert stats.open_count() == 0


def test_open_count_unchanged_on_wrong_note_off():
    """open_count should not change on failed note-off."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    assert stats.open_count() == 1
    stats.on_note_off(61, 1, 0.1)  # Wrong note
    assert stats.open_count() == 1  # Unchanged


# ---------------------------------------------------------------------------
# FIFO ring buffer / max_samples
# ---------------------------------------------------------------------------


def test_max_samples_fifo_eviction():
    """Exceeding max_samples should evict oldest (FIFO)."""
    cfg = NoteDurationConfig(max_samples=105)
    stats = NoteDurationStats(cfg)
    # Record 107 notes
    for i in range(107):
        stats.on_note_on(i % 128, 1, float(i))
        stats.on_note_off(i % 128, 1, float(i) + 0.1)
    # sample_count should be clamped to max_samples
    assert stats.sample_count() == 105


def test_fifo_ring_buffer_preserves_order():
    """FIFO order should be preserved: oldest evicted first."""
    cfg = NoteDurationConfig(max_samples=103)
    stats = NoteDurationStats(cfg)
    # Record first 4 notes
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.1)
    stats.on_note_on(61, 1, 0.1)
    stats.on_note_off(61, 1, 0.2)
    stats.on_note_on(62, 1, 0.2)
    stats.on_note_off(62, 1, 0.3)
    stats.on_note_on(63, 1, 0.3)
    stats.on_note_off(63, 1, 0.4)
    assert stats.sample_count() == 4
    first_mean = stats.mean()
    assert first_mean is not None

    # Record 100 more
    for i in range(100):
        stats.on_note_on(64 + (i % 64), 1, float(100 + i))
        stats.on_note_off(64 + (i % 64), 1, float(100 + i) + 0.05)

    # Should have exactly 103 samples now
    assert stats.sample_count() == 103
    # Mean should have changed (oldest evicted)
    assert stats.mean() is not None


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_resets_samples():
    """clear should reset all samples and open notes."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    stats.on_note_on(61, 1, 0.5)
    stats.clear()
    assert stats.sample_count() == 0
    assert stats.open_count() == 0
    assert stats.mean() is None
    assert stats.median() is None


def test_clear_then_record_again():
    """Recording after clear should work normally."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    stats.clear()
    stats.on_note_on(61, 1, 0.0)
    stats.on_note_off(61, 1, 0.3)
    assert stats.sample_count() == 1
    assert abs(stats.mean() - 0.3) < 0.001


# ---------------------------------------------------------------------------
# category
# ---------------------------------------------------------------------------


def test_category_stab():
    """category should be 'stab' for mean < 0.1s."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.05)
    assert stats.category() == "stab"


def test_category_short():
    """category should be 'short' for mean < 0.3s (and >= 0.1s)."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.2)
    assert stats.category() == "short"


def test_category_medium():
    """category should be 'medium' for mean < 1.0s (and >= 0.3s)."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    assert stats.category() == "medium"


def test_category_long():
    """category should be 'long' for mean < 3.0s (and >= 1.0s)."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 2.0)
    assert stats.category() == "long"


def test_category_sustained():
    """category should be 'sustained' for mean >= 3.0s."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 5.0)
    assert stats.category() == "sustained"


def test_category_multiple_notes_average():
    """category should be based on mean of multiple notes."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    # Two notes: 0.1s and 0.3s → mean = 0.2s → "short"
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.1)
    stats.on_note_on(61, 1, 0.1)
    stats.on_note_off(61, 1, 0.4)
    # mean = (0.1 + 0.3) / 2 = 0.2
    assert stats.category() == "short"


# ---------------------------------------------------------------------------
# clamp negative duration
# ---------------------------------------------------------------------------


def test_negative_duration_clamped_to_zero():
    """If now_s < start_time (shouldn't happen), duration should clamp to 0."""
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 1.0)
    duration = stats.on_note_off(60, 1, 0.5)  # End time before start time
    assert duration == 0.0


# ---------------------------------------------------------------------------
# spec scenario
# ---------------------------------------------------------------------------


def test_spec_scenario():
    """Test the exact scenario from the spec:
    on_note_on(60,1,0) + on_note_off(60,1,0.5) → 0.5
    on_note_on(60,1,1) + on_note_off(60,1,1.2) → 0.2
    sample_count() = 2
    mean() ≈ 0.35
    category() = "medium" (0.35 is >= 0.3 and < 1.0)
    """
    cfg = NoteDurationConfig()
    stats = NoteDurationStats(cfg)
    stats.on_note_on(60, 1, 0.0)
    stats.on_note_off(60, 1, 0.5)
    stats.on_note_on(60, 1, 1.0)
    stats.on_note_off(60, 1, 1.2)
    assert stats.sample_count() == 2
    assert abs(stats.mean() - 0.35) < 0.001
    assert stats.category() == "medium"
