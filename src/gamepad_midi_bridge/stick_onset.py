"""Stick onset detector for percussive MIDI note triggering.

Pure stdlib module for detecting sudden bursts of stick motion (strikes) and
converting them to percussive MIDI note velocity. Uses speed and acceleration
thresholds to identify impacts, with configurable cooldown to prevent rapid
refires.

When both speed and acceleration exceed their thresholds, a MIDI note velocity
is computed from speed and returned. Otherwise, returns None.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Optional
import math


@dataclass
class StickOnsetConfig:
    """Configuration for stick onset detection.

    Attributes:
        enabled: Whether stick onset detection is active.
        min_speed: Minimum speed (units/sec) to register an onset. Clamped [0.1..20].
        min_acceleration: Minimum acceleration (units/sec²) spike required. Clamped [0.1..100].
        cooldown_ms: Minimum milliseconds between consecutive onsets. Clamped [10..1000].
        velocity_scale: Multiplier from speed to MIDI velocity. Clamped [1..200].
        velocity_min: Minimum MIDI velocity (1..127). Clamped and auto-swapped with velocity_max.
        velocity_max: Maximum MIDI velocity (1..127). Clamped and auto-swapped with velocity_min.
    """

    enabled: bool = False
    min_speed: float = 1.5
    min_acceleration: float = 5.0
    cooldown_ms: int = 80
    velocity_scale: float = 30.0
    velocity_min: int = 30
    velocity_max: int = 127

    def __post_init__(self) -> None:
        """Validate and clamp all config values to safe ranges."""
        self.min_speed = max(0.1, min(20.0, self.min_speed))
        self.min_acceleration = max(0.1, min(100.0, self.min_acceleration))
        self.cooldown_ms = max(10, min(1000, self.cooldown_ms))
        self.velocity_scale = max(1.0, min(200.0, self.velocity_scale))
        self.velocity_min = max(1, min(127, self.velocity_min))
        self.velocity_max = max(1, min(127, self.velocity_max))

        # Auto-swap if min > max
        if self.velocity_min > self.velocity_max:
            self.velocity_min, self.velocity_max = self.velocity_max, self.velocity_min

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: enabled, min_speed, min_acceleration, cooldown_ms,
            velocity_scale, velocity_min, velocity_max.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "StickOnsetConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with config keys. Missing keys use defaults.

        Returns:
            StickOnsetConfig instance with validated values.

        Examples:
            >>> config = StickOnsetConfig.from_dict(
            ...     {"enabled": True, "min_speed": 1.0, "min_acceleration": 2.0}
            ... )
            >>> config.enabled
            True
        """
        return StickOnsetConfig(
            enabled=data.get("enabled", False),
            min_speed=data.get("min_speed", 1.5),
            min_acceleration=data.get("min_acceleration", 5.0),
            cooldown_ms=data.get("cooldown_ms", 80),
            velocity_scale=data.get("velocity_scale", 30.0),
            velocity_min=data.get("velocity_min", 30),
            velocity_max=data.get("velocity_max", 127),
        )


class StickOnsetDetector:
    """Detects sudden stick motion bursts and fires percussive MIDI note velocity.

    Uses speed and acceleration thresholds to identify stick strikes. When both
    thresholds are exceeded, returns a MIDI velocity (1–127) computed from speed.
    Includes cooldown to suppress rapid refires.

    Attributes:
        cfg: StickOnsetConfig instance.
        _last_speed: Previous frame speed for acceleration computation.
        _last_onset_at: Unix timestamp (seconds) of the last fired onset.
    """

    def __init__(self, cfg: StickOnsetConfig) -> None:
        """Initialize stick onset detector.

        Args:
            cfg: StickOnsetConfig instance.
        """
        self.cfg = cfg
        self._last_speed: float = 0.0
        self._last_onset_at: Optional[float] = None

    def feed(
        self, speed: float, acceleration: float, now_s: float
    ) -> Optional[int]:
        """Process stick motion data and return MIDI velocity if an onset fires.

        Checks enabled flag, speed and acceleration thresholds, and cooldown window.
        If all checks pass, computes velocity from speed and returns it (clamped to
        [velocity_min, velocity_max]). Otherwise returns None.

        Args:
            speed: Current stick speed (units/sec, typically 0–10).
            acceleration: Current acceleration spike (units/sec², typically 0–50+).
            now_s: Current time in seconds (Unix timestamp or session-relative).

        Returns:
            MIDI velocity (1–127) if onset fires, else None.

        Examples:
            >>> cfg = StickOnsetConfig(enabled=True, min_speed=1.0, min_acceleration=1.0)
            >>> d = StickOnsetDetector(cfg)
            >>> d.feed(2.0, 5.0, 0.0)  # Speed and accel both above threshold
            100
            >>> d.feed(2.0, 5.0, 0.02)  # Within cooldown window
            >>> d.feed(2.0, 5.0, 0.1)  # After cooldown
            100
        """
        # If disabled, return None immediately
        if not self.cfg.enabled:
            self._last_speed = speed
            return None

        # Check speed threshold
        if speed < self.cfg.min_speed:
            self._last_speed = speed
            return None

        # Check acceleration threshold
        if acceleration < self.cfg.min_acceleration:
            self._last_speed = speed
            return None

        # Check cooldown: if we're within the cooldown window, suppress
        if self._last_onset_at is not None:
            cooldown_sec = self.cfg.cooldown_ms / 1000.0
            if now_s - self._last_onset_at < cooldown_sec:
                self._last_speed = speed
                return None

        # All checks passed — compute velocity from speed
        velocity = int(speed * self.cfg.velocity_scale)
        velocity = max(self.cfg.velocity_min, min(self.cfg.velocity_max, velocity))

        # Update state
        self._last_onset_at = now_s
        self._last_speed = speed

        return velocity

    def reset(self) -> None:
        """Reset detector state.

        Clears the last onset timestamp so the next onset fires immediately.
        Useful for cleanup between sessions or on controller disconnect.
        """
        self._last_speed = 0.0
        self._last_onset_at = None
