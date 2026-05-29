"""Tap-delay echo helper tests."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.tap_delay import DelayedTap, TapDelay, TapDelayConfig


def test_schedule_returns_three_taps():
    """schedule with taps=3 returns 3 DelayedTap entries."""
    cfg = TapDelayConfig(enabled=True, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 0.0)
    assert len(taps) == 3
    assert all(isinstance(t, DelayedTap) for t in taps)


def test_velocities_decrease_by_feedback():
    """Velocities decrease: each is feedback * previous."""
    cfg = TapDelayConfig(enabled=True, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 0.0)
    # 100, 100*0.6=60, 100*0.36=36
    assert taps[0].velocity == 100
    assert taps[1].velocity == 60
    assert taps[2].velocity == 36


def test_velocities_clamped_to_one_minimum():
    """Velocity clamped to 1..127; feedback=0.99 never floors to 0."""
    cfg = TapDelayConfig(enabled=True, taps=8, delay_ms=100, feedback=0.99)
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 0.0)
    # All velocities should be >= 1.
    assert all(t.velocity >= 1 for t in taps)
    assert all(t.velocity <= 127 for t in taps)


def test_velocities_clamped_to_127_maximum():
    """Velocity clamped to 1..127 maximum."""
    cfg = TapDelayConfig(enabled=True, taps=2, delay_ms=100, feedback=1.0)
    td = TapDelay(cfg)
    taps = td.schedule(60, 150, 1, 0.0)
    # First should be clamped to 127.
    assert taps[0].velocity == 127
    assert taps[1].velocity == 127


def test_fire_at_s_spaced_by_delay_ms():
    """fire_at_s spaced by delay_ms (in seconds)."""
    cfg = TapDelayConfig(enabled=True, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 0.0)
    # delay_ms=100 → 0.1s
    assert abs(taps[0].fire_at_s - 0.1) < 0.0001
    assert abs(taps[1].fire_at_s - 0.2) < 0.0001
    assert abs(taps[2].fire_at_s - 0.3) < 0.0001


def test_fire_at_s_respects_now():
    """fire_at_s is relative to now_s."""
    cfg = TapDelayConfig(enabled=True, taps=2, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 5.0)
    # now_s=5.0, delay=0.1s
    assert abs(taps[0].fire_at_s - 5.1) < 0.0001
    assert abs(taps[1].fire_at_s - 5.2) < 0.0001


def test_pop_ready_returns_nothing_when_not_ready():
    """pop_ready returns nothing when now < earliest fire_at."""
    cfg = TapDelayConfig(enabled=True, taps=2, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    td.schedule(60, 100, 1, 0.0)
    # fire_at is 0.1, 0.2; now is 0.05
    ready = td.pop_ready(0.05)
    assert len(ready) == 0


def test_pop_ready_returns_ready_taps():
    """pop_ready returns taps with fire_at_s <= now_s."""
    cfg = TapDelayConfig(enabled=True, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    td.schedule(60, 100, 1, 0.0)
    # fire_at is 0.1, 0.2, 0.3; now is 0.15
    ready = td.pop_ready(0.15)
    assert len(ready) == 1
    assert ready[0].fire_at_s == pytest.approx(0.1)


def test_pop_ready_removes_from_queue():
    """pop_ready removes returned taps from internal queue."""
    cfg = TapDelayConfig(enabled=True, taps=2, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    td.schedule(60, 100, 1, 0.0)
    assert td.pending_count() == 2
    td.pop_ready(0.15)
    assert td.pending_count() == 1
    td.pop_ready(0.25)
    assert td.pending_count() == 0


def test_pop_ready_sorted_by_fire_at_s():
    """pop_ready results are sorted by fire_at_s."""
    cfg = TapDelayConfig(enabled=True, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    td.schedule(60, 100, 1, 0.0)
    # Manually add out-of-order for testing.
    ready = td.pop_ready(0.35)
    assert len(ready) == 3
    # Verify sorted by fire_at_s.
    assert ready[0].fire_at_s < ready[1].fire_at_s < ready[2].fire_at_s


def test_pitch_shift_per_tap_shifts_each_echo():
    """pitch_shift_per_tap shifts each echo."""
    cfg = TapDelayConfig(
        enabled=True, taps=3, delay_ms=100, feedback=0.6, pitch_shift_per_tap=2
    )
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 0.0)
    # note 60: 60+(0*2)=60, 60+(1*2)=62, 60+(2*2)=64
    assert taps[0].note == 60
    assert taps[1].note == 62
    assert taps[2].note == 64


def test_pitch_shift_per_tap_negative():
    """pitch_shift_per_tap can be negative."""
    cfg = TapDelayConfig(
        enabled=True, taps=3, delay_ms=100, feedback=0.6, pitch_shift_per_tap=-1
    )
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 0.0)
    # note 60: 60+(0*-1)=60, 60+(1*-1)=59, 60+(2*-1)=58
    assert taps[0].note == 60
    assert taps[1].note == 59
    assert taps[2].note == 58


def test_pitch_shift_out_of_range_drops_echo():
    """Echoes with note < 0 or > 127 are dropped."""
    cfg = TapDelayConfig(
        enabled=True, taps=5, delay_ms=100, feedback=0.6, pitch_shift_per_tap=12
    )
    td = TapDelay(cfg)
    # note 60: 60+(0*12)=60, 60+(1*12)=72, 60+(2*12)=84, 60+(3*12)=96, 60+(4*12)=108
    # All in range, but let's test with a note closer to 127.
    taps = td.schedule(115, 100, 1, 0.0)
    # 115+(0*12)=115, 115+(1*12)=127, 115+(2*12)=139 (out), ...
    assert len(taps) == 2
    assert taps[0].note == 115
    assert taps[1].note == 127


def test_pitch_shift_low_boundary():
    """Echoes with note < 0 are dropped."""
    cfg = TapDelayConfig(
        enabled=True, taps=3, delay_ms=100, feedback=0.6, pitch_shift_per_tap=-30
    )
    td = TapDelay(cfg)
    # note 10: 10, -20 (out), -50 (out)
    taps = td.schedule(10, 100, 1, 0.0)
    assert len(taps) == 1
    assert taps[0].note == 10


def test_clear_empties_queue():
    """clear() empties the queue."""
    cfg = TapDelayConfig(enabled=True, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    td.schedule(60, 100, 1, 0.0)
    assert td.pending_count() == 3
    td.clear()
    assert td.pending_count() == 0


def test_pending_count_reflects_queued():
    """pending_count reflects number of queued taps."""
    cfg = TapDelayConfig(enabled=True, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    td.schedule(60, 100, 1, 0.0)
    assert td.pending_count() == 3
    td.pop_ready(0.15)
    assert td.pending_count() == 2
    td.pop_ready(0.35)
    assert td.pending_count() == 0


def test_clamping_taps_minimum():
    """taps < 1 clamped to 1."""
    cfg = TapDelayConfig(taps=0)
    assert cfg.taps == 1


def test_clamping_taps_maximum():
    """taps > 16 clamped to 16."""
    cfg = TapDelayConfig(taps=20)
    assert cfg.taps == 16


def test_clamping_delay_ms_minimum():
    """delay_ms < 10 clamped to 10."""
    cfg = TapDelayConfig(delay_ms=5)
    assert cfg.delay_ms == 10


def test_clamping_delay_ms_maximum():
    """delay_ms > 5000 clamped to 5000."""
    cfg = TapDelayConfig(delay_ms=10000)
    assert cfg.delay_ms == 5000


def test_clamping_feedback_minimum():
    """feedback < 0 clamped to 0.0."""
    cfg = TapDelayConfig(feedback=-0.5)
    assert cfg.feedback == 0.0


def test_clamping_feedback_maximum():
    """feedback > 0.99 clamped to 0.99."""
    cfg = TapDelayConfig(feedback=1.0)
    assert cfg.feedback == 0.99


def test_clamping_pitch_shift_minimum():
    """pitch_shift_per_tap < -12 clamped to -12."""
    cfg = TapDelayConfig(pitch_shift_per_tap=-20)
    assert cfg.pitch_shift_per_tap == -12


def test_clamping_pitch_shift_maximum():
    """pitch_shift_per_tap > 12 clamped to 12."""
    cfg = TapDelayConfig(pitch_shift_per_tap=20)
    assert cfg.pitch_shift_per_tap == 12


def test_roundtrip_serialization():
    """to_dict / from_dict round-trip."""
    cfg1 = TapDelayConfig(
        enabled=True,
        taps=5,
        delay_ms=200,
        feedback=0.7,
        pitch_shift_per_tap=3,
    )
    d = cfg1.to_dict()
    cfg2 = TapDelayConfig.from_dict(d)
    assert cfg2.enabled == cfg1.enabled
    assert cfg2.taps == cfg1.taps
    assert cfg2.delay_ms == cfg1.delay_ms
    assert cfg2.feedback == cfg1.feedback
    assert cfg2.pitch_shift_per_tap == cfg1.pitch_shift_per_tap


def test_disabled_returns_empty_list():
    """schedule with enabled=False returns empty list."""
    cfg = TapDelayConfig(enabled=False, taps=3, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 1, 0.0)
    assert taps == []
    assert td.pending_count() == 0


def test_multiple_schedules_accumulate():
    """Multiple schedule calls accumulate taps in queue."""
    cfg = TapDelayConfig(enabled=True, taps=2, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    td.schedule(60, 100, 1, 0.0)
    td.schedule(62, 80, 1, 0.0)
    assert td.pending_count() == 4


def test_channel_preserved():
    """channel parameter is preserved in DelayedTap."""
    cfg = TapDelayConfig(enabled=True, taps=2, delay_ms=100, feedback=0.6)
    td = TapDelay(cfg)
    taps = td.schedule(60, 100, 5, 0.0)
    assert all(t.channel == 5 for t in taps)
