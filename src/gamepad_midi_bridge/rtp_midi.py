"""Minimal RTP-MIDI sender (RFC 4695 / 6295 — simplified subset).

Sends one MIDI message per UDP datagram to a configured peer.  No session
negotiation, no journal, no retransmission — good enough for a single-hop
LAN where packet loss is negligible (iPad, second Mac, Raspberry Pi, etc.).

Packet layout (per tick, 3-byte MIDI example):
  [ RTP header 12 bytes ][ MIDI command section 1 byte ][ MIDI payload 3 bytes ]
  = 16 bytes total for a 3-byte message like CC or Note-On.

RTP header fields used:
  V=2  P=0  X=0  CC=0  M=0  PT=97 (dynamic, RTP-MIDI convention)
  sequence (16-bit, auto-increments)
  timestamp (32-bit, wraps; sourced from perf_counter so receivers can
             compute jitter but we don't need it for correctness)
  SSRC (32-bit, random per session — identifies this sender)

MIDI command section (simplified — no delta-time list):
  Bit 7 (B) = 0  (no journal)
  Bit 6 (J) = 0  (no journal)
  Bit 5 (Z) = 0  (delta-time not present on first message in section)
  Bit 4 (P) = 0  (no phantom)
  Bits 3–0  = length of MIDI payload (1–3 bytes)

Usage:
  sender = RtpMidiSender("192.168.1.42", 5004, "My Session")
  sender.start()
  sender.send_midi(0xB0, 7, 64)   # CC
  sender.stop()
"""
from __future__ import annotations

import random
import socket
import struct
import time
from typing import Optional


_RTP_VERSION = 2
_RTP_PAYLOAD_TYPE = 97   # RTP-MIDI convention


class RtpMidiSender:
    """UDP-based RTP-MIDI sender for a single peer.

    Thread-safe enough for the BridgeWorker pattern: start() and stop()
    are called from the QThread; send_midi() is called from the same
    poll loop, so no locking is needed.
    """

    def __init__(self, peer_host: str, peer_port: int,
                 session_name: str = "UCM Bridge") -> None:
        self.peer_host = peer_host
        self.peer_port = peer_port
        self.session_name = session_name

        self._sock: Optional[socket.socket] = None
        self._seq: int = random.randint(0, 0xFFFF)
        # 32-bit random SSRC — identifies this RTP stream to receivers.
        self._ssrc: int = random.randint(0, 0xFFFF_FFFF)
        # Reference wall-clock for RTP timestamps (1 kHz clock rate).
        self._ts_origin: float = time.perf_counter()

    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the UDP socket.  Idempotent — safe to call twice."""
        if self._sock is not None:
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Non-blocking so a send never stalls the poll loop.
        self._sock.setblocking(False)

    def stop(self) -> None:
        """Close the UDP socket.  Idempotent."""
        if self._sock is None:
            return
        try:
            self._sock.close()
        except OSError:
            pass
        self._sock = None

    # ------------------------------------------------------------------

    def send_midi(self, status: int, data1: int, data2: int) -> None:
        """Build one RTP-MIDI packet and send it via UDP.

        status / data1 / data2 are the raw MIDI bytes.  For 1-byte
        messages (e.g. 0xF8 clock) set data1=data2=0 and pass length
        in the payload instead — but the bridge only calls this for
        3-byte messages (CC, Note-On, Note-Off) so we always use 3 bytes.
        """
        if self._sock is None:
            return
        try:
            packet = self._build_packet(status, data1, data2)
            self._sock.sendto(packet, (self.peer_host, self.peer_port))
        except (OSError, BlockingIOError):
            # Non-fatal: LAN hiccup or buffer full — drop and continue.
            pass

    # ------------------------------------------------------------------

    def _build_packet(self, status: int, data1: int, data2: int) -> bytes:
        """Assemble the RTP + MIDI command section + MIDI payload."""
        self._seq = (self._seq + 1) & 0xFFFF

        # RTP timestamp: milliseconds since sender started (1 kHz resolution).
        ts = int((time.perf_counter() - self._ts_origin) * 1000) & 0xFFFF_FFFF

        # RTP header: 12 bytes.
        # Byte 0: V=2 P=0 X=0 CC=0  →  0b10_0_0_0000 = 0x80
        # Byte 1: M=0 PT=97          →  0b0_1100001  = 0x61
        rtp_header = struct.pack(
            "!BBHII",
            0x80,               # V=2, P=0, X=0, CC=0
            0x61,               # M=0, PT=97
            self._seq,          # sequence number
            ts,                 # timestamp
            self._ssrc,         # SSRC
        )

        # MIDI command section header: 1 byte (B=0 J=0 Z=0 P=0 LEN=3).
        midi_len = 3
        cmd_section = struct.pack("B", midi_len & 0x0F)

        # MIDI payload: 3 bytes (status, data1, data2).
        midi_payload = struct.pack("BBB", status & 0xFF, data1 & 0x7F, data2 & 0x7F)

        return rtp_header + cmd_section + midi_payload

    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._sock is not None
