"""Pure-function MIDI velocity quantizer for chip-tune feel and dynamic range control.

This module provides velocity quantization to N discrete levels, useful for:
  - Chip-tune / lo-fi aesthetic (4 levels: pp/mp/mf/ff).
  - Limiting dynamic range for controllers with poor velocity control.
  - Stylized expression curves.

Features:
  - Quantize velocity to 2..32 discrete levels, evenly spaced.
  - Optional bias: shift bin boundaries (positive = favor higher levels, negative = favor lower).
  - Optional level names (e.g. ["pp", "mp", "mf", "ff"]).
  - Preview curve: map all 128 input velocities to output for UI visualization.
  - Pure stdlib: No Qt, no external deps, deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class VelocityQuantizerConfig:
    """Configuration for velocity quantizer.

    Attributes:
        enabled: Whether velocity quantization is active. If False, quantize() returns raw input unchanged.
        levels: Number of discrete velocity levels (2..32). Clamped on construction.
               Default: 4 (pp/mp/mf/ff).
        min_value: Minimum output velocity (1..127). Default: 1.
                  Clamped on construction.
        max_value: Maximum output velocity (1..127, >= min_value). Default: 127.
                  Clamped on construction.
        bias: Bias factor for level boundaries (-1.0..+1.0). Default: 0.0.
             Positive bias: shift boundaries up → favor higher levels.
             Negative bias: shift boundaries down → favor lower levels.
             Clamped on construction.
        level_names: Optional human-readable names for each level.
                    If provided, must have exactly `levels` entries.
                    Example: ["pp", "mp", "mf", "ff"] for 4 levels.
    """
    enabled: bool = False
    levels: int = 4
    min_value: int = 1
    max_value: int = 127
    bias: float = 0.0
    level_names: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp levels to 2..32.
        self.levels = max(2, min(32, self.levels))

        # Clamp min_value to 1..127.
        self.min_value = max(1, min(127, self.min_value))

        # Clamp max_value to 1..127 and ensure >= min_value.
        self.max_value = max(1, min(127, self.max_value))
        if self.max_value < self.min_value:
            self.max_value = self.min_value

        # Clamp bias to -1.0..+1.0.
        self.bias = max(-1.0, min(1.0, self.bias))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "levels": self.levels,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "bias": self.bias,
            "level_names": self.level_names,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VelocityQuantizerConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            levels=data.get("levels", 4),
            min_value=data.get("min_value", 1),
            max_value=data.get("max_value", 127),
            bias=data.get("bias", 0.0),
            level_names=data.get("level_names", []),
        )


def compute_levels(cfg: VelocityQuantizerConfig) -> List[int]:
    """Compute the actual velocity value at each discrete level.

    Maps levels 0..N-1 to evenly-spaced velocity values from min_value to max_value.

    Args:
        cfg: VelocityQuantizerConfig specifying levels, min, max.

    Returns:
        List of N velocity values (one per level), evenly spaced.
        Example: 4 levels from 1 to 127 → [1, 43, 85, 127] (approx).
    """
    n = cfg.levels
    min_v = cfg.min_value
    max_v = cfg.max_value

    if n == 1:
        return [max_v]

    result: List[int] = []
    for i in range(n):
        frac = i / (n - 1)
        value = min_v + frac * (max_v - min_v)
        result.append(int(round(value)))

    return result


def quantize(velocity: int, cfg: VelocityQuantizerConfig) -> int:
    """Quantize a raw MIDI velocity to one of the discrete levels.

    Maps velocity 0..127 to a discrete level, with optional bias applied to
    the bin boundaries.

    Args:
        velocity: Raw MIDI velocity (0..127).
        cfg: VelocityQuantizerConfig specifying levels, bias, min/max.

    Returns:
        Quantized velocity (one of the computed level values).
        If not enabled, returns raw velocity clamped to 0..127.
    """
    velocity = max(0, min(127, velocity))

    if not cfg.enabled:
        return velocity

    levels_list = compute_levels(cfg)

    n = cfg.levels
    bin_width = 128.0 / n

    bias_shift = cfg.bias * bin_width

    raw_index = (velocity + bias_shift) / bin_width
    bin_index = int(raw_index)

    bin_index = max(0, min(n - 1, bin_index))

    return levels_list[bin_index]


def level_index(velocity: int, cfg: VelocityQuantizerConfig) -> int:
    """Return the level index (0..levels-1) for a given velocity.

    Args:
        velocity: Raw MIDI velocity (0..127).
        cfg: VelocityQuantizerConfig.

    Returns:
        Level index (0..levels-1), or 0 if not enabled.
    """
    if not cfg.enabled:
        return 0

    velocity = max(0, min(127, velocity))
    n = cfg.levels
    bin_width = 128.0 / n

    bias_shift = cfg.bias * bin_width
    raw_index = (velocity + bias_shift) / bin_width
    bin_index = int(raw_index)

    return max(0, min(n - 1, bin_index))


def level_name(velocity: int, cfg: VelocityQuantizerConfig) -> str:
    """Return the name of the level for a given velocity, if defined.

    Args:
        velocity: Raw MIDI velocity (0..127).
        cfg: VelocityQuantizerConfig with optional level_names.

    Returns:
        The name at level_names[index] if defined and in range, else "".
    """
    if not cfg.enabled or not cfg.level_names:
        return ""

    index = level_index(velocity, cfg)

    if 0 <= index < len(cfg.level_names):
        return cfg.level_names[index]

    return ""


def preview_curve(cfg: VelocityQuantizerConfig, samples: int = 128) -> List[int]:
    """Generate a preview curve mapping input velocities to output.

    Useful for UI visualization (e.g. a curve graph showing the quantization effect).

    Args:
        cfg: VelocityQuantizerConfig.
        samples: Number of samples to generate (default: 128 for full MIDI range).

    Returns:
        List of `samples` output velocities, one per input velocity index.
    """
    result: List[int] = []
    for i in range(samples):
        output = quantize(i, cfg)
        result.append(output)

    return result
