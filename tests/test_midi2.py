"""Tests for MIDI 2.0 / UMP helpers in gamepad_midi_bridge.midi2."""
import struct

import pytest

from gamepad_midi_bridge import midi2
from gamepad_midi_bridge.midi2 import (
    pack_midi2_cc,
    pack_midi2_note_on,
    scale_7bit_to_16bit,
    scale_7bit_to_32bit,
    is_supported,
    clear_probe_cache,
)


# ---------------------------------------------------------------------------
# Scaling helpers
# ---------------------------------------------------------------------------

class TestScale7bitTo16bit:
    def test_zero(self):
        assert scale_7bit_to_16bit(0) == 0

    def test_full(self):
        assert scale_7bit_to_16bit(127) == 0xFFFF

    def test_midpoint(self):
        # 64 should land roughly in the middle of the 16-bit range
        v = scale_7bit_to_16bit(64)
        assert 0x7F00 <= v <= 0x8200, f"midpoint {v:#06x} out of expected range"

    def test_clamps_above_127(self):
        assert scale_7bit_to_16bit(200) == 0xFFFF

    def test_clamps_below_0(self):
        assert scale_7bit_to_16bit(-5) == 0

    def test_monotonic(self):
        values = [scale_7bit_to_16bit(i) for i in range(128)]
        for a, b in zip(values, values[1:]):
            assert b >= a, "scale_7bit_to_16bit must be monotonically non-decreasing"


class TestScale7bitTo32bit:
    def test_zero(self):
        assert scale_7bit_to_32bit(0) == 0

    def test_full(self):
        assert scale_7bit_to_32bit(127) == 0xFFFFFFFF

    def test_monotonic(self):
        values = [scale_7bit_to_32bit(i) for i in range(128)]
        for a, b in zip(values, values[1:]):
            assert b >= a


# ---------------------------------------------------------------------------
# pack_midi2_note_on
# ---------------------------------------------------------------------------

class TestPackMidi2NoteOn:
    def test_returns_8_bytes(self):
        result = pack_midi2_note_on(0, 0, 60, 0xFFFF)
        assert isinstance(result, bytes)
        assert len(result) == 8

    def test_message_type_nibble(self):
        result = pack_midi2_note_on(0, 0, 60, 0x8000)
        word1, _ = struct.unpack(">II", result)
        msg_type = (word1 >> 28) & 0xF
        assert msg_type == 0x4, "message type must be 4 (MIDI 2.0 channel voice)"

    def test_status_nibble_is_note_on(self):
        result = pack_midi2_note_on(0, 0, 60, 0x8000)
        word1, _ = struct.unpack(">II", result)
        status_nibble = (word1 >> 20) & 0xF
        assert status_nibble == 0x9, "status nibble must be 9 (Note On)"

    def test_channel_encoded(self):
        for ch in (0, 5, 15):
            result = pack_midi2_note_on(0, ch, 60, 0x8000)
            word1, _ = struct.unpack(">II", result)
            channel = (word1 >> 16) & 0xF
            assert channel == ch

    def test_note_encoded(self):
        for note in (0, 60, 127):
            result = pack_midi2_note_on(0, 0, note, 0x8000)
            word1, _ = struct.unpack(">II", result)
            encoded_note = (word1 >> 8) & 0xFF
            assert encoded_note == note

    def test_velocity_in_word2_upper(self):
        vel = 0x1234
        result = pack_midi2_note_on(0, 0, 60, vel)
        _, word2 = struct.unpack(">II", result)
        upper_16 = (word2 >> 16) & 0xFFFF
        assert upper_16 == vel

    def test_group_encoded(self):
        for grp in (0, 7, 15):
            result = pack_midi2_note_on(grp, 0, 60, 0x8000)
            word1, _ = struct.unpack(">II", result)
            group = (word1 >> 24) & 0xF
            assert group == grp

    def test_clamps_note_to_127(self):
        result = pack_midi2_note_on(0, 0, 200, 0x8000)
        word1, _ = struct.unpack(">II", result)
        note = (word1 >> 8) & 0xFF
        assert note == 127

    def test_velocity_16bit_max_from_7bit_127(self):
        """scale_7bit_to_16bit(127) → 0xFFFF, packed correctly in word 2."""
        vel_16 = scale_7bit_to_16bit(127)
        assert vel_16 == 0xFFFF
        result = pack_midi2_note_on(0, 0, 60, vel_16)
        _, word2 = struct.unpack(">II", result)
        assert (word2 >> 16) & 0xFFFF == 0xFFFF


# ---------------------------------------------------------------------------
# pack_midi2_cc
# ---------------------------------------------------------------------------

class TestPackMidi2CC:
    def test_returns_8_bytes(self):
        result = pack_midi2_cc(0, 0, 1, 0xFFFFFFFF)
        assert isinstance(result, bytes)
        assert len(result) == 8

    def test_message_type_nibble(self):
        result = pack_midi2_cc(0, 0, 1, 0)
        word1, _ = struct.unpack(">II", result)
        msg_type = (word1 >> 28) & 0xF
        assert msg_type == 0x4

    def test_status_nibble_is_cc(self):
        result = pack_midi2_cc(0, 0, 1, 0)
        word1, _ = struct.unpack(">II", result)
        status_nibble = (word1 >> 20) & 0xF
        assert status_nibble == 0xB, "status nibble must be B (Control Change)"

    def test_cc_number_encoded(self):
        for cc in (0, 7, 127):
            result = pack_midi2_cc(0, 0, cc, 0)
            word1, _ = struct.unpack(">II", result)
            encoded_cc = (word1 >> 8) & 0xFF
            assert encoded_cc == cc

    def test_value_32bit_in_word2(self):
        val = 0xDEADBEEF
        result = pack_midi2_cc(0, 0, 1, val)
        _, word2 = struct.unpack(">II", result)
        assert word2 == val

    def test_channel_encoded(self):
        for ch in (0, 9, 15):
            result = pack_midi2_cc(0, ch, 1, 0)
            word1, _ = struct.unpack(">II", result)
            channel = (word1 >> 16) & 0xF
            assert channel == ch


# ---------------------------------------------------------------------------
# is_supported / probe cache
# ---------------------------------------------------------------------------

class _MockPort:
    """Minimal stub that mimics rtmidi's MidiOut.send_message interface."""
    def __init__(self, accept: bool = True):
        self._accept = accept
        self.calls: list = []

    def send_message(self, msg: list) -> None:
        self.calls.append(msg)
        if not self._accept:
            raise RuntimeError("Port does not accept UMP")


class TestIsSupported:
    def setup_method(self):
        clear_probe_cache()

    def test_accepting_port_returns_true(self):
        port = _MockPort(accept=True)
        assert is_supported(port) is True

    def test_rejecting_port_returns_false(self):
        port = _MockPort(accept=False)
        assert is_supported(port) is False

    def test_probe_cached_after_first_call(self):
        port = _MockPort(accept=True)
        is_supported(port)
        is_supported(port)
        # Only one send_message call despite two is_supported calls
        assert len(port.calls) == 1

    def test_probe_sends_8_bytes(self):
        port = _MockPort(accept=True)
        is_supported(port)
        assert len(port.calls) == 1
        assert len(port.calls[0]) == 8

    def test_clear_cache_re_probes(self):
        port = _MockPort(accept=True)
        is_supported(port)
        clear_probe_cache()
        is_supported(port)
        assert len(port.calls) == 2
