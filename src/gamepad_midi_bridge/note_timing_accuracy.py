"""Note-timing accuracy meter for comparing note timestamps against a BPM grid.

Pure stdlib module that measures how often a user lands "on", "ahead", or "behind"
the beat. Tracks offsets from the nearest grid subdivision and computes accuracy
statistics.
"""

import math
from dataclasses import dataclass, asdict, field
from typing import Dict, List

from . import bpm_sync


@dataclass
class TimingAccuracyConfig:
    """Configuration for note-timing accuracy measurement.

    Attributes:
        bpm: Tempo in beats per minute (clamped 20–400).
        subdivision: Subdivision to measure against (validated; unknown → "1/16").
        tolerance_ms: Window around grid point where note is "on" (clamped 1–500ms).
        max_samples: Maximum samples to keep in history (clamped 10–1000000).
    """

    bpm: float = 120.0
    subdivision: str = "1/16"
    tolerance_ms: float = 20.0
    max_samples: int = 1000

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Clamp BPM to 20–400 range
        self.bpm = max(20.0, min(400.0, self.bpm))

        # Validate subdivision; default to "1/16" if unknown
        if self.subdivision not in bpm_sync.SUBDIVISIONS:
            self.subdivision = "1/16"

        # Clamp tolerance_ms to 1–500
        self.tolerance_ms = max(1.0, min(500.0, self.tolerance_ms))

        # Clamp max_samples to 10–1000000
        self.max_samples = max(10, min(1000000, self.max_samples))

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: bpm, subdivision, tolerance_ms, max_samples.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "TimingAccuracyConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with keys: bpm, subdivision, tolerance_ms, max_samples.

        Returns:
            TimingAccuracyConfig instance with validated values.
        """
        return TimingAccuracyConfig(
            bpm=data.get("bpm", 120.0),
            subdivision=data.get("subdivision", "1/16"),
            tolerance_ms=data.get("tolerance_ms", 20.0),
            max_samples=data.get("max_samples", 1000),
        )


@dataclass
class TimingAccuracy:
    """Timing accuracy report from analysis.

    Attributes:
        on_count: Number of notes within tolerance window.
        ahead_count: Number of notes that came early (before grid point).
        behind_count: Number of notes that came late (after grid point).
        total: Total number of samples analyzed.
        mean_offset_ms: Average offset (negative = ahead, positive = behind).
        worst_offset_ms: Maximum absolute offset magnitude.
        accuracy_pct: Percentage of notes within tolerance (0–100).
    """

    on_count: int = 0
    ahead_count: int = 0
    behind_count: int = 0
    total: int = 0
    mean_offset_ms: float = 0.0
    worst_offset_ms: float = 0.0
    accuracy_pct: float = 0.0

    def to_dict(self) -> Dict[str, any]:
        """Serialize report to a dictionary.

        Returns:
            Dictionary with all timing accuracy fields.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "TimingAccuracy":
        """Deserialise report from a dictionary.

        Args:
            data: Dictionary with timing accuracy fields.

        Returns:
            TimingAccuracy instance.
        """
        return TimingAccuracy(
            on_count=data.get("on_count", 0),
            ahead_count=data.get("ahead_count", 0),
            behind_count=data.get("behind_count", 0),
            total=data.get("total", 0),
            mean_offset_ms=data.get("mean_offset_ms", 0.0),
            worst_offset_ms=data.get("worst_offset_ms", 0.0),
            accuracy_pct=data.get("accuracy_pct", 0.0),
        )


class NoteTimingAccuracy:
    """Measures note timing accuracy against a BPM grid.

    Tracks when notes arrive relative to grid subdivision points and computes
    timing statistics (how many on-beat, early, late, mean offset, etc).
    """

    def __init__(self, cfg: TimingAccuracyConfig, ref_start_s: float = 0.0) -> None:
        """Initialize the accuracy meter.

        Args:
            cfg: TimingAccuracyConfig with BPM, subdivision, tolerance, and sample limit.
            ref_start_s: Reference start time in seconds for grid alignment (default: 0.0).
        """
        self.config = cfg
        self.ref_start_s = ref_start_s
        self._offsets_ms: List[float] = []

    def record(self, now_s: float) -> float:
        """Record a note timestamp and compute its offset from the nearest grid point.

        Args:
            now_s: Current timestamp in seconds (typically from time.time() or similar).

        Returns:
            Offset in milliseconds (negative = ahead, positive = behind).
        """
        # Get duration since reference start
        elapsed_s = now_s - self.ref_start_s

        # Get subdivision duration in milliseconds
        sub_ms = bpm_sync.subdivision_ms(self.config.bpm, self.config.subdivision)

        # Convert elapsed time to milliseconds
        elapsed_ms = elapsed_s * 1000.0

        # Find nearest grid point
        grid_index = round(elapsed_ms / sub_ms)
        nearest_grid_ms = grid_index * sub_ms

        # Compute offset
        offset_ms = elapsed_ms - nearest_grid_ms

        # Maintain FIFO history with max_samples limit
        self._offsets_ms.append(offset_ms)
        if len(self._offsets_ms) > self.config.max_samples:
            self._offsets_ms.pop(0)

        return offset_ms

    def analyze(self) -> TimingAccuracy:
        """Analyze recorded offsets and return timing accuracy report.

        Returns:
            TimingAccuracy instance with on/ahead/behind counts and statistics.
        """
        if not self._offsets_ms:
            return TimingAccuracy(total=0, accuracy_pct=0.0)

        total = len(self._offsets_ms)
        on_count = 0
        ahead_count = 0
        behind_count = 0
        worst_offset = 0.0
        sum_offset = 0.0

        for offset in self._offsets_ms:
            abs_offset = abs(offset)
            worst_offset = max(worst_offset, abs_offset)
            sum_offset += offset

            # Classify based on tolerance window
            if abs_offset <= self.config.tolerance_ms:
                on_count += 1
            elif offset < 0:
                ahead_count += 1
            else:
                behind_count += 1

        mean_offset = sum_offset / total
        accuracy_pct = (on_count / total) * 100.0 if total > 0 else 0.0

        return TimingAccuracy(
            on_count=on_count,
            ahead_count=ahead_count,
            behind_count=behind_count,
            total=total,
            mean_offset_ms=mean_offset,
            worst_offset_ms=worst_offset,
            accuracy_pct=accuracy_pct,
        )

    def clear(self) -> None:
        """Clear all recorded samples."""
        self._offsets_ms.clear()

    def total(self) -> int:
        """Return total number of recorded samples."""
        return len(self._offsets_ms)
