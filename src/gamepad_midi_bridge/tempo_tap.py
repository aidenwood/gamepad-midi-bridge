"""Tempo-tap detector: estimate BPM from a sequence of taps.

Pure stdlib, no Qt, no global state. Register taps with timestamps and get
current BPM estimate, stability metrics, and inter-tap intervals.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TapState:
    """Configuration and state for tap detection."""
    taps: list[float] = field(default_factory=list)
    max_history: int = 8
    reset_timeout_s: float = 2.0


class TempoTap:
    """Tempo tap detector: takes timestamped taps and estimates BPM.

    Usage:
        tapper = TempoTap(max_history=8, reset_timeout_s=2.0)
        bpm = tapper.tap(now_s=0.0)  # None (only 1 tap)
        bpm = tapper.tap(now_s=0.5)  # 120.0 (2 taps @ 0.5s apart)
    """

    def __init__(
        self,
        max_history: int = 8,
        reset_timeout_s: float = 2.0,
        min_bpm: float = 30.0,
        max_bpm: float = 300.0,
    ):
        """Initialize the tempo tap detector.

        Args:
            max_history: Maximum number of tap times to keep.
            reset_timeout_s: If gap from previous tap > this, clear history first.
            min_bpm: Clamp BPM estimate to this floor.
            max_bpm: Clamp BPM estimate to this ceiling.
        """
        self.max_history = max_history
        self.reset_timeout_s = reset_timeout_s
        self.min_bpm = min_bpm
        self.max_bpm = max_bpm
        self._taps: list[float] = []

    def tap(self, now_s: float) -> Optional[float]:
        """Register a tap at time `now_s`. Returns current BPM estimate.

        If gap from previous tap > reset_timeout_s, history is cleared first.
        History is capped to max_history (oldest taps dropped).

        Args:
            now_s: Current time in seconds (from any reference point).

        Returns:
            Current BPM estimate (or None if fewer than 2 taps).
        """
        # If there's a gap larger than reset_timeout, clear history.
        if self._taps and (now_s - self._taps[-1]) > self.reset_timeout_s:
            self._taps.clear()

        # Append the new tap.
        self._taps.append(now_s)

        # Cap history to max_history (drop oldest).
        if len(self._taps) > self.max_history:
            self._taps.pop(0)

        # Return BPM estimate (None if fewer than 2 taps).
        return self.bpm()

    def bpm(self) -> Optional[float]:
        """Return the current BPM estimate.

        Calculates mean BPM from inter-tap intervals and clamps to
        [min_bpm, max_bpm].

        Returns:
            Current BPM (or None if fewer than 2 taps).
        """
        if len(self._taps) < 2:
            return None

        intervals = self.intervals()
        if not intervals:
            return None

        # Mean interval in seconds → BPM (60 seconds per minute).
        mean_interval_s = statistics.mean(intervals)
        if mean_interval_s == 0:
            return None

        estimated_bpm = 60.0 / mean_interval_s
        return max(self.min_bpm, min(self.max_bpm, estimated_bpm))

    def reset(self) -> None:
        """Clear all taps."""
        self._taps.clear()

    def intervals(self) -> list[float]:
        """Return inter-tap intervals (in seconds).

        Returns:
            List of intervals between consecutive taps (length = len(taps) - 1).
        """
        if len(self._taps) < 2:
            return []

        return [self._taps[i + 1] - self._taps[i] for i in range(len(self._taps) - 1)]

    def stability(self) -> Optional[float]:
        """Return coefficient of variation of inter-tap intervals.

        Lower = more consistent tapping. None if fewer than 3 taps.

        Returns:
            stddev / mean of intervals (or None if <3 taps).
        """
        if len(self._taps) < 3:
            return None

        intervals = self.intervals()
        if not intervals:
            return None

        mean_interval = statistics.mean(intervals)
        if mean_interval == 0:
            return None

        stddev = statistics.stdev(intervals)
        return stddev / mean_interval
