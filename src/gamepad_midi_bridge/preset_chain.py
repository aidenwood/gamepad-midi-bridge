"""Preset chain sequencer: walk through a list of presets at configured intervals.

Pure stdlib + dataclasses, no Qt. Provides:
- ChainStep: a step with preset slug, duration, optional label
- PresetChainConfig: configuration for the sequencer (enabled, steps, loop, crossfade_ms)
- PresetChain: the sequencer state machine (start, tick, advance, progress, remaining_s)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class ChainStep:
    """A single step in a preset chain.

    Fields:
        preset_slug: the preset to load for this step (e.g., 'lead', 'Live/intro')
        duration_s: how long to play this step (clamped 0.5..3600)
        label: optional human-readable name for this step
    """

    preset_slug: str
    duration_s: float = 30.0
    label: str = ""

    def __post_init__(self):
        """Enforce duration constraints."""
        self.duration_s = max(0.5, min(3600.0, self.duration_s))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ChainStep:
        """Deserialize from dict."""
        return cls(
            preset_slug=d.get("preset_slug", ""),
            duration_s=d.get("duration_s", 30.0),
            label=d.get("label", ""),
        )


@dataclass
class PresetChainConfig:
    """Configuration for a preset chain sequencer.

    Fields:
        enabled: master switch (default False)
        steps: list of ChainStep objects (default empty)
        loop: if True, wrap to step 0 after the last step;
              if False, stay on the last step (default True)
        crossfade_ms: milliseconds for crossfade between steps (0..5000, placeholder)
    """

    enabled: bool = False
    steps: List[ChainStep] = field(default_factory=list)
    loop: bool = True
    crossfade_ms: int = 0

    def __post_init__(self):
        """Enforce constraints."""
        self.crossfade_ms = max(0, min(5000, self.crossfade_ms))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "enabled": self.enabled,
            "steps": [s.to_dict() for s in self.steps],
            "loop": self.loop,
            "crossfade_ms": self.crossfade_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PresetChainConfig:
        """Deserialize from dict."""
        steps_data = d.get("steps", [])
        steps = [ChainStep.from_dict(s) for s in steps_data]
        return cls(
            enabled=d.get("enabled", False),
            steps=steps,
            loop=d.get("loop", True),
            crossfade_ms=d.get("crossfade_ms", 0),
        )


@dataclass
class PresetChain:
    """Timed preset chain sequencer.

    Manages stepping through a list of preset slugs, each active for a configured
    duration. Provides progress tracking and manual advance controls.

    State:
        cfg: PresetChainConfig
        _index: current step index (0..len(steps)-1)
        _started_at: wall time when start() was called
        _step_started_at: wall time when current step began
    """

    cfg: PresetChainConfig = field(default_factory=PresetChainConfig)
    _index: int = field(default=0, init=False)
    _started_at: Optional[float] = field(default=None, init=False)
    _step_started_at: Optional[float] = field(default=None, init=False)

    def start(self, now_s: float) -> Optional[str]:
        """Begin the chain at the given time.

        Sets start timestamps and returns the current step's preset slug.
        If the chain is empty, returns None.

        Args:
            now_s: current time in seconds (typically time.time())

        Returns:
            the preset slug of the first step, or None if no steps
        """
        self._index = 0
        self._started_at = now_s
        self._step_started_at = now_s
        return self.current().preset_slug if self.current() else None

    def tick(self, now_s: float) -> Optional[str]:
        """Check if the current step has completed and advance if needed.

        If the current step's duration has elapsed, move to the next step
        (or wrap to 0 if loop=True, or stay if loop=False). Otherwise, no change.

        Args:
            now_s: current time in seconds

        Returns:
            the preset slug of the new step if advanced, else None
        """
        if not self.current() or self._step_started_at is None:
            return None

        elapsed = now_s - self._step_started_at
        step = self.current()

        if elapsed >= step.duration_s:
            return self.advance(now_s)

        return None

    def current(self) -> Optional[ChainStep]:
        """Return the active step, or None if empty or out of bounds."""
        if 0 <= self._index < len(self.cfg.steps):
            return self.cfg.steps[self._index]
        return None

    def advance(self, now_s: float) -> Optional[str]:
        """Jump to the next step and return its preset slug.

        If loop=True and we're on the last step, wraps to 0.
        If loop=False and we're on the last step, stays there and returns None.

        Args:
            now_s: current time in seconds

        Returns:
            the preset slug of the new step if advanced, None if staying on last step
        """
        if not self.cfg.steps:
            return None

        # Check if we're on the last step before advancing
        is_last_step = self._index == len(self.cfg.steps) - 1

        if not is_last_step:
            # Not on the last step: move forward
            self._index += 1
        elif self.cfg.loop:
            # On the last step and looping: wrap to 0
            self._index = 0
        else:
            # On the last step and not looping: stay, return None
            return None

        self._step_started_at = now_s
        step = self.current()
        return step.preset_slug if step else None

    def reset(self) -> None:
        """Reset the chain to initial state (index=0, timestamps=None)."""
        self._index = 0
        self._started_at = None
        self._step_started_at = None

    def progress(self, now_s: float) -> float:
        """Return progress through the current step as 0..1.

        0 = step just started
        1 = step complete (or past complete)

        Args:
            now_s: current time in seconds

        Returns:
            progress in range [0, 1], clamped
        """
        if not self.current() or self._step_started_at is None:
            return 0.0

        elapsed = now_s - self._step_started_at
        duration = self.current().duration_s
        p = elapsed / duration if duration > 0 else 0.0
        return max(0.0, min(1.0, p))

    def remaining_s(self, now_s: float) -> Optional[float]:
        """Return seconds remaining in the current step.

        If the step is complete, returns a very small or negative value.
        If no current step, returns None.

        Args:
            now_s: current time in seconds

        Returns:
            seconds remaining, or None if no current step
        """
        if not self.current() or self._step_started_at is None:
            return None

        elapsed = now_s - self._step_started_at
        duration = self.current().duration_s
        remaining = duration - elapsed
        return max(0.0, remaining)

    def total_duration_s(self) -> float:
        """Return the sum of all step durations in seconds.

        Returns:
            sum of all steps' duration_s, or 0.0 if empty
        """
        return sum(step.duration_s for step in self.cfg.steps)
