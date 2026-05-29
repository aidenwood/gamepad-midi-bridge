"""BPM-sync helper for LFO rates.

Converts musical subdivision names into LFO rate_hz values so that one full
LFO cycle equals one subdivision. For example, at 120 BPM, a "1/4" (quarter note)
subdivision becomes rate_hz=2.0 (one cycle per 0.5 seconds).

Pure stdlib module with no Qt dependencies.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any

from gamepad_midi_bridge.bpm_sync import SUBDIVISIONS, subdivision_ms


def subdivision_to_rate_hz(subdivision: str, bpm: float) -> float:
    """Convert a subdivision name to an LFO rate in Hz.

    One full LFO cycle will equal one subdivision duration at the given BPM.

    Args:
        subdivision: Subdivision name (e.g. "1/4", "1/16", "1/8d").
        bpm: Tempo in beats per minute (must be > 0).

    Returns:
        LFO rate in Hz (cycles per second).

    Raises:
        KeyError: If subdivision is unknown.
        ValueError: If bpm <= 0.

    Examples:
        >>> subdivision_to_rate_hz("1/4", 120)
        2.0
        >>> subdivision_to_rate_hz("1/8", 120)
        4.0
        >>> subdivision_to_rate_hz("1/16", 120)
        8.0
        >>> subdivision_to_rate_hz("1/4", 60)
        1.0
    """
    if subdivision not in SUBDIVISIONS:
        raise KeyError(
            f"Unknown subdivision: {subdivision}. "
            f"Valid options: {list(SUBDIVISIONS.keys())}"
        )
    if bpm <= 0:
        raise ValueError(f"BPM must be positive, got {bpm}")

    # Get duration in milliseconds for this subdivision at this BPM
    sub_ms = subdivision_ms(bpm, subdivision)

    # LFO rate_hz = 1000 ms/s / duration_ms
    # This gives cycles per second where one cycle = one subdivision
    rate_hz = 1000.0 / sub_ms
    return rate_hz


def rate_hz_to_nearest_subdivision(rate_hz: float, bpm: float) -> str:
    """Find the subdivision name whose rate_hz is closest to the given rate.

    Args:
        rate_hz: LFO rate in Hz.
        bpm: Tempo in beats per minute.

    Returns:
        Subdivision name (e.g. "1/16", "1/8d").

    Raises:
        ValueError: If bpm <= 0.

    Examples:
        >>> rate_hz_to_nearest_subdivision(8.0, 120)
        '1/16'
        >>> rate_hz_to_nearest_subdivision(2.0, 120)
        '1/4'
        >>> rate_hz_to_nearest_subdivision(4.0, 120)
        '1/8'
    """
    if bpm <= 0:
        raise ValueError(f"BPM must be positive, got {bpm}")

    best_sub = None
    best_distance = float("inf")

    for sub_name in SUBDIVISIONS:
        sub_rate_hz = subdivision_to_rate_hz(sub_name, bpm)
        distance = abs(sub_rate_hz - rate_hz)
        if distance < best_distance:
            best_distance = distance
            best_sub = sub_name

    return best_sub


def cycles_per_bar(subdivision: str, beats_per_bar: int = 4) -> float:
    """Calculate how many LFO cycles fit in one bar at this subdivision.

    Args:
        subdivision: Subdivision name (e.g. "1/16").
        beats_per_bar: Number of beats per bar (default: 4 for 4/4 time).

    Returns:
        Number of complete LFO cycles in one bar.

    Raises:
        KeyError: If subdivision is unknown.

    Examples:
        >>> cycles_per_bar("1/4", 4)
        4.0
        >>> cycles_per_bar("1/8", 4)
        8.0
        >>> cycles_per_bar("1/16", 4)
        16.0
        >>> cycles_per_bar("1/2", 4)
        2.0
    """
    if subdivision not in SUBDIVISIONS:
        raise KeyError(
            f"Unknown subdivision: {subdivision}. "
            f"Valid options: {list(SUBDIVISIONS.keys())}"
        )

    # One bar = beats_per_bar quarter notes
    # Each LFO cycle = one subdivision duration
    # So cycles per bar = beats_per_bar / (subdivision as fraction of quarter)
    multiplier = SUBDIVISIONS[subdivision]
    return beats_per_bar / multiplier


@dataclass
class LfoBpmSyncConfig:
    """Configuration for BPM-synced LFO rates.

    When enabled, the LFO rate_hz is computed from the BPM and subdivision
    so that one full LFO cycle equals the subdivision duration.

    Attributes:
        enabled: Whether BPM sync is active.
        bpm: Tempo in beats per minute (clamped 20..300).
        subdivision: Subdivision name (validated; unknown → "1/4").
        auto_update_rate: If True, rate_hz is recomputed when bpm/subdivision change.
    """

    enabled: bool = False
    bpm: float = 120.0
    subdivision: str = "1/4"
    auto_update_rate: bool = True

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Clamp BPM to 20–300 range
        self.bpm = max(20.0, min(300.0, self.bpm))

        # Validate subdivision; default to "1/4" if unknown
        if self.subdivision not in SUBDIVISIONS:
            self.subdivision = "1/4"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: enabled, bpm, subdivision, auto_update_rate.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "LfoBpmSyncConfig":
        """Deserialize config from a dictionary.

        Args:
            data: Dictionary with keys: enabled, bpm, subdivision, auto_update_rate.

        Returns:
            LfoBpmSyncConfig instance with validated values.

        Examples:
            >>> cfg = LfoBpmSyncConfig.from_dict(
            ...     {"enabled": True, "bpm": 140, "subdivision": "1/8"}
            ... )
            >>> cfg.bpm
            140.0
            >>> cfg.subdivision
            '1/8'
        """
        return LfoBpmSyncConfig(
            enabled=data.get("enabled", False),
            bpm=data.get("bpm", 120.0),
            subdivision=data.get("subdivision", "1/4"),
            auto_update_rate=data.get("auto_update_rate", True),
        )


def apply_to_lfo_config(lfo_cfg_dict: dict, sync_cfg: LfoBpmSyncConfig) -> dict:
    """Apply BPM sync to an LFO config dictionary.

    If sync_cfg.enabled and auto_update_rate are both True, returns a NEW dict
    with rate_hz overwritten to the value from subdivision_to_rate_hz(). Otherwise,
    returns the dict unchanged. Input dict is never mutated.

    Args:
        lfo_cfg_dict: Dictionary with LFO config (must have 'rate_hz' key).
        sync_cfg: LfoBpmSyncConfig instance.

    Returns:
        New dictionary (input is not mutated).

    Examples:
        >>> lfo = {"enabled": True, "shape": "sine", "rate_hz": 1.0}
        >>> sync = LfoBpmSyncConfig(enabled=True, bpm=120, subdivision="1/4")
        >>> result = apply_to_lfo_config(lfo, sync)
        >>> result["rate_hz"]
        2.0
        >>> lfo["rate_hz"]  # original unchanged
        1.0
        >>> sync_disabled = LfoBpmSyncConfig(enabled=False)
        >>> result = apply_to_lfo_config(lfo, sync_disabled)
        >>> result["rate_hz"]
        1.0
    """
    # Create a shallow copy to avoid mutating input
    result = lfo_cfg_dict.copy()

    # Only update rate_hz if sync is enabled and auto_update is on
    if sync_cfg.enabled and sync_cfg.auto_update_rate:
        result["rate_hz"] = subdivision_to_rate_hz(sync_cfg.subdivision, sync_cfg.bpm)

    return result
