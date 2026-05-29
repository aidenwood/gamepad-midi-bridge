"""MIDI Clock BPM estimator.

Derives tempo (BPM) from incoming MIDI Clock tick timestamps (24 ticks per quarter note).
Useful for syncing internal LFOs and sweeps to an external clock master.

Pure stdlib module — no Qt dependencies.
"""

from dataclasses import dataclass, asdict
from statistics import mean, stdev
from typing import Dict, List, Optional


@dataclass
class MidiClockEstimatorConfig:
    """Configuration for MIDI Clock BPM estimation.

    Attributes:
        enabled: Whether BPM estimation is active.
        window_size: Number of tick intervals to average for BPM calculation.
            Clamped to [24, 480]. Default 96 (4 quarter notes worth of ticks).
        smoothing: One-pole smoothing factor for BPM output.
            Clamped to [0.0, 0.99]. Default 0.3 (30% old, 70% new).
        min_bpm: Minimum BPM for clamping. Clamped to [10, 400]. Default 20.
        max_bpm: Maximum BPM for clamping. Clamped to [10, 400], >= min_bpm. Default 300.
    """

    enabled: bool = False
    window_size: int = 96
    smoothing: float = 0.3
    min_bpm: float = 20.0
    max_bpm: float = 300.0

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Clamp window_size to [24, 480]
        self.window_size = max(24, min(480, self.window_size))

        # Clamp smoothing to [0.0, 0.99]
        self.smoothing = max(0.0, min(0.99, self.smoothing))

        # Clamp min_bpm to [10, 400]
        self.min_bpm = max(10.0, min(400.0, self.min_bpm))

        # Clamp max_bpm to [10, 400], ensure >= min_bpm
        self.max_bpm = max(10.0, min(400.0, self.max_bpm))
        if self.max_bpm < self.min_bpm:
            self.max_bpm = self.min_bpm

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: enabled, window_size, smoothing, min_bpm, max_bpm.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "MidiClockEstimatorConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with keys: enabled, window_size, smoothing, min_bpm, max_bpm.

        Returns:
            MidiClockEstimatorConfig instance with validated values.
        """
        return MidiClockEstimatorConfig(
            enabled=data.get("enabled", False),
            window_size=data.get("window_size", 96),
            smoothing=data.get("smoothing", 0.3),
            min_bpm=data.get("min_bpm", 20.0),
            max_bpm=data.get("max_bpm", 300.0),
        )


class MidiClockEstimator:
    """Estimates BPM from incoming MIDI Clock ticks.

    MIDI Clock sends 24 ticks per quarter note. This estimator:
    - Buffers tick timestamps in a sliding window.
    - Computes inter-tick intervals and derives mean BPM.
    - Applies one-pole smoothing to stabilise the estimate.
    - Clamps to [min_bpm, max_bpm].
    - Provides lock detection (checks if external clock is steady).

    Attributes:
        _config: MidiClockEstimatorConfig instance.
        _tick_times: List of tick arrival times (seconds), truncated to window_size.
        _smoothed_bpm: Current smoothed BPM estimate, or None if not yet computed.
    """

    def __init__(self, cfg: MidiClockEstimatorConfig) -> None:
        """Initialise estimator with config.

        Args:
            cfg: MidiClockEstimatorConfig instance.
        """
        self._config = cfg
        self._tick_times: List[float] = []
        self._smoothed_bpm: Optional[float] = None

    def tick(self, now_s: float) -> Optional[float]:
        """Record a MIDI Clock tick and return smoothed BPM estimate.

        Args:
            now_s: Timestamp of the tick in seconds (e.g. from time.perf_counter()).

        Returns:
            Smoothed BPM estimate (clamped to [min_bpm, max_bpm]), or None if fewer
            than 2 ticks have been recorded.
        """
        # Append tick time and truncate to window_size
        self._tick_times.append(now_s)
        if len(self._tick_times) > self._config.window_size:
            self._tick_times = self._tick_times[-self._config.window_size :]

        # Need at least 2 ticks to compute an interval
        if len(self._tick_times) < 2:
            return None

        # Compute inter-tick intervals (seconds)
        intervals = [
            self._tick_times[i + 1] - self._tick_times[i]
            for i in range(len(self._tick_times) - 1)
        ]

        # Mean interval per tick
        mean_interval = mean(intervals)

        # Convert to BPM: 24 ticks per quarter, quarter = 60 / BPM seconds
        # BPM = 60 / (mean_interval * 24)
        if mean_interval <= 0:
            return None

        bpm = 60.0 / (mean_interval * 24.0)

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

    def reset(self) -> None:
        """Clear all state (tick history and smoothed BPM)."""
        self._tick_times = []
        self._smoothed_bpm = None

    def is_locked(self, jitter_threshold: float = 0.05) -> bool:
        """Check if external clock is steady (coefficient of variation below threshold).

        Args:
            jitter_threshold: Maximum allowed coefficient of variation (stdev / mean)
                for the external clock to be considered "locked". Default 0.05 (5%).

        Returns:
            True if clock is locked (steady), False if jittery or fewer than 5 samples.
        """
        # Need at least 5 intervals to assess variance
        if len(self._tick_times) < 6:
            return False

        intervals = [
            self._tick_times[i + 1] - self._tick_times[i]
            for i in range(len(self._tick_times) - 1)
        ]

        mean_interval = mean(intervals)
        if mean_interval == 0:
            return False

        # Coefficient of variation = stdev / mean
        std_dev = stdev(intervals)
        cv = std_dev / mean_interval

        return cv < jitter_threshold

    def intervals(self) -> List[float]:
        """Return the list of inter-tick intervals (in seconds).

        Returns:
            List of time differences between consecutive ticks. Empty if fewer than 2 ticks.
        """
        if len(self._tick_times) < 2:
            return []

        return [
            self._tick_times[i + 1] - self._tick_times[i]
            for i in range(len(self._tick_times) - 1)
        ]
