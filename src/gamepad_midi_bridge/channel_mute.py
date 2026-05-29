"""Per-channel MIDI mute and solo matrix.

Provides a 16-channel array for muting/soloing specific MIDI channels
before messages are sent. Pure data + helper functions, no side effects.

Mute/Solo logic:
- If ANY solo channel is set, ONLY soloed channels are audible.
  Non-soloed channels return True from is_muted() (silenced).
- If no solos are active, mute list is checked directly.
- Mute always wins: a channel that is both muted and soloed is silenced.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelMute:
    """16-channel mute and solo state matrix.

    Index 0 = MIDI channel 1, index 15 = MIDI channel 16.
    Both lists are automatically padded/trimmed to exactly 16 elements.
    """

    muted_channels: list[bool] = field(default_factory=lambda: [False] * 16)
    solo_channels: list[bool] = field(default_factory=lambda: [False] * 16)

    def __post_init__(self) -> None:
        """Enforce 16-element lists on both muted and solo channels."""
        # Pad or trim muted_channels to 16
        if len(self.muted_channels) < 16:
            self.muted_channels.extend([False] * (16 - len(self.muted_channels)))
        else:
            self.muted_channels = self.muted_channels[:16]

        # Pad or trim solo_channels to 16
        if len(self.solo_channels) < 16:
            self.solo_channels.extend([False] * (16 - len(self.solo_channels)))
        else:
            self.solo_channels = self.solo_channels[:16]

    def is_muted(self, channel_1_16: int) -> bool:
        """Check if a channel should be silenced.

        Args:
            channel_1_16: MIDI channel number (1..16).

        Returns:
            True if the channel should be silenced, False if audible.
            Out-of-range channels return True (safety: don't send to invalid channels).

        Logic:
            - If out of range: return True (safety).
            - If mute is set for this channel: return True (mute always wins).
            - If any solo is active:
              - If this channel is soloed: return False (audible).
              - Otherwise: return True (silenced by solo logic).
            - If no solos: return False (audible, not muted).
        """
        # Convert 1-based channel to 0-based index
        idx = channel_1_16 - 1

        # Safety: out-of-range channels are always muted
        if idx < 0 or idx >= 16:
            return True

        # Mute always wins
        if self.muted_channels[idx]:
            return True

        # If any solo is set, only soloed channels are audible
        if self.any_soloed():
            return not self.solo_channels[idx]

        # No mute, no solos: channel is audible
        return False

    def set_mute(self, channel_1_16: int, value: bool) -> None:
        """Set mute state for a channel.

        Args:
            channel_1_16: MIDI channel number (1..16). Clamped to valid range.
            value: True to mute, False to unmute.
        """
        idx = max(0, min(channel_1_16 - 1, 15))
        self.muted_channels[idx] = value

    def set_solo(self, channel_1_16: int, value: bool) -> None:
        """Set solo state for a channel.

        Args:
            channel_1_16: MIDI channel number (1..16). Clamped to valid range.
            value: True to solo, False to un-solo.
        """
        idx = max(0, min(channel_1_16 - 1, 15))
        self.solo_channels[idx] = value

    def toggle_mute(self, channel_1_16: int) -> bool:
        """Toggle mute state for a channel.

        Args:
            channel_1_16: MIDI channel number (1..16). Clamped to valid range.

        Returns:
            The new mute state (True = muted, False = unmuted).
        """
        idx = max(0, min(channel_1_16 - 1, 15))
        self.muted_channels[idx] = not self.muted_channels[idx]
        return self.muted_channels[idx]

    def toggle_solo(self, channel_1_16: int) -> bool:
        """Toggle solo state for a channel.

        Args:
            channel_1_16: MIDI channel number (1..16). Clamped to valid range.

        Returns:
            The new solo state (True = soloed, False = not soloed).
        """
        idx = max(0, min(channel_1_16 - 1, 15))
        self.solo_channels[idx] = not self.solo_channels[idx]
        return self.solo_channels[idx]

    def clear_all_mutes(self) -> None:
        """Unmute all channels."""
        self.muted_channels = [False] * 16

    def clear_all_solos(self) -> None:
        """Remove solo from all channels."""
        self.solo_channels = [False] * 16

    def any_soloed(self) -> bool:
        """Check if any channel is soloed.

        Returns:
            True if at least one solo bit is set, False otherwise.
        """
        return any(self.solo_channels)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for storage/serialization.

        Returns:
            A dict with keys 'muted_channels' and 'solo_channels'.
        """
        return {
            "muted_channels": self.muted_channels.copy(),
            "solo_channels": self.solo_channels.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChannelMute:
        """Deserialize from a dictionary, with safe defaults.

        Args:
            data: A dictionary with optional keys 'muted_channels' and 'solo_channels'.
                  Missing keys default to all-False. Lists are padded/trimmed to 16.

        Returns:
            A new ChannelMute instance.
        """
        muted = data.get("muted_channels", [False] * 16)
        solo = data.get("solo_channels", [False] * 16)

        # Ensure both are lists (in case of corrupted data)
        if not isinstance(muted, list):
            muted = [False] * 16
        if not isinstance(solo, list):
            solo = [False] * 16

        # __post_init__ will pad/trim to 16
        return cls(muted_channels=muted, solo_channels=solo)
