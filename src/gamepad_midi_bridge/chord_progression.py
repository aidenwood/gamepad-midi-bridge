"""Chord-progression cycler: walk through a list of chord shapes one-at-a-time.

Pure stdlib, no Qt. Stateful helper that advances through a chord sequence
on demand (fire) or automatically after a timeout (tick). Each chord is a
ChordStep with MIDI notes, velocity, and optional channel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChordStep:
    """A single chord in a progression: notes, velocity, channel, label.

    Attributes:
        notes: List of MIDI note numbers (0..127).
        velocity: MIDI velocity (1..127, default 100).
        channel: MIDI channel (1..16) or None to inherit from parent.
        label: Display name (e.g., "Cmaj", "Fmaj7").
    """

    notes: list[int] = field(default_factory=list)
    velocity: int = 100
    channel: Optional[int] = None
    label: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict, clamping values defensively."""
        return {
            "notes": [max(0, min(127, n)) for n in self.notes],
            "velocity": max(1, min(127, self.velocity)),
            "channel": self.channel if self.channel is None else max(1, min(16, self.channel)),
            "label": self.label,
        }

    @staticmethod
    def from_dict(data: dict) -> ChordStep:
        """Deserialize from dict, clamping values defensively."""
        notes = [max(0, min(127, n)) for n in data.get("notes", [])]
        velocity = max(1, min(127, data.get("velocity", 100)))
        channel = data.get("channel")
        if channel is not None:
            channel = max(1, min(16, channel))
        label = data.get("label", "")
        return ChordStep(notes=notes, velocity=velocity, channel=channel, label=label)


@dataclass
class ChordProgressionConfig:
    """Configuration for a chord progression.

    Attributes:
        enabled: Whether the progression is active.
        steps: List of ChordStep objects to cycle through.
        loop: If True, wrap to step 0 at end; if False, stay on last step.
        auto_advance_ms: Auto-advance interval (0 = manual only; 1..60000).
    """

    enabled: bool = False
    steps: list[ChordStep] = field(default_factory=list)
    loop: bool = True
    auto_advance_ms: int = 0

    def to_dict(self) -> dict:
        """Serialize to dict, clamping values defensively."""
        return {
            "enabled": self.enabled,
            "steps": [step.to_dict() for step in self.steps],
            "loop": self.loop,
            "auto_advance_ms": max(0, min(60000, self.auto_advance_ms)),
        }

    @staticmethod
    def from_dict(data: dict) -> ChordProgressionConfig:
        """Deserialize from dict, clamping values defensively."""
        enabled = data.get("enabled", False)
        steps = [ChordStep.from_dict(s) for s in data.get("steps", [])]
        loop = data.get("loop", True)
        auto_advance_ms = max(0, min(60000, data.get("auto_advance_ms", 0)))
        return ChordProgressionConfig(
            enabled=enabled, steps=steps, loop=loop, auto_advance_ms=auto_advance_ms
        )


class ChordProgression:
    """Chord progression cycler: advance through chord shapes on demand or timer.

    Usage:
        cfg = ChordProgressionConfig(
            enabled=True,
            steps=[
                ChordStep(notes=[60, 64, 67], label="Cmaj"),
                ChordStep(notes=[65, 69, 72], label="Fmaj"),
                ChordStep(notes=[67, 71, 74], label="Gmaj"),
            ],
            loop=True,
        )
        prog = ChordProgression(cfg)
        step = prog.fire(0.0)  # C major, advances to next
        step = prog.fire(0.1)  # F major, advances to next
        step = prog.fire(0.2)  # G major, wraps to C
    """

    def __init__(self, cfg: ChordProgressionConfig):
        """Initialize the progression.

        Args:
            cfg: ChordProgressionConfig with steps and behavior.
        """
        self.config = cfg
        self.index: int = 0
        self.last_fired_at: Optional[float] = None

    def current(self) -> Optional[ChordStep]:
        """Return the current chord step (at self.index).

        Returns:
            ChordStep at current index, or None if steps are empty.
        """
        if not self.config.steps:
            return None
        return self.config.steps[self.index]

    def fire(self, now_s: float) -> Optional[ChordStep]:
        """Return current step and advance to the next.

        If steps are empty, returns None without advancing.
        If at end of steps:
            - loop=True: wraps to step 0
            - loop=False: stays on last step
        Updates last_fired_at to now_s.

        Args:
            now_s: Current time in seconds.

        Returns:
            ChordStep at current index before advancing, or None if empty.
        """
        if not self.config.steps:
            return None

        current_step = self.config.steps[self.index]
        self.last_fired_at = now_s

        # Advance to next step
        if self.index < len(self.config.steps) - 1:
            self.index += 1
        elif self.config.loop:
            self.index = 0
        # else: stay on last step (don't advance)

        return current_step

    def advance(self) -> None:
        """Manually advance to the next step without firing.

        If at end:
            - loop=True: wraps to step 0
            - loop=False: stays on last step
        """
        if not self.config.steps:
            return

        if self.index < len(self.config.steps) - 1:
            self.index += 1
        elif self.config.loop:
            self.index = 0
        # else: stay on last step (don't advance)

    def reset(self) -> None:
        """Reset to the first step and clear last_fired_at."""
        self.index = 0
        self.last_fired_at = None

    def tick(self, now_s: float) -> Optional[int]:
        """Auto-advance if auto_advance_ms has elapsed since last fire.

        If auto_advance_ms > 0 and last_fired_at is not None and
        (now_s - last_fired_at) * 1000 >= auto_advance_ms:
            - Calls advance()
            - Updates last_fired_at to now_s
            - Returns new index

        Otherwise returns None.

        Args:
            now_s: Current time in seconds.

        Returns:
            New index if auto-advanced, None otherwise.
        """
        if self.config.auto_advance_ms == 0:
            return None

        if self.last_fired_at is None:
            return None

        elapsed_ms = (now_s - self.last_fired_at) * 1000
        if elapsed_ms >= self.config.auto_advance_ms:
            self.advance()
            self.last_fired_at = now_s
            return self.index

        return None
