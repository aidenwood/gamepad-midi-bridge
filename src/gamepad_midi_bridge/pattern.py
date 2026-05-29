"""Pattern recorder — continuous loop recorder with overdub.

Distinct from the one-shot Macro recorder: a Pattern plays continuously
at a fixed duration while it is active, and the user can layer new events
on top (overdub) while the loop is already running.

State machine:
    IDLE → (start_recording) → RECORDING
    RECORDING → (stop_recording) → PLAYING
    PLAYING → (start_overdub) → OVERDUB
    OVERDUB → (stop_overdub) → PLAYING
    PLAYING / OVERDUB / RECORDING → (stop_loop) → IDLE
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Callable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model

@dataclass
class PatternEvent:
    """One MIDI event anchored to a position inside the loop."""
    delay_ms: int   # ms from loop start (0 = beginning of bar)
    status: int     # MIDI status byte
    data1: int      # note / CC number
    data2: int      # velocity / CC value

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PatternEvent":
        return cls(
            delay_ms=max(0, int(d.get("delay_ms", 0))),
            status=max(0, min(255, int(d.get("status", 0)))),
            data1=max(0, min(127, int(d.get("data1", 0)))),
            data2=max(0, min(127, int(d.get("data2", 0)))),
        )


@dataclass
class Pattern:
    """A fixed-length loop of MIDI events.

    ``duration_ms`` is authoritative — events beyond it are ignored on
    playback.  Events are kept sorted by delay_ms so playback iteration is
    a simple linear scan.
    """
    duration_ms: int = 2000          # 1 bar @ 120 BPM = 2 s
    events: List[PatternEvent] = field(default_factory=list)

    # ---------------------------------------------------------------- mutations

    def add_event(self, delay_ms: int, status: int, data1: int, data2: int,
                  *,
                  quantize: bool = False,
                  grid_ms: int = 125) -> None:
        """Append one event, optionally snapping to the nearest grid boundary.

        ``grid_ms`` is the grid resolution in milliseconds.  For 1/16 notes
        at 120 BPM: ``(60 / 120) / 4 * 1000 = 125 ms``.
        """
        pos = delay_ms % max(1, self.duration_ms)   # wrap to loop length
        if quantize and grid_ms > 0:
            pos = _quantize_to_grid(pos, grid_ms, self.duration_ms)
        ev = PatternEvent(delay_ms=pos, status=status, data1=data1, data2=data2)
        self.events.append(ev)
        # Keep sorted for deterministic playback
        self.events.sort(key=lambda e: e.delay_ms)

    def clear(self) -> None:
        self.events.clear()

    # ---------------------------------------------------------------- serialisation

    def to_dict(self) -> dict:
        return {
            "duration_ms": self.duration_ms,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pattern":
        duration_ms = max(1, int(d.get("duration_ms", 2000)))
        raw_events = d.get("events") or []
        events: List[PatternEvent] = []
        for entry in raw_events:
            if isinstance(entry, dict):
                try:
                    events.append(PatternEvent.from_dict(entry))
                except (TypeError, ValueError):
                    continue
        return cls(duration_ms=duration_ms, events=events)


# ---------------------------------------------------------------------------
# Grid quantize helper

def _quantize_to_grid(pos_ms: int, grid_ms: int, loop_ms: int) -> int:
    """Snap ``pos_ms`` to the nearest multiple of ``grid_ms``.

    The result is clamped to ``[0, loop_ms)``.

    Args:
        pos_ms:  Raw position in milliseconds inside the loop.
        grid_ms: Grid step in milliseconds (e.g. 125 ms for 1/16 @ 120 BPM).
        loop_ms: Total loop length in milliseconds.

    Returns:
        Quantized position, guaranteed to be in ``[0, loop_ms)``.
    """
    if grid_ms <= 0:
        return max(0, min(pos_ms, loop_ms - 1))
    half = grid_ms // 2
    snapped = ((pos_ms + half) // grid_ms) * grid_ms
    return max(0, min(snapped, loop_ms - 1))


# ---------------------------------------------------------------------------
# State machine

class PatternState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PLAYING = auto()
    OVERDUB = auto()


class PatternEngine:
    """State machine that drives loop recording, playback, and overdub.

    Designed to run without Qt so it can be unit-tested without a QApplication.
    The optional ``send_fn`` callback is invoked for each MIDI event during
    playback: ``send_fn(status, data1, data2)``.

    Playback is tick-driven via ``tick()``.  The caller should invoke
    ``tick()`` at a regular interval (e.g. every 10 ms from a QTimer or a
    plain thread).  The engine does not create its own timer; that keeps it
    testable and integrable.
    """

    def __init__(
        self,
        send_fn: Optional[Callable[[int, int, int], None]] = None,
        *,
        bpm: float = 120.0,
        loop_length_bars: int = 1,
        quantize_to_grid: bool = True,
    ) -> None:
        self._send_fn = send_fn
        self._bpm = max(1.0, float(bpm))
        self._loop_length_bars = max(1, int(loop_length_bars))
        self._quantize = quantize_to_grid

        # Compute loop and grid durations from BPM + bars
        self._loop_ms = self._compute_loop_ms()
        self._grid_ms = self._compute_grid_ms()

        self._pattern: Pattern = Pattern(duration_ms=self._loop_ms)
        self._state: PatternState = PatternState.IDLE

        # Recording
        self._rec_start_ms: float = 0.0   # wall-clock ms when recording started

        # Playback
        self._loop_start_ms: float = 0.0  # wall-clock ms when loop phase 0 started
        self._play_cursor: int = 0         # index into sorted events

    # ---------------------------------------------------------------- config

    def _compute_loop_ms(self) -> int:
        beat_ms = (60.0 / self._bpm) * 1000.0
        return max(1, int(round(beat_ms * 4.0 * self._loop_length_bars)))

    def _compute_grid_ms(self) -> int:
        """1/16 grid in ms."""
        beat_ms = (60.0 / self._bpm) * 1000.0
        return max(1, int(round(beat_ms / 4.0)))

    def reconfigure(self, bpm: float, loop_length_bars: int,
                    quantize_to_grid: bool) -> None:
        """Update BPM / bars / quantize live (only safe in IDLE state)."""
        self._bpm = max(1.0, float(bpm))
        self._loop_length_bars = max(1, int(loop_length_bars))
        self._quantize = quantize_to_grid
        self._loop_ms = self._compute_loop_ms()
        self._grid_ms = self._compute_grid_ms()
        self._pattern.duration_ms = self._loop_ms

    # ---------------------------------------------------------------- state queries

    @property
    def state(self) -> PatternState:
        return self._state

    @property
    def pattern(self) -> Pattern:
        return self._pattern

    @property
    def loop_ms(self) -> int:
        return self._loop_ms

    @property
    def grid_ms(self) -> int:
        return self._grid_ms

    # ---------------------------------------------------------------- state transitions

    def start_recording(self) -> None:
        """IDLE → RECORDING.  Clears any previously recorded events."""
        if self._state not in (PatternState.IDLE,):
            return
        self._pattern.clear()
        self._pattern.duration_ms = self._loop_ms
        self._rec_start_ms = _now_ms()
        self._state = PatternState.RECORDING

    def stop_recording(self) -> None:
        """RECORDING → PLAYING.  Seals the recorded pattern and starts playback."""
        if self._state != PatternState.RECORDING:
            return
        self._state = PatternState.PLAYING
        self._begin_playback()

    def start_overdub(self) -> None:
        """PLAYING → OVERDUB.  Keeps playing while accepting new events."""
        if self._state != PatternState.PLAYING:
            return
        self._rec_start_ms = self._current_loop_phase_start_ms()
        self._state = PatternState.OVERDUB

    def stop_overdub(self) -> None:
        """OVERDUB → PLAYING."""
        if self._state != PatternState.OVERDUB:
            return
        self._state = PatternState.PLAYING

    def stop_loop(self) -> None:
        """Any → IDLE.  Clears nothing — the pattern is preserved."""
        self._state = PatternState.IDLE
        self._play_cursor = 0

    # ---------------------------------------------------------------- event capture

    def record_event(self, status: int, data1: int, data2: int) -> None:
        """Capture an outbound MIDI event into the current recording.

        No-op unless state is RECORDING or OVERDUB.
        """
        if self._state not in (PatternState.RECORDING, PatternState.OVERDUB):
            return
        now = _now_ms()
        delay = int(now - self._rec_start_ms)
        self._pattern.add_event(
            delay,
            status,
            data1,
            data2,
            quantize=self._quantize,
            grid_ms=self._grid_ms,
        )

    # ---------------------------------------------------------------- tick-driven playback

    def tick(self) -> None:
        """Advance playback by one tick.

        Should be called at a regular cadence (e.g. every 10 ms).  Fires all
        events whose position has been passed since the last tick.
        """
        if self._state not in (PatternState.PLAYING, PatternState.OVERDUB):
            return
        if not self._pattern.events:
            # Loop wrapping still needs to happen even when no events
            self._handle_loop_wrap()
            return

        now = _now_ms()
        loop_phase_ms = int(now - self._loop_start_ms)

        # Detect loop wrap
        if loop_phase_ms >= self._loop_ms:
            self._handle_loop_wrap()
            now = _now_ms()
            loop_phase_ms = int(now - self._loop_start_ms)

        events = self._pattern.events
        n = len(events)

        # Fire every event whose delay_ms has been crossed in this tick
        while self._play_cursor < n:
            ev = events[self._play_cursor]
            if ev.delay_ms <= loop_phase_ms:
                if self._send_fn is not None:
                    try:
                        self._send_fn(ev.status, ev.data1, ev.data2)
                    except Exception:
                        pass
                self._play_cursor += 1
            else:
                break

    # ---------------------------------------------------------------- internals

    def _begin_playback(self) -> None:
        self._loop_start_ms = _now_ms()
        self._play_cursor = 0

    def _handle_loop_wrap(self) -> None:
        """Reset loop phase, keeping start aligned to multiples of loop_ms."""
        now = _now_ms()
        # Advance loop_start by full loop increments to keep phase coherent
        elapsed_since_start = now - self._loop_start_ms
        periods = max(1, int(elapsed_since_start // self._loop_ms))
        self._loop_start_ms += periods * self._loop_ms
        self._play_cursor = 0

    def _current_loop_phase_start_ms(self) -> float:
        """Wall-clock ms corresponding to the beginning of the current loop."""
        return self._loop_start_ms


# ---------------------------------------------------------------------------
# Tiny wall-clock helper (kept at module level for easy monkeypatching in tests)

def _now_ms() -> float:
    return time.time() * 1000.0
