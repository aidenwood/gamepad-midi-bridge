"""LFO waveform library with pure functions and state machine.

This module provides a collection of LFO (Low Frequency Oscillator) waveforms
and a state machine for tracking LFO evolution over time.

Waveforms:
  - sine: Smooth sinusoidal oscillation (0..1 range).
  - triangle: Linear ramp up then down (0..1 range).
  - ramp_up: Linear rise from 0 to 1, resets each cycle.
  - ramp_down: Linear fall from 1 to 0, resets each cycle.
  - square: Digital square wave with configurable duty cycle.
  - sample_hold: Random stepped waveform (re-samples each cycle).
  - smooth_random: Sample-and-hold with smoothing between samples.

All pure functions take a phase value (0..1) and return output (0..1).
The LfoState class manages time-based phase tracking and shape dispatch.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


# Type alias for LFO shape names.
LfoShape = Literal[
    "sine", "triangle", "ramp_up", "ramp_down", "square", "sample_hold", "smooth_random"
]


def sine(phase: float) -> float:
    """Sine wave oscillation.

    Args:
        phase: Phase value 0..1 (wraps at 1).

    Returns:
        Output 0..1 (scaled from sin range -1..1).

    Examples:
        >>> round(sine(0), 3)
        0.5
        >>> round(sine(0.25), 3)
        1.0
        >>> round(sine(0.5), 3)
        0.5
        >>> round(sine(0.75), 3)
        0.0
    """
    return (math.sin(2 * math.pi * phase) + 1) / 2


def triangle(phase: float) -> float:
    """Triangle wave: ramps up 0→1 in first half, down 1→0 in second half.

    Args:
        phase: Phase value 0..1.

    Returns:
        Output 0..1.

    Examples:
        >>> triangle(0)
        0.0
        >>> triangle(0.25)
        0.5
        >>> triangle(0.5)
        1.0
        >>> triangle(0.75)
        0.5
        >>> triangle(1.0)
        0.0
    """
    if phase < 0.5:
        return 2 * phase
    else:
        return 2 * (1 - phase)


def ramp_up(phase: float) -> float:
    """Linear ramp 0→1 over one cycle.

    Args:
        phase: Phase value 0..1.

    Returns:
        Output 0..1 (exactly phase).

    Examples:
        >>> ramp_up(0)
        0.0
        >>> ramp_up(0.5)
        0.5
        >>> ramp_up(1.0)
        1.0
    """
    return phase


def ramp_down(phase: float) -> float:
    """Linear ramp 1→0 over one cycle (inverted ramp_up).

    Args:
        phase: Phase value 0..1.

    Returns:
        Output 0..1 (inverted phase).

    Examples:
        >>> ramp_down(0)
        1.0
        >>> ramp_down(0.5)
        0.5
        >>> ramp_down(1.0)
        0.0
    """
    return 1 - phase


def square(phase: float, duty: float = 0.5) -> float:
    """Square wave with configurable duty cycle.

    Args:
        phase: Phase value 0..1.
        duty: Duty cycle 0..1 (fraction of cycle at high state). Clamped.

    Returns:
        1.0 if phase < duty else 0.0.

    Examples:
        >>> square(0.3, duty=0.5)
        1.0
        >>> square(0.7, duty=0.5)
        0.0
        >>> square(0.5, duty=0.5)
        0.0
        >>> square(0.3, duty=1.0)
        1.0
        >>> square(0.7, duty=1.0)
        1.0
        >>> square(0.3, duty=0.0)
        0.0
    """
    duty = max(0.0, min(1.0, duty))
    return 1.0 if phase < duty else 0.0


def evaluate(shape: str, phase: float, duty: float = 0.5) -> float:
    """Dispatch to the appropriate waveform function.

    Args:
        shape: Waveform name (sine, triangle, ramp_up, ramp_down, square,
               sample_hold, smooth_random). Unknown → sine.
        phase: Phase value 0..1.
        duty: Duty cycle for square wave. Ignored for other shapes.

    Returns:
        Waveform output 0..1.

    Examples:
        >>> round(evaluate("sine", 0.25), 3)
        1.0
        >>> evaluate("triangle", 0.5)
        1.0
        >>> evaluate("ramp_up", 0.5)
        0.5
        >>> evaluate("unknown", 0.25) == sine(0.25)
        True
    """
    if shape == "sine":
        return sine(phase)
    elif shape == "triangle":
        return triangle(phase)
    elif shape == "ramp_up":
        return ramp_up(phase)
    elif shape == "ramp_down":
        return ramp_down(phase)
    elif shape == "square":
        return square(phase, duty)
    else:
        # Unknown shape falls back to sine.
        return sine(phase)


@dataclass
class LfoConfig:
    """Configuration for an LFO instance.

    Attributes:
        enabled: Whether the LFO is active.
        shape: Waveform shape name. Unknown → sine.
        rate_hz: Oscillation rate in Hz. Clamped to 0.01..50.
        depth: Output multiplier. Clamped to 0..1. Applies after waveform eval.
        phase_offset: Initial phase offset 0..1 (phase_offset is added to phase).
        duty: Duty cycle for square wave. Clamped to 0..1.
        bipolar: If True, output is scaled from 0..1 to -depth..+depth.
                 If False (default), output is 0..depth.
    """

    enabled: bool = False
    shape: str = "sine"
    rate_hz: float = 2.0
    depth: float = 1.0
    phase_offset: float = 0.0
    duty: float = 0.5
    bipolar: bool = False

    def __post_init__(self) -> None:
        """Clamp all values to valid ranges."""
        # Unknown shape → sine.
        if self.shape not in (
            "sine",
            "triangle",
            "ramp_up",
            "ramp_down",
            "square",
            "sample_hold",
            "smooth_random",
        ):
            self.shape = "sine"

        # Clamp rate_hz to 0.01..50 Hz.
        self.rate_hz = max(0.01, min(50.0, self.rate_hz))

        # Clamp depth to 0..1.
        self.depth = max(0.0, min(1.0, self.depth))

        # Clamp phase_offset to 0..1.
        self.phase_offset = max(0.0, min(1.0, self.phase_offset))

        # Clamp duty to 0..1.
        self.duty = max(0.0, min(1.0, self.duty))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "shape": self.shape,
            "rate_hz": self.rate_hz,
            "depth": self.depth,
            "phase_offset": self.phase_offset,
            "duty": self.duty,
            "bipolar": self.bipolar,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LfoConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            shape=data.get("shape", "sine"),
            rate_hz=data.get("rate_hz", 2.0),
            depth=data.get("depth", 1.0),
            phase_offset=data.get("phase_offset", 0.0),
            duty=data.get("duty", 0.5),
            bipolar=data.get("bipolar", False),
        )


class LfoState:
    """Stateful LFO oscillator.

    Manages phase tracking over time and handles special waveforms (sample_hold,
    smooth_random) that require per-cycle RNG updates.

    Attributes:
        cfg: LfoConfig instance (may be mutated externally; state reads it).
        _start_time: Absolute timestamp when start() was called. None if not started.
        _rng: Random number generator instance (seeded or unseeded).
        _sh_value: Current sample_hold / smooth_random value.
        _sh_target: Target value for smooth_random lerp.
        _sh_last_phase: Last observed phase; used to detect cycle boundaries.
    """

    def __init__(self, cfg: LfoConfig, seed: Optional[int] = None) -> None:
        """Initialize LFO state.

        Args:
            cfg: LfoConfig instance to use.
            seed: Optional random seed. If provided, sample_hold output is deterministic.
        """
        self.cfg = cfg
        self._start_time: Optional[float] = None
        self._rng = random.Random(seed)
        self._sh_value: float = 0.0
        self._sh_target: float = 0.0
        self._sh_last_phase: float = -1.0

    def start(self, now_s: float) -> None:
        """Mark the start time for this LFO.

        Args:
            now_s: Current time in seconds (e.g. from time.time()).
        """
        self._start_time = now_s

    def value(self, now_s: float) -> float:
        """Compute the current LFO output value.

        If the LFO is not enabled or not started, returns 0.

        For sample_hold and smooth_random, detects cycle boundaries (phase wraps
        from high to low) and re-rolls the random target.

        Args:
            now_s: Current time in seconds.

        Returns:
            LFO output in range:
              - Unipolar (bipolar=False): 0..depth
              - Bipolar (bipolar=True): -depth..+depth
        """
        if not self.cfg.enabled or self._start_time is None:
            return 0.0

        # Compute phase: seconds elapsed * rate_hz, wrapped 0..1, plus offset.
        elapsed = now_s - self._start_time
        phase = ((elapsed * self.cfg.rate_hz + self.cfg.phase_offset) % 1.0)

        # Dispatch to waveform function.
        if self.cfg.shape in ("sample_hold", "smooth_random"):
            # Detect cycle boundary (phase wrapped).
            if phase < self._sh_last_phase:
                # Phase wrapped; re-roll target.
                self._sh_target = self._rng.random()

            self._sh_last_phase = phase

            if self.cfg.shape == "sample_hold":
                # Return the re-rolled target directly.
                self._sh_value = self._sh_target
            else:
                # smooth_random: lerp current value toward target by 0.1.
                self._sh_value = self._sh_value + 0.1 * (self._sh_target - self._sh_value)

            output = self._sh_value
        else:
            # Standard waveform dispatch.
            output = evaluate(self.cfg.shape, phase, self.cfg.duty)

        # Apply depth multiplier.
        output = output * self.cfg.depth

        # Apply bipolar transform.
        if self.cfg.bipolar:
            # Scale from 0..depth to -depth..+depth.
            # Map: 0 -> -depth, depth/2 -> 0, depth -> +depth
            output = output * 2 - self.cfg.depth

        return output

    def reset(self) -> None:
        """Reset the LFO state (start time, sample_hold tracking).

        After reset, the next value() call will return 0 until start() is called again.
        """
        self._start_time = None
        self._sh_value = 0.0
        self._sh_target = 0.0
        self._sh_last_phase = -1.0


def to_cc(value: float, min_cc: int = 0, max_cc: int = 127, bipolar: bool = False) -> int:
    """Map an LFO output value to a MIDI CC range.

    Args:
        value: LFO output value.
               - If bipolar=False: expects 0..1 (unipolar), mapped to 0..127 or min_cc..max_cc.
               - If bipolar=True: expects -1..1 (bipolar), mapped with mid=64.
        min_cc: Lower bound of CC range (default 0).
        max_cc: Upper bound of CC range (default 127).
        bipolar: If True, value is treated as -1..1 with mid at 64.

    Returns:
        Integer CC value clamped to 0..127.

    Examples:
        >>> to_cc(0.5)  # unipolar mid
        64
        >>> to_cc(1.0)  # unipolar max
        127
        >>> to_cc(0.0)  # unipolar min
        0
        >>> to_cc(0.0, bipolar=True)  # bipolar mid (0 → 64)
        64
        >>> to_cc(1.0, bipolar=True)  # bipolar max (1 → 127)
        127
        >>> to_cc(-1.0, bipolar=True)  # bipolar min (-1 → 0)
        0
    """
    if bipolar:
        # Map -1..1 to 0..127.
        # 0 (mid) → 64
        # 1 (max) → 127
        # -1 (min) → 0
        cc_value = 64 + (value * 63.5)
    else:
        # Map 0..1 to 0..127 (or min_cc..max_cc).
        range_size = max_cc - min_cc
        cc_value = min_cc + (value * range_size)

    # Clamp to 0..127 and round.
    return max(0, min(127, int(round(cc_value))))
