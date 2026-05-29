"""Tests for the pattern recorder — Pattern data model, PatternEngine state
machine, and quantize-to-grid maths."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from gamepad_midi_bridge.pattern import (
    Pattern,
    PatternEngine,
    PatternEvent,
    PatternState,
    _quantize_to_grid,
)
from gamepad_midi_bridge.mapping import (
    Mapping,
    PatternRecorderConfig,
    _pattern_recorder_from_dict,
)


# ============================================================
# PatternEvent round-trip

class TestPatternEvent:
    def test_round_trip(self):
        ev = PatternEvent(delay_ms=250, status=0x90, data1=60, data2=100)
        d = ev.to_dict()
        ev2 = PatternEvent.from_dict(d)
        assert ev2.delay_ms == 250
        assert ev2.status == 0x90
        assert ev2.data1 == 60
        assert ev2.data2 == 100

    def test_from_dict_defaults(self):
        ev = PatternEvent.from_dict({})
        assert ev.delay_ms == 0
        assert ev.status == 0
        assert ev.data1 == 0
        assert ev.data2 == 0

    def test_from_dict_clamps_status(self):
        ev = PatternEvent.from_dict({"status": 999, "data1": 200, "data2": -5})
        assert ev.status == 255
        assert ev.data1 == 127
        assert ev.data2 == 0


# ============================================================
# Pattern round-trip

class TestPattern:
    def test_empty_round_trip(self):
        p = Pattern(duration_ms=2000)
        d = p.to_dict()
        p2 = Pattern.from_dict(d)
        assert p2.duration_ms == 2000
        assert p2.events == []

    def test_events_round_trip(self):
        p = Pattern(duration_ms=2000)
        p.add_event(500, 0x90, 60, 100)
        p.add_event(1000, 0x80, 60, 0)
        d = p.to_dict()
        p2 = Pattern.from_dict(d)
        assert len(p2.events) == 2
        assert p2.events[0].delay_ms == 500
        assert p2.events[1].delay_ms == 1000

    def test_add_event_wraps_to_loop(self):
        """Events beyond loop length wrap into [0, duration_ms)."""
        p = Pattern(duration_ms=2000)
        p.add_event(2500, 0x90, 60, 100)  # 2500 % 2000 = 500
        assert p.events[0].delay_ms == 500

    def test_events_sorted(self):
        p = Pattern(duration_ms=2000)
        p.add_event(1000, 0x90, 62, 100)
        p.add_event(250, 0x90, 60, 100)
        p.add_event(750, 0x90, 61, 100)
        delays = [e.delay_ms for e in p.events]
        assert delays == sorted(delays)

    def test_clear(self):
        p = Pattern(duration_ms=2000)
        p.add_event(100, 0x90, 60, 100)
        p.clear()
        assert p.events == []

    def test_from_dict_skips_bad_entries(self):
        d = {
            "duration_ms": 1000,
            "events": [
                {"delay_ms": 100, "status": 0x90, "data1": 60, "data2": 100},
                "not a dict",
                None,
                {"delay_ms": 200, "status": 0x80, "data1": 60, "data2": 0},
            ],
        }
        p = Pattern.from_dict(d)
        assert len(p.events) == 2

    def test_from_dict_missing_duration_defaults(self):
        p = Pattern.from_dict({})
        assert p.duration_ms == 2000


# ============================================================
# Quantize-to-grid

class TestQuantizeToGrid:
    @pytest.mark.parametrize("pos, grid, loop, expected", [
        (0, 125, 2000, 0),
        (60, 125, 2000, 0),       # round down (60 < 62.5)
        (63, 125, 2000, 125),     # round up (63 >= 62.5)
        (130, 125, 2000, 125),    # round to nearest below
        (189, 125, 2000, 250),    # round up to 250
        (1999, 125, 2000, 1999),  # rounds up to 2000 but clamped to loop_ms-1=1999
        (500, 125, 2000, 500),    # already on grid
        (0, 0, 2000, 0),          # zero grid: no-op clamped
    ])
    def test_snap(self, pos, grid, loop, expected):
        result = _quantize_to_grid(pos, grid, loop)
        assert result == expected

    def test_result_never_exceeds_loop_minus_one(self):
        """Snapped position must be < loop_ms."""
        for pos in range(0, 2001, 100):
            result = _quantize_to_grid(pos, 125, 2000)
            assert 0 <= result < 2000

    def test_pattern_quantize_flag(self):
        """Pattern.add_event with quantize=True snaps events."""
        p = Pattern(duration_ms=2000)
        p.add_event(63, 0x90, 60, 100, quantize=True, grid_ms=125)
        assert p.events[0].delay_ms == 125  # rounds up to next grid


# ============================================================
# PatternEngine state machine

def _make_engine(**kwargs) -> tuple[PatternEngine, list]:
    sent: list = []
    eng = PatternEngine(send_fn=lambda s, d1, d2: sent.append((s, d1, d2)), **kwargs)
    return eng, sent


class TestPatternEngineIdle:
    def test_initial_state_is_idle(self):
        eng, _ = _make_engine()
        assert eng.state == PatternState.IDLE

    def test_tick_in_idle_is_noop(self):
        eng, sent = _make_engine()
        eng.tick()
        assert sent == []

    def test_stop_overdub_in_idle_is_noop(self):
        eng, _ = _make_engine()
        eng.stop_overdub()
        assert eng.state == PatternState.IDLE

    def test_stop_loop_in_idle_is_noop(self):
        eng, _ = _make_engine()
        eng.stop_loop()
        assert eng.state == PatternState.IDLE


class TestPatternEngineRecording:
    def test_start_recording_transitions(self):
        eng, _ = _make_engine()
        eng.start_recording()
        assert eng.state == PatternState.RECORDING

    def test_start_recording_clears_previous_events(self):
        eng, _ = _make_engine()
        # Put a manual event in the pattern
        eng._pattern.add_event(100, 0x90, 60, 100)
        eng.start_recording()
        assert eng._pattern.events == []

    def test_record_event_captured_during_recording(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.record_event(0x90, 60, 100)
        assert len(eng._pattern.events) == 1
        assert eng._pattern.events[0].status == 0x90

    def test_record_event_ignored_in_idle(self):
        eng, _ = _make_engine()
        eng.record_event(0x90, 60, 100)
        assert eng._pattern.events == []

    def test_start_recording_ignored_when_already_recording(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.record_event(0x90, 60, 100)
        eng.start_recording()  # second call should be no-op
        # Still in RECORDING (not re-entered from another state)
        assert eng.state == PatternState.RECORDING

    def test_overdub_ignored_during_recording(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.start_overdub()
        assert eng.state == PatternState.RECORDING


class TestPatternEngineRecordingToPlaying:
    def test_stop_recording_transitions_to_playing(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.stop_recording()
        assert eng.state == PatternState.PLAYING

    def test_stop_recording_in_idle_is_noop(self):
        eng, _ = _make_engine()
        eng.stop_recording()
        assert eng.state == PatternState.IDLE


class TestPatternEnginePlayback:
    def test_loop_ms_matches_bpm_and_bars(self):
        # 120 BPM, 1 bar = 2000 ms
        eng, _ = _make_engine(bpm=120.0, loop_length_bars=1)
        assert eng.loop_ms == 2000

    def test_loop_ms_two_bars(self):
        eng, _ = _make_engine(bpm=120.0, loop_length_bars=2)
        assert eng.loop_ms == 4000

    def test_grid_ms_at_120bpm_is_125(self):
        eng, _ = _make_engine(bpm=120.0)
        assert eng.grid_ms == 125

    def test_playback_fires_events(self):
        """Tick-driven playback: events at t=0 fire immediately."""
        sent: list = []
        eng = PatternEngine(
            send_fn=lambda s, d1, d2: sent.append((s, d1, d2)),
            bpm=120.0,
        )
        # Manually inject an event at position 0 ms
        eng.start_recording()
        eng._pattern.clear()
        eng._pattern.add_event(0, 0x90, 60, 100)
        eng.stop_recording()  # → PLAYING, sets loop_start_ms to now

        # First tick should fire the event at position 0
        eng.tick()
        assert (0x90, 60, 100) in sent

    def test_stop_loop_returns_to_idle(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.stop_recording()
        assert eng.state == PatternState.PLAYING
        eng.stop_loop()
        assert eng.state == PatternState.IDLE

    def test_stop_loop_resets_cursor(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng._pattern.add_event(0, 0x90, 60, 100)
        eng.stop_recording()
        eng.stop_loop()
        assert eng._play_cursor == 0


class TestPatternEngineOverdub:
    def test_start_overdub_from_playing(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.stop_recording()
        eng.start_overdub()
        assert eng.state == PatternState.OVERDUB

    def test_overdub_event_appended(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.stop_recording()
        n_before = len(eng._pattern.events)
        eng.start_overdub()
        eng.record_event(0x90, 62, 80)
        assert len(eng._pattern.events) == n_before + 1

    def test_stop_overdub_returns_to_playing(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.stop_recording()
        eng.start_overdub()
        eng.stop_overdub()
        assert eng.state == PatternState.PLAYING

    def test_stop_loop_from_overdub(self):
        eng, _ = _make_engine()
        eng.start_recording()
        eng.stop_recording()
        eng.start_overdub()
        eng.stop_loop()
        assert eng.state == PatternState.IDLE

    def test_overdub_ignored_if_not_playing(self):
        eng, _ = _make_engine()
        eng.start_overdub()  # called from IDLE — should be no-op
        assert eng.state == PatternState.IDLE

    def test_full_state_sequence(self):
        """IDLE → RECORDING → PLAYING → OVERDUB → PLAYING → IDLE."""
        eng, _ = _make_engine()
        assert eng.state == PatternState.IDLE
        eng.start_recording()
        assert eng.state == PatternState.RECORDING
        eng.stop_recording()
        assert eng.state == PatternState.PLAYING
        eng.start_overdub()
        assert eng.state == PatternState.OVERDUB
        eng.stop_overdub()
        assert eng.state == PatternState.PLAYING
        eng.stop_loop()
        assert eng.state == PatternState.IDLE


class TestPatternEngineLoopWrap:
    def test_loop_wraps_and_replays(self):
        """Events fire on both the first and second loop iteration."""
        fake_clock = [0.0]

        def fake_now():
            return fake_clock[0]

        sent: list = []

        with patch("gamepad_midi_bridge.pattern._now_ms", side_effect=fake_now):
            eng = PatternEngine(
                send_fn=lambda s, d1, d2: sent.append((s, d1, d2)),
                bpm=120.0,
                loop_length_bars=1,
            )
            # Build a pattern with one event at 0 ms
            fake_clock[0] = 0.0
            eng.start_recording()
            eng._pattern.clear()
            eng._pattern.add_event(0, 0x90, 60, 100)
            eng.stop_recording()   # loop_start_ms = 0

            # First tick at t=0 — event fires
            fake_clock[0] = 1.0
            eng.tick()
            first_count = len(sent)
            assert first_count >= 1

            # Advance past the loop boundary (2001 ms > 2000 ms loop)
            fake_clock[0] = 2001.0
            eng.tick()
            # The wrap should reset cursor; tick fires the event again
            assert len(sent) > first_count


# ============================================================
# PatternRecorderConfig schema

class TestPatternRecorderConfig:
    def test_defaults(self):
        cfg = PatternRecorderConfig()
        assert cfg.enabled is False
        assert cfg.record_button == -1
        assert cfg.overdub_button == -1
        assert cfg.cancel_button == -1
        assert cfg.loop_length_bars == 1
        assert cfg.quantize_to_grid is True

    def test_from_dict_full(self):
        d = {
            "enabled": True,
            "record_button": 5,
            "overdub_button": 6,
            "cancel_button": 7,
            "loop_length_bars": 2,
            "quantize_to_grid": False,
        }
        cfg = _pattern_recorder_from_dict(d)
        assert cfg.enabled is True
        assert cfg.record_button == 5
        assert cfg.overdub_button == 6
        assert cfg.cancel_button == 7
        assert cfg.loop_length_bars == 2
        assert cfg.quantize_to_grid is False

    def test_from_dict_none(self):
        cfg = _pattern_recorder_from_dict(None)
        assert cfg.enabled is False

    def test_from_dict_empty(self):
        cfg = _pattern_recorder_from_dict({})
        assert cfg.enabled is False
        assert cfg.loop_length_bars == 1

    def test_loop_length_bars_minimum_one(self):
        cfg = _pattern_recorder_from_dict({"loop_length_bars": 0})
        assert cfg.loop_length_bars == 1

    def test_mapping_includes_pattern_recorder(self):
        m = Mapping()
        assert hasattr(m, "pattern_recorder")
        assert isinstance(m.pattern_recorder, PatternRecorderConfig)

    def test_mapping_from_dict_round_trip(self):
        m = Mapping()
        m.pattern_recorder.enabled = True
        m.pattern_recorder.record_button = 10
        d = m.to_dict()
        m2 = Mapping.from_dict(d)
        assert m2.pattern_recorder.enabled is True
        assert m2.pattern_recorder.record_button == 10

    def test_mapping_from_dict_missing_key_defaults(self):
        """Old presets without pattern_recorder key load cleanly (disabled)."""
        d = Mapping().to_dict()
        d.pop("pattern_recorder", None)
        m = Mapping.from_dict(d)
        assert m.pattern_recorder.enabled is False
