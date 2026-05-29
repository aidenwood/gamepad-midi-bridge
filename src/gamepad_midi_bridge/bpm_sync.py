"""BPM and beat-grid synchronisation helpers.

Pure stdlib module for converting between BPM and milliseconds, snapping durations
to standard musical subdivisions, and managing BPM sync configuration.

Subdivisions are expressed as quarter-note multipliers:
  - "1/1" = 4.0 (whole note)
  - "1/2" = 2.0 (half note)
  - "1/4" = 1.0 (quarter note)
  - "1/8" = 0.5 (eighth note)
  - "1/16" = 0.25 (sixteenth note)
  - "1/32" = 0.125 (thirty-second note)
  - Dotted variants: "1/2d", "1/4d", "1/8d", "1/16d" (add 50% to base)
  - Triplet variants: "1/4t", "1/8t", "1/16t" (divide by 3 instead of 2)
"""

from dataclasses import dataclass, asdict
from typing import Dict


# Mapping subdivision names to quarter-note multipliers
SUBDIVISIONS: Dict[str, float] = {
    # Standard subdivisions
    "1/1": 4.0,        # whole note
    "1/2": 2.0,        # half note
    "1/4": 1.0,        # quarter note
    "1/8": 0.5,        # eighth note
    "1/16": 0.25,      # sixteenth note
    "1/32": 0.125,     # thirty-second note
    # Dotted variants (add 50%)
    "1/2d": 3.0,       # dotted half
    "1/4d": 1.5,       # dotted quarter
    "1/8d": 0.75,      # dotted eighth
    "1/16d": 0.375,    # dotted sixteenth
    # Triplet variants (divide by 3 instead of 2)
    "1/4t": 2.0 / 3.0,   # quarter triplet
    "1/8t": 1.0 / 3.0,   # eighth triplet
    "1/16t": 1.0 / 6.0,  # sixteenth triplet
}


def bpm_to_quarter_ms(bpm: float) -> float:
    """Convert BPM to milliseconds per quarter note.

    Args:
        bpm: Tempo in beats per minute (must be > 0).

    Returns:
        Duration of one quarter note in milliseconds.

    Raises:
        ValueError: If bpm <= 0.

    Examples:
        >>> bpm_to_quarter_ms(120)
        500.0
        >>> bpm_to_quarter_ms(60)
        1000.0
    """
    if bpm <= 0:
        raise ValueError(f"BPM must be positive, got {bpm}")
    return 60000 / bpm


def subdivision_ms(bpm: float, subdivision: str) -> float:
    """Get duration in milliseconds for a specific subdivision at a given BPM.

    Args:
        bpm: Tempo in beats per minute.
        subdivision: Subdivision name (e.g. "1/16", "1/8d", "1/4t").

    Returns:
        Duration in milliseconds.

    Raises:
        ValueError: If bpm <= 0.
        KeyError: If subdivision is unknown.

    Examples:
        >>> subdivision_ms(120, "1/4")
        500.0
        >>> subdivision_ms(120, "1/16")
        125.0
        >>> subdivision_ms(120, "1/8d")
        375.0
    """
    if subdivision not in SUBDIVISIONS:
        raise KeyError(f"Unknown subdivision: {subdivision}. Valid options: {list(SUBDIVISIONS.keys())}")
    quarter_ms = bpm_to_quarter_ms(bpm)
    multiplier = SUBDIVISIONS[subdivision]
    return quarter_ms * multiplier


def snap_ms_to_grid(ms: float, bpm: float, subdivision: str = "1/16") -> float:
    """Round a duration to the nearest subdivision of a beat grid.

    Args:
        ms: Duration in milliseconds to snap.
        bpm: Tempo in beats per minute.
        subdivision: Subdivision to snap to (default: "1/16").

    Returns:
        Snapped duration in milliseconds.

    Raises:
        ValueError: If bpm <= 0.
        KeyError: If subdivision is unknown.

    Examples:
        >>> snap_ms_to_grid(130, 120, "1/16")
        125.0
        >>> snap_ms_to_grid(180, 120, "1/16")
        125.0
    """
    sub_ms = subdivision_ms(bpm, subdivision)
    snapped = round(ms / sub_ms) * sub_ms
    return snapped


def ms_to_nearest_subdivision(ms: float, bpm: float) -> str:
    """Find the subdivision name whose duration is closest to the given milliseconds.

    Args:
        ms: Duration in milliseconds.
        bpm: Tempo in beats per minute.

    Returns:
        Subdivision name (e.g. "1/16", "1/8d").

    Raises:
        ValueError: If bpm <= 0.

    Examples:
        >>> ms_to_nearest_subdivision(125, 120)
        '1/16'
        >>> ms_to_nearest_subdivision(500, 120)
        '1/4'
    """
    best_sub = None
    best_distance = float("inf")

    for sub_name in SUBDIVISIONS:
        sub_ms = subdivision_ms(bpm, sub_name)
        distance = abs(sub_ms - ms)
        if distance < best_distance:
            best_distance = distance
            best_sub = sub_name

    return best_sub


def subdivisions_per_bar(subdivision: str, beats_per_bar: int = 4) -> float:
    """Calculate how many subdivisions fit in one bar.

    Args:
        subdivision: Subdivision name (e.g. "1/16").
        beats_per_bar: Number of beats per bar (default: 4 for 4/4 time).

    Returns:
        Number of subdivisions in one bar.

    Raises:
        KeyError: If subdivision is unknown.

    Examples:
        >>> subdivisions_per_bar("1/16")
        16.0
        >>> subdivisions_per_bar("1/8d")
        5.333...
    """
    if subdivision not in SUBDIVISIONS:
        raise KeyError(f"Unknown subdivision: {subdivision}. Valid options: {list(SUBDIVISIONS.keys())}")

    # One bar = beats_per_bar quarter notes
    # Each subdivision = SUBDIVISIONS[subdivision] quarter notes
    # subdivisions per bar = beats_per_bar / (subdivision as fraction of quarter)
    multiplier = SUBDIVISIONS[subdivision]
    return beats_per_bar / multiplier


@dataclass
class BpmSyncConfig:
    """Configuration for BPM-based synchronisation.

    Attributes:
        enabled: Whether BPM sync is active.
        bpm: Tempo in beats per minute (clamped 20–300).
        subdivision: Subdivision to sync to (validated; unknown → "1/16").
    """

    enabled: bool = False
    bpm: float = 120.0
    subdivision: str = "1/16"

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Clamp BPM to 20–300 range
        self.bpm = max(20.0, min(300.0, self.bpm))

        # Validate subdivision; default to "1/16" if unknown
        if self.subdivision not in SUBDIVISIONS:
            self.subdivision = "1/16"

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: enabled, bpm, subdivision.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "BpmSyncConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with keys: enabled, bpm, subdivision.

        Returns:
            BpmSyncConfig instance with validated values.

        Examples:
            >>> config = BpmSyncConfig.from_dict({"enabled": True, "bpm": 140, "subdivision": "1/8"})
            >>> config.bpm
            140.0
        """
        return BpmSyncConfig(
            enabled=data.get("enabled", False),
            bpm=data.get("bpm", 120.0),
            subdivision=data.get("subdivision", "1/16"),
        )
