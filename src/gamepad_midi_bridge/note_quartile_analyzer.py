"""Analyze note distribution across frequency quartiles (sub-bass, bass, mids, highs)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


# Quartile boundaries: MIDI notes 0..127 split into 4 ranges
QUARTILE_NAMES = ["sub_bass", "bass", "mids", "highs"]
QUARTILE_RANGES = [(0, 31), (32, 63), (64, 95), (96, 127)]


@dataclass
class QuartileAnalysis:
    """Result of analyzing a session's note quartile distribution."""

    quartile_counts: list[int]  # 4-element list: [sub_bass, bass, mids, highs] note counts
    quartile_names: list[str]  # ["sub_bass", "bass", "mids", "highs"]
    total_notes: int  # Total samples currently retained
    dominant_quartile_index: Optional[int]  # Index 0..3 of highest count, or None if no samples
    dominant_quartile_name: Optional[str]  # Name of dominant quartile, or None if no samples
    quartile_percentages: list[float]  # 4-element list: [0..1] percentage per quartile

    def to_dict(self) -> dict:
        """Serialize analysis to dict."""
        return {
            "quartile_counts": self.quartile_counts,
            "quartile_names": self.quartile_names,
            "total_notes": self.total_notes,
            "dominant_quartile_index": self.dominant_quartile_index,
            "dominant_quartile_name": self.dominant_quartile_name,
            "quartile_percentages": self.quartile_percentages,
        }

    @classmethod
    def from_dict(cls, data: dict) -> QuartileAnalysis:
        """Deserialize analysis from dict."""
        return cls(
            quartile_counts=list(data.get("quartile_counts", [0, 0, 0, 0])),
            quartile_names=list(data.get("quartile_names", QUARTILE_NAMES)),
            total_notes=int(data.get("total_notes", 0)),
            dominant_quartile_index=data.get("dominant_quartile_index"),
            dominant_quartile_name=data.get("dominant_quartile_name"),
            quartile_percentages=list(data.get("quartile_percentages", [0.0, 0.0, 0.0, 0.0])),
        )


@dataclass
class QuartileConfig:
    """Configuration for note quartile analyzer."""

    max_samples: int = 50000

    def __post_init__(self) -> None:
        """Clamp max_samples to valid range."""
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> QuartileConfig:
        """Deserialize config from dict."""
        return cls(**data)


class NoteQuartileAnalyzer:
    """Track note plays per quartile (sub-bass, bass, mids, highs).

    Analyzes:
    - Quartile-based note distribution (4 frequency ranges)
    - Dominant quartile (most notes played)
    - Percentage breakdown per quartile
    - FIFO sampling with max_samples eviction
    """

    def __init__(self, cfg: QuartileConfig) -> None:
        """Initialize note quartile analyzer.

        Args:
            cfg: QuartileConfig instance.
        """
        self.config = cfg
        self._samples: list[int] = []  # FIFO list of recorded notes
        self._quartile_counts: list[int] = [0, 0, 0, 0]  # [sub_bass, bass, mids, highs]

    def quartile_for(self, note: int) -> int:
        """Determine which quartile a note belongs to.

        Args:
            note: MIDI note number (0..127), will be clamped.

        Returns:
            Quartile index 0..3.
        """
        # Clamp note to valid range
        note = max(0, min(127, note))

        # Determine quartile: 0..31=0, 32..63=1, 64..95=2, 96..127=3
        return note // 32

    def record(self, note: int) -> None:
        """Record a note play.

        Clamps note to 0..127. Determines quartile and increments count.
        Maintains FIFO with max_samples eviction (and decrements quartile on evict).

        Args:
            note: MIDI note number (0..127), will be clamped.
        """
        # Clamp note to valid range
        note = max(0, min(127, note))

        # Determine quartile
        q = self.quartile_for(note)

        # Enforce max_samples limit before adding (evict oldest from front if at capacity)
        if len(self._samples) >= self.config.max_samples:
            evicted_note = self._samples.pop(0)
            evicted_q = self.quartile_for(evicted_note)
            self._quartile_counts[evicted_q] -= 1

        # Increment quartile count
        self._quartile_counts[q] += 1

        # Append to FIFO
        self._samples.append(note)

    def analyze(self) -> QuartileAnalysis:
        """Analyze current quartile distribution.

        Returns:
            QuartileAnalysis with counts, percentages, and dominant quartile.
        """
        total = len(self._samples)

        # Determine dominant quartile
        dominant_index = None
        dominant_name = None
        max_count = 0
        for i, count in enumerate(self._quartile_counts):
            if count > max_count:
                max_count = count
                dominant_index = i
                dominant_name = QUARTILE_NAMES[i]

        # Calculate percentages
        if total > 0:
            percentages = [count / total for count in self._quartile_counts]
        else:
            percentages = [0.0, 0.0, 0.0, 0.0]

        return QuartileAnalysis(
            quartile_counts=list(self._quartile_counts),
            quartile_names=list(QUARTILE_NAMES),
            total_notes=total,
            dominant_quartile_index=dominant_index,
            dominant_quartile_name=dominant_name,
            quartile_percentages=percentages,
        )

    def clear(self) -> None:
        """Clear all samples and quartile counts."""
        self._samples = []
        self._quartile_counts = [0, 0, 0, 0]

    def total(self) -> int:
        """Get total number of note plays (size of FIFO window).

        Returns:
            Count of notes in the current sample window.
        """
        return len(self._samples)
