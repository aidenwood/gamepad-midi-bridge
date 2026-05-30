"""Tests for note_interval_distribution module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_interval_distribution import (
    NoteIntervalDistribution,
    IntervalAnalysis,
    IntervalConfig,
    INTERVAL_NAMES,
)


# ---------------------------------------------------------------------------
# config: defaults and clamping
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config should have max_samples=50000 and fold_octaves=True."""
    cfg = IntervalConfig()
    assert cfg.max_samples == 50000
    assert cfg.fold_octaves is True


def test_config_clamp_max_samples_min():
    """max_samples < 100 should be clamped to 100."""
    cfg = IntervalConfig(max_samples=50)
    assert cfg.max_samples == 100


def test_config_clamp_max_samples_max():
    """max_samples > 1000000 should be clamped to 1000000."""
    cfg = IntervalConfig(max_samples=2000000)
    assert cfg.max_samples == 1000000


def test_config_to_dict():
    """to_dict should return serializable dict."""
    cfg = IntervalConfig(max_samples=5000, fold_octaves=False)
    d = cfg.to_dict()
    assert d["max_samples"] == 5000
    assert d["fold_octaves"] is False


def test_config_from_dict():
    """from_dict should reconstruct config."""
    d = {"max_samples": 5000, "fold_octaves": False}
    cfg = IntervalConfig.from_dict(d)
    assert cfg.max_samples == 5000
    assert cfg.fold_octaves is False


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: empty state
# ---------------------------------------------------------------------------


def test_analyzer_init_empty():
    """Newly initialized analyzer should have no intervals."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    assert analyzer.total() == 0


def test_analyze_empty():
    """Analyze on empty analyzer should return None for dominant/mean."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    result = analyzer.analyze()
    assert result.dominant_interval is None
    assert result.dominant_name is None
    assert result.mean_interval is None
    assert result.largest_interval is None
    assert result.total_intervals == 0
    assert result.melodic_ratio == 0.0


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: single note (no interval yet)
# ---------------------------------------------------------------------------


def test_record_single_note():
    """Recording one note should not produce any interval."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    assert analyzer.total() == 0
    result = analyzer.analyze()
    assert result.total_intervals == 0
    assert result.dominant_interval is None


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: two notes (one interval)
# ---------------------------------------------------------------------------


def test_record_two_notes_major_second():
    """60 -> 62 should produce interval 2 (maj2)."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(62)
    result = analyzer.analyze()
    assert result.total_intervals == 1
    assert result.dominant_interval == 2
    assert result.dominant_name == "maj2"
    assert result.mean_interval == 2.0
    assert result.largest_interval == 2


def test_record_two_notes_perfect_fifth():
    """60 -> 67 should produce interval 7 (perf5)."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(67)
    result = analyzer.analyze()
    assert result.total_intervals == 1
    assert result.dominant_interval == 7
    assert result.dominant_name == "perf5"


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: multiple intervals
# ---------------------------------------------------------------------------


def test_record_sequence_fifths():
    """60 -> 67 -> 60 should produce two intervals of 7 (perf5)."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(67)
    analyzer.record(60)
    result = analyzer.analyze()
    assert result.total_intervals == 2
    assert result.dominant_interval == 7
    assert result.dominant_name == "perf5"
    assert result.interval_counts[7] == 2
    assert result.mean_interval == 7.0


def test_record_stepwise_sequence():
    """60 -> 62 -> 64 -> 67 -> 64 -> 62 -> 60 should analyze melody."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    sequence = [60, 62, 64, 67, 64, 62, 60]
    for note in sequence:
        analyzer.record(note)
    result = analyzer.analyze()
    # Intervals: 2, 2, 3, 3, 2, 2
    assert result.total_intervals == 6
    expected_intervals = [2, 2, 3, 3, 2, 2]
    for iv in expected_intervals:
        assert result.interval_counts[iv] > 0
    # Dominant should be 2 (appears 4 times)
    assert result.dominant_interval == 2
    assert result.dominant_name == "maj2"
    # Mean should be (2+2+3+3+2+2)/6 = 14/6 ≈ 2.33
    assert result.mean_interval == pytest.approx(14 / 6, rel=0.01)


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: downward intervals (absolute value)
# ---------------------------------------------------------------------------


def test_downward_interval():
    """72 -> 60 should produce interval 12 (octave down, abs value)."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(72)
    analyzer.record(60)
    result = analyzer.analyze()
    assert result.total_intervals == 1
    assert result.dominant_interval == 12
    assert result.dominant_name == "octave"


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: melodic_ratio (stepwise feel)
# ---------------------------------------------------------------------------


def test_melodic_ratio_all_stepwise():
    """All intervals <= 2 should give melodic_ratio ≈ 1.0."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    # 60 -> 61 -> 62 -> 63 -> 64 (all semitones or whole steps)
    for note in [60, 61, 62, 63, 64]:
        analyzer.record(note)
    result = analyzer.analyze()
    # Intervals: 1, 1, 1, 1 (all <= 2)
    assert result.melodic_ratio == pytest.approx(1.0)


def test_melodic_ratio_no_stepwise():
    """No intervals <= 2 should give melodic_ratio ≈ 0.0."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    # 60 -> 67 -> 60 -> 67 (all perfect 5ths = 7)
    for note in [60, 67, 60, 67]:
        analyzer.record(note)
    result = analyzer.analyze()
    # Intervals: 7, 7, 7 (all > 2)
    assert result.melodic_ratio == pytest.approx(0.0)


def test_melodic_ratio_mixed():
    """Mixed intervals should give ratio between 0 and 1."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    # 60 -> 62 -> 64 -> 67 (intervals: 2, 2, 3; 2 are <= 2, so 2/3 ≈ 0.67)
    analyzer.record(60)
    analyzer.record(62)
    analyzer.record(64)
    analyzer.record(67)
    result = analyzer.analyze()
    assert result.melodic_ratio == pytest.approx(2 / 3, rel=0.01)


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: dominant_interval and largest_interval
# ---------------------------------------------------------------------------


def test_dominant_interval_highest_count():
    """dominant_interval should be the interval with highest count."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    # Record intervals: 2 (3x), 7 (2x)
    # 60 -> 62 -> 64 -> 66 -> 73 -> 80 -> 87
    for note in [60, 62, 64, 66, 73, 80, 87]:
        analyzer.record(note)
    result = analyzer.analyze()
    assert result.dominant_interval == 2  # Appears 3 times (most)


def test_largest_interval():
    """largest_interval should be the maximum observed interval (after folding)."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    # 60 -> 62 -> 67 -> 100 (intervals: 2, 5, 33)
    # With fold_octaves=True, 33 % 12 = 9
    for note in [60, 62, 67, 100]:
        analyzer.record(note)
    result = analyzer.analyze()
    # Largest folded interval is 9
    assert result.largest_interval == 9


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: fold_octaves
# ---------------------------------------------------------------------------


def test_fold_octaves_octave_stays_octave():
    """With fold_octaves=True, 60 -> 72 (12 semitones) should stay 12."""
    cfg = IntervalConfig(fold_octaves=True)
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(72)
    result = analyzer.analyze()
    assert result.dominant_interval == 12
    assert result.dominant_name == "octave"


def test_fold_octaves_24_semitones():
    """With fold_octaves=True, 60 -> 84 (24 semitones) should fold to 12."""
    cfg = IntervalConfig(fold_octaves=True)
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(84)
    result = analyzer.analyze()
    # 24 % 12 = 0, but we convert 0 back to 12 (octave)
    assert result.dominant_interval == 12
    assert result.dominant_name == "octave"


def test_fold_octaves_19_semitones():
    """With fold_octaves=True, 60 -> 79 (19 semitones) should fold to 7."""
    cfg = IntervalConfig(fold_octaves=True)
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(79)
    result = analyzer.analyze()
    # 19 % 12 = 7
    assert result.dominant_interval == 7
    assert result.dominant_name == "perf5"


def test_fold_octaves_disabled():
    """With fold_octaves=False, 60 -> 84 (24 semitones) should stay 24."""
    cfg = IntervalConfig(fold_octaves=False)
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(84)
    result = analyzer.analyze()
    assert result.dominant_interval == 24
    assert result.dominant_name == "24st"


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: interval_name
# ---------------------------------------------------------------------------


def test_interval_name_unison():
    """interval_name(0) should return 'unison'."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    assert analyzer.interval_name(0) == "unison"


def test_interval_name_perf5():
    """interval_name(7) should return 'perf5'."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    assert analyzer.interval_name(7) == "perf5"


def test_interval_name_octave():
    """interval_name(12) should return 'octave'."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    assert analyzer.interval_name(12) == "octave"


def test_interval_name_all_standard():
    """All entries in INTERVAL_NAMES should map correctly."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    for semitones, expected_name in INTERVAL_NAMES.items():
        assert analyzer.interval_name(semitones) == expected_name


def test_interval_name_unmapped():
    """Unmapped interval should return f'{semitones}st'."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    assert analyzer.interval_name(25) == "25st"
    assert analyzer.interval_name(100) == "100st"


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: note clamping
# ---------------------------------------------------------------------------


def test_record_clamps_note_low():
    """Negative note should be clamped to 0."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(-5)
    analyzer.record(10)
    result = analyzer.analyze()
    # 0 -> 10 = 10 semitones
    assert result.dominant_interval == 10


def test_record_clamps_note_high():
    """Note > 127 should be clamped to 127."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(200)
    result = analyzer.analyze()
    # 60 -> 127 = 67 semitones (with fold_octaves, 67 % 12 = 7, but 7 != 0 so stays 7)
    # Wait, 67 > 12 so it gets folded: 67 % 12 = 7
    assert result.dominant_interval == 7
    assert result.dominant_name == "perf5"


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: max_samples and FIFO eviction
# ---------------------------------------------------------------------------


def test_max_samples_fifo_eviction():
    """Exceeding max_samples should evict oldest from front."""
    cfg = IntervalConfig(max_samples=100)
    analyzer = NoteIntervalDistribution(cfg)
    # Record 5 notes (producing 4 intervals)
    for note in [60, 62, 64, 66, 68]:
        analyzer.record(note)
    assert analyzer.total() == 4

    # Record 96 more intervals (need 97 more notes)
    last_note = 68
    for i in range(97):
        next_note = (last_note + 2) % 128
        analyzer.record(next_note)
        last_note = next_note

    assert analyzer.total() == 100


def test_max_samples_fifo_eviction_small_window():
    """Test FIFO eviction with minimum allowed window."""
    cfg = IntervalConfig(max_samples=100)
    analyzer = NoteIntervalDistribution(cfg)
    # Record notes to create exactly 100 intervals
    for i in range(101):
        analyzer.record((60 + i) % 128)
    assert analyzer.total() == 100

    # Record one more interval
    analyzer.record((60 + 101) % 128)
    assert analyzer.total() == 100


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: clear
# ---------------------------------------------------------------------------


def test_clear_empties():
    """clear should reset all state."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(62)
    analyzer.record(64)
    analyzer.clear()
    assert analyzer.total() == 0
    result = analyzer.analyze()
    assert result.total_intervals == 0
    assert result.dominant_interval is None


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: total
# ---------------------------------------------------------------------------


def test_total_intervals_tracks():
    """total() should return current interval count."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    assert analyzer.total() == 0  # No interval yet
    analyzer.record(62)
    assert analyzer.total() == 1  # First interval
    analyzer.record(64)
    assert analyzer.total() == 2  # Second interval
    analyzer.record(67)
    assert analyzer.total() == 3  # Third interval


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: serialization
# ---------------------------------------------------------------------------


def test_analysis_to_dict():
    """to_dict should return serializable dict."""
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    analyzer.record(60)
    analyzer.record(62)
    analyzer.record(64)
    result = analyzer.analyze()
    d = result.to_dict()
    assert d["total_intervals"] == 2
    assert d["dominant_interval"] == 2
    assert d["dominant_name"] == "maj2"


def test_analysis_from_dict():
    """from_dict should reconstruct analysis."""
    d = {
        "interval_counts": {2: 3, 7: 2},
        "total_intervals": 5,
        "dominant_interval": 2,
        "dominant_name": "maj2",
        "mean_interval": 3.4,
        "largest_interval": 7,
        "melodic_ratio": 0.6,
    }
    result = IntervalAnalysis.from_dict(d)
    assert result.total_intervals == 5
    assert result.dominant_interval == 2
    assert result.dominant_name == "maj2"
    assert result.mean_interval == 3.4
    assert result.largest_interval == 7
    assert result.melodic_ratio == 0.6


# ---------------------------------------------------------------------------
# NoteIntervalDistribution: integrated scenario (from spec)
# ---------------------------------------------------------------------------


def test_spec_scenario():
    """Test scenario: [60, 62, 64, 67, 64, 62, 60].

    Expected intervals: [2, 2, 3, 3, 2, 2]
    Expected dominant: 2 (appears 4 times)
    Expected dominant_name: 'maj2'
    Expected mean_interval: 14/6 ≈ 2.33
    Expected melodic_ratio: 4/6 ≈ 0.67 (all <= 2)
    Expected largest_interval: 3
    """
    cfg = IntervalConfig()
    analyzer = NoteIntervalDistribution(cfg)
    for note in [60, 62, 64, 67, 64, 62, 60]:
        analyzer.record(note)
    result = analyzer.analyze()

    assert result.total_intervals == 6
    assert result.dominant_interval == 2
    assert result.dominant_name == "maj2"
    assert result.mean_interval == pytest.approx(2.33, rel=0.01)
    assert result.melodic_ratio == pytest.approx(4 / 6, rel=0.01)
    assert result.largest_interval == 3
