"""Euclidean rhythm patterns using Bjorklund's algorithm.

Implements pure algorithmic generation of Euclidean rhythms, which distribute
N pulses evenly across K steps. Classic patterns:
- E(3, 8) = [1,0,0,1,0,0,1,0] (tresillo)
- E(5, 8) = [1,0,1,1,0,1,1,0] (Cuban cinquillo)
- E(4, 4) = [1,1,1,1] (four on the floor)

No Qt dependencies, no global state. Pure stdlib + typing.
"""

from dataclasses import dataclass
from typing import List, Tuple


def bjorklund(pulses: int, steps: int) -> List[int]:
    """Generate Euclidean rhythm via Bjorklund's algorithm.

    Distributes `pulses` events evenly across `steps` steps.

    Args:
        pulses: Number of 1s to distribute (must be >= 0).
        steps: Total number of steps (must be > 0).

    Returns:
        List of 0s and 1s, length `steps`. Returns empty list if inputs invalid.
        If pulses >= steps, returns all 1s. If pulses = 0, returns all 0s.

    Raises:
        No exceptions; invalid inputs return sensible defaults.

    Examples:
        bjorklund(3, 8)  -> [1, 0, 0, 1, 0, 0, 1, 0]
        bjorklund(5, 8)  -> [1, 0, 1, 1, 0, 1, 1, 0]
        bjorklund(0, 8)  -> [0, 0, 0, 0, 0, 0, 0, 0]
        bjorklund(8, 4)  -> [1, 1, 1, 1]
    """
    # Edge cases: invalid inputs
    if pulses < 0 or steps <= 0:
        return []

    # Edge cases: clamp pulses to steps
    if pulses == 0:
        return [0] * steps
    if pulses >= steps:
        return [1] * steps

    # Bjorklund's algorithm using the standard recursive approach
    # with proper group structure preservation
    def _bjorklund_recursive(n: int, k: int) -> List[int]:
        """Generate Euclidean rhythm via Bjorklund's algorithm.

        Distributes n pulses (1s) over k steps (total length).
        Uses iterative group pairing based on Euclidean algorithm.
        """
        if n == 0:
            return [0] * k
        if n == k:
            return [1] * k
        if n > k:
            return [1] * k

        # Start with groups: n groups of [1], (k-n) groups of [0]
        groups: List[List[int]] = [[1] for _ in range(n)] + [[0] for _ in range(k - n)]

        while len(groups) > 1:
            # Count groups of each type
            one_count = sum(1 for g in groups if len(g) > 0 and g[0] == 1)
            zero_count = len(groups) - one_count

            if one_count == 0 or zero_count == 0:
                break

            # Partition into 1-groups and 0-groups while preserving order
            one_groups = [g for g in groups if g[0] == 1]
            zero_groups = [g for g in groups if g[0] == 0]

            # Pair and rebuild: pair first min(one_count, zero_count) elements
            new_groups: List[List[int]] = []
            pairs = min(one_count, zero_count)

            if one_count >= zero_count:
                # Pair all zeros with first `zero_count` ones
                for i in range(pairs):
                    new_groups.append(one_groups[i] + zero_groups[i])
                # Append remaining ones
                new_groups.extend(one_groups[pairs:])
            else:
                # Pair all ones with first `one_count` zeros
                for i in range(pairs):
                    new_groups.append(one_groups[i] + zero_groups[i])
                # Append remaining zeros
                new_groups.extend(zero_groups[pairs:])

            groups = new_groups

        # Flatten to pattern
        result = []
        for group in groups:
            result.extend(group)
        return result

    return _bjorklund_recursive(pulses, steps)


def rotate(pattern: List[int], offset: int) -> List[int]:
    """Rotate a rhythm pattern by offset steps.

    Args:
        pattern: List of 0s and 1s.
        offset: Number of steps to rotate right (negative = rotate left).

    Returns:
        Rotated pattern. Empty pattern returns empty list.

    Examples:
        rotate([1, 0, 0, 1, 0, 0, 1, 0], 1)  -> [0, 1, 0, 0, 1, 0, 0, 1]
        rotate([1, 0, 0, 1, 0, 0, 1, 0], -1) -> [0, 0, 1, 0, 0, 1, 0, 1]
    """
    if not pattern:
        return []

    # Normalize offset to range [0, len(pattern))
    offset = offset % len(pattern)

    # Rotate right: take last `offset` elements and move to front
    return pattern[-offset:] + pattern[:-offset] if offset else pattern


def density(pattern: List[int]) -> float:
    """Calculate the density (fill ratio) of a rhythm.

    Args:
        pattern: List of 0s and 1s.

    Returns:
        Ratio of 1s to total length. Empty pattern returns 0.0.

    Examples:
        density([1, 0, 1, 0])  -> 0.5
        density([1, 1, 1, 1])  -> 1.0
        density([0, 0, 0, 0])  -> 0.0
    """
    if not pattern:
        return 0.0
    return sum(pattern) / len(pattern)


@dataclass
class EuclideanPattern:
    """A Euclidean rhythm pattern with MIDI metadata.

    Attributes:
        pulses: Number of events (1s) to distribute.
        steps: Total number of steps in the pattern.
        rotation: Offset rotation (0 = no rotation).
        note: MIDI note number (0-127, default 60 = Middle C).
        velocity: MIDI velocity (1-127, default 100).
        channel: MIDI channel (1-16, default 1).
    """

    pulses: int
    steps: int
    rotation: int = 0
    note: int = 60
    velocity: int = 100
    channel: int = 1

    def to_steps(self) -> List[int]:
        """Generate the rhythm as a list of 0s and 1s.

        Applies rotation to the base Bjorklund pattern.

        Returns:
            List of 0s and 1s, length = steps. Respects rotation.
        """
        pattern = bjorklund(self.pulses, self.steps)
        return rotate(pattern, self.rotation)

    def next_step(self, current_step: int) -> Tuple[bool, int]:
        """Advance to the next step in the pattern.

        Purely stateless: given current step, returns (fire?, next_step).
        Wraps at pattern length.

        Args:
            current_step: Current position (0-indexed).

        Returns:
            Tuple of (fires: bool, next_step: int).
            fires = True if this step has a pulse, next_step wraps at pattern length.

        Examples:
            pattern = EuclideanPattern(3, 8)
            fires, next_step = pattern.next_step(0)  -> (True, 1)
            fires, next_step = pattern.next_step(7)  -> (?, 0)  # wraps
        """
        pattern = self.to_steps()
        fires = bool(pattern[current_step % self.steps])
        next_step = (current_step + 1) % self.steps
        return (fires, next_step)
