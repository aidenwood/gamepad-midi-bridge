"""LFO bank manager for running N independent LFOs with optional phase sync.

This module provides a bank of LFOs that can run simultaneously with optional
shared start time for phase synchronization. Pure stdlib, no Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from gamepad_midi_bridge.lfo_waveforms import LfoConfig, LfoState


@dataclass
class LfoBankSlot:
    """A single LFO slot in the bank with MIDI routing.

    Attributes:
        name: Human-readable name for this slot (e.g. "vibrato").
        cc: MIDI CC number (0..127). Output destination controller.
        channel: MIDI channel (1..16).
        config_dict: Serialized LfoConfig dict for this slot.
    """

    name: str = ""
    cc: int = 1
    channel: int = 1
    config_dict: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Clamp cc and channel to valid MIDI ranges."""
        self.cc = max(0, min(127, self.cc))
        self.channel = max(1, min(16, self.channel))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "cc": self.cc,
            "channel": self.channel,
            "config_dict": self.config_dict,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LfoBankSlot:
        """Deserialize from a dict (e.g. from JSON)."""
        return cls(
            name=data.get("name", ""),
            cc=data.get("cc", 1),
            channel=data.get("channel", 1),
            config_dict=data.get("config_dict", {}),
        )


@dataclass
class LfoBankConfig:
    """Configuration for an LFO bank.

    Attributes:
        enabled: Whether the bank is active.
        slots: List of LfoBankSlot definitions.
        shared_start: If True, all LFOs use the same start_time when started.
        max_slots: Maximum number of slots allowed (1..32). Slots list is
                   truncated to this size during initialization.
    """

    enabled: bool = False
    slots: List[LfoBankSlot] = field(default_factory=list)
    shared_start: bool = True
    max_slots: int = 8

    def __post_init__(self) -> None:
        """Clamp max_slots and truncate slots list."""
        self.max_slots = max(1, min(32, self.max_slots))
        if len(self.slots) > self.max_slots:
            self.slots = self.slots[: self.max_slots]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "slots": [slot.to_dict() for slot in self.slots],
            "shared_start": self.shared_start,
            "max_slots": self.max_slots,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LfoBankConfig:
        """Deserialize from a dict (e.g. from JSON)."""
        slots = [
            LfoBankSlot.from_dict(slot_data)
            for slot_data in data.get("slots", [])
        ]
        return cls(
            enabled=data.get("enabled", False),
            slots=slots,
            shared_start=data.get("shared_start", True),
            max_slots=data.get("max_slots", 8),
        )


class LfoBank:
    """Runs N independent LFOs with optional phase synchronization.

    Attributes:
        cfg: LfoBankConfig instance.
        _states: Dict mapping slot index to LfoState.
        _shared_start_time: Shared start time if shared_start=True, else None.
    """

    def __init__(self, cfg: LfoBankConfig) -> None:
        """Initialize the LFO bank.

        Args:
            cfg: LfoBankConfig instance defining slots and behavior.
        """
        self.cfg = cfg
        self._states: Dict[int, LfoState] = {}
        self._shared_start_time: float | None = None

        # Build LfoState for each slot.
        for idx, slot in enumerate(cfg.slots):
            lfo_cfg = LfoConfig.from_dict(slot.config_dict)
            self._states[idx] = LfoState(lfo_cfg)

    def start(self, now_s: float) -> None:
        """Start all LFOs at the given time.

        If shared_start=True, all LFOs use the same start_time for phase sync.
        Otherwise, each LFO's start time is tracked independently.

        Args:
            now_s: Current time in seconds (e.g. from time.time()).
        """
        if self.cfg.shared_start:
            self._shared_start_time = now_s
            for state in self._states.values():
                state.start(now_s)
        else:
            for state in self._states.values():
                state.start(now_s)

    def values(self, now_s: float) -> List[Tuple[int, int, int, float]]:
        """Get current values for all active LFOs.

        Returns a list of (slot_index, cc, channel, value) tuples where value
        is the raw float output from the LFO (after depth and bipolar transform).

        Args:
            now_s: Current time in seconds.

        Returns:
            List of (slot_index, cc, channel, value) tuples.
        """
        result = []
        for idx, state in self._states.items():
            if idx < len(self.cfg.slots):
                slot = self.cfg.slots[idx]
                value = state.value(now_s)
                result.append((idx, slot.cc, slot.channel, value))
        return result

    def cc_messages(self, now_s: float) -> List[List[int]]:
        """Generate MIDI CC messages for all active LFOs.

        Returns a list of MIDI CC messages as [status_byte, cc, value_int]
        where status_byte encodes the channel and message type.

        Args:
            now_s: Current time in seconds.

        Returns:
            List of [status_byte, cc, value_int] MIDI messages.
        """
        messages = []
        for idx, state in self._states.items():
            if idx < len(self.cfg.slots):
                slot = self.cfg.slots[idx]
                value = state.value(now_s)

                # Map float value to 0..127.
                # Determine bipolar mode from the LfoConfig.
                bipolar = state.cfg.bipolar

                if bipolar:
                    # Bipolar: value is -depth..+depth, map to 0..127 with mid at 64.
                    cc_value = int(round(64 + (value * 63.5)))
                else:
                    # Unipolar: value is 0..depth, map to 0..127.
                    cc_value = int(round(value * 127 / state.cfg.depth)) if state.cfg.depth > 0 else 0

                cc_value = max(0, min(127, cc_value))

                # Status byte: 0xB0 (CC message) + channel - 1 (channel is 1..16).
                status = 0xB0 + (slot.channel - 1)

                messages.append([status, slot.cc, cc_value])

        return messages

    def reset(self) -> None:
        """Reset all LFO states."""
        for state in self._states.values():
            state.reset()
        self._shared_start_time = None

    def slot_count(self) -> int:
        """Return the number of active slots."""
        return len(self._states)
