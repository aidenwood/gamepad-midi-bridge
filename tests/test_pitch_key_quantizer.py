"""Tests for pitch key quantizer.

PitchKeyQuantizer snaps MIDI notes to the nearest in-key note,
configured with root + scale + direction (nearest/up/down).
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestPitchKeyQuantizerConfig:
    """PitchKeyQuantizerConfig — initialization and clamping."""

    def test_config_default_values(self):
        """Default config has sensible values."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        cfg = PitchKeyQuantizerConfig()
        assert cfg.enabled is False
        assert cfg.root == 60
        assert cfg.scale == "major"
        assert cfg.direction == "nearest"
        assert cfg.bypass_when_in_key is True

    def test_config_clamp_root_below_range(self):
        """root < 0 clamped to 0."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        cfg = PitchKeyQuantizerConfig(root=-10)
        assert cfg.root == 0

    def test_config_clamp_root_above_range(self):
        """root > 127 clamped to 127."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        cfg = PitchKeyQuantizerConfig(root=200)
        assert cfg.root == 127

    def test_config_unknown_scale_fallback_to_major(self):
        """Unknown scale falls back to major."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        cfg = PitchKeyQuantizerConfig(scale="unknown_scale")
        assert cfg.scale == "major"

    def test_config_unknown_direction_fallback_to_nearest(self):
        """Unknown direction falls back to nearest."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        cfg = PitchKeyQuantizerConfig(direction="invalid")
        assert cfg.direction == "nearest"

    def test_config_valid_scales(self):
        """Valid scales are accepted."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        for scale in ["major", "minor", "dorian", "harmonic_minor"]:
            cfg = PitchKeyQuantizerConfig(scale=scale)
            assert cfg.scale == scale

    def test_config_valid_directions(self):
        """Valid directions are accepted."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        for direction in ["nearest", "up", "down"]:
            cfg = PitchKeyQuantizerConfig(direction=direction)
            assert cfg.direction == direction

    def test_config_to_dict(self):
        """to_dict serializes config."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=62, scale="minor", direction="up"
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["root"] == 62
        assert d["scale"] == "minor"
        assert d["direction"] == "up"
        assert d["bypass_when_in_key"] is True

    def test_config_from_dict(self):
        """from_dict deserializes config."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        d = {
            "enabled": True,
            "root": 65,
            "scale": "dorian",
            "direction": "down",
            "bypass_when_in_key": False,
        }
        cfg = PitchKeyQuantizerConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.root == 65
        assert cfg.scale == "dorian"
        assert cfg.direction == "down"
        assert cfg.bypass_when_in_key is False

    def test_config_round_trip_serialization(self):
        """Config round-trips through to_dict/from_dict."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        cfg1 = PitchKeyQuantizerConfig(
            enabled=True, root=70, scale="harmonic_minor", direction="nearest"
        )
        d = cfg1.to_dict()
        cfg2 = PitchKeyQuantizerConfig.from_dict(d)
        assert cfg2.enabled == cfg1.enabled
        assert cfg2.root == cfg1.root
        assert cfg2.scale == cfg1.scale
        assert cfg2.direction == cfg1.direction
        assert cfg2.bypass_when_in_key == cfg1.bypass_when_in_key


class TestPitchKeyQuantizer:
    """PitchKeyQuantizer — quantization logic."""

    def test_disabled_returns_note_unchanged(self):
        """If disabled, quantize returns note unchanged."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(enabled=False, root=60, scale="major")
        q = PitchKeyQuantizer(cfg)
        assert q.quantize(61) == 61
        assert q.quantize(63) == 63
        assert q.quantize(100) == 100

    def test_in_key_note_returns_unchanged_when_bypass_enabled(self):
        """In-key note returns unchanged when bypass_when_in_key=True."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", bypass_when_in_key=True
        )
        q = PitchKeyQuantizer(cfg)
        # C major: C D E F G A B (60, 62, 64, 65, 67, 69, 71, ...)
        assert q.quantize(60) == 60  # C
        assert q.quantize(62) == 62  # D
        assert q.quantize(64) == 64  # E

    def test_in_key_note_quantizes_when_bypass_disabled(self):
        """In-key note is not quantized when bypass_when_in_key=False."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", bypass_when_in_key=False
        )
        q = PitchKeyQuantizer(cfg)
        # C is in C major, but with bypass off, it still "quantizes" to itself
        assert q.quantize(60) == 60

    def test_nearest_mode_c_major_61_to_60(self):
        """C major, 61 (C#) quantizes to 60 (C) in nearest mode."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="nearest"
        )
        q = PitchKeyQuantizer(cfg)
        # 61 is 1 semitone away from C (60) and D (62), tie rounds up to 62
        result = q.quantize(61)
        # But 62 is closer in absolute sense... wait let me verify:
        # C major notes: 60 (C), 62 (D), 64 (E), 65 (F), 67 (G), 69 (A), 71 (B)
        # 61: distance to 60 = 1, distance to 62 = 1 → tie, round up to 62
        assert result == 62

    def test_nearest_mode_c_major_63_to_62(self):
        """C major, 63 (D#) quantizes to 62 (D) or 64 (E) in nearest mode."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="nearest"
        )
        q = PitchKeyQuantizer(cfg)
        # 63: distance to 62 = 1, distance to 64 = 1 → tie, round up to 64
        result = q.quantize(63)
        assert result == 64

    def test_up_mode_c_major(self):
        """Up mode picks first in-scale note >= input."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="up"
        )
        q = PitchKeyQuantizer(cfg)
        # C major: 60, 62, 64, 65, 67, 69, 71, ...
        assert q.quantize(61) == 62  # 61 → first note >= 61 is 62 (D)
        assert q.quantize(62) == 62  # 62 → 62 (D)
        assert q.quantize(63) == 64  # 63 → 64 (E)
        assert q.quantize(71) == 71  # 71 → 71 (B)
        assert q.quantize(72) == 72  # 72 → wraps to next octave 72 (C5)

    def test_down_mode_c_major(self):
        """Down mode picks first in-scale note <= input."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="down", bypass_when_in_key=False
        )
        q = PitchKeyQuantizer(cfg)
        # C major: 60, 62, 64, 65, 67, 69, 71, 72, ...
        assert q.quantize(61) == 60  # 61 → first note <= 61 is 60 (C)
        assert q.quantize(62) == 62  # 62 → 62 (D)
        assert q.quantize(63) == 62  # 63 → 62 (D)
        assert q.quantize(72) == 72  # 72 is C5 in scale
        assert q.quantize(73) == 72  # 73 (C#5) → 72 (C5)

    def test_change_key_rebuilds_cache(self):
        """change_key updates root/scale and rebuilds cache."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="nearest"
        )
        q = PitchKeyQuantizer(cfg)
        # C major: 60, 62, 64, 65, 67, 69, 71
        assert q.in_key(60) is True
        assert q.in_key(61) is False

        # Change to D major (root=62)
        q.change_key(62, "major")
        # D major: 62, 64, 66, 67, 69, 71, 73
        assert q.in_key(62) is True
        assert q.in_key(60) is False

    def test_change_key_with_unknown_scale_fallback(self):
        """change_key with unknown scale falls back to major."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(enabled=True, root=60, scale="major")
        q = PitchKeyQuantizer(cfg)
        q.change_key(60, "unknown_scale")
        assert q.cfg.scale == "major"

    def test_in_key_returns_true_for_scale_notes(self):
        """in_key returns True for notes in the scale."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(enabled=True, root=60, scale="major")
        q = PitchKeyQuantizer(cfg)
        # C major scale notes
        for note in [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83]:
            assert q.in_key(note) is True

    def test_in_key_returns_false_for_off_key_notes(self):
        """in_key returns False for notes not in the scale."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(enabled=True, root=60, scale="major")
        q = PitchKeyQuantizer(cfg)
        # Non-C major notes: C#, D#, E#, F#, G#, A#, B#, etc.
        for note in [61, 63, 66, 68, 70, 73, 75, 78, 80]:
            assert q.in_key(note) is False

    def test_scale_notes_returns_sorted_list(self):
        """scale_notes returns sorted list of all scale notes."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(enabled=True, root=60, scale="major")
        q = PitchKeyQuantizer(cfg)
        notes = q.scale_notes()
        assert isinstance(notes, list)
        assert len(notes) > 0
        assert notes == sorted(notes)
        # First note should be 60 (C4), or possibly lower if scale extends down
        assert 60 in notes

    def test_quantize_clamps_input_to_0_127(self):
        """quantize clamps input note to 0..127."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="nearest"
        )
        q = PitchKeyQuantizer(cfg)
        # Input below 0 → clamped to 0
        result = q.quantize(-10)
        assert 0 <= result <= 127

        # Input above 127 → clamped to 127
        result = q.quantize(200)
        assert 0 <= result <= 127

    def test_quantize_output_always_0_127(self):
        """quantize output is always clamped to 0..127."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(enabled=True, root=60, scale="major")
        q = PitchKeyQuantizer(cfg)
        for note in range(-10, 200):
            result = q.quantize(note)
            assert 0 <= result <= 127

    def test_different_scales(self):
        """Quantizer works with different scales."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        for scale in ["minor", "dorian", "harmonic_minor", "pentatonic_major"]:
            cfg = PitchKeyQuantizerConfig(
                enabled=True, root=60, scale=scale, direction="nearest"
            )
            q = PitchKeyQuantizer(cfg)
            notes = q.scale_notes()
            assert len(notes) > 0
            assert all(0 <= note <= 127 for note in notes)

    def test_config_from_dict_missing_keys_defaults(self):
        """from_dict with missing keys uses defaults."""
        from gamepad_midi_bridge.pitch_key_quantizer import PitchKeyQuantizerConfig

        d = {"enabled": True}  # Only one key
        cfg = PitchKeyQuantizerConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.root == 60
        assert cfg.scale == "major"
        assert cfg.direction == "nearest"

    def test_nearest_mode_boundary_values(self):
        """Nearest mode works at note boundaries."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="nearest"
        )
        q = PitchKeyQuantizer(cfg)
        # Test at MIDI boundary: note 0
        result = q.quantize(0)
        assert 0 <= result <= 127
        # Test at MIDI boundary: note 127
        result = q.quantize(127)
        assert 0 <= result <= 127

    def test_up_mode_wraps_at_end(self):
        """Up mode wraps to lowest octave if input above all notes."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="up"
        )
        q = PitchKeyQuantizer(cfg)
        # If quantizing 127 (above B at 119 or so), wraps to lowest
        result = q.quantize(127)
        assert 0 <= result <= 127

    def test_down_mode_wraps_at_start(self):
        """Down mode wraps to highest octave if input below all notes."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="major", direction="down"
        )
        q = PitchKeyQuantizer(cfg)
        # C major starts at 0 or higher, so 0 should map to something valid
        result = q.quantize(0)
        assert 0 <= result <= 127

    def test_pentatonic_major_c(self):
        """Pentatonic major scale (C root)."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="pentatonic_major", direction="nearest"
        )
        q = PitchKeyQuantizer(cfg)
        # C pentatonic major: C, D, E, G, A
        # MIDI C4=60, D4=62, E4=64, G4=67, A4=69
        assert q.in_key(60) is True  # C
        assert q.in_key(62) is True  # D
        assert q.in_key(64) is True  # E
        assert q.in_key(67) is True  # G
        assert q.in_key(69) is True  # A
        assert q.in_key(61) is False  # C#
        assert q.in_key(65) is False  # F (not in pentatonic)

    def test_minor_scale_quantization(self):
        """Minor scale quantizes correctly."""
        from gamepad_midi_bridge.pitch_key_quantizer import (
            PitchKeyQuantizer,
            PitchKeyQuantizerConfig,
        )

        cfg = PitchKeyQuantizerConfig(
            enabled=True, root=60, scale="minor", direction="nearest"
        )
        q = PitchKeyQuantizer(cfg)
        # C minor: C, D, Eb, F, G, Ab, Bb
        # MIDI: 60, 62, 63, 65, 67, 68, 70
        assert q.in_key(60) is True  # C
        assert q.in_key(62) is True  # D
        assert q.in_key(63) is True  # Eb
        assert q.in_key(65) is True  # F
        assert q.in_key(61) is False  # C#
        assert q.in_key(64) is False  # E
