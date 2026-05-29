"""CC sweep / envelope automator: stateful generator producing CC values along
configurable envelopes (linear, exponential, logarithmic, sine, triangle, sawtooth)
over a duration. Fire "send CC74 from 0→127 over 2 seconds" from a button press.

Pure stdlib + math, no Qt, no global state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class CcSweepConfig:
    """Configuration for a CC sweep envelope."""
    enabled: bool = False
    cc: int = 1  # clamp 0..127
    channel: int = 1  # clamp 1..16
    start_value: int = 0  # clamp 0..127
    end_value: int = 127  # clamp 0..127
    duration_s: float = 1.0  # clamp 0.01..60.0
    shape: str = "linear"  # validate against allowed; unknown → "linear"
    loop: bool = False

    ALLOWED_SHAPES = {"linear", "exponential", "logarithmic", "sine", "triangle", "sawtooth"}

    def __post_init__(self):
        """Validate and clamp all fields to legal ranges."""
        self.enabled = bool(self.enabled)
        self.cc = max(0, min(127, int(self.cc)))
        self.channel = max(1, min(16, int(self.channel)))
        self.start_value = max(0, min(127, int(self.start_value)))
        self.end_value = max(0, min(127, int(self.end_value)))
        self.duration_s = max(0.01, min(60.0, float(self.duration_s)))
        self.loop = bool(self.loop)

        # Validate shape; fall back to "linear" if unknown.
        if self.shape not in self.ALLOWED_SHAPES:
            self.shape = "linear"
        else:
            self.shape = str(self.shape)

    def to_dict(self) -> dict:
        """Round-trip serialization to dict."""
        return {
            "enabled": self.enabled,
            "cc": self.cc,
            "channel": self.channel,
            "start_value": self.start_value,
            "end_value": self.end_value,
            "duration_s": self.duration_s,
            "shape": self.shape,
            "loop": self.loop,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> CcSweepConfig:
        """Deserialize from dict; missing keys use defaults."""
        if data is None:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            cc=data.get("cc", 1),
            channel=data.get("channel", 1),
            start_value=data.get("start_value", 0),
            end_value=data.get("end_value", 127),
            duration_s=data.get("duration_s", 1.0),
            shape=data.get("shape", "linear"),
            loop=data.get("loop", False),
        )


class CcSweep:
    """Stateful CC sweep engine: tracks start time, generates values along
    a configurable envelope shape, handles looping and completion state.
    """

    def __init__(self, cfg: CcSweepConfig):
        """Initialize with config. Does not start the sweep."""
        self.cfg = cfg
        self.start_time: Optional[float] = None
        self.last_value: Optional[int] = None
        self.done = False

    def start(self, now_s: float) -> None:
        """Stamp the start time and reset done state. Call before polling value_at()."""
        self.start_time = now_s
        self.done = False

    def value_at(self, now_s: float) -> Optional[int]:
        """Return current CC value (0..127), or None if not started.

        Once start() has been called, progress = (now_s - start_time) / duration_s.
        If progress >= 1.0 and not loop → set done = True.
        If loop → wrap progress with modulo.
        Apply shape function and linearly interpolate between start/end values.
        """
        if self.start_time is None:
            return None

        progress = (now_s - self.start_time) / self.cfg.duration_s

        # Handle loop and done state
        if progress >= 1.0:
            if not self.cfg.loop:
                self.done = True
            else:
                progress = progress % 1.0

        # Apply shape function to progress [0, 1]
        t = self._apply_shape(progress)

        # Linear interpolation between start and end
        value = self.cfg.start_value + (self.cfg.end_value - self.cfg.start_value) * t
        int_value = max(0, min(127, int(round(value))))

        self.last_value = int_value
        return int_value

    def _apply_shape(self, progress: float) -> float:
        """Apply shape function to progress value [0, 1] → [0, 1]."""
        progress = max(0.0, min(1.0, progress))  # Clamp to [0, 1]

        if self.cfg.shape == "linear":
            return progress
        elif self.cfg.shape == "exponential":
            return progress * progress
        elif self.cfg.shape == "logarithmic":
            return math.sqrt(progress)
        elif self.cfg.shape == "sine":
            # Ease-in-out sine: smooth ramp from 0 → 1
            return (1.0 - math.cos(progress * math.pi)) / 2.0
        elif self.cfg.shape == "triangle":
            # Peaks at progress=0.5, returns to 0 at progress=1.0
            if progress <= 0.5:
                return 2.0 * progress
            else:
                return 2.0 * (1.0 - progress)
        elif self.cfg.shape == "sawtooth":
            # Linear ramp each cycle (unless loop, always resets at progress=1)
            return progress
        else:
            # Fallback to linear (should not happen if __post_init__ is correct)
            return progress

    def is_done(self) -> bool:
        """Return True if sweep has completed (non-looping only)."""
        return self.done

    def reset(self) -> None:
        """Clear state: ready for a fresh start()."""
        self.start_time = None
        self.done = False
        self.last_value = None
