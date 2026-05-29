"""Tests for note_frequency module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_frequency import (
    NoteFrequencyConfig,
    NoteFrequency,
    apply_decay,
)


# ---------------------------------------------------------------------------
# config: defaults and clamping
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config should have max_samples=50000, decay_enabled=False."""
    cfg = NoteFrequencyConfig()
    assert cfg.max_samples == 50000
    assert cfg.decay_enabled is False
    assert cfg.decay_half_life_s == 60.0


def test_config_clamp_max_samples_min():
    """max_samples < 100 should be clamped to 100."""
    cfg = NoteFrequencyConfig(max_samples=50)
    assert cfg.max_samples == 100


def test_config_clamp_max_samples_max():
    """max_samples > 1000000 should be clamped to 1000000."""
    cfg = NoteFrequencyConfig(max_samples=2000000)
    assert cfg.max_samples == 1000000


def test_config_clamp_decay_half_life_min():
    """decay_half_life_s < 1.0 should be clamped to 1.0."""
    cfg = NoteFrequencyConfig(decay_enabled=True, decay_half_life_s=0.5)
    assert cfg.decay_half_life_s == 1.0


def test_config_clamp_decay_half_life_max():
    """decay_half_life_s > 3600 should be clamped to 3600."""
    cfg = NoteFrequencyConfig(decay_enabled=True, decay_half_life_s=5000.0)
    assert cfg.decay_half_life_s == 3600.0


def test_config_to_dict():
    """to_dict should return serializable dict."""
    cfg = NoteFrequencyConfig(max_samples=5000, decay_enabled=True, decay_half_life_s=120.0)
    d = cfg.to_dict()
    assert d["max_samples"] == 5000
    assert d["decay_enabled"] is True
    assert d["decay_half_life_s"] == 120.0


def test_config_from_dict():
    """from_dict should reconstruct config."""
    d = {"max_samples": 5000, "decay_enabled": True, "decay_half_life_s": 120.0}
    cfg = NoteFrequencyConfig.from_dict(d)
    assert cfg.max_samples == 5000
    assert cfg.decay_enabled is True
    assert cfg.decay_half_life_s == 120.0


# ---------------------------------------------------------------------------
# apply_decay function
# ---------------------------------------------------------------------------


def test_apply_decay_half_life():
    """After elapsed time equals half_life, counts should be halved."""
    counts = [10.0, 20.0, 30.0]
    result = apply_decay(counts, elapsed_s=60.0, half_life_s=60.0)
    assert result[0] == pytest.approx(5.0)
    assert result[1] == pytest.approx(10.0)
    assert result[2] == pytest.approx(15.0)


def test_apply_decay_zero_elapsed():
    """Zero elapsed time should not change counts."""
    counts = [10.0, 20.0, 30.0]
    result = apply_decay(counts, elapsed_s=0.0, half_life_s=60.0)
    assert result[0] == pytest.approx(10.0)
    assert result[1] == pytest.approx(20.0)
    assert result[2] == pytest.approx(30.0)


def test_apply_decay_two_half_lives():
    """After two half-lives, counts should be 1/4."""
    counts = [16.0]
    result = apply_decay(counts, elapsed_s=120.0, half_life_s=60.0)
    assert result[0] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# NoteFrequency: basic recording and counting
# ---------------------------------------------------------------------------


def test_note_frequency_init():
    """Should initialize with zeros."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    assert nf.count(60) == 0.0
    assert nf.total_plays() == 0.0


def test_record_single_note():
    """Recording a note should increment its count."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    assert nf.count(60) == 1.0


def test_record_same_note_multiple_times():
    """Recording the same note multiple times should accumulate."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    nf.record(60)
    nf.record(60)
    assert nf.count(60) == 3.0


def test_record_clamps_note_low():
    """Negative note should be clamped to 0."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(-5)
    assert nf.count(0) == 1.0
    assert nf.count(-5) == 1.0  # clamped to 0


def test_record_clamps_note_high():
    """Note > 127 should be clamped to 127."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(200)
    assert nf.count(127) == 1.0


# ---------------------------------------------------------------------------
# NoteFrequency: top_n
# ---------------------------------------------------------------------------


def test_top_n_empty():
    """top_n on empty tracker should return empty list."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    assert nf.top_n(5) == []


def test_top_n_single_note():
    """top_n should return one note if only one recorded."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    result = nf.top_n(5)
    assert result == [(60, 1.0)]


def test_top_n_multiple_notes():
    """top_n should return notes sorted by count descending."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    nf.record(60)
    nf.record(60)
    nf.record(64)
    nf.record(64)
    nf.record(72)
    result = nf.top_n(5)
    assert result == [(60, 3.0), (64, 2.0), (72, 1.0)]


def test_top_n_n_limit():
    """top_n(2) should return only top 2 notes."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    nf.record(60)
    nf.record(60)
    nf.record(64)
    nf.record(64)
    nf.record(72)
    result = nf.top_n(2)
    assert result == [(60, 3.0), (64, 2.0)]


def test_top_n_skips_zero_counts():
    """top_n should skip notes with count 0."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    nf.record(64)
    # Never recorded 72, 76, etc.
    result = nf.top_n(5)
    assert len(result) == 2
    assert 60 in [note for note, count in result]
    assert 64 in [note for note, count in result]


# ---------------------------------------------------------------------------
# NoteFrequency: total_plays
# ---------------------------------------------------------------------------


def test_total_plays_empty():
    """total_plays on empty tracker should be 0."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    assert nf.total_plays() == 0.0


def test_total_plays_accumulates():
    """total_plays should sum all counts."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    nf.record(60)
    nf.record(64)
    nf.record(64)
    nf.record(72)
    assert nf.total_plays() == 5.0


# ---------------------------------------------------------------------------
# NoteFrequency: key_center_guess and pitch_class_distribution
# ---------------------------------------------------------------------------


def test_pitch_class_distribution_length():
    """pitch_class_distribution should always return 12 elements."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    dist = nf.pitch_class_distribution()
    assert len(dist) == 12


def test_pitch_class_distribution_empty():
    """pitch_class_distribution on empty tracker should be all zeros."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    dist = nf.pitch_class_distribution()
    assert dist == [0.0] * 12


def test_pitch_class_distribution_sums_octaves():
    """pitch_class_distribution should sum counts across octaves.

    Notes 60 (C4), 72 (C5), 84 (C6) all have pitch class 0 (C).
    """
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)  # C4, pitch class 0
    nf.record(72)  # C5, pitch class 0
    nf.record(84)  # C6, pitch class 0
    dist = nf.pitch_class_distribution()
    assert dist[0] == 3.0  # All three C notes
    assert sum(dist) == 3.0


def test_key_center_guess_empty():
    """key_center_guess on empty tracker should return None."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    assert nf.key_center_guess() is None


def test_key_center_guess_single_note():
    """key_center_guess should return pitch class of single note.

    Note 60 is C (pitch class 0).
    """
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    assert nf.key_center_guess() == 0  # C


def test_key_center_guess_multiple_octaves():
    """key_center_guess should identify most-played pitch class across octaves."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    # Record C notes (pitch class 0) heavily
    nf.record(60)
    nf.record(60)
    nf.record(72)
    nf.record(84)
    # Record some other notes
    nf.record(64)  # E (pitch class 4)
    nf.record(67)  # G (pitch class 7)
    assert nf.key_center_guess() == 0  # Most-played is C


# ---------------------------------------------------------------------------
# NoteFrequency: max_samples and FIFO eviction
# ---------------------------------------------------------------------------


def test_max_samples_fifo_eviction():
    """Exceeding max_samples should evict oldest and decrement its count."""
    cfg = NoteFrequencyConfig(max_samples=105)
    nf = NoteFrequency(cfg)
    nf.record(10)
    nf.record(20)
    nf.record(30)

    # Record 102 more notes (use 40-100, 102-143 to avoid 10, 20, 30)
    for note in list(range(40, 101)) + list(range(102, 143)):
        nf.record(note)

    # Now at 105 samples, with 10 as the oldest
    assert len(nf._samples) == 105
    assert nf.total_plays() == 105.0
    assert nf.count(10) == 1.0

    # Record one more (will evict the oldest: 10)
    nf.record(1)
    assert len(nf._samples) == 105
    assert nf.count(10) == 0.0
    assert nf.count(1) == 1.0
    assert nf.total_plays() == 105.0


def test_max_samples_fifo_correct_note():
    """FIFO eviction should decrement the correct note."""
    cfg = NoteFrequencyConfig(max_samples=110)
    nf = NoteFrequency(cfg)
    nf.record(10)
    nf.record(10)
    nf.record(10)
    nf.record(20)
    nf.record(20)
    assert nf.count(10) == 3.0
    assert nf.count(20) == 2.0

    # Record 105 more notes using range(30, 101) + range(102, 136) = 71 + 34 = 105
    for note in list(range(30, 101)) + list(range(102, 136)):
        nf.record(note)

    # Now at 110 samples
    assert len(nf._samples) == 110
    # Record one more (will evict oldest 10)
    nf.record(2)
    assert nf.count(10) == 2.0  # One of three 10s evicted
    assert nf.count(20) == 2.0
    assert nf.count(2) == 1.0
    assert nf.total_plays() == 110.0


# ---------------------------------------------------------------------------
# NoteFrequency: clear
# ---------------------------------------------------------------------------


def test_clear_zeros_all():
    """clear should zero all counts and samples."""
    cfg = NoteFrequencyConfig()
    nf = NoteFrequency(cfg)
    nf.record(60)
    nf.record(64)
    nf.record(67)
    nf.clear()
    assert nf.count(60) == 0.0
    assert nf.count(64) == 0.0
    assert nf.count(67) == 0.0
    assert nf.total_plays() == 0.0
    assert nf.top_n(5) == []


# ---------------------------------------------------------------------------
# NoteFrequency: decay
# ---------------------------------------------------------------------------


def test_decay_disabled_by_default():
    """Decay should be disabled by default."""
    cfg = NoteFrequencyConfig()
    assert cfg.decay_enabled is False


def test_decay_enabled_first_record_no_decay():
    """First record should not decay (no previous time reference)."""
    cfg = NoteFrequencyConfig(decay_enabled=True, decay_half_life_s=60.0)
    nf = NoteFrequency(cfg)
    nf.record(60, now_s=0.0)
    assert nf.count(60) == 1.0


def test_decay_enabled_applies_decay():
    """Records with elapsed time should decay previous counts."""
    cfg = NoteFrequencyConfig(decay_enabled=True, decay_half_life_s=60.0)
    nf = NoteFrequency(cfg)
    nf.record(60, now_s=0.0)
    assert nf.count(60) == 1.0

    # Record another note 60 seconds later (one half-life)
    nf.record(64, now_s=60.0)
    # The 60 should have decayed to ~0.5
    assert nf.count(60) == pytest.approx(0.5, abs=1e-6)
    # The 64 is fresh
    assert nf.count(64) == 1.0


def test_decay_halves_after_one_half_life():
    """After one half-life, count should be halved."""
    cfg = NoteFrequencyConfig(decay_enabled=True, decay_half_life_s=60.0)
    nf = NoteFrequency(cfg)
    nf.record(60, now_s=0.0)
    nf.record(60, now_s=0.0)
    nf.record(60, now_s=0.0)
    assert nf.count(60) == 3.0

    # Record at one half-life
    nf.record(64, now_s=60.0)
    # 60 should decay to ~1.5
    assert nf.count(60) == pytest.approx(1.5, abs=1e-6)
