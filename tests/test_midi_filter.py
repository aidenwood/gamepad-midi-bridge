"""
Tests for MIDI filtering and transformation module.
"""

import pytest
from gamepad_midi_bridge.midi_filter import (
    MidiFilterConfig,
    filter_message,
)


class TestMessageTypeBlocking:
    """Test blocking of specific MIDI message types."""

    def test_block_note_on(self):
        """Note on (0x90) should be blocked when block_note_on=True."""
        cfg = MidiFilterConfig(block_note_on=True)
        msg = [0x90, 60, 100]  # Note on, middle C, velocity 100
        assert filter_message(msg, cfg) is None

    def test_block_note_off(self):
        """Note off (0x80) should be blocked when block_note_off=True."""
        cfg = MidiFilterConfig(block_note_off=True)
        msg = [0x80, 60, 0]  # Note off, middle C
        assert filter_message(msg, cfg) is None

    def test_block_cc(self):
        """Control change (0xB0) should be blocked when block_cc=True."""
        cfg = MidiFilterConfig(block_cc=True)
        msg = [0xB0, 1, 64]  # CC1, value 64
        assert filter_message(msg, cfg) is None

    def test_block_pitch_bend(self):
        """Pitch bend (0xE0) should be blocked when block_pitch_bend=True."""
        cfg = MidiFilterConfig(block_pitch_bend=True)
        msg = [0xE0, 0, 64]  # Pitch bend, center
        assert filter_message(msg, cfg) is None

    def test_block_program_change(self):
        """Program change (0xC0) should be blocked when block_program_change=True."""
        cfg = MidiFilterConfig(block_program_change=True)
        msg = [0xC0, 5]  # Program change, program 5
        assert filter_message(msg, cfg) is None

    def test_block_aftertouch(self):
        """Aftertouch (poly and channel) should be blocked when block_aftertouch=True."""
        cfg = MidiFilterConfig(block_aftertouch=True)
        # Poly aftertouch
        msg_poly = [0xA0, 60, 100]
        assert filter_message(msg_poly, cfg) is None
        # Channel aftertouch
        msg_chan = [0xD0, 100]
        assert filter_message(msg_chan, cfg) is None

    def test_block_clock(self):
        """Timing clock and start/stop/continue should be blocked when block_clock=True."""
        cfg = MidiFilterConfig(block_clock=True)
        assert filter_message([0xF8], cfg) is None  # Timing clock
        assert filter_message([0xFA], cfg) is None  # Start
        assert filter_message([0xFB], cfg) is None  # Continue
        assert filter_message([0xFC], cfg) is None  # Stop

    def test_block_sysex(self):
        """Sysex (0xF0) should be blocked when block_sysex=True."""
        cfg = MidiFilterConfig(block_sysex=True)
        msg = [0xF0, 0x7E, 0x00, 0x09, 0x01, 0xF7]  # Sysex with end
        assert filter_message(msg, cfg) is None


class TestChannelFiltering:
    """Test MIDI channel filtering."""

    def test_empty_allowed_channels_allows_all(self):
        """Empty allowed_channels should allow all channels."""
        cfg = MidiFilterConfig(allowed_channels=[])
        # Test channels 0-15 (channels 1-16 in human terms)
        for ch in range(16):
            msg = [0x90 | ch, 60, 100]  # Note on on channel ch
            assert filter_message(msg, cfg) == msg

    def test_allowed_channels_filters_correctly(self):
        """Only messages on allowed channels should pass."""
        cfg = MidiFilterConfig(allowed_channels=[1, 2])
        # Channel 1 (0x90) should pass
        msg_ch1 = [0x90, 60, 100]
        assert filter_message(msg_ch1, cfg) == msg_ch1
        # Channel 2 (0x91) should pass
        msg_ch2 = [0x91, 60, 100]
        assert filter_message(msg_ch2, cfg) == msg_ch2
        # Channel 3 (0x92) should be blocked
        msg_ch3 = [0x92, 60, 100]
        assert filter_message(msg_ch3, cfg) is None

    def test_allowed_channels_with_cc(self):
        """Channel filtering should work with CC messages."""
        cfg = MidiFilterConfig(allowed_channels=[1])
        # Channel 1 CC should pass
        msg_ch1 = [0xB0, 1, 64]
        assert filter_message(msg_ch1, cfg) == msg_ch1
        # Channel 2 CC should be blocked
        msg_ch2 = [0xB1, 1, 64]
        assert filter_message(msg_ch2, cfg) is None


class TestTransposition:
    """Test note transposition."""

    def test_transpose_positive(self):
        """Positive transposition should raise pitch."""
        cfg = MidiFilterConfig(transpose_semitones=12)
        msg = [0x90, 60, 100]  # Middle C
        result = filter_message(msg, cfg)
        assert result == [0x90, 72, 100]  # C5

    def test_transpose_negative(self):
        """Negative transposition should lower pitch."""
        cfg = MidiFilterConfig(transpose_semitones=-2)
        msg = [0x90, 60, 100]  # C4
        result = filter_message(msg, cfg)
        assert result == [0x90, 58, 100]  # Bb3

    def test_transpose_out_of_range_high(self):
        """Notes transposed above 127 should be blocked."""
        cfg = MidiFilterConfig(transpose_semitones=12)
        msg = [0x90, 120, 100]
        assert filter_message(msg, cfg) is None

    def test_transpose_out_of_range_low(self):
        """Notes transposed below 0 should be blocked."""
        cfg = MidiFilterConfig(transpose_semitones=-12)
        msg = [0x90, 5, 100]
        assert filter_message(msg, cfg) is None

    def test_transpose_applies_to_note_off(self):
        """Transposition should apply to note off messages too."""
        cfg = MidiFilterConfig(transpose_semitones=5)
        msg = [0x80, 60, 0]
        result = filter_message(msg, cfg)
        assert result == [0x80, 65, 0]

    def test_transpose_zero_passes_through(self):
        """Zero transposition should pass messages unchanged."""
        cfg = MidiFilterConfig(transpose_semitones=0)
        msg = [0x90, 60, 100]
        assert filter_message(msg, cfg) == msg


class TestVelocityScaling:
    """Test velocity scaling."""

    def test_velocity_scale_down(self):
        """Velocity should be scaled down by factor < 1.0."""
        cfg = MidiFilterConfig(velocity_scale=0.5)
        msg = [0x90, 60, 100]
        result = filter_message(msg, cfg)
        assert result == [0x90, 60, 50]

    def test_velocity_scale_up(self):
        """Velocity should be scaled up by factor > 1.0."""
        cfg = MidiFilterConfig(velocity_scale=2.0)
        msg = [0x90, 60, 100]
        result = filter_message(msg, cfg)
        assert result == [0x90, 60, 127]  # Clamped to 127

    def test_velocity_scale_clamped_min(self):
        """Scaled velocity should be clamped to minimum 1."""
        cfg = MidiFilterConfig(velocity_scale=0.001)
        msg = [0x90, 60, 100]
        result = filter_message(msg, cfg)
        assert result == [0x90, 60, 1]

    def test_velocity_scale_one_passes_through(self):
        """Velocity scale of 1.0 should not change velocity."""
        cfg = MidiFilterConfig(velocity_scale=1.0)
        msg = [0x90, 60, 100]
        assert filter_message(msg, cfg) == msg

    def test_velocity_scale_does_not_affect_note_off(self):
        """Velocity scaling should not apply to note off."""
        cfg = MidiFilterConfig(velocity_scale=0.5)
        msg = [0x80, 60, 0]
        assert filter_message(msg, cfg) == msg


class TestCCRemapping:
    """Test CC (control change) remapping."""

    def test_cc_remap_single(self):
        """CC number should be remapped according to cc_remap dict."""
        cfg = MidiFilterConfig(cc_remap={1: 7})
        msg = [0xB0, 1, 64]  # CC1 value 64
        result = filter_message(msg, cfg)
        assert result == [0xB0, 7, 64]  # Remapped to CC7

    def test_cc_remap_multiple(self):
        """Multiple CC remappings should work."""
        cfg = MidiFilterConfig(cc_remap={1: 7, 11: 1})
        msg1 = [0xB0, 1, 64]
        msg2 = [0xB0, 11, 100]
        assert filter_message(msg1, cfg) == [0xB0, 7, 64]
        assert filter_message(msg2, cfg) == [0xB0, 1, 100]

    def test_cc_remap_unmapped_cc_passes(self):
        """CCs not in remap dict should pass unchanged."""
        cfg = MidiFilterConfig(cc_remap={1: 7})
        msg = [0xB0, 10, 64]  # CC10, not in remap
        assert filter_message(msg, cfg) == msg

    def test_cc_remap_empty_passes_through(self):
        """Empty cc_remap should pass all CCs through."""
        cfg = MidiFilterConfig(cc_remap={})
        msg = [0xB0, 5, 64]
        assert filter_message(msg, cfg) == msg


class TestCombinedFilters:
    """Test combinations of filters."""

    def test_block_and_transpose_same_message(self):
        """Block should take precedence over transpose."""
        cfg = MidiFilterConfig(block_note_on=True, transpose_semitones=12)
        msg = [0x90, 60, 100]
        assert filter_message(msg, cfg) is None

    def test_channel_filter_before_transpose(self):
        """Channel filtering should happen before transposition."""
        cfg = MidiFilterConfig(allowed_channels=[1], transpose_semitones=12)
        # Channel 1 note should be transposed
        msg_ch1 = [0x90, 60, 100]
        result = filter_message(msg_ch1, cfg)
        assert result == [0x90, 72, 100]
        # Channel 2 note should be blocked before transposition
        msg_ch2 = [0x91, 60, 100]
        assert filter_message(msg_ch2, cfg) is None

    def test_cc_remap_with_channel_filter(self):
        """CC remapping should work with channel filtering."""
        cfg = MidiFilterConfig(allowed_channels=[1], cc_remap={1: 7})
        msg_ch1 = [0xB0, 1, 64]
        result = filter_message(msg_ch1, cfg)
        assert result == [0xB0, 7, 64]
        msg_ch2 = [0xB1, 1, 64]
        assert filter_message(msg_ch2, cfg) is None

    def test_velocity_scale_with_transpose(self):
        """Velocity scaling and transposition should both apply."""
        cfg = MidiFilterConfig(transpose_semitones=12, velocity_scale=0.5)
        msg = [0x90, 60, 100]
        result = filter_message(msg, cfg)
        assert result == [0x90, 72, 50]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_message(self):
        """Empty message should return None."""
        cfg = MidiFilterConfig()
        assert filter_message([], cfg) is None

    def test_single_byte_message(self):
        """Single-byte system messages should pass through."""
        cfg = MidiFilterConfig()
        msg = [0xF8]  # Timing clock
        assert filter_message(msg, cfg) == msg

    def test_incomplete_note_on(self):
        """Note on with missing velocity should still work."""
        cfg = MidiFilterConfig()
        msg = [0x90, 60]  # Missing velocity
        # Should pass through as-is since we can't safely modify
        assert filter_message(msg, cfg) == msg

    def test_multiple_system_messages(self):
        """Various system messages should pass through when not blocked."""
        cfg = MidiFilterConfig()
        assert filter_message([0xF1], cfg) == [0xF1]  # Quarter frame
        assert filter_message([0xF2, 0, 0], cfg) == [0xF2, 0, 0]  # Song position
        assert filter_message([0xF3, 0], cfg) == [0xF3, 0]  # Song select


class TestDefaultConfig:
    """Test default configuration behavior."""

    def test_default_config_passes_everything(self):
        """Default config should pass all messages unchanged."""
        cfg = MidiFilterConfig()
        test_messages = [
            [0x90, 60, 100],  # Note on
            [0x80, 60, 0],    # Note off
            [0xB0, 1, 64],    # CC
            [0xE0, 0, 64],    # Pitch bend
            [0xC0, 5],        # Program change
            [0xF8],           # Timing clock
        ]
        for msg in test_messages:
            assert filter_message(msg, cfg) == msg


class TestSerialization:
    """Test config serialization and deserialization."""

    def test_to_dict(self):
        """Config should serialize to dict."""
        cfg = MidiFilterConfig(
            block_note_on=True,
            transpose_semitones=12,
            allowed_channels=[1, 2],
            cc_remap={1: 7},
            velocity_scale=0.5,
        )
        d = cfg.to_dict()
        assert d["block_note_on"] is True
        assert d["transpose_semitones"] == 12
        assert d["allowed_channels"] == [1, 2]
        assert d["cc_remap"] == {1: 7}
        assert d["velocity_scale"] == 0.5

    def test_from_dict(self):
        """Config should deserialize from dict."""
        d = {
            "block_note_on": True,
            "transpose_semitones": 12,
            "allowed_channels": [1, 2],
            "cc_remap": {1: 7},
            "velocity_scale": 0.5,
        }
        cfg = MidiFilterConfig.from_dict(d)
        assert cfg.block_note_on is True
        assert cfg.transpose_semitones == 12
        assert cfg.allowed_channels == [1, 2]
        assert cfg.cc_remap == {1: 7}
        assert cfg.velocity_scale == 0.5

    def test_round_trip(self):
        """Config should survive round-trip serialization."""
        original = MidiFilterConfig(
            block_cc=True,
            transpose_semitones=-5,
            allowed_channels=[3, 4, 5],
            cc_remap={7: 1, 11: 7},
            velocity_scale=1.5,
        )
        d = original.to_dict()
        restored = MidiFilterConfig.from_dict(d)
        assert restored.block_cc == original.block_cc
        assert restored.transpose_semitones == original.transpose_semitones
        assert restored.allowed_channels == original.allowed_channels
        assert restored.cc_remap == original.cc_remap
        assert restored.velocity_scale == original.velocity_scale

    def test_from_dict_with_missing_keys(self):
        """from_dict should handle missing keys gracefully."""
        d = {"block_note_on": True}  # Missing most keys
        cfg = MidiFilterConfig.from_dict(d)
        assert cfg.block_note_on is True
        assert cfg.transpose_semitones == 0  # Default
        assert cfg.allowed_channels == []  # Default
        assert cfg.velocity_scale == 1.0  # Default
