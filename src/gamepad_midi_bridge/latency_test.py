"""Latency self-test — measures controller-input → MIDI-output latency.

Usage::

    tracker = latency_test.tracker()
    tracker.reset()

    # Inside the hot poll loop (only when test mode is active):
    tracker.record_input(time.perf_counter())
    # ... MIDI send ...
    tracker.record_output(time.perf_counter())

    print(tracker.mean_ms())   # mean over all completed samples
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LatencyMeasurement:
    """A single controller-press → MIDI-send round-trip."""
    button_press_ts: float   # time.perf_counter() at button event
    midi_send_ts: float      # time.perf_counter() just before send_message

    @property
    def delta_ms(self) -> float:
        return (self.midi_send_ts - self.button_press_ts) * 1_000.0


class LatencyTracker:
    """Accumulates latency samples across one test run.

    Thread-safe: record_input / record_output may be called from the bridge
    poll thread while the UI reads results from the GUI thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending_input_ts: Optional[float] = None
        self.samples: List[LatencyMeasurement] = []

    # ------------------------------------------------------------------
    # Recording API (called from hot loop — must stay lightweight)

    def record_input(self, ts: float) -> None:
        """Record the timestamp of a button press event."""
        with self._lock:
            self._pending_input_ts = ts

    def record_output(self, ts: float) -> None:
        """Record the timestamp of the MIDI send for the matching press.

        Pairs with the most recent record_input() call.  If no pending
        input is waiting, this call is a no-op (e.g. non-test mode leak).
        """
        with self._lock:
            if self._pending_input_ts is None:
                return
            m = LatencyMeasurement(
                button_press_ts=self._pending_input_ts,
                midi_send_ts=ts,
            )
            self.samples.append(m)
            self._pending_input_ts = None

    # ------------------------------------------------------------------
    # Query API (called from GUI thread)

    def last_delta_ms(self) -> Optional[float]:
        """Return the most recent sample's delta in ms, or None if no samples."""
        with self._lock:
            if not self.samples:
                return None
            return self.samples[-1].delta_ms

    def mean_ms(self) -> Optional[float]:
        """Return the arithmetic mean latency in ms, or None if no samples."""
        with self._lock:
            if not self.samples:
                return None
            return sum(s.delta_ms for s in self.samples) / len(self.samples)

    def min_ms(self) -> Optional[float]:
        with self._lock:
            if not self.samples:
                return None
            return min(s.delta_ms for s in self.samples)

    def max_ms(self) -> Optional[float]:
        with self._lock:
            if not self.samples:
                return None
            return max(s.delta_ms for s in self.samples)

    def std_ms(self) -> Optional[float]:
        """Population standard deviation in ms, or None if fewer than 2 samples."""
        with self._lock:
            n = len(self.samples)
            if n < 2:
                return None
            mean = sum(s.delta_ms for s in self.samples) / n
            variance = sum((s.delta_ms - mean) ** 2 for s in self.samples) / n
            return math.sqrt(variance)

    def reset(self) -> None:
        """Clear all samples and any pending un-paired input timestamp."""
        with self._lock:
            self.samples.clear()
            self._pending_input_ts = None


# Module-level singleton — import and call tracker() everywhere.
_tracker: Optional[LatencyTracker] = None
_tracker_lock = threading.Lock()


def tracker() -> LatencyTracker:
    """Return (or lazily create) the module-level singleton LatencyTracker."""
    global _tracker
    with _tracker_lock:
        if _tracker is None:
            _tracker = LatencyTracker()
        return _tracker
