"""Tests for humanized quantizer.

Combines grid quantization, groove templates, and per-event jitter.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestHumanizedQuantizerConfig:
    """HumanizedQuantizerConfig — configuration with validation and clamping."""

    def test_config_defaults(self):
        """Default config values."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg = HumanizedQuantizerConfig()
        assert cfg.enabled is False
        assert cfg.bpm == 120.0
        assert cfg.subdivision == "1/16"
        assert cfg.humanize_ms == 5.0
        assert cfg.velocity_humanize == 5
        assert cfg.groove_template_name == "straight"
        assert cfg.groove_intensity == 1.0
        assert cfg.seed is None

    def test_config_clamp_bpm_below_minimum(self):
        """BPM < 20 clamped to 20."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg = HumanizedQuantizerConfig(bpm=10)
        assert cfg.bpm == 20.0

    def test_config_clamp_bpm_above_maximum(self):
        """BPM > 300 clamped to 300."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg = HumanizedQuantizerConfig(bpm=400)
        assert cfg.bpm == 300.0

    def test_config_clamp_humanize_ms(self):
        """humanize_ms clamped to 0–50."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg_neg = HumanizedQuantizerConfig(humanize_ms=-10)
        assert cfg_neg.humanize_ms == 0.0

        cfg_max = HumanizedQuantizerConfig(humanize_ms=100)
        assert cfg_max.humanize_ms == 50.0

    def test_config_clamp_velocity_humanize(self):
        """velocity_humanize clamped to 0–40."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg_neg = HumanizedQuantizerConfig(velocity_humanize=-5)
        assert cfg_neg.velocity_humanize == 0

        cfg_max = HumanizedQuantizerConfig(velocity_humanize=100)
        assert cfg_max.velocity_humanize == 40

    def test_config_clamp_groove_intensity(self):
        """groove_intensity clamped to 0–2."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg_neg = HumanizedQuantizerConfig(groove_intensity=-0.5)
        assert cfg_neg.groove_intensity == 0.0

        cfg_max = HumanizedQuantizerConfig(groove_intensity=5.0)
        assert cfg_max.groove_intensity == 2.0

    def test_config_validate_subdivision(self):
        """Unknown subdivision defaults to '1/16'."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg = HumanizedQuantizerConfig(subdivision="invalid")
        assert cfg.subdivision == "1/16"

    def test_config_validate_groove_template(self):
        """Unknown groove template defaults to 'straight'."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg = HumanizedQuantizerConfig(groove_template_name="nonexistent")
        assert cfg.groove_template_name == "straight"

    def test_config_to_dict(self):
        """to_dict() serializes config."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg = HumanizedQuantizerConfig(
            enabled=True,
            bpm=140,
            subdivision="1/8",
            humanize_ms=10.0,
            velocity_humanize=8,
            groove_template_name="swing_light",
            groove_intensity=0.8,
            seed=42,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["bpm"] == 140.0
        assert d["subdivision"] == "1/8"
        assert d["humanize_ms"] == 10.0
        assert d["velocity_humanize"] == 8
        assert d["groove_template_name"] == "swing_light"
        assert d["groove_intensity"] == 0.8
        assert d["seed"] == 42

    def test_config_from_dict(self):
        """from_dict() deserializes config with validation."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        data = {
            "enabled": True,
            "bpm": 160,
            "subdivision": "1/4",
            "humanize_ms": 15.0,
            "velocity_humanize": 10,
            "groove_template_name": "swing_heavy",
            "groove_intensity": 1.5,
            "seed": 99,
        }
        cfg = HumanizedQuantizerConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.bpm == 160.0
        assert cfg.subdivision == "1/4"
        assert cfg.humanize_ms == 15.0
        assert cfg.velocity_humanize == 10
        assert cfg.groove_template_name == "swing_heavy"
        assert cfg.groove_intensity == 1.5
        assert cfg.seed == 99

    def test_config_round_trip(self):
        """to_dict() → from_dict() round-trip."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig

        cfg1 = HumanizedQuantizerConfig(
            enabled=True,
            bpm=110,
            subdivision="1/8d",
            humanize_ms=20.0,
            velocity_humanize=15,
            groove_template_name="shuffle",
            groove_intensity=1.2,
            seed=777,
        )
        d = cfg1.to_dict()
        cfg2 = HumanizedQuantizerConfig.from_dict(d)

        assert cfg2.enabled == cfg1.enabled
        assert cfg2.bpm == cfg1.bpm
        assert cfg2.subdivision == cfg1.subdivision
        assert cfg2.humanize_ms == cfg1.humanize_ms
        assert cfg2.velocity_humanize == cfg1.velocity_humanize
        assert cfg2.groove_template_name == cfg1.groove_template_name
        assert cfg2.groove_intensity == cfg1.groove_intensity
        assert cfg2.seed == cfg1.seed


class TestHumanizedQuantizer:
    """HumanizedQuantizer — quantization with grid, groove, and jitter."""

    def test_quantize_time_basic_snap(self):
        """quantize_time() snaps to grid without jitter."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg = HumanizedQuantizerConfig(
            enabled=True,
            bpm=120,
            subdivision="1/4",
            humanize_ms=0,
            velocity_humanize=0,
            seed=42,
        )
        q = HumanizedQuantizer(cfg)
        # At 120 BPM, 1/4 note = 500ms = 0.5s
        # Snap 0.3s to nearest grid → should be 0.5s
        t = q.quantize_time(0.3)
        assert abs(t - 0.5) < 0.001

    def test_quantize_time_with_jitter_reproducible(self):
        """quantize_time() with seed produces reproducible offsets."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg = HumanizedQuantizerConfig(
            enabled=True,
            bpm=120,
            subdivision="1/4",
            humanize_ms=10.0,
            velocity_humanize=0,
            seed=42,
        )
        q1 = HumanizedQuantizer(cfg)
        q2 = HumanizedQuantizer(cfg)

        t1 = q1.quantize_time(0.3)
        t2 = q2.quantize_time(0.3)
        # Same seed should produce same result
        assert abs(t1 - t2) < 1e-10

    def test_quantize_time_different_seeds_differ(self):
        """quantize_time() with different seeds produces different offsets."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg1 = HumanizedQuantizerConfig(
            enabled=True,
            bpm=120,
            subdivision="1/4",
            humanize_ms=10.0,
            velocity_humanize=0,
            seed=42,
        )
        cfg2 = HumanizedQuantizerConfig(
            enabled=True,
            bpm=120,
            subdivision="1/4",
            humanize_ms=10.0,
            velocity_humanize=0,
            seed=99,
        )
        q1 = HumanizedQuantizer(cfg1)
        q2 = HumanizedQuantizer(cfg2)

        t1 = q1.quantize_time(0.3)
        t2 = q2.quantize_time(0.3)
        # Different seeds should produce different jitter
        assert abs(t1 - t2) > 1e-6  # Unlikely to collide by chance

    def test_humanize_velocity_basic(self):
        """humanize_velocity() returns velocity within range."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg = HumanizedQuantizerConfig(velocity_humanize=5, seed=42)
        q = HumanizedQuantizer(cfg)

        v = q.humanize_velocity(100)
        # Should be within ±5 of 100
        assert 95 <= v <= 105
        assert isinstance(v, int)

    def test_humanize_velocity_zero_offset(self):
        """velocity_humanize=0 returns input unchanged."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg = HumanizedQuantizerConfig(velocity_humanize=0)
        q = HumanizedQuantizer(cfg)

        assert q.humanize_velocity(100) == 100
        assert q.humanize_velocity(50) == 50
        assert q.humanize_velocity(127) == 127

    def test_humanize_velocity_clamp_low(self):
        """humanize_velocity() clamps to 1 at low end."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg = HumanizedQuantizerConfig(velocity_humanize=20, seed=1)
        q = HumanizedQuantizer(cfg)

        # Try several times to find a downward clamp case
        for base in [5, 10, 15]:
            v = q.humanize_velocity(base)
            assert v >= 1
            assert v <= 127

    def test_humanize_velocity_clamp_high(self):
        """humanize_velocity() clamps to 127 at high end."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg = HumanizedQuantizerConfig(velocity_humanize=20, seed=2)
        q = HumanizedQuantizer(cfg)

        # Try several times to find an upward clamp case
        for base in [110, 115, 120]:
            v = q.humanize_velocity(base)
            assert v >= 1
            assert v <= 127

    def test_reset_reproduces_sequence(self):
        """reset() reseeds the RNG to produce same sequence."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg = HumanizedQuantizerConfig(velocity_humanize=10, seed=42)
        q = HumanizedQuantizer(cfg)

        # First sequence
        v1_first = q.humanize_velocity(100)
        v1_second = q.humanize_velocity(100)

        # Reset and capture again
        q.reset()
        v2_first = q.humanize_velocity(100)
        v2_second = q.humanize_velocity(100)

        # Should match after reset
        assert v1_first == v2_first
        assert v1_second == v2_second

    def test_seeded_at(self):
        """seeded_at() returns the configured seed."""
        from gamepad_midi_bridge.humanized_quantizer import HumanizedQuantizerConfig, HumanizedQuantizer

        cfg_seeded = HumanizedQuantizerConfig(seed=42)
        q_seeded = HumanizedQuantizer(cfg_seeded)
        assert q_seeded.seeded_at() == 42

        cfg_unseeded = HumanizedQuantizerConfig(seed=None)
        q_unseeded = HumanizedQuantizer(cfg_unseeded)
        assert q_unseeded.seeded_at() is None
