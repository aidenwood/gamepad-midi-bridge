"""Tests for audio-reactive MIDI CC simulator.

AudioReactiveSim generates MIDI CC values from synthetic audio samples using
peak-hold, envelope-follower, or direct-follow modes. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestAudioReactiveConfig:
    """AudioReactiveConfig — clamp values on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig()
        assert cfg.enabled is False
        assert cfg.cc == 1
        assert cfg.channel == 1
        assert cfg.mode == "follow"
        assert cfg.attack_ms == 5.0
        assert cfg.release_ms == 100.0
        assert cfg.gain == 1.0
        assert cfg.threshold == 0.0
        assert cfg.invert is False
        assert cfg.min_cc == 0
        assert cfg.max_cc == 127

    def test_config_clamp_cc_below_zero(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(cc=-1)
        assert cfg.cc == 0
        cfg = AudioReactiveConfig(cc=-100)
        assert cfg.cc == 0

    def test_config_clamp_cc_above_127(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(cc=128)
        assert cfg.cc == 127
        cfg = AudioReactiveConfig(cc=200)
        assert cfg.cc == 127

    def test_config_clamp_channel_below_1(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(channel=0)
        assert cfg.channel == 1
        cfg = AudioReactiveConfig(channel=-5)
        assert cfg.channel == 1

    def test_config_clamp_channel_above_16(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(channel=17)
        assert cfg.channel == 16
        cfg = AudioReactiveConfig(channel=100)
        assert cfg.channel == 16

    def test_config_mode_follow(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(mode="follow")
        assert cfg.mode == "follow"

    def test_config_mode_peak_hold(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(mode="peak_hold")
        assert cfg.mode == "peak_hold"

    def test_config_mode_envelope(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(mode="envelope")
        assert cfg.mode == "envelope"

    def test_config_mode_case_insensitive(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(mode="FOLLOW")
        assert cfg.mode == "follow"
        cfg = AudioReactiveConfig(mode="Peak_Hold")
        assert cfg.mode == "peak_hold"
        cfg = AudioReactiveConfig(mode="ENVELOPE")
        assert cfg.mode == "envelope"

    def test_config_mode_unknown_defaults_to_follow(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(mode="unknown_mode")
        assert cfg.mode == "follow"

    def test_config_clamp_attack_ms_below_0_1(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(attack_ms=0.01)
        assert cfg.attack_ms == 0.1
        cfg = AudioReactiveConfig(attack_ms=-5.0)
        assert cfg.attack_ms == 0.1

    def test_config_clamp_attack_ms_above_2000(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(attack_ms=2001.0)
        assert cfg.attack_ms == 2000.0
        cfg = AudioReactiveConfig(attack_ms=10000.0)
        assert cfg.attack_ms == 2000.0

    def test_config_clamp_release_ms_below_1(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(release_ms=0.5)
        assert cfg.release_ms == 1.0
        cfg = AudioReactiveConfig(release_ms=-100.0)
        assert cfg.release_ms == 1.0

    def test_config_clamp_release_ms_above_10000(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(release_ms=10001.0)
        assert cfg.release_ms == 10000.0
        cfg = AudioReactiveConfig(release_ms=20000.0)
        assert cfg.release_ms == 10000.0

    def test_config_clamp_gain_below_0_01(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(gain=0.001)
        assert cfg.gain == 0.01
        cfg = AudioReactiveConfig(gain=-1.0)
        assert cfg.gain == 0.01

    def test_config_clamp_gain_above_10(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(gain=10.1)
        assert cfg.gain == 10.0
        cfg = AudioReactiveConfig(gain=100.0)
        assert cfg.gain == 10.0

    def test_config_clamp_threshold_below_0(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(threshold=-0.1)
        assert cfg.threshold == 0.0
        cfg = AudioReactiveConfig(threshold=-1.0)
        assert cfg.threshold == 0.0

    def test_config_clamp_threshold_above_1(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(threshold=1.1)
        assert cfg.threshold == 1.0
        cfg = AudioReactiveConfig(threshold=2.0)
        assert cfg.threshold == 1.0

    def test_config_clamp_min_cc_below_0(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(min_cc=-1)
        assert cfg.min_cc == 0

    def test_config_clamp_min_cc_above_127(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(min_cc=128)
        assert cfg.min_cc == 127

    def test_config_clamp_max_cc_below_0(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(max_cc=-1)
        assert cfg.max_cc == 0

    def test_config_clamp_max_cc_above_127(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(max_cc=128)
        assert cfg.max_cc == 127

    def test_config_swap_min_max_if_reversed(self):
        """If min_cc > max_cc, they are swapped."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(min_cc=100, max_cc=50)
        assert cfg.min_cc == 50
        assert cfg.max_cc == 100

    def test_config_to_dict(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True,
            cc=5,
            channel=3,
            mode="envelope",
            attack_ms=10.0,
            release_ms=200.0,
            gain=2.0,
            threshold=0.1,
            invert=True,
            min_cc=20,
            max_cc=120,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["cc"] == 5
        assert d["channel"] == 3
        assert d["mode"] == "envelope"
        assert d["attack_ms"] == 10.0
        assert d["release_ms"] == 200.0
        assert d["gain"] == 2.0
        assert d["threshold"] == 0.1
        assert d["invert"] is True
        assert d["min_cc"] == 20
        assert d["max_cc"] == 120

    def test_config_from_dict(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        d = {
            "enabled": True,
            "cc": 7,
            "channel": 4,
            "mode": "peak_hold",
            "attack_ms": 15.0,
            "release_ms": 250.0,
            "gain": 1.5,
            "threshold": 0.2,
            "invert": False,
            "min_cc": 30,
            "max_cc": 110,
        }
        cfg = AudioReactiveConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.cc == 7
        assert cfg.channel == 4
        assert cfg.mode == "peak_hold"

    def test_config_from_dict_missing_keys_use_defaults(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        d = {"enabled": True}
        cfg = AudioReactiveConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.cc == 1
        assert cfg.channel == 1
        assert cfg.mode == "follow"
        assert cfg.attack_ms == 5.0
        assert cfg.release_ms == 100.0
        assert cfg.gain == 1.0
        assert cfg.threshold == 0.0
        assert cfg.invert is False
        assert cfg.min_cc == 0
        assert cfg.max_cc == 127

    def test_config_round_trip(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveConfig
        original = AudioReactiveConfig(
            enabled=True,
            cc=10,
            channel=8,
            mode="envelope",
            attack_ms=20.0,
            release_ms=150.0,
            gain=1.5,
            threshold=0.05,
            invert=True,
            min_cc=25,
            max_cc=100,
        )
        d = original.to_dict()
        restored = AudioReactiveConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.cc == original.cc
        assert restored.channel == original.channel
        assert restored.mode == original.mode
        assert restored.attack_ms == original.attack_ms
        assert restored.release_ms == original.release_ms
        assert restored.gain == original.gain
        assert restored.threshold == original.threshold
        assert restored.invert == original.invert
        assert restored.min_cc == original.min_cc
        assert restored.max_cc == original.max_cc


class TestAudioReactiveSim:
    """AudioReactiveSim — stateful audio-reactive CC simulator."""

    def test_feed_disabled_returns_min_cc(self):
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=False, min_cc=10, max_cc=100)
        sim = AudioReactiveSim(cfg)
        # Regardless of input, disabled returns min_cc.
        assert sim.feed(0.0, 0.0) == 10
        assert sim.feed(0.5, 0.1) == 10
        assert sim.feed(1.0, 0.2) == 10

    def test_feed_follow_mode_zero_input(self):
        """follow mode with 0.0 input → min_cc."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=True, mode="follow", min_cc=0, max_cc=127)
        sim = AudioReactiveSim(cfg)
        # 0.0 * 1.0 gain → 0.0 processed → maps to 0 + 0.0 * 127 = 0.
        assert sim.feed(0.0, 0.0) == 0

    def test_feed_follow_mode_half_input(self):
        """follow mode with 0.5 input → center CC."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=True, mode="follow", min_cc=0, max_cc=127)
        sim = AudioReactiveSim(cfg)
        # 0.5 * 1.0 gain → 0.5 processed → maps to 0 + 0.5 * 127 = 63.5 → 64.
        result = sim.feed(0.5, 0.0)
        assert result == 63 or result == 64  # Rounding.

    def test_feed_follow_mode_full_input(self):
        """follow mode with 1.0 input → max_cc."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=True, mode="follow", min_cc=0, max_cc=127)
        sim = AudioReactiveSim(cfg)
        # 1.0 * 1.0 gain → 1.0 processed → maps to 0 + 1.0 * 127 = 127.
        assert sim.feed(1.0, 0.0) == 127

    def test_feed_clamp_input_level_below_zero(self):
        """Negative input level clamped to 0."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=True, mode="follow", min_cc=0, max_cc=127)
        sim = AudioReactiveSim(cfg)
        # -0.5 clamped to 0.0 → 0 CC.
        assert sim.feed(-0.5, 0.0) == 0

    def test_feed_clamp_input_level_above_one(self):
        """Input > 1.0 clamped to 1.0."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=True, mode="follow", min_cc=0, max_cc=127)
        sim = AudioReactiveSim(cfg)
        # 2.0 clamped to 1.0 → 127 CC.
        assert sim.feed(2.0, 0.0) == 127

    def test_feed_threshold_below_suppresses(self):
        """Input below threshold → output is min_cc."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="follow", threshold=0.5, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # 0.1 * gain < 0.5 threshold → output = 0 → 0 CC.
        assert sim.feed(0.1, 0.0) == 0

    def test_feed_threshold_above_passes(self):
        """Input above threshold → output is normal."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="follow", threshold=0.3, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # 0.7 * gain >= 0.3 threshold → output = 0.7 → ~89 CC.
        result = sim.feed(0.7, 0.0)
        assert result > 80

    def test_feed_gain_amplifies(self):
        """gain > 1.0 amplifies the signal."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="follow", gain=2.0, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # 0.5 * 2.0 gain = 1.0 → 127 CC.
        result = sim.feed(0.5, 0.0)
        assert result == 127

    def test_feed_gain_attenuates(self):
        """gain < 1.0 attenuates the signal."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="follow", gain=0.5, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # 0.8 * 0.5 gain = 0.4 → ~51 CC.
        result = sim.feed(0.8, 0.0)
        assert result in range(48, 55)

    def test_feed_invert_flips_output(self):
        """invert=True reverses the signal."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="follow", invert=False, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        normal = sim.feed(0.3, 0.0)

        cfg_inv = AudioReactiveConfig(
            enabled=True, mode="follow", invert=True, min_cc=0, max_cc=127
        )
        sim_inv = AudioReactiveSim(cfg_inv)
        inverted = sim_inv.feed(0.3, 0.0)

        # inverted should be approximately 127 - normal.
        assert abs((127 - normal) - inverted) <= 1

    def test_feed_min_max_cc_mapping(self):
        """Output scaled to [min_cc, max_cc]."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="follow", min_cc=50, max_cc=100
        )
        sim = AudioReactiveSim(cfg)
        # 0.0 → 50 CC.
        assert sim.feed(0.0, 0.0) == 50
        # 1.0 → 100 CC.
        assert sim.feed(1.0, 0.0) == 100
        # 0.5 → 50 + 0.5 * 50 = 75.
        result = sim.feed(0.5, 0.0)
        assert result in [74, 75, 76]

    def test_feed_peak_hold_tracks_peak(self):
        """peak_hold mode tracks rising peaks."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="peak_hold", min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # Feed 0.5 → peak = 0.5 → ~64 CC.
        r1 = sim.feed(0.5, 0.0)
        assert r1 > 60

        # Feed 0.8 → peak = 0.8 → ~102 CC.
        r2 = sim.feed(0.8, 0.01)
        assert r2 > 95

    def test_feed_peak_hold_decays(self):
        """peak_hold mode decays after release_ms."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="peak_hold", release_ms=100, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # Set peak to 0.9.
        r1 = sim.feed(0.9, 0.0)
        assert r1 > 100

        # Very soon after, no decay yet (< 100 ms).
        r2 = sim.feed(0.1, 0.01)
        assert r2 > r1 - 5  # Should still be high.

        # After release_ms, decay applies.
        r3 = sim.feed(0.1, 0.15)
        assert r3 < r2  # Should have decayed.

    def test_feed_envelope_rising(self):
        """envelope mode rises with attack_ms."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="envelope", attack_ms=10.0, release_ms=100.0, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # First feed initializes envelope to level.
        r1 = sim.feed(0.9, 0.0)
        assert r1 > 100

        # Second feed should approach 1.0 gradually (short dt).
        r2 = sim.feed(1.0, 0.001)
        # With dt=0.001 and attack=10ms (0.01s), alpha ≈ 1 - exp(-0.001/0.01) ≈ 0.095.
        # env ≈ 0.9 + 0.095 * (1.0 - 0.9) = 0.9095 → ~115 CC.
        assert r2 > 100

    def test_feed_envelope_falling(self):
        """envelope mode falls with release_ms."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="envelope", attack_ms=5.0, release_ms=50.0, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        # Ramp up to high level.
        sim.feed(1.0, 0.0)
        sim.feed(1.0, 0.01)

        # Drop level; should fall slowly with release_ms.
        r1 = sim.feed(0.0, 0.02)
        assert r1 > 50  # Should still be fairly high.

        # Much later, level should have fallen more.
        r2 = sim.feed(0.0, 0.15)
        assert r2 < r1  # Further decay.

    def test_reset_clears_state(self):
        """reset() clears envelope, peak, and timing."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="peak_hold", release_ms=100, min_cc=0, max_cc=127
        )
        sim = AudioReactiveSim(cfg)
        sim.feed(0.9, 0.0)
        assert sim._peak > 0
        assert sim._peak_set_at is not None

        sim.reset()
        assert sim._peak == 0.0
        assert sim._env == 0.0
        assert sim._peak_set_at is None

    def test_feed_rapid_samples_dont_blow_up(self):
        """Rapid high-frequency sampling doesn't cause NaN/Inf."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=True, mode="envelope", min_cc=0, max_cc=127)
        sim = AudioReactiveSim(cfg)
        # Simulate 1000 samples at 44.1 kHz (22.7 ms total).
        for i in range(1000):
            t = i / 44100.0
            level = 0.5 + 0.3 * ((i % 100) / 100.0)  # Oscillate.
            result = sim.feed(level, t)
            assert 0 <= result <= 127
            assert not (result != result)  # Not NaN.

    def test_very_small_attack_release_times(self):
        """Extreme clamping of attack/release doesn't break."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True, mode="envelope", attack_ms=0.05, release_ms=0.5
        )
        # Should be clamped to 0.1 and 1.0.
        assert cfg.attack_ms == 0.1
        assert cfg.release_ms == 1.0
        sim = AudioReactiveSim(cfg)
        result = sim.feed(0.7, 0.0)
        assert 0 <= result <= 127

    def test_disabled_always_returns_min_cc_regardless_of_mode(self):
        """Disabled config always returns min_cc, even with complex params."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=False,
            mode="envelope",
            gain=5.0,
            threshold=0.1,
            min_cc=40,
            max_cc=120,
        )
        sim = AudioReactiveSim(cfg)
        # Even with extreme settings, always returns min_cc.
        assert sim.feed(0.5, 0.0) == 40
        assert sim.feed(1.0, 0.0) == 40
        assert sim.feed(0.01, 0.0) == 40

    def test_unknown_mode_defaults_to_follow(self):
        """Unknown mode falls back to follow."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(enabled=True, mode="nonexistent", min_cc=0, max_cc=127)
        # Config should have normalized mode to "follow".
        assert cfg.mode == "follow"
        sim = AudioReactiveSim(cfg)
        # Should behave like follow mode.
        r1 = sim.feed(0.5, 0.0)
        r2 = sim.feed(1.0, 0.0)
        assert r2 > r1  # Direct follow should increase.

    def test_cc_output_always_0_to_127(self):
        """All outputs are in 0..127 range."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        import random
        random.seed(42)
        cfg = AudioReactiveConfig(
            enabled=True, mode="envelope", min_cc=30, max_cc=110, gain=3.0, threshold=0.1
        )
        sim = AudioReactiveSim(cfg)
        for _ in range(100):
            level = random.uniform(0.0, 1.5)
            t = random.uniform(0.0, 1.0)
            result = sim.feed(level, t)
            assert 0 <= result <= 127

    def test_comprehensive_workflow_follow_with_min_max(self):
        """End-to-end: follow mode, custom min/max, gain, threshold."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True,
            mode="follow",
            gain=1.5,
            threshold=0.2,
            min_cc=20,
            max_cc=100,
        )
        sim = AudioReactiveSim(cfg)

        # Below threshold: min_cc.
        assert sim.feed(0.1, 0.0) == 20

        # At threshold (0.2): just passes, output near min_cc.
        result = sim.feed(0.2, 0.0)
        assert result >= 20

        # Well above threshold: interpolated in [20, 100].
        result = sim.feed(0.8, 0.0)
        assert 70 <= result <= 100

    def test_comprehensive_workflow_peak_hold(self):
        """End-to-end: peak_hold mode with decay."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True,
            mode="peak_hold",
            release_ms=100,
            min_cc=0,
            max_cc=127,
        )
        sim = AudioReactiveSim(cfg)

        # Spike to 0.8.
        r1 = sim.feed(0.8, 0.0)
        assert r1 > 95

        # Drop to 0.1 immediately, but peak holds.
        r2 = sim.feed(0.1, 0.001)
        assert r2 > r1 - 10  # Should still be high.

        # Wait 150 ms, decay should have happened multiple times.
        r3 = sim.feed(0.1, 0.15)
        assert r3 < r2  # Should have decayed.

    def test_comprehensive_workflow_envelope(self):
        """End-to-end: envelope mode with attack and release."""
        from gamepad_midi_bridge.audio_reactive_sim import AudioReactiveSim, AudioReactiveConfig
        cfg = AudioReactiveConfig(
            enabled=True,
            mode="envelope",
            attack_ms=20.0,
            release_ms=100.0,
            min_cc=0,
            max_cc=127,
        )
        sim = AudioReactiveSim(cfg)

        # Ramp up: should follow with attack time constant.
        r0 = sim.feed(1.0, 0.0)
        assert r0 == 127  # First sample sets envelope to level.

        # Drop to 0: should fall slowly.
        r1 = sim.feed(0.0, 0.01)
        assert r1 < 127 and r1 > 50  # Decayed, but not fully.

        # Much later: almost at 0.
        r2 = sim.feed(0.0, 0.2)
        assert r2 < r1  # Further decayed.
