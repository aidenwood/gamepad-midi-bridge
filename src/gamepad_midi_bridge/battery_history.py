"""Battery percentage history tracker — record DualSense battery levels over time.

Records battery samples with timestamps and charging status, estimates drain rate,
and predicts remaining time. Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class BatterySample:
    """A single battery observation.

    Attributes:
        percent: Battery percentage 0..100.
        timestamp_s: Unix timestamp (seconds) when sample was recorded.
        is_charging: Whether the controller was charging at this moment.
    """
    percent: int
    timestamp_s: float
    is_charging: bool = False

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "percent": self.percent,
            "timestamp_s": self.timestamp_s,
            "is_charging": self.is_charging,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BatterySample:
        """Deserialize from JSON-friendly dict."""
        return cls(
            percent=int(d.get("percent", 0)),
            timestamp_s=float(d.get("timestamp_s", 0.0)),
            is_charging=bool(d.get("is_charging", False)),
        )


@dataclass
class BatteryHistoryConfig:
    """Configuration for BatteryHistory.

    Attributes:
        max_samples: Maximum number of samples to keep (clamped 10..100000).
        min_samples_for_estimate: Minimum samples needed for drain rate estimate (clamped 2..100).
    """
    max_samples: int = 1000
    min_samples_for_estimate: int = 3

    def __post_init__(self) -> None:
        """Clamp parameters to valid ranges."""
        self.max_samples = max(10, min(100000, self.max_samples))
        self.min_samples_for_estimate = max(2, min(100, self.min_samples_for_estimate))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "max_samples": self.max_samples,
            "min_samples_for_estimate": self.min_samples_for_estimate,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BatteryHistoryConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            max_samples=int(d.get("max_samples", 1000)),
            min_samples_for_estimate=int(d.get("min_samples_for_estimate", 3)),
        )


class BatteryHistory:
    """Tracks battery level history and estimates drain rate and remaining time.

    Records samples of battery percentage with timestamps and charging status.
    Computes drain rate (percent/hour) and predicts remaining time to discharge.
    """

    def __init__(self, cfg: BatteryHistoryConfig) -> None:
        """Initialize with config.

        Args:
            cfg: BatteryHistoryConfig instance.
        """
        self.cfg = cfg
        self._samples: List[BatterySample] = []

    # ---------------------------------------------------------------- record

    def record(
        self,
        percent: int,
        now_s: float,
        is_charging: bool = False,
    ) -> None:
        """Record a battery sample.

        Clamps percent to 0..100. If count exceeds max_samples, FIFO-removes oldest.

        Args:
            percent: Battery percentage (clamped to 0..100).
            now_s: Unix timestamp in seconds.
            is_charging: Whether the controller is charging.
        """
        pct = max(0, min(100, percent))
        sample = BatterySample(
            percent=pct,
            timestamp_s=now_s,
            is_charging=is_charging,
        )
        self._samples.append(sample)

        # Truncate oldest if we exceeded max
        if len(self._samples) > self.cfg.max_samples:
            self._samples.pop(0)

    # ---------------------------------------------------------------- query

    def current(self) -> Optional[BatterySample]:
        """Return the most recent sample, or None if no samples recorded.

        Returns:
            The latest BatterySample, or None.
        """
        if not self._samples:
            return None
        return self._samples[-1]

    def drain_rate_per_hour(self) -> Optional[float]:
        """Estimate battery drain rate in percent per hour.

        Computes (first_percent - last_percent) / observation_window_hours.
        Returns None if:
            - Fewer than min_samples_for_estimate samples recorded.
            - Any sample in the window has is_charging=True.
            - Drain rate would be negative (indicates charging trend).

        Returns:
            Drain rate in percent/hour, or None if estimate unavailable.
        """
        if len(self._samples) < self.cfg.min_samples_for_estimate:
            return None

        # Check if any sample is marked as charging
        if any(s.is_charging for s in self._samples):
            return None

        first = self._samples[0]
        last = self._samples[-1]

        time_hours = (last.timestamp_s - first.timestamp_s) / 3600.0
        if time_hours <= 0:
            return None

        drain_pct = first.percent - last.percent
        if drain_pct < 0:
            # Charging trend detected; return 0 instead of negative
            return 0.0

        rate = drain_pct / time_hours
        return rate

    def predicted_remaining_minutes(self) -> Optional[float]:
        """Predict remaining time until battery is fully discharged.

        Returns (current_percent / drain_per_hour * 60).
        Returns None if:
            - Current percent is not available.
            - Drain rate estimate is unavailable or is 0.

        Returns:
            Remaining minutes until discharge, or None.
        """
        current = self.current()
        if current is None:
            return None

        drain_rate = self.drain_rate_per_hour()
        if drain_rate is None or drain_rate <= 0:
            return None

        remaining_min = (current.percent / drain_rate) * 60.0
        return remaining_min

    def peak_drain_rate(self) -> Optional[float]:
        """Return the maximum drain rate observed over any 2-sample window.

        Examines consecutive pairs of samples and returns the highest drain rate.
        Returns None if fewer than 2 samples or if no discharging window found.

        Returns:
            Peak percent/hour, or None.
        """
        if len(self._samples) < 2:
            return None

        max_rate = None
        for i in range(len(self._samples) - 1):
            first = self._samples[i]
            second = self._samples[i + 1]

            # Skip windows with charging
            if first.is_charging or second.is_charging:
                continue

            time_hours = (second.timestamp_s - first.timestamp_s) / 3600.0
            if time_hours <= 0:
                continue

            drain_pct = first.percent - second.percent
            if drain_pct < 0:
                # Skip charging windows
                continue

            rate = drain_pct / time_hours
            if max_rate is None or rate > max_rate:
                max_rate = rate

        return max_rate

    def last_charge_time(self) -> Optional[float]:
        """Return the timestamp of the most recent charging sample.

        Returns None if no charging samples recorded.

        Returns:
            Unix timestamp of most recent charging sample, or None.
        """
        for sample in reversed(self._samples):
            if sample.is_charging:
                return sample.timestamp_s
        return None

    # ---------------------------------------------------------------- clear

    def clear(self) -> None:
        """Delete all recorded samples."""
        self._samples.clear()

    # ---------------------------------------------------------------- summary

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of current state and estimates.

        Returns:
            Dict with keys:
                - "current": Current percent (int), or None.
                - "drain_per_hour": Estimated drain rate, or None.
                - "remaining_min": Predicted remaining minutes, or None.
                - "samples": Number of samples recorded (int).
                - "is_charging": Whether the most recent sample shows charging (bool).
        """
        current_sample = self.current()
        return {
            "current": current_sample.percent if current_sample else None,
            "drain_per_hour": self.drain_rate_per_hour(),
            "remaining_min": self.predicted_remaining_minutes(),
            "samples": len(self._samples),
            "is_charging": current_sample.is_charging if current_sample else False,
        }
