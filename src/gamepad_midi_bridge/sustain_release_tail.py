"""Sustain release tail helper: delays note-off messages for natural decay.

This module provides note release tail management, delaying note-off messages
by a configurable duration so notes "ring out" instead of cutting cleanly.
Useful for string instruments, pads, and reverb-heavy patches.

Features:
  - Configurable tail duration: 1..10000 ms.
  - Random jitter: Add slight randomization (0..500 ms) for natural feel.
  - PRNG seeding: Reproducible randomization with optional seed.
  - Pure stdlib: No Qt, no external deps, deterministic and testable.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PendingRelease:
    """A queued note-off that will fire at a specific time.

    Attributes:
        note: MIDI note number (0..127).
        channel: MIDI channel (0..15).
        fire_at_s: Absolute time (seconds) when this release should fire.
    """

    note: int
    channel: int
    fire_at_s: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "note": self.note,
            "channel": self.channel,
            "fire_at_s": self.fire_at_s,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PendingRelease:
        """Deserialize from a dict (e.g. from JSON)."""
        return cls(
            note=data.get("note", 0),
            channel=data.get("channel", 0),
            fire_at_s=data.get("fire_at_s", 0.0),
        )


@dataclass
class SustainTailConfig:
    """Configuration for sustain release tail.

    Attributes:
        enabled: Whether sustain tail is active. If False, queue_release() is a no-op.
        tail_ms: Duration to delay note-off (1..10000 ms). Clamped on construction.
        random_jitter_ms: Random ± offset to tail (0..500 ms). Adds slight
                         randomization to each release for natural feel.
                         Clamped on construction.
        seed: Optional seed for the PRNG. If None, uses OS entropy.
             If set, allows reproducible randomization across sessions.
    """

    enabled: bool = False
    tail_ms: float = 200.0
    random_jitter_ms: float = 0.0
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp tail_ms to 1..10000.
        self.tail_ms = max(1.0, min(10000.0, self.tail_ms))
        # Clamp random_jitter_ms to 0..500.
        self.random_jitter_ms = max(0.0, min(500.0, self.random_jitter_ms))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "tail_ms": self.tail_ms,
            "random_jitter_ms": self.random_jitter_ms,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SustainTailConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            tail_ms=data.get("tail_ms", 200.0),
            random_jitter_ms=data.get("random_jitter_ms", 0.0),
            seed=data.get("seed", None),
        )


class SustainReleaseTail:
    """Manager for delayed note-off messages.

    Queues pending note releases and yields ready releases based on elapsed
    time. Pure stdlib with optional seeded PRNG for reproducible jitter.

    Example:
        cfg = SustainTailConfig(enabled=True, tail_ms=200)
        srt = SustainReleaseTail(cfg)

        # Queue a note release in 200 ms
        srt.queue_release(note=60, channel=0, now_s=0.0)

        # Later, check what's ready to fire
        released = srt.pop_ready(now_s=0.25)  # Returns [PendingRelease(...)]
    """

    def __init__(self, cfg: SustainTailConfig) -> None:
        """Initialize with config and PRNG.

        Args:
            cfg: SustainTailConfig instance (clamping happens in __post_init__).
        """
        self.cfg = cfg
        self._pending: List[PendingRelease] = []
        # Initialize PRNG with optional seed.
        self._rng = random.Random(cfg.seed)

    def queue_release(
        self, note: int, channel: int, now_s: float
    ) -> PendingRelease:
        """Queue a note-off to fire after tail_ms (+ optional jitter).

        Args:
            note: MIDI note number (0..127).
            channel: MIDI channel (0..15).
            now_s: Current time in seconds.

        Returns:
            PendingRelease entry (appended to internal queue).
        """
        if not self.cfg.enabled:
            # Return a dummy entry without queueing (fire immediately).
            return PendingRelease(note=note, channel=channel, fire_at_s=now_s)

        # Calculate base fire time.
        base_fire_at_s = now_s + self.cfg.tail_ms / 1000.0

        # Apply optional jitter.
        if self.cfg.random_jitter_ms > 0:
            # Random ± jitter in milliseconds.
            jitter_ms = self._rng.uniform(
                -self.cfg.random_jitter_ms, self.cfg.random_jitter_ms
            )
            fire_at_s = base_fire_at_s + jitter_ms / 1000.0
        else:
            fire_at_s = base_fire_at_s

        entry = PendingRelease(note=note, channel=channel, fire_at_s=fire_at_s)
        self._pending.append(entry)
        return entry

    def pop_ready(self, now_s: float) -> List[PendingRelease]:
        """Return and remove all pending releases that are ready to fire.

        Returns entries with fire_at_s <= now_s, sorted by fire_at_s (earliest first).
        Removes matched entries from the internal queue.

        Args:
            now_s: Current time in seconds.

        Returns:
            List of PendingRelease entries, sorted by fire_at_s.
        """
        ready = []
        remaining = []

        for entry in self._pending:
            if entry.fire_at_s <= now_s:
                ready.append(entry)
            else:
                remaining.append(entry)

        self._pending = remaining

        # Sort ready by fire_at_s (earliest first).
        ready.sort(key=lambda e: e.fire_at_s)

        return ready

    def pending_count(self) -> int:
        """Return the number of pending releases."""
        return len(self._pending)

    def flush_all(self) -> List[PendingRelease]:
        """Return and remove all pending releases (panic/shutdown).

        Returns:
            List of all PendingRelease entries (unsorted).
        """
        result = self._pending[:]
        self._pending = []
        return result

    def clear(self) -> None:
        """Clear all pending releases."""
        self._pending = []

    def next_fire_at(self) -> Optional[float]:
        """Return the earliest fire_at_s, or None if no pending releases."""
        if not self._pending:
            return None
        return min(e.fire_at_s for e in self._pending)
