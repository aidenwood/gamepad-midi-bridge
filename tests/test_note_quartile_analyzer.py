"""Tests for note_quartile_analyzer module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_quartile_analyzer import (
    NoteQuartileAnalyzer,
    QuartileAnalysis,
    QuartileConfig,
    QUARTILE_NAMES,
    QUARTILE_RANGES,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_quartile_names_has_four_entries():
    """QUARTILE_NAMES should have exactly 4 entries."""
    assert len(QUARTILE_NAMES) == 4
    assert QUARTILE_NAMES == ["sub_bass", "bass", "mids", "highs"]


def test_quartile_ranges_has_four_entries():
    """QUARTILE_RANGES should have exactly 4 entries."""
    assert len(QUARTILE_RANGES) == 4
    assert QUARTILE_RANGES == [(0, 31), (32, 63), (64, 95), (96, 127)]


# ---------------------------------------------------------------------------
# Config: defaults and clamping
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config should have max_samples=50000."""
    cfg = QuartileConfig()
    assert cfg.max_samples == 50000


def test_config_clamp_max_samples_min():
    """max_samples < 100 should be clamped to 100."""
    cfg = QuartileConfig(max_samples=50)
    assert cfg.max_samples == 100


def test_config_clamp_max_samples_max():
    """max_samples > 1000000 should be clamped to 1000000."""
    cfg = QuartileConfig(max_samples=2000000)
    assert cfg.max_samples == 1000000


def test_config_to_dict():
    """to_dict should return serializable dict."""
    cfg = QuartileConfig(max_samples=5000)
    d = cfg.to_dict()
    assert d["max_samples"] == 5000


def test_config_from_dict():
    """from_dict should reconstruct config."""
    d = {"max_samples": 5000}
    cfg = QuartileConfig.from_dict(d)
    assert cfg.max_samples == 5000


# ---------------------------------------------------------------------------
# NoteQuartileAnalyzer: empty state
# ---------------------------------------------------------------------------


def test_analyzer_init_empty():
    """Newly initialized analyzer should have no samples."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.total() == 0


def test_analyze_empty():
    """Analyze on empty analyzer should return analysis with dominant None."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    result = analyzer.analyze()
    assert result.total_notes == 0
    assert result.dominant_quartile_index is None
    assert result.dominant_quartile_name is None
    assert result.quartile_counts == [0, 0, 0, 0]
    assert result.quartile_percentages == [0.0, 0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Note to quartile mapping
# ---------------------------------------------------------------------------


def test_quartile_for_note_0():
    """Note 0 should map to quartile 0 (sub_bass)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(0) == 0


def test_quartile_for_note_31():
    """Note 31 should map to quartile 0 (sub_bass)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(31) == 0


def test_quartile_for_note_32():
    """Note 32 should map to quartile 1 (bass)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(32) == 1


def test_quartile_for_note_63():
    """Note 63 should map to quartile 1 (bass)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(63) == 1


def test_quartile_for_note_64():
    """Note 64 should map to quartile 2 (mids)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(64) == 2


def test_quartile_for_note_95():
    """Note 95 should map to quartile 2 (mids)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(95) == 2


def test_quartile_for_note_96():
    """Note 96 should map to quartile 3 (highs)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(96) == 3


def test_quartile_for_note_127():
    """Note 127 should map to quartile 3 (highs)."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    assert analyzer.quartile_for(127) == 3


# ---------------------------------------------------------------------------
# Note clamping
# ---------------------------------------------------------------------------


def test_record_clamps_note_negative():
    """Recording note < 0 should clamp to 0."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    analyzer.record(-10)
    result = analyzer.analyze()
    assert result.quartile_counts[0] == 1  # Note 0 is quartile 0


def test_record_clamps_note_high():
    """Recording note > 127 should clamp to 127."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    analyzer.record(200)
    result = analyzer.analyze()
    assert result.quartile_counts[3] == 1  # Note 127 is quartile 3


# ---------------------------------------------------------------------------
# Recording and analysis
# ---------------------------------------------------------------------------


def test_record_single_note():
    """Recording one note should update correct quartile."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    analyzer.record(12)  # sub_bass quartile
    result = analyzer.analyze()
    assert result.quartile_counts == [1, 0, 0, 0]
    assert result.total_notes == 1


def test_analyze_multiple_notes():
    """Analyze should count notes in each quartile correctly."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    # 12, 28 → sub_bass (quartile 0) = 2
    # 50, 60 → bass (quartile 1) = 2
    # 70, 80, 90 → mids (quartile 2) = 3
    # 100 → highs (quartile 3) = 1
    notes = [12, 28, 50, 60, 70, 80, 90, 100]
    for note in notes:
        analyzer.record(note)
    result = analyzer.analyze()
    assert result.quartile_counts == [2, 2, 3, 1]
    assert result.total_notes == 8


def test_dominant_quartile_index():
    """dominant_quartile_index should identify highest count."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    notes = [12, 28, 50, 60, 70, 80, 90, 100]
    for note in notes:
        analyzer.record(note)
    result = analyzer.analyze()
    assert result.dominant_quartile_index == 2  # mids has 4 notes


def test_dominant_quartile_name():
    """dominant_quartile_name should match index."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    notes = [12, 28, 50, 60, 70, 80, 90, 100]
    for note in notes:
        analyzer.record(note)
    result = analyzer.analyze()
    assert result.dominant_quartile_name == "mids"


def test_quartile_percentages_sum_to_one():
    """quartile_percentages should sum to 1.0."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    notes = [12, 28, 50, 60, 70, 80, 90, 100]
    for note in notes:
        analyzer.record(note)
    result = analyzer.analyze()
    total_pct = sum(result.quartile_percentages)
    assert abs(total_pct - 1.0) < 1e-9


def test_quartile_percentages_correct():
    """quartile_percentages should match counts."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    notes = [12, 28, 50, 60, 70, 80, 90, 100]
    for note in notes:
        analyzer.record(note)
    result = analyzer.analyze()
    expected = [2/8, 2/8, 3/8, 1/8]
    for i, pct in enumerate(result.quartile_percentages):
        assert abs(pct - expected[i]) < 1e-9


# ---------------------------------------------------------------------------
# FIFO eviction and max_samples
# ---------------------------------------------------------------------------


def test_max_samples_fifo_eviction():
    """Recording beyond max_samples should evict oldest (FIFO)."""
    cfg = QuartileConfig(max_samples=5)  # Will be clamped to 100
    analyzer = NoteQuartileAnalyzer(cfg)
    # Record 5 sub_bass notes
    for _ in range(5):
        analyzer.record(10)
    result = analyzer.analyze()
    assert result.quartile_counts[0] == 5
    assert analyzer.total() == 5

    # Record many more to exceed max_samples (now 100)
    for _ in range(96):
        analyzer.record(10)
    result = analyzer.analyze()
    assert result.quartile_counts[0] == 100  # At max capacity
    assert analyzer.total() == 100

    # Record 1 more: oldest evicted, count stays at 100
    analyzer.record(10)
    result = analyzer.analyze()
    assert result.quartile_counts[0] == 100
    assert analyzer.total() == 100


def test_fifo_eviction_decrements_correct_quartile():
    """Evicting from a quartile should decrement that quartile's count."""
    cfg = QuartileConfig(max_samples=100)  # Clamped to 100
    analyzer = NoteQuartileAnalyzer(cfg)
    # Record 3 sub_bass, then 2 bass, then fill to 100
    analyzer.record(10)  # sub_bass, index 0
    analyzer.record(20)  # sub_bass, index 1
    analyzer.record(30)  # sub_bass, index 2
    analyzer.record(40)  # bass, index 3
    analyzer.record(50)  # bass, index 4
    # Fill remaining 95 with highs to avoid interfering with bass count
    for _ in range(95):
        analyzer.record(100)
    result = analyzer.analyze()
    assert result.quartile_counts[0] == 3
    assert result.quartile_counts[1] == 2
    assert analyzer.total() == 100

    # Record 1 more bass: oldest item (note 10) evicted, sub_bass count decrements
    analyzer.record(50)  # bass
    result = analyzer.analyze()
    assert result.quartile_counts[0] == 2  # Lost one sub_bass
    assert result.quartile_counts[1] == 3  # Gained one bass
    assert analyzer.total() == 100


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


def test_clear_empties_counts():
    """clear() should reset all counts to zero."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    analyzer.record(12)
    analyzer.record(50)
    analyzer.clear()
    result = analyzer.analyze()
    assert result.quartile_counts == [0, 0, 0, 0]
    assert analyzer.total() == 0


def test_clear_resets_dominant():
    """clear() should reset dominant to None."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    analyzer.record(12)
    analyzer.clear()
    result = analyzer.analyze()
    assert result.dominant_quartile_index is None
    assert result.dominant_quartile_name is None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_analysis_to_dict():
    """to_dict should return serializable dict."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    notes = [12, 28, 50, 60]
    for note in notes:
        analyzer.record(note)
    result = analyzer.analyze()
    d = result.to_dict()
    assert "quartile_counts" in d
    assert "dominant_quartile_index" in d
    assert d["total_notes"] == 4


def test_analysis_from_dict():
    """from_dict should reconstruct analysis."""
    d = {
        "quartile_counts": [2, 1, 4, 1],
        "quartile_names": ["sub_bass", "bass", "mids", "highs"],
        "total_notes": 8,
        "dominant_quartile_index": 2,
        "dominant_quartile_name": "mids",
        "quartile_percentages": [0.25, 0.125, 0.5, 0.125],
    }
    result = QuartileAnalysis.from_dict(d)
    assert result.quartile_counts == [2, 1, 4, 1]
    assert result.dominant_quartile_index == 2
    assert result.dominant_quartile_name == "mids"


def test_round_trip_analysis():
    """Serialize and deserialize analysis should match."""
    cfg = QuartileConfig()
    analyzer = NoteQuartileAnalyzer(cfg)
    notes = [12, 28, 50, 60, 70, 80, 90, 100]
    for note in notes:
        analyzer.record(note)
    original = analyzer.analyze()
    d = original.to_dict()
    restored = QuartileAnalysis.from_dict(d)
    assert restored.quartile_counts == original.quartile_counts
    assert restored.dominant_quartile_index == original.dominant_quartile_index
    assert restored.total_notes == original.total_notes
