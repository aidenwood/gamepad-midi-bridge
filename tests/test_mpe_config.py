"""Tests for mpe_config module — MPE channel allocator and configuration.

MPE (MIDI Polyphonic Expression) zone setup, channel allocation, and MCM messages.
All operations are stateful (allocator) or pure functions (config, channels, MCM).
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import mpe_config as mpe


# ─────────────────────────────────────────────────────────────────────
# MpeConfig — dataclass construction and validation
# ─────────────────────────────────────────────────────────────────────


def test_mpe_config_default():
    """Default config: enabled=False, zone='lower', 15 members, 48 pb range."""
    cfg = mpe.MpeConfig()
    assert cfg.enabled is False
    assert cfg.zone == "lower"
    assert cfg.member_channel_count == 15
    assert cfg.pitch_bend_range_semitones == 48
    assert cfg.enable_y_axis is True
    assert cfg.enable_z_axis is True


def test_mpe_config_explicit():
    """Explicit config construction."""
    cfg = mpe.MpeConfig(
        enabled=True,
        zone="upper",
        member_channel_count=10,
        pitch_bend_range_semitones=96,
        enable_y_axis=False,
    )
    assert cfg.enabled is True
    assert cfg.zone == "upper"
    assert cfg.member_channel_count == 10
    assert cfg.pitch_bend_range_semitones == 96
    assert cfg.enable_y_axis is False


def test_mpe_config_clamp_member_channel_count_low():
    """member_channel_count < 1 clamps to 1."""
    cfg = mpe.MpeConfig(member_channel_count=0)
    assert cfg.member_channel_count == 1

    cfg = mpe.MpeConfig(member_channel_count=-5)
    assert cfg.member_channel_count == 1


def test_mpe_config_clamp_member_channel_count_high():
    """member_channel_count > 15 clamps to 15."""
    cfg = mpe.MpeConfig(member_channel_count=20)
    assert cfg.member_channel_count == 15

    cfg = mpe.MpeConfig(member_channel_count=100)
    assert cfg.member_channel_count == 15


def test_mpe_config_clamp_pitch_bend_range_low():
    """pitch_bend_range_semitones < 0 clamps to 0."""
    cfg = mpe.MpeConfig(pitch_bend_range_semitones=-10)
    assert cfg.pitch_bend_range_semitones == 0


def test_mpe_config_clamp_pitch_bend_range_high():
    """pitch_bend_range_semitones > 96 clamps to 96."""
    cfg = mpe.MpeConfig(pitch_bend_range_semitones=200)
    assert cfg.pitch_bend_range_semitones == 96


def test_mpe_config_unknown_zone_defaults_to_lower():
    """Unknown zone string defaults to 'lower'."""
    cfg = mpe.MpeConfig(zone="invalid")
    assert cfg.zone == "lower"

    cfg = mpe.MpeConfig(zone="")
    assert cfg.zone == "lower"


# ─────────────────────────────────────────────────────────────────────
# Serialization: to_dict / from_dict
# ─────────────────────────────────────────────────────────────────────


def test_mpe_config_to_dict():
    """to_dict round-trips all fields."""
    cfg = mpe.MpeConfig(
        enabled=True,
        zone="upper",
        member_channel_count=8,
        pitch_bend_range_semitones=72,
        enable_y_axis=False,
        enable_z_axis=True,
    )
    d = cfg.to_dict()
    assert d == {
        "enabled": True,
        "zone": "upper",
        "member_channel_count": 8,
        "pitch_bend_range_semitones": 72,
        "enable_y_axis": False,
        "enable_z_axis": True,
    }


def test_mpe_config_from_dict():
    """from_dict reconstructs config, clamping applies."""
    d = {
        "enabled": True,
        "zone": "lower",
        "member_channel_count": 3,
        "pitch_bend_range_semitones": 48,
        "enable_y_axis": True,
        "enable_z_axis": False,
    }
    cfg = mpe.MpeConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.zone == "lower"
    assert cfg.member_channel_count == 3
    assert cfg.pitch_bend_range_semitones == 48
    assert cfg.enable_y_axis is True
    assert cfg.enable_z_axis is False


def test_mpe_config_from_dict_clamps():
    """from_dict clamps out-of-range values."""
    d = {
        "enabled": True,
        "zone": "invalid",
        "member_channel_count": 999,
        "pitch_bend_range_semitones": -50,
    }
    cfg = mpe.MpeConfig.from_dict(d)
    assert cfg.zone == "lower"
    assert cfg.member_channel_count == 15
    assert cfg.pitch_bend_range_semitones == 0


def test_mpe_config_round_trip():
    """Serialize and deserialize preserves all valid values."""
    original = mpe.MpeConfig(
        enabled=True,
        zone="upper",
        member_channel_count=7,
        pitch_bend_range_semitones=60,
        enable_y_axis=False,
    )
    d = original.to_dict()
    restored = mpe.MpeConfig.from_dict(d)
    assert restored.enabled == original.enabled
    assert restored.zone == original.zone
    assert restored.member_channel_count == original.member_channel_count
    assert restored.pitch_bend_range_semitones == original.pitch_bend_range_semitones
    assert restored.enable_y_axis == original.enable_y_axis
    assert restored.enable_z_axis == original.enable_z_axis


# ─────────────────────────────────────────────────────────────────────
# master_channel(cfg) — returns 1 for lower, 16 for upper
# ─────────────────────────────────────────────────────────────────────


def test_master_channel_lower():
    """Lower zone master is channel 1."""
    cfg = mpe.MpeConfig(zone="lower")
    assert mpe.master_channel(cfg) == 1


def test_master_channel_upper():
    """Upper zone master is channel 16."""
    cfg = mpe.MpeConfig(zone="upper")
    assert mpe.master_channel(cfg) == 16


def test_master_channel_invalid_defaults_to_lower():
    """Invalid zone defaults to lower, so master is 1."""
    cfg = mpe.MpeConfig(zone="invalid")
    assert mpe.master_channel(cfg) == 1


# ─────────────────────────────────────────────────────────────────────
# member_channels(cfg) — returns list of member channels
# ─────────────────────────────────────────────────────────────────────


def test_member_channels_lower_3():
    """Lower zone with 3 members: [2, 3, 4]."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    assert mpe.member_channels(cfg) == [2, 3, 4]


def test_member_channels_lower_15():
    """Lower zone with 15 members: [2, 3, ..., 16]."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=15)
    channels = mpe.member_channels(cfg)
    assert channels == list(range(2, 17))
    assert len(channels) == 15


def test_member_channels_lower_1():
    """Lower zone with 1 member: [2]."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=1)
    assert mpe.member_channels(cfg) == [2]


def test_member_channels_upper_3():
    """Upper zone with 3 members: [15, 14, 13]."""
    cfg = mpe.MpeConfig(zone="upper", member_channel_count=3)
    assert mpe.member_channels(cfg) == [15, 14, 13]


def test_member_channels_upper_15():
    """Upper zone with 15 members: [15, 14, ..., 1]."""
    cfg = mpe.MpeConfig(zone="upper", member_channel_count=15)
    channels = mpe.member_channels(cfg)
    assert channels == list(range(15, 0, -1))
    assert len(channels) == 15


def test_member_channels_upper_1():
    """Upper zone with 1 member: [15]."""
    cfg = mpe.MpeConfig(zone="upper", member_channel_count=1)
    assert mpe.member_channels(cfg) == [15]


# ─────────────────────────────────────────────────────────────────────
# build_mcm_message(cfg) — builds RPN 6 MCM sequence
# ─────────────────────────────────────────────────────────────────────


def test_build_mcm_message_lower():
    """MCM message for lower zone (master ch1) with 3 members."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    msgs = mpe.build_mcm_message(cfg)

    assert len(msgs) == 5
    # All on channel 0 (0xB0 | 0 = 0xB0)
    assert msgs[0] == [0xB0, 101, 0]      # CC 101 = 0
    assert msgs[1] == [0xB0, 100, 6]      # CC 100 = 6 (MCM)
    assert msgs[2] == [0xB0, 6, 3]        # CC 6 = 3 (member count)
    assert msgs[3] == [0xB0, 101, 127]    # CC 101 = 127
    assert msgs[4] == [0xB0, 100, 127]    # CC 100 = 127


def test_build_mcm_message_upper():
    """MCM message for upper zone (master ch16) with 5 members."""
    cfg = mpe.MpeConfig(zone="upper", member_channel_count=5)
    msgs = mpe.build_mcm_message(cfg)

    assert len(msgs) == 5
    # All on channel 15 (0xB0 | 15 = 0xBF)
    assert msgs[0] == [0xBF, 101, 0]      # CC 101 = 0
    assert msgs[1] == [0xBF, 100, 6]      # CC 100 = 6
    assert msgs[2] == [0xBF, 6, 5]        # CC 6 = 5
    assert msgs[3] == [0xBF, 101, 127]    # CC 101 = 127
    assert msgs[4] == [0xBF, 100, 127]    # CC 100 = 127


def test_build_mcm_message_count_respects_clamped_value():
    """MCM member count reflects clamped value."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=999)  # Clamps to 15
    msgs = mpe.build_mcm_message(cfg)
    assert msgs[2][2] == 15  # Data Entry = 15


# ─────────────────────────────────────────────────────────────────────
# MpeAllocator — channel allocation state machine
# ─────────────────────────────────────────────────────────────────────


def test_allocator_init():
    """Allocator initializes with all channels free."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    assert alloc.holding(2) is None
    assert alloc.holding(3) is None
    assert alloc.holding(4) is None


def test_allocator_allocate_first_note():
    """First allocated note gets first member channel."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    ch = alloc.allocate(60)
    assert ch == 2
    assert alloc.holding(2) == 60


def test_allocator_allocate_second_note():
    """Second allocated note gets second member channel."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    ch1 = alloc.allocate(60)
    ch2 = alloc.allocate(64)
    assert ch1 == 2
    assert ch2 == 3
    assert alloc.holding(2) == 60
    assert alloc.holding(3) == 64


def test_allocator_allocate_same_note_twice_idempotent():
    """Allocating same note twice returns same channel, no double-allocation."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    ch1 = alloc.allocate(60)
    ch2 = alloc.allocate(60)
    assert ch1 == 2
    assert ch2 == 2
    assert alloc.holding(2) == 60


def test_allocator_allocate_when_full_returns_none():
    """Allocating when all channels busy returns None."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    ch1 = alloc.allocate(60)
    ch2 = alloc.allocate(64)
    ch3 = alloc.allocate(67)
    ch4 = alloc.allocate(72)

    assert ch1 == 2
    assert ch2 == 3
    assert ch3 == 4
    assert ch4 is None


def test_allocator_release_frees_channel():
    """Release returns the channel and marks it free."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    alloc.allocate(60)
    released = alloc.release(60)

    assert released == 2
    assert alloc.holding(2) is None


def test_allocator_release_enables_reuse():
    """Released channel can be reused for new note."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    alloc.allocate(60)
    alloc.release(60)
    new_ch = alloc.allocate(72)

    assert new_ch == 2
    assert alloc.holding(2) == 72


def test_allocator_release_nonexistent_returns_none():
    """Releasing a note not held returns None."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    result = alloc.release(60)
    assert result is None


def test_allocator_reset_clears_all():
    """Reset clears all allocations."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    alloc.allocate(60)
    alloc.allocate(64)
    alloc.allocate(67)

    alloc.reset()

    assert alloc.holding(2) is None
    assert alloc.holding(3) is None
    assert alloc.holding(4) is None


def test_allocator_complex_scenario():
    """Realistic allocation-release-reuse scenario."""
    cfg = mpe.MpeConfig(zone="lower", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    # Allocate 3 notes
    ch1 = alloc.allocate(60)
    ch2 = alloc.allocate(64)
    ch3 = alloc.allocate(67)
    assert [ch1, ch2, ch3] == [2, 3, 4]

    # Try to allocate 4th (no space)
    ch4 = alloc.allocate(72)
    assert ch4 is None

    # Release middle note
    alloc.release(64)
    assert alloc.holding(3) is None

    # Allocate new note gets freed channel
    ch5 = alloc.allocate(71)
    assert ch5 == 3

    # Release first and allocate new
    alloc.release(60)
    ch6 = alloc.allocate(59)
    assert ch6 == 2

    # Verify state
    assert alloc.holding(2) == 59
    assert alloc.holding(3) == 71
    assert alloc.holding(4) == 67


def test_allocator_upper_zone():
    """Allocator works with upper zone (master ch16, members 15..13)."""
    cfg = mpe.MpeConfig(zone="upper", member_channel_count=3)
    alloc = mpe.MpeAllocator(cfg)

    ch1 = alloc.allocate(60)
    ch2 = alloc.allocate(64)
    ch3 = alloc.allocate(67)

    assert ch1 == 15
    assert ch2 == 14
    assert ch3 == 13
    assert alloc.holding(15) == 60
    assert alloc.holding(14) == 64
    assert alloc.holding(13) == 67
