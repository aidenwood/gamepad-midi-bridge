"""Tap-delay echo helper: fire a note plus N delayed copies at decreasing velocity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TapDelayConfig:
    """Configuration for tap-delay echo behavior."""

    enabled: bool = False
    taps: int = 3  # Number of echoes after the initial hit
    delay_ms: int = 250  # Gap between echoes (milliseconds)
    feedback: float = 0.6  # Velocity multiplier per echo
    pitch_shift_per_tap: int = 0  # Semitones to add per echo

    def __post_init__(self) -> None:
        """Clamp all parameters to valid ranges."""
        # taps: 1..16
        self.taps = max(1, min(16, self.taps))
        # delay_ms: 10..5000
        self.delay_ms = max(10, min(5000, self.delay_ms))
        # feedback: 0..0.99
        self.feedback = max(0.0, min(0.99, self.feedback))
        # pitch_shift_per_tap: -12..+12
        self.pitch_shift_per_tap = max(-12, min(12, self.pitch_shift_per_tap))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "enabled": self.enabled,
            "taps": self.taps,
            "delay_ms": self.delay_ms,
            "feedback": self.feedback,
            "pitch_shift_per_tap": self.pitch_shift_per_tap,
        }

    @staticmethod
    def from_dict(d: dict) -> TapDelayConfig:
        """Deserialize from dict."""
        return TapDelayConfig(
            enabled=d.get("enabled", False),
            taps=d.get("taps", 3),
            delay_ms=d.get("delay_ms", 250),
            feedback=d.get("feedback", 0.6),
            pitch_shift_per_tap=d.get("pitch_shift_per_tap", 0),
        )


@dataclass
class DelayedTap:
    """A note scheduled to fire at a future time."""

    note: int
    velocity: int
    fire_at_s: float
    channel: int


class TapDelay:
    """Generates delayed echo copies of a note with decreasing velocity."""

    def __init__(self, cfg: TapDelayConfig) -> None:
        """Initialize tap-delay with config."""
        self.cfg = cfg
        self._queue: List[DelayedTap] = []

    def schedule(
        self, note: int, velocity: int, channel: int, now_s: float
    ) -> List[DelayedTap]:
        """
        Schedule N delayed echoes of a note.

        Returns the newly created DelayedTap entries in order.
        Notes outside 0..127 after pitch shift are dropped.
        Velocities are clamped to 1..127 after feedback scaling.
        """
        if not self.cfg.enabled:
            return []

        new_taps: List[DelayedTap] = []
        delay_s = self.cfg.delay_ms / 1000.0

        for tap_idx in range(self.cfg.taps):
            # Calculate velocity: apply feedback N times, clamp to 1..127.
            tap_velocity = velocity * (self.cfg.feedback ** tap_idx)
            tap_velocity_int = max(1, min(127, int(round(tap_velocity))))

            # Calculate pitch: add pitch_shift_per_tap * tap_idx (0-based).
            # tap_idx 0 → no shift (original note)
            # tap_idx 1 → shift by 1*pitch_shift_per_tap
            # tap_idx 2 → shift by 2*pitch_shift_per_tap, etc.
            tap_note = note + (self.cfg.pitch_shift_per_tap * tap_idx)
            if tap_note < 0 or tap_note > 127:
                # Drop this echo if it's out of range.
                continue

            # Calculate fire time.
            fire_at = now_s + (delay_s * (tap_idx + 1))

            tap = DelayedTap(
                note=tap_note, velocity=tap_velocity_int, fire_at_s=fire_at, channel=channel
            )
            new_taps.append(tap)
            self._queue.append(tap)

        return new_taps

    def pop_ready(self, now_s: float) -> List[DelayedTap]:
        """
        Return and remove all queued taps with fire_at_s <= now_s.

        Results are sorted by fire_at_s.
        """
        ready = [tap for tap in self._queue if tap.fire_at_s <= now_s]
        # Remove ready taps from queue.
        self._queue = [tap for tap in self._queue if tap.fire_at_s > now_s]
        # Sort by fire time.
        ready.sort(key=lambda t: t.fire_at_s)
        return ready

    def pending_count(self) -> int:
        """Return the number of queued taps awaiting firing."""
        return len(self._queue)

    def clear(self) -> None:
        """Empty the queue."""
        self._queue.clear()
