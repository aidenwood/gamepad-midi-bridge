"""The handshake is only useful if SysEx can actually reach it.

`connectors/handshake.py` was fully implemented and fully unit-tested on
2026-10-24 and still did nothing, because `midi_input` called
`ignore_types(sysex=True, ...)` — rtmidi dropped every heartbeat before any of
our code ran. Nothing failed; the status simply stayed inferred forever.

These tests cover the join between the two halves, which is exactly the part
that unit tests of either half cannot see:

  1. the input port is configured to deliver SysEx (and still drops clock)
  2. the bridge's rtmidi callback feeds heartbeats to its tracker
  3. a non-heartbeat SysEx from some other app does not crash the hot path
  4. `connected_hosts()` reflects what arrived, and times out on its own
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gamepad_midi_bridge import midi_input
from gamepad_midi_bridge.connectors import handshake as H


class TestInputPortDeliversSysEx:
    def test_sysex_is_not_ignored(self):
        """The whole bug in one assertion."""
        inp = MagicMock()
        midi_input._filter_message_types(inp)
        _, kwargs = inp.ignore_types.call_args
        assert kwargs["sysex"] is False

    def test_clock_and_active_sense_are_still_ignored(self):
        """Enabling SysEx must not reopen the timing firehose."""
        inp = MagicMock()
        midi_input._filter_message_types(inp)
        _, kwargs = inp.ignore_types.call_args
        assert kwargs["timing"] is True
        assert kwargs["active_sense"] is True

    def test_every_open_path_uses_the_one_filter(self):
        """Two call sites copy-pasting the same line is how they drift."""
        src = (
            midi_input.__file__
            and open(midi_input.__file__, encoding="utf-8").read()
        )
        # Match real call sites (`inp.ignore_types(`), not prose — the helper's
        # own docstring refers to `ignore_types(...)` when explaining the bug.
        assert src.count("inp.ignore_types(") == 1
        # Trailing newline keeps `def _filter_message_types(inp) -> None:` out
        # of the count — it contains the call text as a substring.
        assert src.count("_filter_message_types(inp)\n") == 2


@pytest.fixture()
def worker():
    from gamepad_midi_bridge.bridge import BridgeWorker

    return BridgeWorker(demo=True)


class TestBridgeFeedsTheTracker:
    def test_heartbeat_marks_the_host_connected(self, worker):
        worker._on_midi_in((H.heartbeat_bytes("ableton"), 0.0), None)
        assert "ableton" in worker.connected_hosts()

    def test_version_is_recorded(self, worker):
        worker._on_midi_in((H.heartbeat_bytes("resolume", 3, 4), 0.0), None)
        assert worker.host_version("resolume") == "3.4"

    def test_nothing_connected_by_default(self, worker):
        assert worker.connected_hosts() == []

    def test_hosts_are_tracked_separately(self, worker):
        worker._on_midi_in((H.heartbeat_bytes("ableton"), 0.0), None)
        hosts = worker.connected_hosts()
        assert "ableton" in hosts
        assert "resolume" not in hosts

    def test_a_quit_host_goes_dark(self, worker):
        """A host that stops sending must not leave the light green."""
        worker._on_midi_in((H.heartbeat_bytes("ableton"), 0.0), None)
        assert worker.connected_hosts() != []
        # Rewind the recorded timestamp past the timeout rather than sleeping.
        worker._host_beats._last_seen["ableton"] -= H.DEFAULT_TIMEOUT_SECONDS + 1
        assert worker.connected_hosts() == []


class TestHotPathSurvivesOtherPeoplesSysEx:
    """This callback now sees every SysEx byte anything on the system sends."""

    @pytest.mark.parametrize(
        "junk",
        [
            [0xF0, 0xF7],                                   # empty sysex
            [0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7],           # universal identity request
            [0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0xF7],  # a Yamaha dump
            [0xF0, 0x7D, 0x55, 0x43, 0x4D, 0x7F, 1, 0, 0xF7],  # our ID, unknown host
            [0xF0] + [0x20] * 500 + [0xF7],                  # a large dump
        ],
    )
    def test_foreign_sysex_is_ignored_without_raising(self, worker, junk):
        worker._on_midi_in((junk, 0.0), None)
        assert worker.connected_hosts() == []

    def test_a_note_still_works_after_sysex(self, worker):
        """The 0xF0 early-return must not swallow ordinary messages."""
        worker._on_midi_in(([0xF0, 0x7E, 0xF7], 0.0), None)
        # A note-on must still reach the normal path — it raises nothing and
        # leaves the host tracker alone.
        worker._on_midi_in(([0x90, 60, 100], 0.0), None)
        assert worker.connected_hosts() == []
