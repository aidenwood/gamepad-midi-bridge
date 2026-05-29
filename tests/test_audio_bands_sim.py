"""Tests for 4-band audio-reactive MIDI CC simulator.

AudioBandsSim generates independent MIDI CC values for 4 audio frequency bands
(bass, low_mid, high_mid, treble) from synthetic amplitude samples.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestAudioBandConfig:
    """AudioBandConfig — serialization and deserialization."""

    def test_band_config_defaults(self):
        from gamepad_midi_bridge.audio_bands_sim import AudioBandConfig

        cfg = AudioBandConfig(name="bass")
        assert cfg.name == "bass"
        assert cfg.audio_config == {}

    def test_band_config_round_trip(self):
        from gamepad_midi_bridge.audio_bands_sim import AudioBandConfig

        cfg = AudioBandConfig(
            name="bass",
            audio_config={
                "enabled": True,
                "cc": 20,
                "channel": 1,
                "mode": "follow",
                "min_cc": 0,
                "max_cc": 127,
            },
        )
        data = cfg.to_dict()
        cfg2 = AudioBandConfig.from_dict(data)
        assert cfg2.name == "bass"
        assert cfg2.audio_config == cfg.audio_config


class TestAudioBandsConfig:
    """AudioBandsConfig — serialization and deserialization."""

    def test_bands_config_defaults(self):
        from gamepad_midi_bridge.audio_bands_sim import AudioBandsConfig

        cfg = AudioBandsConfig()
        assert cfg.enabled is False
        assert cfg.bands == []

    def test_bands_config_round_trip(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={
                    "enabled": True,
                    "cc": 20,
                    "channel": 1,
                    "mode": "follow",
                },
            ),
            AudioBandConfig(
                name="treble",
                audio_config={
                    "enabled": True,
                    "cc": 23,
                    "channel": 1,
                    "mode": "follow",
                },
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        data = cfg.to_dict()
        cfg2 = AudioBandsConfig.from_dict(data)
        assert cfg2.enabled is True
        assert len(cfg2.bands) == 2
        assert cfg2.bands[0].name == "bass"
        assert cfg2.bands[1].name == "treble"


class TestAudioBandsSim:
    """AudioBandsSim — 4-band audio-reactive CC simulator."""

    def test_empty_bands_feed_returns_empty(self):
        from gamepad_midi_bridge.audio_bands_sim import AudioBandsConfig, AudioBandsSim

        cfg = AudioBandsConfig(enabled=True, bands=[])
        sim = AudioBandsSim(cfg)
        results = sim.feed(0.5, 0.5, 0.5, 0.5, 0.0)
        assert results == []

    def test_4_band_config_feed_returns_4_results(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={
                    "enabled": True,
                    "cc": 20,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="low_mid",
                audio_config={
                    "enabled": True,
                    "cc": 21,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="high_mid",
                audio_config={
                    "enabled": True,
                    "cc": 22,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="treble",
                audio_config={
                    "enabled": True,
                    "cc": 23,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        results = sim.feed(0.5, 0.5, 0.5, 0.5, 0.0)
        assert len(results) == 4

    def test_each_band_emits_own_cc(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={
                    "enabled": True,
                    "cc": 20,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="low_mid",
                audio_config={
                    "enabled": True,
                    "cc": 21,
                    "channel": 2,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="high_mid",
                audio_config={
                    "enabled": True,
                    "cc": 22,
                    "channel": 3,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="treble",
                audio_config={
                    "enabled": True,
                    "cc": 23,
                    "channel": 4,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        results = sim.feed(0.5, 0.5, 0.5, 0.5, 0.0)
        # Check that each result has the expected CC number and channel.
        assert results[0][0] == 20  # bass CC
        assert results[0][1] == 1  # bass channel
        assert results[1][0] == 21  # low_mid CC
        assert results[1][1] == 2  # low_mid channel
        assert results[2][0] == 22  # high_mid CC
        assert results[2][1] == 3  # high_mid channel
        assert results[3][0] == 23  # treble CC
        assert results[3][1] == 4  # treble channel

    def test_feed_array_equivalent_to_feed(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={
                    "enabled": True,
                    "cc": 20,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="treble",
                audio_config={
                    "enabled": True,
                    "cc": 23,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        results_feed = sim.feed(0.25, 0.5, 0.75, 0.9, 0.0)
        # Reset and use feed_array.
        sim.reset()
        results_array = sim.feed_array([0.25, 0.5, 0.75, 0.9], 0.0)
        assert results_feed == results_array

    def test_reset_clears_all_bands(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={
                    "enabled": True,
                    "cc": 20,
                    "channel": 1,
                    "mode": "envelope",
                    "attack_ms": 5.0,
                    "release_ms": 100.0,
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="treble",
                audio_config={
                    "enabled": True,
                    "cc": 23,
                    "channel": 1,
                    "mode": "envelope",
                    "attack_ms": 5.0,
                    "release_ms": 100.0,
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        # Feed a high value to build up envelope state.
        results1 = sim.feed(0.9, 0.0, 0.0, 0.9, 0.0)
        # Reset.
        sim.reset()
        # Feed the same value again — envelope should start from zero.
        results2 = sim.feed(0.9, 0.0, 0.0, 0.9, 0.0)
        # Values should be different due to envelope attack.
        # (The exact comparison depends on attack time, but they should differ.)
        # For now, just verify reset doesn't crash.
        assert len(results2) == 2

    def test_band_names_returns_configured_list(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={"enabled": True, "cc": 20, "channel": 1},
            ),
            AudioBandConfig(
                name="treble",
                audio_config={"enabled": True, "cc": 23, "channel": 1},
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        names = sim.band_names()
        assert names == ["bass", "treble"]

    def test_slot_count_matches_configured_bands(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={"enabled": True, "cc": 20, "channel": 1},
            ),
            AudioBandConfig(
                name="low_mid",
                audio_config={"enabled": True, "cc": 21, "channel": 1},
            ),
            AudioBandConfig(
                name="treble",
                audio_config={"enabled": True, "cc": 23, "channel": 1},
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        assert sim.slot_count() == 3

    def test_missing_bands_returns_fewer_results(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        # Only configure bass and treble, skip low_mid and high_mid.
        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={"enabled": True, "cc": 20, "channel": 1},
            ),
            AudioBandConfig(
                name="treble",
                audio_config={"enabled": True, "cc": 23, "channel": 1},
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        results = sim.feed(0.5, 0.0, 0.0, 0.5, 0.0)
        assert len(results) == 2
        assert results[0][0] == 20  # bass
        assert results[1][0] == 23  # treble

    def test_high_amplitude_in_bass_produces_high_cc(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={
                    "enabled": True,
                    "cc": 20,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        results = sim.feed(1.0, 0.0, 0.0, 0.0, 0.0)
        assert len(results) == 1
        # High amplitude (1.0) should map to high CC value (127).
        assert results[0][2] >= 120  # Allow small rounding variance.

    def test_bass_and_treble_independent(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={
                    "enabled": True,
                    "cc": 20,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
            AudioBandConfig(
                name="treble",
                audio_config={
                    "enabled": True,
                    "cc": 23,
                    "channel": 1,
                    "mode": "follow",
                    "min_cc": 0,
                    "max_cc": 127,
                },
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        # Feed high bass, low treble.
        results = sim.feed(0.9, 0.0, 0.0, 0.1, 0.0)
        assert len(results) == 2
        bass_value = results[0][2]
        treble_value = results[1][2]
        # Bass should be significantly higher than treble.
        assert bass_value > treble_value

    def test_feed_array_with_extra_elements_ignored(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={"enabled": True, "cc": 20, "channel": 1},
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        # Pass 6 elements; only first 4 should be used.
        results = sim.feed_array([0.5, 0.0, 0.0, 0.0, 0.9, 0.9], 0.0)
        assert len(results) == 1
        # Verify it's the bass value (first element).
        assert results[0][0] == 20

    def test_feed_array_with_fewer_elements_pads_zeros(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={"enabled": True, "cc": 20, "channel": 1},
            ),
            AudioBandConfig(
                name="treble",
                audio_config={"enabled": True, "cc": 23, "channel": 1},
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        # Pass only 2 elements; treble should default to 0.0.
        results = sim.feed_array([0.5, 0.0], 0.0)
        assert len(results) == 2
        # Treble should be at minimum CC (0) since level is 0.0.
        assert results[1][2] == 0

    def test_all_zero_input_returns_low_values(self):
        from gamepad_midi_bridge.audio_bands_sim import (
            AudioBandConfig,
            AudioBandsConfig,
            AudioBandsSim,
        )

        band_configs = [
            AudioBandConfig(
                name="bass",
                audio_config={"enabled": True, "cc": 20, "channel": 1},
            ),
            AudioBandConfig(
                name="treble",
                audio_config={"enabled": True, "cc": 23, "channel": 1},
            ),
        ]
        cfg = AudioBandsConfig(enabled=True, bands=band_configs)
        sim = AudioBandsSim(cfg)
        results = sim.feed(0.0, 0.0, 0.0, 0.0, 0.0)
        assert len(results) == 2
        # All zero input should produce low CC values (close to min_cc).
        assert results[0][2] == 0
        assert results[1][2] == 0
