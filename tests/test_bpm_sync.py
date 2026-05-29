"""Tests for BPM and beat-grid synchronisation module."""

import pytest
from gamepad_midi_bridge.bpm_sync import (
    SUBDIVISIONS,
    bpm_to_quarter_ms,
    subdivision_ms,
    snap_ms_to_grid,
    ms_to_nearest_subdivision,
    subdivisions_per_bar,
    BpmSyncConfig,
)


class TestBpmToQuarterMs:
    """Tests for BPM to quarter note millisecond conversion."""

    def test_120_bpm(self):
        """120 BPM should be 500ms per quarter."""
        assert bpm_to_quarter_ms(120) == 500.0

    def test_60_bpm(self):
        """60 BPM should be 1000ms per quarter."""
        assert bpm_to_quarter_ms(60) == 1000.0

    def test_240_bpm(self):
        """240 BPM should be 250ms per quarter."""
        assert bpm_to_quarter_ms(240) == 250.0

    def test_zero_bpm_raises(self):
        """BPM of 0 should raise ValueError."""
        with pytest.raises(ValueError):
            bpm_to_quarter_ms(0)

    def test_negative_bpm_raises(self):
        """Negative BPM should raise ValueError."""
        with pytest.raises(ValueError):
            bpm_to_quarter_ms(-120)


class TestSubdivisionMs:
    """Tests for subdivision duration calculation."""

    def test_quarter_at_120_bpm(self):
        """Quarter note at 120 BPM is 500ms."""
        assert subdivision_ms(120, "1/4") == 500.0

    def test_sixteenth_at_120_bpm(self):
        """Sixteenth note at 120 BPM is 125ms."""
        assert subdivision_ms(120, "1/16") == 125.0

    def test_eighth_at_120_bpm(self):
        """Eighth note at 120 BPM is 250ms."""
        assert subdivision_ms(120, "1/8") == 250.0

    def test_dotted_eighth_at_120_bpm(self):
        """Dotted eighth at 120 BPM is 375ms (1.5 * 250)."""
        assert subdivision_ms(120, "1/8d") == 375.0

    def test_eighth_triplet_at_120_bpm(self):
        """Eighth triplet at 120 BPM is ~166.67ms."""
        result = subdivision_ms(120, "1/8t")
        assert pytest.approx(result, abs=0.01) == 166.67

    def test_quarter_triplet_at_120_bpm(self):
        """Quarter triplet at 120 BPM is ~333.33ms."""
        result = subdivision_ms(120, "1/4t")
        assert pytest.approx(result, abs=0.01) == 333.33

    def test_dotted_quarter_at_120_bpm(self):
        """Dotted quarter at 120 BPM is 750ms."""
        assert subdivision_ms(120, "1/4d") == 750.0

    def test_whole_note_at_120_bpm(self):
        """Whole note at 120 BPM is 2000ms."""
        assert subdivision_ms(120, "1/1") == 2000.0

    def test_unknown_subdivision_raises(self):
        """Unknown subdivision should raise KeyError."""
        with pytest.raises(KeyError):
            subdivision_ms(120, "1/7")

    def test_invalid_bpm_raises(self):
        """Invalid BPM should raise ValueError."""
        with pytest.raises(ValueError):
            subdivision_ms(0, "1/16")


class TestSnapMsToGrid:
    """Tests for snapping durations to beat grid."""

    def test_snap_130_to_125(self):
        """130ms should snap to 125ms (nearest 1/16 at 120 BPM)."""
        result = snap_ms_to_grid(130, 120, "1/16")
        assert result == 125.0

    def test_snap_180_to_125(self):
        """180ms should snap to 125ms (nearest 1/16 at 120 BPM)."""
        result = snap_ms_to_grid(180, 120, "1/16")
        assert result == 125.0

    def test_snap_to_quarter(self):
        """510ms should snap to 500ms (nearest 1/4 at 120 BPM)."""
        result = snap_ms_to_grid(510, 120, "1/4")
        assert result == 500.0

    def test_snap_to_eighth(self):
        """260ms should snap to 250ms (nearest 1/8 at 120 BPM)."""
        result = snap_ms_to_grid(260, 120, "1/8")
        assert result == 250.0

    def test_snap_already_on_grid(self):
        """Duration already on grid should remain unchanged."""
        result = snap_ms_to_grid(125, 120, "1/16")
        assert result == 125.0

    def test_snap_with_fast_tempo(self):
        """Snap should work correctly at higher BPM."""
        # At 240 BPM, 1/16 = 62.5ms
        result = snap_ms_to_grid(65, 240, "1/16")
        assert result == 62.5


class TestMsToNearestSubdivision:
    """Tests for finding nearest subdivision."""

    def test_125ms_is_sixteenth(self):
        """125ms at 120 BPM is a sixteenth note."""
        assert ms_to_nearest_subdivision(125, 120) == "1/16"

    def test_500ms_is_quarter(self):
        """500ms at 120 BPM is a quarter note."""
        assert ms_to_nearest_subdivision(500, 120) == "1/4"

    def test_250ms_is_eighth(self):
        """250ms at 120 BPM is an eighth note."""
        assert ms_to_nearest_subdivision(250, 120) == "1/8"

    def test_1000ms_is_half(self):
        """1000ms at 120 BPM is a half note."""
        assert ms_to_nearest_subdivision(1000, 120) == "1/2"

    def test_2000ms_is_whole(self):
        """2000ms at 120 BPM is a whole note."""
        assert ms_to_nearest_subdivision(2000, 120) == "1/1"

    def test_375ms_is_dotted_eighth(self):
        """375ms at 120 BPM is a dotted eighth."""
        assert ms_to_nearest_subdivision(375, 120) == "1/8d"


class TestSubdivisionsPerBar:
    """Tests for subdivisions per bar calculation."""

    def test_sixteenth_per_bar(self):
        """16 sixteenths fit in a 4/4 bar."""
        assert subdivisions_per_bar("1/16") == 16.0

    def test_quarter_per_bar(self):
        """4 quarters fit in a 4/4 bar."""
        assert subdivisions_per_bar("1/4") == 4.0

    def test_eighth_per_bar(self):
        """8 eighths fit in a 4/4 bar."""
        assert subdivisions_per_bar("1/8") == 8.0

    def test_half_per_bar(self):
        """2 halves fit in a 4/4 bar."""
        assert subdivisions_per_bar("1/2") == 2.0

    def test_whole_per_bar(self):
        """1 whole note fits in a 4/4 bar."""
        assert subdivisions_per_bar("1/1") == 1.0

    def test_dotted_eighth_per_bar(self):
        """Dotted eighth: 4 / 0.75 = 5.333..."""
        result = subdivisions_per_bar("1/8d")
        assert pytest.approx(result, abs=0.01) == 5.33

    def test_quarter_triplet_per_bar(self):
        """Quarter triplet: 4 / (2/3) = 6."""
        result = subdivisions_per_bar("1/4t")
        assert pytest.approx(result, abs=0.01) == 6.0

    def test_custom_beats_per_bar(self):
        """Test with custom time signature (3/4)."""
        result = subdivisions_per_bar("1/16", beats_per_bar=3)
        assert result == 12.0

    def test_unknown_subdivision_raises(self):
        """Unknown subdivision should raise KeyError."""
        with pytest.raises(KeyError):
            subdivisions_per_bar("1/7")


class TestBpmSyncConfig:
    """Tests for BpmSyncConfig dataclass."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = BpmSyncConfig()
        assert config.enabled is False
        assert config.bpm == 120.0
        assert config.subdivision == "1/16"

    def test_custom_config(self):
        """Custom config should respect provided values."""
        config = BpmSyncConfig(enabled=True, bpm=140, subdivision="1/8")
        assert config.enabled is True
        assert config.bpm == 140.0
        assert config.subdivision == "1/8"

    def test_bpm_clamping_low(self):
        """BPM below 20 should clamp to 20."""
        config = BpmSyncConfig(bpm=10)
        assert config.bpm == 20.0

    def test_bpm_clamping_high(self):
        """BPM above 300 should clamp to 300."""
        config = BpmSyncConfig(bpm=400)
        assert config.bpm == 300.0

    def test_bpm_valid_range(self):
        """Valid BPM should pass through unchanged."""
        config = BpmSyncConfig(bpm=100)
        assert config.bpm == 100.0

    def test_invalid_subdivision_defaults(self):
        """Invalid subdivision should default to '1/16'."""
        config = BpmSyncConfig(subdivision="1/7")
        assert config.subdivision == "1/16"

    def test_valid_subdivision(self):
        """Valid subdivision should be preserved."""
        config = BpmSyncConfig(subdivision="1/8d")
        assert config.subdivision == "1/8d"

    def test_to_dict(self):
        """Config should serialize to dict."""
        config = BpmSyncConfig(enabled=True, bpm=140, subdivision="1/8")
        data = config.to_dict()
        assert data["enabled"] is True
        assert data["bpm"] == 140.0
        assert data["subdivision"] == "1/8"

    def test_from_dict(self):
        """Config should deserialise from dict."""
        data = {"enabled": True, "bpm": 140, "subdivision": "1/8"}
        config = BpmSyncConfig.from_dict(data)
        assert config.enabled is True
        assert config.bpm == 140.0
        assert config.subdivision == "1/8"

    def test_round_trip_serialization(self):
        """Config should round-trip through dict serialization."""
        original = BpmSyncConfig(enabled=True, bpm=150, subdivision="1/4d")
        data = original.to_dict()
        restored = BpmSyncConfig.from_dict(data)
        assert restored.enabled == original.enabled
        assert restored.bpm == original.bpm
        assert restored.subdivision == original.subdivision

    def test_from_dict_with_clamping(self):
        """Deserialization should apply validation."""
        data = {"enabled": False, "bpm": 500, "subdivision": "1/9"}
        config = BpmSyncConfig.from_dict(data)
        assert config.bpm == 300.0  # clamped
        assert config.subdivision == "1/16"  # defaulted


class TestSubdivisionsConstant:
    """Tests for SUBDIVISIONS mapping."""

    def test_all_subdivisions_present(self):
        """All expected subdivisions should be in the mapping."""
        expected = {
            "1/1", "1/2", "1/4", "1/8", "1/16", "1/32",
            "1/2d", "1/4d", "1/8d", "1/16d",
            "1/4t", "1/8t", "1/16t",
        }
        assert set(SUBDIVISIONS.keys()) == expected

    def test_standard_subdivisions_values(self):
        """Standard subdivisions should have correct multipliers."""
        assert SUBDIVISIONS["1/1"] == 4.0
        assert SUBDIVISIONS["1/2"] == 2.0
        assert SUBDIVISIONS["1/4"] == 1.0
        assert SUBDIVISIONS["1/8"] == 0.5
        assert SUBDIVISIONS["1/16"] == 0.25
        assert SUBDIVISIONS["1/32"] == 0.125

    def test_dotted_subdivisions_values(self):
        """Dotted subdivisions should be 1.5x their base."""
        assert SUBDIVISIONS["1/4d"] == 1.5 * SUBDIVISIONS["1/4"]
        assert SUBDIVISIONS["1/8d"] == 1.5 * SUBDIVISIONS["1/8"]
        assert SUBDIVISIONS["1/16d"] == 1.5 * SUBDIVISIONS["1/16"]

    def test_triplet_subdivisions_values(self):
        """Triplet subdivisions should be 2/3 of their base."""
        assert SUBDIVISIONS["1/4t"] == pytest.approx(2.0 / 3.0)
        assert SUBDIVISIONS["1/8t"] == pytest.approx(1.0 / 3.0)
        assert SUBDIVISIONS["1/16t"] == pytest.approx(1.0 / 6.0)
