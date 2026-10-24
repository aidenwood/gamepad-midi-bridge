"""Host handshake — turning "the app is running" into "the app is connected".

`liveness.py` can tell you a host process exists. It cannot tell you that host
has opened our port and is listening, which is the thing a performer actually
wants to know before a set. Process detection would happily show green for an
Ableton that has our Remote Script installed, is running, and has the control
surface set to None.

This is the protocol for closing that gap: the host-side integration sends a
small SysEx heartbeat on our input port, and anything that receives it knows —
rather than infers — that the integration is loaded and talking.

    F0  7D  'U' 'C' 'M'  <host>  <major> <minor>  F7

0x7D is the SysEx manufacturer ID reserved for non-commercial and prototype
use, which is exactly what a private app-to-app heartbeat is. Using a real
manufacturer ID we do not own would be squatting on someone's identifier.

Pure stdlib: no Qt, no MIDI I/O, no clock of its own — the caller supplies
timestamps. That keeps it testable without a DAW, and keeps it off the hot
rtmidi callback thread's conscience.

WIRED as of 2026-10-24. `midi_input._filter_message_types` now passes SysEx
through (`sysex=False`) while still ignoring clock and active-sense, and
`BridgeWorker._on_midi_in` feeds every inbound message to a `HeartbeatTracker`.

That feed runs on librtmidi's C thread, which the bridge comments are explicit
must stay non-blocking — so the hot path does exactly two things: a cheap
first-byte check for 0xF0, then `tracker.feed()`, which is a dict write. No
lock, no allocation beyond the parse, no I/O. `feed()` is also total: it returns
None for anything that is not our heartbeat, and `parse()` is exhaustively
fuzzed against malformed input in tests/test_connector_handshake.py, because
this now sees every SysEx byte any host on the system decides to send.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SYSEX_START = 0xF0
SYSEX_END = 0xF7

#: Non-commercial / prototype manufacturer ID.
MANUFACTURER_NON_COMMERCIAL = 0x7D

#: "UCM" — identifies the heartbeat as ours rather than any other 0x7D traffic.
MAGIC = (0x55, 0x43, 0x4D)

#: Host identifiers. Values are frozen once shipped: an integration in the
#: wild keeps sending the number it was built with, so renumbering would make
#: an older Remote Script report as a different host.
HOST_IDS: dict[int, str] = {
    0x01: "ableton",
    0x02: "resolume",
    0x03: "touchdesigner",
    0x04: "madmapper",
    0x05: "vdmx",
    0x06: "obs",
    0x07: "reaper",
}
_SLUG_TO_ID = {slug: hid for hid, slug in HOST_IDS.items()}

#: How long a heartbeat stays valid. Live calls update_display about ten times
#: a second, so three seconds tolerates a stall without claiming a host that
#: has quit is still there.
DEFAULT_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class Heartbeat:
    """A decoded heartbeat."""

    slug: str
    major: int
    minor: int

    @property
    def version(self) -> str:
        return f"{self.major}.{self.minor}"


def heartbeat_bytes(slug: str, major: int = 1, minor: int = 0) -> list[int]:
    """The exact bytes a host integration should send.

    Raises ValueError for an unknown slug rather than emitting a heartbeat
    nothing can decode.
    """
    host_id = _SLUG_TO_ID.get(slug)
    if host_id is None:
        raise ValueError(f"unknown host slug: {slug!r}")
    for value, name in ((major, "major"), (minor, "minor")):
        if not 0 <= value <= 127:
            raise ValueError(f"{name} must fit in a MIDI data byte: {value}")
    return [SYSEX_START, MANUFACTURER_NON_COMMERCIAL, *MAGIC,
            host_id, major, minor, SYSEX_END]


def parse(message: list[int] | tuple[int, ...] | bytes) -> Heartbeat | None:
    """Decode a heartbeat, or None if this is not one.

    Returns None rather than raising for anything unrecognised: this runs on
    whatever arrives at the input port, most of which is other people's MIDI.
    """
    data = list(message)
    if len(data) != 9:
        return None
    if data[0] != SYSEX_START or data[-1] != SYSEX_END:
        return None
    if data[1] != MANUFACTURER_NON_COMMERCIAL:
        return None
    if tuple(data[2:5]) != MAGIC:
        return None
    slug = HOST_IDS.get(data[5])
    if slug is None:
        return None
    return Heartbeat(slug=slug, major=data[6], minor=data[7])


@dataclass
class HeartbeatTracker:
    """Remembers when each host was last heard from.

    The caller supplies `now` on every call — no internal clock, so tests can
    step time without sleeping and the hot MIDI thread never reads one.
    """

    timeout: float = DEFAULT_TIMEOUT_SECONDS
    _last_seen: dict[str, float] = field(default_factory=dict)
    _last_version: dict[str, str] = field(default_factory=dict)

    def record(self, heartbeat: Heartbeat, now: float) -> None:
        self._last_seen[heartbeat.slug] = now
        self._last_version[heartbeat.slug] = heartbeat.version

    def feed(self, message, now: float) -> Heartbeat | None:
        """Parse and record in one step. Returns the heartbeat if it was one."""
        hb = parse(message)
        if hb is not None:
            self.record(hb, now)
        return hb

    def is_connected(self, slug: str, now: float) -> bool:
        """True when a heartbeat for `slug` arrived within the timeout."""
        last = self._last_seen.get(slug)
        if last is None:
            return False
        return (now - last) <= self.timeout

    def version_of(self, slug: str) -> str | None:
        """Integration version last reported, for a mismatch warning later."""
        return self._last_version.get(slug)

    def seconds_since(self, slug: str, now: float) -> float | None:
        last = self._last_seen.get(slug)
        return None if last is None else now - last

    def forget(self, slug: str) -> None:
        """Drop a host — used when its port closes, so a stale timestamp
        cannot keep a light green after an explicit disconnect."""
        self._last_seen.pop(slug, None)
        self._last_version.pop(slug, None)

    def connected_hosts(self, now: float) -> list[str]:
        return sorted(s for s in self._last_seen if self.is_connected(s, now))
