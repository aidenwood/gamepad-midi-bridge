"""Tests for daw_transport module — DAW transport and MIDI Machine Control (MMC).

MMC SysEx commands, MIDI real-time transport bytes, and song position helpers.
All operations are pure functions (no state).
"""

from __future__ import annotations

import pytest

from gamepad_midi_bridge import daw_transport as daw


# ─────────────────────────────────────────────────────────────────────
# mmc() — MIDI Machine Control SysEx commands
# ─────────────────────────────────────────────────────────────────────


def test_mmc_play():
    """MMC play command has correct structure: [F0, 7F, 7F, 06, 02, F7]."""
    msg = daw.mmc("play")
    assert msg[0] == 0xF0  # SYSEX_START
    assert msg[1] == 0x7F  # UNIVERSAL_REALTIME
    assert msg[2] == 0x7F  # device_id (default all)
    assert msg[3] == 0x06  # MMC command ID
    assert msg[4] == 0x02  # play command byte
    assert msg[5] == 0xF7  # SYSEX_END
    assert len(msg) == 6


def test_mmc_stop():
    """MMC stop command byte is 0x01."""
    msg = daw.mmc("stop")
    assert msg[4] == 0x01


def test_mmc_pause():
    """MMC pause command byte is 0x09."""
    msg = daw.mmc("pause")
    assert msg[4] == 0x09


def test_mmc_record_strobe():
    """MMC record_strobe command byte is 0x06."""
    msg = daw.mmc("record_strobe")
    assert msg[4] == 0x06


def test_mmc_rewind():
    """MMC rewind command byte is 0x05."""
    msg = daw.mmc("rewind")
    assert msg[4] == 0x05


def test_mmc_fast_forward():
    """MMC fast_forward command byte is 0x04."""
    msg = daw.mmc("fast_forward")
    assert msg[4] == 0x04


def test_mmc_record_exit():
    """MMC record_exit command byte is 0x07."""
    msg = daw.mmc("record_exit")
    assert msg[4] == 0x07


def test_mmc_eject():
    """MMC eject command byte is 0x0A."""
    msg = daw.mmc("eject")
    assert msg[4] == 0x0A


def test_mmc_deferred_play():
    """MMC deferred_play command byte is 0x03."""
    msg = daw.mmc("deferred_play")
    assert msg[4] == 0x03


def test_mmc_specific_device_id():
    """MMC with specific device_id (e.g., 0x42)."""
    msg = daw.mmc("stop", device_id=0x42)
    assert msg[2] == 0x42


def test_mmc_clamp_device_id_low():
    """MMC device_id < 0 clamps to 0."""
    msg = daw.mmc("stop", device_id=-5)
    assert msg[2] == 0x00


def test_mmc_clamp_device_id_high():
    """MMC device_id > 127 clamps to 127."""
    msg = daw.mmc("stop", device_id=200)
    assert msg[2] == 0x7F


def test_mmc_unknown_command():
    """MMC with unknown command raises KeyError."""
    with pytest.raises(KeyError):
        daw.mmc("unknown_command")


def test_mmc_all_commands_exist():
    """All documented MMC commands can be built."""
    commands = [
        "play",
        "stop",
        "pause",
        "record_strobe",
        "rewind",
        "fast_forward",
        "eject",
        "deferred_play",
        "record_exit",
        "record_pause",
        "chase",
        "command_error_reset",
        "mmc_reset",
    ]
    for cmd in commands:
        msg = daw.mmc(cmd)
        assert msg[0] == 0xF0
        assert msg[-1] == 0xF7


# ─────────────────────────────────────────────────────────────────────
# mmc_locate() — MMC locate with SMPTE timecode
# ─────────────────────────────────────────────────────────────────────


def test_mmc_locate_basic():
    """MMC locate command has correct structure."""
    msg = daw.mmc_locate(hours=1, minutes=2, seconds=3, frames=4)
    assert msg[0] == 0xF0  # SYSEX_START
    assert msg[1] == 0x7F  # UNIVERSAL_REALTIME
    assert msg[2] == 0x7F  # device_id (default all)
    assert msg[3] == 0x06  # MMC command ID
    assert msg[4] == 0x44  # Locate command
    assert msg[5] == 0x06  # Data length
    assert msg[6] == 0x01  # SMPTE format type
    assert msg[7] == 0x01  # hours
    assert msg[8] == 0x02  # minutes
    assert msg[9] == 0x03  # seconds
    assert msg[10] == 0x04  # frames
    assert msg[11] == 0xF7  # SYSEX_END
    assert len(msg) == 12


def test_mmc_locate_zero_timecode():
    """MMC locate with all zeros."""
    msg = daw.mmc_locate(0, 0, 0, 0)
    assert msg[7] == 0x00
    assert msg[8] == 0x00
    assert msg[9] == 0x00
    assert msg[10] == 0x00


def test_mmc_locate_max_timecode():
    """MMC locate with maximum valid SMPTE values."""
    msg = daw.mmc_locate(23, 59, 59, 29)
    assert msg[7] == 0x17  # 23 in hex
    assert msg[8] == 0x3B  # 59 in hex
    assert msg[9] == 0x3B  # 59 in hex
    assert msg[10] == 0x1D  # 29 in hex


def test_mmc_locate_clamp_hours():
    """MMC locate hours > 23 clamps to 23."""
    msg = daw.mmc_locate(100, 0, 0, 0)
    assert msg[7] == 0x17


def test_mmc_locate_clamp_minutes():
    """MMC locate minutes > 59 clamps to 59."""
    msg = daw.mmc_locate(0, 120, 0, 0)
    assert msg[8] == 0x3B


def test_mmc_locate_clamp_seconds():
    """MMC locate seconds > 59 clamps to 59."""
    msg = daw.mmc_locate(0, 0, 100, 0)
    assert msg[9] == 0x3B


def test_mmc_locate_clamp_frames():
    """MMC locate frames > 29 clamps to 29."""
    msg = daw.mmc_locate(0, 0, 0, 100)
    assert msg[10] == 0x1D


def test_mmc_locate_clamp_negative():
    """MMC locate negative values clamp to 0."""
    msg = daw.mmc_locate(-10, -5, -1, -20)
    assert msg[7] == 0x00
    assert msg[8] == 0x00
    assert msg[9] == 0x00
    assert msg[10] == 0x00


def test_mmc_locate_specific_device_id():
    """MMC locate with specific device_id."""
    msg = daw.mmc_locate(1, 2, 3, 4, device_id=0x50)
    assert msg[2] == 0x50


# ─────────────────────────────────────────────────────────────────────
# MIDI Real-Time transport messages
# ─────────────────────────────────────────────────────────────────────


def test_realtime_start():
    """Real-time START message is [FA]."""
    msg = daw.realtime_start()
    assert msg == [0xFA]


def test_realtime_stop():
    """Real-time STOP message is [FC]."""
    msg = daw.realtime_stop()
    assert msg == [0xFC]


def test_realtime_continue():
    """Real-time CONTINUE message is [FB]."""
    msg = daw.realtime_continue()
    assert msg == [0xFB]


# ─────────────────────────────────────────────────────────────────────
# Song Position Pointer (SPP) and Song Select
# ─────────────────────────────────────────────────────────────────────


def test_song_position_pointer_zero():
    """SPP at position 0 is [F2, 00, 00]."""
    msg = daw.song_position_pointer(0)
    assert msg == [0xF2, 0x00, 0x00]


def test_song_position_pointer_16():
    """SPP at position 16 (0x10) is [F2, 10, 00]."""
    msg = daw.song_position_pointer(16)
    assert msg == [0xF2, 0x10, 0x00]


def test_song_position_pointer_128():
    """SPP at position 128 (0x80) crosses into MSB: [F2, 00, 01]."""
    msg = daw.song_position_pointer(128)
    assert msg == [0xF2, 0x00, 0x01]


def test_song_position_pointer_255():
    """SPP at position 255 (0xFF) is [F2, 7F, 01]."""
    msg = daw.song_position_pointer(255)
    assert msg == [0xF2, 0x7F, 0x01]


def test_song_position_pointer_max():
    """SPP at position 16383 (max) is [F2, 7F, 7F]."""
    msg = daw.song_position_pointer(16383)
    assert msg == [0xF2, 0x7F, 0x7F]


def test_song_position_pointer_clamp_high():
    """SPP > 16383 clamps to 16383."""
    msg = daw.song_position_pointer(20000)
    assert msg == [0xF2, 0x7F, 0x7F]


def test_song_position_pointer_clamp_negative():
    """SPP < 0 clamps to 0."""
    msg = daw.song_position_pointer(-100)
    assert msg == [0xF2, 0x00, 0x00]


def test_song_select_zero():
    """Song select 0 is [F3, 00]."""
    msg = daw.song_select(0)
    assert msg == [0xF3, 0x00]


def test_song_select_max():
    """Song select 127 is [F3, 7F]."""
    msg = daw.song_select(127)
    assert msg == [0xF3, 0x7F]


def test_song_select_clamp_high():
    """Song select > 127 clamps to 127."""
    msg = daw.song_select(200)
    assert msg == [0xF3, 0x7F]


def test_song_select_clamp_negative():
    """Song select < 0 clamps to 0."""
    msg = daw.song_select(-10)
    assert msg == [0xF3, 0x00]


# ─────────────────────────────────────────────────────────────────────
# Tune Request
# ─────────────────────────────────────────────────────────────────────


def test_tune_request():
    """Tune request is [F6]."""
    msg = daw.tune_request()
    assert msg == [0xF6]


# ─────────────────────────────────────────────────────────────────────
# TransportPreference dataclass
# ─────────────────────────────────────────────────────────────────────


def test_transport_preference_default():
    """Default TransportPreference: disabled, all devices, MMC preferred."""
    pref = daw.TransportPreference()
    assert pref.enabled is False
    assert pref.device_id == 0x7F
    assert pref.prefer_mmc is True


def test_transport_preference_explicit():
    """Explicit TransportPreference construction."""
    pref = daw.TransportPreference(
        enabled=True,
        device_id=0x50,
        prefer_mmc=False,
    )
    assert pref.enabled is True
    assert pref.device_id == 0x50
    assert pref.prefer_mmc is False


def test_transport_preference_clamp_device_id():
    """TransportPreference clamps device_id on construction."""
    pref = daw.TransportPreference(device_id=200)
    assert pref.device_id == 0x7F

    pref = daw.TransportPreference(device_id=-10)
    assert pref.device_id == 0x00


def test_transport_preference_to_dict():
    """TransportPreference.to_dict() round-trips."""
    pref = daw.TransportPreference(
        enabled=True,
        device_id=0x42,
        prefer_mmc=False,
    )
    d = pref.to_dict()
    assert d == {
        "enabled": True,
        "device_id": 0x42,
        "prefer_mmc": False,
    }


def test_transport_preference_from_dict():
    """TransportPreference.from_dict() round-trips."""
    d = {
        "enabled": True,
        "device_id": 0x42,
        "prefer_mmc": False,
    }
    pref = daw.TransportPreference.from_dict(d)
    assert pref.enabled is True
    assert pref.device_id == 0x42
    assert pref.prefer_mmc is False


def test_transport_preference_round_trip():
    """TransportPreference to_dict + from_dict round-trip."""
    original = daw.TransportPreference(
        enabled=True,
        device_id=0x55,
        prefer_mmc=False,
    )
    restored = daw.TransportPreference.from_dict(original.to_dict())
    assert restored.enabled == original.enabled
    assert restored.device_id == original.device_id
    assert restored.prefer_mmc == original.prefer_mmc


# ─────────────────────────────────────────────────────────────────────
# build_command() — Composite transport routing
# ─────────────────────────────────────────────────────────────────────


def test_build_command_disabled():
    """build_command with disabled preference returns empty list."""
    pref = daw.TransportPreference(enabled=False)
    msg = daw.build_command("play", pref)
    assert msg == []


def test_build_command_play_mmc():
    """build_command play with prefer_mmc=True emits MMC play."""
    pref = daw.TransportPreference(enabled=True, prefer_mmc=True)
    msgs = daw.build_command("play", pref)
    assert len(msgs) == 1
    assert msgs[0][4] == 0x02  # play command byte


def test_build_command_play_realtime():
    """build_command play with prefer_mmc=False emits realtime_start."""
    pref = daw.TransportPreference(enabled=True, prefer_mmc=False)
    msgs = daw.build_command("play", pref)
    assert len(msgs) == 1
    assert msgs[0] == [0xFA]


def test_build_command_stop_mmc():
    """build_command stop with prefer_mmc=True emits MMC stop."""
    pref = daw.TransportPreference(enabled=True, prefer_mmc=True)
    msgs = daw.build_command("stop", pref)
    assert len(msgs) == 1
    assert msgs[0][4] == 0x01  # stop command byte


def test_build_command_stop_realtime():
    """build_command stop with prefer_mmc=False emits realtime_stop."""
    pref = daw.TransportPreference(enabled=True, prefer_mmc=False)
    msgs = daw.build_command("stop", pref)
    assert len(msgs) == 1
    assert msgs[0] == [0xFC]


def test_build_command_continue_mmc():
    """build_command continue with prefer_mmc=True emits MMC deferred_play."""
    pref = daw.TransportPreference(enabled=True, prefer_mmc=True)
    msgs = daw.build_command("continue", pref)
    assert len(msgs) == 1
    assert msgs[0][4] == 0x03  # deferred_play command byte


def test_build_command_continue_realtime():
    """build_command continue with prefer_mmc=False emits realtime_continue."""
    pref = daw.TransportPreference(enabled=True, prefer_mmc=False)
    msgs = daw.build_command("continue", pref)
    assert len(msgs) == 1
    assert msgs[0] == [0xFB]


def test_build_command_pause():
    """build_command pause always emits MMC pause."""
    pref = daw.TransportPreference(enabled=True, prefer_mmc=False)
    msgs = daw.build_command("pause", pref)
    assert len(msgs) == 1
    assert msgs[0][4] == 0x09  # pause command byte


def test_build_command_record_strobe():
    """build_command record_strobe always emits MMC record_strobe."""
    pref = daw.TransportPreference(enabled=True)
    msgs = daw.build_command("record_strobe", pref)
    assert len(msgs) == 1
    assert msgs[0][4] == 0x06  # record_strobe command byte


def test_build_command_rewind():
    """build_command rewind always emits MMC rewind."""
    pref = daw.TransportPreference(enabled=True)
    msgs = daw.build_command("rewind", pref)
    assert len(msgs) == 1
    assert msgs[0][4] == 0x05  # rewind command byte


def test_build_command_fast_forward():
    """build_command fast_forward always emits MMC fast_forward."""
    pref = daw.TransportPreference(enabled=True)
    msgs = daw.build_command("fast_forward", pref)
    assert len(msgs) == 1
    assert msgs[0][4] == 0x04  # fast_forward command byte


def test_build_command_respects_device_id():
    """build_command respects device_id from preference."""
    pref = daw.TransportPreference(enabled=True, device_id=0x50, prefer_mmc=True)
    msgs = daw.build_command("play", pref)
    assert msgs[0][2] == 0x50


def test_build_command_unknown():
    """build_command with unknown command returns empty list."""
    pref = daw.TransportPreference(enabled=True)
    msgs = daw.build_command("unknown", pref)
    assert msgs == []


def test_build_command_locate_not_supported():
    """build_command locate returns empty list (use mmc_locate directly)."""
    pref = daw.TransportPreference(enabled=True)
    msgs = daw.build_command("locate", pref)
    assert msgs == []
