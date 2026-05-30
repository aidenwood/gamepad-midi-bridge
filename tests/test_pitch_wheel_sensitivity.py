"""Tests for pitch_wheel_sensitivity module — per-channel RPN 0,0 config.

Stores pitch bend range per MIDI channel, builds RPN messages,
serialization round-trip, and channel management.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import pitch_wheel_sensitivity as pws


# ─────────────────────────────────────────────────────────────────────
# PitchWheelChannelConfig — single channel config and validation
# ─────────────────────────────────────────────────────────────────────


def test_pitch_wheel_channel_config_default():
    """Default: channel=1, semitones=2, cents=0."""
    cfg = pws.PitchWheelChannelConfig()
    assert cfg.channel == 1
    assert cfg.semitones == 2
    assert cfg.cents == 0


def test_pitch_wheel_channel_config_explicit():
    """Explicit config construction."""
    cfg = pws.PitchWheelChannelConfig(channel=5, semitones=12, cents=50)
    assert cfg.channel == 5
    assert cfg.semitones == 12
    assert cfg.cents == 50


def test_pitch_wheel_channel_config_clamp_channel_low():
    """channel < 1 clamps to 1."""
    cfg = pws.PitchWheelChannelConfig(channel=0)
    assert cfg.channel == 1

    cfg = pws.PitchWheelChannelConfig(channel=-5)
    assert cfg.channel == 1


def test_pitch_wheel_channel_config_clamp_channel_high():
    """channel > 16 clamps to 16."""
    cfg = pws.PitchWheelChannelConfig(channel=20)
    assert cfg.channel == 16

    cfg = pws.PitchWheelChannelConfig(channel=100)
    assert cfg.channel == 16


def test_pitch_wheel_channel_config_clamp_semitones_low():
    """semitones < 0 clamps to 0."""
    cfg = pws.PitchWheelChannelConfig(semitones=-10)
    assert cfg.semitones == 0


def test_pitch_wheel_channel_config_clamp_semitones_high():
    """semitones > 96 clamps to 96."""
    cfg = pws.PitchWheelChannelConfig(semitones=200)
    assert cfg.semitones == 96


def test_pitch_wheel_channel_config_clamp_cents_low():
    """cents < 0 clamps to 0."""
    cfg = pws.PitchWheelChannelConfig(cents=-5)
    assert cfg.cents == 0


def test_pitch_wheel_channel_config_clamp_cents_high():
    """cents > 99 clamps to 99."""
    cfg = pws.PitchWheelChannelConfig(cents=150)
    assert cfg.cents == 99


def test_pitch_wheel_channel_config_to_dict():
    """to_dict round-trips all fields."""
    cfg = pws.PitchWheelChannelConfig(channel=7, semitones=24, cents=50)
    d = cfg.to_dict()
    assert d == {"channel": 7, "semitones": 24, "cents": 50}


def test_pitch_wheel_channel_config_from_dict():
    """from_dict reconstructs config, clamping applies."""
    d = {"channel": 3, "semitones": 48, "cents": 25}
    cfg = pws.PitchWheelChannelConfig.from_dict(d)
    assert cfg.channel == 3
    assert cfg.semitones == 48
    assert cfg.cents == 25


def test_pitch_wheel_channel_config_from_dict_clamps():
    """from_dict clamps out-of-range values."""
    d = {"channel": 99, "semitones": -10, "cents": 999}
    cfg = pws.PitchWheelChannelConfig.from_dict(d)
    assert cfg.channel == 16
    assert cfg.semitones == 0
    assert cfg.cents == 99


def test_pitch_wheel_channel_config_round_trip():
    """Serialize and deserialize preserves all valid values."""
    original = pws.PitchWheelChannelConfig(
        channel=10, semitones=48, cents=75
    )
    d = original.to_dict()
    restored = pws.PitchWheelChannelConfig.from_dict(d)
    assert restored.channel == original.channel
    assert restored.semitones == original.semitones
    assert restored.cents == original.cents


# ─────────────────────────────────────────────────────────────────────
# PitchWheelSensitivityConfig — container config
# ─────────────────────────────────────────────────────────────────────


def test_pitch_wheel_sensitivity_config_default():
    """Default: enabled=False, channels=[], send_on_load=True."""
    cfg = pws.PitchWheelSensitivityConfig()
    assert cfg.enabled is False
    assert cfg.channels == []
    assert cfg.send_on_load is True


def test_pitch_wheel_sensitivity_config_explicit():
    """Explicit config construction with channels."""
    ch1 = pws.PitchWheelChannelConfig(channel=1, semitones=12)
    ch2 = pws.PitchWheelChannelConfig(channel=5, semitones=48)
    cfg = pws.PitchWheelSensitivityConfig(
        enabled=True, channels=[ch1, ch2], send_on_load=False
    )
    assert cfg.enabled is True
    assert len(cfg.channels) == 2
    assert cfg.send_on_load is False


def test_pitch_wheel_sensitivity_config_to_dict():
    """to_dict includes nested channels."""
    ch1 = pws.PitchWheelChannelConfig(channel=1, semitones=12, cents=0)
    ch2 = pws.PitchWheelChannelConfig(channel=5, semitones=24, cents=50)
    cfg = pws.PitchWheelSensitivityConfig(
        enabled=True, channels=[ch1, ch2], send_on_load=False
    )
    d = cfg.to_dict()
    assert d == {
        "enabled": True,
        "channels": [
            {"channel": 1, "semitones": 12, "cents": 0},
            {"channel": 5, "semitones": 24, "cents": 50},
        ],
        "send_on_load": False,
    }


def test_pitch_wheel_sensitivity_config_from_dict():
    """from_dict reconstructs config with nested channels."""
    d = {
        "enabled": True,
        "channels": [
            {"channel": 3, "semitones": 12, "cents": 0},
            {"channel": 7, "semitones": 48, "cents": 75},
        ],
        "send_on_load": False,
    }
    cfg = pws.PitchWheelSensitivityConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.send_on_load is False
    assert len(cfg.channels) == 2
    assert cfg.channels[0].channel == 3
    assert cfg.channels[0].semitones == 12
    assert cfg.channels[1].channel == 7
    assert cfg.channels[1].cents == 75


def test_pitch_wheel_sensitivity_config_round_trip():
    """Serialize and deserialize preserves all valid values."""
    ch1 = pws.PitchWheelChannelConfig(channel=1, semitones=2, cents=0)
    ch2 = pws.PitchWheelChannelConfig(channel=16, semitones=96, cents=99)
    original = pws.PitchWheelSensitivityConfig(
        enabled=True, channels=[ch1, ch2], send_on_load=True
    )
    d = original.to_dict()
    restored = pws.PitchWheelSensitivityConfig.from_dict(d)
    assert restored.enabled == original.enabled
    assert restored.send_on_load == original.send_on_load
    assert len(restored.channels) == 2
    assert restored.channels[0].channel == 1
    assert restored.channels[1].semitones == 96


# ─────────────────────────────────────────────────────────────────────
# PitchWheelSensitivity — manager for channel operations
# ─────────────────────────────────────────────────────────────────────


def test_pitch_wheel_sensitivity_init():
    """Initialize with config."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    assert manager.all_channels() == []


def test_pitch_wheel_sensitivity_set_channel_add():
    """set_channel adds a new entry."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    manager.set_channel(1, 12, 0)
    ch = manager.get_channel(1)
    assert ch is not None
    assert ch.channel == 1
    assert ch.semitones == 12
    assert ch.cents == 0


def test_pitch_wheel_sensitivity_set_channel_duplicate_updates():
    """set_channel updates existing entry."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    manager.set_channel(1, 12, 0)
    manager.set_channel(1, 24, 50)

    ch = manager.get_channel(1)
    assert ch is not None
    assert ch.semitones == 24
    assert ch.cents == 50
    # Verify only one entry
    assert len(manager.all_channels()) == 1


def test_pitch_wheel_sensitivity_set_channel_clamps():
    """set_channel clamps inputs."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    manager.set_channel(99, -5, 999)
    ch = manager.get_channel(16)
    assert ch is not None
    assert ch.channel == 16
    assert ch.semitones == 0
    assert ch.cents == 99


def test_pitch_wheel_sensitivity_get_channel_found():
    """get_channel returns config if found."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(5, 12)

    ch = manager.get_channel(5)
    assert ch is not None
    assert ch.semitones == 12


def test_pitch_wheel_sensitivity_get_channel_not_found():
    """get_channel returns None if not found."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    ch = manager.get_channel(5)
    assert ch is None


def test_pitch_wheel_sensitivity_remove_channel_success():
    """remove_channel deletes entry and returns True."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(5, 12)

    result = manager.remove_channel(5)
    assert result is True
    assert manager.get_channel(5) is None


def test_pitch_wheel_sensitivity_remove_channel_not_found():
    """remove_channel returns False if channel not found."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    result = manager.remove_channel(5)
    assert result is False


def test_pitch_wheel_sensitivity_all_channels_empty():
    """all_channels returns empty list when no entries."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    channels = manager.all_channels()
    assert channels == []


def test_pitch_wheel_sensitivity_all_channels_multiple():
    """all_channels returns copy of all entries."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(1, 12, 0)
    manager.set_channel(5, 24, 50)
    manager.set_channel(16, 96, 99)

    channels = manager.all_channels()
    assert len(channels) == 3
    assert channels[0].channel == 1
    assert channels[1].channel == 5
    assert channels[2].channel == 16


def test_pitch_wheel_sensitivity_all_channels_is_copy():
    """all_channels returns a copy, not a reference."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(1, 12)

    channels1 = manager.all_channels()
    channels2 = manager.all_channels()
    assert channels1 is not channels2
    assert channels1[0] is not channels2[0]


def test_pitch_wheel_sensitivity_rpn_messages_for_found():
    """rpn_messages_for builds 6 messages for configured channel."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(1, 12, 0)

    msgs = manager.rpn_messages_for(1)
    assert len(msgs) == 6
    # First msg: CC 101 = 0 on channel 1 (status 0xB0)
    assert msgs[0] == [0xB0, 0x65, 0x00]
    # Second msg: CC 100 = 0
    assert msgs[1] == [0xB0, 0x64, 0x00]
    # Third msg: CC 6 = semitones
    assert msgs[2] == [0xB0, 0x06, 12]
    # Fourth msg: CC 38 = cents
    assert msgs[3] == [0xB0, 0x26, 0]
    # Fifth msg: CC 101 = 127
    assert msgs[4] == [0xB0, 0x65, 0x7F]
    # Sixth msg: CC 100 = 127
    assert msgs[5] == [0xB0, 0x64, 0x7F]


def test_pitch_wheel_sensitivity_rpn_messages_for_not_found():
    """rpn_messages_for returns empty list if channel not configured."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    msgs = manager.rpn_messages_for(1)
    assert msgs == []


def test_pitch_wheel_sensitivity_rpn_messages_for_different_channels():
    """rpn_messages_for uses correct status byte per channel."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(5, 24, 50)
    manager.set_channel(16, 96, 99)

    msgs5 = manager.rpn_messages_for(5)
    msgs16 = manager.rpn_messages_for(16)

    # Channel 5: status = 0xB0 | 4 = 0xB4
    assert msgs5[0][0] == 0xB4
    assert msgs5[2] == [0xB4, 0x06, 24]
    assert msgs5[3] == [0xB4, 0x26, 50]

    # Channel 16: status = 0xB0 | 15 = 0xBF
    assert msgs16[0][0] == 0xBF
    assert msgs16[2] == [0xBF, 0x06, 96]
    assert msgs16[3] == [0xBF, 0x26, 99]


def test_pitch_wheel_sensitivity_all_rpn_messages_empty():
    """all_rpn_messages returns empty list when no channels."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)

    msgs = manager.all_rpn_messages()
    assert msgs == []


def test_pitch_wheel_sensitivity_all_rpn_messages_concatenates():
    """all_rpn_messages concatenates messages from all channels."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(1, 12, 0)
    manager.set_channel(5, 24, 50)

    msgs = manager.all_rpn_messages()
    # 2 channels * 6 messages each
    assert len(msgs) == 12

    # First 6 for channel 1
    assert msgs[0] == [0xB0, 0x65, 0x00]
    assert msgs[2] == [0xB0, 0x06, 12]

    # Next 6 for channel 5
    assert msgs[6] == [0xB4, 0x65, 0x00]
    assert msgs[8] == [0xB4, 0x06, 24]


def test_pitch_wheel_sensitivity_clear():
    """clear removes all channel configs."""
    cfg = pws.PitchWheelSensitivityConfig()
    manager = pws.PitchWheelSensitivity(cfg)
    manager.set_channel(1, 12)
    manager.set_channel(5, 24)
    manager.set_channel(16, 96)

    manager.clear()

    assert manager.all_channels() == []
    assert manager.get_channel(1) is None
    assert manager.get_channel(5) is None
    assert manager.get_channel(16) is None


def test_pitch_wheel_sensitivity_integration_workflow():
    """Realistic workflow: configure, generate, serialize."""
    cfg = pws.PitchWheelSensitivityConfig(enabled=True)
    manager = pws.PitchWheelSensitivity(cfg)

    # Configure three channels
    manager.set_channel(1, 2, 0)
    manager.set_channel(5, 12, 0)
    manager.set_channel(16, 96, 0)

    # Verify all are present
    all_ch = manager.all_channels()
    assert len(all_ch) == 3

    # Generate all messages
    all_msgs = manager.all_rpn_messages()
    assert len(all_msgs) == 18  # 3 channels * 6 msgs

    # Serialize
    d = cfg.to_dict()
    assert d["enabled"] is True
    assert len(d["channels"]) == 3

    # Deserialize and verify
    cfg2 = pws.PitchWheelSensitivityConfig.from_dict(d)
    manager2 = pws.PitchWheelSensitivity(cfg2)
    all_msgs2 = manager2.all_rpn_messages()
    assert all_msgs == all_msgs2
