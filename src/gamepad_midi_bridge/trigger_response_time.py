"""Trigger pull response time analyzer — measures how long each trigger takes to reach peak pressure.

Records the time it takes for L2/R2 triggers to travel from rest to peak pressure,
providing a rough proxy for how "snappy" or "soft" the player's touch is. Pure stdlib, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PullEvent:
    """A single trigger pull observation.

    Attributes:
        trigger: "L2" or "R2" identifier.
        start_at_s: Unix timestamp (seconds) when pull began (pressure exceeded release_threshold).
        peak_at_s: Unix timestamp (seconds) when peak pressure was reached.
        peak_pressure: Maximum pressure recorded during the pull (0..1).
        duration_ms: Time from start to peak in milliseconds.
    """
    trigger: str
    start_at_s: float
    peak_at_s: float
    peak_pressure: float
    duration_ms: float

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "trigger": self.trigger,
            "start_at_s": self.start_at_s,
            "peak_at_s": self.peak_at_s,
            "peak_pressure": self.peak_pressure,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PullEvent:
        """Deserialize from JSON-friendly dict."""
        return cls(
            trigger=str(d.get("trigger", "L2")),
            start_at_s=float(d.get("start_at_s", 0.0)),
            peak_at_s=float(d.get("peak_at_s", 0.0)),
            peak_pressure=float(d.get("peak_pressure", 0.0)),
            duration_ms=float(d.get("duration_ms", 0.0)),
        )


@dataclass
class TriggerResponseConfig:
    """Configuration for TriggerResponseAnalyzer.

    Attributes:
        release_threshold: Pressure below which a trigger is considered "released" (clamped 0..1).
        peak_min: Minimum peak pressure to count as a valid pull (clamped 0..1).
        max_pulls: Maximum number of pulls to keep in history (clamped 10..100000).
    """
    release_threshold: float = 0.05
    peak_min: float = 0.7
    max_pulls: int = 1000

    def __post_init__(self) -> None:
        """Clamp parameters to valid ranges."""
        self.release_threshold = max(0.0, min(1.0, self.release_threshold))
        self.peak_min = max(0.0, min(1.0, self.peak_min))
        self.max_pulls = max(10, min(100000, self.max_pulls))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "release_threshold": self.release_threshold,
            "peak_min": self.peak_min,
            "max_pulls": self.max_pulls,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TriggerResponseConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            release_threshold=float(d.get("release_threshold", 0.05)),
            peak_min=float(d.get("peak_min", 0.7)),
            max_pulls=int(d.get("max_pulls", 1000)),
        )


class TriggerResponseAnalyzer:
    """Analyzes trigger pull response times and provides snappiness metrics.

    Tracks when L2/R2 triggers are pressed and released, records the time to reach
    peak pressure, and provides statistics on how long pulls typically take.
    """

    def __init__(self, cfg: TriggerResponseConfig) -> None:
        """Initialize with config.

        Args:
            cfg: TriggerResponseConfig instance.
        """
        self.cfg = cfg
        self._state: Dict[str, Dict[str, Any]] = {
            "L2": {
                "is_pressed": False,
                "start_at_s": 0.0,
                "peak_pressure": 0.0,
                "peak_at_s": 0.0,
            },
            "R2": {
                "is_pressed": False,
                "start_at_s": 0.0,
                "peak_pressure": 0.0,
                "peak_at_s": 0.0,
            },
        }
        self._pulls: List[PullEvent] = []

    # ---------------------------------------------------------------- record

    def record(
        self,
        trigger: str,
        pressure: float,
        now_s: float,
    ) -> Optional[PullEvent]:
        """Record a trigger pressure sample.

        Clamps pressure to 0..1. Tracks pull start/peak, and finalizes when released.
        Unknown trigger names are silently ignored.

        Args:
            trigger: "L2" or "R2" identifier.
            pressure: Trigger pressure (clamped to 0..1).
            now_s: Unix timestamp in seconds.

        Returns:
            A completed PullEvent if the trigger was just released and peak >= peak_min,
            otherwise None.
        """
        # Ignore unknown triggers
        if trigger not in self._state:
            return None

        # Clamp pressure to valid range
        pressure = max(0.0, min(1.0, pressure))
        state = self._state[trigger]

        # Transition: not pressed -> pressed
        if pressure > self.cfg.release_threshold and not state["is_pressed"]:
            state["is_pressed"] = True
            state["start_at_s"] = now_s
            state["peak_pressure"] = pressure
            state["peak_at_s"] = now_s
            return None

        # Pressed: update peak if this sample is higher
        if pressure > self.cfg.release_threshold and state["is_pressed"]:
            if pressure > state["peak_pressure"]:
                state["peak_pressure"] = pressure
                state["peak_at_s"] = now_s
            return None

        # Transition: pressed -> not pressed (release)
        if pressure <= self.cfg.release_threshold and state["is_pressed"]:
            state["is_pressed"] = False
            peak_pres = state["peak_pressure"]

            # Only emit PullEvent if peak meets threshold
            if peak_pres >= self.cfg.peak_min:
                duration_ms = (state["peak_at_s"] - state["start_at_s"]) * 1000.0
                event = PullEvent(
                    trigger=trigger,
                    start_at_s=state["start_at_s"],
                    peak_at_s=state["peak_at_s"],
                    peak_pressure=peak_pres,
                    duration_ms=duration_ms,
                )
                self._pulls.append(event)

                # FIFO eviction if we exceed max_pulls
                if len(self._pulls) > self.cfg.max_pulls:
                    self._pulls.pop(0)

                return event

            return None

        # No transition
        return None

    # ---------------------------------------------------------------- query

    def mean_duration_ms(self, trigger: Optional[str] = None) -> Optional[float]:
        """Compute mean pull duration in milliseconds.

        Filters by trigger name if provided. Returns None if no pulls match.

        Args:
            trigger: Optional "L2" or "R2" to filter; None = all triggers.

        Returns:
            Mean duration in milliseconds, or None if no matching pulls.
        """
        if trigger is None:
            pulls = self._pulls
        else:
            pulls = [p for p in self._pulls if p.trigger == trigger]

        if not pulls:
            return None

        return sum(p.duration_ms for p in pulls) / len(pulls)

    def min_duration_ms(self, trigger: Optional[str] = None) -> Optional[float]:
        """Return the fastest pull duration in milliseconds.

        Filters by trigger name if provided. Returns None if no pulls match.

        Args:
            trigger: Optional "L2" or "R2" to filter; None = all triggers.

        Returns:
            Minimum duration in milliseconds, or None if no matching pulls.
        """
        if trigger is None:
            pulls = self._pulls
        else:
            pulls = [p for p in self._pulls if p.trigger == trigger]

        if not pulls:
            return None

        return min(p.duration_ms for p in pulls)

    def max_duration_ms(self, trigger: Optional[str] = None) -> Optional[float]:
        """Return the slowest pull duration in milliseconds.

        Filters by trigger name if provided. Returns None if no pulls match.

        Args:
            trigger: Optional "L2" or "R2" to filter; None = all triggers.

        Returns:
            Maximum duration in milliseconds, or None if no matching pulls.
        """
        if trigger is None:
            pulls = self._pulls
        else:
            pulls = [p for p in self._pulls if p.trigger == trigger]

        if not pulls:
            return None

        return max(p.duration_ms for p in pulls)

    def pull_count(self, trigger: Optional[str] = None) -> int:
        """Return the number of recorded pulls.

        Filters by trigger name if provided.

        Args:
            trigger: Optional "L2" or "R2" to filter; None = all triggers.

        Returns:
            Count of pulls (int).
        """
        if trigger is None:
            return len(self._pulls)
        return len([p for p in self._pulls if p.trigger == trigger])

    # ---------------------------------------------------------------- summary

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of pull statistics.

        Returns:
            Dict with keys:
                - "L2_mean_ms": Mean L2 pull duration (ms), or None.
                - "L2_count": Number of L2 pulls recorded (int).
                - "R2_mean_ms": Mean R2 pull duration (ms), or None.
                - "R2_count": Number of R2 pulls recorded (int).
                - "fastest_ms": Fastest pull across all triggers (ms), or None.
                - "slowest_ms": Slowest pull across all triggers (ms), or None.
        """
        return {
            "L2_mean_ms": self.mean_duration_ms("L2"),
            "L2_count": self.pull_count("L2"),
            "R2_mean_ms": self.mean_duration_ms("R2"),
            "R2_count": self.pull_count("R2"),
            "fastest_ms": self.min_duration_ms(),
            "slowest_ms": self.max_duration_ms(),
        }

    # ---------------------------------------------------------------- clear

    def clear(self) -> None:
        """Delete all recorded pulls."""
        self._pulls.clear()
