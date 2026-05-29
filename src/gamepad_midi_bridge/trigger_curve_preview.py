"""Pure-function sampler for trigger curve previews.

Generates sample arrays for UI sparkline rendering without Qt dependencies.
Each sampler produces a sequence of MIDI 7-bit CC values (0..127) that
represent the response curve of a particular trigger shaping mode.

All functions are pure and stdlib-only, suitable for offline rendering
or live preview generation during UI interaction.
"""
from __future__ import annotations

import math
from typing import List, Tuple


def sample_linear(
    samples: int = 32,
    min_value: int = 0,
    max_value: int = 127,
) -> List[int]:
    """Sample a linear ramp from min_value to max_value.

    Args:
        samples: Number of points to generate (default 32).
        min_value: Starting CC value (default 0).
        max_value: Ending CC value (default 127).

    Returns:
        List of `samples` integers, each in 0..127, linearly interpolated.
    """
    if samples <= 0:
        return []
    if samples == 1:
        return [max_value]

    result: List[int] = []
    for i in range(samples):
        t = i / (samples - 1)  # 0..1 across the range
        value = int(round(min_value + t * (max_value - min_value)))
        result.append(max(0, min(127, value)))

    return result


def sample_with_ceiling(
    samples: int = 32,
    ceiling: int = 80,
    max_value: int = 127,
) -> List[int]:
    """Sample a linear ramp that clips at a ceiling value.

    Models the "ceiling" trigger mode, where the output rises linearly
    but never exceeds the ceiling, even at full pressure.

    Args:
        samples: Number of points to generate (default 32).
        ceiling: CC value to cap output at (default 80).
        max_value: Ceiling position as fraction of full travel. Default 127
                   treats ceiling as an absolute MIDI value. If < 127, the
                   ramp reaches ceiling before the final sample.

    Returns:
        List of `samples` integers from 0 up to ceiling (inclusive).
    """
    if samples <= 0:
        return []

    # Clamp ceiling to 0..127 range
    cap = max(0, min(127, ceiling))

    result: List[int] = []
    for i in range(samples):
        t = i / (samples - 1) if samples > 1 else 0.0
        # Linear from 0 to cap
        value = int(round(t * cap))
        result.append(value)

    return result


def sample_inverted(
    samples: int = 32,
    min_value: int = 0,
    max_value: int = 127,
) -> List[int]:
    """Sample a descending ramp from max_value to min_value.

    Inverted trigger mode: rest position is high, full press is low.
    Useful for sustain-style controls.

    Args:
        samples: Number of points to generate (default 32).
        min_value: Ending CC value (default 0).
        max_value: Starting CC value (default 127).

    Returns:
        List of `samples` integers, descending from max to min.
    """
    if samples <= 0:
        return []
    if samples == 1:
        return [min_value]

    result: List[int] = []
    for i in range(samples):
        t = i / (samples - 1)
        # Descend from max to min
        value = int(round(max_value - t * (max_value - min_value)))
        result.append(max(0, min(127, value)))

    return result


def sample_latched(
    samples: int = 32,
    threshold: float = 0.5,
    low_value: int = 0,
    high_value: int = 127,
) -> List[int]:
    """Sample a latched/stepped curve with hysteresis.

    Footswitch-style toggle: below threshold is low, above is high.
    The threshold is positioned at threshold * samples, and includes
    5% hysteresis for a smooth transition visualization.

    Args:
        samples: Number of points to generate (default 32).
        threshold: Normalized position of the trigger point (0..1, default 0.5).
        low_value: CC value when inactive (default 0).
        high_value: CC value when active (default 127).

    Returns:
        List of `samples` integers, each either low_value or high_value.
    """
    if samples <= 0:
        return []

    t = max(0.0, min(1.0, threshold))
    # Position the transition at threshold * samples
    transition_idx = int(t * samples)

    result: List[int] = []
    for i in range(samples):
        if i < transition_idx:
            result.append(low_value)
        else:
            result.append(high_value)

    return result


def sample_bow(
    samples: int = 32,
    min_velocity: float = 0.1,
    max_velocity: float = 5.0,
) -> List[int]:
    """Sample a bow-expression curve (triangle-like envelope).

    Peaks in the middle and falls off at the very edges. Useful for
    modulating expression or velocity where the user expects subtle
    control in the middle and less effect at the extremes.

    Args:
        samples: Number of points to generate (default 32).
        min_velocity: Minimum output scaling (default 0.1, lower = quieter edges).
        max_velocity: Peak output scaling (default 5.0, higher = louder peak).

    Returns:
        List of `samples` integers, peaking near the middle.
    """
    if samples <= 0:
        return []

    result: List[int] = []
    for i in range(samples):
        # Normalize position across the range [0, 1]
        t = i / (samples - 1) if samples > 1 else 0.5

        # Triangle envelope: rises from 0 to 1 at t=0.5, then falls back to 0
        envelope = 1.0 - abs(t - 0.5) * 2.0  # 0 at edges, 1 at center

        # Scale envelope by velocity range
        scaled = min_velocity + envelope * (max_velocity - min_velocity)
        value = int(round(scaled * 25.4))  # Scale to ~0..127 (5.0 * 25.4 ≈ 127)
        result.append(max(0, min(127, value)))

    return result


def sample_crossfade(
    samples: int = 32,
    curve: float = 1.0,
) -> Tuple[List[int], List[int]]:
    """Sample two opposing crossfade curves from a single pressure.

    Generates (a_curve, b_curve) where a rises 0→127 and b falls 127→0
    as pressure increases. The curve exponent can bias one direction.

    Args:
        samples: Number of points to generate (default 32).
        curve: Response curve exponent (0.1..4.0, default 1.0).
               1.0 = linear crossfade.
               < 1.0 = logarithmic, biases high initially (eases in).
               > 1.0 = exponential, biases low initially (eases out).

    Returns:
        Tuple of (a_curve, b_curve), each a list of `samples` integers.
        At each position, a[i] + b[i] ≈ 127 (within rounding).
    """
    if samples <= 0:
        return ([], [])

    c = max(0.1, min(4.0, curve))
    a_curve: List[int] = []
    b_curve: List[int] = []

    for i in range(samples):
        t = i / (samples - 1) if samples > 1 else 0.5
        # Apply curve to pressure
        if c == 1.0:
            shaped_t = t
        else:
            shaped_t = t ** c

        # A rises, B falls
        a_value = int(round(shaped_t * 127.0))
        b_value = 127 - a_value

        a_curve.append(max(0, min(127, a_value)))
        b_curve.append(max(0, min(127, b_value)))

    return (a_curve, b_curve)


def sample_from_mode(
    mode: str = "linear",
    samples: int = 32,
    **kwargs,
) -> List[int]:
    """Dispatcher: sample a trigger curve based on mode string.

    Routes to the appropriate sampler function and returns the primary
    (or only) curve. Useful for UI code that needs to preview any trigger
    mode without knowing the exact sampler function name.

    Args:
        mode: Mode name ("linear", "ceiling", "inverted", "latch", "bow").
              Unknown modes default to linear.
        samples: Number of points to generate (default 32).
        **kwargs: Additional arguments passed to the sampler.
                  - ceiling (int, 0..127): for ceiling mode
                  - threshold (float, 0..1): for latch mode
                  - min_value, max_value (int): for linear/inverted
                  - min_velocity, max_velocity (float): for bow mode
                  - curve (float): for crossfade-like modes

    Returns:
        List of integers in 0..127 representing the curve.
    """
    mode_lower = mode.lower().strip()

    if mode_lower == "ceiling":
        ceiling = kwargs.get("ceiling", 80)
        return sample_with_ceiling(samples, ceiling)

    if mode_lower == "inverted":
        min_val = kwargs.get("min_value", 0)
        max_val = kwargs.get("max_value", 127)
        return sample_inverted(samples, min_val, max_val)

    if mode_lower == "latch":
        threshold = kwargs.get("threshold", 0.5)
        low = kwargs.get("low_value", 0)
        high = kwargs.get("high_value", 127)
        return sample_latched(samples, threshold, low, high)

    if mode_lower == "bow":
        min_vel = kwargs.get("min_velocity", 0.1)
        max_vel = kwargs.get("max_velocity", 5.0)
        return sample_bow(samples, min_vel, max_vel)

    # Default: linear
    min_val = kwargs.get("min_value", 0)
    max_val = kwargs.get("max_value", 127)
    return sample_linear(samples, min_val, max_val)
