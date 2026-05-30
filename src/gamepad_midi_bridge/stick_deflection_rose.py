"""Stick deflection rose chart: buckets stick (x, y) samples by direction into angular bins.

Pure stdlib module for analyzing stick movement patterns. Buckets stick samples into
8 or 16 directional bins. Used for UI rose-chart visualization showing which directions
the user pushes most.

A "rose" is a radial histogram where each angular bin represents one direction and the
bar height/area represents how many samples fell into that bin. Starts at North (top)
and goes clockwise: N, NE, E, SE, S, SW, W, NW.

This module buckets raw stick samples and provides analysis tools (dominant direction,
percentages, etc.) for rose-chart rendering.
"""

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


BIN_NAMES_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
BIN_NAMES_16 = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


@dataclass
class DeflectionRose:
    """Result of analyzing stick deflection samples into directional bins.

    Attributes:
        bin_counts: List of sample counts per bin (8 or 16 entries).
        bin_names: List of bin names (e.g., ["N", "NE", ...]).
        total_samples: Total number of samples recorded.
        dominant_bin_index: Index of bin with most samples; None if empty.
        dominant_bin_name: Name of dominant bin; None if empty.
        bin_percentages: List of percentages per bin (0.0 to 100.0).
    """

    bin_counts: List[int] = field(default_factory=list)
    bin_names: List[str] = field(default_factory=list)
    total_samples: int = 0
    dominant_bin_index: Optional[int] = None
    dominant_bin_name: Optional[str] = None
    bin_percentages: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Serialize to dict for storage.

        Returns:
            Dictionary with all fields serialized.
        """
        return {
            "bin_counts": self.bin_counts,
            "bin_names": self.bin_names,
            "total_samples": self.total_samples,
            "dominant_bin_index": self.dominant_bin_index,
            "dominant_bin_name": self.dominant_bin_name,
            "bin_percentages": self.bin_percentages,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DeflectionRose":
        """Deserialize from dict.

        Args:
            data: Dictionary with keys matching DeflectionRose fields.

        Returns:
            DeflectionRose instance.
        """
        return cls(
            bin_counts=data.get("bin_counts", []),
            bin_names=data.get("bin_names", []),
            total_samples=data.get("total_samples", 0),
            dominant_bin_index=data.get("dominant_bin_index"),
            dominant_bin_name=data.get("dominant_bin_name"),
            bin_percentages=data.get("bin_percentages", []),
        )


@dataclass
class DeflectionRoseConfig:
    """Configuration for stick deflection rose analysis.

    Attributes:
        bin_count: Number of angular bins (8 or 16; defaults to 8).
        min_magnitude: Ignore samples below this magnitude (0.0 to 1.0; defaults to 0.1).
                       Used to skip center deadzone.
        max_samples: Maximum number of samples to retain in a FIFO buffer
                     (100 to 1000000; defaults to 50000).
    """

    bin_count: int = 8
    min_magnitude: float = 0.1
    max_samples: int = 50000

    def __post_init__(self) -> None:
        """Clamp numeric bounds."""
        # Only allow 8 or 16 bins; default to 8 if invalid
        if self.bin_count not in (8, 16):
            self.bin_count = 8
        # Clamp magnitude to [0.0, 1.0]
        self.min_magnitude = max(0.0, min(self.min_magnitude, 1.0))
        # Clamp max_samples to [100, 1000000]
        self.max_samples = max(100, min(self.max_samples, 1000000))

    def to_dict(self) -> Dict:
        """Serialize to dict for storage.

        Returns:
            Dictionary with keys: bin_count, min_magnitude, max_samples.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "DeflectionRoseConfig":
        """Deserialize from dict.

        Args:
            data: Dictionary with keys matching DeflectionRoseConfig fields.

        Returns:
            DeflectionRoseConfig instance with validated values.
        """
        return cls(
            bin_count=data.get("bin_count", 8),
            min_magnitude=data.get("min_magnitude", 0.1),
            max_samples=data.get("max_samples", 50000),
        )


class StickDeflectionRose:
    """Analyzer for stick movement patterns; buckets samples into directional bins.

    Records stick (x, y) samples, buckets them by angle starting at North (top) and
    going clockwise into 8 or 16 bins. Provides analysis (dominant direction,
    percentages, etc.) for rose-chart visualization.

    Angle convention: North (0, 1) = 0°, East (1, 0) = 90°, South (0, -1) = 180°,
    West (-1, 0) = 270°. Bins start at N and go clockwise.

    Attributes:
        cfg: DeflectionRoseConfig instance.
        _bin_counts: List of sample counts per bin.
        _samples: FIFO list of bin indices recorded (for max_samples eviction).
    """

    def __init__(self, cfg: DeflectionRoseConfig) -> None:
        """Initialize deflection rose analyzer.

        Args:
            cfg: DeflectionRoseConfig instance.
        """
        self.cfg = cfg
        self._bin_counts: List[int] = [0] * cfg.bin_count
        self._samples: List[int] = []  # FIFO of bin indices for max_samples tracking

    def record(self, x: float, y: float) -> None:
        """Record a stick sample; bucket by direction.

        Clamps x, y to [-1, 1]. Computes magnitude = sqrt(x^2 + y^2). If below
        min_magnitude, skips sample. Otherwise, computes angle via atan2(y, x)
        and determines bin index. Starts at North and goes clockwise.
        Increments bin count. If total samples exceed max_samples, evicts oldest
        sample (FIFO).

        Args:
            x: Horizontal position (clamped to [-1, 1]).
            y: Vertical position (clamped to [-1, 1]).
        """
        # Clamp x, y to [-1, 1]
        x = max(-1.0, min(x, 1.0))
        y = max(-1.0, min(y, 1.0))

        # Compute magnitude
        magnitude = math.sqrt(x * x + y * y)

        # Skip if below min_magnitude (center deadzone)
        if magnitude < self.cfg.min_magnitude:
            return

        # Compute angle in radians; atan2(y, x) returns [-pi, pi]
        # North is pi/2 (90°). Rotate so North is at 0, then go clockwise.
        angle = math.atan2(y, x)
        # Adjust so North (pi/2) maps to 0, and we go clockwise (decreasing angle)
        adjusted = -(angle - math.pi / 2) / (2 * math.pi)
        if adjusted < 0:
            adjusted += 1.0
        # Map [0, 1) to [0, bin_count)
        bin_index = int(adjusted * self.cfg.bin_count) % self.cfg.bin_count

        # Increment bin count
        self._bin_counts[bin_index] += 1
        self._samples.append(bin_index)

        # If we exceed max_samples, evict the oldest sample (FIFO)
        if len(self._samples) > self.cfg.max_samples:
            oldest_bin = self._samples.pop(0)
            self._bin_counts[oldest_bin] -= 1

    def bin_for(self, x: float, y: float) -> Optional[int]:
        """Compute bin index for a stick position without recording.

        Returns the bin index for the given (x, y), or None if below min_magnitude.

        Args:
            x: Horizontal position (clamped to [-1, 1]).
            y: Vertical position (clamped to [-1, 1]).

        Returns:
            Bin index (0 to bin_count-1) or None if below min_magnitude.
        """
        # Clamp x, y to [-1, 1]
        x = max(-1.0, min(x, 1.0))
        y = max(-1.0, min(y, 1.0))

        # Compute magnitude
        magnitude = math.sqrt(x * x + y * y)

        # Return None if below min_magnitude
        if magnitude < self.cfg.min_magnitude:
            return None

        # Compute angle and bin index (same as record)
        angle = math.atan2(y, x)
        adjusted = -(angle - math.pi / 2) / (2 * math.pi)
        if adjusted < 0:
            adjusted += 1.0
        bin_index = int(adjusted * self.cfg.bin_count) % self.cfg.bin_count

        return bin_index

    def analyze(self) -> DeflectionRose:
        """Analyze current samples and return DeflectionRose result.

        Computes bin percentages, dominant bin, and returns a DeflectionRose
        with all fields populated.

        Returns:
            DeflectionRose instance with current analysis.
        """
        # Determine bin names
        if self.cfg.bin_count == 16:
            bin_names = BIN_NAMES_16
        else:
            bin_names = BIN_NAMES_8

        # Compute total samples
        total_samples = sum(self._bin_counts)

        # Compute percentages
        if total_samples > 0:
            bin_percentages = [
                (count / total_samples) * 100.0 for count in self._bin_counts
            ]
        else:
            bin_percentages = [0.0] * self.cfg.bin_count

        # Find dominant bin
        dominant_bin_index = None
        dominant_bin_name = None
        if total_samples > 0:
            dominant_bin_index = self._bin_counts.index(max(self._bin_counts))
            dominant_bin_name = bin_names[dominant_bin_index]

        return DeflectionRose(
            bin_counts=list(self._bin_counts),
            bin_names=bin_names,
            total_samples=total_samples,
            dominant_bin_index=dominant_bin_index,
            dominant_bin_name=dominant_bin_name,
            bin_percentages=bin_percentages,
        )

    def clear(self) -> None:
        """Clear all samples and bin counts.

        Resets the deflection rose to initial state; useful between sessions.
        """
        self._bin_counts = [0] * self.cfg.bin_count
        self._samples = []

    def total(self) -> int:
        """Return total number of samples recorded.

        Returns:
            Total count of non-evicted samples in the FIFO buffer.
        """
        return len(self._samples)
