"""Per-channel pitch wheel sensitivity config and RPN message builder.

Stores pitch bend range (in semitones + cents) for each of 16 MIDI channels,
plus helpers for emitting the RPN 0,0 sequence to set it per-channel.
Pure stdlib only — no Qt, no bridge wiring.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PitchWheelChannelConfig:
    """Configuration for a single MIDI channel's pitch wheel sensitivity."""

    channel: int = 1
    semitones: int = 2
    cents: int = 0

    def __post_init__(self) -> None:
        """Clamp all fields to valid ranges."""
        self.channel = max(1, min(16, self.channel))
        self.semitones = max(0, min(96, self.semitones))
        self.cents = max(0, min(99, self.cents))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "channel": self.channel,
            "semitones": self.semitones,
            "cents": self.cents,
        }

    @staticmethod
    def from_dict(d: dict) -> PitchWheelChannelConfig:
        """Deserialize from dict."""
        return PitchWheelChannelConfig(
            channel=d.get("channel", 1),
            semitones=d.get("semitones", 2),
            cents=d.get("cents", 0),
        )


@dataclass
class PitchWheelSensitivityConfig:
    """Configuration for per-channel pitch wheel sensitivity (RPN 0,0) storage."""

    enabled: bool = False
    channels: list[PitchWheelChannelConfig] = field(default_factory=list)
    send_on_load: bool = True

    def to_dict(self) -> dict:
        """Serialize to dict (including nested channels)."""
        return {
            "enabled": self.enabled,
            "channels": [ch.to_dict() for ch in self.channels],
            "send_on_load": self.send_on_load,
        }

    @staticmethod
    def from_dict(d: dict) -> PitchWheelSensitivityConfig:
        """Deserialize from dict (including nested channels)."""
        channels_data = d.get("channels", [])
        channels = [
            PitchWheelChannelConfig.from_dict(ch) for ch in channels_data
        ]
        return PitchWheelSensitivityConfig(
            enabled=d.get("enabled", False),
            channels=channels,
            send_on_load=d.get("send_on_load", True),
        )


class PitchWheelSensitivity:
    """Manager for per-channel pitch wheel sensitivity settings."""

    def __init__(self, cfg: PitchWheelSensitivityConfig) -> None:
        """Initialize with a config object."""
        self._cfg = cfg

    def set_channel(
        self, channel: int, semitones: int, cents: int = 0
    ) -> None:
        """
        Add or update sensitivity for a single channel.

        Args:
            channel: MIDI channel 1..16 (clamped)
            semitones: Range 0..96 (clamped)
            cents: Range 0..99 (clamped)
        """
        channel = max(1, min(16, channel))
        semitones = max(0, min(96, semitones))
        cents = max(0, min(99, cents))

        # Look for existing entry
        for ch_cfg in self._cfg.channels:
            if ch_cfg.channel == channel:
                ch_cfg.semitones = semitones
                ch_cfg.cents = cents
                return

        # Add new entry
        self._cfg.channels.append(
            PitchWheelChannelConfig(
                channel=channel, semitones=semitones, cents=cents
            )
        )

    def get_channel(self, channel: int) -> PitchWheelChannelConfig | None:
        """
        Get sensitivity for a channel, or None if not configured.

        Args:
            channel: MIDI channel 1..16

        Returns:
            PitchWheelChannelConfig if found, else None.
        """
        for ch_cfg in self._cfg.channels:
            if ch_cfg.channel == channel:
                return ch_cfg
        return None

    def remove_channel(self, channel: int) -> bool:
        """
        Remove sensitivity config for a channel.

        Args:
            channel: MIDI channel 1..16

        Returns:
            True if removed, False if not found.
        """
        for i, ch_cfg in enumerate(self._cfg.channels):
            if ch_cfg.channel == channel:
                self._cfg.channels.pop(i)
                return True
        return False

    def all_channels(self) -> list[PitchWheelChannelConfig]:
        """
        Return a copy of all configured channels.

        Returns:
            List of PitchWheelChannelConfig objects (copy, not reference).
        """
        return [
            PitchWheelChannelConfig(
                channel=ch.channel, semitones=ch.semitones, cents=ch.cents
            )
            for ch in self._cfg.channels
        ]

    def rpn_messages_for(self, channel: int) -> list[list[int]]:
        """
        Build RPN 0,0 (Pitch Bend Sensitivity) message sequence for one channel.

        Returns the 6-message sequence (or empty list if channel not configured):
        - CC 101 = 0 (RPN MSB)
        - CC 100 = 0 (RPN LSB) → selects pitch bend sensitivity
        - CC 6 = semitones (Data Entry MSB)
        - CC 38 = cents (Data Entry LSB)
        - CC 101 = 127 (RPN Null MSB)
        - CC 100 = 127 (RPN Null LSB)

        Args:
            channel: MIDI channel 1..16

        Returns:
            List of 6 [status, data1, data2] messages, or [] if no config for channel.
        """
        ch_cfg = self.get_channel(channel)
        if ch_cfg is None:
            return []

        status = 0xB0 | (channel - 1)

        return [
            [status, 0x65, 0x00],  # CC 101 = 0 (RPN MSB)
            [status, 0x64, 0x00],  # CC 100 = 0 (RPN LSB)
            [status, 0x06, ch_cfg.semitones],  # CC 6 = semitones
            [status, 0x26, ch_cfg.cents],  # CC 38 = cents
            [status, 0x65, 0x7F],  # CC 101 = 127
            [status, 0x64, 0x7F],  # CC 100 = 127
        ]

    def all_rpn_messages(self) -> list[list[int]]:
        """
        Build concatenated RPN messages for all configured channels.

        Returns:
            Flattened list of [status, data1, data2] messages ready to send.
        """
        result = []
        for ch_cfg in self._cfg.channels:
            result.extend(self.rpn_messages_for(ch_cfg.channel))
        return result

    def clear(self) -> None:
        """Clear all channel configurations."""
        self._cfg.channels.clear()
