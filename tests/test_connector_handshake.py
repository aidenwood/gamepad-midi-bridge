"""Tests for the host handshake.

The one that matters most is test_remote_script_bytes_match_the_protocol: the
Ableton Remote Script hardcodes its heartbeat as a literal tuple, because it
runs inside Live and cannot import from this package. If those bytes and
handshake.py ever drift, nothing errors — the heartbeat simply stops being
recognised and the status light quietly falls back to inference forever.
"""

import re
from pathlib import Path

import pytest

from gamepad_midi_bridge.connectors import handshake as H

REMOTE_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "src" / "gamepad_midi_bridge" / "connectors" / "templates"
    / "ableton_remote_script" / "Universal Controller MIDI"
    / "GamepadMidiBridge.py"
)


class TestEncoding:
    def test_round_trips(self):
        for slug in H.HOST_IDS.values():
            hb = H.parse(H.heartbeat_bytes(slug, 2, 7))
            assert hb is not None
            assert hb.slug == slug
            assert hb.version == "2.7"

    def test_uses_the_non_commercial_manufacturer_id(self):
        """Squatting on a real manufacturer's ID would be someone else's."""
        assert H.heartbeat_bytes("ableton")[1] == 0x7D

    def test_is_a_well_formed_sysex(self):
        data = H.heartbeat_bytes("resolume")
        assert data[0] == 0xF0
        assert data[-1] == 0xF7
        assert all(0 <= b <= 0xFF for b in data)
        # Every byte between the delimiters must be a 7-bit data byte.
        assert all(b <= 0x7F for b in data[1:-1])

    def test_unknown_slug_raises(self):
        with pytest.raises(ValueError):
            H.heartbeat_bytes("not_a_host")

    @pytest.mark.parametrize("bad", [-1, 128, 999])
    def test_version_must_fit_a_data_byte(self, bad):
        with pytest.raises(ValueError):
            H.heartbeat_bytes("ableton", bad, 0)

    def test_host_ids_are_unique(self):
        assert len(set(H.HOST_IDS)) == len(H.HOST_IDS)
        assert len(set(H.HOST_IDS.values())) == len(H.HOST_IDS)


class TestParsingIsDefensive:
    """This runs against whatever arrives on the port, most of which is
    other people's MIDI. It must never raise."""

    @pytest.mark.parametrize("junk", [
        [],
        [0x90, 60, 100],                      # a note on
        [0xF0, 0xF7],                         # empty sysex
        [0xF0, 0x7E, 0x55, 0x43, 0x4D, 1, 1, 0, 0xF7],   # wrong manufacturer
        [0xF0, 0x7D, 0x00, 0x00, 0x00, 1, 1, 0, 0xF7],   # wrong magic
        [0xF0, 0x7D, 0x55, 0x43, 0x4D, 0x7F, 1, 0, 0xF7],  # unknown host id
        [0xF0, 0x7D, 0x55, 0x43, 0x4D, 1, 1, 0],           # truncated
        [0xF0, 0x7D, 0x55, 0x43, 0x4D, 1, 1, 0, 0xF7, 0],  # too long
    ])
    def test_non_heartbeats_return_none(self, junk):
        assert H.parse(junk) is None

    def test_accepts_bytes_and_tuples_too(self):
        data = H.heartbeat_bytes("ableton")
        assert H.parse(tuple(data)) is not None
        assert H.parse(bytes(data)) is not None


class TestTracker:
    def test_unknown_host_is_not_connected(self):
        assert H.HeartbeatTracker().is_connected("ableton", 100.0) is False

    def test_connected_right_after_a_heartbeat(self):
        t = H.HeartbeatTracker()
        t.feed(H.heartbeat_bytes("ableton"), now=100.0)
        assert t.is_connected("ableton", 100.0) is True

    def test_still_connected_inside_the_timeout(self):
        t = H.HeartbeatTracker(timeout=3.0)
        t.feed(H.heartbeat_bytes("ableton"), now=100.0)
        assert t.is_connected("ableton", 102.9) is True

    def test_disconnects_after_the_timeout(self):
        """A host that quits must not leave the light green."""
        t = H.HeartbeatTracker(timeout=3.0)
        t.feed(H.heartbeat_bytes("ableton"), now=100.0)
        assert t.is_connected("ableton", 103.1) is False

    def test_hosts_are_tracked_separately(self):
        t = H.HeartbeatTracker()
        t.feed(H.heartbeat_bytes("ableton"), now=100.0)
        assert t.is_connected("ableton", 100.0) is True
        assert t.is_connected("resolume", 100.0) is False

    def test_feed_ignores_junk(self):
        t = H.HeartbeatTracker()
        assert t.feed([0x90, 60, 100], now=100.0) is None
        assert t.connected_hosts(100.0) == []

    def test_records_the_version(self):
        t = H.HeartbeatTracker()
        t.feed(H.heartbeat_bytes("resolume", 3, 4), now=1.0)
        assert t.version_of("resolume") == "3.4"

    def test_forget_drops_it_immediately(self):
        """An explicit port close must not be outlived by a timestamp."""
        t = H.HeartbeatTracker()
        t.feed(H.heartbeat_bytes("ableton"), now=100.0)
        t.forget("ableton")
        assert t.is_connected("ableton", 100.0) is False

    def test_connected_hosts_lists_only_live_ones(self):
        t = H.HeartbeatTracker(timeout=3.0)
        t.feed(H.heartbeat_bytes("ableton"), now=100.0)
        t.feed(H.heartbeat_bytes("resolume"), now=90.0)
        assert t.connected_hosts(101.0) == ["ableton"]


class TestRemoteScriptStaysInSync:
    """The Remote Script runs inside Live and cannot import this package, so
    it hardcodes the bytes. Drift would not error — the heartbeat would just
    stop being recognised and the status would silently fall back forever."""

    def test_remote_script_exists(self):
        assert REMOTE_SCRIPT.is_file()

    def test_remote_script_bytes_match_the_protocol(self):
        src = REMOTE_SCRIPT.read_text()
        match = re.search(r"_HEARTBEAT\s*=\s*\(([^)]*)\)", src)
        assert match, "no _HEARTBEAT tuple found in the Remote Script"

        literal = [int(tok.strip(), 0) for tok in match.group(1).split(",") if tok.strip()]
        expected = H.heartbeat_bytes("ableton", 1, 0)
        assert literal == expected, (
            f"Remote Script sends {literal}, protocol expects {expected}"
        )

    def test_the_hardcoded_bytes_actually_parse(self):
        src = REMOTE_SCRIPT.read_text()
        match = re.search(r"_HEARTBEAT\s*=\s*\(([^)]*)\)", src)
        literal = [int(tok.strip(), 0) for tok in match.group(1).split(",") if tok.strip()]
        hb = H.parse(literal)
        assert hb is not None and hb.slug == "ableton"

    def test_heartbeat_interval_is_inside_the_timeout(self):
        """Sending less often than the timeout would flap the light."""
        src = REMOTE_SCRIPT.read_text()
        match = re.search(r"_HEARTBEAT_INTERVAL\s*=\s*([0-9.]+)", src)
        assert match, "no _HEARTBEAT_INTERVAL found"
        assert float(match.group(1)) < H.DEFAULT_TIMEOUT_SECONDS

    def test_heartbeat_send_is_guarded(self):
        """A status heartbeat must never take Live's control surface down."""
        src = REMOTE_SCRIPT.read_text()
        block = src[src.index("def update_display"):]
        assert "try:" in block[:400] and "except Exception" in block[:700]
