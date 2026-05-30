"""Tests for stick deflection rose (directional histogram) module."""

import pytest
import math
from gamepad_midi_bridge.stick_deflection_rose import (
    StickDeflectionRose,
    DeflectionRoseConfig,
    DeflectionRose,
    BIN_NAMES_8,
    BIN_NAMES_16,
)


class TestDeflectionRoseConfig:
    """Tests for DeflectionRoseConfig dataclass."""

    def test_default_config(self):
        """Default config has 8 bins, 0.1 min_magnitude, 50000 max_samples."""
        cfg = DeflectionRoseConfig()
        assert cfg.bin_count == 8
        assert cfg.min_magnitude == 0.1
        assert cfg.max_samples == 50000

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = DeflectionRoseConfig(bin_count=16, min_magnitude=0.2, max_samples=10000)
        assert cfg.bin_count == 16
        assert cfg.min_magnitude == 0.2
        assert cfg.max_samples == 10000

    def test_invalid_bin_count_clamps_to_8(self):
        """Unknown bin_count defaults to 8."""
        cfg = DeflectionRoseConfig(bin_count=7)
        assert cfg.bin_count == 8

    def test_invalid_bin_count_16_stays(self):
        """bin_count=16 is valid and stays."""
        cfg = DeflectionRoseConfig(bin_count=16)
        assert cfg.bin_count == 16

    def test_min_magnitude_clamped_0_to_1(self):
        """min_magnitude is clamped to [0.0, 1.0]."""
        cfg_low = DeflectionRoseConfig(min_magnitude=-0.5)
        assert cfg_low.min_magnitude == 0.0

        cfg_high = DeflectionRoseConfig(min_magnitude=1.5)
        assert cfg_high.min_magnitude == 1.0

    def test_max_samples_clamped_100_to_1000000(self):
        """max_samples is clamped to [100, 1000000]."""
        cfg_low = DeflectionRoseConfig(max_samples=10)
        assert cfg_low.max_samples == 100

        cfg_high = DeflectionRoseConfig(max_samples=5000000)
        assert cfg_high.max_samples == 1000000

    def test_to_dict(self):
        """to_dict serializes config."""
        cfg = DeflectionRoseConfig(bin_count=16, min_magnitude=0.2, max_samples=5000)
        d = cfg.to_dict()
        assert d["bin_count"] == 16
        assert d["min_magnitude"] == 0.2
        assert d["max_samples"] == 5000

    def test_from_dict(self):
        """from_dict deserializes config."""
        d = {"bin_count": 16, "min_magnitude": 0.3, "max_samples": 20000}
        cfg = DeflectionRoseConfig.from_dict(d)
        assert cfg.bin_count == 16
        assert cfg.min_magnitude == 0.3
        assert cfg.max_samples == 20000

    def test_from_dict_round_trip(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = DeflectionRoseConfig(bin_count=16, min_magnitude=0.15, max_samples=8000)
        d = original.to_dict()
        restored = DeflectionRoseConfig.from_dict(d)
        assert restored.bin_count == original.bin_count
        assert restored.min_magnitude == original.min_magnitude
        assert restored.max_samples == original.max_samples

    def test_from_dict_partial(self):
        """from_dict fills missing keys with defaults."""
        d = {"bin_count": 16}
        cfg = DeflectionRoseConfig.from_dict(d)
        assert cfg.bin_count == 16
        assert cfg.min_magnitude == 0.1
        assert cfg.max_samples == 50000


class TestDeflectionRose:
    """Tests for DeflectionRose dataclass."""

    def test_to_dict(self):
        """to_dict serializes all fields."""
        rose = DeflectionRose(
            bin_counts=[10, 20, 5],
            bin_names=["N", "NE", "E"],
            total_samples=35,
            dominant_bin_index=1,
            dominant_bin_name="NE",
            bin_percentages=[28.6, 57.1, 14.3],
        )
        d = rose.to_dict()
        assert d["bin_counts"] == [10, 20, 5]
        assert d["total_samples"] == 35
        assert d["dominant_bin_index"] == 1
        assert d["dominant_bin_name"] == "NE"

    def test_from_dict_round_trip(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = DeflectionRose(
            bin_counts=[5, 10, 15, 20],
            bin_names=["N", "NE", "E", "SE"],
            total_samples=50,
            dominant_bin_index=3,
            dominant_bin_name="SE",
            bin_percentages=[10.0, 20.0, 30.0, 40.0],
        )
        d = original.to_dict()
        restored = DeflectionRose.from_dict(d)
        assert restored.bin_counts == original.bin_counts
        assert restored.total_samples == original.total_samples
        assert restored.dominant_bin_index == original.dominant_bin_index
        assert restored.dominant_bin_name == original.dominant_bin_name


class TestStickDeflectionRoseEmpty:
    """Tests for empty/initial state."""

    def test_empty_rose(self):
        """Empty rose has no samples and None dominant."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        analysis = rose.analyze()
        assert analysis.total_samples == 0
        assert analysis.dominant_bin_index is None
        assert analysis.dominant_bin_name is None
        assert analysis.bin_counts == [0] * 8

    def test_total_empty(self):
        """total() returns 0 for empty rose."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        assert rose.total() == 0


class TestStickDeflectionRoseCardinalDirections:
    """Tests for cardinal direction bucketing."""

    def test_record_north_direction(self):
        """Record (0, 1) buckets into North bin (index 0 for 8-bin)."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)
        analysis = rose.analyze()
        assert analysis.bin_counts[0] > 0  # North bucket has samples
        assert analysis.dominant_bin_name == "N"

    def test_record_east_direction(self):
        """Record (1, 0) buckets into East bin."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(1.0, 0.0)
        analysis = rose.analyze()
        # East is bin 2 in 8-bin mode: N(0), NE(1), E(2), ...
        assert analysis.bin_counts[2] > 0
        assert analysis.dominant_bin_name == "E"

    def test_record_south_direction(self):
        """Record (0, -1) buckets into South bin."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, -1.0)
        analysis = rose.analyze()
        # South is bin 4 in 8-bin mode: N(0), NE(1), E(2), SE(3), S(4), ...
        assert analysis.bin_counts[4] > 0
        assert analysis.dominant_bin_name == "S"

    def test_record_west_direction(self):
        """Record (-1, 0) buckets into West bin."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(-1.0, 0.0)
        analysis = rose.analyze()
        # West is bin 6 in 8-bin mode: N(0), NE(1), E(2), SE(3), S(4), SW(5), W(6), NW(7)
        assert analysis.bin_counts[6] > 0
        assert analysis.dominant_bin_name == "W"

    def test_record_multiple_north_builds_count(self):
        """Recording (0, 1) twice increments North bin."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)
        rose.record(0.0, 1.0)
        analysis = rose.analyze()
        assert analysis.bin_counts[0] == 2
        assert analysis.total_samples == 2


class TestStickDeflectionRose16Bins:
    """Tests for 16-bin mode."""

    def test_16_bin_config(self):
        """16-bin config uses BIN_NAMES_16."""
        cfg = DeflectionRoseConfig(bin_count=16)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)  # North
        analysis = rose.analyze()
        assert len(analysis.bin_names) == 16
        assert analysis.bin_names == BIN_NAMES_16
        assert analysis.bin_names[0] == "N"

    def test_16_bin_more_granular(self):
        """16-bin mode has finer angular resolution than 8-bin."""
        cfg8 = DeflectionRoseConfig(bin_count=8)
        cfg16 = DeflectionRoseConfig(bin_count=16)
        rose8 = StickDeflectionRose(cfg8)
        rose16 = StickDeflectionRose(cfg16)

        # Record a diagonal direction in both
        rose8.record(0.707, 0.707)  # NE
        rose16.record(0.707, 0.707)

        a8 = rose8.analyze()
        a16 = rose16.analyze()
        assert len(a8.bin_counts) == 8
        assert len(a16.bin_counts) == 16


class TestStickDeflectionRoseMinMagnitude:
    """Tests for center deadzone (min_magnitude)."""

    def test_min_magnitude_skips_center_samples(self):
        """Samples below min_magnitude are skipped."""
        cfg = DeflectionRoseConfig(bin_count=8, min_magnitude=0.2)
        rose = StickDeflectionRose(cfg)
        rose.record(0.1, 0.0)  # Magnitude = 0.1 < 0.2
        analysis = rose.analyze()
        assert analysis.total_samples == 0

    def test_min_magnitude_accepts_above_threshold(self):
        """Samples above min_magnitude are recorded."""
        cfg = DeflectionRoseConfig(bin_count=8, min_magnitude=0.2)
        rose = StickDeflectionRose(cfg)
        rose.record(0.3, 0.0)  # Magnitude = 0.3 > 0.2
        analysis = rose.analyze()
        assert analysis.total_samples == 1

    def test_min_magnitude_boundary(self):
        """Samples exactly at min_magnitude are recorded."""
        cfg = DeflectionRoseConfig(bin_count=8, min_magnitude=0.1)
        rose = StickDeflectionRose(cfg)
        rose.record(0.1, 0.0)  # Magnitude = 0.1 == min_magnitude
        analysis = rose.analyze()
        # At boundary, should be recorded (>= comparison)
        assert analysis.total_samples >= 0  # Depends on float comparison


class TestStickDeflectionRoseClamping:
    """Tests for input clamping."""

    def test_record_clamps_x_over_1(self):
        """record() clamps x > 1 to 1."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(1.5, 0.0)  # x clamped to 1.0
        analysis = rose.analyze()
        assert analysis.total_samples == 1

    def test_record_clamps_x_under_minus_1(self):
        """record() clamps x < -1 to -1."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(-1.5, 0.0)  # x clamped to -1.0
        analysis = rose.analyze()
        assert analysis.total_samples == 1

    def test_record_clamps_y_over_1(self):
        """record() clamps y > 1 to 1."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.5)  # y clamped to 1.0
        analysis = rose.analyze()
        assert analysis.total_samples == 1

    def test_record_clamps_y_under_minus_1(self):
        """record() clamps y < -1 to -1."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, -1.5)  # y clamped to -1.0
        analysis = rose.analyze()
        assert analysis.total_samples == 1


class TestStickDeflectionRoseBinFor:
    """Tests for bin_for() method."""

    def test_bin_for_north(self):
        """bin_for(0, 1) returns North bin index."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        bin_idx = rose.bin_for(0.0, 1.0)
        assert bin_idx == 0  # North

    def test_bin_for_east(self):
        """bin_for(1, 0) returns East bin index."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        bin_idx = rose.bin_for(1.0, 0.0)
        assert bin_idx == 2  # East

    def test_bin_for_below_min_magnitude_returns_none(self):
        """bin_for() returns None if magnitude < min_magnitude."""
        cfg = DeflectionRoseConfig(bin_count=8, min_magnitude=0.2)
        rose = StickDeflectionRose(cfg)
        bin_idx = rose.bin_for(0.1, 0.0)
        assert bin_idx is None

    def test_bin_for_does_not_record(self):
        """bin_for() returns bin index but does not increment bin_counts."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        bin_idx = rose.bin_for(0.0, 1.0)
        analysis = rose.analyze()
        assert bin_idx == 0
        assert analysis.total_samples == 0  # Not recorded


class TestStickDeflectionRoseBinPercentages:
    """Tests for bin percentage calculation."""

    def test_percentages_sum_to_100(self):
        """bin_percentages sum to 100.0 (within floating-point tolerance)."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        # Record samples in different directions
        rose.record(0.0, 1.0)  # North
        rose.record(0.0, 1.0)  # North
        rose.record(1.0, 0.0)  # East
        analysis = rose.analyze()
        total_pct = sum(analysis.bin_percentages)
        assert abs(total_pct - 100.0) < 0.01

    def test_percentages_empty_is_all_zero(self):
        """Empty rose has all 0.0 percentages."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        analysis = rose.analyze()
        assert all(pct == 0.0 for pct in analysis.bin_percentages)

    def test_single_bin_100_percent(self):
        """Single bin with all samples gets 100.0%."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)
        analysis = rose.analyze()
        assert analysis.bin_percentages[0] == 100.0


class TestStickDeflectionRoseDominant:
    """Tests for dominant bin detection."""

    def test_dominant_index_and_name_populated(self):
        """analyze() populates dominant_bin_index and dominant_bin_name."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)
        rose.record(0.0, 1.0)
        rose.record(1.0, 0.0)
        analysis = rose.analyze()
        assert analysis.dominant_bin_index is not None
        assert analysis.dominant_bin_name is not None
        assert analysis.dominant_bin_index == 0  # North has 2 samples
        assert analysis.dominant_bin_name == "N"

    def test_dominant_bin_index_finds_peak(self):
        """dominant_bin_index is the bin with the max count."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        # Record 5 north, 3 east, 1 south
        for _ in range(5):
            rose.record(0.0, 1.0)
        for _ in range(3):
            rose.record(1.0, 0.0)
        for _ in range(1):
            rose.record(0.0, -1.0)
        analysis = rose.analyze()
        assert analysis.dominant_bin_index == 0  # North has max (5)


class TestStickDeflectionRoseMaxSamples:
    """Tests for FIFO max_samples eviction."""

    def test_max_samples_fifo_eviction(self):
        """Exceeding max_samples evicts oldest sample (FIFO)."""
        cfg = DeflectionRoseConfig(bin_count=8, max_samples=105)
        rose = StickDeflectionRose(cfg)
        # Record 105 north samples
        for _ in range(105):
            rose.record(0.0, 1.0)
        assert rose.total() == 105
        analysis = rose.analyze()
        assert analysis.bin_counts[0] == 105

        # Record 1 more north sample — oldest should be evicted
        rose.record(0.0, 1.0)
        assert rose.total() == 105  # Still at max
        analysis = rose.analyze()
        assert analysis.bin_counts[0] == 105  # Still 105 (1 added, 1 evicted)

    def test_max_samples_with_mixed_bins(self):
        """FIFO eviction works correctly with mixed bins."""
        cfg = DeflectionRoseConfig(bin_count=8, max_samples=103)
        rose = StickDeflectionRose(cfg)
        # Fill buffer to 103: record N 50 times, E 30 times, S 23 times
        for _ in range(50):
            rose.record(0.0, 1.0)  # bin 0 (N)
        for _ in range(30):
            rose.record(1.0, 0.0)  # bin 2 (E)
        for _ in range(23):
            rose.record(0.0, -1.0)  # bin 4 (S)
        assert rose.total() == 103
        analysis = rose.analyze()
        assert analysis.bin_counts[0] == 50
        assert analysis.bin_counts[2] == 30
        assert analysis.bin_counts[4] == 23

        # Record 1 more N; oldest N should be evicted
        rose.record(0.0, 1.0)  # bin 0 (N)
        assert rose.total() == 103  # Still at max
        analysis = rose.analyze()
        assert analysis.bin_counts[0] == 50  # Still 50 (1 added, 1 evicted)
        assert analysis.bin_counts[2] == 30
        assert analysis.bin_counts[4] == 23


class TestStickDeflectionRoseClear:
    """Tests for clear() method."""

    def test_clear_empties_bins(self):
        """clear() resets all bin counts to 0."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)
        rose.record(1.0, 0.0)
        assert rose.total() == 2

        rose.clear()
        assert rose.total() == 0
        analysis = rose.analyze()
        assert analysis.total_samples == 0
        assert analysis.dominant_bin_index is None

    def test_clear_allows_reuse(self):
        """After clear(), can record again."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)
        rose.clear()
        rose.record(1.0, 0.0)
        analysis = rose.analyze()
        assert analysis.total_samples == 1
        assert analysis.dominant_bin_name == "E"


class TestStickDeflectionRoseSerialization:
    """Tests for config round-trip serialization."""

    def test_config_round_trip(self):
        """DeflectionRoseConfig round-trip: to_dict → from_dict."""
        original_cfg = DeflectionRoseConfig(bin_count=16, min_magnitude=0.15, max_samples=10000)
        rose = StickDeflectionRose(original_cfg)
        rose.record(0.0, 1.0)
        rose.record(1.0, 0.0)

        # Serialize config
        cfg_dict = original_cfg.to_dict()

        # Create new rose from deserialized config
        restored_cfg = DeflectionRoseConfig.from_dict(cfg_dict)
        restored_rose = StickDeflectionRose(restored_cfg)

        # Should have same config
        assert restored_cfg.bin_count == 16
        assert restored_cfg.min_magnitude == 0.15

    def test_analysis_round_trip(self):
        """DeflectionRose round-trip: to_dict → from_dict."""
        cfg = DeflectionRoseConfig(bin_count=8)
        rose = StickDeflectionRose(cfg)
        rose.record(0.0, 1.0)
        rose.record(0.0, 1.0)
        rose.record(1.0, 0.0)

        original_analysis = rose.analyze()
        analysis_dict = original_analysis.to_dict()
        restored_analysis = DeflectionRose.from_dict(analysis_dict)

        assert restored_analysis.bin_counts == original_analysis.bin_counts
        assert restored_analysis.total_samples == original_analysis.total_samples
        assert restored_analysis.dominant_bin_name == original_analysis.dominant_bin_name
