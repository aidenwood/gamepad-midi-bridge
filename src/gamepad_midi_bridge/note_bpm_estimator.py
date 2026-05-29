"""Note-based BPM auto-estimator.

Takes a stream of note_on timestamps from ANY note (drums, bass, lead — anything
the user is playing) and infers a likely BPM via autocorrelation-style analysis
on note intervals.

Pure stdlib + statistics, no Qt dependencies.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class NoteBpmConfig:
    """Configuration for note-based BPM estimation.

    Attributes:
        enabled: Whether BPM estimation is active.
        min_bpm: Minimum BPM for clamping. Clamped to [20, 400]. Default 40.
        max_bpm: Maximum BPM for clamping. Clamped to [20, 400], >= min_bpm. Default 240.
        min_samples: Minimum number of note timestamps needed to compute BPM.
            Clamped to [4, 256]. Default 8.
        max_history: Maximum number of note timestamps to keep in memory.
            Clamped to [16, 10000]. Default 256.
        smoothing: One-pole smoothing factor for BPM output.
            Clamped to [0.0, 0.99]. Default 0.5 (50% old, 50% new).
        subdivision_assumption: Which note value to assume the median interval is.
            One of "1/4", "1/8", "1/16". Default "1/8" (eighth note).
    """

    enabled: bool = False
    min_bpm: float = 40.0
    max_bpm: float = 240.0
    min_samples: int = 8
    max_history: int = 256
    smoothing: float = 0.5
    subdivision_assumption: str = "1/8"

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Clamp min_bpm and max_bpm to [20, 400]
        self.min_bpm = max(20.0, min(400.0, self.min_bpm))
        self.max_bpm = max(20.0, min(400.0, self.max_bpm))

        # Ensure max_bpm >= min_bpm
        if self.max_bpm < self.min_bpm:
            self.max_bpm = self.min_bpm

        # Clamp min_samples to [4, 256]
        self.min_samples = max(4, min(256, self.min_samples))

        # Clamp max_history to [16, 10000]
        self.max_history = max(16, min(10000, self.max_history))

        # Clamp smoothing to [0.0, 0.99]
        self.smoothing = max(0.0, min(0.99, self.smoothing))

        # Validate subdivision_assumption
        if self.subdivision_assumption not in ("1/4", "1/8", "1/16"):
            self.subdivision_assumption = "1/8"

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with all config fields.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "NoteBpmConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with config fields.

        Returns:
            NoteBpmConfig instance with validated values.
        """
        return NoteBpmConfig(
            enabled=data.get("enabled", False),
            min_bpm=data.get("min_bpm", 40.0),
            max_bpm=data.get("max_bpm", 240.0),
            min_samples=data.get("min_samples", 8),
            max_history=data.get("max_history", 256),
            smoothing=data.get("smoothing", 0.5),
            subdivision_assumption=data.get("subdivision_assumption", "1/8"),
        )


class NoteBpmEstimator:
    """Estimates BPM from a stream of note_on timestamps.

    Takes note timestamps (in seconds) from any note source and derives a BPM
    estimate by:
    1. Computing intervals between consecutive note onsets.
    2. Finding the median interval (most common rhythmic unit).
    3. Assuming that interval corresponds to a configured subdivision (1/4, 1/8, 1/16).
    4. Converting to BPM.
    5. Applying one-pole smoothing.

    Attributes:
        _config: NoteBpmConfig instance.
        _note_times: List of note onset times (seconds), capped at max_history.
        _smoothed_bpm: Current smoothed BPM estimate, or None if not yet computed.
    """

    def __init__(self, cfg: NoteBpmConfig) -> None:
        """Initialise estimator with config.

        Args:
            cfg: NoteBpmConfig instance.
        """
        self._config = cfg
        self._note_times: List[float] = []
        self._smoothed_bpm: Optional[float] = None

    def on_note(self, now_s: float) -> Optional[float]:
        """Record a note onset and return smoothed BPM estimate.

        Args:
            now_s: Timestamp of the note onset in seconds.

        Returns:
            Smoothed BPM estimate (clamped to [min_bpm, max_bpm]), or None if fewer
            than min_samples notes have been recorded.
        """
        # Append note time and truncate to max_history
        self._note_times.append(now_s)
        if len(self._note_times) > self._config.max_history:
            self._note_times = self._note_times[-self._config.max_history :]

        # Need at least min_samples notes
        if len(self._note_times) < self._config.min_samples:
            return None

        # Compute inter-note intervals (seconds)
        intervals = [
            self._note_times[i + 1] - self._note_times[i]
            for i in range(len(self._note_times) - 1)
        ]

        # Find median interval (most common rhythmic unit)
        median_interval = statistics.median(intervals)

        if median_interval <= 0:
            return None

        # Convert median interval to quarter-note interval based on subdivision
        if self._config.subdivision_assumption == "1/4":
            # Assume median is a quarter note
            quarter_interval = median_interval
        elif self._config.subdivision_assumption == "1/16":
            # Assume median is a sixteenth note (4 per quarter)
            quarter_interval = median_interval * 4
        else:
            # Default to 1/8 (assume median is an eighth note, 2 per quarter)
            quarter_interval = median_interval * 2

        # Convert quarter-note interval to BPM: quarter_note = 60 / BPM
        # So BPM = 60 / quarter_interval
        if quarter_interval <= 0:
            return None

        bpm = 60.0 / quarter_interval

        # Apply smoothing: smoothed = old * factor + new * (1 - factor)
        if self._smoothed_bpm is None:
            self._smoothed_bpm = bpm
        else:
            self._smoothed_bpm = (
                self._smoothed_bpm * self._config.smoothing
                + bpm * (1.0 - self._config.smoothing)
            )

        # Clamp to [min_bpm, max_bpm]
        self._smoothed_bpm = max(
            self._config.min_bpm,
            min(self._config.max_bpm, self._smoothed_bpm),
        )

        return self._smoothed_bpm

    def current_bpm(self) -> Optional[float]:
        """Return the current smoothed BPM estimate.

        Returns:
            Smoothed BPM estimate (clamped to [min_bpm, max_bpm]), or None if not yet computed.
        """
        return self._smoothed_bpm

    def clear(self) -> None:
        """Clear all state (note history and smoothed BPM)."""
        self._note_times = []
        self._smoothed_bpm = None

    def confidence(self) -> Optional[float]:
        """Return confidence of the BPM estimate based on interval consistency.

        Calculates 1 - (coefficient of variation), clamped to [0, 1].
        Higher = more consistent intervals.

        Returns:
            Confidence score (0.0 to 1.0), or None if fewer than min_samples notes.
        """
        if len(self._note_times) < self._config.min_samples:
            return None

        intervals = [
            self._note_times[i + 1] - self._note_times[i]
            for i in range(len(self._note_times) - 1)
        ]

        if not intervals:
            return None

        mean_interval = statistics.mean(intervals)
        if mean_interval <= 0:
            return None

        # Coefficient of variation
        if len(intervals) == 1:
            # Single interval → no variance
            cv = 0.0
        else:
            std_dev = statistics.stdev(intervals)
            cv = std_dev / mean_interval

        # Confidence = 1 - cv, clamped to [0, 1]
        confidence = max(0.0, min(1.0, 1.0 - cv))
        return confidence
