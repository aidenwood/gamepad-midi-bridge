"""Tests for pitch bend range RPN configuration.

Covers PitchBendRangeConfig dataclass, RPN message building, and bend/cents conversion.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import pitch_bend_range as pbr


# ─────────────────────────────────────────────────────────────────────
# PitchBendRangeConfig — defaults and clamping
# ─────────────────────────────────────────────────────────────────────


def test_config_defaults():
    """Default config should have sensible values."""
    cfg = pbr.PitchBendRangeConfig()
    assert cfg.enabled is False
    assert cfg.semitones == 2
    assert cfg.cents == 0
    assert cfg.channel == 1
    assert cfg.send_on_load is True


def test_config_clamp_semitones_below():
    """Negative semitones should clamp to 0."""
    cfg = pbr.PitchBendRangeConfig(semitones=-5)
    assert cfg.semitones == 0


def test_config_clamp_semitones_above():
    """Semitones > 24 should clamp to 24."""
    cfg = pbr.PitchBendRangeConfig(semitones=30)
    assert cfg.semitones == 24


def test_config_clamp_cents_below():
    """Negative cents should clamp to 0."""
    cfg = pbr.PitchBendRangeConfig(cents=-10)
    assert cfg.cents == 0


def test_config_clamp_cents_above():
    """Cents > 99 should clamp to 99."""
    cfg = pbr.PitchBendRangeConfig(cents=150)
    assert cfg.cents == 99


def test_config_clamp_channel_below():
    """Channel < 1 should clamp to 1."""
    cfg = pbr.PitchBendRangeConfig(channel=0)
    assert cfg.channel == 1


def test_config_clamp_channel_above():
    """Channel > 16 should clamp to 16."""
    cfg = pbr.PitchBendRangeConfig(channel=20)
    assert cfg.channel == 16


# ─────────────────────────────────────────────────────────────────────
# PitchBendRangeConfig — serialization
# ─────────────────────────────────────────────────────────────────────


def test_config_to_dict():
    """to_dict should round-trip all fields."""
    cfg = pbr.PitchBendRangeConfig(
        enabled=True, semitones=12, cents=50, channel=5, send_on_load=False
    )
    d = cfg.to_dict()
    assert d == {
        "enabled": True,
        "semitones": 12,
        "cents": 50,
        "channel": 5,
        "send_on_load": False,
    }


def test_config_from_dict():
    """from_dict should reconstruct config exactly."""
    d = {
        "enabled": True,
        "semitones": 12,
        "cents": 50,
        "channel": 5,
        "send_on_load": False,
    }
    cfg = pbr.PitchBendRangeConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.semitones == 12
    assert cfg.cents == 50
    assert cfg.channel == 5
    assert cfg.send_on_load is False


def test_config_round_trip():
    """to_dict → from_dict should preserve all fields."""
    cfg1 = pbr.PitchBendRangeConfig(
        enabled=True, semitones=8, cents=25, channel=10, send_on_load=False
    )
    cfg2 = pbr.PitchBendRangeConfig.from_dict(cfg1.to_dict())
    assert cfg2.enabled == cfg1.enabled
    assert cfg2.semitones == cfg1.semitones
    assert cfg2.cents == cfg1.cents
    assert cfg2.channel == cfg1.channel
    assert cfg2.send_on_load == cfg1.send_on_load


def test_config_from_dict_with_defaults():
    """from_dict should fill in missing fields with defaults."""
    cfg = pbr.PitchBendRangeConfig.from_dict({})
    assert cfg.enabled is False
    assert cfg.semitones == 2
    assert cfg.cents == 0
    assert cfg.channel == 1
    assert cfg.send_on_load is True


# ─────────────────────────────────────────────────────────────────────
# build_rpn_messages — structure and channel encoding
# ─────────────────────────────────────────────────────────────────────


def test_build_rpn_messages_returns_6_messages():
    """RPN sequence should contain exactly 6 CC messages."""
    msgs = pbr.build_rpn_messages(2, 0, 1)
    assert len(msgs) == 6


def test_build_rpn_messages_message_structure():
    """Each message should be [status, data1, data2]."""
    msgs = pbr.build_rpn_messages(2, 0, 1)
    for msg in msgs:
        assert len(msg) == 3
        assert all(isinstance(x, int) for x in msg)
        assert 0 <= msg[0] <= 255
        assert 0 <= msg[1] <= 127
        assert 0 <= msg[2] <= 127


def test_build_rpn_messages_channel_1():
    """Channel 1 should encode as 0xB0."""
    msgs = pbr.build_rpn_messages(2, 0, 1)
    for msg in msgs:
        assert msg[0] == 0xB0


def test_build_rpn_messages_channel_5():
    """Channel 5 should encode as 0xB4 (0xB0 | 4)."""
    msgs = pbr.build_rpn_messages(2, 0, 5)
    for msg in msgs:
        assert msg[0] == 0xB4


def test_build_rpn_messages_channel_16():
    """Channel 16 should encode as 0xBF (0xB0 | 15)."""
    msgs = pbr.build_rpn_messages(2, 0, 16)
    for msg in msgs:
        assert msg[0] == 0xBF


def test_build_rpn_messages_first_two_select_rpn():
    """First two messages should select RPN 0,0 (pitch bend sensitivity)."""
    msgs = pbr.build_rpn_messages(2, 0, 1)
    # CC 101 = 0
    assert msgs[0][1] == 0x65
    assert msgs[0][2] == 0x00
    # CC 100 = 0
    assert msgs[1][1] == 0x64
    assert msgs[1][2] == 0x00


def test_build_rpn_messages_data_entry_values():
    """Messages 3–4 should set Data Entry to [semitones, cents]."""
    msgs = pbr.build_rpn_messages(12, 50, 1)
    # CC 6 = semitones
    assert msgs[2][1] == 0x06
    assert msgs[2][2] == 12
    # CC 38 = cents
    assert msgs[3][1] == 0x26
    assert msgs[3][2] == 50


def test_build_rpn_messages_null_terminator():
    """Last two messages should null the RPN selection (CC 101/100 = 127)."""
    msgs = pbr.build_rpn_messages(2, 0, 1)
    # CC 101 = 127 (RPN Null MSB)
    assert msgs[4][1] == 0x65
    assert msgs[4][2] == 0x7F
    # CC 100 = 127 (RPN Null LSB)
    assert msgs[5][1] == 0x64
    assert msgs[5][2] == 0x7F


def test_build_rpn_messages_clamps_inputs():
    """build_rpn_messages should clamp semitones, cents, and channel."""
    msgs = pbr.build_rpn_messages(30, 150, 20)  # all out of range
    # Should clamp to 24, 99, 16
    assert msgs[2][2] == 24
    assert msgs[3][2] == 99
    assert msgs[0][0] == 0xBF  # channel 16 → 0xB0 | 15 = 0xBF


# ─────────────────────────────────────────────────────────────────────
# bend_to_cents — pitch bend to cents conversion
# ─────────────────────────────────────────────────────────────────────


def test_bend_to_cents_at_center():
    """Pitch bend 0 should map to 0 cents."""
    assert pbr.bend_to_cents(0, 2, 0) == pytest.approx(0.0, abs=1e-6)


def test_bend_to_cents_full_positive():
    """Full positive bend (8191) should map to +max_cents."""
    # max_cents = 2 * 100 + 0 = 200
    result = pbr.bend_to_cents(8191, 2, 0)
    assert result == pytest.approx(200.0, abs=1e-6)


def test_bend_to_cents_full_negative():
    """Full negative bend (-8192) should map to approx -max_cents (slight asymmetry due to MIDI range)."""
    # MIDI range is -8192..+8191 (asymmetric), so -8192 is slightly beyond perfect symmetry
    # max_cents = 2 * 100 + 0 = 200
    result = pbr.bend_to_cents(-8192, 2, 0)
    assert result == pytest.approx(-200.0, abs=0.03)  # Allow for MIDI asymmetry


def test_bend_to_cents_half_positive():
    """Half positive bend (≈4095) should map to ≈100 cents (1 semitone)."""
    result = pbr.bend_to_cents(4095, 2, 0)
    # 4095 / 8191 * 200 ≈ 100
    assert result == pytest.approx(100.0, abs=1.0)


def test_bend_to_cents_with_cents_config():
    """Should incorporate cents offset into range."""
    # max_cents = 2 * 100 + 50 = 250
    result = pbr.bend_to_cents(8191, 2, 50)
    assert result == pytest.approx(250.0, abs=1e-6)


def test_bend_to_cents_wide_range():
    """12 semitones = 1200 cents."""
    result = pbr.bend_to_cents(8191, 12, 0)
    assert result == pytest.approx(1200.0, abs=1e-6)


def test_bend_to_cents_clamps_inputs():
    """Inputs should be clamped to valid ranges."""
    # Even if passed out-of-range, should clamp and compute correctly
    result = pbr.bend_to_cents(8191, 30, 150, )
    # 30 → 24, 150 → 99; max_cents = 2499
    assert result == pytest.approx(2499.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────
# cents_to_bend — cents to pitch bend conversion (inverse)
# ─────────────────────────────────────────────────────────────────────


def test_cents_to_bend_at_center():
    """0 cents should map to pitch bend 0."""
    assert pbr.cents_to_bend(0, 2, 0) == 0


def test_cents_to_bend_full_range_positive():
    """Max cents should map to approximately 8191."""
    result = pbr.cents_to_bend(200, 2, 0)
    assert result == pytest.approx(8191, abs=1)


def test_cents_to_bend_full_range_negative():
    """Min cents should map to approximately -8192."""
    result = pbr.cents_to_bend(-200, 2, 0)
    assert result == pytest.approx(-8192, abs=1)


def test_cents_to_bend_half_range():
    """100 cents (half of 2-semitone range) should map to ≈4096."""
    result = pbr.cents_to_bend(100, 2, 0)
    assert result == pytest.approx(4096, abs=1)


def test_cents_to_bend_clamps_to_range():
    """Out-of-range cents should clamp to ±8191/-8192."""
    result = pbr.cents_to_bend(500, 2, 0)  # exceeds max of 200
    assert result == 8191

    result = pbr.cents_to_bend(-500, 2, 0)
    assert result == -8192


def test_cents_to_bend_with_cents_offset():
    """Should account for cents offset."""
    # max_cents = 2 * 100 + 50 = 250
    result = pbr.cents_to_bend(250, 2, 50)
    assert result == pytest.approx(8191, abs=1)


def test_cents_to_bend_zero_range():
    """If semitones and cents are both 0, should return 0 for any input."""
    assert pbr.cents_to_bend(100, 0, 0) == 0
    assert pbr.cents_to_bend(-100, 0, 0) == 0


# ─────────────────────────────────────────────────────────────────────
# Round-trip consistency
# ─────────────────────────────────────────────────────────────────────


def test_round_trip_bend_to_cents_to_bend():
    """Converting bend → cents → bend should recover original (within rounding)."""
    for bend in [-8192, -4096, -1000, 0, 1000, 4095, 8191]:
        cents = pbr.bend_to_cents(bend, 2, 0)
        recovered_bend = pbr.cents_to_bend(cents, 2, 0)
        assert recovered_bend == pytest.approx(bend, abs=1)


def test_round_trip_with_wide_range():
    """Round-trip with 12-semitone range."""
    for bend in [-8192, -4096, 0, 4095, 8191]:
        cents = pbr.bend_to_cents(bend, 12, 0)
        recovered_bend = pbr.cents_to_bend(cents, 12, 0)
        assert recovered_bend == pytest.approx(bend, abs=1)


def test_round_trip_with_cents_offset():
    """Round-trip with non-zero cents offset."""
    for bend in [-8192, -4096, 0, 4095, 8191]:
        cents = pbr.bend_to_cents(bend, 2, 50)
        recovered_bend = pbr.cents_to_bend(cents, 2, 50)
        assert recovered_bend == pytest.approx(bend, abs=1)
