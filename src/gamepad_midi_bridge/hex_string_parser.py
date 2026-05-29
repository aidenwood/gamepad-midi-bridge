"""Hex string parser: converts between human-readable hex and byte lists.

Pure stdlib, no Qt. Tolerates space-separated, comma-separated, 0x prefix,
brackets, tabs, newlines, mixed case, and contiguous hex pairs.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple


def parse_hex_string(s: str) -> List[int]:
    """Parse a hex string into a list of 0..255 integers.

    Tolerates:
    - Space-separated: "F0 41 10"
    - Comma-separated: "F0, 41, 10" or "F0,41,10"
    - Mixed delimiters: "F0, 41 10"
    - 0x prefix: "0xF0 0x41" or "0XF0,0x41"
    - Brackets: "[F0, 41, 10]" or "{F0 41}"
    - Tabs, newlines, multiple spaces
    - Lower, upper, mixed case
    - Contiguous hex pairs with no delimiter: "F0F1F2" (even length only)
    - Empty string returns []

    Args:
        s: hex string to parse

    Returns:
        list of integers 0..255

    Raises:
        ValueError: if invalid hex characters or byte > 255
    """
    if not s:
        return []

    # Strip whitespace and brackets
    s = s.strip()
    s = re.sub(r'[\[\{\}\]]', '', s)
    s = s.strip()

    if not s:
        return []

    # Replace common delimiters with spaces, then split
    s = re.sub(r'[,;\s]+', ' ', s)
    tokens = s.split()

    result = []
    for token in tokens:
        if not token:
            continue

        # Handle 0x/0X prefix
        if token.lower().startswith('0x'):
            token = token[2:]

        # Try to parse as single hex byte
        if len(token) <= 2:
            try:
                value = int(token, 16)
                if value > 255:
                    raise ValueError(f"Byte value {hex(value)} > 255")
                result.append(value)
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"Invalid hex characters in '{token}'")
                raise
        else:
            # Contiguous hex pairs: "F0F1F2" → [0xF0, 0xF1, 0xF2]
            # Only allow even length
            if len(token) % 2 != 0:
                raise ValueError(
                    f"Hex token '{token}' has odd length (expected pairs or 0x prefix)"
                )
            for i in range(0, len(token), 2):
                hex_pair = token[i : i + 2]
                try:
                    value = int(hex_pair, 16)
                    if value > 255:
                        raise ValueError(f"Byte value {hex(value)} > 255")
                    result.append(value)
                except ValueError as e:
                    if "invalid literal" in str(e):
                        raise ValueError(f"Invalid hex characters in '{hex_pair}'")
                    raise

    return result


def bytes_to_hex(
    bytes_list: List[int],
    separator: str = " ",
    prefix: str = "",
    uppercase: bool = True,
) -> str:
    """Convert list of integers to hex string.

    Args:
        bytes_list: list of integers 0..255
        separator: delimiter between bytes (default " ")
        prefix: prefix for each byte (e.g., "0x" → "0xF0 0x41")
        uppercase: use uppercase hex digits (default True)

    Returns:
        formatted hex string
    """
    fmt = "02X" if uppercase else "02x"
    hex_bytes = [f"{prefix}{byte:{fmt}}" for byte in bytes_list]
    return separator.join(hex_bytes)


def validate_sysex_string(s: str) -> Tuple[bool, Optional[str]]:
    """Validate a SysEx hex string: starts with F0, ends with F7, interior 0..127.

    Args:
        s: hex string to validate

    Returns:
        (is_valid, error_message) tuple. On success, returns (True, None).
        On failure, returns (False, "reason").
    """
    try:
        bytes_list = parse_hex_string(s)
    except ValueError as e:
        return False, f"Parse error: {e}"

    if not bytes_list:
        return False, "Empty SysEx (missing F0 and F7)"

    if bytes_list[0] != 0xF0:
        return False, f"SysEx must start with F0 (got {hex(bytes_list[0])})"

    if bytes_list[-1] != 0xF7:
        return False, f"SysEx must end with F7 (got {hex(bytes_list[-1])})"

    # Interior bytes must be 0..127 (MSB not set)
    for i, byte in enumerate(bytes_list[1:-1], start=1):
        if byte > 127:
            return False, f"Interior byte at index {i} is {hex(byte)} > 127"

    return True, None


def format_sysex(bytes_list: List[int], chunk_size: int = 16) -> str:
    """Format a byte list as a pretty multi-line hex dump.

    Chunks every chunk_size bytes onto a new line.

    Args:
        bytes_list: list of integers 0..255
        chunk_size: bytes per line (default 16)

    Returns:
        formatted hex dump string
    """
    if not bytes_list:
        return ""

    lines = []
    for i in range(0, len(bytes_list), chunk_size):
        chunk = bytes_list[i : i + chunk_size]
        line = bytes_to_hex(chunk, separator=" ", prefix="", uppercase=True)
        lines.append(line)

    return "\n".join(lines)


def from_clipboard_format(s: str) -> List[int]:
    """Alias for parse_hex_string, suitable for clipboard paste input.

    Args:
        s: hex string pasted from clipboard

    Returns:
        list of integers 0..255
    """
    return parse_hex_string(s)
