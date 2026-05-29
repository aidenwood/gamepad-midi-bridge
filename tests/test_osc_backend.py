"""OSC 1.0 packet builder + receiver — byte-exact fixtures and integration tests."""
from __future__ import annotations

import socket
import struct
import threading
import time

import pytest

from gamepad_midi_bridge.osc_backend import (
    OscReceiver,
    _build_message,
    _pad4,
    _parse_message,
)
from gamepad_midi_bridge.mapping import OscConfig, OscHapticBinding, _osc_from_dict


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


# ============================================================ OscHapticBinding schema


def test_osc_haptic_binding_defaults():
    b = OscHapticBinding()
    assert b.address == "/midi/note/36"
    assert b.trigger == "L2"
    assert b.effect == "vibration"
    assert b.intensity_scale == 1.0


def test_osc_haptic_binding_round_trip():
    """to_dict / _osc_haptic_binding_from_dict round-trip preserves all fields."""
    from dataclasses import asdict
    from gamepad_midi_bridge.mapping import _osc_haptic_binding_from_dict
    original = OscHapticBinding(
        address="/resolume/clip/connect",
        trigger="R2",
        effect="feedback",
        intensity_scale=0.75,
    )
    d = asdict(original)
    restored = _osc_haptic_binding_from_dict(d)
    assert restored.address == original.address
    assert restored.trigger == original.trigger
    assert restored.effect == original.effect
    assert restored.intensity_scale == original.intensity_scale


def test_osc_config_listen_disabled_by_default():
    cfg = OscConfig()
    assert cfg.listen_enabled is False
    assert cfg.listen_port == 7001
    assert cfg.listen_bindings == []


def test_osc_from_dict_hydrates_listen_fields():
    d = {
        "enabled": True,
        "listen_enabled": True,
        "listen_port": 9001,
        "listen_bindings": [
            {"address": "/clip/1", "trigger": "L2", "effect": "vibration", "intensity_scale": 0.5},
        ],
    }
    cfg = _osc_from_dict(d)
    assert cfg.listen_enabled is True
    assert cfg.listen_port == 9001
    assert len(cfg.listen_bindings) == 1
    assert cfg.listen_bindings[0].address == "/clip/1"
    assert cfg.listen_bindings[0].intensity_scale == 0.5


def test_osc_from_dict_old_preset_no_listen_fields():
    """Old presets without listen fields load cleanly with defaults."""
    d = {"enabled": True, "host": "10.0.0.1", "port": 7000}
    cfg = _osc_from_dict(d)
    assert cfg.listen_enabled is False
    assert cfg.listen_port == 7001
    assert cfg.listen_bindings == []


# ============================================================ OscReceiver bind/unbind


def _free_port() -> int:
    """Find a free UDP port by briefly binding to port 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def test_osc_receiver_start_stop_no_leaked_threads():
    """start() spawns exactly one daemon thread; stop() joins it cleanly."""
    port = _free_port()
    recv = OscReceiver(port=port)
    assert not recv.is_alive()
    recv.start()
    assert recv.is_alive()
    recv.stop()
    # Thread should be gone within the join timeout
    assert not recv.is_alive()
    assert recv._thread is None


def test_osc_receiver_double_start_is_idempotent():
    port = _free_port()
    recv = OscReceiver(port=port)
    recv.start()
    thread_before = recv._thread
    recv.start()   # should be a no-op
    assert recv._thread is thread_before
    recv.stop()


def test_osc_receiver_stop_without_start_is_safe():
    recv = OscReceiver(port=_free_port())
    recv.stop()  # should not raise


# ============================================================ OscReceiver dispatch


def test_osc_receiver_dispatches_float_message():
    """Sending a ,f datagram fires the callback exactly once with correct values."""
    port = _free_port()
    received: list = []
    event = threading.Event()

    def cb(address, args):
        received.append((address, args))
        event.set()

    recv = OscReceiver(port=port)
    recv.set_callback(cb)
    recv.start()

    # Build and fire a /kick 0.9 message
    pkt = _build_message("/kick", (0.9,))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(pkt, ("127.0.0.1", port))
        fired = event.wait(timeout=1.0)
    finally:
        sock.close()
        recv.stop()

    assert fired, "Callback was never called"
    assert len(received) == 1
    address, args = received[0]
    assert address == "/kick"
    assert len(args) == 1
    assert abs(args[0] - 0.9) < 1e-5


def test_osc_receiver_address_match_fires_callback_once():
    """Fires exactly once per matching datagram, no duplicates."""
    port = _free_port()
    call_count = [0]
    done = threading.Event()

    def cb(address, args):
        call_count[0] += 1
        done.set()

    recv = OscReceiver(port=port)
    recv.set_callback(cb)
    recv.start()

    pkt = _build_message("/snare", (1.0,))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(pkt, ("127.0.0.1", port))
        done.wait(timeout=1.0)
        # Brief extra wait to catch any spurious duplicate deliveries
        time.sleep(0.05)
    finally:
        sock.close()
        recv.stop()

    assert call_count[0] == 1


# ============================================================ OSC 1.0 parsing


def test_parse_message_float_arg():
    pkt = _build_message("/test", (0.5,))
    address, args = _parse_message(pkt)
    assert address == "/test"
    assert len(args) == 1
    assert abs(args[0] - 0.5) < 1e-5


def test_parse_message_int_arg():
    pkt = _build_message("/val", (42,))
    address, args = _parse_message(pkt)
    assert address == "/val"
    assert args == [42]


def test_parse_message_string_arg():
    pkt = _build_message("/s", ("hello",))
    address, args = _parse_message(pkt)
    assert address == "/s"
    assert args == ["hello"]


def test_parse_message_bool_true():
    pkt = _build_message("/b", (True,))
    address, args = _parse_message(pkt)
    assert address == "/b"
    assert args == [True]


def test_parse_message_bool_false():
    pkt = _build_message("/b", (False,))
    address, args = _parse_message(pkt)
    assert address == "/b"
    assert args == [False]


def test_parse_message_comma_f_type_tag_float():
    """Explicit: OSC 1.0 ,f type tag with a single float argument."""
    # Construct the raw packet manually to be spec-certain
    addr = b"/midi/note/36\x00\x00\x00"   # 16 bytes (14 + 2 pad to 16)
    assert len(addr) == 16
    type_tag = b",f\x00\x00"               # 4 bytes
    payload = struct.pack(">f", 0.75)      # 4 bytes
    pkt = addr + type_tag + payload
    assert len(pkt) == 24
    address, args = _parse_message(pkt)
    assert address == "/midi/note/36"
    assert len(args) == 1
    assert abs(args[0] - 0.75) < 1e-5


def test_parse_message_no_args():
    pkt = _build_message("/ping", ())
    address, args = _parse_message(pkt)
    assert address == "/ping"
    assert args == []


def test_parse_message_bad_address_raises():
    with pytest.raises(ValueError):
        _parse_message(b"no-slash\x00\x00\x00\x00" + b",\x00\x00\x00")


def test_parse_message_too_short_raises():
    with pytest.raises(ValueError):
        _parse_message(b"/x")


def test_parse_message_multiple_args():
    """Round-trip: int + float + string all decoded correctly."""
    pkt = _build_message("/multi", (7, 3.14, "abc"))
    address, args = _parse_message(pkt)
    assert address == "/multi"
    assert args[0] == 7
    assert abs(args[1] - 3.14) < 1e-4
    assert args[2] == "abc"
