"""Minimal OSC 1.0 sender — UDP only, no bundles.

OSC is the richer alternative to MIDI for Resolume / TouchDesigner /
MadMapper. Every parameter in those apps has an addressable OSC path
(`/composition/layers/1/video/opacity` etc.) so a single OSC message
moves a single named target without the user wiring MIDI Learn.

We implement just enough of OSC to send `float`, `int`, and `string`
arguments — covers ~100% of VJ/DAW control surfaces.

Spec: https://opensoundcontrol.stanford.edu/spec-1_0.html
"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from typing import Optional, Sequence, Union


OscValue = Union[int, float, str]


@dataclass
class OscSender:
    """One-shot UDP sender. Cheap to construct, safe to recreate per send."""

    host: str = "127.0.0.1"
    port: int = 7000          # Resolume's default OSC input port

    def __post_init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        try:
            self._sock.close()
        except Exception:
            pass

    def send(self, address: str, *args: OscValue) -> bool:
        """Build + fire an OSC message. Returns True on success."""
        try:
            packet = _build_message(address, args)
            self._sock.sendto(packet, (self.host, self.port))
            return True
        except Exception:
            return False


# --------------------------------------------------------------- packet building


def _pad4(b: bytes) -> bytes:
    """OSC strings + blobs pad to a 4-byte boundary with NULLs."""
    return b + b"\x00" * (-len(b) % 4)


def _build_message(address: str, args: Sequence[OscValue]) -> bytes:
    # OSC address: null-terminated string, padded to 4 bytes.
    addr = _pad4(address.encode("utf-8") + b"\x00")

    type_tags = b","
    payload = b""
    for arg in args:
        if isinstance(arg, bool):
            type_tags += b"T" if arg else b"F"
            # No payload bytes for booleans in OSC 1.0; tag only.
        elif isinstance(arg, int):
            type_tags += b"i"
            payload += struct.pack(">i", arg)
        elif isinstance(arg, float):
            type_tags += b"f"
            payload += struct.pack(">f", arg)
        elif isinstance(arg, str):
            type_tags += b"s"
            payload += _pad4(arg.encode("utf-8") + b"\x00")
        else:
            raise TypeError(f"Unsupported OSC arg type: {type(arg).__name__}")

    return addr + _pad4(type_tags + b"\x00") + payload


# --------------------------------------------------------------- self-check

if __name__ == "__main__":
    # Spec sanity — round-trip-check packet shape against a known fixture.
    pkt = _build_message("/test", (1.5,))
    # /test\0\0\0 (8B) + ",f\0\0" (4B) + float 1.5 (4B) = 16 bytes total
    assert len(pkt) == 16, f"unexpected packet length {len(pkt)}"
    print(f"OK packet for /test 1.5 = {pkt.hex()}")

    pkt2 = _build_message("/composition/tempocontroller/tempo", (128.0,))
    print(f"Resolume tempo packet ({len(pkt2)}B) = {pkt2.hex()}")
