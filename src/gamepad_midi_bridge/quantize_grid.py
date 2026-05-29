"""Quantize-to-grid scheduler for aligning note events to a beat grid.

Pure stdlib module for snapping arbitrary note-on timestamps to a beat grid
defined by BPM, subdivision, and reference start time. Supports quantization
modes (nearest, next, previous), swing, and humanization.
"""

import math
import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from . import bpm_sync


@dataclass
class QuantizeGridConfig:
    """Configuration for quantize-to-grid scheduling.

    Attributes:
        enabled: Whether quantization is active.
        bpm: Tempo in beats per minute (clamped 20–300).
        subdivision: Subdivision to snap to (validated; unknown → "1/16").
        mode: Quantization mode: "nearest", "next", or "previous" (unknown → "nearest").
        swing_percent: Swing intensity (clamped 50–75; 50 = straight, 75 = max swing).
    """

    enabled: bool = False
    bpm: float = 120.0
    subdivision: str = "1/16"
    mode: str = "nearest"
    swing_percent: float = 50.0

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Clamp BPM to 20–300 range
        self.bpm = max(20.0, min(300.0, self.bpm))

        # Validate subdivision; default to "1/16" if unknown
        if self.subdivision not in bpm_sync.SUBDIVISIONS:
            self.subdivision = "1/16"

        # Validate mode; default to "nearest" if unknown
        if self.mode not in ("nearest", "next", "previous"):
            self.mode = "nearest"

        # Clamp swing_percent to 50–75
        self.swing_percent = max(50.0, min(75.0, self.swing_percent))

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: enabled, bpm, subdivision, mode, swing_percent.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "QuantizeGridConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with keys: enabled, bpm, subdivision, mode, swing_percent.

        Returns:
            QuantizeGridConfig instance with validated values.

        Examples:
            >>> config = QuantizeGridConfig.from_dict({
            ...     "enabled": True,
            ...     "bpm": 140,
            ...     "subdivision": "1/8",
            ...     "mode": "next",
            ...     "swing_percent": 65.0
            ... })
            >>> config.bpm
            140.0
        """
        return QuantizeGridConfig(
            enabled=data.get("enabled", False),
            bpm=data.get("bpm", 120.0),
            subdivision=data.get("subdivision", "1/16"),
            mode=data.get("mode", "nearest"),
            swing_percent=data.get("swing_percent", 50.0),
        )


def next_grid_time(
    now_s: float, ref_start_s: float, cfg: QuantizeGridConfig
) -> float:
    """Return the next grid-aligned timestamp for a note event.

    Given a current time (now_s), a reference start time (ref_start_s), and a
    quantization config, calculate the grid-aligned timestamp using the specified
    mode (nearest, next, or previous).

    Args:
        now_s: Current time in seconds.
        ref_start_s: Reference start time in seconds (origin of the grid).
        cfg: QuantizeGridConfig with bpm, subdivision, and mode.

    Returns:
        Next grid-aligned time in seconds.

    Examples:
        >>> cfg = QuantizeGridConfig(bpm=120, subdivision="1/4")
        >>> next_grid_time(0.3, 0.0, cfg)  # quarter note = 0.5s at 120 BPM
        0.5
        >>> cfg_prev = QuantizeGridConfig(bpm=120, subdivision="1/4", mode="previous")
        >>> next_grid_time(0.3, 0.0, cfg_prev)
        0.0
    """
    # Grid step in seconds
    grid_step_s = bpm_sync.subdivision_ms(cfg.bpm, cfg.subdivision) / 1000.0

    # Elapsed time from reference start
    elapsed = now_s - ref_start_s

    # Current grid index (fractional)
    grid_index = elapsed / grid_step_s

    # Snap based on mode
    if cfg.mode == "next":
        snapped_index = math.ceil(grid_index)
    elif cfg.mode == "previous":
        snapped_index = math.floor(grid_index)
    else:  # "nearest"
        snapped_index = round(grid_index)

    # Convert back to time
    candidate_s = ref_start_s + snapped_index * grid_step_s
    return candidate_s


def apply_swing(
    grid_time_s: float, ref_start_s: float, cfg: QuantizeGridConfig
) -> float:
    """Apply swing to a grid-aligned time.

    Swing shifts every odd grid index forward by a fraction of the grid step.
    The shift amount is proportional to (swing_percent - 50) / 50, clamped to
    (0, 1) where 50% = no shift and 75% = maximum shift.

    Args:
        grid_time_s: A grid-aligned time in seconds.
        ref_start_s: Reference start time (same as in next_grid_time).
        cfg: QuantizeGridConfig with bpm, subdivision, and swing_percent.

    Returns:
        Swing-adjusted time in seconds.

    Examples:
        >>> cfg = QuantizeGridConfig(bpm=120, subdivision="1/8", swing_percent=50.0)
        >>> t = 0.5  # grid time
        >>> apply_swing(t, 0.0, cfg)  # no swing at 50%
        0.5
        >>> cfg_swing = QuantizeGridConfig(bpm=120, subdivision="1/8", swing_percent=75.0)
        >>> apply_swing(0.25, 0.0, cfg_swing)  # index 1 is odd; will shift forward
        0.27500...
    """
    if cfg.swing_percent <= 50.0:
        # No swing
        return grid_time_s

    # Grid step in seconds
    grid_step_s = bpm_sync.subdivision_ms(cfg.bpm, cfg.subdivision) / 1000.0

    # Grid index of this time
    elapsed = grid_time_s - ref_start_s
    grid_index = int(round(elapsed / grid_step_s))

    # Only shift odd indices
    if grid_index % 2 == 0:
        return grid_time_s

    # Calculate shift amount: (swing_percent - 50) / 50 * grid_step_s
    # At 75%, shift_fraction = 0.5 (shift by 50% of grid step)
    shift_fraction = (cfg.swing_percent - 50.0) / 50.0
    shift_s = shift_fraction * grid_step_s
    return grid_time_s + shift_s


def humanize_offset_ms(jitter_ms: int = 10, seed: Optional[int] = None) -> float:
    """Generate a random humanization offset for natural feel.

    Returns a uniformly-distributed random value in the range
    (-jitter_ms / 2, +jitter_ms / 2) milliseconds.

    Args:
        jitter_ms: Maximum total jitter range in milliseconds (default: 10).
        seed: Optional random seed for determinism (for testing).

    Returns:
        Offset in milliseconds.

    Examples:
        >>> import random
        >>> random.seed(42)
        >>> offset = humanize_offset_ms(10, seed=42)
        >>> -5 <= offset <= 5
        True
    """
    if seed is not None:
        random.seed(seed)

    half_jitter = jitter_ms / 2.0
    return random.uniform(-half_jitter, half_jitter)


class QuantizeScheduler:
    """Scheduler for quantizing note events to a beat grid.

    Attributes:
        cfg: QuantizeGridConfig instance.
        ref_start_s: Reference start time for the grid (origin).
    """

    def __init__(self, cfg: QuantizeGridConfig, ref_start_s: float = 0.0) -> None:
        """Initialize the scheduler.

        Args:
            cfg: QuantizeGridConfig with bpm, subdivision, mode, and swing settings.
            ref_start_s: Reference start time in seconds (default: 0.0).
        """
        self.cfg = cfg
        self.ref_start_s = ref_start_s

    def quantize(self, now_s: float) -> float:
        """Quantize an event time to the grid and apply swing.

        Args:
            now_s: Current time in seconds.

        Returns:
            Grid-aligned and swing-adjusted time in seconds.

        Examples:
            >>> cfg = QuantizeGridConfig(enabled=True, bpm=120, subdivision="1/4")
            >>> scheduler = QuantizeScheduler(cfg, ref_start_s=0.0)
            >>> scheduler.quantize(0.3)
            0.5
        """
        grid_time = next_grid_time(now_s, self.ref_start_s, self.cfg)
        swing_time = apply_swing(grid_time, self.ref_start_s, self.cfg)
        return swing_time

    def next_n_grid_times(self, now_s: float, n: int) -> List[float]:
        """Return the next n grid times after now_s.

        Args:
            now_s: Current time in seconds.
            n: Number of grid times to return.

        Returns:
            List of n monotonically-increasing grid-aligned times.

        Examples:
            >>> cfg = QuantizeGridConfig(bpm=120, subdivision="1/4")
            >>> scheduler = QuantizeScheduler(cfg, ref_start_s=0.0)
            >>> times = scheduler.next_n_grid_times(0.0, 3)
            >>> len(times)
            3
            >>> times[1] - times[0]
            0.5
        """
        grid_step_s = bpm_sync.subdivision_ms(self.cfg.bpm, self.cfg.subdivision) / 1000.0

        # Start from the next grid time after now_s
        first_grid = next_grid_time(now_s, self.ref_start_s, self.cfg)
        if first_grid <= now_s and self.cfg.mode != "previous":
            # If we got a past time (shouldn't happen in "next"/"nearest" mode),
            # bump to the next grid
            first_grid += grid_step_s

        result = []
        for i in range(n):
            candidate = first_grid + i * grid_step_s
            result.append(candidate)

        return result
