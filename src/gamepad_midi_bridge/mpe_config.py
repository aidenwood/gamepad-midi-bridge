"""MPE (MIDI Polyphonic Expression) channel allocator.

Each note gets its own MIDI channel so pitch bend, aftertouch, and CC74 (timbre)
can apply per-note. Standard MPE Zone uses channel 1 as master + 2..16 as members
(or channel 16 as master + 15..2 reversed for upper zone).

Pure stdlib only, no Qt. All operations immutable or explicitly stateful.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MpeConfig:
    """MPE configuration for a single zone."""

    enabled: bool = False
    zone: str = "lower"  # "lower" or "upper"; unknown → "lower"
    member_channel_count: int = 15  # Clamp 1..15
    pitch_bend_range_semitones: int = 48  # Clamp 0..96; MPE default is 48
    enable_y_axis: bool = True  # CC74 timbre
    enable_z_axis: bool = True  # Channel aftertouch

    def __post_init__(self) -> None:
        """Clamp and validate fields after construction."""
        # Validate zone; unknown → "lower"
        if self.zone not in ("lower", "upper"):
            self.zone = "lower"

        # Clamp member_channel_count to 1..15
        self.member_channel_count = max(1, min(15, self.member_channel_count))

        # Clamp pitch_bend_range_semitones to 0..96
        self.pitch_bend_range_semitones = max(
            0, min(96, self.pitch_bend_range_semitones)
        )

    def to_dict(self) -> dict:
        """Serialize to dict, safe for JSON or pickling."""
        return {
            "enabled": self.enabled,
            "zone": self.zone,
            "member_channel_count": self.member_channel_count,
            "pitch_bend_range_semitones": self.pitch_bend_range_semitones,
            "enable_y_axis": self.enable_y_axis,
            "enable_z_axis": self.enable_z_axis,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MpeConfig:
        """Deserialize from dict. Clamps and validates automatically."""
        return cls(
            enabled=bool(data.get("enabled", False)),
            zone=str(data.get("zone", "lower")),
            member_channel_count=int(data.get("member_channel_count", 15)),
            pitch_bend_range_semitones=int(data.get("pitch_bend_range_semitones", 48)),
            enable_y_axis=bool(data.get("enable_y_axis", True)),
            enable_z_axis=bool(data.get("enable_z_axis", True)),
        )


def master_channel(cfg: MpeConfig) -> int:
    """Return the master channel for this MPE zone.

    Args:
        cfg: MpeConfig.

    Returns:
        1 for "lower" zone, 16 for "upper" zone.
    """
    return 1 if cfg.zone == "lower" else 16


def member_channels(cfg: MpeConfig) -> List[int]:
    """Return the list of member channels for this MPE zone.

    Args:
        cfg: MpeConfig.

    Returns:
        For "lower": [2, 3, ..., member_channel_count+1].
        For "upper": [15, 14, ..., 16-member_channel_count].
        All clamped to 1..16 range.
    """
    if cfg.zone == "upper":
        # Upper zone: master is 16, members are 15, 14, ..., 16-count
        channels = [15 - i for i in range(cfg.member_channel_count)]
    else:
        # Lower zone: master is 1, members are 2, 3, ..., 1+count
        channels = [2 + i for i in range(cfg.member_channel_count)]

    # Clamp to 1..16 range
    return [max(1, min(16, ch)) for ch in channels]


def build_mcm_message(cfg: MpeConfig) -> List[List[int]]:
    """Build the MPE Configuration Message (RPN 6) sequence.

    Args:
        cfg: MpeConfig.

    Returns:
        List of 5 MIDI control change messages (each [status, cc, value]):
        - CC 101 = 0 (RPN MSB)
        - CC 100 = 6 (RPN LSB — MCM)
        - CC 6 = member_channel_count (Data Entry MSB)
        - CC 101 = 127, CC 100 = 127 (RPN Null)
        All on master channel (returned as channel index 0..15, which caller
        will map to actual MIDI channel number, or caller uses (0xB0 | channel)).
    """
    master_ch = master_channel(cfg)  # 1 or 16
    midi_channel = master_ch - 1  # Convert to 0-based for MIDI status byte

    messages = [
        [0xB0 | midi_channel, 101, 0],  # CC 101 = 0 (RPN MSB)
        [0xB0 | midi_channel, 100, 6],  # CC 100 = 6 (RPN LSB = MCM)
        [0xB0 | midi_channel, 6, cfg.member_channel_count],  # CC 6 = count
        [0xB0 | midi_channel, 101, 127],  # CC 101 = 127 (RPN Null)
        [0xB0 | midi_channel, 100, 127],  # CC 100 = 127 (RPN Null)
    ]

    return messages


class MpeAllocator:
    """Allocates MIDI channels to notes in real-time.

    Each held note occupies one member channel. Allocations are tracked
    in insertion order (priority FIFO).
    """

    def __init__(self, cfg: MpeConfig) -> None:
        """Initialize allocator with MPE config.

        Args:
            cfg: MpeConfig.
        """
        self.cfg = cfg
        # Dict: member_channel (1-based) → note (0..127) or None
        self._channel_notes: Dict[int, Optional[int]] = {
            ch: None for ch in member_channels(cfg)
        }

    def allocate(self, note: int) -> Optional[int]:
        """Allocate a channel for a note.

        If the note is already held, return the same channel (idempotent).
        If no free channels, return None.

        Args:
            note: MIDI note number (0..127).

        Returns:
            1-based MIDI channel number, or None if all busy.
        """
        # Check if note is already allocated
        for ch, held_note in self._channel_notes.items():
            if held_note == note:
                return ch

        # Find first free channel (preserves insertion order)
        for ch, held_note in self._channel_notes.items():
            if held_note is None:
                self._channel_notes[ch] = note
                return ch

        # No free channels
        return None

    def release(self, note: int) -> Optional[int]:
        """Release a note and free its channel.

        Args:
            note: MIDI note number (0..127).

        Returns:
            The 1-based channel that was freed, or None if note not held.
        """
        for ch, held_note in self._channel_notes.items():
            if held_note == note:
                self._channel_notes[ch] = None
                return ch

        return None

    def holding(self, channel: int) -> Optional[int]:
        """Return the note currently held on a channel.

        Args:
            channel: 1-based MIDI channel number.

        Returns:
            MIDI note number (0..127), or None if channel is free.
        """
        return self._channel_notes.get(channel, None)

    def reset(self) -> None:
        """Clear all allocations."""
        for ch in self._channel_notes:
            self._channel_notes[ch] = None
