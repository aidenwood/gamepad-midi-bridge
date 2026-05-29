"""Preset blending: morph between two configs via linear interpolation.

Pure stdlib + dataclasses, no Qt. Provides:
- lerp / lerp_int / lerp_bool for individual value blending
- lerp_dict_values / blend_configs for structured config blending
- BlendConfig + BlendAnimator for animation support
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation: a at t=0, b at t=1. Clamps t to [0, 1]."""
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def lerp_int(a: int, b: int, t: float) -> int:
    """Integer interpolation: lerp + round to nearest int."""
    return round(lerp(float(a), float(b), t))


def lerp_bool(a: bool, b: bool, t: float) -> bool:
    """Boolean crossfade: returns a if t < 0.5, else b."""
    return a if t < 0.5 else b


def lerp_dict_values(
    a: Dict[str, Any],
    b: Dict[str, Any],
    t: float,
    numeric_keys: List[str] | None = None,
    int_keys: List[str] | None = None,
    bool_keys: List[str] | None = None,
) -> Dict[str, Any]:
    """Interpolate dict values with type-aware lerping.

    Args:
        a: source dict at t=0
        b: source dict at t=1
        t: blend factor (clamped 0..1)
        numeric_keys: list of keys to lerp as floats
        int_keys: list of keys to lerp as ints (rounded)
        bool_keys: list of keys to crossfade (bool)

    Returns:
        new dict with blended values. Keys only in one dict are skipped.
        Keys not in any category default to: take from a if t<0.5 else b.
    """
    numeric_keys = numeric_keys or []
    int_keys = int_keys or []
    bool_keys = bool_keys or []

    result = {}
    all_keys = set(a.keys()) & set(b.keys())  # both must have the key

    for key in all_keys:
        if key in numeric_keys:
            result[key] = lerp(float(a[key]), float(b[key]), t)
        elif key in int_keys:
            result[key] = lerp_int(int(a[key]), int(b[key]), t)
        elif key in bool_keys:
            result[key] = lerp_bool(bool(a[key]), bool(b[key]), t)
        else:
            # categorical: crossfade at 0.5
            result[key] = a[key] if t < 0.5 else b[key]

    return result


def blend_configs(
    a_dict: dict,
    b_dict: dict,
    t: float,
    schema: Dict[str, str],
) -> dict:
    """Blend two config dicts using a schema.

    Args:
        a_dict: config dict at t=0
        b_dict: config dict at t=1
        t: blend factor (0..1)
        schema: dict mapping key -> type string:
                "float", "int", "bool", or "categorical"
                (any other type defaults to categorical)

    Returns:
        new dict with blended values
    """
    numeric_keys = [k for k, v in schema.items() if v == "float"]
    int_keys = [k for k, v in schema.items() if v == "int"]
    bool_keys = [k for k, v in schema.items() if v == "bool"]

    return lerp_dict_values(a_dict, b_dict, t, numeric_keys, int_keys, bool_keys)


@dataclass
class BlendConfig:
    """Configuration for preset blending.

    Fields:
        enabled: master switch for blending (default False)
        blend_factor: blend value 0..1 (clamped)
        auto_animate: if True, blend_factor animates automatically
        animation_duration_s: duration of animation in seconds (0.01..60.0)
    """

    enabled: bool = False
    blend_factor: float = 0.0
    auto_animate: bool = False
    animation_duration_s: float = 1.0

    def __post_init__(self):
        """Enforce constraints."""
        self.blend_factor = max(0.0, min(1.0, self.blend_factor))
        self.animation_duration_s = max(0.01, min(60.0, self.animation_duration_s))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> BlendConfig:
        """Deserialize from dict."""
        return cls(
            enabled=d.get("enabled", False),
            blend_factor=d.get("blend_factor", 0.0),
            auto_animate=d.get("auto_animate", False),
            animation_duration_s=d.get("animation_duration_s", 1.0),
        )


@dataclass
class BlendAnimator:
    """Animate blend_factor over time.

    Tracks animation state: start time, initial factor, target factor, duration.
    Call set_target to start an animation, then call current(now_s) each frame.
    """

    cfg: BlendConfig = field(default_factory=BlendConfig)
    _start_time: Optional[float] = field(default=None, init=False)
    _start_factor: float = field(default=0.0, init=False)
    _target_factor: float = field(default=0.0, init=False)

    def set_target(self, target: float, now_s: float) -> None:
        """Begin animating to target factor.

        Args:
            target: blend factor to reach (clamped 0..1)
            now_s: current time in seconds
        """
        # Capture current value BEFORE changing _target_factor
        # (current() uses _target_factor for interpolation)
        self._start_factor = self.current(now_s)
        self._target_factor = max(0.0, min(1.0, target))
        self._start_time = now_s

    def current(self, now_s: float) -> float:
        """Get current blend factor at given time.

        If not animating, returns cfg.blend_factor.
        If animating, returns interpolated value.
        Settles at target when duration elapses.

        Args:
            now_s: current time in seconds

        Returns:
            current blend factor (0..1)
        """
        # Not animating
        if self._start_time is None:
            return self.cfg.blend_factor

        # Calculate animation progress
        elapsed = now_s - self._start_time
        progress = elapsed / self.cfg.animation_duration_s

        # Animation complete
        if progress >= 1.0:
            self.cfg.blend_factor = self._target_factor
            self._start_time = None
            return self._target_factor

        # Interpolate
        return lerp(self._start_factor, self._target_factor, progress)
