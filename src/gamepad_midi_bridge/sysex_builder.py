"""Pure stdlib MIDI System Exclusive (SysEx) message builder.

Provides helpers to construct common SysEx byte sequences for MIDI devices:
- Universal device inquiry
- GM/GS/XG reset messages
- Program change with bank select
- Roland manufacturer-specific patch dumps

All functions return lists of bytes suitable for MIDI output (0-255 range for
MIDI status, 0-127 range for 7-bit data bytes in SysEx).
"""

from typing import List

# MIDI constants
SYSEX_START = 0xF0  # 240: Start of exclusive
SYSEX_END = 0xF7    # 247: End of exclusive

# Common manufacturer IDs (7-bit, except universal non-realtime/realtime which are special)
MANUFACTURERS = {
    "roland": 0x41,
    "yamaha": 0x43,
    "korg": 0x42,
    "akai": 0x47,
    "alesis": 0x00,
    "novation": 0x40,
    "elektron": 0x60,
    "universal_non_realtime": 0x7E,
    "universal_realtime": 0x7F,
}


def validate_payload(payload: List[int]) -> None:
    """Validate that payload contains only 7-bit data bytes (0-127).

    SysEx data bytes (excluding start/end status bytes) must be 0-127 to avoid
    interpretation as MIDI status bytes.

    Args:
        payload: List of byte values to validate

    Raises:
        ValueError: If any byte is outside the 0-127 range
    """
    for i, byte in enumerate(payload):
        if not isinstance(byte, int) or byte < 0 or byte > 127:
            raise ValueError(
                f"SysEx payload byte at index {i} is {byte}: must be 0-127"
            )


def wrap(payload: List[int]) -> List[int]:
    """Wrap a SysEx payload with start and end bytes.

    Args:
        payload: List of 7-bit payload bytes (0-127)

    Returns:
        New list: [SYSEX_START, *payload, SYSEX_END]

    Raises:
        ValueError: If any payload byte is outside 0-127
    """
    validate_payload(payload)
    return [SYSEX_START] + payload + [SYSEX_END]


def universal_device_inquiry(device_id: int = 0x7F) -> List[int]:
    """Build a Universal Device Inquiry (IDENTITY REQUEST) message.

    Queries a MIDI device to identify itself. Standard non-realtime SysEx.

    Args:
        device_id: Target device ID (0x7F = all devices, default; 0x00-0x7E = specific)

    Returns:
        SysEx message: [F0, 7E, device_id, 06, 01, F7]
    """
    return wrap([0x7E, device_id, 0x06, 0x01])


def gm_reset() -> List[int]:
    """Build a GM System On (General MIDI 1) reset message.

    Standard General MIDI initialization. All instruments to default, pitch bend
    range to ±2 semitones, aftertouch disabled, etc.

    Returns:
        SysEx message: [F0, 7E, 7F, 09, 01, F7]
    """
    return wrap([0x7E, 0x7F, 0x09, 0x01])


def gm2_reset() -> List[int]:
    """Build a GM2 System On (General MIDI 2) reset message.

    General MIDI 2 initialization, extends GM1 with additional voices and control.

    Returns:
        SysEx message: [F0, 7E, 7F, 09, 03, F7]
    """
    return wrap([0x7E, 0x7F, 0x09, 0x03])


def gs_reset() -> List[int]:
    """Build a Roland GS System On reset message.

    Initializes Roland GS mode (includes 128 drums in channel 10, extended
    controls, reverb/chorus). Includes pre-computed checksum.

    Returns:
        SysEx message: [F0, 41, 10, 42, 12, 40, 00, 7F, 00, 41, F7]
    """
    # Roland GS reset: address 40 00 7F (system area, master volume)
    # data = 00 (ignored for reset)
    # Device ID = 0x10, Model ID = 0x42 (SC-55 family)
    data = [0x40, 0x00, 0x7F, 0x00]
    checksum = roland_checksum(data)
    return wrap([0x41, 0x10, 0x42, 0x12] + data + [checksum])


def xg_reset() -> List[int]:
    """Build a Yamaha XG System On reset message.

    Initializes Yamaha XG mode (extended General MIDI with FM synthesis voices,
    effects, and control parameters).

    Returns:
        SysEx message: [F0, 43, 10, 4C, 00, 00, 7E, 00, F7]
    """
    return wrap([0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00])


def program_change_with_bank(
    program: int,
    msb: int,
    lsb: int,
    channel: int = 1,
) -> List[List[int]]:
    """Build three MIDI messages for program change with bank select.

    Sends Bank Select MSB, Bank Select LSB, then Program Change on the given
    channel. Standard MIDI (not SysEx).

    Args:
        program: Program number (0-127)
        msb: Bank Select MSB (0-127)
        lsb: Bank Select LSB (0-127)
        channel: MIDI channel (1-16, default 1)

    Returns:
        List of three messages: [[Bn 00 msb], [Bn 20 lsb], [Cn pp]]
        where n = channel - 1, pp = program

    Raises:
        ValueError: If any value is out of range
    """
    if not (0 <= program <= 127):
        raise ValueError(f"program must be 0-127, got {program}")
    if not (0 <= msb <= 127):
        raise ValueError(f"msb must be 0-127, got {msb}")
    if not (0 <= lsb <= 127):
        raise ValueError(f"lsb must be 0-127, got {lsb}")
    if not (1 <= channel <= 16):
        raise ValueError(f"channel must be 1-16, got {channel}")

    ch = channel - 1
    bank_select_msb = [0xB0 | ch, 0x00, msb]
    bank_select_lsb = [0xB0 | ch, 0x20, lsb]
    program_change = [0xC0 | ch, program]

    return [bank_select_msb, bank_select_lsb, program_change]


def roland_checksum(data: List[int]) -> int:
    """Compute Roland 7-bit checksum.

    Roland SysEx messages include a 7-bit checksum to ensure data integrity.
    Checksum = (128 - (sum(data) % 128)) % 128

    Args:
        data: List of payload bytes (address + values, before checksum)

    Returns:
        Computed checksum byte (0-127)
    """
    total = sum(data) % 128
    return (128 - total) % 128


def roland_data_set(
    model_id: int,
    address: List[int],
    data: List[int],
    device_id: int = 0x10,
) -> List[int]:
    """Build a Roland Data Set message (RQ1 format).

    Sends data to a specific address in Roland synth/module memory.
    Automatically computes and appends checksum.

    Args:
        model_id: Roland device model ID (0x42=SC-55, 0x41=MT-32, etc.)
        address: Address bytes, 1-4 bytes (e.g. [0x12, 0x34, 0x56])
        data: Data bytes to send, 1+ bytes
        device_id: Device ID (0x10 default for most Roland units)

    Returns:
        Complete SysEx message with checksum

    Raises:
        ValueError: If address is empty or > 4 bytes, or data is empty
    """
    if not address or len(address) > 4:
        raise ValueError(f"address must be 1-4 bytes, got {len(address)}")
    if not data:
        raise ValueError("data cannot be empty")

    payload = address + data
    checksum = roland_checksum(payload)

    return wrap([0x41, device_id, model_id, 0x12] + payload + [checksum])
