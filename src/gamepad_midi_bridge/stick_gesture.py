"""Stick gesture detector for identifying joystick motions.

Pure stdlib module for detecting common stick gestures: swipes (up, down, left, right)
and circular motions (clockwise, counter-clockwise). Samples stick position over time,
accumulates angle change for circles, and fires a gesture name once when detected.

Gesture types:
  - "swipe_up": fast upward movement (high positive Y displacement)
  - "swipe_down": fast downward movement (high negative Y displacement)
  - "swipe_left": fast leftward movement (high negative X displacement)
  - "swipe_right": fast rightward movement (high positive X displacement)
  - "circle_cw": circular motion with accumulated positive angle
  - "circle_ccw": circular motion with accumulated negative angle
"""

import math
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple


Gesture = str  # "swipe_up", "swipe_down", "swipe_left", "swipe_right", "circle_cw", "circle_ccw"


@dataclass
class StickGestureConfig:
    """Configuration for stick gesture detection.

    Attributes:
        enabled: Whether gesture detection is active.
        swipe_min_magnitude: Minimum displacement magnitude to fire a swipe (0.1..2.0).
                             Default 0.7: stick must move 70% distance to trigger.
        swipe_max_duration_s: Maximum seconds for a swipe to complete (0.05..5.0).
                              Default 0.5: swipe must happen within 500ms.
        circle_min_arc: Minimum accumulated angle (radians) to fire a circle (1.0..20.0).
                        Default 5.5: ~5.5 rad (≈315°) allows strong-but-not-full circle.
                        2π ≈ 6.28 rad (full circle).
        circle_max_duration_s: Maximum seconds for a circle to complete (0.1..10.0).
                               Default 2.0: circle must complete within 2 seconds.
        min_radius: Minimum stick magnitude during circle to count (0.05..1.0).
                    Default 0.3: stick must be at least 30% extended during circle.
        max_history: Maximum samples to retain in history (4..256).
                     Default 64: keeps last ~64 samples (at 60Hz ≈ 1 second).
    """

    enabled: bool = False
    swipe_min_magnitude: float = 0.7
    swipe_max_duration_s: float = 0.5
    circle_min_arc: float = 5.5
    circle_max_duration_s: float = 2.0
    min_radius: float = 0.3
    max_history: int = 64

    def __post_init__(self) -> None:
        """Clamp all numeric values to their valid ranges."""
        self.swipe_min_magnitude = max(0.1, min(2.0, self.swipe_min_magnitude))
        self.swipe_max_duration_s = max(0.05, min(5.0, self.swipe_max_duration_s))
        self.circle_min_arc = max(1.0, min(20.0, self.circle_min_arc))
        self.circle_max_duration_s = max(0.1, min(10.0, self.circle_max_duration_s))
        self.min_radius = max(0.05, min(1.0, self.min_radius))
        self.max_history = max(4, min(256, self.max_history))

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with all config fields.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "StickGestureConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with config fields.

        Returns:
            StickGestureConfig instance with validated values.

        Examples:
            >>> config = StickGestureConfig.from_dict(
            ...     {"enabled": True, "swipe_min_magnitude": 0.5}
            ... )
            >>> config.enabled
            True
        """
        return StickGestureConfig(
            enabled=data.get("enabled", False),
            swipe_min_magnitude=data.get("swipe_min_magnitude", 0.7),
            swipe_max_duration_s=data.get("swipe_max_duration_s", 0.5),
            circle_min_arc=data.get("circle_min_arc", 5.5),
            circle_max_duration_s=data.get("circle_max_duration_s", 2.0),
            min_radius=data.get("min_radius", 0.3),
            max_history=data.get("max_history", 64),
        )


class StickGestureDetector:
    """Stick gesture detector for identifying joystick motions.

    Accumulates a history of stick samples (timestamp, x, y) and analyzes recent
    motion to detect swipes and circles. Returns gesture name once when detected,
    then prunes history to prevent re-triggering on the same motion.

    Attributes:
        cfg: StickGestureConfig instance.
        _history: List of (timestamp, x, y) tuples.
    """

    def __init__(self, cfg: StickGestureConfig) -> None:
        """Initialize gesture detector.

        Args:
            cfg: StickGestureConfig instance.
        """
        self.cfg = cfg
        self._history: List[Tuple[float, float, float]] = []

    def sample(self, x: float, y: float, now_s: float) -> Optional[Gesture]:
        """Sample stick position and detect gesture.

        Appends (now_s, x, y) to history, then checks for matching gestures.
        Returns gesture name once when detected; returns None otherwise.
        After firing a gesture, clears history to prevent re-triggering.

        Args:
            x: Stick X position (normalized -1.0 to 1.0).
            y: Stick Y position (normalized -1.0 to 1.0).
            now_s: Current time in seconds (monotonic, e.g. time.monotonic()).

        Returns:
            Gesture name ("swipe_up", "swipe_down", "swipe_left", "swipe_right",
            "circle_cw", "circle_ccw") if detected, None otherwise.

        Examples:
            >>> cfg = StickGestureConfig(enabled=True)
            >>> detector = StickGestureDetector(cfg)
            >>> detector.sample(0.0, 0.0, 0.0)  # Start at origin
            >>> detector.sample(0.0, 1.0, 0.1)  # Swipe up
            'swipe_up'
        """
        # Append new sample
        self._history.append((now_s, x, y))

        # Trim history to max_history
        if len(self._history) > self.cfg.max_history:
            self._history = self._history[-self.cfg.max_history :]

        # Check for gestures
        gesture = self._detect_gesture(now_s)

        # If gesture detected, clear history to prevent re-fire
        if gesture is not None:
            self._history.clear()

        return gesture

    def _detect_gesture(self, now_s: float) -> Optional[Gesture]:
        """Detect gesture from current history.

        Checks for swipes (displacement-based) and circles (angle-based) in
        recent history within configured time windows.

        Args:
            now_s: Current time in seconds.

        Returns:
            Gesture name if detected, None otherwise.
        """
        if len(self._history) < 2:
            return None

        # Check for swipes first (faster, more responsive)
        swipe = self._detect_swipe(now_s)
        if swipe is not None:
            return swipe

        # Check for circles
        circle = self._detect_circle(now_s)
        if circle is not None:
            return circle

        return None

    def _detect_swipe(self, now_s: float) -> Optional[Gesture]:
        """Detect swipe gesture from recent displacement.

        Scans history for a sample within swipe_max_duration_s where the
        displacement magnitude from current position exceeds swipe_min_magnitude.
        Classifies direction by dominant axis: Y → up/down, X → left/right.

        Args:
            now_s: Current time in seconds.

        Returns:
            Gesture name ("swipe_up", "swipe_down", "swipe_left", "swipe_right")
            or None.
        """
        now_x, now_y = self._history[-1][1], self._history[-1][2]

        for past_idx in range(len(self._history) - 1):
            past_t, past_x, past_y = self._history[past_idx]
            dt = now_s - past_t

            # Only consider samples within swipe_max_duration_s
            if dt > self.cfg.swipe_max_duration_s:
                continue

            # Calculate displacement
            dx = now_x - past_x
            dy = now_y - past_y
            magnitude = math.sqrt(dx * dx + dy * dy)

            # Check if magnitude exceeds threshold
            if magnitude >= self.cfg.swipe_min_magnitude:
                # Classify by dominant axis
                if abs(dy) > abs(dx):
                    # Dominant: vertical
                    return "swipe_up" if dy > 0 else "swipe_down"
                else:
                    # Dominant: horizontal
                    return "swipe_right" if dx > 0 else "swipe_left"

        return None

    def _detect_circle(self, now_s: float) -> Optional[Gesture]:
        """Detect circle gesture from accumulated angle.

        Scans history within circle_max_duration_s, computing cumulative angle
        change between consecutive samples where both have magnitude >= min_radius.
        If |cumulative_angle| >= circle_min_arc, returns circle_cw (positive) or
        circle_ccw (negative).

        Args:
            now_s: Current time in seconds.

        Returns:
            Gesture name ("circle_cw", "circle_ccw") or None.
        """
        # Filter history to recent samples within circle_max_duration_s
        recent = [
            (t, x, y)
            for t, x, y in self._history
            if now_s - t <= self.cfg.circle_max_duration_s
        ]

        if len(recent) < 2:
            return None

        # Accumulate angle change
        cumulative_angle = 0.0

        for i in range(1, len(recent)):
            prev_t, prev_x, prev_y = recent[i - 1]
            curr_t, curr_x, curr_y = recent[i]

            # Both samples must have sufficient radius
            prev_mag = math.sqrt(prev_x * prev_x + prev_y * prev_y)
            curr_mag = math.sqrt(curr_x * curr_x + curr_y * curr_y)

            if prev_mag < self.cfg.min_radius or curr_mag < self.cfg.min_radius:
                continue

            # Compute angle at each point
            prev_angle = math.atan2(prev_y, prev_x)
            curr_angle = math.atan2(curr_y, curr_x)

            # Compute delta, handling wrap-around at ±π
            delta = curr_angle - prev_angle
            if delta > math.pi:
                delta -= 2 * math.pi
            elif delta < -math.pi:
                delta += 2 * math.pi

            cumulative_angle += delta

        # Check if cumulative angle exceeds threshold
        if abs(cumulative_angle) >= self.cfg.circle_min_arc:
            return "circle_cw" if cumulative_angle > 0 else "circle_ccw"

        return None

    def reset(self) -> None:
        """Clear history.

        Useful for cleanup between sessions or on controller disconnect.
        """
        self._history.clear()

    def pending_history_size(self) -> int:
        """Return number of samples currently in history.

        Returns:
            Length of internal history buffer.

        Examples:
            >>> detector = StickGestureDetector(StickGestureConfig())
            >>> detector.sample(0, 0, 0.0)
            >>> detector.sample(0.5, 0.5, 0.1)
            >>> detector.pending_history_size()
            2
        """
        return len(self._history)
