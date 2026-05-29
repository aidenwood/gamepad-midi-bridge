"""Tests for LFO BPM sync module."""

import pytest

from gamepad_midi_bridge.lfo_bpm_sync import (
    LfoBpmSyncConfig,
    apply_to_lfo_config,
    cycles_per_bar,
    rate_hz_to_nearest_subdivision,
    subdivision_to_rate_hz,
)


class TestSubdivisionToRateHz:
    """Test subdivision_to_rate_hz function."""

    def test_quarter_note_120_bpm(self) -> None:
        """At 120 BPM, 1/4 note = 500ms → rate_hz = 2.0."""
        assert subdivision_to_rate_hz("1/4", 120) == 2.0

    def test_eighth_note_120_bpm(self) -> None:
        """At 120 BPM, 1/8 note = 250ms → rate_hz = 4.0."""
        assert subdivision_to_rate_hz("1/8", 120) == 4.0

    def test_sixteenth_note_120_bpm(self) -> None:
        """At 120 BPM, 1/16 note = 125ms → rate_hz = 8.0."""
        assert subdivision_to_rate_hz("1/16", 120) == 8.0

    def test_quarter_note_60_bpm(self) -> None:
        """At 60 BPM, 1/4 note = 1000ms → rate_hz = 1.0."""
        assert subdivision_to_rate_hz("1/4", 60) == 1.0

    def test_unknown_subdivision_raises(self) -> None:
        """Unknown subdivision raises KeyError."""
        with pytest.raises(KeyError, match="Unknown subdivision"):
            subdivision_to_rate_hz("1/99", 120)

    def test_zero_bpm_raises(self) -> None:
        """BPM <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="BPM must be positive"):
            subdivision_to_rate_hz("1/4", 0)

    def test_negative_bpm_raises(self) -> None:
        """Negative BPM raises ValueError."""
        with pytest.raises(ValueError, match="BPM must be positive"):
            subdivision_to_rate_hz("1/4", -60)

    def test_whole_note_120_bpm(self) -> None:
        """At 120 BPM, 1/1 (whole) = 2000ms → rate_hz = 0.5."""
        assert subdivision_to_rate_hz("1/1", 120) == 0.5

    def test_dotted_quarter_120_bpm(self) -> None:
        """At 120 BPM, 1/4d (dotted quarter) = 750ms → rate_hz ≈ 1.333."""
        result = subdivision_to_rate_hz("1/4d", 120)
        assert abs(result - (1000.0 / 750.0)) < 1e-9

    def test_triplet_120_bpm(self) -> None:
        """At 120 BPM, 1/4t (quarter triplet) ≈ 333.33ms → rate_hz = 3.0."""
        result = subdivision_to_rate_hz("1/4t", 120)
        expected = 1000.0 / (500.0 * 2.0 / 3.0)
        assert abs(result - expected) < 1e-9


class TestRateHzToNearestSubdivision:
    """Test rate_hz_to_nearest_subdivision function."""

    def test_rate_8_at_120_bpm_is_sixteenth(self) -> None:
        """8.0 Hz at 120 BPM is closest to 1/16."""
        assert rate_hz_to_nearest_subdivision(8.0, 120) == "1/16"

    def test_rate_2_at_120_bpm_is_quarter(self) -> None:
        """2.0 Hz at 120 BPM is closest to 1/4."""
        assert rate_hz_to_nearest_subdivision(2.0, 120) == "1/4"

    def test_rate_4_at_120_bpm_is_eighth(self) -> None:
        """4.0 Hz at 120 BPM is closest to 1/8."""
        assert rate_hz_to_nearest_subdivision(4.0, 120) == "1/8"

    def test_zero_bpm_raises(self) -> None:
        """BPM <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="BPM must be positive"):
            rate_hz_to_nearest_subdivision(2.0, 0)

    def test_negative_bpm_raises(self) -> None:
        """Negative BPM raises ValueError."""
        with pytest.raises(ValueError, match="BPM must be positive"):
            rate_hz_to_nearest_subdivision(2.0, -120)

    def test_roundtrip_subdivision_to_nearest(self) -> None:
        """Converting subdivision to rate_hz and back returns same subdivision."""
        original_sub = "1/16"
        rate_hz = subdivision_to_rate_hz(original_sub, 120)
        recovered_sub = rate_hz_to_nearest_subdivision(rate_hz, 120)
        assert recovered_sub == original_sub

    def test_rate_1_at_120_bpm_is_quarter(self) -> None:
        """1.0 Hz at 120 BPM is close to 1/4 (but really 1/2 at 60 BPM)."""
        # At 120 BPM: 1/4 = 2.0 Hz, so 1.0 Hz is halfway between 1/4 and 1/2
        # 1/2 at 120 BPM = 1000.0 / 1000.0 = 1.0 Hz
        result = rate_hz_to_nearest_subdivision(1.0, 120)
        assert result == "1/2"


class TestCyclesPerBar:
    """Test cycles_per_bar function."""

    def test_quarter_at_4_4(self) -> None:
        """In 4/4, 4 quarter notes per bar → 4 cycles."""
        assert cycles_per_bar("1/4", 4) == 4.0

    def test_eighth_at_4_4(self) -> None:
        """In 4/4, 8 eighth notes per bar → 8 cycles."""
        assert cycles_per_bar("1/8", 4) == 8.0

    def test_sixteenth_at_4_4(self) -> None:
        """In 4/4, 16 sixteenth notes per bar → 16 cycles."""
        assert cycles_per_bar("1/16", 4) == 16.0

    def test_half_at_4_4(self) -> None:
        """In 4/4, 2 half notes per bar → 2 cycles."""
        assert cycles_per_bar("1/2", 4) == 2.0

    def test_whole_at_4_4(self) -> None:
        """In 4/4, 1 whole note per bar → 1 cycle."""
        assert cycles_per_bar("1/1", 4) == 1.0

    def test_quarter_at_3_4(self) -> None:
        """In 3/4, 3 quarter notes per bar → 3 cycles."""
        assert cycles_per_bar("1/4", 3) == 3.0

    def test_eighth_at_3_4(self) -> None:
        """In 3/4, 6 eighth notes per bar → 6 cycles."""
        assert cycles_per_bar("1/8", 3) == 6.0

    def test_dotted_quarter_at_4_4(self) -> None:
        """In 4/4, dotted quarters: 4 / 1.5 ≈ 2.667 cycles."""
        result = cycles_per_bar("1/4d", 4)
        assert abs(result - (4.0 / 1.5)) < 1e-9

    def test_triplet_at_4_4(self) -> None:
        """In 4/4, quarter triplets: 4 / (2/3) = 6 cycles."""
        result = cycles_per_bar("1/4t", 4)
        expected = 4.0 / (2.0 / 3.0)
        assert abs(result - expected) < 1e-9

    def test_unknown_subdivision_raises(self) -> None:
        """Unknown subdivision raises KeyError."""
        with pytest.raises(KeyError, match="Unknown subdivision"):
            cycles_per_bar("1/99", 4)


class TestLfoBpmSyncConfig:
    """Test LfoBpmSyncConfig dataclass."""

    def test_defaults(self) -> None:
        """Default config is disabled with 120 BPM and 1/4 subdivision."""
        cfg = LfoBpmSyncConfig()
        assert cfg.enabled is False
        assert cfg.bpm == 120.0
        assert cfg.subdivision == "1/4"
        assert cfg.auto_update_rate is True

    def test_bpm_clamping_low(self) -> None:
        """BPM clamped to min 20."""
        cfg = LfoBpmSyncConfig(bpm=10)
        assert cfg.bpm == 20.0

    def test_bpm_clamping_high(self) -> None:
        """BPM clamped to max 300."""
        cfg = LfoBpmSyncConfig(bpm=500)
        assert cfg.bpm == 300.0

    def test_invalid_subdivision_falls_back(self) -> None:
        """Unknown subdivision falls back to 1/4."""
        cfg = LfoBpmSyncConfig(subdivision="1/99")
        assert cfg.subdivision == "1/4"

    def test_valid_subdivision_preserved(self) -> None:
        """Valid subdivision is preserved."""
        cfg = LfoBpmSyncConfig(subdivision="1/16")
        assert cfg.subdivision == "1/16"

    def test_to_dict(self) -> None:
        """Config serializes to dict."""
        cfg = LfoBpmSyncConfig(enabled=True, bpm=140, subdivision="1/8")
        result = cfg.to_dict()
        assert result["enabled"] is True
        assert result["bpm"] == 140.0
        assert result["subdivision"] == "1/8"
        assert result["auto_update_rate"] is True

    def test_from_dict_minimal(self) -> None:
        """from_dict with minimal data uses defaults."""
        cfg = LfoBpmSyncConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.bpm == 120.0
        assert cfg.subdivision == "1/4"
        assert cfg.auto_update_rate is True

    def test_from_dict_full(self) -> None:
        """from_dict with full data restores all fields."""
        data = {
            "enabled": True,
            "bpm": 140,
            "subdivision": "1/16",
            "auto_update_rate": False,
        }
        cfg = LfoBpmSyncConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.bpm == 140.0
        assert cfg.subdivision == "1/16"
        assert cfg.auto_update_rate is False

    def test_roundtrip_serialization(self) -> None:
        """Config round-trips through dict serialization."""
        original = LfoBpmSyncConfig(enabled=True, bpm=130, subdivision="1/8d")
        data = original.to_dict()
        restored = LfoBpmSyncConfig.from_dict(data)
        assert restored.enabled == original.enabled
        assert restored.bpm == original.bpm
        assert restored.subdivision == original.subdivision
        assert restored.auto_update_rate == original.auto_update_rate


class TestApplyToLfoConfig:
    """Test apply_to_lfo_config function."""

    def test_updates_rate_when_enabled_and_auto_update(self) -> None:
        """When enabled and auto_update_rate, rate_hz is updated."""
        lfo_cfg = {"enabled": True, "shape": "sine", "rate_hz": 1.0, "depth": 1.0}
        sync_cfg = LfoBpmSyncConfig(enabled=True, bpm=120, subdivision="1/4")
        result = apply_to_lfo_config(lfo_cfg, sync_cfg)

        assert result["rate_hz"] == 2.0
        assert result["shape"] == "sine"
        assert result["depth"] == 1.0

    def test_preserves_other_fields(self) -> None:
        """apply_to_lfo_config preserves other LFO fields."""
        lfo_cfg = {
            "enabled": True,
            "shape": "triangle",
            "rate_hz": 1.0,
            "depth": 0.5,
            "phase_offset": 0.25,
            "duty": 0.6,
            "bipolar": True,
        }
        sync_cfg = LfoBpmSyncConfig(enabled=True, bpm=120, subdivision="1/8")
        result = apply_to_lfo_config(lfo_cfg, sync_cfg)

        assert result["shape"] == "triangle"
        assert result["depth"] == 0.5
        assert result["phase_offset"] == 0.25
        assert result["duty"] == 0.6
        assert result["bipolar"] is True
        assert result["rate_hz"] == 4.0

    def test_no_update_when_sync_disabled(self) -> None:
        """When sync disabled, rate_hz unchanged."""
        lfo_cfg = {"enabled": True, "shape": "sine", "rate_hz": 1.0}
        sync_cfg = LfoBpmSyncConfig(enabled=False)
        result = apply_to_lfo_config(lfo_cfg, sync_cfg)

        assert result["rate_hz"] == 1.0

    def test_no_update_when_auto_update_false(self) -> None:
        """When auto_update_rate False, rate_hz unchanged."""
        lfo_cfg = {"enabled": True, "shape": "sine", "rate_hz": 1.0}
        sync_cfg = LfoBpmSyncConfig(
            enabled=True, bpm=120, subdivision="1/4", auto_update_rate=False
        )
        result = apply_to_lfo_config(lfo_cfg, sync_cfg)

        assert result["rate_hz"] == 1.0

    def test_does_not_mutate_input(self) -> None:
        """apply_to_lfo_config does not mutate input dict."""
        lfo_cfg = {"enabled": True, "shape": "sine", "rate_hz": 1.0}
        original_rate = lfo_cfg["rate_hz"]

        sync_cfg = LfoBpmSyncConfig(enabled=True, bpm=120, subdivision="1/4")
        result = apply_to_lfo_config(lfo_cfg, sync_cfg)

        # Input unchanged
        assert lfo_cfg["rate_hz"] == original_rate
        # Result changed
        assert result["rate_hz"] == 2.0
        # Different objects
        assert result is not lfo_cfg

    def test_apply_sixteenth_at_60_bpm(self) -> None:
        """Sixteenth at 60 BPM: 1/16 = 62.5ms → rate_hz = 16.0."""
        lfo_cfg = {"rate_hz": 1.0}
        sync_cfg = LfoBpmSyncConfig(enabled=True, bpm=60, subdivision="1/16")
        result = apply_to_lfo_config(lfo_cfg, sync_cfg)

        expected_rate = subdivision_to_rate_hz("1/16", 60)
        assert result["rate_hz"] == expected_rate
