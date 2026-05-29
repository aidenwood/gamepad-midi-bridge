"""Pure-function DualSense IMU (gyro / accelerometer) → CC mapper with smoothing + gain.

This module provides motion sensor sample processing for DualSense gyroscope and
accelerometer inputs, mapping raw motion values onto MIDI CC outputs with
per-axis smoothing, gain control, deadzone suppression, and optional inversion.

Features:
  - Per-axis configuration: gyro (x, y, z) and accel (x, y, z).
  - Gain control: Amplify raw motion (0.01..100x).
  - One-pole smoothing: Suppress jitter (0..0.99 blend factor).
  - Deadzone: Treat small values as zero (0..1 raw magnitude).
  - Bipolar/unipolar modes: -1..+1 (bipolar) or 0..1 (unipolar) → 0..127.
  - Invert per-axis: Flip sign before output.
  - Pure stdlib: No Qt, no hardware reads; caller supplies raw floats.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ImuAxisConfig:
    """Configuration for a single IMU axis (gyro or accel component).

    Attributes:
        enabled: Whether this axis is active. If False, feed() returns None.
        cc: MIDI CC number (0..127). Clamped on construction.
        channel: MIDI channel (1..16). Clamped on construction.
        gain: Linear amplifier on raw input (0.01..100). Clamped on construction.
               1.0 = no amplification. >1 = boost signal.
        invert: If True, negate raw value after gain before smoothing.
        smoothing: One-pole smoothing factor (0..0.99). Clamped on construction.
                  0.0 = no smoothing (direct passthrough).
                  0.99 = max smoothing (very sluggish).
                  Blending: _smoothed = _smoothed * smoothing + raw * (1 - smoothing).
        deadzone: Suppress small values (0..1 raw magnitude). Clamped on construction.
                 If abs(raw) <= deadzone, treat as 0.
        bipolar: If True, raw range is -1..+1 mapped to CC 0..127 (mid=64).
                If False, raw range is 0..1 mapped to CC 0..127.
    """
    enabled: bool = False
    cc: int = 1
    channel: int = 1
    gain: float = 1.0
    invert: bool = False
    smoothing: float = 0.3
    deadzone: float = 0.05
    bipolar: bool = True

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp cc to 0..127.
        self.cc = max(0, min(127, self.cc))

        # Clamp channel to 1..16.
        self.channel = max(1, min(16, self.channel))

        # Clamp gain to 0.01..100.
        self.gain = max(0.01, min(100.0, self.gain))

        # Clamp smoothing to 0..0.99.
        self.smoothing = max(0.0, min(0.99, self.smoothing))

        # Clamp deadzone to 0..1.
        self.deadzone = max(0.0, min(1.0, self.deadzone))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "cc": self.cc,
            "channel": self.channel,
            "gain": self.gain,
            "invert": self.invert,
            "smoothing": self.smoothing,
            "deadzone": self.deadzone,
            "bipolar": self.bipolar,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ImuAxisConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            cc=data.get("cc", 1),
            channel=data.get("channel", 1),
            gain=data.get("gain", 1.0),
            invert=data.get("invert", False),
            smoothing=data.get("smoothing", 0.3),
            deadzone=data.get("deadzone", 0.05),
            bipolar=data.get("bipolar", True),
        )


@dataclass
class ImuMappingConfig:
    """Configuration for all 6 IMU axes (3 gyro + 3 accel).

    Attributes:
        enabled: Master enable for IMU processing.
        gyro_x, gyro_y, gyro_z: Gyroscope axes (rotation rate).
        accel_x, accel_y, accel_z: Accelerometer axes (linear acceleration).
    """
    enabled: bool = False
    gyro_x: ImuAxisConfig = field(default_factory=ImuAxisConfig)
    gyro_y: ImuAxisConfig = field(default_factory=ImuAxisConfig)
    gyro_z: ImuAxisConfig = field(default_factory=ImuAxisConfig)
    accel_x: ImuAxisConfig = field(default_factory=ImuAxisConfig)
    accel_y: ImuAxisConfig = field(default_factory=ImuAxisConfig)
    accel_z: ImuAxisConfig = field(default_factory=ImuAxisConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "gyro_x": self.gyro_x.to_dict(),
            "gyro_y": self.gyro_y.to_dict(),
            "gyro_z": self.gyro_z.to_dict(),
            "accel_x": self.accel_x.to_dict(),
            "accel_y": self.accel_y.to_dict(),
            "accel_z": self.accel_z.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ImuMappingConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. Nested ImuAxisConfig
        objects use their own from_dict for reconstruction.
        """
        return cls(
            enabled=data.get("enabled", False),
            gyro_x=ImuAxisConfig.from_dict(data.get("gyro_x", {})),
            gyro_y=ImuAxisConfig.from_dict(data.get("gyro_y", {})),
            gyro_z=ImuAxisConfig.from_dict(data.get("gyro_z", {})),
            accel_x=ImuAxisConfig.from_dict(data.get("accel_x", {})),
            accel_y=ImuAxisConfig.from_dict(data.get("accel_y", {})),
            accel_z=ImuAxisConfig.from_dict(data.get("accel_z", {})),
        )


class ImuAxisProcessor:
    """Stateful processor for a single IMU axis.

    Applies deadzone suppression, gain, inversion, one-pole smoothing,
    and bipolar/unipolar mapping to output CC values (0..127).
    """

    def __init__(self, cfg: ImuAxisConfig) -> None:
        """Initialize axis processor with config.

        Args:
            cfg: ImuAxisConfig describing the axis behavior.
        """
        self.cfg = cfg
        self._smoothed: float = 0.0

    def feed(self, raw: float) -> Optional[int]:
        """Feed a raw motion sample through the axis processor.

        Args:
            raw: Raw motion value (typically -1..+1 for gyro, -1..+1 for accel,
                 but unbounded floats are accepted).

        Returns:
            CC value (0..127) if axis is enabled, or None if disabled.
        """
        # If not enabled, return None.
        if not self.cfg.enabled:
            return None

        # Apply deadzone: if magnitude is below threshold, treat as zero.
        if abs(raw) <= self.cfg.deadzone:
            raw = 0.0

        # Apply gain.
        raw_g = raw * self.cfg.gain

        # Apply invert.
        if self.cfg.invert:
            raw_g = -raw_g

        # One-pole smoothing.
        self._smoothed = self._smoothed * self.cfg.smoothing + raw_g * (1.0 - self.cfg.smoothing)

        # Map to CC 0..127.
        if self.cfg.bipolar:
            # Bipolar mode: clamp to -1..+1, map to 0..127 with mid=64.
            smoothed_clamped = max(-1.0, min(1.0, self._smoothed))
            # Map -1..+1 to 0..127: (s + 1) * 63.5, clamp to 0..127.
            cc_value = round((smoothed_clamped + 1.0) * 63.5)
            cc_value = max(0, min(127, cc_value))
        else:
            # Unipolar mode: clamp to 0..1, map to 0..127.
            smoothed_clamped = max(0.0, min(1.0, self._smoothed))
            cc_value = round(smoothed_clamped * 127.0)
            cc_value = max(0, min(127, cc_value))

        return cc_value

    def reset(self) -> None:
        """Reset the smoothed state to 0.

        Next feed() will apply smoothing from a clean slate.
        """
        self._smoothed = 0.0


class ImuMapping:
    """Stateful processor for all 6 IMU axes (gyro + accel).

    Maintains 6 ImuAxisProcessor instances and orchestrates batch processing.
    """

    def __init__(self, cfg: ImuMappingConfig) -> None:
        """Initialize IMU mapping with config.

        Args:
            cfg: ImuMappingConfig describing all 6 axes.
        """
        self.cfg = cfg
        self._gyro_x = ImuAxisProcessor(cfg.gyro_x)
        self._gyro_y = ImuAxisProcessor(cfg.gyro_y)
        self._gyro_z = ImuAxisProcessor(cfg.gyro_z)
        self._accel_x = ImuAxisProcessor(cfg.accel_x)
        self._accel_y = ImuAxisProcessor(cfg.accel_y)
        self._accel_z = ImuAxisProcessor(cfg.accel_z)

    def process(
        self,
        gyro: Tuple[float, float, float],
        accel: Tuple[float, float, float],
    ) -> List[Tuple[int, int, int]]:
        """Process gyro and accel samples, returning CC tuples for enabled axes.

        Args:
            gyro: (gx, gy, gz) gyroscope rotation rates.
            accel: (ax, ay, az) accelerometer linear accelerations.

        Returns:
            List of (cc, channel, value) tuples for each enabled axis that
            produced a non-None value. Empty list if master enabled=False or
            all axes are disabled.
        """
        if not self.cfg.enabled:
            return []

        results = []

        # Process gyro axes.
        gx_cc = self._gyro_x.feed(gyro[0])
        if gx_cc is not None:
            results.append((self.cfg.gyro_x.cc, self.cfg.gyro_x.channel, gx_cc))

        gy_cc = self._gyro_y.feed(gyro[1])
        if gy_cc is not None:
            results.append((self.cfg.gyro_y.cc, self.cfg.gyro_y.channel, gy_cc))

        gz_cc = self._gyro_z.feed(gyro[2])
        if gz_cc is not None:
            results.append((self.cfg.gyro_z.cc, self.cfg.gyro_z.channel, gz_cc))

        # Process accel axes.
        ax_cc = self._accel_x.feed(accel[0])
        if ax_cc is not None:
            results.append((self.cfg.accel_x.cc, self.cfg.accel_x.channel, ax_cc))

        ay_cc = self._accel_y.feed(accel[1])
        if ay_cc is not None:
            results.append((self.cfg.accel_y.cc, self.cfg.accel_y.channel, ay_cc))

        az_cc = self._accel_z.feed(accel[2])
        if az_cc is not None:
            results.append((self.cfg.accel_z.cc, self.cfg.accel_z.channel, az_cc))

        return results

    def reset(self) -> None:
        """Reset all 6 axis processors.

        Clears smoothing state on all axes for a clean slate.
        """
        self._gyro_x.reset()
        self._gyro_y.reset()
        self._gyro_z.reset()
        self._accel_x.reset()
        self._accel_y.reset()
        self._accel_z.reset()
