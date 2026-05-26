"""CornerDetector hysteresis + sector quantization."""
from __future__ import annotations

import math

import pytest

from gamepad_midi_bridge.corner_quantizer import CornerDetector, decode_switch


def test_idle_until_r_enter():
    """Sub-threshold radius must never fire — protects against noise."""
    det = CornerDetector(n=4, r_enter=0.9, r_exit=0.5)
    assert det.update(0.0, 0.0) is None
    assert det.update(0.4, 0.4) is None      # r ~ 0.566
    assert det.update(0.6, 0.0) is None      # below r_enter
    assert det.active_sector is None


def test_four_cardinals_fire_distinct_sectors():
    """N=4 with the four cardinal directions hits sectors 0..3."""
    sectors = []
    for x, y in ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)):
        det = CornerDetector(n=4, r_enter=0.9, r_exit=0.5)
        ev = det.update(x, y)
        assert ev is not None and ev.kind == "on"
        sectors.append(ev.sector)
    assert sorted(sectors) == [0, 1, 2, 3]


def test_hysteresis_hold_then_release():
    """Enter at 0.95, stay active at 0.85, release at 0.5."""
    det = CornerDetector(n=4, r_enter=0.9, r_exit=0.6)
    on_ev = det.update(0.95, 0.0)
    assert on_ev is not None and on_ev.kind == "on"
    # In the hold-band: must NOT emit anything.
    assert det.update(0.85, 0.0) is None
    assert det.active_sector == on_ev.sector
    # Drop below r_exit -> "off".
    off_ev = det.update(0.3, 0.0)
    assert off_ev is not None and off_ev.kind == "off"
    assert off_ev.sector == on_ev.sector
    assert det.active_sector is None


def test_switch_event_sweeping_around_rim():
    """Holding radius above r_exit but rotating to a new sector emits a switch."""
    det = CornerDetector(n=4, r_enter=0.9, r_exit=0.5)
    first = det.update(1.0, 0.0)
    assert first is not None and first.kind == "on" and first.sector == 0
    # Stay on the rim, rotate 90 degrees clockwise to +Y.
    ev = det.update(0.0, 1.0)
    assert ev is not None and ev.kind == "switch"
    old, new = decode_switch(ev)
    assert old == 0 and new == 1


def test_n_values_accepted():
    for n in (4, 8, 16):
        CornerDetector(n=n)


def test_invalid_n_raises():
    with pytest.raises(ValueError):
        CornerDetector(n=5)


def test_invalid_hysteresis_raises():
    with pytest.raises(ValueError):
        CornerDetector(r_enter=0.5, r_exit=0.5)
    with pytest.raises(ValueError):
        CornerDetector(r_enter=0.4, r_exit=0.9)


def test_reset_clears_state():
    det = CornerDetector(n=4, r_enter=0.9, r_exit=0.5)
    det.update(1.0, 0.0)
    assert det.active_sector == 0
    det.reset()
    assert det.active_sector is None


def test_decode_switch_rejects_non_switch():
    det = CornerDetector(n=4, r_enter=0.9, r_exit=0.5)
    on_ev = det.update(1.0, 0.0)
    with pytest.raises(ValueError):
        decode_switch(on_ev)
