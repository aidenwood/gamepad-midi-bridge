"""Pitch bend range helpers: RPN-based config to tell MIDI receivers the pitch bend range.

Implements MIDI RPN 0,0 (Pitch Bend Sensitivity) to configure how many semitones
a full pitch bend (±8192) should span. Pure stdlib only — no Qt, no bridge wiring.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PitchBendRangeConfig:
    """Configuration for pitch bend range (RPN 0,0)."""

    enabled: bool = False
    semitones: int = 2
    cents: int = 0
    channel: int = 1
    send_on_load: bool = True

    def __post_init__(self) -> None:
        """Clamp all fields to valid ranges."""
        self.semitones = max(0, min(24, self.semitones))
        self.cents = max(0, min(99, self.cents))
        self.channel = max(1, min(16, self.channel))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "enabled": self.enabled,
            "semitones": self.semitones,
            "cents": self.cents,
            "channel": self.channel,
            "send_on_load": self.send_on_load,
        }

    @staticmethod
    def from_dict(d: dict) -> PitchBendRangeConfig:
        """Deserialize from dict."""
        return PitchBendRangeConfig(
            enabled=d.get("enabled", False),
            semitones=d.get("semitones", 2),
            cents=d.get("cents", 0),
            channel=d.get("channel", 1),
            send_on_load=d.get("send_on_load", True),
        )


def build_rpn_messages(
    semitones: int, cents: int = 0, channel: int = 1
) -> list[list[int]]:
    """
    Build RPN 0,0 (Pitch Bend Sensitivity) message sequence.

    Clamps inputs first, then returns a list of 6 MIDI CC messages (each [status, data1, data2]):
    - CC 101 = 0 (RPN MSB)
    - CC 100 = 0 (RPN LSB) — selects pitch bend sensitivity
    - CC 6 = semitones (Data Entry MSB)
    - CC 38 = cents (Data Entry LSB)
    - CC 101 = 127 (RPN Null MSB)
    - CC 100 = 127 (RPN Null LSB)

    Args:
        semitones: Range 0..24 (clamped)
        cents: Range 0..99 (clamped)
        channel: MIDI channel 1..16 (clamped)

    Returns:
        List of 6 [status, data1, data2] messages ready to send.
    """
    semitones = max(0, min(24, semitones))
    cents = max(0, min(99, cents))
    channel = max(1, min(16, channel))

    status = 0xB0 | (channel - 1)

    return [
        [status, 0x65, 0x00],  # CC 101 = 0 (RPN MSB)
        [status, 0x64, 0x00],  # CC 100 = 0 (RPN LSB) → selects pitch bend sensitivity
        [status, 0x06, semitones],  # CC 6 = semitones (Data Entry MSB)
        [status, 0x26, cents],  # CC 38 = cents (Data Entry LSB)
        [status, 0x65, 0x7F],  # CC 101 = 127 (RPN Null MSB)
        [status, 0x64, 0x7F],  # CC 100 = 127 (RPN Null LSB)
    ]


def bend_to_cents(bend_value: int, semitones: int, cents: int = 0) -> float:
    """
    Convert a pitch bend value to cents based on configured range.

    Maps -8192..+8191 pitch bend range to -(semitones*100+cents)..+(semitones*100+cents) cents.

    Args:
        bend_value: MIDI pitch bend value -8192..+8191
        semitones: Range 0..24
        cents: Range 0..99

    Returns:
        Cents value (float), with sign matching bend direction.
    """
    semitones = max(0, min(24, semitones))
    cents = max(0, min(99, cents))

    max_cents = semitones * 100 + cents
    return (bend_value / 8191.0) * max_cents


def cents_to_bend(target_cents: float, semitones: int, cents: int = 0) -> int:
    """
    Convert a target cents value to pitch bend value based on configured range.

    Inverse of bend_to_cents. Clamps result to -8192..+8191.

    Args:
        target_cents: Desired cents (can be negative)
        semitones: Range 0..24
        cents: Range 0..99

    Returns:
        Pitch bend value clamped to -8192..+8191.
    """
    semitones = max(0, min(24, semitones))
    cents = max(0, min(99, cents))

    max_cents = semitones * 100 + cents

    if max_cents == 0:
        return 0

    bend = (target_cents / max_cents) * 8191.0
    return max(-8192, min(8191, int(round(bend))))
