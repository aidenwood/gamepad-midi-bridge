"""Aftertouch peak analyzer — records aftertouch pressure events and exposes peak/mean stats.

Records aftertouch pressure values per note/channel pair, tracks peak pressure,
mean pressure, minimum pressure, and sample counts. Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AftertouchPeakAnalysis:
    """Analysis of aftertouch pressure for a single note/channel pair.

    Attributes:
        note: MIDI note number 0..127.
        channel: MIDI channel 1..16.
        peak_value: Maximum aftertouch pressure recorded (0..127).
        mean_value: Average aftertouch pressure across all samples (0..127).
        min_value: Minimum aftertouch pressure recorded (0..127).
        sample_count: Number of aftertouch samples recorded.
    """
    note: int
    channel: int
    peak_value: int
    mean_value: float
    min_value: int
    sample_count: int

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "note": self.note,
            "channel": self.channel,
            "peak_value": self.peak_value,
            "mean_value": self.mean_value,
            "min_value": self.min_value,
            "sample_count": self.sample_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AftertouchPeakAnalysis:
        """Deserialize from JSON-friendly dict."""
        return cls(
            note=int(d.get("note", 0)),
            channel=int(d.get("channel", 1)),
            peak_value=int(d.get("peak_value", 0)),
            mean_value=float(d.get("mean_value", 0.0)),
            min_value=int(d.get("min_value", 0)),
            sample_count=int(d.get("sample_count", 0)),
        )


@dataclass
class AftertouchPeakConfig:
    """Configuration for AftertouchPeakAnalyzer.

    Attributes:
        max_samples_per_note: Maximum number of samples per (note, channel) pair
                              (clamped 10..100000).
    """
    max_samples_per_note: int = 500

    def __post_init__(self) -> None:
        """Clamp parameters to valid ranges."""
        self.max_samples_per_note = max(10, min(100000, self.max_samples_per_note))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "max_samples_per_note": self.max_samples_per_note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AftertouchPeakConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            max_samples_per_note=int(d.get("max_samples_per_note", 500)),
        )


class AftertouchPeakAnalyzer:
    """Tracks aftertouch pressure peaks and statistics per note/channel.

    Records aftertouch pressure samples indexed by (note, channel) pair,
    computes peak, mean, and minimum values, and provides statistical summaries.
    """

    def __init__(self, cfg: AftertouchPeakConfig) -> None:
        """Initialize with config.

        Args:
            cfg: AftertouchPeakConfig instance.
        """
        self.cfg = cfg
        self._samples: Dict[Tuple[int, int], List[int]] = {}

    # ---------------------------------------------------------------- record

    def record(self, note: int, channel: int, value: int) -> None:
        """Record an aftertouch pressure sample for a note/channel pair.

        Clamps note to 0..127, channel to 1..16, value to 0..127.
        If sample count for (note, channel) exceeds max_samples_per_note,
        FIFO-removes oldest.

        Args:
            note: MIDI note number (clamped to 0..127).
            channel: MIDI channel (clamped to 1..16).
            value: Aftertouch pressure (clamped to 0..127).
        """
        note = max(0, min(127, note))
        channel = max(1, min(16, channel))
        value = max(0, min(127, value))

        key = (note, channel)
        if key not in self._samples:
            self._samples[key] = []

        self._samples[key].append(value)

        # Truncate oldest if we exceeded max
        if len(self._samples[key]) > self.cfg.max_samples_per_note:
            self._samples[key].pop(0)

    # ---------------------------------------------------------------- query

    def analyze_note(
        self, note: int, channel: int
    ) -> Optional[AftertouchPeakAnalysis]:
        """Analyze aftertouch data for a specific note/channel pair.

        Returns analysis with peak, mean, min, and sample count,
        or None if no samples recorded for this pair.

        Args:
            note: MIDI note number.
            channel: MIDI channel.

        Returns:
            AftertouchPeakAnalysis, or None if no data.
        """
        key = (note, channel)
        if key not in self._samples or not self._samples[key]:
            return None

        samples = self._samples[key]
        return AftertouchPeakAnalysis(
            note=note,
            channel=channel,
            peak_value=max(samples),
            mean_value=mean(samples),
            min_value=min(samples),
            sample_count=len(samples),
        )

    def analyze_all(self) -> List[AftertouchPeakAnalysis]:
        """Analyze all recorded note/channel pairs.

        Returns:
            List of AftertouchPeakAnalysis, sorted by peak_value descending.
        """
        analyses = []
        for (note, channel) in self._samples:
            analysis = self.analyze_note(note, channel)
            if analysis is not None:
                analyses.append(analysis)

        # Sort by peak_value descending
        analyses.sort(key=lambda a: a.peak_value, reverse=True)
        return analyses

    def top_notes(self, n: int = 5) -> List[AftertouchPeakAnalysis]:
        """Return top N note/channel pairs by peak pressure.

        Args:
            n: Number of top notes to return (default 5).

        Returns:
            List of top N AftertouchPeakAnalysis sorted by peak_value descending.
        """
        all_analyses = self.analyze_all()
        return all_analyses[:n]

    def total_records(self) -> int:
        """Return total number of aftertouch samples across all note/channel pairs.

        Returns:
            Sum of sample counts.
        """
        return sum(len(samples) for samples in self._samples.values())

    def note_count(self) -> int:
        """Return number of distinct (note, channel) pairs with samples.

        Returns:
            Count of unique pairs.
        """
        return len(self._samples)

    # ---------------------------------------------------------------- clear

    def clear(self) -> None:
        """Delete all recorded samples."""
        self._samples.clear()

    # ---------------------------------------------------------------- summary

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of current state and statistics.

        Returns:
            Dict with keys:
                - "note_count": Number of distinct (note, channel) pairs (int).
                - "total_records": Total samples across all pairs (int).
                - "overall_peak": Maximum pressure recorded across all pairs (int), or None.
                - "overall_mean": Average pressure across all pairs (float), or None.
        """
        if not self._samples:
            return {
                "note_count": 0,
                "total_records": 0,
                "overall_peak": None,
                "overall_mean": None,
            }

        all_analyses = self.analyze_all()
        all_values = [v for samples in self._samples.values() for v in samples]

        return {
            "note_count": len(self._samples),
            "total_records": len(all_values),
            "overall_peak": max(all_values) if all_values else None,
            "overall_mean": mean(all_values) if all_values else None,
        }
