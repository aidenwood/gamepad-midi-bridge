"""Tests for trigger_pressure_stats module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.trigger_pressure_stats import (
    TriggerPressureConfig,
    TriggerPressureStats,
)


def make_stats(
    bucket_count: int = 10, max_samples: int = 20000
) -> TriggerPressureStats:
    """Create a fresh TriggerPressureStats for each test."""
    cfg = TriggerPressureConfig(bucket_count=bucket_count, max_samples=max_samples)
    return TriggerPressureStats(cfg)


# ---------------------------------------------------------------------------
# config: validation and serialization
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config has bucket_count=10, max_samples=20000."""
    cfg = TriggerPressureConfig()
    assert cfg.bucket_count == 10
    assert cfg.max_samples == 20000


def test_config_bucket_count_clamped_low():
    """bucket_count < 4 is clamped to 4."""
    cfg = TriggerPressureConfig(bucket_count=2)
    assert cfg.bucket_count == 4


def test_config_bucket_count_clamped_high():
    """bucket_count > 64 is clamped to 64."""
    cfg = TriggerPressureConfig(bucket_count=100)
    assert cfg.bucket_count == 64


def test_config_max_samples_clamped_low():
    """max_samples < 100 is clamped to 100."""
    cfg = TriggerPressureConfig(max_samples=50)
    assert cfg.max_samples == 100


def test_config_max_samples_clamped_high():
    """max_samples > 1000000 is clamped to 1000000."""
    cfg = TriggerPressureConfig(max_samples=2000000)
    assert cfg.max_samples == 1000000


def test_config_to_dict():
    """Config round-trip serialization: to_dict() → from_dict()."""
    cfg1 = TriggerPressureConfig(bucket_count=8, max_samples=5000)
    d = cfg1.to_dict()
    cfg2 = TriggerPressureConfig.from_dict(d)
    assert cfg2.bucket_count == 8
    assert cfg2.max_samples == 5000


# ---------------------------------------------------------------------------
# empty state
# ---------------------------------------------------------------------------


def test_peak_empty():
    """peak() returns None when no samples."""
    s = make_stats()
    assert s.peak("L2") is None
    assert s.peak("R2") is None


def test_mean_empty():
    """mean() returns None when no samples."""
    s = make_stats()
    assert s.mean("L2") is None
    assert s.mean("R2") is None


def test_percentile_empty():
    """percentile() returns None when no samples."""
    s = make_stats()
    assert s.percentile("L2", 50) is None
    assert s.percentile("R2", 50) is None


def test_buckets_empty():
    """buckets() returns list of zeros when no samples."""
    s = make_stats(bucket_count=10)
    assert s.buckets("L2") == [0] * 10
    assert s.buckets("R2") == [0] * 10


def test_total_samples_empty():
    """total_samples() returns 0 when empty."""
    s = make_stats()
    assert s.total_samples("L2") == 0
    assert s.total_samples("R2") == 0


def test_heatmap_normalized_empty():
    """heatmap_normalized() returns empty list when no samples."""
    s = make_stats()
    assert s.heatmap_normalized("L2") == []
    assert s.heatmap_normalized("R2") == []


# ---------------------------------------------------------------------------
# record and basic aggregations
# ---------------------------------------------------------------------------


def test_record_single_l2():
    """Record a single L2 pressure."""
    s = make_stats()
    s.record("L2", 0.5)
    assert s.peak("L2") == 0.5
    assert s.mean("L2") == 0.5
    assert s.total_samples("L2") == 1


def test_record_single_r2():
    """Record a single R2 pressure."""
    s = make_stats()
    s.record("R2", 0.75)
    assert s.peak("R2") == 0.75
    assert s.mean("R2") == 0.75
    assert s.total_samples("R2") == 1


def test_peak_max():
    """peak() returns the maximum pressure recorded."""
    s = make_stats()
    pressures = [0.1, 0.5, 0.9, 0.3, 0.7]
    for p in pressures:
        s.record("L2", p)
    assert s.peak("L2") == 0.9


def test_mean_average():
    """mean() returns the average of all pressures."""
    s = make_stats()
    pressures = [0.1, 0.5, 0.9]
    for p in pressures:
        s.record("L2", p)
    expected_mean = sum(pressures) / len(pressures)
    assert abs(s.mean("L2") - expected_mean) < 1e-9


def test_record_multiple_triggers():
    """Record pressures for both L2 and R2 independently."""
    s = make_stats()
    for p in [0.1, 0.5, 0.9]:
        s.record("L2", p)
    for p in [0.2, 0.4, 0.8]:
        s.record("R2", p)

    assert s.peak("L2") == 0.9
    assert s.peak("R2") == 0.8
    assert s.total_samples("L2") == 3
    assert s.total_samples("R2") == 3


# ---------------------------------------------------------------------------
# pressure clamping
# ---------------------------------------------------------------------------


def test_clamp_negative_to_zero():
    """Negative pressure is clamped to 0."""
    s = make_stats()
    s.record("L2", -0.5)
    assert s.peak("L2") == 0.0
    assert s.mean("L2") == 0.0


def test_clamp_over_one_to_one():
    """Pressure > 1.0 is clamped to 1.0."""
    s = make_stats()
    s.record("L2", 1.5)
    assert s.peak("L2") == 1.0
    assert s.mean("L2") == 1.0


def test_clamp_boundary_zero():
    """Pressure = 0.0 is valid."""
    s = make_stats()
    s.record("L2", 0.0)
    assert s.peak("L2") == 0.0


def test_clamp_boundary_one():
    """Pressure = 1.0 is valid."""
    s = make_stats()
    s.record("L2", 1.0)
    assert s.peak("L2") == 1.0


# ---------------------------------------------------------------------------
# unknown trigger names
# ---------------------------------------------------------------------------


def test_unknown_trigger_ignored():
    """Recording to unknown trigger name is silently ignored."""
    s = make_stats()
    s.record("X9", 0.5)  # Unknown trigger
    assert s.total_samples("L2") == 0
    assert s.total_samples("R2") == 0
    assert s.peak("L2") is None
    assert s.peak("R2") is None


def test_query_unknown_trigger_returns_none():
    """Querying unknown trigger returns None or empty list."""
    s = make_stats()
    assert s.peak("X9") is None
    assert s.mean("X9") is None
    assert s.percentile("X9", 50) is None
    assert s.total_samples("X9") == 0
    assert s.buckets("X9") == []
    assert s.heatmap_normalized("X9") == []


# ---------------------------------------------------------------------------
# histogram buckets
# ---------------------------------------------------------------------------


def test_bucket_count_default():
    """Default bucket count is 10."""
    s = make_stats()
    assert len(s.buckets("L2")) == 10
    assert len(s.buckets("R2")) == 10


def test_bucket_count_custom():
    """Custom bucket_count is respected."""
    s = make_stats(bucket_count=4)
    assert len(s.buckets("L2")) == 4
    assert len(s.buckets("R2")) == 4


def test_bucket_ranges_length():
    """bucket_ranges() returns list with length = bucket_count."""
    s = make_stats(bucket_count=5)
    ranges = s.bucket_ranges()
    assert len(ranges) == 5


def test_bucket_ranges_first_lo_zero():
    """First bucket range starts at 0.0."""
    s = make_stats(bucket_count=10)
    ranges = s.bucket_ranges()
    assert ranges[0][0] == 0.0


def test_bucket_ranges_last_hi_one():
    """Last bucket range ends at 1.0."""
    s = make_stats(bucket_count=10)
    ranges = s.bucket_ranges()
    assert ranges[-1][1] == 1.0


def test_bucket_ranges_continuous():
    """Bucket ranges are continuous (no gaps)."""
    s = make_stats(bucket_count=5)
    ranges = s.bucket_ranges()
    for i in range(len(ranges) - 1):
        assert ranges[i][1] == ranges[i + 1][0]


def test_bucket_ranges_width():
    """Each bucket range has consistent width (1.0 / bucket_count)."""
    s = make_stats(bucket_count=4)
    ranges = s.bucket_ranges()
    step = 1.0 / 4
    for i, (lo, hi) in enumerate(ranges):
        expected_lo = i * step
        expected_hi = (i + 1) * step
        # Use fuzzy comparison for floating-point safety
        assert abs(lo - expected_lo) < 1e-9 or i == 0
        # Last hi must be exactly 1.0
        if i == len(ranges) - 1:
            assert hi == 1.0
        else:
            assert abs(hi - expected_hi) < 1e-9


# ---------------------------------------------------------------------------
# histogram increments
# ---------------------------------------------------------------------------


def test_record_increments_bucket():
    """Recording pressure increments the corresponding bucket."""
    s = make_stats(bucket_count=10)
    s.record("L2", 0.35)  # Bucket index = min(9, int(0.35 * 10)) = 3
    buckets = s.buckets("L2")
    assert buckets[3] == 1
    assert sum(buckets) == 1


def test_record_multiple_same_bucket():
    """Multiple samples in same bucket increment count."""
    s = make_stats(bucket_count=10)
    s.record("L2", 0.25)  # Bucket 2
    s.record("L2", 0.29)  # Bucket 2
    buckets = s.buckets("L2")
    assert buckets[2] == 2


def test_record_boundary_bucket():
    """Pressure = 1.0 goes to last bucket."""
    s = make_stats(bucket_count=10)
    s.record("L2", 1.0)
    buckets = s.buckets("L2")
    assert buckets[9] == 1  # Last bucket


def test_record_zero_bucket():
    """Pressure = 0.0 goes to first bucket."""
    s = make_stats(bucket_count=10)
    s.record("L2", 0.0)
    buckets = s.buckets("L2")
    assert buckets[0] == 1  # First bucket


# ---------------------------------------------------------------------------
# heatmap normalization
# ---------------------------------------------------------------------------


def test_heatmap_normalized_values_in_range():
    """Normalized heatmap values are in [0.0, 1.0]."""
    s = make_stats(bucket_count=10)
    for p in [0.1, 0.5, 0.9, 0.3, 0.7]:
        s.record("L2", p)
    heatmap = s.heatmap_normalized("L2")
    assert all(0.0 <= v <= 1.0 for v in heatmap)


def test_heatmap_normalized_peak_is_one():
    """Peak bucket in normalized heatmap is always 1.0."""
    s = make_stats(bucket_count=10)
    for _ in range(5):
        s.record("L2", 0.55)  # Bucket 5
    for _ in range(2):
        s.record("L2", 0.25)  # Bucket 2
    heatmap = s.heatmap_normalized("L2")
    assert max(heatmap) == 1.0
    # The bucket with 5 samples should be peak
    assert heatmap[5] == 1.0


def test_heatmap_normalized_relative_scale():
    """Normalized heatmap reflects bucket proportions."""
    s = make_stats(bucket_count=10)
    # Record 10 samples in bucket 3, 5 in bucket 7
    for _ in range(10):
        s.record("L2", 0.35)
    for _ in range(5):
        s.record("L2", 0.75)
    heatmap = s.heatmap_normalized("L2")
    # Bucket 3 is peak (10), bucket 7 should be 0.5
    assert heatmap[3] == 1.0
    assert abs(heatmap[7] - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------


def test_percentile_p0():
    """percentile(p=0) returns minimum."""
    s = make_stats()
    for p in [0.1, 0.5, 0.9]:
        s.record("L2", p)
    assert s.percentile("L2", 0) == 0.1


def test_percentile_p100():
    """percentile(p=100) returns maximum."""
    s = make_stats()
    for p in [0.1, 0.5, 0.9]:
        s.record("L2", p)
    assert s.percentile("L2", 100) == 0.9


def test_percentile_p50():
    """percentile(p=50) approximates median."""
    s = make_stats()
    for p in [0.1, 0.5, 0.9]:
        s.record("L2", p)
    median = s.percentile("L2", 50)
    assert median is not None
    assert 0.4 < median < 0.6  # Should be close to 0.5


def test_percentile_clamped():
    """percentile() clamps p to 0..100."""
    s = make_stats()
    s.record("L2", 0.5)
    # Request p=-10 (should clamp to 0)
    assert s.percentile("L2", -10) == 0.5
    # Request p=150 (should clamp to 100)
    assert s.percentile("L2", 150) == 0.5


# ---------------------------------------------------------------------------
# FIFO eviction with bucket decrement
# ---------------------------------------------------------------------------


def test_max_samples_fifo_eviction():
    """When max_samples exceeded, oldest sample is evicted (FIFO)."""
    # Use max_samples=150 (valid range 100-1000000)
    s = make_stats(bucket_count=10, max_samples=150)
    # Record 160 samples; after 150, next 10 will trigger eviction
    for i in range(160):
        s.record("L2", float(i % 10) / 10.0)
    # After 160 samples with max=150, only 150 remain (FIFO eviction)
    assert s.total_samples("L2") == 150


def test_eviction_decrements_old_bucket():
    """Evicting a sample decrements its bucket count."""
    # Use max_samples=101; so max buffer is 101 samples
    s = make_stats(bucket_count=10, max_samples=101)
    # Record 101 samples in bucket 2 (pressure ~0.25)
    for _ in range(101):
        s.record("L2", 0.25)
    # Check bucket 2 has 101 samples
    assert s.buckets("L2")[2] == 101
    # Record 1 sample in bucket 5: buffer at 101, >= 101 so evict first
    s.record("L2", 0.55)
    # Now we have 101 samples (evicted 1 from bucket 2, added 1 to bucket 5)
    assert s.buckets("L2")[2] == 100  # Decremented
    assert s.buckets("L2")[5] == 1  # Incremented
    assert s.total_samples("L2") == 101


def test_eviction_independent_per_trigger():
    """Eviction on L2 doesn't affect R2."""
    s = make_stats(bucket_count=10, max_samples=101)
    for _ in range(101):
        s.record("L2", 0.25)
    for _ in range(50):
        s.record("R2", 0.75)
    # L2 is at max (101), R2 has 50 samples
    s.record("L2", 0.5)  # Triggers L2 eviction
    assert s.total_samples("L2") == 101
    assert s.total_samples("R2") == 50  # Unchanged


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_empties_samples():
    """clear() removes all samples."""
    s = make_stats()
    s.record("L2", 0.5)
    s.record("R2", 0.75)
    s.clear()
    assert s.total_samples("L2") == 0
    assert s.total_samples("R2") == 0
    assert s.peak("L2") is None
    assert s.peak("R2") is None


def test_clear_resets_buckets():
    """clear() resets histogram buckets to zeros."""
    s = make_stats(bucket_count=10)
    for p in [0.1, 0.5, 0.9]:
        s.record("L2", p)
    s.clear()
    assert s.buckets("L2") == [0] * 10
    assert s.buckets("R2") == [0] * 10


def test_clear_both_triggers():
    """clear() resets both L2 and R2."""
    s = make_stats()
    s.record("L2", 0.5)
    s.record("R2", 0.75)
    s.clear()
    assert s.total_samples("L2") == 0
    assert s.total_samples("R2") == 0


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


def test_comparison_empty():
    """comparison() returns None for each metric when empty."""
    s = make_stats()
    cmp = s.comparison()
    assert len(cmp) == 4
    assert cmp["l2_mean"] is None
    assert cmp["l2_peak"] is None
    assert cmp["r2_mean"] is None
    assert cmp["r2_peak"] is None


def test_comparison_with_data():
    """comparison() returns aggregates for both triggers."""
    s = make_stats()
    for p in [0.1, 0.5, 0.9]:
        s.record("L2", p)
    for p in [0.2, 0.4]:
        s.record("R2", p)
    cmp = s.comparison()
    assert cmp["l2_peak"] == 0.9
    assert abs(cmp["l2_mean"] - 0.5) < 1e-9  # (0.1 + 0.5 + 0.9) / 3
    assert cmp["r2_peak"] == 0.4
    assert abs(cmp["r2_mean"] - 0.3) < 1e-9  # (0.2 + 0.4) / 2


def test_comparison_mixed_coverage():
    """comparison() handles one trigger having data, other empty."""
    s = make_stats()
    s.record("L2", 0.75)
    cmp = s.comparison()
    assert cmp["l2_peak"] == 0.75
    assert cmp["l2_mean"] == 0.75
    assert cmp["r2_peak"] is None
    assert cmp["r2_mean"] is None


# ---------------------------------------------------------------------------
# integration: quick smoke test (the manual verification case)
# ---------------------------------------------------------------------------


def test_quick_smoke():
    """Integration smoke test matching the manual verification command."""
    cfg = TriggerPressureConfig(bucket_count=4)
    s = TriggerPressureStats(cfg)
    pressures = [0.1, 0.5, 0.9, 0.7, 1.0]
    for p in pressures:
        s.record("L2", p)

    buckets = s.buckets("L2")
    mean = s.mean("L2")
    peak = s.peak("L2")

    # Verify the expected output
    assert buckets is not None  # Should be [1, 0, 2, 2]
    assert mean is not None
    assert abs(mean - 0.64) < 0.01  # ~0.64
    assert peak == 1.0
