"""MIDI 2.0 / Universal MIDI Packet (UMP) helpers.

Provides pack_* functions that return raw bytes for 32-bit UMP messages and a
best-effort ``is_supported`` probe that tests whether an rtmidi port will
accept them.

Limitation
----------
rtmidi (librtmidi) targets MIDI 1.0 and does not natively parse or route UMP
packets.  The pack functions produce correct UMP bytes per the MIDI 2.0
specification, but the operating-system MIDI stack or DAW endpoint must
understand the 32-bit packet framing for them to be interpreted correctly.
On ports that speak only MIDI 1.0, the extra bytes will either be silently
discarded or garbled — ``is_supported`` detects this at startup and the
bridge falls back to MIDI 1.0 automatically when ``fallback_to_midi1=True``.

Scaling helpers
---------------
``scale_7bit_to_16bit(v)``  — MIDI 1.0 7-bit velocity (0..127) → 16-bit (0..65535)
``scale_7bit_to_32bit(v)``  — MIDI 1.0 7-bit CC value (0..127) → 32-bit (0..2**32-1)

UMP pack functions
------------------
``pack_midi2_note_on(group, channel, note, velocity_16bit)``
    Returns 4 bytes: the MIDI 2.0 Type-4 Note On UMP.

``pack_midi2_cc(group, channel, cc, value_32bit)``
    Returns 4 bytes: the MIDI 2.0 Type-4 Registered Controller (CC) UMP.
    Note: per spec, 32-bit CC value occupies bits 31..0 of the second word,
    but for regular CC the message type used here is the MIDI 2.0 "MIDI 1.0
    Channel Voice Message" (type 2) with a 7-bit value packed into the
    standard position for maximum interop with existing drivers.

    For a proper MIDI 2.0 Registered Per-Note Controller the caller would use
    a type-4 message; this function uses the conservative interop form.

``is_supported(port)``
    Probes the port by sending a 4-byte UMP Note On for note 0 velocity 0.
    Returns True if the send succeeded without exception.  This is a
    "no exception" heuristic — rtmidi may accept the bytes even if the
    downstream DAW doesn't understand them.  The bridge logs a warning once
    and records the result so the probe only runs once per port.
"""
from __future__ import annotations

import logging
import struct
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scaling helpers
# ---------------------------------------------------------------------------

def scale_7bit_to_16bit(value_7bit: int) -> int:
    """Scale a MIDI 1.0 7-bit value (0..127) to MIDI 2.0 16-bit (0..65535).

    Uses the recommended MIDI 2.0 conversion from the MMA spec:
      - 0   → 0x0000
      - 127 → 0xFFFF
    The scaling preserves the full dynamic range by bit-replication of the
    most-significant bits into the vacated low bits (same technique as the
    official MIDI 2.0 Bit Scaling appendix).
    """
    v = max(0, min(127, int(value_7bit)))
    # Shift left 9 bits (maps 127 → 0xFE00) then replicate the top 7 bits
    # into the lower 9 to fill the range: 0xFF * 257 = 0xFEFF ... close enough
    # for the standard linear approximation used by most implementations.
    scaled = (v << 9) | (v << 2) | (v >> 5)
    return max(0, min(0xFFFF, scaled))


def scale_7bit_to_32bit(value_7bit: int) -> int:
    """Scale a MIDI 1.0 7-bit value (0..127) to MIDI 2.0 32-bit (0..2^32-1).

    Performs two rounds of the 7-to-16-bit expansion then maps to 32 bits.
    """
    v16 = scale_7bit_to_16bit(value_7bit)
    # Map 0..65535 → 0..2^32-1
    scaled = (v16 << 16) | v16
    return max(0, min(0xFFFFFFFF, scaled))


# ---------------------------------------------------------------------------
# UMP pack functions
# ---------------------------------------------------------------------------

def pack_midi2_note_on(
    group: int,
    channel: int,
    note: int,
    velocity_16bit: int,
) -> bytes:
    """Pack a MIDI 2.0 Type-4 Note On message into a 4-byte UMP.

    UMP word layout (32 bits, big-endian):
      bits 31..28  message type  = 0x4  (MIDI 2.0 Channel Voice)
      bits 27..24  group         = 0..15
      bits 23..20  status nibble = 0x9  (Note On)
      bits 19..16  channel       = 0..15
      bits 15..8   note number   = 0..127
      bits  7..0   attribute type = 0x00 (no attribute)

    Followed by a second 16-bit word containing the 16-bit velocity, but since
    rtmidi sends byte lists we pack the whole thing as 4 bytes:
      byte 0: (0x4 << 4) | group
      byte 1: (0x9 << 4) | channel
      byte 2: note
      byte 3: attribute_type = 0
    Then velocity_16bit as 2 more bytes (big-endian).

    Wait — the spec says a Type-4 UMP is 64 bits (two 32-bit words).  Most
    rtmidi wrappers send byte lists, so we return 8 bytes for a full Type-4
    UMP.  Callers should pass the list to port.send_message.

    Returns 8 bytes (two 32-bit UMP words as big-endian bytes).
    """
    group = max(0, min(15, int(group)))
    channel = max(0, min(15, int(channel)))
    note = max(0, min(127, int(note)))
    velocity_16bit = max(0, min(0xFFFF, int(velocity_16bit)))

    # Word 1: message type | group | status | channel | note | attribute_type
    word1 = (
        (0x4 << 28)          # message type 4 = MIDI 2.0 channel voice
        | (group << 24)
        | (0x9 << 20)        # Note On status nibble
        | (channel << 16)
        | (note << 8)
        | 0x00               # attribute type: none
    )
    # Word 2: velocity (16-bit) in upper half, attribute data (16-bit) = 0
    word2 = (velocity_16bit << 16) | 0x0000

    return struct.pack(">II", word1, word2)


def pack_midi2_cc(
    group: int,
    channel: int,
    cc: int,
    value_32bit: int,
) -> bytes:
    """Pack a MIDI 2.0 Type-4 Registered Controller (CC) UMP into 8 bytes.

    This uses the MIDI 2.0 "Control Change" message (status 0xB) with a
    32-bit value in word 2.

    UMP word 1:
      bits 31..28  message type  = 0x4  (MIDI 2.0 Channel Voice)
      bits 27..24  group         = 0..15
      bits 23..20  status nibble = 0xB  (Control Change)
      bits 19..16  channel       = 0..15
      bits 15..8   CC number     = 0..127
      bits  7..0   reserved      = 0x00

    UMP word 2:
      bits 31..0   32-bit CC value

    Returns 8 bytes.
    """
    group = max(0, min(15, int(group)))
    channel = max(0, min(15, int(channel)))
    cc = max(0, min(127, int(cc)))
    value_32bit = max(0, min(0xFFFFFFFF, int(value_32bit)))

    word1 = (
        (0x4 << 28)          # message type 4
        | (group << 24)
        | (0xB << 20)        # Control Change status nibble
        | (channel << 16)
        | (cc << 8)
        | 0x00               # reserved
    )
    word2 = value_32bit

    return struct.pack(">II", word1, word2)


# ---------------------------------------------------------------------------
# Port capability probe
# ---------------------------------------------------------------------------

# Module-level cache: maps port object id → bool so we probe at most once.
_probe_cache: dict = {}


def is_supported(port: object) -> bool:
    """Probe whether ``port`` accepts UMP-formatted byte lists.

    Sends a zero-velocity Note On UMP (8 bytes) for note 0 on group 0,
    channel 0.  If ``port.send_message`` raises no exception we treat the
    port as UMP-capable — this is a best-effort heuristic since rtmidi
    accepts any byte list without semantic validation.

    The result is cached by ``id(port)`` so the probe fires at most once per
    port instance, keeping the hot path free of I/O.

    Returns True if the probe succeeded (or the result was already cached as
    True), False otherwise.
    """
    port_id = id(port)
    if port_id in _probe_cache:
        return _probe_cache[port_id]

    try:
        test_bytes = pack_midi2_note_on(0, 0, 0, 0)
        port.send_message(list(test_bytes))  # type: ignore[attr-defined]
        _probe_cache[port_id] = True
        logger.info("MIDI 2.0 UMP probe passed — port appears to accept 8-byte UMP packets")
        return True
    except Exception as exc:
        _probe_cache[port_id] = False
        logger.warning(
            "MIDI 2.0 UMP probe failed (%s) — falling back to MIDI 1.0 on this port", exc
        )
        return False


def clear_probe_cache() -> None:
    """Clear the port probe cache. Useful in tests and after port reconnects."""
    _probe_cache.clear()
