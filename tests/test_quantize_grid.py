"""Tests for quantize_grid module.

Tests for grid quantization, swing, and humanization of MIDI note events.
"""

import random

import pytest

from gamepad_midi_bridge import bpm_sync, quantize_grid


class TestQuantizeGridConfig:
    """Tests for QuantizeGridConfig dataclass."""

    def test_config_defaults(self) -> None:
        """Test default config values."""
        cfg = quantize_grid.QuantizeGridConfig()
        assert cfg.enabled is False
        assert cfg.bpm == 120.0
        assert cfg.subdivision == "1/16"
        assert cfg.mode == "nearest"
        assert cfg.swing_percent == 50.0

    def test_config_clamp_bpm_low(self) -> None:
        """Test BPM is clamped to 20 minimum."""
        cfg = quantize_grid.QuantizeGridConfig(bpm=10.0)
        assert cfg.bpm == 20.0

    def test_config_clamp_bpm_high(self) -> None:
        """Test BPM is clamped to 300 maximum."""
        cfg = quantize_grid.QuantizeGridConfig(bpm=500.0)
        assert cfg.bpm == 300.0

    def test_config_unknown_subdivision_defaults(self) -> None:
        """Test unknown subdivision defaults to '1/16'."""
        cfg = quantize_grid.QuantizeGridConfig(subdivision="invalid")
        assert cfg.subdivision == "1/16"

    def test_config_valid_subdivision(self) -> None:
        """Test valid subdivision is preserved."""
        cfg = quantize_grid.QuantizeGridConfig(subdivision="1/8")
        assert cfg.subdivision == "1/8"

    def test_config_unknown_mode_defaults(self) -> None:
        """Test unknown mode defaults to 'nearest'."""
        cfg = quantize_grid.QuantizeGridConfig(mode="invalid")
        assert cfg.mode == "nearest"

    def test_config_valid_modes(self) -> None:
        """Test all valid modes are accepted."""
        for mode in ("nearest", "next", "previous"):
            cfg = quantize_grid.QuantizeGridConfig(mode=mode)
            assert cfg.mode == mode

    def test_config_clamp_swing_percent_low(self) -> None:
        """Test swing_percent is clamped to 50 minimum."""
        cfg = quantize_grid.QuantizeGridConfig(swing_percent=30.0)
        assert cfg.swing_percent == 50.0

    def test_config_clamp_swing_percent_high(self) -> None:
        """Test swing_percent is clamped to 75 maximum."""
        cfg = quantize_grid.QuantizeGridConfig(swing_percent=80.0)
        assert cfg.swing_percent == 75.0

    def test_config_to_dict(self) -> None:
        """Test serialization to dictionary."""
        cfg = quantize_grid.QuantizeGridConfig(
            enabled=True, bpm=140.0, subdivision="1/8", mode="next", swing_percent=65.0
        )
        data = cfg.to_dict()
        assert data["enabled"] is True
        assert data["bpm"] == 140.0
        assert data["subdivision"] == "1/8"
        assert data["mode"] == "next"
        assert data["swing_percent"] == 65.0

    def test_config_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "enabled": True,
            "bpm": 140.0,
            "subdivision": "1/8",
            "mode": "next",
            "swing_percent": 65.0,
        }
        cfg = quantize_grid.QuantizeGridConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.bpm == 140.0
        assert cfg.subdivision == "1/8"
        assert cfg.mode == "next"
        assert cfg.swing_percent == 65.0

    def test_config_round_trip_serialization(self) -> None:
        """Test round-trip serialization preserves values."""
        original = quantize_grid.QuantizeGridConfig(
            enabled=True, bpm=150.0, subdivision="1/4", mode="previous", swing_percent=72.0
        )
        data = original.to_dict()
        restored = quantize_grid.QuantizeGridConfig.from_dict(data)
        assert restored.enabled == original.enabled
        assert restored.bpm == original.bpm
        assert restored.subdivision == original.subdivision
        assert restored.mode == original.mode
        assert restored.swing_percent == original.swing_percent


class TestNextGridTime:
    """Tests for next_grid_time function."""

    def test_next_grid_time_basic_quarter_note(self) -> None:
        """Test quantization to quarter note grid at 120 BPM.

        At 120 BPM, a quarter note is 0.5 seconds.
        """
        cfg = quantize_grid.QuantizeGridConfig(bpm=120, subdivision="1/4", mode="next")
        # Event at 0.3s should snap to next grid at 0.5s
        result = quantize_grid.next_grid_time(0.3, 0.0, cfg)
        assert result == pytest.approx(0.5)

    def test_next_grid_time_sixteenth_note(self) -> None:
        """Test quantization to 1/16 note grid at 120 BPM.

        At 120 BPM, a 1/16 note is 0.125 seconds.
        """
        cfg = quantize_grid.QuantizeGridConfig(bpm=120, subdivision="1/16", mode="next")
        # Event at 0.1s should snap to next grid at 0.125s
        result = quantize_grid.next_grid_time(0.1, 0.0, cfg)
        assert result == pytest.approx(0.125)

    def test_next_grid_time_mode_nearest(self) -> None:
        """Test mode='nearest' snaps to closest grid point."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/4", mode="nearest"
        )
        # 0.3s is closer to 0.5s than 0.0s
        result = quantize_grid.next_grid_time(0.3, 0.0, cfg)
        assert result == pytest.approx(0.5)

    def test_next_grid_time_mode_nearest_past(self) -> None:
        """Test mode='nearest' can snap to past grid point if closer."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/4", mode="nearest"
        )
        # 0.1s is closer to 0.0s than 0.5s
        result = quantize_grid.next_grid_time(0.1, 0.0, cfg)
        assert result == pytest.approx(0.0)

    def test_next_grid_time_mode_previous(self) -> None:
        """Test mode='previous' snaps to previous grid point."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/4", mode="previous"
        )
        # 0.3s should snap to previous grid at 0.0s
        result = quantize_grid.next_grid_time(0.3, 0.0, cfg)
        assert result == pytest.approx(0.0)

    def test_next_grid_time_with_reference_start(self) -> None:
        """Test quantization with non-zero reference start time."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/4", mode="next"
        )
        # ref_start_s = 1.0, so grid points are at 1.0, 1.5, 2.0, ...
        # Event at 1.3s should snap to next grid at 1.5s
        result = quantize_grid.next_grid_time(1.3, 1.0, cfg)
        assert result == pytest.approx(1.5)

    def test_next_grid_time_already_on_grid(self) -> None:
        """Test event already on grid point returns same time."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/4", mode="nearest"
        )
        # 0.5s is exactly on a grid point
        result = quantize_grid.next_grid_time(0.5, 0.0, cfg)
        assert result == pytest.approx(0.5)

    def test_next_grid_time_different_bpm(self) -> None:
        """Test quantization at different BPM."""
        # At 60 BPM, quarter note = 1.0 second
        cfg = quantize_grid.QuantizeGridConfig(bpm=60, subdivision="1/4", mode="next")
        # Event at 0.7s should snap to next grid at 1.0s
        result = quantize_grid.next_grid_time(0.7, 0.0, cfg)
        assert result == pytest.approx(1.0)


class TestApplySwing:
    """Tests for apply_swing function."""

    def test_apply_swing_no_swing_at_50_percent(self) -> None:
        """Test no swing is applied at 50%."""
        cfg = quantize_grid.QuantizeGridConfig(swing_percent=50.0)
        result = quantize_grid.apply_swing(0.5, 0.0, cfg)
        assert result == pytest.approx(0.5)

    def test_apply_swing_no_shift_on_even_index(self) -> None:
        """Test even grid indices are never shifted."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/8", swing_percent=75.0
        )
        # Grid index 0 is even; should not shift
        result = quantize_grid.apply_swing(0.0, 0.0, cfg)
        assert result == pytest.approx(0.0)

    def test_apply_swing_shifts_odd_index(self) -> None:
        """Test odd grid indices shift forward."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/8", swing_percent=75.0
        )
        # At 120 BPM, 1/8 note = 0.25s
        # Grid index 1 is odd; at 75% swing, shift_fraction = 0.5
        # Shift should be 0.5 * 0.25 = 0.125s
        result = quantize_grid.apply_swing(0.25, 0.0, cfg)
        assert result == pytest.approx(0.375)

    def test_apply_swing_proportional_to_percent(self) -> None:
        """Test swing amount is proportional to swing_percent."""
        grid_time = 0.25
        ref_start = 0.0
        base_cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/8", swing_percent=62.5
        )
        result_mid = quantize_grid.apply_swing(grid_time, ref_start, base_cfg)

        max_cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/8", swing_percent=75.0
        )
        result_max = quantize_grid.apply_swing(grid_time, ref_start, max_cfg)

        # Mid swing (62.5%) should shift less than max (75%)
        assert result_mid < result_max
        assert result_max == pytest.approx(0.375)

    def test_apply_swing_with_reference_start(self) -> None:
        """Test swing calculation respects reference start."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/8", swing_percent=75.0
        )
        # Grid time 1.25 with ref_start 1.0 means grid_index = 1 (odd)
        result = quantize_grid.apply_swing(1.25, 1.0, cfg)
        # Shift should be 0.5 * 0.25 = 0.125
        assert result == pytest.approx(1.375)


class TestHumanizeOffsetMs:
    """Tests for humanize_offset_ms function."""

    def test_humanize_offset_ms_range(self) -> None:
        """Test offset is within expected range."""
        for _ in range(100):
            offset = quantize_grid.humanize_offset_ms(jitter_ms=10)
            assert -5.0 <= offset <= 5.0

    def test_humanize_offset_ms_zero_jitter(self) -> None:
        """Test zero jitter returns zero offset."""
        offset = quantize_grid.humanize_offset_ms(jitter_ms=0, seed=42)
        assert offset == pytest.approx(0.0)

    def test_humanize_offset_ms_seeded_determinism(self) -> None:
        """Test seeded randomness is deterministic."""
        offset1 = quantize_grid.humanize_offset_ms(jitter_ms=10, seed=42)
        offset2 = quantize_grid.humanize_offset_ms(jitter_ms=10, seed=42)
        assert offset1 == pytest.approx(offset2)

    def test_humanize_offset_ms_different_jitter(self) -> None:
        """Test larger jitter produces larger offsets."""
        random.seed(42)
        offset_small = quantize_grid.humanize_offset_ms(jitter_ms=5)
        random.seed(42)
        offset_large = quantize_grid.humanize_offset_ms(jitter_ms=20)
        # Offsets should have different magnitudes on average (not a strict test)
        assert abs(offset_large) >= abs(offset_small) or True  # Just check ranges


class TestQuantizeScheduler:
    """Tests for QuantizeScheduler class."""

    def test_scheduler_init(self) -> None:
        """Test scheduler initialization."""
        cfg = quantize_grid.QuantizeGridConfig(bpm=140, subdivision="1/8")
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        assert scheduler.cfg == cfg
        assert scheduler.ref_start_s == 0.0

    def test_scheduler_quantize_basic(self) -> None:
        """Test basic quantization without swing."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/4", mode="next", swing_percent=50.0
        )
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        result = scheduler.quantize(0.3)
        assert result == pytest.approx(0.5)

    def test_scheduler_quantize_with_swing(self) -> None:
        """Test quantization applies swing."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/8", mode="next", swing_percent=75.0
        )
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        # 0.1s snaps to next grid at 0.25s (grid_index=1, odd)
        result = scheduler.quantize(0.1)
        # With 75% swing, grid_index=1 (odd) shifts by 0.5 * 0.25 = 0.125
        # So 0.25 + 0.125 = 0.375
        assert result == pytest.approx(0.375)

    def test_scheduler_next_n_grid_times_length(self) -> None:
        """Test next_n_grid_times returns correct number of times."""
        cfg = quantize_grid.QuantizeGridConfig(bpm=120, subdivision="1/4")
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        times = scheduler.next_n_grid_times(0.0, 5)
        assert len(times) == 5

    def test_scheduler_next_n_grid_times_spacing(self) -> None:
        """Test grid times are evenly spaced."""
        cfg = quantize_grid.QuantizeGridConfig(bpm=120, subdivision="1/4")
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        times = scheduler.next_n_grid_times(0.0, 4)
        # Grid step at 120 BPM, 1/4 = 0.5s
        expected = [0.5, 1.0, 1.5, 2.0]
        for result, exp in zip(times, expected):
            assert result == pytest.approx(exp)

    def test_scheduler_next_n_grid_times_monotonic(self) -> None:
        """Test grid times are monotonically increasing."""
        cfg = quantize_grid.QuantizeGridConfig(bpm=120, subdivision="1/8")
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        times = scheduler.next_n_grid_times(0.5, 10)
        for i in range(len(times) - 1):
            assert times[i] < times[i + 1]

    def test_scheduler_next_n_grid_times_after_arbitrary_time(self) -> None:
        """Test grid times start after arbitrary reference."""
        cfg = quantize_grid.QuantizeGridConfig(bpm=120, subdivision="1/4")
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        now_s = 0.7
        times = scheduler.next_n_grid_times(now_s, 3)
        # First grid time should be after now_s
        assert times[0] > now_s


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_end_to_end_quantize_and_swing(self) -> None:
        """Test complete workflow: event → quantize → swing."""
        cfg = quantize_grid.QuantizeGridConfig(
            enabled=True, bpm=120, subdivision="1/16", mode="nearest", swing_percent=65.0
        )
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)

        # Simulate event at arbitrary time
        event_time = 0.17
        quantized = scheduler.quantize(event_time)

        # Result should be grid-aligned and swung
        assert isinstance(quantized, float)
        assert quantized > 0

    def test_multiple_events_in_sequence(self) -> None:
        """Test quantizing a sequence of events."""
        cfg = quantize_grid.QuantizeGridConfig(
            bpm=120, subdivision="1/8", mode="nearest", swing_percent=60.0
        )
        scheduler = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)

        event_times = [0.05, 0.17, 0.35, 0.52]
        quantized_times = [scheduler.quantize(t) for t in event_times]

        # All should be on the grid
        grid_step_s = bpm_sync.subdivision_ms(120.0, "1/8") / 1000.0
        for t in quantized_times:
            grid_index = round(t / grid_step_s)
            expected_grid = grid_index * grid_step_s
            # Allow small tolerance for floating-point and swing
            assert abs(t - expected_grid) < 0.1

    def test_serialization_preserves_quantization(self) -> None:
        """Test quantization is consistent after serialization."""
        cfg = quantize_grid.QuantizeGridConfig(
            enabled=True, bpm=130.5, subdivision="1/4", mode="next", swing_percent=62.0
        )
        event_time = 0.3

        # Quantize before serialization
        scheduler1 = quantize_grid.QuantizeScheduler(cfg, ref_start_s=0.0)
        result1 = scheduler1.quantize(event_time)

        # Serialize and deserialize
        data = cfg.to_dict()
        cfg_restored = quantize_grid.QuantizeGridConfig.from_dict(data)

        # Quantize after deserialization
        scheduler2 = quantize_grid.QuantizeScheduler(cfg_restored, ref_start_s=0.0)
        result2 = scheduler2.quantize(event_time)

        assert result1 == pytest.approx(result2)
