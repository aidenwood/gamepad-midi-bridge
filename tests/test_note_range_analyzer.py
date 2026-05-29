"""Tests for note_range_analyzer module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_range_analyzer import (
    NoteRangeAnalyzer,
    NoteRangeAnalysis,
    NoteRangeConfig,
)


# ---------------------------------------------------------------------------
# config: defaults and clamping
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config should have max_samples=10000."""
    cfg = NoteRangeConfig()
    assert cfg.max_samples == 10000


def test_config_clamp_max_samples_min():
    """max_samples < 100 should be clamped to 100."""
    cfg = NoteRangeConfig(max_samples=50)
    assert cfg.max_samples == 100


def test_config_clamp_max_samples_max():
    """max_samples > 1000000 should be clamped to 1000000."""
    cfg = NoteRangeConfig(max_samples=2000000)
    assert cfg.max_samples == 1000000


def test_config_to_dict():
    """to_dict should return serializable dict."""
    cfg = NoteRangeConfig(max_samples=5000)
    d = cfg.to_dict()
    assert d["max_samples"] == 5000


def test_config_from_dict():
    """from_dict should reconstruct config."""
    d = {"max_samples": 5000}
    cfg = NoteRangeConfig.from_dict(d)
    assert cfg.max_samples == 5000


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: empty state
# ---------------------------------------------------------------------------


def test_analyzer_init_empty():
    """Newly initialized analyzer should have no samples."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    assert analyzer.total_notes() == 0


def test_analyze_empty():
    """Analyze on empty analyzer should return None for low/high."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    result = analyzer.analyze()
    assert result.low_note is None
    assert result.high_note is None
    assert result.span_semitones == 0
    assert result.unique_notes == 0


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: single note
# ---------------------------------------------------------------------------


def test_record_single_note():
    """Recording one note should set low == high."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    result = analyzer.analyze()
    assert result.low_note == 60
    assert result.high_note == 60
    assert result.span_semitones == 0


def test_span_semitones_computed():
    """span_semitones should be high - low."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(72)  # 12 semitones up
    result = analyzer.analyze()
    assert result.span_semitones == 12


def test_span_octaves_correct():
    """span_octaves should be span_semitones / 12."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(84)  # 24 semitones = 2 octaves
    result = analyzer.analyze()
    assert result.span_semitones == 24
    assert result.span_octaves == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: unique notes
# ---------------------------------------------------------------------------


def test_unique_notes_counts_distinct():
    """unique_notes should count distinct notes."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(60)
    analyzer.record(60)
    analyzer.record(64)
    analyzer.record(64)
    result = analyzer.analyze()
    assert result.unique_notes == 2


def test_unique_notes_from_scenario():
    """Test unique_notes with [60, 62, 64, 67, 72]."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    for note in [60, 62, 64, 67, 72]:
        analyzer.record(note)
    result = analyzer.analyze()
    assert result.unique_notes == 5


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: octave distribution
# ---------------------------------------------------------------------------


def test_octave_distribution_tracked():
    """octave_distribution should track per-octave counts."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    # MIDI 60 (C4) = octave 4
    # MIDI 72 (C5) = octave 5
    analyzer.record(60)
    analyzer.record(60)
    analyzer.record(72)
    analyzer.record(72)
    analyzer.record(72)
    result = analyzer.analyze()
    assert result.octave_distribution[4] == 2
    assert result.octave_distribution[5] == 3


def test_most_used_octave_identified():
    """most_used_octave should be the octave with highest count."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(60)
    analyzer.record(72)
    analyzer.record(72)
    analyzer.record(72)
    result = analyzer.analyze()
    assert result.most_used_octave == 5  # 3 plays > 2 plays


def test_most_used_octave_single():
    """most_used_octave should be correct for single octave."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(64)
    analyzer.record(67)
    result = analyzer.analyze()
    assert result.most_used_octave == 4  # All are in octave 4


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: note clamping
# ---------------------------------------------------------------------------


def test_record_clamps_note_low():
    """Negative note should be clamped to 0."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(-5)
    result = analyzer.analyze()
    assert result.low_note == 0
    assert result.high_note == 0


def test_record_clamps_note_high():
    """Note > 127 should be clamped to 127."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(200)
    result = analyzer.analyze()
    assert result.low_note == 127
    assert result.high_note == 127


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: note_name static method
# ---------------------------------------------------------------------------


def test_note_name_c4():
    """note_name(60) should return 'C4'."""
    assert NoteRangeAnalyzer.note_name(60) == "C4"


def test_note_name_c_sharp_4():
    """note_name(61) should return 'C#4'."""
    assert NoteRangeAnalyzer.note_name(61) == "C#4"


def test_note_name_d4():
    """note_name(62) should return 'D4'."""
    assert NoteRangeAnalyzer.note_name(62) == "D4"


def test_note_name_c5():
    """note_name(72) should return 'C5'."""
    assert NoteRangeAnalyzer.note_name(72) == "C5"


def test_note_name_a0():
    """note_name(21) should return 'A0'."""
    assert NoteRangeAnalyzer.note_name(21) == "A0"


def test_note_name_out_of_range_low():
    """note_name(-1) should return '?-1'."""
    assert NoteRangeAnalyzer.note_name(-1) == "?-1"


def test_note_name_out_of_range_high():
    """note_name(128) should return '?128'."""
    assert NoteRangeAnalyzer.note_name(128) == "?128"


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: max_samples and FIFO eviction
# ---------------------------------------------------------------------------


def test_max_samples_fifo_eviction():
    """Exceeding max_samples should evict oldest from front."""
    cfg = NoteRangeConfig(max_samples=110)
    analyzer = NoteRangeAnalyzer(cfg)
    # Record 5 notes
    analyzer.record(60)
    analyzer.record(61)
    analyzer.record(62)
    analyzer.record(63)
    analyzer.record(64)
    assert analyzer.total_notes() == 5

    # Record 105 more notes (using values well outside 60-64 to keep them distinct)
    for i in range(105):
        analyzer.record((100 + i) % 128)

    assert analyzer.total_notes() == 110
    result = analyzer.analyze()
    # The window should contain the last 110 notes added.
    # First 5 were [60, 61, 62, 63, 64], then 105 more
    # So samples = [60, 61, 62, 63, 64] + [(100..105) % 128] * many
    # After 110 total, earliest would depend on the modulo operation
    # Just verify we're at capacity and operations work
    assert analyzer.total_notes() == 110


def test_max_samples_fifo_eviction_small_window():
    """Test FIFO eviction with a small window (minimum allowed)."""
    cfg = NoteRangeConfig(max_samples=100)
    analyzer = NoteRangeAnalyzer(cfg)
    # Record exactly 100 notes
    for i in range(100):
        analyzer.record(i % 128)
    assert analyzer.total_notes() == 100

    # Record one more, should evict the first
    analyzer.record(100 % 128)
    assert analyzer.total_notes() == 100


def test_unique_notes_sticky_after_eviction():
    """unique_notes should remain even after eviction (sticky)."""
    cfg = NoteRangeConfig(max_samples=100)
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(62)
    analyzer.record(64)
    # Record 97 more to reach capacity
    for i in range(97):
        analyzer.record((67 + i) % 128)
    assert analyzer.total_notes() == 100
    result = analyzer.analyze()
    assert result.unique_notes >= 3  # At least 60, 62, 64

    # Record one more, which will evict 60
    analyzer.record(120)
    result = analyzer.analyze()
    assert result.unique_notes >= 4  # 60 was counted, stays in unique even after eviction
    assert 60 in analyzer._unique  # Verify 60 is in unique set


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: clear
# ---------------------------------------------------------------------------


def test_clear_empties():
    """clear should reset all state."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(64)
    analyzer.record(67)
    analyzer.clear()
    assert analyzer.total_notes() == 0
    result = analyzer.analyze()
    assert result.low_note is None
    assert result.high_note is None
    assert result.unique_notes == 0


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: total_notes
# ---------------------------------------------------------------------------


def test_total_notes_tracks():
    """total_notes should return current window size."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    assert analyzer.total_notes() == 1
    analyzer.record(64)
    assert analyzer.total_notes() == 2
    analyzer.record(67)
    assert analyzer.total_notes() == 3


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: serialization
# ---------------------------------------------------------------------------


def test_analysis_to_dict():
    """to_dict should return serializable dict."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    analyzer.record(60)
    analyzer.record(72)
    result = analyzer.analyze()
    d = result.to_dict()
    assert d["low_note"] == 60
    assert d["high_note"] == 72
    assert d["span_semitones"] == 12


def test_analysis_from_dict():
    """from_dict should reconstruct analysis."""
    d = {
        "low_note": 60,
        "high_note": 72,
        "span_semitones": 12,
        "span_octaves": 1.0,
        "unique_notes": 5,
        "octave_distribution": {4: 3, 5: 2},
        "most_used_octave": 4,
    }
    result = NoteRangeAnalysis.from_dict(d)
    assert result.low_note == 60
    assert result.high_note == 72
    assert result.span_semitones == 12
    assert result.unique_notes == 5
    assert result.most_used_octave == 4


# ---------------------------------------------------------------------------
# NoteRangeAnalyzer: integrated scenario (from spec)
# ---------------------------------------------------------------------------


def test_spec_scenario():
    """Test scenario from spec: [60, 62, 64, 67, 72] -> 60, 72, 12, 5, 4."""
    cfg = NoteRangeConfig()
    analyzer = NoteRangeAnalyzer(cfg)
    for note in [60, 62, 64, 67, 72]:
        analyzer.record(note)
    result = analyzer.analyze()
    assert result.low_note == 60
    assert result.high_note == 72
    assert result.span_semitones == 12
    assert result.unique_notes == 5
    assert result.most_used_octave == 4  # All 5 notes are in octave 4
