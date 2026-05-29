"""Trigger-tap cadence detector: recognize rhythmic tapping on analog triggers.

Pure stdlib, no Qt, no global state. Detects press/release events on L2/R2
triggers and estimates BPM from a sequence of taps. Distinct from tempo_tap
because triggers are analog — this module first detects press-then-release
events via hysteresis thresholds before computing cadence.

Usage:
    cfg = TriggerCadenceConfig(tap_threshold=0.5, release_threshold=0.1)
    detector = TriggerCadenceDetector(cfg)
    bpm = detector.feed('L2', pressure=0.8, now_s=0.0)  # None (only 1 tap)
    bpm = detector.feed('L2', pressure=0.0, now_s=0.1)  # Release recorded
    bpm = detector.feed('L2', pressure=0.8, now_s=0.5)  # 2nd tap, still None
    bpm = detector.feed('L2', pressure=0.0, now_s=0.6)  # 3rd press detected, ~120 BPM
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TriggerCadenceConfig:
    """Configuration for trigger cadence detection.

    Attributes:
        tap_threshold: Pressure threshold to detect press (0.1..1.0).
                      Pressure above this counts as a press.
        release_threshold: Pressure threshold to detect release (0.0..0.9).
                          Pressure below this counts as a release.
                          Must be < tap_threshold (auto-clamped in __post_init__).
        min_taps: Minimum taps to compute cadence (2..32).
        max_history: Maximum tap times to retain (4..256).
        reset_after_ms: Gap longer than this (ms) clears history (100..30000).
                       Converted to seconds internally.
        min_bpm: Clamp BPM estimate to this floor (default 30).
        max_bpm: Clamp BPM estimate to this ceiling (default 300).
    """

    tap_threshold: float = 0.5
    release_threshold: float = 0.1
    min_taps: int = 3
    max_history: int = 16
    reset_after_ms: int = 2000
    min_bpm: float = 30.0
    max_bpm: float = 300.0

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp tap_threshold to 0.1..1.0.
        self.tap_threshold = max(0.1, min(1.0, self.tap_threshold))

        # Clamp release_threshold to 0.0..0.9.
        self.release_threshold = max(0.0, min(0.9, self.release_threshold))

        # Ensure release_threshold < tap_threshold.
        if self.release_threshold >= self.tap_threshold:
            self.release_threshold = self.tap_threshold - 0.1
            self.release_threshold = max(0.0, self.release_threshold)

        # Clamp min_taps to 2..32.
        self.min_taps = max(2, min(32, self.min_taps))

        # Clamp max_history to 4..256.
        self.max_history = max(4, min(256, self.max_history))

        # Clamp reset_after_ms to 100..30000.
        self.reset_after_ms = max(100, min(30000, self.reset_after_ms))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "tap_threshold": self.tap_threshold,
            "release_threshold": self.release_threshold,
            "min_taps": self.min_taps,
            "max_history": self.max_history,
            "reset_after_ms": self.reset_after_ms,
            "min_bpm": self.min_bpm,
            "max_bpm": self.max_bpm,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TriggerCadenceConfig:
        """Deserialize from a JSON-compatible dict."""
        return cls(
            tap_threshold=data.get("tap_threshold", 0.5),
            release_threshold=data.get("release_threshold", 0.1),
            min_taps=data.get("min_taps", 3),
            max_history=data.get("max_history", 16),
            reset_after_ms=data.get("reset_after_ms", 2000),
            min_bpm=data.get("min_bpm", 30.0),
            max_bpm=data.get("max_bpm", 300.0),
        )


class TriggerCadenceDetector:
    """Detects rhythmic tapping cadence on L2/R2 trigger via press/release events.

    Maintains a state machine per trigger:
      - "released": waiting for pressure > tap_threshold
      - "pressed": waiting for pressure < release_threshold

    Each press-to-release cycle records a tap time. BPM is estimated from
    the mean inter-tap interval.
    """

    def __init__(self, cfg: TriggerCadenceConfig):
        """Initialize the trigger cadence detector.

        Args:
            cfg: TriggerCadenceConfig instance.
        """
        self.cfg = cfg
        self._state: Dict[str, str] = {"L2": "released", "R2": "released"}
        self._tap_times: Dict[str, List[float]] = {"L2": [], "R2": []}
        self._current_bpm: Dict[str, Optional[float]] = {"L2": None, "R2": None}

    def feed(self, trigger: str, pressure: float, now_s: float) -> Optional[float]:
        """Process a trigger pressure sample and return current BPM if available.

        Tracks state machine for the trigger and records tap times when
        press events are detected (pressure crosses above tap_threshold).
        Returns the current BPM estimate (None if insufficient taps).

        Args:
            trigger: Trigger name ("L2" or "R2"). Unknown triggers are ignored.
            pressure: Analog pressure (0.0..1.0).
            now_s: Current time in seconds (from any reference point).

        Returns:
            Current BPM estimate for this trigger (or None if < min_taps).
        """
        # Ignore unknown triggers.
        if trigger not in {"L2", "R2"}:
            return None

        state = self._state[trigger]
        reset_threshold_s = self.cfg.reset_after_ms / 1000.0

        # State machine: released -> pressed on cross-above tap_threshold.
        if state == "released" and pressure > self.cfg.tap_threshold:
            self._state[trigger] = "pressed"

            # Prune history if gap from previous tap exceeds reset threshold.
            if self._tap_times[trigger]:
                gap_s = now_s - self._tap_times[trigger][-1]
                if gap_s > reset_threshold_s:
                    self._tap_times[trigger].clear()

            # Record this tap.
            self._tap_times[trigger].append(now_s)

            # Truncate to max_history (drop oldest).
            if len(self._tap_times[trigger]) > self.cfg.max_history:
                self._tap_times[trigger].pop(0)

            # Compute BPM.
            self._current_bpm[trigger] = self._compute_bpm(trigger)

        # State machine: pressed -> released on cross-below release_threshold.
        elif state == "pressed" and pressure < self.cfg.release_threshold:
            self._state[trigger] = "released"

        return self._current_bpm[trigger]

    def _compute_bpm(self, trigger: str) -> Optional[float]:
        """Compute BPM from tap times for the given trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            BPM estimate (clamped to [min_bpm, max_bpm]) or None if < min_taps.
        """
        tap_times = self._tap_times[trigger]

        if len(tap_times) < self.cfg.min_taps:
            return None

        # Compute inter-tap intervals.
        intervals = [tap_times[i + 1] - tap_times[i] for i in range(len(tap_times) - 1)]

        if not intervals:
            return None

        mean_interval_s = statistics.mean(intervals)
        if mean_interval_s == 0:
            return None

        estimated_bpm = 60.0 / mean_interval_s
        return max(self.cfg.min_bpm, min(self.cfg.max_bpm, estimated_bpm))

    def current_bpm(self, trigger: str) -> Optional[float]:
        """Return the last computed BPM for a trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Last computed BPM (or None if insufficient taps or unknown trigger).
        """
        if trigger not in {"L2", "R2"}:
            return None
        return self._current_bpm[trigger]

    def clear(self, trigger: Optional[str] = None) -> None:
        """Clear tap history and state for one or both triggers.

        Args:
            trigger: Trigger name ("L2" or "R2"). If None, clear all triggers.
        """
        if trigger is None:
            # Clear all.
            for t in {"L2", "R2"}:
                self._tap_times[t].clear()
                self._state[t] = "released"
                self._current_bpm[t] = None
        elif trigger in {"L2", "R2"}:
            # Clear only this trigger.
            self._tap_times[trigger].clear()
            self._state[trigger] = "released"
            self._current_bpm[trigger] = None

    def tap_count(self, trigger: str) -> int:
        """Return the number of taps recorded for a trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Number of taps in current window (0 if unknown trigger).
        """
        if trigger not in {"L2", "R2"}:
            return 0
        return len(self._tap_times[trigger])

    def stability(self, trigger: str) -> Optional[float]:
        """Return coefficient of variation of inter-tap intervals for a trigger.

        Lower = more consistent tapping. None if < min_taps or insufficient intervals.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Coefficient of variation (stddev / mean) of intervals, or None.
        """
        if trigger not in {"L2", "R2"}:
            return None

        tap_times = self._tap_times[trigger]

        if len(tap_times) < self.cfg.min_taps:
            return None

        intervals = [tap_times[i + 1] - tap_times[i] for i in range(len(tap_times) - 1)]

        if not intervals or len(intervals) < 2:
            return None

        mean_interval = statistics.mean(intervals)
        if mean_interval == 0:
            return None

        stddev = statistics.stdev(intervals)
        return stddev / mean_interval
