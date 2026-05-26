"""DualSense trigger block + Bluetooth framing CRC.

Pure-data tests — no controller plugged in, no HID handle opened.
"""
from __future__ import annotations

import zlib

from gamepad_midi_bridge.dualsense import (
    TRIGGER_EFFECTS,
    _bt_output_packet,
    _crc32_dualsense,
    _trigger_block,
)


def test_weapon_block_shape_and_id():
    """weapon -> 11 bytes starting with 0x25 (Sony effect id)."""
    block = _trigger_block("weapon")
    assert len(block) == 11
    assert block[0] == 0x25


def test_all_effects_have_distinct_nonzero_ids():
    first_bytes = {name: _trigger_block(name)[0] for name in TRIGGER_EFFECTS}
    assert len(set(first_bytes.values())) == len(TRIGGER_EFFECTS)
    assert all(b != 0 for b in first_bytes.values())


def test_unknown_effect_falls_back_to_off():
    """Garbage name must not crash; lands on 0x05 (off)."""
    assert _trigger_block("totally-fake")[0] == 0x05
    assert _trigger_block("")[0] == 0x05


def test_crc32_helper_matches_zlib():
    """The Sony CRC is plain IEEE 802.3 — same as zlib.crc32."""
    assert _crc32_dualsense(b"") == zlib.crc32(b"")
    assert _crc32_dualsense(b"hello") == zlib.crc32(b"hello")
    assert _crc32_dualsense(bytes(range(64))) == zlib.crc32(bytes(range(64)))


def test_bt_output_packet_length_and_tail():
    """78-byte buffer; tail [74:78] is little-endian CRC32 over [0:74]."""
    off_block = _trigger_block("off")
    pkt = _bt_output_packet(off_block, off_block)
    assert len(pkt) == 78
    expected_crc = zlib.crc32(bytes(pkt[0:74])) & 0xFFFFFFFF
    assert pkt[74:78] == expected_crc.to_bytes(4, "little")


def test_bt_packet_framing_constants():
    """The 0xA2 seed + 0x31 report id + 0x02/0xFF/0xF7 flag bytes are fixed."""
    off_block = _trigger_block("off")
    pkt = _bt_output_packet(off_block, off_block)
    assert pkt[0] == 0xA2     # CRC seed prefix
    assert pkt[1] == 0x31     # BT output report id
    assert pkt[2] == 0x02     # tag byte
    assert pkt[3] == 0xFF     # flags1
    assert pkt[4] == 0xF7     # flags2


def test_bt_packet_off_off_reference_crc():
    """Documented regression tripwire — must equal 0x81C5A8D1."""
    off_block = _trigger_block("off")
    pkt = _bt_output_packet(off_block, off_block)
    crc = int.from_bytes(pkt[74:78], "little")
    assert crc == 0x81C5A8D1


def test_bt_packet_trigger_blocks_placed_at_documented_offsets():
    """R2 occupies [13:24], L2 occupies [24:35]."""
    weapon = _trigger_block("weapon")
    vibration = _trigger_block("vibration")
    pkt = _bt_output_packet(weapon, vibration)
    # L2 first arg to _bt_output_packet is the L2 block, R2 is the second.
    assert pkt[13:24] == vibration
    assert pkt[24:35] == weapon
