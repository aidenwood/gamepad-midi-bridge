"""Named haptic effect descriptors for DualSense controllers.

This module provides a pure-data library of pre-defined haptic effects (kick, snap,
click, buzz, etc.) that can be consumed by haptic-aware code. Each effect is a
dataclass descriptor with type, intensity, duration, pulse parameters, and frequency.

No Qt, no hardware writes — purely descriptive data that other code can use to
construct actual rumble/trigger/lightbar commands.

Features:
  - 8 builtin effects: kick, snap, click, buzz, heartbeat, tick, flash, drum_roll.
  - Effect types: rumble, trigger_click, trigger_buzz, trigger_pulse, lightbar_flash.
  - Fully parameterized: intensity (0..1), duration (1..5000 ms), pulse count/gap,
    frequency (1..200 Hz).
  - Serialization: to_dict() / from_dict() round-trip.
  - Lookup: get_effect(slug), list_effects(), effects_by_type(type).
  - Scaling: scale_effect(effect, factor) returns new instance with scaled intensity.
  - Pure stdlib: no external deps, deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class HapticEffect:
    """Descriptor for a named haptic effect.

    Attributes:
        slug: Unique identifier (e.g., "kick", "heartbeat"). Lowercase, underscore-safe.
        display_name: Human-readable name (e.g., "Kick").
        effect_type: Type of effect. One of "rumble", "trigger_click", "trigger_buzz",
                    "trigger_pulse", "lightbar_flash". Unknown values are allowed but
                    flagged in validation.
        intensity: Effect strength (0.0..1.0). Clamped on construction.
                  0.0 = silent/no effect.
                  1.0 = maximum strength.
        duration_ms: Total effect duration in milliseconds (1..5000). Clamped on construction.
        pulse_count: For pulse-type effects, number of pulses (1..32). Clamped on construction.
                    Ignored for non-pulse types.
        pulse_gap_ms: Gap between pulses in milliseconds (1..1000). Clamped on construction.
                     Ignored for non-pulse types.
        frequency_hz: Rumble frequency in Hz (1..200). Clamped on construction.
                     Ignored for non-rumble types.
        description: Optional human-readable description (e.g., "Punchy low-frequency kick").
    """
    slug: str
    display_name: str
    effect_type: str
    intensity: float = 0.5
    duration_ms: int = 100
    pulse_count: int = 1
    pulse_gap_ms: int = 50
    frequency_hz: float = 30.0
    description: str = ""

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp intensity to 0..1.
        self.intensity = max(0.0, min(1.0, self.intensity))

        # Clamp duration_ms to 1..5000.
        self.duration_ms = max(1, min(5000, self.duration_ms))

        # Clamp pulse_count to 1..32.
        self.pulse_count = max(1, min(32, self.pulse_count))

        # Clamp pulse_gap_ms to 1..1000.
        self.pulse_gap_ms = max(1, min(1000, self.pulse_gap_ms))

        # Clamp frequency_hz to 1..200.
        self.frequency_hz = max(1.0, min(200.0, self.frequency_hz))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage / transmission.

        Returns:
            Dictionary with all effect parameters.
        """
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "effect_type": self.effect_type,
            "intensity": self.intensity,
            "duration_ms": self.duration_ms,
            "pulse_count": self.pulse_count,
            "pulse_gap_ms": self.pulse_gap_ms,
            "frequency_hz": self.frequency_hz,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HapticEffect:
        """Deserialize from dictionary.

        Args:
            data: Dictionary with effect parameters. Missing keys use dataclass defaults.

        Returns:
            New HapticEffect instance.
        """
        return cls(
            slug=data.get("slug", ""),
            display_name=data.get("display_name", ""),
            effect_type=data.get("effect_type", "rumble"),
            intensity=data.get("intensity", 0.5),
            duration_ms=data.get("duration_ms", 100),
            pulse_count=data.get("pulse_count", 1),
            pulse_gap_ms=data.get("pulse_gap_ms", 50),
            frequency_hz=data.get("frequency_hz", 30.0),
            description=data.get("description", ""),
        )


# 8 builtin effects: kick, snap, click, buzz, heartbeat, tick, flash, drum_roll.
BUILTIN_EFFECTS: List[HapticEffect] = [
    HapticEffect(
        slug="kick",
        display_name="Kick",
        effect_type="rumble",
        intensity=0.9,
        duration_ms=80,
        frequency_hz=25.0,
        description="Punchy low-frequency kick drum hit.",
    ),
    HapticEffect(
        slug="snap",
        display_name="Snap",
        effect_type="trigger_click",
        intensity=0.7,
        duration_ms=20,
        description="Sharp, snappy trigger click.",
    ),
    HapticEffect(
        slug="click",
        display_name="Click",
        effect_type="trigger_click",
        intensity=0.4,
        duration_ms=10,
        description="Subtle, quiet click.",
    ),
    HapticEffect(
        slug="buzz",
        display_name="Buzz",
        effect_type="trigger_buzz",
        intensity=0.6,
        duration_ms=200,
        frequency_hz=60.0,
        description="High-frequency buzz or vibration.",
    ),
    HapticEffect(
        slug="heartbeat",
        display_name="Heartbeat",
        effect_type="trigger_pulse",
        intensity=0.5,
        duration_ms=600,
        pulse_count=2,
        pulse_gap_ms=100,
        description="Two-beat pulse simulating a heartbeat.",
    ),
    HapticEffect(
        slug="tick",
        display_name="Tick",
        effect_type="trigger_click",
        intensity=0.3,
        duration_ms=8,
        description="Very subtle, fast tick.",
    ),
    HapticEffect(
        slug="flash",
        display_name="Flash",
        effect_type="lightbar_flash",
        intensity=1.0,
        duration_ms=100,
        description="Lightbar flash at full brightness.",
    ),
    HapticEffect(
        slug="drum_roll",
        display_name="Drum Roll",
        effect_type="trigger_pulse",
        intensity=0.7,
        duration_ms=500,
        pulse_count=8,
        pulse_gap_ms=60,
        description="Rapid drum roll with 8 pulses.",
    ),
]


def get_effect(slug: str) -> Optional[HapticEffect]:
    """Look up a builtin effect by slug.

    Args:
        slug: Effect slug (e.g., "kick", "heartbeat").

    Returns:
        HapticEffect if found, None otherwise.
    """
    for effect in BUILTIN_EFFECTS:
        if effect.slug == slug:
            return effect
    return None


def list_effects() -> List[HapticEffect]:
    """Return all builtin effects.

    Returns:
        List of all HapticEffect instances.
    """
    return list(BUILTIN_EFFECTS)


def effects_by_type(effect_type: str) -> List[HapticEffect]:
    """Filter effects by type.

    Args:
        effect_type: Effect type (e.g., "rumble", "trigger_click").

    Returns:
        List of matching HapticEffect instances. Empty if no matches.
    """
    return [e for e in BUILTIN_EFFECTS if e.effect_type == effect_type]


def scale_effect(effect: HapticEffect, factor: float) -> HapticEffect:
    """Create a scaled copy of an effect.

    The new effect has intensity multiplied by factor, clamped to 0..1.
    All other parameters remain unchanged. Returns a new instance (non-mutating).

    Args:
        effect: Source HapticEffect.
        factor: Scaling factor. Clamped to 0..2 (effectively).

    Returns:
        New HapticEffect with scaled intensity.
    """
    # Clamp factor to reasonable range, then scale intensity.
    factor = max(0.0, min(2.0, factor))
    new_intensity = effect.intensity * factor

    # Return new instance (avoid mutating the source).
    return HapticEffect(
        slug=effect.slug,
        display_name=effect.display_name,
        effect_type=effect.effect_type,
        intensity=new_intensity,  # Will be clamped in __post_init__.
        duration_ms=effect.duration_ms,
        pulse_count=effect.pulse_count,
        pulse_gap_ms=effect.pulse_gap_ms,
        frequency_hz=effect.frequency_hz,
        description=effect.description,
    )
