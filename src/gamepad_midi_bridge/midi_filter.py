"""
MIDI message filtering and transformation module.

Pure data + filter logic. No Qt, no rtmidi, no bridge wiring.
Agnostic to message source/destination.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class MidiFilterConfig:
    """Configuration for MIDI message filtering and transformation."""

    # Block entire message types
    block_note_on: bool = False
    block_note_off: bool = False
    block_cc: bool = False
    block_pitch_bend: bool = False
    block_program_change: bool = False
    block_aftertouch: bool = False
    block_clock: bool = False  # Timing clock, start, stop, continue
    block_sysex: bool = False

    # Channel filtering: empty list allows all, non-empty list allows only those channels (1..16)
    allowed_channels: List[int] = field(default_factory=list)

    # Note transposition in semitones, clamped to -48..+48
    transpose_semitones: int = 0

    # CC remapping: {source_cc: destination_cc}
    cc_remap: Dict[int, int] = field(default_factory=dict)

    # Velocity scaling: 0.0..2.0, clamped to 1..127
    velocity_scale: float = 1.0

    def to_dict(self) -> dict:
        """Serialize config to dictionary."""
        return {
            "block_note_on": self.block_note_on,
            "block_note_off": self.block_note_off,
            "block_cc": self.block_cc,
            "block_pitch_bend": self.block_pitch_bend,
            "block_program_change": self.block_program_change,
            "block_aftertouch": self.block_aftertouch,
            "block_clock": self.block_clock,
            "block_sysex": self.block_sysex,
            "allowed_channels": self.allowed_channels,
            "transpose_semitones": self.transpose_semitones,
            "cc_remap": self.cc_remap,
            "velocity_scale": self.velocity_scale,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MidiFilterConfig":
        """Deserialize config from dictionary."""
        return cls(
            block_note_on=data.get("block_note_on", False),
            block_note_off=data.get("block_note_off", False),
            block_cc=data.get("block_cc", False),
            block_pitch_bend=data.get("block_pitch_bend", False),
            block_program_change=data.get("block_program_change", False),
            block_aftertouch=data.get("block_aftertouch", False),
            block_clock=data.get("block_clock", False),
            block_sysex=data.get("block_sysex", False),
            allowed_channels=data.get("allowed_channels", []),
            transpose_semitones=data.get("transpose_semitones", 0),
            cc_remap=data.get("cc_remap", {}),
            velocity_scale=data.get("velocity_scale", 1.0),
        )


def filter_message(msg_bytes: List[int], cfg: MidiFilterConfig) -> Optional[List[int]]:
    """
    Filter and transform a MIDI message according to config.

    Args:
        msg_bytes: Raw MIDI message bytes
        cfg: Filter configuration

    Returns:
        Transformed message bytes, or None if the message should be blocked.
    """
    if not msg_bytes:
        return None

    status = msg_bytes[0]

    # System-wide messages (no channel)
    if status == 0xF8:  # Timing clock
        return None if cfg.block_clock else msg_bytes
    if status == 0xFA:  # Start
        return None if cfg.block_clock else msg_bytes
    if status == 0xFB:  # Continue
        return None if cfg.block_clock else msg_bytes
    if status == 0xFC:  # Stop
        return None if cfg.block_clock else msg_bytes
    if status == 0xF0:  # Sysex
        return None if cfg.block_sysex else msg_bytes
    if status in (0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7):  # Other system messages
        return msg_bytes

    # Channel messages: extract channel (0-indexed internally, 1-16 externally)
    if status >= 0x80 and status <= 0xEF:
        channel = (status & 0x0F) + 1  # Convert to 1-based for allowed_channels check

        # Check channel filter
        if cfg.allowed_channels and channel not in cfg.allowed_channels:
            return None

        message_type = status & 0xF0

        # Note off (0x80)
        if message_type == 0x80:
            if cfg.block_note_off:
                return None
            if len(msg_bytes) >= 3:
                note = msg_bytes[1]
                transposed = _transpose_note(note, cfg.transpose_semitones)
                if transposed is None:
                    return None
                return [status, transposed, msg_bytes[2]]
            return msg_bytes

        # Note on (0x90)
        if message_type == 0x90:
            if cfg.block_note_on:
                return None
            if len(msg_bytes) >= 3:
                note = msg_bytes[1]
                velocity = msg_bytes[2]
                transposed = _transpose_note(note, cfg.transpose_semitones)
                if transposed is None:
                    return None
                scaled_velocity = _scale_velocity(velocity, cfg.velocity_scale)
                return [status, transposed, scaled_velocity]
            return msg_bytes

        # Poly aftertouch (0xA0)
        if message_type == 0xA0:
            if cfg.block_aftertouch:
                return None
            return msg_bytes

        # Control change (0xB0)
        if message_type == 0xB0:
            if cfg.block_cc:
                return None
            if len(msg_bytes) >= 3:
                cc_number = msg_bytes[1]
                cc_value = msg_bytes[2]
                # Apply CC remapping
                remapped_cc = cfg.cc_remap.get(cc_number, cc_number)
                return [status, remapped_cc, cc_value]
            return msg_bytes

        # Program change (0xC0)
        if message_type == 0xC0:
            if cfg.block_program_change:
                return None
            return msg_bytes

        # Channel aftertouch (0xD0)
        if message_type == 0xD0:
            if cfg.block_aftertouch:
                return None
            return msg_bytes

        # Pitch bend (0xE0)
        if message_type == 0xE0:
            if cfg.block_pitch_bend:
                return None
            return msg_bytes

    return msg_bytes


def _transpose_note(note: int, semitones: int) -> Optional[int]:
    """
    Transpose a note by the given number of semitones.

    Args:
        note: MIDI note number (0-127)
        semitones: Transposition in semitones (-48..+48)

    Returns:
        Transposed note (0-127), or None if out of range.
    """
    if semitones == 0:
        return note
    transposed = note + semitones
    if transposed < 0 or transposed > 127:
        return None
    return transposed


def _scale_velocity(velocity: int, scale: float) -> int:
    """
    Scale velocity by the given factor.

    Args:
        velocity: Original velocity (1-127, or 0 for note-off)
        scale: Scale factor (0.0..2.0)

    Returns:
        Scaled velocity, clamped to 1-127.
    """
    if scale == 1.0:
        return velocity
    scaled = int(velocity * scale)
    return max(1, min(127, scaled))
