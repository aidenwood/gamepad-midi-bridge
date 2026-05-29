"""Named trigger resistance curves for DualSense adaptive trigger profiles.

This module provides a pure-data library of pre-defined trigger resistance curves
that describe the adaptive trigger feel as an array of 10 force levels (0..255).
Each profile is a dataclass descriptor with slug, display name, force levels,
mode hint, and optional description.

No Qt, no hardware writes — purely descriptive data that other code can use to
construct actual trigger resistance commands.

Features:
  - 8 builtin profiles: off, light_resistance, heavy_resistance, two_stage,
    gradual, weapon, springy, mountain.
  - Force levels array (exactly 10 entries, each clamped 0..255).
  - Mode hints: "constant", "two_stage", "gradual", "click", "vibration".
  - Fully parameterized: interpolation, inversion, custom builder.
  - Serialization: to_dict() / from_dict() round-trip.
  - Lookup: get_profile(slug), list_profiles(), profiles_by_mode(mode).
  - Interpolation: interpolate_profile(profile, position_0_1) for smooth force at any position.
  - Inversion: invert_profile(profile) reverses force curve.
  - Custom builder: build_custom(slug, display_name, force_levels, mode_hint).
  - Pure stdlib: no external deps, deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TriggerHapticProfile:
    """Descriptor for a named trigger resistance profile.

    Attributes:
        slug: Unique identifier (e.g., "off", "gradual"). Lowercase, underscore-safe.
        display_name: Human-readable name (e.g., "Gradual Resistance").
        force_levels: Exactly 10 force levels (0..255). Clamped on construction.
                     Index 0 is trigger fully unpressed, index 9 fully pressed.
        mode_hint: Type of profile. One of "constant", "two_stage", "gradual",
                  "click", "vibration". Unknown values are allowed.
        description: Optional human-readable description (e.g., "Light constant resistance").
    """
    slug: str
    display_name: str
    force_levels: List[int]
    mode_hint: str = "constant"
    description: str = ""

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Pad or truncate force_levels to exactly 10 entries.
        if len(self.force_levels) < 10:
            self.force_levels = self.force_levels + [0] * (10 - len(self.force_levels))
        elif len(self.force_levels) > 10:
            self.force_levels = self.force_levels[:10]

        # Clamp each force level to 0..255.
        self.force_levels = [max(0, min(255, f)) for f in self.force_levels]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage / transmission.

        Returns:
            Dictionary with all profile parameters.
        """
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "force_levels": self.force_levels,
            "mode_hint": self.mode_hint,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TriggerHapticProfile:
        """Deserialize from dictionary.

        Args:
            data: Dictionary with profile parameters. Missing keys use dataclass defaults.

        Returns:
            New TriggerHapticProfile instance.
        """
        return cls(
            slug=data.get("slug", ""),
            display_name=data.get("display_name", ""),
            force_levels=data.get("force_levels", [0] * 10),
            mode_hint=data.get("mode_hint", "constant"),
            description=data.get("description", ""),
        )


# 8 builtin profiles.
BUILTIN_PROFILES: List[TriggerHapticProfile] = [
    TriggerHapticProfile(
        slug="off",
        display_name="Off",
        force_levels=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        mode_hint="constant",
        description="No resistance.",
    ),
    TriggerHapticProfile(
        slug="light_resistance",
        display_name="Light Resistance",
        force_levels=[60, 60, 60, 60, 60, 60, 60, 60, 60, 60],
        mode_hint="constant",
        description="Light, uniform resistance throughout trigger travel.",
    ),
    TriggerHapticProfile(
        slug="heavy_resistance",
        display_name="Heavy Resistance",
        force_levels=[200, 200, 200, 200, 200, 200, 200, 200, 200, 200],
        mode_hint="constant",
        description="Heavy, uniform resistance throughout trigger travel.",
    ),
    TriggerHapticProfile(
        slug="two_stage",
        display_name="Two-Stage",
        force_levels=[40, 40, 40, 40, 200, 200, 200, 200, 200, 200],
        mode_hint="two_stage",
        description="Light resistance for first half, suddenly heavy for second half.",
    ),
    TriggerHapticProfile(
        slug="gradual",
        display_name="Gradual",
        force_levels=[20, 40, 70, 100, 130, 160, 190, 210, 230, 250],
        mode_hint="gradual",
        description="Resistance increases linearly from light to heavy.",
    ),
    TriggerHapticProfile(
        slug="weapon",
        display_name="Weapon",
        force_levels=[200, 200, 200, 0, 0, 0, 0, 0, 0, 0],
        mode_hint="click",
        description="Heavy resistance to halfway, then sudden break.",
    ),
    TriggerHapticProfile(
        slug="springy",
        display_name="Springy",
        force_levels=[80, 100, 130, 160, 180, 160, 130, 100, 80, 60],
        mode_hint="vibration",
        description="Peaks in the middle of travel, like a compressed spring.",
    ),
    TriggerHapticProfile(
        slug="mountain",
        display_name="Mountain",
        force_levels=[40, 80, 140, 200, 240, 200, 140, 80, 40, 20],
        mode_hint="vibration",
        description="Resistance peaks at midpoint, tapers at both ends.",
    ),
]


def get_profile(slug: str) -> Optional[TriggerHapticProfile]:
    """Look up a builtin profile by slug.

    Args:
        slug: Profile slug (e.g., "off", "gradual").

    Returns:
        TriggerHapticProfile if found, None otherwise.
    """
    for profile in BUILTIN_PROFILES:
        if profile.slug == slug:
            return profile
    return None


def list_profiles() -> List[TriggerHapticProfile]:
    """Return all builtin profiles.

    Returns:
        List of all TriggerHapticProfile instances.
    """
    return list(BUILTIN_PROFILES)


def profiles_by_mode(mode_hint: str) -> List[TriggerHapticProfile]:
    """Filter profiles by mode hint.

    Args:
        mode_hint: Mode hint (e.g., "constant", "gradual").

    Returns:
        List of matching TriggerHapticProfile instances. Empty if no matches.
    """
    return [p for p in BUILTIN_PROFILES if p.mode_hint == mode_hint]


def interpolate_profile(
    profile: TriggerHapticProfile, position_0_1: float
) -> int:
    """Interpolate the force at a normalized trigger position.

    Given a trigger position from 0.0 (fully unpressed) to 1.0 (fully pressed),
    returns the force (0..255) at that position by linear interpolation between
    the force_levels array entries.

    Args:
        profile: TriggerHapticProfile to interpolate.
        position_0_1: Normalized trigger position (0.0..1.0). Clamped to this range.

    Returns:
        Force level (0..255, int).
    """
    # Clamp position to 0..1.
    pos = max(0.0, min(1.0, position_0_1))

    # Map position to index range 0..9.
    index_float = pos * 9.0  # 0 = index 0, 1 = index 9

    # Get lower and upper indices and interpolation factor.
    lower_idx = int(index_float)
    upper_idx = min(lower_idx + 1, 9)
    alpha = index_float - lower_idx

    # Linear interpolation.
    lower_force = profile.force_levels[lower_idx]
    upper_force = profile.force_levels[upper_idx]
    force = lower_force + alpha * (upper_force - lower_force)

    return int(round(force))


def build_custom(
    slug: str,
    display_name: str,
    force_levels: List[int],
    mode_hint: str = "constant",
) -> TriggerHapticProfile:
    """Create a custom trigger profile.

    Pads short lists to 10 entries (with zeros), truncates long lists to 10,
    and clamps each force level to 0..255.

    Args:
        slug: Unique profile identifier.
        display_name: Human-readable name.
        force_levels: List of force values. Will be normalized to exactly 10.
        mode_hint: Mode hint (default "constant").

    Returns:
        New TriggerHapticProfile instance.
    """
    return TriggerHapticProfile(
        slug=slug,
        display_name=display_name,
        force_levels=force_levels,
        mode_hint=mode_hint,
    )


def invert_profile(profile: TriggerHapticProfile) -> TriggerHapticProfile:
    """Create an inverted copy of a profile.

    Returns a new profile with force_levels reversed (index 0 becomes index 9, etc.)
    and slug/display_name suffixed with "_inverted".

    Args:
        profile: Source TriggerHapticProfile.

    Returns:
        New TriggerHapticProfile with reversed force_levels.
    """
    return TriggerHapticProfile(
        slug=profile.slug + "_inverted",
        display_name=profile.display_name + " (Inverted)",
        force_levels=list(reversed(profile.force_levels)),
        mode_hint=profile.mode_hint,
        description=profile.description + " (Reversed.)",
    )
