"""Pure-function audio-reactive simulator for MIDI CC generation.

This module simulates audio-reactive MIDI CC output without capturing real audio.
Callers provide synthetic amplitude samples, and the simulator emits CC values based
on configurable envelope-follower, peak-hold, or direct-follow modes.

Features:
  - Direct-follow mode: output = input level (linear).
  - Peak-hold mode: output tracks peaks with decay over release_ms.
  - Envelope-follower mode: asymmetric rise/fall with attack_ms and release_ms.
  - Threshold: below threshold_level, output is minimum.
  - Gain: scale the signal before threshold and mapping.
  - Invert: flip the signal (1 - output).
  - CC mapping: scale output to [min_cc, max_cc] clamped 0..127.
  - Pure stdlib: No Qt, no real audio, deterministic and testable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AudioReactiveConfig:
    """Configuration for audio-reactive MIDI CC simulator.

    Attributes:
        enabled: Whether audio-reactive mode is active. If False, feed() returns min_cc.
        cc: MIDI CC number (0..127). Clamped on construction.
        channel: MIDI channel (1..16). Clamped on construction.
        mode: Reactivity mode ("follow", "peak_hold", "envelope").
              "follow": direct amplitude tracking.
              "peak_hold": track peaks with time-based decay.
              "envelope": envelope-follower with separate attack/release times.
              Unknown modes default to "follow". Case-insensitive.
        attack_ms: Attack time for envelope-follower (0.1..2000 ms).
                   Clamped on construction.
        release_ms: Release/decay time (1..10000 ms).
                    Clamped on construction.
        gain: Signal amplification factor (0.01..10.0).
              Clamped on construction.
        threshold: Below this level (0..1), output is min_cc.
                   Clamped on construction.
        invert: If True, output = 1 - processed_output (before mapping).
        min_cc: Minimum CC output value (0..127).
                Clamped on construction. Swapped with max_cc if > max_cc.
        max_cc: Maximum CC output value (0..127).
                Clamped on construction. Swapped with min_cc if < min_cc.
    """
    enabled: bool = False
    cc: int = 1
    channel: int = 1
    mode: str = "follow"
    attack_ms: float = 5.0
    release_ms: float = 100.0
    gain: float = 1.0
    threshold: float = 0.0
    invert: bool = False
    min_cc: int = 0
    max_cc: int = 127

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp cc to 0..127.
        self.cc = max(0, min(127, self.cc))

        # Clamp channel to 1..16.
        self.channel = max(1, min(16, self.channel))

        # Normalize mode to known values, default to "follow".
        mode_lower = self.mode.lower()
        if mode_lower in ("follow", "peak_hold", "envelope"):
            self.mode = mode_lower
        else:
            self.mode = "follow"

        # Clamp attack_ms to 0.1..2000.
        self.attack_ms = max(0.1, min(2000.0, self.attack_ms))

        # Clamp release_ms to 1..10000.
        self.release_ms = max(1.0, min(10000.0, self.release_ms))

        # Clamp gain to 0.01..10.
        self.gain = max(0.01, min(10.0, self.gain))

        # Clamp threshold to 0..1.
        self.threshold = max(0.0, min(1.0, self.threshold))

        # Clamp min_cc and max_cc to 0..127, and ensure min <= max.
        self.min_cc = max(0, min(127, self.min_cc))
        self.max_cc = max(0, min(127, self.max_cc))
        if self.min_cc > self.max_cc:
            self.min_cc, self.max_cc = self.max_cc, self.min_cc

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "cc": self.cc,
            "channel": self.channel,
            "mode": self.mode,
            "attack_ms": self.attack_ms,
            "release_ms": self.release_ms,
            "gain": self.gain,
            "threshold": self.threshold,
            "invert": self.invert,
            "min_cc": self.min_cc,
            "max_cc": self.max_cc,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AudioReactiveConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            cc=data.get("cc", 1),
            channel=data.get("channel", 1),
            mode=data.get("mode", "follow"),
            attack_ms=data.get("attack_ms", 5.0),
            release_ms=data.get("release_ms", 100.0),
            gain=data.get("gain", 1.0),
            threshold=data.get("threshold", 0.0),
            invert=data.get("invert", False),
            min_cc=data.get("min_cc", 0),
            max_cc=data.get("max_cc", 127),
        )


class AudioReactiveSim:
    """Stateful audio-reactive MIDI CC simulator.

    Accepts synthetic audio samples and emits CC values based on envelope-follower,
    peak-hold, or direct-follow logic.
    """

    def __init__(self, cfg: AudioReactiveConfig) -> None:
        """Initialize simulator with config.

        Args:
            cfg: AudioReactiveConfig describing reactivity mode and parameters.
        """
        self.cfg = cfg
        self._env: float = 0.0  # Envelope state (for envelope-follower mode).
        self._peak: float = 0.0  # Peak state (for peak-hold mode).
        self._peak_set_at: Optional[float] = None  # Time peak was last set.

    def feed(self, level: float, now_s: float) -> int:
        """Feed a synthetic audio level sample and return MIDI CC value.

        Args:
            level: Audio amplitude (nominally 0..1; clamped here).
            now_s: Current time in seconds (for envelope and peak timing).

        Returns:
            MIDI CC value (0..127). If not enabled, returns min_cc.
        """
        # Clamp input level to 0..1.
        level = max(0.0, min(1.0, level))

        # If not enabled, return min_cc.
        if not self.cfg.enabled:
            return self.cfg.min_cc

        # Apply gain.
        processed = level * self.cfg.gain
        processed = max(0.0, min(1.0, processed))  # Clamp after gain.

        # Apply threshold: if below threshold, output is 0.
        if processed < self.cfg.threshold:
            processed = 0.0

        # Compute output based on mode.
        if self.cfg.mode == "peak_hold":
            processed = self._apply_peak_hold(processed, now_s)
        elif self.cfg.mode == "envelope":
            processed = self._apply_envelope(processed, now_s)
        # else: "follow" mode, processed is already set.

        # Apply invert.
        if self.cfg.invert:
            processed = 1.0 - processed

        # Clamp to 0..1.
        processed = max(0.0, min(1.0, processed))

        # Map to [min_cc, max_cc].
        cc_value = self._map_to_cc(processed)

        return cc_value

    def _apply_peak_hold(self, level: float, now_s: float) -> float:
        """Peak-hold logic: track peaks, decay over release_ms.

        Args:
            level: Current processed level (0..1).
            now_s: Current time in seconds.

        Returns:
            Output level (0..1).
        """
        # If new level exceeds peak, update peak.
        if level > self._peak:
            self._peak = level
            self._peak_set_at = now_s
        # Else, decay peak over release_ms.
        elif self._peak_set_at is not None:
            elapsed_ms = (now_s - self._peak_set_at) * 1000.0
            if elapsed_ms > self.cfg.release_ms:
                # Exponential decay: multiply by 0.95 per sample.
                # (In production, this might be time-constant-based, but 0.95x per
                # sample is a reasonable heuristic.)
                self._peak *= 0.95
                # Reset decay timer so next decay applies after another release_ms.
                self._peak_set_at = now_s

        return self._peak

    def _apply_envelope(self, level: float, now_s: float) -> float:
        """Envelope-follower logic: attack with attack_ms, release with release_ms.

        Uses one-pole exponential smoothing with separate time constants.

        Args:
            level: Current processed level (0..1).
            now_s: Current time in seconds.

        Returns:
            Smoothed envelope level (0..1).
        """
        # On first sample, initialize envelope to level.
        if self._env == 0.0 and level > 0.0:
            self._env = level
            self._peak_set_at = now_s
            return self._env

        if self._peak_set_at is None:
            self._peak_set_at = now_s

        # Compute time since last update (dt in seconds).
        dt_s = now_s - self._peak_set_at
        self._peak_set_at = now_s

        # Choose time constant based on direction.
        if level > self._env:
            # Rising: use attack_ms.
            tau_s = self.cfg.attack_ms / 1000.0
        else:
            # Falling: use release_ms.
            tau_s = self.cfg.release_ms / 1000.0

        # One-pole exponential smoothing:
        # env += (level - env) * (1 - exp(-dt / tau))
        if tau_s > 0:
            alpha = 1.0 - math.exp(-dt_s / tau_s)
        else:
            alpha = 1.0  # Shouldn't happen, but handle it.

        self._env = self._env + (level - self._env) * alpha

        return self._env

    def _map_to_cc(self, processed: float) -> int:
        """Map normalized level (0..1) to CC range [min_cc, max_cc].

        Args:
            processed: Normalized level (0..1).

        Returns:
            CC value (0..127).
        """
        # Linear interpolation: cc = min_cc + processed * (max_cc - min_cc).
        cc_float = self.cfg.min_cc + processed * (self.cfg.max_cc - self.cfg.min_cc)
        cc_int = int(round(cc_float))

        # Clamp to 0..127.
        cc_int = max(0, min(127, cc_int))

        return cc_int

    def reset(self) -> None:
        """Reset simulator state.

        Clears envelope, peak, and timing state so the next feed() starts fresh.
        """
        self._env = 0.0
        self._peak = 0.0
        self._peak_set_at = None
