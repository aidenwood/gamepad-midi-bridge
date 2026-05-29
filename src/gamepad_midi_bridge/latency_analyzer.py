"""Latency analyzer — records timestamps for MIDI sent/received and computes round-trip statistics."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import statistics


# ================================================================ LatencyMeasurement


@dataclass
class LatencyMeasurement:
    """A single round-trip latency measurement."""

    sent_at_s: float
    received_at_s: float
    label: str = ""

    @property
    def round_trip_ms(self) -> float:
        """Computed: round-trip time in milliseconds."""
        return (self.received_at_s - self.sent_at_s) * 1000.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict (includes computed round_trip_ms)."""
        return {
            "sent_at_s": self.sent_at_s,
            "received_at_s": self.received_at_s,
            "round_trip_ms": self.round_trip_ms,
            "label": self.label,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> LatencyMeasurement:
        """Deserialize from dict (ignores computed round_trip_ms)."""
        return LatencyMeasurement(
            sent_at_s=d["sent_at_s"],
            received_at_s=d["received_at_s"],
            label=d.get("label", ""),
        )


# ================================================================ LatencyAnalyzerConfig


@dataclass
class LatencyAnalyzerConfig:
    """Configuration for LatencyAnalyzer."""

    max_measurements: int = 1000
    timeout_ms: float = 500.0

    def __post_init__(self) -> None:
        """Clamp values to safe ranges."""
        self.max_measurements = max(10, min(100000, self.max_measurements))
        self.timeout_ms = max(10.0, min(10000.0, self.timeout_ms))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> LatencyAnalyzerConfig:
        """Deserialize from dict."""
        cfg = LatencyAnalyzerConfig(
            max_measurements=d.get("max_measurements", 1000),
            timeout_ms=d.get("timeout_ms", 500.0),
        )
        return cfg


# ================================================================ LatencyAnalyzer


class LatencyAnalyzer:
    """
    Records timestamps for sent/received MIDI messages and computes
    round-trip latency statistics (mean, median, percentiles, jitter).
    """

    def __init__(self, cfg: LatencyAnalyzerConfig) -> None:
        """Initialize with config."""
        self.cfg = cfg
        self._pending: dict[str, float] = {}  # token → sent_at_s
        self._measurements: list[LatencyMeasurement] = []

    def mark_sent(self, token: str, now_s: float, label: str = "") -> None:
        """Record a sent MIDI message. Token is caller-chosen identifier."""
        self._pending[token] = now_s

    def mark_received(
        self, token: str, now_s: float, label: str = ""
    ) -> Optional[LatencyMeasurement]:
        """
        Record a received MIDI echo/response.
        Returns measurement if token found, else None.
        Appends to measurements list (FIFO eviction if > max).
        """
        if token not in self._pending:
            return None

        sent_at_s = self._pending.pop(token)
        measurement = LatencyMeasurement(
            sent_at_s=sent_at_s,
            received_at_s=now_s,
            label=label,
        )

        self._measurements.append(measurement)

        # FIFO eviction: remove oldest if at or over capacity
        while len(self._measurements) > self.cfg.max_measurements:
            self._measurements.pop(0)

        return measurement

    def prune_timed_out(self, now_s: float) -> int:
        """
        Remove pending entries where now_s - sent_at_s > timeout_ms / 1000.
        Returns count pruned.
        """
        timeout_s = self.cfg.timeout_ms / 1000.0
        tokens_to_remove = [
            token
            for token, sent_at_s in self._pending.items()
            if (now_s - sent_at_s) > timeout_s
        ]

        for token in tokens_to_remove:
            del self._pending[token]

        return len(tokens_to_remove)

    def mean_ms(self) -> Optional[float]:
        """Arithmetic mean of round_trip_ms across all measurements."""
        if not self._measurements:
            return None
        return statistics.mean(m.round_trip_ms for m in self._measurements)

    def median_ms(self) -> Optional[float]:
        """Median of round_trip_ms."""
        if not self._measurements:
            return None
        return statistics.median(m.round_trip_ms for m in self._measurements)

    def min_ms(self) -> Optional[float]:
        """Minimum round_trip_ms."""
        if not self._measurements:
            return None
        return min(m.round_trip_ms for m in self._measurements)

    def max_ms(self) -> Optional[float]:
        """Maximum round_trip_ms."""
        if not self._measurements:
            return None
        return max(m.round_trip_ms for m in self._measurements)

    def percentile_ms(self, p: float) -> Optional[float]:
        """
        Percentile of round_trip_ms (0 <= p <= 100).
        Returns None if < 2 measurements (quantiles requires at least 2).
        """
        if len(self._measurements) < 2:
            return None
        return statistics.quantiles(
            [m.round_trip_ms for m in self._measurements],
            n=100,
        )[int(p) - 1]

    def jitter_ms(self) -> Optional[float]:
        """
        Standard deviation of round_trip_ms (jitter).
        Returns None if < 2 measurements.
        """
        if len(self._measurements) < 2:
            return None
        return statistics.stdev(m.round_trip_ms for m in self._measurements)

    def summary(self) -> dict[str, Any]:
        """Return dict with count, mean, median, min, max, jitter, p95."""
        return {
            "count": len(self._measurements),
            "mean_ms": self.mean_ms(),
            "median_ms": self.median_ms(),
            "min_ms": self.min_ms(),
            "max_ms": self.max_ms(),
            "jitter_ms": self.jitter_ms(),
            "p95_ms": self.percentile_ms(95),
        }

    def clear(self) -> None:
        """Empty both pending and measurements."""
        self._pending.clear()
        self._measurements.clear()

    def pending_count(self) -> int:
        """Count of in-flight measurements (sent but not yet received)."""
        return len(self._pending)
