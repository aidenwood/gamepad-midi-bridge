"""Minimal OSC 1.0 sender + receiver — UDP only, no bundles.

OSC is the richer alternative to MIDI for Resolume / TouchDesigner /
MadMapper. Every parameter in those apps has an addressable OSC path
(`/composition/layers/1/video/opacity` etc.) so a single OSC message
moves a single named target without the user wiring MIDI Learn.

We implement just enough of OSC to send `float`, `int`, and `string`
arguments — covers ~100% of VJ/DAW control surfaces.

OscReceiver (feature #16) listens on a UDP port and dispatches incoming
messages to a registered callback. Uses stdlib only — no python-osc dep.

Spec: https://opensoundcontrol.stanford.edu/spec-1_0.html
"""
from __future__ import annotations

import socket
import struct
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple, Union


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

    def ping(self) -> bool:
        """Send a `/gmb/ping` discovery message. Useful from the GUI as a
        'is anything listening on this port' button — Resolume's OSC
        monitor or TouchDesigner's OSC In CHOP will surface it as a
        named address, confirming the route.
        """
        return self.send("/gmb/ping", 1)


# --------------------------------------------------------------- OSC receiver

# Callback type: (address: str, args: List[Union[int, float, str]]) -> None
OscCallback = Callable[[str, List[Union[int, float, str]]], None]


@dataclass
class OscReceiver:
    """UDP listener that parses incoming OSC 1.0 datagrams and dispatches them.

    Spawns a single daemon thread on `start()`. The thread loops on
    `socket.recvfrom(4096)` with a short timeout so `stop()` returns promptly.
    Uses stdlib only — no python-osc dependency.
    """

    port: int = 7001
    _callback: Optional[OscCallback] = None
    _sock: Optional[socket.socket] = None
    _thread: Optional[threading.Thread] = None
    _running: bool = False

    def set_callback(self, cb: OscCallback) -> None:
        self._callback = cb

    def start(self) -> None:
        if self._running:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.port))
        sock.settimeout(0.1)   # 100 ms — keeps stop() responsive
        self._sock = sock
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name=f"osc-recv-{self.port}")
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._running = False
        # Close the socket so recvfrom unblocks immediately on all platforms.
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---------------------------------------------------------------- internals

    def _loop(self) -> None:
        while self._running:
            sock = self._sock
            if sock is None:
                break
            try:
                data, _addr = sock.recvfrom(4096)
            except OSError:
                # Socket closed (stop() called) or timeout — both are fine.
                break
            except Exception:
                continue
            try:
                address, args = _parse_message(data)
            except Exception:
                continue
            cb = self._callback
            if cb is not None:
                try:
                    cb(address, args)
                except Exception:
                    pass


# --------------------------------------------------------------- OSC parsing


def _read_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Read a null-terminated, 4-byte-aligned OSC string starting at offset.

    Returns (string, new_offset).
    """
    end = data.index(b"\x00", offset)
    s = data[offset:end].decode("utf-8", errors="replace")
    # Advance past the null and any padding to the next 4-byte boundary
    padded = end + 1
    padded = padded + (-padded % 4)
    return s, padded


def _parse_message(data: bytes) -> Tuple[str, List[Union[int, float, str]]]:
    """Parse a minimal OSC 1.0 datagram.

    Supports type tags: i (int32), f (float32), s (string), T (True), F (False).
    Unknown tags are silently skipped (no payload consumed for them — callers
    that need strict compliance should filter on address first).

    Returns (address, args_list).
    Raises ValueError on obviously malformed packets.
    """
    if len(data) < 8:
        raise ValueError("Datagram too short to be a valid OSC message")
    address, offset = _read_string(data, 0)
    if not address.startswith("/"):
        raise ValueError(f"OSC address must start with '/': {address!r}")

    # Type tag string — starts with ','
    if offset >= len(data):
        return address, []
    type_str, offset = _read_string(data, offset)
    if not type_str.startswith(","):
        raise ValueError(f"OSC type tag must start with ',': {type_str!r}")

    tags = type_str[1:]   # strip leading ','
    args: List[Union[int, float, str]] = []
    for tag in tags:
        if tag == "i":
            if offset + 4 > len(data):
                break
            (val,) = struct.unpack_from(">i", data, offset)
            args.append(val)
            offset += 4
        elif tag == "f":
            if offset + 4 > len(data):
                break
            (val,) = struct.unpack_from(">f", data, offset)
            args.append(float(val))
            offset += 4
        elif tag == "s":
            val, offset = _read_string(data, offset)
            args.append(val)
        elif tag == "T":
            args.append(True)
        elif tag == "F":
            args.append(False)
        # Unknown/unsupported tags — skip without consuming payload.
        # For tags with a fixed payload size we'd need a size table; for
        # now we just stop parsing args on the first unknown tag.
        else:
            break
    return address, args


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
