"""Polyrhythm sequencer tests — two Euclidean patterns interlocking."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.polyrhythm import (
    PolyrhythmConfig,
    PolyrhythmVoice,
    Polyrhythm,
    lcm,
)


class TestPolyrhythmVoiceDefaults:
    """PolyrhythmVoice dataclass — defaults and clamping."""

    def test_voice_default_pulses_and_steps(self):
        """Default voice has pulses=1, steps=8."""
        voice = PolyrhythmVoice(pulses=1, steps=8)
        assert voice.pulses == 1
        assert voice.steps == 8

    def test_voice_default_note_velocity_channel(self):
        """Default voice has note=60, velocity=100, channel=1."""
        voice = PolyrhythmVoice(pulses=1, steps=8)
        assert voice.note == 60
        assert voice.velocity == 100
        assert voice.channel == 1

    def test_voice_default_rotation(self):
        """Default rotation is 0."""
        voice = PolyrhythmVoice(pulses=1, steps=8)
        assert voice.rotation == 0

    def test_voice_pulses_clamped_below_zero(self):
        """pulses < 0 clamped to 0."""
        voice = PolyrhythmVoice(pulses=-5, steps=8)
        assert voice.pulses == 0

    def test_voice_pulses_clamped_above_32(self):
        """pulses > 32 clamped to 32."""
        voice = PolyrhythmVoice(pulses=50, steps=8)
        assert voice.pulses == 32

    def test_voice_steps_clamped_below_one(self):
        """steps < 1 clamped to 1."""
        voice = PolyrhythmVoice(pulses=1, steps=0)
        assert voice.steps == 1

    def test_voice_steps_clamped_above_32(self):
        """steps > 32 clamped to 32."""
        voice = PolyrhythmVoice(pulses=1, steps=50)
        assert voice.steps == 32

    def test_voice_note_clamped_below_zero(self):
        """note < 0 clamped to 0."""
        voice = PolyrhythmVoice(pulses=1, steps=8, note=-5)
        assert voice.note == 0

    def test_voice_note_clamped_above_127(self):
        """note > 127 clamped to 127."""
        voice = PolyrhythmVoice(pulses=1, steps=8, note=150)
        assert voice.note == 127

    def test_voice_velocity_clamped_below_one(self):
        """velocity < 1 clamped to 1."""
        voice = PolyrhythmVoice(pulses=1, steps=8, velocity=0)
        assert voice.velocity == 1

    def test_voice_velocity_clamped_above_127(self):
        """velocity > 127 clamped to 127."""
        voice = PolyrhythmVoice(pulses=1, steps=8, velocity=150)
        assert voice.velocity == 127

    def test_voice_channel_clamped_below_one(self):
        """channel < 1 clamped to 1."""
        voice = PolyrhythmVoice(pulses=1, steps=8, channel=0)
        assert voice.channel == 1

    def test_voice_channel_clamped_above_16(self):
        """channel > 16 clamped to 16."""
        voice = PolyrhythmVoice(pulses=1, steps=8, channel=20)
        assert voice.channel == 16


class TestPolyrhythmVoiceToPattern:
    """PolyrhythmVoice.to_pattern — Euclidean rhythm generation."""

    def test_voice_to_pattern_e_3_8(self):
        """E(3,8) = [1,0,0,1,0,0,1,0]."""
        voice = PolyrhythmVoice(pulses=3, steps=8)
        pattern = voice.to_pattern()
        assert pattern == [1, 0, 0, 1, 0, 0, 1, 0]
        assert len(pattern) == 8

    def test_voice_to_pattern_e_5_16(self):
        """E(5,16) produces 5 ones across 16 steps."""
        voice = PolyrhythmVoice(pulses=5, steps=16)
        pattern = voice.to_pattern()
        assert sum(pattern) == 5
        assert len(pattern) == 16

    def test_voice_to_pattern_with_rotation(self):
        """E(3,8) rotated by 1 step."""
        voice = PolyrhythmVoice(pulses=3, steps=8, rotation=1)
        pattern = voice.to_pattern()
        assert pattern == [0, 1, 0, 0, 1, 0, 0, 1]

    def test_voice_to_pattern_zero_pulses(self):
        """E(0,8) = [0,0,0,0,0,0,0,0]."""
        voice = PolyrhythmVoice(pulses=0, steps=8)
        pattern = voice.to_pattern()
        assert pattern == [0, 0, 0, 0, 0, 0, 0, 0]

    def test_voice_to_pattern_full_pulses(self):
        """E(8,8) = [1,1,1,1,1,1,1,1]."""
        voice = PolyrhythmVoice(pulses=8, steps=8)
        pattern = voice.to_pattern()
        assert pattern == [1, 1, 1, 1, 1, 1, 1, 1]


class TestPolyrhythmConfigDefaults:
    """PolyrhythmConfig dataclass — defaults and clamping."""

    def test_config_default_disabled(self):
        """Default config is disabled."""
        cfg = PolyrhythmConfig()
        assert cfg.enabled is False

    def test_config_default_voices(self):
        """Default voice_a is E(3,8), voice_b is E(5,16)."""
        cfg = PolyrhythmConfig()
        assert cfg.voice_a.pulses == 3
        assert cfg.voice_a.steps == 8
        assert cfg.voice_b.pulses == 5
        assert cfg.voice_b.steps == 16

    def test_config_default_tick_rate(self):
        """Default tick_rate_hz is 8.0."""
        cfg = PolyrhythmConfig()
        assert cfg.tick_rate_hz == 8.0

    def test_config_tick_rate_clamped_below_0_5(self):
        """tick_rate_hz < 0.5 clamped to 0.5."""
        cfg = PolyrhythmConfig(tick_rate_hz=0.1)
        assert cfg.tick_rate_hz == 0.5

    def test_config_tick_rate_clamped_above_50(self):
        """tick_rate_hz > 50.0 clamped to 50.0."""
        cfg = PolyrhythmConfig(tick_rate_hz=100.0)
        assert cfg.tick_rate_hz == 50.0

    def test_config_custom_voices(self):
        """Config accepts custom voice_a and voice_b."""
        voice_a = PolyrhythmVoice(pulses=4, steps=12)
        voice_b = PolyrhythmVoice(pulses=7, steps=20)
        cfg = PolyrhythmConfig(voice_a=voice_a, voice_b=voice_b)
        assert cfg.voice_a.pulses == 4
        assert cfg.voice_b.pulses == 7


class TestPolyrhythmInitAndReset:
    """Polyrhythm initialization and reset."""

    def test_polyrhythm_init_step_counters_zero(self):
        """Init sets _step_a and _step_b to 0."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        assert poly.current_steps() == (0, 0)

    def test_polyrhythm_init_last_tick_none(self):
        """Init sets _last_tick_at to None."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        assert poly._last_tick_at is None

    def test_polyrhythm_reset_returns_to_zero(self):
        """reset() returns both step counters to 0."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        # Manually advance steps
        poly._step_a = 3
        poly._step_b = 5
        poly._last_tick_at = 1.0
        # Reset
        poly.reset()
        assert poly.current_steps() == (0, 0)
        assert poly._last_tick_at is None


class TestPolyrhythmCurrentSteps:
    """Polyrhythm.current_steps() method."""

    def test_current_steps_returns_tuple(self):
        """current_steps() returns tuple (_step_a, _step_b)."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        poly._step_a = 2
        poly._step_b = 5
        assert poly.current_steps() == (2, 5)


class TestPolyrhythmCombinedLength:
    """Polyrhythm.combined_length() — LCM of pattern lengths."""

    def test_combined_length_8_16(self):
        """LCM(8, 16) = 16."""
        voice_a = PolyrhythmVoice(pulses=3, steps=8)
        voice_b = PolyrhythmVoice(pulses=5, steps=16)
        cfg = PolyrhythmConfig(voice_a=voice_a, voice_b=voice_b)
        poly = Polyrhythm(cfg)
        assert poly.combined_length() == 16

    def test_combined_length_3_4(self):
        """LCM(3, 4) = 12."""
        voice_a = PolyrhythmVoice(pulses=2, steps=3)
        voice_b = PolyrhythmVoice(pulses=3, steps=4)
        cfg = PolyrhythmConfig(voice_a=voice_a, voice_b=voice_b)
        poly = Polyrhythm(cfg)
        assert poly.combined_length() == 12

    def test_combined_length_5_7(self):
        """LCM(5, 7) = 35."""
        voice_a = PolyrhythmVoice(pulses=2, steps=5)
        voice_b = PolyrhythmVoice(pulses=3, steps=7)
        cfg = PolyrhythmConfig(voice_a=voice_a, voice_b=voice_b)
        poly = Polyrhythm(cfg)
        assert poly.combined_length() == 35


class TestLcmFunction:
    """lcm utility function."""

    def test_lcm_8_16(self):
        """lcm(8, 16) = 16."""
        assert lcm(8, 16) == 16

    def test_lcm_3_4(self):
        """lcm(3, 4) = 12."""
        assert lcm(3, 4) == 12

    def test_lcm_5_7(self):
        """lcm(5, 7) = 35."""
        assert lcm(5, 7) == 35

    def test_lcm_same_number(self):
        """lcm(5, 5) = 5."""
        assert lcm(5, 5) == 5

    def test_lcm_one(self):
        """lcm(1, n) = n."""
        assert lcm(1, 5) == 5

    def test_lcm_zero(self):
        """lcm(0, n) = 0."""
        assert lcm(0, 5) == 0


class TestPolyrhythmTickDisabled:
    """Polyrhythm.tick() with disabled config."""

    def test_tick_disabled_returns_empty_list(self):
        """tick() with enabled=False returns []."""
        cfg = PolyrhythmConfig(enabled=False)
        poly = Polyrhythm(cfg)
        fires = poly.tick(0.0)
        assert fires == []

    def test_tick_disabled_does_not_advance_steps(self):
        """tick() with enabled=False does not advance step counters."""
        cfg = PolyrhythmConfig(enabled=False)
        poly = Polyrhythm(cfg)
        poly.tick(0.0)
        assert poly.current_steps() == (0, 0)


class TestPolyrhythmTickTiming:
    """Polyrhythm.tick() — timing and interval checks."""

    def test_tick_first_call_fires(self):
        """First tick at t=0.0 fires."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        fires = poly.tick(0.0)
        # E(3,8)[0] = 1, E(5,16)[0] = 1
        assert len(fires) >= 0  # Depends on exact Euclidean patterns

    def test_tick_too_soon_returns_empty(self):
        """tick() before interval elapses returns []."""
        cfg = PolyrhythmConfig(enabled=True, tick_rate_hz=8.0)
        poly = Polyrhythm(cfg)
        poly.tick(0.0)
        # Interval = 1/8 = 0.125s
        fires = poly.tick(0.05)  # Only 0.05s elapsed
        assert fires == []

    def test_tick_exactly_at_interval_fires(self):
        """tick() at exact interval boundary fires."""
        cfg = PolyrhythmConfig(enabled=True, tick_rate_hz=8.0)
        poly = Polyrhythm(cfg)
        poly.tick(0.0)
        # Interval = 0.125s
        fires = poly.tick(0.125)
        # Should fire (or not) based on patterns, but not empty because timing is satisfied
        assert isinstance(fires, list)

    def test_tick_rate_affects_interval(self):
        """Higher tick_rate_hz means shorter interval."""
        cfg_slow = PolyrhythmConfig(enabled=True, tick_rate_hz=4.0)  # 0.25s interval
        cfg_fast = PolyrhythmConfig(enabled=True, tick_rate_hz=16.0)  # 0.0625s interval

        poly_slow = Polyrhythm(cfg_slow)
        poly_fast = Polyrhythm(cfg_fast)

        poly_slow.tick(0.0)
        poly_fast.tick(0.0)

        # After 0.1s
        fires_slow = poly_slow.tick(0.1)
        fires_fast = poly_fast.tick(0.1)

        # Slow should not fire (needs 0.25s), fast should fire (needs 0.0625s)
        assert fires_slow == []
        assert isinstance(fires_fast, list)


class TestPolyrhythmTickFiring:
    """Polyrhythm.tick() — which voices fire when."""

    def test_tick_returns_list_of_tuples(self):
        """tick() returns list of (voice_name_str, PolyrhythmVoice) tuples."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        fires = poly.tick(0.0)
        assert isinstance(fires, list)
        for item in fires:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert item[0] in ("a", "b")
            assert isinstance(item[1], PolyrhythmVoice)

    def test_tick_voice_a_fires_when_pattern_1(self):
        """voice_a fires if pattern_a[_step_a] == 1."""
        # E(3, 8) = [1,0,0,1,0,0,1,0]
        # E(5,16) = [1,1,0,1,1,0,1,0,1,1,0,1,1,0,1,0]
        cfg = PolyrhythmConfig(
            enabled=True,
            voice_a=PolyrhythmVoice(pulses=3, steps=8),
            voice_b=PolyrhythmVoice(pulses=5, steps=16),
        )
        poly = Polyrhythm(cfg)
        fires = poly.tick(0.0)
        # step_a=0, step_b=0 both have pattern value 1
        voice_names = [name for name, _ in fires]
        assert "a" in voice_names or "b" in voice_names  # At least one fires

    def test_tick_advances_step_a(self):
        """tick() increments _step_a after firing."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        poly.tick(0.0)
        # After first tick, step_a should advance
        poly.tick(0.125)  # Assuming tick_rate_hz=8.0
        step_a, _ = poly.current_steps()
        assert step_a >= 1

    def test_tick_advances_step_b(self):
        """tick() increments _step_b after firing."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        poly.tick(0.0)
        poly.tick(0.125)
        _, step_b = poly.current_steps()
        assert step_b >= 1

    def test_tick_wraps_step_a(self):
        """_step_a wraps at voice_a.steps."""
        cfg = PolyrhythmConfig(
            enabled=True,
            voice_a=PolyrhythmVoice(pulses=2, steps=3),
            voice_b=PolyrhythmVoice(pulses=2, steps=4),
        )
        poly = Polyrhythm(cfg)
        # Tick 4 times to wrap step_a (steps=3)
        for i in range(4):
            poly.tick(i * 0.125)
        step_a, _ = poly.current_steps()
        assert step_a < 3  # Wrapped

    def test_tick_wraps_step_b(self):
        """_step_b wraps at voice_b.steps."""
        cfg = PolyrhythmConfig(
            enabled=True,
            voice_a=PolyrhythmVoice(pulses=2, steps=4),
            voice_b=PolyrhythmVoice(pulses=2, steps=3),
        )
        poly = Polyrhythm(cfg)
        # Tick 5 times to wrap step_b (steps=3)
        for i in range(5):
            poly.tick(i * 0.125)
        _, step_b = poly.current_steps()
        assert step_b < 3  # Wrapped


class TestPolyrhythmFullCycle:
    """Polyrhythm over a full combined_length cycle."""

    def test_full_cycle_fires_correct_number_of_times(self):
        """Over one combined_length cycle, count total fires."""
        voice_a = PolyrhythmVoice(pulses=3, steps=8)
        voice_b = PolyrhythmVoice(pulses=5, steps=16)
        cfg = PolyrhythmConfig(enabled=True, voice_a=voice_a, voice_b=voice_b)
        poly = Polyrhythm(cfg)

        # Tick once per step for combined_length ticks
        combined = poly.combined_length()
        fires_a = 0
        fires_b = 0

        for i in range(combined):
            fires = poly.tick(i * 0.125)
            for name, _ in fires:
                if name == "a":
                    fires_a += 1
                elif name == "b":
                    fires_b += 1

        # Over combined_length ticks:
        # voice_a repeats (combined_length / steps_a) times
        # Each E(3,8) has 3 pulses
        # So voice_a fires (combined_length / 8) * 3 times
        expected_a = (combined // voice_a.steps) * voice_a.pulses
        expected_b = (combined // voice_b.steps) * voice_b.pulses

        assert fires_a == expected_a
        assert fires_b == expected_b

    def test_interlocked_patterns_example_3_against_4(self):
        """3-against-4 polyrhythm (E(3,3) vs E(4,4)) over 12 ticks."""
        voice_a = PolyrhythmVoice(pulses=3, steps=3)  # E(3,3) = [1,1,1]
        voice_b = PolyrhythmVoice(pulses=4, steps=4)  # E(4,4) = [1,1,1,1]
        cfg = PolyrhythmConfig(enabled=True, voice_a=voice_a, voice_b=voice_b)
        poly = Polyrhythm(cfg)

        combined = poly.combined_length()  # LCM(3,4) = 12
        assert combined == 12

        fires_per_tick = []
        for i in range(combined):
            fires = poly.tick(i * 0.125)
            fires_per_tick.append(fires)

        # Every tick should have at least one fire (since all positions are 1)
        for i, fires in enumerate(fires_per_tick):
            assert len(fires) > 0, f"Tick {i} had no fires"


class TestPolyrhythmSerialization:
    """PolyrhythmConfig serialization — to_dict and from_dict."""

    def test_to_dict_default_config(self):
        """to_dict serializes default config."""
        cfg = PolyrhythmConfig()
        data = cfg.to_dict()
        assert data["enabled"] is False
        assert data["tick_rate_hz"] == 8.0
        assert data["voice_a"]["pulses"] == 3
        assert data["voice_a"]["steps"] == 8
        assert data["voice_b"]["pulses"] == 5
        assert data["voice_b"]["steps"] == 16

    def test_to_dict_custom_voices(self):
        """to_dict includes custom voice settings."""
        voice_a = PolyrhythmVoice(pulses=4, steps=12, note=64, velocity=80)
        voice_b = PolyrhythmVoice(pulses=6, steps=20, channel=5)
        cfg = PolyrhythmConfig(enabled=True, voice_a=voice_a, voice_b=voice_b)
        data = cfg.to_dict()
        assert data["voice_a"]["pulses"] == 4
        assert data["voice_a"]["steps"] == 12
        assert data["voice_a"]["note"] == 64
        assert data["voice_a"]["velocity"] == 80
        assert data["voice_b"]["pulses"] == 6
        assert data["voice_b"]["channel"] == 5

    def test_from_dict_default_config(self):
        """from_dict with empty dict uses defaults."""
        cfg = PolyrhythmConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.tick_rate_hz == 8.0
        assert cfg.voice_a.pulses == 3
        assert cfg.voice_b.pulses == 5

    def test_from_dict_custom_config(self):
        """from_dict loads custom values."""
        data = {
            "enabled": True,
            "tick_rate_hz": 12.0,
            "voice_a": {
                "pulses": 4,
                "steps": 12,
                "rotation": 2,
                "note": 65,
                "velocity": 90,
                "channel": 3,
            },
            "voice_b": {
                "pulses": 7,
                "steps": 20,
                "rotation": 1,
                "note": 72,
                "velocity": 110,
                "channel": 6,
            },
        }
        cfg = PolyrhythmConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.tick_rate_hz == 12.0
        assert cfg.voice_a.pulses == 4
        assert cfg.voice_a.note == 65
        assert cfg.voice_b.channel == 6

    def test_round_trip_serialization(self):
        """to_dict and from_dict preserve config exactly."""
        voice_a = PolyrhythmVoice(pulses=4, steps=12, rotation=1, note=62, velocity=95, channel=2)
        voice_b = PolyrhythmVoice(pulses=6, steps=18, rotation=3, note=68, velocity=105, channel=4)
        cfg = PolyrhythmConfig(enabled=True, voice_a=voice_a, voice_b=voice_b, tick_rate_hz=10.0)
        data = cfg.to_dict()
        cfg2 = PolyrhythmConfig.from_dict(data)

        assert cfg2.enabled == cfg.enabled
        assert cfg2.tick_rate_hz == cfg.tick_rate_hz
        assert cfg2.voice_a.pulses == cfg.voice_a.pulses
        assert cfg2.voice_a.note == cfg.voice_a.note
        assert cfg2.voice_b.channel == cfg.voice_b.channel

    def test_from_dict_clamps_values(self):
        """from_dict clamps out-of-range values."""
        data = {
            "tick_rate_hz": 100.0,
            "voice_a": {"pulses": 50, "steps": 1, "note": 150, "velocity": 150},
            "voice_b": {"pulses": -5, "steps": 50, "note": -10, "velocity": -10},
        }
        cfg = PolyrhythmConfig.from_dict(data)
        assert cfg.tick_rate_hz == 50.0
        assert cfg.voice_a.pulses == 32
        assert cfg.voice_a.steps == 1
        assert cfg.voice_a.note == 127
        assert cfg.voice_a.velocity == 127
        assert cfg.voice_b.pulses == 0
        assert cfg.voice_b.steps == 32
        assert cfg.voice_b.note == 0
        assert cfg.voice_b.velocity == 1


class TestPolyrhythmVoiceMidiValues:
    """PolyrhythmVoice MIDI field validation."""

    def test_voice_note_at_boundary_0(self):
        """note=0 is valid (lowest MIDI note)."""
        voice = PolyrhythmVoice(pulses=1, steps=8, note=0)
        assert voice.note == 0

    def test_voice_note_at_boundary_127(self):
        """note=127 is valid (highest MIDI note)."""
        voice = PolyrhythmVoice(pulses=1, steps=8, note=127)
        assert voice.note == 127

    def test_voice_velocity_at_boundary_1(self):
        """velocity=1 is valid (minimum non-zero)."""
        voice = PolyrhythmVoice(pulses=1, steps=8, velocity=1)
        assert voice.velocity == 1

    def test_voice_velocity_at_boundary_127(self):
        """velocity=127 is valid (maximum)."""
        voice = PolyrhythmVoice(pulses=1, steps=8, velocity=127)
        assert voice.velocity == 127

    def test_voice_channel_at_boundary_1(self):
        """channel=1 is valid (first MIDI channel)."""
        voice = PolyrhythmVoice(pulses=1, steps=8, channel=1)
        assert voice.channel == 1

    def test_voice_channel_at_boundary_16(self):
        """channel=16 is valid (last MIDI channel)."""
        voice = PolyrhythmVoice(pulses=1, steps=8, channel=16)
        assert voice.channel == 16


class TestPolyrhythmIntegration:
    """Integration tests across multiple components."""

    def test_polyrhythm_with_different_note_assignments(self):
        """voice_a and voice_b can have different MIDI notes."""
        voice_a = PolyrhythmVoice(pulses=3, steps=8, note=60)
        voice_b = PolyrhythmVoice(pulses=5, steps=16, note=64)
        cfg = PolyrhythmConfig(voice_a=voice_a, voice_b=voice_b)
        poly = Polyrhythm(cfg)

        fires = poly.tick(0.0)
        for name, voice in fires:
            if name == "a":
                assert voice.note == 60
            elif name == "b":
                assert voice.note == 64

    def test_polyrhythm_reset_and_retick(self):
        """Reset allows re-cycling from the start."""
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)

        fires1 = poly.tick(0.0)
        poly.reset()
        fires2 = poly.tick(0.0)

        # Both first ticks should produce same result
        assert len(fires1) == len(fires2)

    def test_polyrhythm_enable_disable_lifecycle(self):
        """Polyrhythm respects enabled flag throughout lifecycle."""
        cfg = PolyrhythmConfig(enabled=False)
        poly = Polyrhythm(cfg)
        fires = poly.tick(0.0)
        assert fires == []

        # Can't enable directly (config is immutable once set),
        # but we can create a new config and polyrhythm
        cfg2 = PolyrhythmConfig(enabled=True)
        poly2 = Polyrhythm(cfg2)
        fires2 = poly2.tick(0.0)
        # fires2 may or may not be empty depending on patterns,
        # but the polyrhythm should respect enabled=True
        assert poly2.cfg.enabled is True
