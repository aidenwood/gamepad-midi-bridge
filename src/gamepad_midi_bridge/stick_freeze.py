"""Stick-freeze latch for locking joystick values during movement.

Pure stdlib module for freezing and unfreezing stick CC values. Allows a button
to be configured to lock the current stick position so the physical stick can move
without sending MIDI updates, then unlock to resume sending. Useful for setting
a filter cutoff exactly and then locking it in place.

Freeze modes:
  - "toggle": button release (press → not pressed) flips freeze on/off
  - "hold": freeze state mirrors button state directly (pressed = frozen)
"""

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple


@dataclass
class StickFreezeConfig:
    """Configuration for stick freeze / latch behaviour.

    Attributes:
        enabled: Whether stick freeze is active.
        freeze_button: Button index that toggles freeze (None = inactive).
        freeze_mode: How freeze state is controlled ("toggle" or "hold";
                     unknown → "toggle").
        feedback_haptic: Whether to signal haptic feedback on state change.
                         Pure flag; does not trigger haptics in this module.
    """

    enabled: bool = False
    freeze_button: Optional[int] = None
    freeze_mode: str = "toggle"
    feedback_haptic: bool = True

    def __post_init__(self) -> None:
        """Validate and normalise config values."""
        # Normalise freeze_mode: unknown → "toggle"
        if self.freeze_mode not in ("toggle", "hold"):
            self.freeze_mode = "toggle"

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: enabled, freeze_button, freeze_mode, feedback_haptic.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "StickFreezeConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with keys: enabled, freeze_button, freeze_mode, feedback_haptic.

        Returns:
            StickFreezeConfig instance with validated values.

        Examples:
            >>> config = StickFreezeConfig.from_dict(
            ...     {"enabled": True, "freeze_button": 5, "freeze_mode": "toggle"}
            ... )
            >>> config.freeze_button
            5
        """
        return StickFreezeConfig(
            enabled=data.get("enabled", False),
            freeze_button=data.get("freeze_button"),
            freeze_mode=data.get("freeze_mode", "toggle"),
            feedback_haptic=data.get("feedback_haptic", True),
        )


class StickFreeze:
    """Stick freeze / latch controller.

    Manages freezing and unfreezing of stick CC values. When frozen, the stick
    returns the last stashed position regardless of physical movement.

    Attributes:
        cfg: StickFreezeConfig instance.
        _frozen: Current freeze state.
        _frozen_value: Stashed (x, y) position when frozen; None if not frozen.
        _button_was_pressed: Tracks previous button state for toggle mode.
    """

    def __init__(self, cfg: StickFreezeConfig) -> None:
        """Initialize stick freeze controller.

        Args:
            cfg: StickFreezeConfig instance.
        """
        self.cfg = cfg
        self._frozen = False
        self._frozen_value: Optional[Tuple[float, float]] = None
        self._button_was_pressed = False

    def update_button(self, button_state: bool) -> bool:
        """Update button state and return True if freeze state changed (for haptic feedback).

        In toggle mode: fires on button release (pressed → not pressed) transition.
        In hold mode: fires if button_state differs from _frozen.

        Args:
            button_state: Current button pressed state (True = pressed, False = released).

        Returns:
            True if a state change occurred that should trigger haptic feedback.

        Examples:
            >>> cfg = StickFreezeConfig(enabled=True, freeze_button=5, freeze_mode="toggle")
            >>> sf = StickFreeze(cfg)
            >>> sf.update_button(True)  # Button pressed
            False
            >>> sf.update_button(False)  # Button released — toggles freeze
            True
            >>> sf.is_frozen()
            True
        """
        if self.cfg.freeze_mode == "hold":
            # Hold mode: freeze state = button state
            old_frozen = self._frozen
            self._frozen = button_state
            state_changed = old_frozen != self._frozen
        else:  # toggle
            # Toggle mode: transition on button release (was pressed, now not pressed)
            state_changed = False
            if self._button_was_pressed and not button_state:
                # Button was released — toggle freeze
                self._frozen = not self._frozen
                state_changed = True

        self._button_was_pressed = button_state
        return state_changed

    def filter_stick(self, x: float, y: float) -> Tuple[float, float]:
        """Filter stick input; return frozen value if frozen, else stash and return input.

        Args:
            x: Raw stick X value (normalized to [-1, 1]).
            y: Raw stick Y value (normalized to [-1, 1]).

        Returns:
            (x, y) tuple: frozen value if frozen, else the input (x, y).
        """
        if self._frozen and self._frozen_value is not None:
            # Return the stashed frozen value
            return self._frozen_value

        # Not frozen — stash the new value and return it
        self._frozen_value = (x, y)
        return (x, y)

    def is_frozen(self) -> bool:
        """Check if stick is currently frozen.

        Returns:
            True if frozen, False otherwise.
        """
        return self._frozen

    def reset(self) -> None:
        """Reset freeze state and clear stashed value.

        Useful for cleanup between sessions or on controller disconnect.
        """
        self._frozen = False
        self._frozen_value = None
        self._button_was_pressed = False
