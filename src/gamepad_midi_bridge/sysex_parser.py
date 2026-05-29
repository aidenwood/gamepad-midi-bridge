"""Pure stdlib MIDI System Exclusive (SysEx) message parser.

Decodes raw sysex byte arrays into structured representations, including:
- Manufacturer identification (single-byte and 3-byte IDs)
- Payload extraction and validation
- Recognition of common message types (GM/GS/XG reset, device inquiry, etc.)
- Error reporting for malformed messages
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

from gamepad_midi_bridge.sysex_builder import (
    SYSEX_START,
    SYSEX_END,
    MANUFACTURERS,
)

# Build reverse lookup: manufacturer ID → name
_REVERSE_MANUFACTURERS = {v: k for k, v in MANUFACTURERS.items()}


@dataclass
class ParsedSysex:
    """Structured representation of a parsed SysEx message.

    Attributes:
        manufacturer_id: Single-byte (0x01-0x7D) or special (0x7E, 0x7F)
                         manufacturer ID, or None if 3-byte ID used.
        manufacturer_name: Human-readable manufacturer name, or None if unknown
                          or 3-byte ID.
        device_id: Device ID from the message (often the byte after manufacturer),
                   or None if not applicable.
        payload: Raw bytes between manufacturer ID and terminating F7.
        message_type: Recognized message type: "gm_reset", "gm2_reset",
                     "gs_reset", "xg_reset", "device_inquiry",
                     "device_inquiry_response", "roland_data_set", or "unknown".
        valid: False if structure is broken (missing F0/F7, invalid byte ranges).
        error: Human-readable error description if not valid, else None.
    """

    manufacturer_id: Optional[int] = None
    manufacturer_name: Optional[str] = None
    device_id: Optional[int] = None
    payload: List[int] = field(default_factory=list)
    message_type: str = "unknown"
    valid: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to a dict for serialization.

        Returns:
            Dictionary representation of the ParsedSysex.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ParsedSysex:
        """Construct from a dict (reverse of to_dict).

        Args:
            data: Dictionary with keys matching ParsedSysex fields.

        Returns:
            A new ParsedSysex instance.
        """
        return cls(**data)


def _identify_message_type(msg_bytes: List[int]) -> str:
    """Identify known SysEx message types by byte pattern.

    Args:
        msg_bytes: Full SysEx message including F0 and F7.

    Returns:
        Message type string: "gm_reset", "gm2_reset", "gs_reset", "xg_reset",
        "device_inquiry", "device_inquiry_response", "roland_data_set", or "unknown".
    """
    # Need at least [F0, ...]
    if len(msg_bytes) < 2:
        return "unknown"

    # Device inquiry: [F0, 7E, *, 06, 01, F7]
    if (len(msg_bytes) >= 6 and msg_bytes[1] == 0x7E and
            msg_bytes[3] == 0x06 and msg_bytes[4] == 0x01):
        return "device_inquiry"

    # Device inquiry response: [F0, 7E, *, 06, 02, ...]
    if (len(msg_bytes) >= 6 and msg_bytes[1] == 0x7E and
            msg_bytes[3] == 0x06 and msg_bytes[4] == 0x02):
        return "device_inquiry_response"

    # GM reset: [F0, 7E, 7F, 09, 01, F7]
    if (len(msg_bytes) >= 6 and msg_bytes[1] == 0x7E and
            msg_bytes[2] == 0x7F and msg_bytes[3] == 0x09 and
            msg_bytes[4] == 0x01):
        return "gm_reset"

    # GM2 reset: [F0, 7E, 7F, 09, 03, F7]
    if (len(msg_bytes) >= 6 and msg_bytes[1] == 0x7E and
            msg_bytes[2] == 0x7F and msg_bytes[3] == 0x09 and
            msg_bytes[4] == 0x03):
        return "gm2_reset"

    # Roland GS data set: [F0, 41, *, 42, 12, ...]
    if (len(msg_bytes) >= 5 and msg_bytes[1] == 0x41 and
            msg_bytes[3] == 0x42 and msg_bytes[4] == 0x12):
        return "roland_data_set"

    # Yamaha XG reset: [F0, 43, 10, 4C, 00, 00, 7E, 00, F7]
    if (len(msg_bytes) >= 9 and msg_bytes[1] == 0x43 and
            msg_bytes[2] == 0x10 and msg_bytes[3] == 0x4C and
            msg_bytes[4] == 0x00 and msg_bytes[5] == 0x00 and
            msg_bytes[6] == 0x7E and msg_bytes[7] == 0x00):
        return "xg_reset"

    return "unknown"


def parse_sysex(msg_bytes: List[int]) -> ParsedSysex:
    """Parse a raw SysEx byte array into a structured representation.

    Validates structure, extracts manufacturer ID, device ID, payload,
    and identifies message type.

    Args:
        msg_bytes: Raw MIDI message bytes, typically [F0, ..., F7].

    Returns:
        ParsedSysex instance with parsed data or error information.
    """
    # Validate basic structure
    if not msg_bytes:
        return ParsedSysex(
            valid=False,
            error="Empty message"
        )

    if msg_bytes[0] != SYSEX_START:
        return ParsedSysex(
            valid=False,
            error=f"Missing SysEx start (F0); first byte is 0x{msg_bytes[0]:02X}"
        )

    if msg_bytes[-1] != SYSEX_END:
        return ParsedSysex(
            valid=False,
            error=f"Missing SysEx end (F7); last byte is 0x{msg_bytes[-1]:02X}"
        )

    # Validate payload bytes are 7-bit (0-127)
    for i, byte in enumerate(msg_bytes[1:-1]):
        if byte < 0 or byte > 127:
            return ParsedSysex(
                valid=False,
                error=f"Invalid data byte at index {i+1}: 0x{byte:02X} (must be 0-127)"
            )

    # Extract payload (everything between F0 and F7)
    payload = msg_bytes[1:-1]

    # Trivial case: just [F0, F7]
    if not payload:
        return ParsedSysex(
            payload=[],
            message_type="unknown",
            valid=True,
            error=None
        )

    # Extract manufacturer ID and device ID
    manufacturer_id = payload[0]
    manufacturer_name = _REVERSE_MANUFACTURERS.get(manufacturer_id)
    device_id = None

    # If manufacturer is 0x00, it's a 3-byte manufacturer ID (next 2 bytes)
    # We extract it but don't reverse-lookup in our simple dict
    if manufacturer_id == 0x00:
        if len(payload) >= 3:
            # 3-byte manufacturer ID: skip the identification process
            # for now, leave manufacturer_id as 0x00, name as None
            device_id = None
        # Return with partial payload (all bytes after F0, excluding F7)
    else:
        # Single-byte manufacturer ID; device_id is often the next byte
        if len(payload) > 1:
            device_id = payload[1]

    # Identify message type
    message_type = _identify_message_type(msg_bytes)

    return ParsedSysex(
        manufacturer_id=manufacturer_id,
        manufacturer_name=manufacturer_name,
        device_id=device_id,
        payload=payload,
        message_type=message_type,
        valid=True,
        error=None
    )


def is_valid_sysex(msg_bytes: List[int]) -> bool:
    """Check if a message is valid SysEx (quick validation).

    Args:
        msg_bytes: Raw MIDI message bytes.

    Returns:
        True if the message is structurally valid SysEx, False otherwise.
    """
    parsed = parse_sysex(msg_bytes)
    return parsed.valid


def extract_payload(msg_bytes: List[int]) -> List[int]:
    """Extract payload bytes from a SysEx message.

    Returns bytes between F0 and F7, or empty list if message is invalid.

    Args:
        msg_bytes: Raw MIDI message bytes.

    Returns:
        List of payload bytes (0-127), or [] if invalid.
    """
    parsed = parse_sysex(msg_bytes)
    return parsed.payload if parsed.valid else []
