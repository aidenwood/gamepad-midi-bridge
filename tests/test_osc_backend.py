"""OSC 1.0 packet builder — byte-exact fixtures."""
from __future__ import annotations

import struct

import pytest

from gamepad_midi_bridge.osc_backend import _build_message, _pad4


def test_test_fixture_matches_self_check():
    """/test + float 1.5 -> 16 bytes; exact hex per OSC 1.0 spec."""
    pkt = _build_message("/test", (1.5,))
    assert len(pkt) == 16
    expected = bytes.fromhex("2f74657374000000" + "2c660000" + "3fc00000")
    assert pkt == expected


def test_address_padding_to_four_byte_boundary():
    """Address + null + padding must always land on a 4-byte boundary."""
    for addr in ("/a", "/ab", "/abc", "/abcd", "/abcde"):
        pkt = _build_message(addr, ())
        # Just the address segment + type tag segment (",\0\0\0") = first chunk.
        # Strip the trailing ",\0\0\0" type tag (4B) and confirm address slot %4 == 0.
        addr_segment = pkt[:-4]
        assert len(addr_segment) % 4 == 0
        assert addr_segment.startswith(addr.encode("utf-8") + b"\x00")


def test_string_length_three_boundary():
    """A 3-char string + null = 4 bytes; needs zero padding past the null."""
    pkt = _build_message("/s", ("abc",))
    # /s\0\0  (4B)  + ,s\0\0  (4B)  + abc\0  (4B)  = 12 B
    assert len(pkt) == 12
    assert pkt.endswith(b"abc\x00")


def test_string_length_four_boundary():
    """A 4-char string + null = 5 bytes; pads to 8 with three nulls."""
    pkt = _build_message("/s", ("abcd",))
    # /s\0\0 (4B) + ,s\0\0 (4B) + abcd\0\0\0\0 (8B) = 16 B
    assert len(pkt) == 16
    assert pkt.endswith(b"abcd\x00\x00\x00\x00")


def test_float_arg_encodes_big_endian():
    pkt = _build_message("/f", (2.5,))
    assert pkt[-4:] == struct.pack(">f", 2.5)


def test_int_arg_encodes_big_endian():
    pkt = _build_message("/i", (42,))
    assert pkt[-4:] == struct.pack(">i", 42)


def test_bool_args_use_tag_only():
    """OSC 1.0 booleans carry no payload bytes — tag is the value."""
    pkt_true = _build_message("/b", (True,))
    pkt_false = _build_message("/b", (False,))
    # /b\0\0 (4B) + ,T\0\0 (4B) = 8 B (no payload for booleans)
    assert len(pkt_true) == 8
    assert pkt_true[4:8] == b",T\x00\x00"
    assert pkt_false[4:8] == b",F\x00\x00"


def test_unsupported_type_raises():
    with pytest.raises(TypeError):
        _build_message("/x", (object(),))


def test_pad4_helper():
    assert _pad4(b"") == b""
    assert _pad4(b"a") == b"a\x00\x00\x00"
    assert _pad4(b"abcd") == b"abcd"
    assert _pad4(b"abcde") == b"abcde\x00\x00\x00"


def test_multiple_args_concatenate_in_order():
    pkt = _build_message("/m", (1, 2.5, "ok"))
    # /m\0\0 (4B) + ,ifs\0\0\0\0 (8B) + int(1)(4B) + float(2.5)(4B) + ok\0\0(4B)
    assert pkt[:4] == b"/m\x00\x00"
    assert pkt[4:12] == b",ifs\x00\x00\x00\x00"
    assert pkt[12:16] == struct.pack(">i", 1)
    assert pkt[16:20] == struct.pack(">f", 2.5)
    assert pkt[20:24] == b"ok\x00\x00"
