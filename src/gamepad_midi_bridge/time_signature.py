"""Time signature helpers for bar lengths, downbeats, and beat positions.

Pure stdlib module for handling time signatures (3/4, 4/4, 5/4, 6/8, 7/8, etc.)
and computing bar durations, beat positions, and downbeat detection.

Time signatures are represented as (numerator, denominator) where:
  - numerator: beats per bar (1–32, typically 2–7)
  - denominator: note value (1, 2, 4, 8, 16; default 4 for quarter notes)

All calculations are in milliseconds and integrate with bpm_sync.bpm_to_quarter_ms.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from gamepad_midi_bridge.bpm_sync import bpm_to_quarter_ms


@dataclass
class TimeSignature:
    """Represents a musical time signature (numerator/denominator).

    Attributes:
        numerator: Beats per bar (clamped 1–32).
        denominator: Note value for one beat (must be 1, 2, 4, 8, or 16; default 4).
    """

    numerator: int
    denominator: int = 4

    def __post_init__(self) -> None:
        """Validate and clamp time signature values."""
        # Clamp numerator to 1–32 range
        self.numerator = max(1, min(32, self.numerator))

        # Map unknown denominators to 4 (quarter note)
        valid_denominators = {1, 2, 4, 8, 16}
        if self.denominator not in valid_denominators:
            self.denominator = 4

    def __str__(self) -> str:
        """Return time signature as "numerator/denominator" string."""
        return f"{self.numerator}/{self.denominator}"

    def to_dict(self) -> Dict[str, int]:
        """Serialize time signature to a dictionary.

        Returns:
            Dictionary with keys: numerator, denominator.
        """
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
        }

    @staticmethod
    def from_dict(data: Dict[str, int]) -> "TimeSignature":
        """Deserialise time signature from a dictionary.

        Args:
            data: Dictionary with keys: numerator, denominator.

        Returns:
            TimeSignature instance with validated values.

        Examples:
            >>> sig = TimeSignature.from_dict({"numerator": 3, "denominator": 4})
            >>> str(sig)
            '3/4'
        """
        return TimeSignature(
            numerator=data.get("numerator", 4),
            denominator=data.get("denominator", 4),
        )


# Common time signatures used in music
COMMON_SIGNATURES: List[TimeSignature] = [
    TimeSignature(4, 4),    # common time
    TimeSignature(3, 4),    # waltz
    TimeSignature(6, 8),    # compound duple
    TimeSignature(5, 4),    # odd meter
    TimeSignature(7, 8),    # odd meter
    TimeSignature(12, 8),   # compound quadruple
    TimeSignature(2, 4),    # simple duple
]


def bar_duration_ms(sig: TimeSignature, bpm: float) -> float:
    """Calculate the duration of one bar in milliseconds.

    Args:
        sig: Time signature (e.g. TimeSignature(4, 4)).
        bpm: Tempo in beats per minute.

    Returns:
        Duration of one bar in milliseconds.

    Examples:
        >>> bar_duration_ms(TimeSignature(4, 4), 120)
        2000.0
        >>> bar_duration_ms(TimeSignature(3, 4), 120)
        1500.0
        >>> bar_duration_ms(TimeSignature(6, 8), 120)
        1500.0
    """
    quarter_ms = bpm_to_quarter_ms(bpm)
    # Duration of one beat at this denominator
    beat_ms = quarter_ms * (4.0 / sig.denominator)
    # Duration of entire bar
    return beat_ms * sig.numerator


def beat_in_bar(
    elapsed_ms: float, sig: TimeSignature, bpm: float
) -> Tuple[int, float]:
    """Find the beat position within a bar at a given elapsed time.

    Args:
        elapsed_ms: Time elapsed in milliseconds (from start or last downbeat).
        sig: Time signature.
        bpm: Tempo in beats per minute.

    Returns:
        Tuple of (beat_index, beat_fraction) where:
          - beat_index: 0-indexed beat within the bar (0 to numerator-1).
          - beat_fraction: position within the beat as 0.0–1.0.

    Examples:
        >>> beat_in_bar(0, TimeSignature(4, 4), 120)
        (0, 0.0)
        >>> beat_in_bar(500, TimeSignature(4, 4), 120)
        (1, 0.0)
        >>> beat_in_bar(750, TimeSignature(4, 4), 120)
        (1, 0.5)
    """
    bar_ms = bar_duration_ms(sig, bpm)
    beat_ms = bar_ms / sig.numerator

    # Position within the current bar (wraps after bar_ms)
    position_in_bar = elapsed_ms % bar_ms

    # Which beat are we on?
    beat_index = int(position_in_bar / beat_ms) % sig.numerator

    # How far through this beat?
    beat_fraction = (position_in_bar % beat_ms) / beat_ms

    return (beat_index, beat_fraction)


def is_downbeat(
    elapsed_ms: float, sig: TimeSignature, bpm: float, tolerance_ms: float = 10.0
) -> bool:
    """Check if the current position is at a downbeat (start of bar).

    Args:
        elapsed_ms: Time elapsed in milliseconds.
        sig: Time signature.
        bpm: Tempo in beats per minute.
        tolerance_ms: Tolerance window in milliseconds (default 10ms).

    Returns:
        True if within tolerance of a downbeat, False otherwise.

    Examples:
        >>> is_downbeat(0, TimeSignature(4, 4), 120)
        True
        >>> is_downbeat(500, TimeSignature(4, 4), 120)
        False
        >>> is_downbeat(2000, TimeSignature(4, 4), 120)
        True
    """
    bar_ms = bar_duration_ms(sig, bpm)
    position_in_bar = elapsed_ms % bar_ms
    return position_in_bar < tolerance_ms


def beats_in_seconds(seconds: float, sig: TimeSignature, bpm: float) -> int:
    """Calculate how many full beats fit in a duration.

    Args:
        seconds: Duration in seconds.
        sig: Time signature.
        bpm: Tempo in beats per minute.

    Returns:
        Number of complete beats in the duration.

    Examples:
        >>> beats_in_seconds(1.0, TimeSignature(4, 4), 120)
        2
        >>> beats_in_seconds(2.0, TimeSignature(4, 4), 120)
        4
    """
    bar_ms = bar_duration_ms(sig, bpm)
    beat_ms = bar_ms / sig.numerator
    ms = seconds * 1000.0
    return int(ms / beat_ms)


def bars_in_seconds(seconds: float, sig: TimeSignature, bpm: float) -> int:
    """Calculate how many full bars fit in a duration.

    Args:
        seconds: Duration in seconds.
        sig: Time signature.
        bpm: Tempo in beats per minute.

    Returns:
        Number of complete bars in the duration.

    Examples:
        >>> bars_in_seconds(2.0, TimeSignature(4, 4), 120)
        1
        >>> bars_in_seconds(4.0, TimeSignature(4, 4), 120)
        2
    """
    bar_ms = bar_duration_ms(sig, bpm)
    ms = seconds * 1000.0
    return int(ms / bar_ms)


def next_downbeat_ms(now_ms: float, sig: TimeSignature, bpm: float) -> float:
    """Calculate milliseconds until the next downbeat from the current time.

    Args:
        now_ms: Current time in milliseconds.
        sig: Time signature.
        bpm: Tempo in beats per minute.

    Returns:
        Milliseconds until the next downbeat (positive value).

    Examples:
        >>> next_downbeat_ms(0, TimeSignature(4, 4), 120)
        2000.0
        >>> next_downbeat_ms(500, TimeSignature(4, 4), 120)
        1500.0
        >>> next_downbeat_ms(1999, TimeSignature(4, 4), 120)
        1.0
    """
    bar_ms = bar_duration_ms(sig, bpm)
    position_in_bar = now_ms % bar_ms
    return bar_ms - position_in_bar
