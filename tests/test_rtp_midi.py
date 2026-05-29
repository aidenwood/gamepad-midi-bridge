"""Tests for RTP-MIDI sender and mapping integration."""
from __future__ import annotations

import socket
import struct
import unittest
from unittest.mock import MagicMock, patch

import pytest

from gamepad_midi_bridge.mapping import Mapping, RtpMidiConfig, _rtp_midi_from_dict
from gamepad_midi_bridge.rtp_midi import RtpMidiSender


# ---------------------------------------------------------------------------
# RtpMidiSender unit tests
# ---------------------------------------------------------------------------

class TestRtpMidiSenderLifecycle:
    """start() / stop() without errors and idempotency."""

    def test_start_stop(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        sender.start()
        assert sender.is_open
        sender.stop()
        assert not sender.is_open

    def test_double_start_is_idempotent(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        sender.start()
        sock1 = sender._sock
        sender.start()          # second call should no-op
        assert sender._sock is sock1
        sender.stop()

    def test_double_stop_is_idempotent(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        sender.start()
        sender.stop()
        sender.stop()           # should not raise
        assert not sender.is_open

    def test_send_before_start_does_not_raise(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        # _sock is None — must be a silent no-op, not an exception
        sender.send_midi(0x90, 60, 100)


class TestRtpMidiPacketBuilding:
    """Verify RTP header layout and packet length for a 3-byte CC message."""

    def _build(self, status=0xB0, data1=7, data2=64):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        # Force known SSRC for deterministic byte checks
        sender._ssrc = 0xDEADBEEF
        sender._seq = 0
        return sender._build_packet(status, data1, data2)

    def test_packet_length_is_16_bytes_for_3byte_midi(self):
        """12 byte RTP header + 1 byte cmd section + 3 byte MIDI = 16."""
        pkt = self._build()
        assert len(pkt) == 16

    def test_rtp_version_bits(self):
        """Byte 0 must have V=2 (bits 7-6 = 0b10)."""
        pkt = self._build()
        assert (pkt[0] >> 6) == 2

    def test_payload_type_is_97(self):
        """Byte 1 bits 6-0 must equal 97 (0x61), M bit = 0."""
        pkt = self._build()
        assert (pkt[1] & 0x7F) == 97
        assert (pkt[1] & 0x80) == 0   # M = 0

    def test_ssrc_encoded_correctly(self):
        """Bytes 8-11 must match the SSRC."""
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        sender._ssrc = 0x12345678
        sender._seq = 0
        pkt = sender._build_packet(0xB0, 7, 64)
        ssrc = struct.unpack("!I", pkt[8:12])[0]
        assert ssrc == 0x12345678

    def test_sequence_in_bytes_2_3(self):
        """Bytes 2-3 must carry the post-increment sequence number."""
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        sender._seq = 9
        pkt = sender._build_packet(0xB0, 7, 64)
        seq = struct.unpack("!H", pkt[2:4])[0]
        assert seq == 10  # post-increment

    def test_midi_command_section_length_nibble(self):
        """Byte 12 (command section) lower nibble must be 3."""
        pkt = self._build()
        assert (pkt[12] & 0x0F) == 3

    def test_midi_payload_bytes(self):
        """Bytes 13-15 must be the raw status / data1 / data2."""
        pkt = self._build(status=0xB0, data1=7, data2=64)
        assert pkt[13] == 0xB0
        assert pkt[14] == 7
        assert pkt[15] == 64


class TestRtpMidiSequenceIncrement:
    """Sequence number auto-increments on each send."""

    def test_sequence_increments_on_build(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        sender._seq = 5
        sender._build_packet(0x90, 60, 100)
        assert sender._seq == 6

    def test_sequence_wraps_at_16bit(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        sender._seq = 0xFFFF
        sender._build_packet(0x90, 60, 100)
        assert sender._seq == 0

    def test_send_midi_increments_sequence(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        sender._sock = mock_sock
        sender._seq = 100
        sender.send_midi(0xB0, 7, 64)
        assert sender._seq == 101

    def test_sequence_monotonic_across_multiple_sends(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        mock_sock = MagicMock()
        sender._sock = mock_sock
        sender._seq = 0
        for _ in range(10):
            sender.send_midi(0x90, 60, 100)
        assert sender._seq == 10


class TestRtpMidiSocketFailure:
    """Socket errors are swallowed — never propagate to caller."""

    def test_sendto_oserror_is_silenced(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = OSError("Network down")
        sender._sock = mock_sock
        # Must not raise
        sender.send_midi(0xB0, 7, 64)

    def test_sendto_blockingio_is_silenced(self):
        sender = RtpMidiSender("127.0.0.1", 15004, "Test")
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = BlockingIOError("Would block")
        sender._sock = mock_sock
        sender.send_midi(0x90, 60, 100)

    def test_no_real_udp_traffic_in_tests(self):
        """Ensure tests patch the socket so nothing hits the real network."""
        sender = RtpMidiSender("192.168.0.99", 5004, "Test")
        mock_sock = MagicMock()
        sender._sock = mock_sock
        sender.send_midi(0xB0, 1, 127)
        mock_sock.sendto.assert_called_once()
        # Verify destination
        _call_args = mock_sock.sendto.call_args
        assert _call_args[0][1] == ("192.168.0.99", 5004)


# ---------------------------------------------------------------------------
# RtpMidiConfig + _rtp_midi_from_dict
# ---------------------------------------------------------------------------

class TestRtpMidiConfig:
    """Defaults and from_dict hydration."""

    def test_default_disabled(self):
        cfg = RtpMidiConfig()
        assert cfg.enabled is False
        assert cfg.peer_host == "127.0.0.1"
        assert cfg.peer_port == 5004
        assert cfg.session_name == "UCM Bridge"

    def test_from_dict_none_returns_default(self):
        cfg = _rtp_midi_from_dict(None)
        assert cfg.enabled is False

    def test_from_dict_empty_returns_default(self):
        cfg = _rtp_midi_from_dict({})
        assert cfg.enabled is False

    def test_from_dict_values(self):
        cfg = _rtp_midi_from_dict({
            "enabled": True,
            "peer_host": "10.0.0.5",
            "peer_port": 5006,
            "session_name": "Studio",
        })
        assert cfg.enabled is True
        assert cfg.peer_host == "10.0.0.5"
        assert cfg.peer_port == 5006
        assert cfg.session_name == "Studio"

    def test_from_dict_port_clamped(self):
        cfg = _rtp_midi_from_dict({"peer_port": 99999})
        assert cfg.peer_port == 65535

    def test_from_dict_bad_port_falls_back(self):
        cfg = _rtp_midi_from_dict({"peer_port": "not_a_number"})
        assert cfg.peer_port == 5004

    def test_mapping_has_rtp_midi_field(self):
        m = Mapping()
        assert hasattr(m, "rtp_midi")
        assert isinstance(m.rtp_midi, RtpMidiConfig)

    def test_mapping_from_dict_rtp_midi(self):
        m = Mapping.from_dict({
            "rtp_midi": {"enabled": True, "peer_host": "192.168.1.10", "peer_port": 5004}
        })
        assert m.rtp_midi.enabled is True
        assert m.rtp_midi.peer_host == "192.168.1.10"

    def test_mapping_from_dict_no_rtp_midi_stays_disabled(self):
        """Old presets without rtp_midi key load cleanly with feature off."""
        m = Mapping.from_dict({"name": "Legacy"})
        assert m.rtp_midi.enabled is False
