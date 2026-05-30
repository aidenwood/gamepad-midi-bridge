"""LFO phase-scope sampler for UI visualization.

This module provides pure functions to sample LFO waveforms over a phase range
and generate scope-style display points for UI visualization. No Qt dependencies.

Classes:
  - PhaseScopePoint: Single sample point (phase, value, time_ms).
  - PhaseScopeConfig: Configuration for scope sampling (samples, cycles, etc).

Functions:
  - sample_cycle(): Sample N points over one LFO cycle.
  - sample_multi_cycles(): Extend sampling over multiple cycles.
  - min_max(): Compute value bounds for axis scaling.
  - as_cc_curve(): Convert points to integer CC values (0..127).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from gamepad_midi_bridge.lfo_waveforms import evaluate


@dataclass
class PhaseScopePoint:
    """Single sample point in a phase-scope curve.

    Attributes:
        phase: Phase position 0..1 (0=cycle start, 1=cycle end).
        value: Raw LFO output (0..1 unipolar or -1..1 bipolar).
        time_ms: Time relative to cycle start in milliseconds.
    """

    phase: float
    value: float
    time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "phase": self.phase,
            "value": self.value,
            "time_ms": self.time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PhaseScopePoint:
        """Deserialize from dict."""
        return cls(
            phase=data.get("phase", 0.0),
            value=data.get("value", 0.0),
            time_ms=data.get("time_ms", 0.0),
        )


@dataclass
class PhaseScopeConfig:
    """Configuration for LFO phase-scope sampling.

    Attributes:
        enabled: Whether scope is active.
        samples: Number of samples per cycle (clamped 8..1024).
        cycles: How many cycles to render (clamped 1..16).
        apply_depth: If True, multiply waveform by lfo_config depth.
        apply_bipolar: If True, convert to -1..+1 when lfo_config.bipolar is set.
    """

    enabled: bool = False
    samples: int = 64
    cycles: int = 1
    apply_depth: bool = True
    apply_bipolar: bool = True

    def __post_init__(self) -> None:
        """Clamp all values to valid ranges."""
        self.samples = max(8, min(1024, self.samples))
        self.cycles = max(1, min(16, self.cycles))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "samples": self.samples,
            "cycles": self.cycles,
            "apply_depth": self.apply_depth,
            "apply_bipolar": self.apply_bipolar,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PhaseScopeConfig:
        """Deserialize from dict."""
        return cls(
            enabled=data.get("enabled", False),
            samples=data.get("samples", 64),
            cycles=data.get("cycles", 1),
            apply_depth=data.get("apply_depth", True),
            apply_bipolar=data.get("apply_bipolar", True),
        )


def sample_cycle(
    lfo_config_dict: Dict[str, Any], scope_cfg: PhaseScopeConfig
) -> List[PhaseScopePoint]:
    """Sample N points over one LFO cycle.

    For each phase step 0..1, evaluates the waveform via lfo_waveforms.evaluate(),
    then applies depth and bipolar transformations if configured.

    Args:
        lfo_config_dict: LFO config dict with keys: shape, rate_hz, depth, duty, bipolar.
                        Missing keys default sensibly (shape→'sine', rate_hz→2.0, depth→1.0).
        scope_cfg: PhaseScopeConfig (samples, apply_depth, apply_bipolar).

    Returns:
        List of N PhaseScopePoint objects spanning phase 0..(N-1)/N.
    """
    shape = lfo_config_dict.get("shape", "sine")
    rate_hz = lfo_config_dict.get("rate_hz", 2.0)
    depth = lfo_config_dict.get("depth", 1.0)
    duty = lfo_config_dict.get("duty", 0.5)
    bipolar = lfo_config_dict.get("bipolar", False)

    # Clamp rate_hz to avoid division by zero or infinite time.
    rate_hz = max(0.01, min(50.0, rate_hz))

    # Cycle duration in seconds.
    cycle_duration_s = 1.0 / rate_hz

    points: List[PhaseScopePoint] = []

    for i in range(scope_cfg.samples):
        # Phase for this sample: 0 at i=0, approaching 1 as i → samples-1.
        phase = i / scope_cfg.samples

        # Evaluate waveform at this phase.
        value = evaluate(shape, phase, duty)

        # Apply depth multiplier if configured.
        if scope_cfg.apply_depth:
            value = value * depth
        else:
            # Clamp to 0..1 range even without depth.
            value = max(0.0, min(1.0, value))

        # Apply bipolar transform if configured and lfo_config says bipolar.
        if scope_cfg.apply_bipolar and bipolar:
            # Scale from 0..depth (or 0..1) to -depth..+depth (or -1..+1).
            # Map: 0 → -amplitude, 0.5*amplitude → 0, amplitude → +amplitude
            amplitude = depth if scope_cfg.apply_depth else 1.0
            value = value * 2 - amplitude

        # Time in milliseconds relative to cycle start.
        time_ms = (phase / rate_hz) * 1000.0

        points.append(PhaseScopePoint(phase=phase, value=value, time_ms=time_ms))

    return points


def sample_multi_cycles(
    lfo_config_dict: Dict[str, Any], scope_cfg: PhaseScopeConfig
) -> List[PhaseScopePoint]:
    """Sample N points over multiple LFO cycles.

    Extends sample_cycle() over scope_cfg.cycles cycles, keeping phase unwrapped
    and time_ms continuously increasing.

    Args:
        lfo_config_dict: LFO config dict.
        scope_cfg: PhaseScopeConfig (samples, cycles, apply_depth, apply_bipolar).

    Returns:
        List of samples * cycles PhaseScopePoint objects.
    """
    rate_hz = lfo_config_dict.get("rate_hz", 2.0)
    rate_hz = max(0.01, min(50.0, rate_hz))
    cycle_duration_s = 1.0 / rate_hz
    cycle_duration_ms = cycle_duration_s * 1000.0

    shape = lfo_config_dict.get("shape", "sine")
    depth = lfo_config_dict.get("depth", 1.0)
    duty = lfo_config_dict.get("duty", 0.5)
    bipolar = lfo_config_dict.get("bipolar", False)

    points: List[PhaseScopePoint] = []

    total_samples = scope_cfg.samples * scope_cfg.cycles

    for i in range(total_samples):
        # Unwrapped phase: 0..cycles as i goes 0..total_samples-1.
        unwrapped_phase = i / scope_cfg.samples

        # Wrapped phase for evaluate(): 0..1.
        phase = unwrapped_phase % 1.0

        # Evaluate waveform.
        value = evaluate(shape, phase, duty)

        # Apply depth if configured.
        if scope_cfg.apply_depth:
            value = value * depth
        else:
            value = max(0.0, min(1.0, value))

        # Apply bipolar transform if configured.
        if scope_cfg.apply_bipolar and bipolar:
            amplitude = depth if scope_cfg.apply_depth else 1.0
            value = value * 2 - amplitude

        # Time in milliseconds (continuous across cycles).
        time_ms = (unwrapped_phase / rate_hz) * 1000.0

        points.append(PhaseScopePoint(phase=unwrapped_phase, value=value, time_ms=time_ms))

    return points


def min_max(points: List[PhaseScopePoint]) -> Tuple[float, float]:
    """Compute min and max values from a list of points.

    Useful for scaling UI axes to fit the data.

    Args:
        points: List of PhaseScopePoint objects.

    Returns:
        Tuple (min_val, max_val). If points is empty, returns (0.0, 1.0).
    """
    if not points:
        return 0.0, 1.0

    values = [p.value for p in points]
    return min(values), max(values)


def as_cc_curve(
    points: List[PhaseScopePoint], min_cc: int = 0, max_cc: int = 127
) -> List[int]:
    """Convert phase-scope points to integer CC values.

    For unipolar (0..1), maps linearly to min_cc..max_cc.
    For bipolar (-1..1), maps with mid=64 (or (min_cc+max_cc)/2).

    Args:
        points: List of PhaseScopePoint objects.
        min_cc: Lower CC bound (default 0).
        max_cc: Upper CC bound (default 127).

    Returns:
        List of integer CC values, one per point.
    """
    if not points:
        return []

    # Detect bipolar by checking if any value < 0.
    is_bipolar = any(p.value < 0.0 for p in points)

    cc_values: List[int] = []

    for point in points:
        if is_bipolar:
            # Bipolar: -1..1 → 0..127 with mid at 64.
            # Map: -1 → 0, 0 → 64, 1 → 127.
            cc_value = 64 + (point.value * 63.5)
        else:
            # Unipolar: 0..1 → min_cc..max_cc.
            range_size = max_cc - min_cc
            cc_value = min_cc + (point.value * range_size)

        # Clamp and round to integer.
        cc_int = max(0, min(127, int(round(cc_value))))
        cc_values.append(cc_int)

    return cc_values
