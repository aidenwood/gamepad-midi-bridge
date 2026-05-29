"""Sustain pedal emulator — hold a button to emit CC values on trigger axes.

A button (or trigger) can be configured to emit a CC (control change) message
at a "pressed" value (e.g. 127 for sustain) while held, and return to a
"released" value (e.g. 0) on release.

Supports:
  - Momentary mode: CC is on while button is held.
  - Latch mode: Each press toggles the CC state.
  - Half-pedal: Analog triggers can be gated by a pressure threshold.
  - Standard MIDI pedal CCs: sustain (64), sostenuto (66), soft (67), etc.

No Qt dependencies — pure stdlib + dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


PEDAL_PRESETS: dict[str, int] = {
    "sustain": 64,
    "sostenuto": 66,
    "soft": 67,
    "legato": 68,
    "hold2": 69,
    "expression": 11,
}


def _clamp(value: int | float, minimum: int | float, maximum: int | float) -> int | float:
    """Clamp a value to [minimum, maximum]."""
    return max(minimum, min(maximum, value))


@dataclass
class SustainPedalConfig:
    """Configuration for a sustain pedal emulator."""

    enabled: bool = False
    cc: int = 64
    channel: int = 1
    pressed_value: int = 127
    released_value: int = 0
    half_pedal_threshold: float = 0.5
    latch: bool = False

    def __post_init__(self) -> None:
        """Clamp all numeric values to valid MIDI ranges."""
        self.cc = int(_clamp(self.cc, 0, 127))
        self.channel = int(_clamp(self.channel, 1, 16))
        self.pressed_value = int(_clamp(self.pressed_value, 0, 127))
        self.released_value = int(_clamp(self.released_value, 0, 127))
        self.half_pedal_threshold = float(_clamp(self.half_pedal_threshold, 0.0, 1.0))

    def to_dict(self) -> dict:
        """Serialize to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SustainPedalConfig:
        """Deserialize from a dictionary."""
        return cls(**data)


class SustainPedal:
    """Sustain pedal state machine — tracks pressure and emits CC values."""

    def __init__(self, cfg: SustainPedalConfig) -> None:
        """Initialize with a config."""
        self.cfg = cfg
        self._is_held = False
        self._latched_on = False

    def update(self, pressure_0_1: float) -> Optional[int]:
        """
        Update the pedal with the latest pressure reading (0.0 to 1.0).

        Returns a CC value (pressed_value or released_value) if a transition
        occurred and should be sent, or None if nothing changed.

        Args:
            pressure_0_1: Normalized pressure in [0.0, 1.0].

        Returns:
            A CC value (0–127) to send, or None if no change.
        """
        threshold = (
            self.cfg.half_pedal_threshold
            if self.cfg.half_pedal_threshold > 0
            else 0
        )
        is_pressed = pressure_0_1 > threshold

        old_held = self._is_held
        self._is_held = is_pressed

        if self.cfg.latch:
            # Latch mode: toggle on press-down transition, no output on hold.
            if not old_held and is_pressed:
                # Transition from not-held to held: toggle latch state
                self._latched_on = not self._latched_on
                return (
                    self.cfg.pressed_value
                    if self._latched_on
                    else self.cfg.released_value
                )
            return None
        else:
            # Momentary mode: output on any transition.
            if old_held != is_pressed:
                return (
                    self.cfg.pressed_value
                    if is_pressed
                    else self.cfg.released_value
                )
            return None

    def force_release(self) -> int:
        """
        Force the pedal to the released state immediately.

        Used during panic (all-notes-off) or preset changes.
        Returns the released_value.
        """
        self._is_held = False
        self._latched_on = False
        return self.cfg.released_value

    def is_active(self) -> bool:
        """
        Return whether the sustain effect should be active right now.

        In latch mode, this reflects the latched state.
        In momentary mode, this reflects whether the button is held.
        """
        if self.cfg.latch:
            return self._latched_on
        return self._is_held
