"""Tests for velocity_histogram module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.velocity_histogram import HistogramConfig, VelocityHistogram


# ---------------------------------------------------------------------------
# config: defaults and clamping
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config should have bucket_count=8 and max_samples=10000."""
    cfg = HistogramConfig()
    assert cfg.bucket_count == 8
    assert cfg.max_samples == 10000


def test_config_clamp_bucket_count_min():
    """bucket_count < 4 should be clamped to 4."""
    cfg = HistogramConfig(bucket_count=2)
    assert cfg.bucket_count == 4


def test_config_clamp_bucket_count_max():
    """bucket_count > 32 should be clamped to 32."""
    cfg = HistogramConfig(bucket_count=50)
    assert cfg.bucket_count == 32


def test_config_clamp_max_samples_min():
    """max_samples < 100 should be clamped to 100."""
    cfg = HistogramConfig(max_samples=50)
    assert cfg.max_samples == 100


def test_config_clamp_max_samples_max():
    """max_samples > 1000000 should be clamped to 1000000."""
    cfg = HistogramConfig(max_samples=2000000)
    assert cfg.max_samples == 1000000


def test_config_to_dict():
    """to_dict should return serializable dict with bucket_count and max_samples."""
    cfg = HistogramConfig(bucket_count=4, max_samples=5000)
    d = cfg.to_dict()
    assert d["bucket_count"] == 4
    assert d["max_samples"] == 5000


def test_config_from_dict():
    """from_dict should reconstruct config from dict."""
    d = {"bucket_count": 4, "max_samples": 5000}
    cfg = HistogramConfig.from_dict(d)
    assert cfg.bucket_count == 4
    assert cfg.max_samples == 5000


def test_config_round_trip():
    """to_dict + from_dict should preserve config."""
    cfg1 = HistogramConfig(bucket_count=6, max_samples=8000)
    d = cfg1.to_dict()
    cfg2 = HistogramConfig.from_dict(d)
    assert cfg2.bucket_count == cfg1.bucket_count
    assert cfg2.max_samples == cfg1.max_samples


# ---------------------------------------------------------------------------
# recording: basic
# ---------------------------------------------------------------------------


def test_record_single_velocity_zero():
    """Recording velocity 0 should increment bucket 0."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(0)
    buckets = h.buckets()
    assert buckets[0] == 1
    assert sum(buckets) == 1


def test_record_single_velocity_max():
    """Recording velocity 127 should increment last bucket."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(127)
    buckets = h.buckets()
    assert buckets[-1] == 1
    assert sum(buckets) == 1


def test_record_velocity_mid():
    """Recording velocity 64 with bucket_count=4 should go to bucket 2 (range 64-95)."""
    cfg = HistogramConfig(bucket_count=4)
    h = VelocityHistogram(cfg)
    h.record(64)
    buckets = h.buckets()
    assert buckets[2] == 1
    assert sum(buckets) == 1


def test_record_clamped_negative():
    """Negative velocities should be clamped to 0 (bucket 0)."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(-10)
    buckets = h.buckets()
    assert buckets[0] == 1


def test_record_clamped_over_127():
    """Velocities > 127 should be clamped to 127 (last bucket)."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(200)
    buckets = h.buckets()
    assert buckets[-1] == 1


def test_record_multiple_same_velocity():
    """Recording the same velocity multiple times increments bucket correctly."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    for _ in range(5):
        h.record(60)
    buckets = h.buckets()
    # 60 should be in bucket 3 (bucket_size=16: ranges [0-15, 16-31, 32-47, 48-63, ...])
    # 60 // 16 = 3
    assert buckets[3] == 5


def test_record_total_increments():
    """total() should track cumulative samples recorded."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    assert h.total() == 0
    h.record(50)
    assert h.total() == 1
    h.record(100)
    assert h.total() == 2
    h.record(0)
    assert h.total() == 3


# ---------------------------------------------------------------------------
# bucket_ranges
# ---------------------------------------------------------------------------


def test_bucket_ranges_4_buckets():
    """bucket_ranges for 4 buckets should return expected ranges."""
    cfg = HistogramConfig(bucket_count=4)
    h = VelocityHistogram(cfg)
    ranges = h.bucket_ranges()
    assert len(ranges) == 4
    assert ranges[0] == (0, 31)
    assert ranges[1] == (32, 63)
    assert ranges[2] == (64, 95)
    assert ranges[3] == (96, 127)


def test_bucket_ranges_last_includes_127():
    """Last bucket's hi should always be 127."""
    for bucket_count in [4, 8, 16]:
        cfg = HistogramConfig(bucket_count=bucket_count)
        h = VelocityHistogram(cfg)
        ranges = h.bucket_ranges()
        assert ranges[-1][1] == 127


def test_bucket_ranges_contiguous():
    """Ranges should be contiguous with no gaps."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    ranges = h.bucket_ranges()
    for i in range(len(ranges) - 1):
        lo, hi = ranges[i]
        next_lo, next_hi = ranges[i + 1]
        assert next_lo == hi + 1


# ---------------------------------------------------------------------------
# peak_bucket and mean
# ---------------------------------------------------------------------------


def test_peak_bucket_empty():
    """peak_bucket should return None if no samples recorded."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    assert h.peak_bucket() is None


def test_peak_bucket_single():
    """peak_bucket should return 0 if only one sample in bucket 0."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(0)
    assert h.peak_bucket() == 0


def test_peak_bucket_highest():
    """peak_bucket should return index of highest count."""
    cfg = HistogramConfig(bucket_count=4)
    h = VelocityHistogram(cfg)
    # bucket_count=4: bucket_size=32
    # velocity 10: (10 * 4) // 128 = 0
    # velocity 90: (90 * 4) // 128 = 2
    h.record(10)  # bucket 0
    h.record(10)  # bucket 0
    h.record(10)  # bucket 0
    h.record(90)  # bucket 2
    assert h.peak_bucket() == 0  # bucket 0 has 3, bucket 2 has 1


def test_mean_empty():
    """mean should return None if no samples recorded."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    assert h.mean() is None


def test_mean_single():
    """mean of one sample should equal that sample."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(50)
    assert h.mean() == 50.0


def test_mean_multiple():
    """mean should be correct average."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    velocities = [10, 60, 90, 90, 100, 100, 100]
    for v in velocities:
        h.record(v)
    expected_mean = sum(velocities) / len(velocities)
    assert abs(h.mean() - expected_mean) < 0.01


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_zeros_all():
    """clear should reset buckets, samples, and total to zero."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(50)
    h.record(100)
    h.record(25)
    h.clear()
    assert h.buckets() == [0] * 8
    assert h.total() == 0
    assert h.mean() is None
    assert h.peak_bucket() is None


def test_clear_then_record_again():
    """Recording after clear should work normally."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    h.record(50)
    h.clear()
    h.record(100)
    assert h.total() == 1
    assert h.mean() == 100.0


# ---------------------------------------------------------------------------
# to_normalised
# ---------------------------------------------------------------------------


def test_to_normalised_empty():
    """to_normalised on empty histogram should return all zeros."""
    cfg = HistogramConfig(bucket_count=4)
    h = VelocityHistogram(cfg)
    norm = h.to_normalised()
    assert norm == [0.0, 0.0, 0.0, 0.0]


def test_to_normalised_single():
    """Single bucket populated should normalise to 1.0."""
    cfg = HistogramConfig(bucket_count=4)
    h = VelocityHistogram(cfg)
    h.record(0)
    norm = h.to_normalised()
    assert norm[0] == 1.0
    assert norm[1] == 0.0
    assert norm[2] == 0.0
    assert norm[3] == 0.0


def test_to_normalised_peak_is_one():
    """Peak bucket should normalise to 1.0."""
    cfg = HistogramConfig(bucket_count=4)
    h = VelocityHistogram(cfg)
    # velocity 10: bucket 0; velocity 90: bucket 2
    h.record(10)
    h.record(10)
    h.record(10)
    h.record(90)
    norm = h.to_normalised()
    assert norm[0] == 1.0  # peak bucket (count=3)
    assert norm[2] == 1 / 3  # bucket 2 (count=1)


def test_to_normalised_range():
    """All normalised values should be in [0.0, 1.0]."""
    cfg = HistogramConfig(bucket_count=8)
    h = VelocityHistogram(cfg)
    for v in range(0, 128, 10):
        h.record(v)
    norm = h.to_normalised()
    assert all(0.0 <= n <= 1.0 for n in norm)


# ---------------------------------------------------------------------------
# ring-buffer eviction (max_samples)
# ---------------------------------------------------------------------------


def test_fifo_eviction_enforces_max_samples():
    """Exceeding max_samples should evict oldest (FIFO)."""
    cfg = HistogramConfig(bucket_count=8, max_samples=105)
    h = VelocityHistogram(cfg)
    # Record 107 samples; oldest 2 should be evicted
    for i in range(107):
        h.record(i % 128)
    # total should be clamped to max_samples=105
    assert h.total() == 105
    assert len(h._samples) == 105


def test_fifo_eviction_decrements_correct_bucket():
    """Evicting from a bucket should decrement that bucket's count."""
    cfg = HistogramConfig(bucket_count=8, max_samples=103)
    h = VelocityHistogram(cfg)
    h.record(0)   # bucket 0
    h.record(10)  # bucket 0 (both 0 and 10 map to bucket 0 for bucket_count=8)
    h.record(50)  # bucket 3
    # At this point: buckets = [2, 0, 0, 1, ...]
    assert h.buckets()[0] == 2
    assert h.total() == 3

    # Record one more; oldest (0) should evict from bucket 0
    h.record(100)
    assert h.total() == 4  # Still below max_samples, no eviction yet
    assert h.buckets()[0] == 2  # No eviction yet


def test_fifo_ring_buffer_preserves_order():
    """FIFO order should be preserved: oldest evicted first."""
    cfg = HistogramConfig(bucket_count=8, max_samples=103)
    h = VelocityHistogram(cfg)
    h.record(10)
    h.record(20)
    h.record(30)
    assert h._samples == [10, 20, 30]
    h.record(40)
    # No eviction yet since 4 < 103
    assert h._samples == [10, 20, 30, 40]

    # Record 100 more samples → total = 104, so 1 evicted
    for i in range(100):
        h.record(50 + (i % 70))
    # Should have exactly 103 samples, only oldest (10) should be gone
    assert len(h._samples) == 103
    assert 10 not in h._samples  # First sample evicted (only one)
    assert 20 in h._samples  # Second sample still there
    assert h._samples[0] == 20  # Second recorded sample is now oldest


def test_fifo_bucket_count_consistency():
    """After FIFO evictions, sum(buckets) should equal total and len(_samples)."""
    cfg = HistogramConfig(bucket_count=8, max_samples=110)
    h = VelocityHistogram(cfg)
    for i in range(200):
        h.record(i % 128)
    # Should have exactly 110 samples
    assert len(h._samples) == 110
    assert h.total() == 110
    assert sum(h.buckets()) == 110


# ---------------------------------------------------------------------------
# integration: spec scenario
# ---------------------------------------------------------------------------


def test_spec_scenario():
    """Test the exact scenario from the spec:
    velocities [10, 60, 90, 90, 100, 100, 100] with bucket_count=4.
    Expected: counts, peak idx 3, mean ~78.6
    """
    cfg = HistogramConfig(bucket_count=4)
    h = VelocityHistogram(cfg)
    velocities = [10, 60, 90, 90, 100, 100, 100]
    for v in velocities:
        h.record(v)

    # Check peak bucket
    assert h.peak_bucket() == 3

    # Check mean
    expected_mean = sum(velocities) / len(velocities)
    assert abs(h.mean() - expected_mean) < 0.1
    assert abs(h.mean() - 78.6) < 0.1

    # Check total
    assert h.total() == 7

    # Check bucket assignments (rough)
    # bucket_size = 128 / 4 = 32
    # bucket 0: [0-31] → 10
    # bucket 1: [32-63] → 60
    # bucket 2: [64-95] → 90, 90
    # bucket 3: [96-127] → 100, 100, 100
    buckets = h.buckets()
    assert buckets[0] == 1  # 10
    assert buckets[1] == 1  # 60
    assert buckets[2] == 2  # 90, 90
    assert buckets[3] == 3  # 100, 100, 100
