"""Pure-function CC value bitcrush quantizer for lo-fi / stepped expression.

This module provides bit-depth reduction and sample-and-hold rate reduction
for CC values, enabling lo-fi and stepped expression control over MIDI.

Features:
  - Bit-depth reduction: Quantize CC values to 2^bit_depth distinct levels.
                         bit_depth=7: no crushing (128 levels).
                         bit_depth=4: 16 distinct levels.
                         bit_depth=1: on/off (2 levels).
  - Sample-and-hold rate reduction: Hold value for N ms before re-emission.
                                    Enables stepped expression.
  - Wet/dry blending: Linearly interpolate between crushed and original.
  - Pure stdlib: No Qt, no external deps, deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CcBitcrushConfig:
    """Configuration for CC bitcrush quantizer.

    Attributes:
        enabled: Whether bitcrush is active. If False, feed() returns raw input unchanged.
        bit_depth: Bit-depth for quantization (1..7). Higher = less crushing / more levels.
                  Clamped on construction.
                  bit_depth=7: 128 levels (no crushing).
                  bit_depth=4: 16 levels.
                  bit_depth=1: 2 levels (on/off).
        sample_hold_ms: Sample-and-hold rate reduction (0..5000 ms).
                       0 = no rate reduction (always emit fresh crushed value).
                       > 0: hold value for this many ms before re-emission.
                       Clamped on construction.
        wet: Wet/dry blend (0.0..1.0). Linear interpolation between crushed and original.
            0.0 = fully dry (original input).
            1.0 = fully wet (crushed output).
            0.5 = 50/50 blend.
            Clamped on construction.
    """
    enabled: bool = False
    bit_depth: int = 7
    sample_hold_ms: int = 0
    wet: float = 1.0

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp bit_depth to 1..7.
        self.bit_depth = max(1, min(7, self.bit_depth))

        # Clamp sample_hold_ms to 0..5000.
        self.sample_hold_ms = max(0, min(5000, self.sample_hold_ms))

        # Clamp wet to 0.0..1.0.
        self.wet = max(0.0, min(1.0, self.wet))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "bit_depth": self.bit_depth,
            "sample_hold_ms": self.sample_hold_ms,
            "wet": self.wet,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CcBitcrushConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            bit_depth=data.get("bit_depth", 7),
            sample_hold_ms=data.get("sample_hold_ms", 0),
            wet=data.get("wet", 1.0),
        )


def crush_value(value: int, bit_depth: int) -> int:
    """Quantize a CC value to 2^bit_depth distinct levels.

    Maps value 0..127 to one of 2^bit_depth discrete levels, uniformly spaced.

    Args:
        value: Raw CC value (0..127).
        bit_depth: Bit-depth (1..7). Higher = less crushing.

    Returns:
        Quantized CC value (0..127).
    """
    # Clamp input to 0..127.
    value = max(0, min(127, value))

    # Compute quantization step: 128 levels / 2^bit_depth levels per octant.
    # e.g., bit_depth=4 → 2^4=16 levels → step=128/16=8.
    step = 128.0 / (2 ** bit_depth)

    # Quantize: which level does this value belong to?
    quantized = int(value / step) * step

    # Snap to 127 if we're at the last level (to handle rounding).
    if quantized > 127:
        quantized = 127

    return int(quantized)


def apply_wet(crushed: int, original: int, wet: float) -> int:
    """Linearly blend between crushed and original values.

    Args:
        crushed: Crushed output.
        original: Original input.
        wet: Blend factor (0.0..1.0). 0=dry, 1=wet.

    Returns:
        Blended value (0..127), rounded to nearest integer.
    """
    return round(crushed * wet + original * (1.0 - wet))


class CcBitcrusher:
    """Stateful CC bitcrush quantizer with rate reduction.

    Maintains sample-and-hold state to enable stepped rate reduction.
    """

    def __init__(self, cfg: CcBitcrushConfig) -> None:
        """Initialize bitcrusher with config.

        Args:
            cfg: CcBitcrushConfig describing quantization and rate reduction.
        """
        self.cfg = cfg
        self._last_emit_at: Optional[float] = None
        self._last_emit_value: int = 0

    def feed(self, raw_value: int, now_s: float) -> int:
        """Feed a raw CC value through the bitcrusher and return the result.

        Args:
            raw_value: Raw CC value (0..127).
            now_s: Current time in seconds (for sample-and-hold rate limiting).

        Returns:
            Quantized CC value (0..127). If not enabled, returns raw_value unchanged.
        """
        # Clamp input to 0..127.
        raw_value = max(0, min(127, raw_value))

        # If not enabled, return raw unchanged.
        if not self.cfg.enabled:
            return raw_value

        # Check sample-and-hold rate limiter.
        if self.cfg.sample_hold_ms > 0 and self._last_emit_at is not None:
            elapsed_ms = (now_s - self._last_emit_at) * 1000.0
            if elapsed_ms < self.cfg.sample_hold_ms:
                # Hold time not yet elapsed; return last emitted value.
                return self._last_emit_value

        # Quantize raw value to discrete levels.
        crushed = crush_value(raw_value, self.cfg.bit_depth)

        # Blend wet/dry.
        result = apply_wet(crushed, raw_value, self.cfg.wet)

        # Update state.
        self._last_emit_value = result
        self._last_emit_at = now_s

        return result

    def reset(self) -> None:
        """Reset the bitcrusher state.

        Clears sample-and-hold memory so the next feed() will emit fresh.
        """
        self._last_emit_at = None
        self._last_emit_value = 0
