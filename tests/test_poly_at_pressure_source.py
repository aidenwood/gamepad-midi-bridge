"""Pressure-source normalisation for poly aftertouch.

``BridgeWorker._get_poly_at_pressure`` turns a controller reading into the
0..1 value that drives poly aftertouch. It had two bugs that only show up
on real hardware:

* **Triggers.** SDL reports a trigger as ``-1.0`` released through ``+1.0``
  fully pressed. The old code clamped that to ``0..1``, so the entire bottom
  half of the trigger travel produced 0 — aftertouch stayed dead until the
  trigger was already half down, then jumped. Every other trigger path in
  bridge.py goes through ``shaping.normalise_trigger_pressure``; this one
  did not.
* **Sticks.** A full diagonal has magnitude 1.414, which was returned
  unclamped and pushed the aftertouch value past 127.
"""
from __future__ import annotations

import pytest


class _FakeReader:
    """Minimal ControllerReader stand-in — canonical axes only."""

    def __init__(self, axes):
        self._axes = axes

    def get_axis(self, idx: int) -> float:
        return self._axes.get(idx, 0.0)


@pytest.fixture
def pressure():
    from gamepad_midi_bridge.bridge import BridgeWorker
    return BridgeWorker._get_poly_at_pressure


@pytest.mark.parametrize("raw,expected", [
    (-1.0, 0.0),    # released
    (-0.5, 0.25),   # quarter — used to read 0.0
    (0.0, 0.5),     # halfway — used to read 0.0
    (0.5, 0.75),
    (1.0, 1.0),     # fully pressed
])
def test_trigger_uses_the_full_travel(pressure, raw, expected):
    for axis, source in ((4, "l2"), (5, "r2")):
        reader = _FakeReader({axis: raw})
        assert pressure(None, reader, source) == pytest.approx(expected)


def test_trigger_at_rest_is_silent(pressure):
    """The fix must not turn a resting trigger into constant pressure."""
    assert pressure(None, _FakeReader({4: -1.0}), "l2") == 0.0
    assert pressure(None, _FakeReader({5: -1.0}), "r2") == 0.0


def test_stick_magnitude_never_exceeds_one(pressure):
    """A full diagonal is 1.414 — unclamped it overflows the MIDI range."""
    diagonal = _FakeReader({0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0})
    assert pressure(None, diagonal, "left_stick_mag") == 1.0
    assert pressure(None, diagonal, "right_stick_mag") == 1.0


def test_stick_magnitude_is_unchanged_below_the_clamp(pressure):
    reader = _FakeReader({0: 0.6, 1: 0.0, 2: 0.0, 3: 0.8})
    assert pressure(None, reader, "left_stick_mag") == pytest.approx(0.6)
    assert pressure(None, reader, "right_stick_mag") == pytest.approx(0.8)


def test_unknown_source_is_zero(pressure):
    assert pressure(None, _FakeReader({}), "nonsense") == 0.0
