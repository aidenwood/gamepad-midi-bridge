"""Tests for note hold distribution bucketing and categorical analysis."""
import pytest

from gamepad_midi_bridge.note_hold_distribution import (
    BUCKET_BOUNDS_S,
    BUCKET_NAMES,
    HoldDistribution,
    HoldDistributionConfig,
    NoteHoldDistribution,
)


class TestBucketConstants:
    """Verify bucket constant structure."""

    def test_bucket_names_count(self):
        """BUCKET_NAMES should have 5 entries."""
        assert len(BUCKET_NAMES) == 5

    def test_bucket_bounds_count(self):
        """BUCKET_BOUNDS_S should have 4 entries."""
        assert len(BUCKET_BOUNDS_S) == 4

    def test_bucket_bounds_ordered(self):
        """BUCKET_BOUNDS_S should be strictly increasing."""
        for i in range(len(BUCKET_BOUNDS_S) - 1):
            assert BUCKET_BOUNDS_S[i] < BUCKET_BOUNDS_S[i + 1]


class TestHoldDistributionConfig:
    """Test HoldDistributionConfig serialization and clamping."""

    def test_default_config(self):
        """Default config should have max_samples=5000."""
        cfg = HoldDistributionConfig()
        assert cfg.max_samples == 5000

    def test_config_clamp_min(self):
        """Config should clamp max_samples to min 100."""
        cfg = HoldDistributionConfig(max_samples=50)
        assert cfg.max_samples == 100

    def test_config_clamp_max(self):
        """Config should clamp max_samples to max 1000000."""
        cfg = HoldDistributionConfig(max_samples=2000000)
        assert cfg.max_samples == 1000000

    def test_config_round_trip(self):
        """Config should serialize and deserialize correctly."""
        cfg = HoldDistributionConfig(max_samples=1000)
        data = cfg.to_dict()
        cfg2 = HoldDistributionConfig.from_dict(data)
        assert cfg2.max_samples == 1000


class TestHoldDistribution:
    """Test HoldDistribution dataclass."""

    def test_default_distribution(self):
        """Default distribution should have zero counts."""
        dist = HoldDistribution()
        assert dist.total_notes == 0
        assert dist.bucket_counts == [0, 0, 0, 0, 0]
        assert dist.dominant_bucket_index is None
        assert dist.dominant_bucket_name is None

    def test_distribution_round_trip(self):
        """Distribution should serialize and deserialize correctly."""
        dist = HoldDistribution(
            bucket_counts=[2, 1, 3, 1, 0],
            total_notes=7,
            dominant_bucket_index=2,
            dominant_bucket_name="medium",
            bucket_percentages=[28.57, 14.29, 42.86, 14.29, 0.0],
        )
        data = dist.to_dict()
        dist2 = HoldDistribution.from_dict(data)
        assert dist2.bucket_counts == [2, 1, 3, 1, 0]
        assert dist2.total_notes == 7
        assert dist2.dominant_bucket_index == 2
        assert dist2.dominant_bucket_name == "medium"


class TestBucketFor:
    """Test bucket assignment logic."""

    def test_stab_bucket(self):
        """duration < 0.1s should be bucket 0 (stab)."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        assert dist.bucket_for(0.05) == 0

    def test_short_bucket(self):
        """0.1s <= duration < 0.3s should be bucket 1 (short)."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        assert dist.bucket_for(0.1) == 1
        assert dist.bucket_for(0.2) == 1

    def test_medium_bucket(self):
        """0.3s <= duration < 1.0s should be bucket 2 (medium)."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        assert dist.bucket_for(0.3) == 2
        assert dist.bucket_for(0.5) == 2

    def test_long_bucket(self):
        """1.0s <= duration < 3.0s should be bucket 3 (long)."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        assert dist.bucket_for(1.0) == 3
        assert dist.bucket_for(2.0) == 3

    def test_sustained_bucket(self):
        """duration >= 3.0s should be bucket 4 (sustained)."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        assert dist.bucket_for(3.0) == 4
        assert dist.bucket_for(5.0) == 4

    def test_bucket_for_negative_clamped(self):
        """Negative duration should be clamped to 0 (stab bucket)."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        assert dist.bucket_for(-1.0) == 0


class TestRecord:
    """Test recording note hold durations."""

    def test_record_single_note(self):
        """Recording one note should increment correct bucket."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.05)
        assert dist._bucket_counts == [1, 0, 0, 0, 0]

    def test_record_multiple_buckets(self):
        """Recording notes should increment correct buckets."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.05)  # stab
        dist.record(0.2)   # short
        dist.record(0.5)   # medium
        dist.record(2.0)   # long
        dist.record(5.0)   # sustained
        assert dist._bucket_counts == [1, 1, 1, 1, 1]

    def test_record_negative_clamped(self):
        """Negative duration should be clamped and placed in stab."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(-0.5)
        assert dist._bucket_counts == [1, 0, 0, 0, 0]

    def test_record_fifo_eviction(self):
        """Exceeding max_samples should evict oldest with bucket decrement."""
        cfg = HoldDistributionConfig(max_samples=4)  # Will be clamped to 100 (min), so use bigger value
        dist = NoteHoldDistribution(cfg)
        # Use a smaller max for testing by directly setting it
        dist.config.max_samples = 3

        dist.record(0.05)  # stab: [1, 0, 0, 0, 0]
        dist.record(0.2)   # short: [1, 1, 0, 0, 0]
        dist.record(0.5)   # medium: [1, 1, 1, 0, 0]
        assert dist._bucket_counts == [1, 1, 1, 0, 0]
        assert len(dist._durations) == 3

        dist.record(2.0)   # long: evict stab (0.05), buckets become [0, 1, 1, 1, 0]
        assert dist._bucket_counts == [0, 1, 1, 1, 0]
        assert len(dist._durations) == 3


class TestAnalyze:
    """Test analyze() results."""

    def test_analyze_empty(self):
        """Empty distribution should have None dominant."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        result = dist.analyze()
        assert result.total_notes == 0
        assert result.bucket_counts == [0, 0, 0, 0, 0]
        assert result.dominant_bucket_index is None
        assert result.dominant_bucket_name is None
        assert result.bucket_percentages == [0.0, 0.0, 0.0, 0.0, 0.0]

    def test_analyze_single_note(self):
        """Single note should have 100% in one bucket."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.2)
        result = dist.analyze()
        assert result.total_notes == 1
        assert result.bucket_counts == [0, 1, 0, 0, 0]
        assert result.dominant_bucket_index == 1
        assert result.dominant_bucket_name == "short"
        assert result.bucket_percentages[1] == 100.0

    def test_analyze_multiple_notes(self):
        """Multiple notes should show distribution."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.05)  # stab
        dist.record(0.05)  # stab
        dist.record(0.2)   # short
        dist.record(0.5)   # medium
        dist.record(0.5)   # medium
        dist.record(0.5)   # medium
        dist.record(2.0)   # long
        result = dist.analyze()
        assert result.total_notes == 7
        assert result.bucket_counts == [2, 1, 3, 1, 0]
        assert result.dominant_bucket_index == 2
        assert result.dominant_bucket_name == "medium"
        # Percentages: [2/7, 1/7, 3/7, 1/7, 0/7] * 100
        assert abs(result.bucket_percentages[0] - 28.571428) < 0.01
        assert abs(result.bucket_percentages[2] - 42.857142) < 0.01

    def test_analyze_percentages_sum(self):
        """Bucket percentages should sum to 100."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        for duration in [0.05, 0.2, 0.5, 2.0, 5.0]:
            dist.record(duration)
        result = dist.analyze()
        total_pct = sum(result.bucket_percentages)
        assert abs(total_pct - 100.0) < 0.01

    def test_analyze_dominant_finds_peak(self):
        """Dominant should be the bucket with highest count."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        for _ in range(10):
            dist.record(0.05)  # stab
        for _ in range(5):
            dist.record(0.2)  # short
        result = dist.analyze()
        assert result.dominant_bucket_index == 0
        assert result.dominant_bucket_name == "stab"


class TestClear:
    """Test clearing state."""

    def test_clear_resets_durations(self):
        """Clear should empty durations list."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.05)
        dist.record(0.2)
        assert len(dist._durations) == 2
        dist.clear()
        assert len(dist._durations) == 0

    def test_clear_resets_buckets(self):
        """Clear should reset all bucket counts to 0."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.05)
        dist.record(0.2)
        dist.record(0.5)
        assert dist._bucket_counts == [1, 1, 1, 0, 0]
        dist.clear()
        assert dist._bucket_counts == [0, 0, 0, 0, 0]

    def test_clear_then_record(self):
        """After clear, should be able to record again."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.05)
        dist.clear()
        dist.record(0.2)
        assert dist._bucket_counts == [0, 1, 0, 0, 0]


class TestTotal:
    """Test total() method."""

    def test_total_empty(self):
        """Total should be 0 when empty."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        assert dist.total() == 0

    def test_total_after_records(self):
        """Total should match number of records."""
        dist = NoteHoldDistribution(HoldDistributionConfig())
        dist.record(0.05)
        dist.record(0.2)
        dist.record(0.5)
        assert dist.total() == 3
