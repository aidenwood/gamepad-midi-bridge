"""The 30 Hz UI throttle must not swallow an axis's final sample.

Observed as triggers rendering solid-green at rest for an entire session,
including during the "keep your hands off the controller" calibration modal.
Not a wrong axis index and not an inverted range — a stale paint.

The poll loop runs at 100 Hz, the UI throttle at 30 Hz, and the caller
updates `_prev_cc` on every change, so a dropped sample is never re-sent. A
spring-loaded trigger returns to rest in 20-40 ms, which fits inside one
33 ms window: the last value the UI ever saw was the full-press one.
"""
from __future__ import annotations

import pytest


class _Recorder:
    """Stands in for the Qt signal — this layer is pure bookkeeping."""

    def __init__(self):
        self.sent = []

    def emit(self, idx, value):
        self.sent.append((idx, value))


@pytest.fixture()
def worker():
    """A BridgeWorker with only the telemetry fields the code under test uses.

    Constructing a real one would start a controller and a MIDI port.
    """
    from gamepad_midi_bridge.bridge import BridgeWorker

    w = BridgeWorker.__new__(BridgeWorker)
    w._last_telemetry = {}
    w._telemetry_interval = 1.0 / 30.0
    w._pending_axis = {}
    w.axis_value = _Recorder()
    return w


def test_first_sample_is_emitted_immediately(worker):
    worker._emit_axis(4, 1.0)
    assert worker.axis_value.sent == [(4, 1.0)]


def test_a_throttled_sample_is_parked_not_dropped(worker):
    worker._emit_axis(4, 1.0)
    worker._emit_axis(4, -1.0)          # inside the 33 ms window
    assert worker.axis_value.sent == [(4, 1.0)]
    assert worker._pending_axis[4] == -1.0


def test_the_parked_sample_is_flushed_once_the_window_passes(worker):
    worker._emit_axis(4, 1.0)
    worker._emit_axis(4, -1.0)
    worker._last_telemetry[4] -= 1.0    # pretend the window elapsed
    worker._flush_pending_axes()
    assert worker.axis_value.sent[-1] == (4, -1.0)
    assert worker._pending_axis == {}


def test_release_inside_one_window_still_reaches_the_ui(worker):
    """The exact reported failure: full press then fast release."""
    worker._emit_axis(5, 1.0)
    for v in (0.6, 0.2, -0.4, -1.0):    # whole release inside one window
        worker._emit_axis(5, v)
    assert worker.axis_value.sent == [(5, 1.0)]
    worker._last_telemetry[5] -= 1.0
    worker._flush_pending_axes()
    assert worker.axis_value.sent[-1] == (5, -1.0), "meter would stay at full travel"


def test_only_the_newest_parked_value_survives(worker):
    """Flushing must not replay a backlog of stale intermediate samples."""
    worker._emit_axis(0, 0.0)
    for v in (0.1, 0.2, 0.3):
        worker._emit_axis(0, v)
    assert worker._pending_axis[0] == 0.3
    worker._last_telemetry[0] -= 1.0
    worker._flush_pending_axes()
    assert worker.axis_value.sent == [(0, 0.0), (0, 0.3)]


def test_axes_throttle_independently(worker):
    worker._emit_axis(0, 0.5)
    worker._emit_axis(1, 0.5)
    assert worker.axis_value.sent == [(0, 0.5), (1, 0.5)]


def test_flush_is_a_noop_when_nothing_is_parked(worker):
    worker._emit_axis(2, 0.5)
    worker._flush_pending_axes()
    assert worker.axis_value.sent == [(2, 0.5)]


def test_an_emitted_sample_clears_any_parked_one(worker):
    worker._emit_axis(3, 0.1)
    worker._emit_axis(3, 0.2)           # parked
    worker._last_telemetry[3] -= 1.0
    worker._emit_axis(3, 0.9)           # window open again
    assert worker._pending_axis == {}
    assert worker.axis_value.sent[-1] == (3, 0.9)
