"""Tests for hex string parser.

Hex string parser converts between human-readable hex strings and byte lists.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestParseHexString:
    """parse_hex_string() — convert hex strings to byte lists."""

    def test_parse_space_separated(self):
        """Space-separated hex bytes."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0 41") == [0xF0, 0x41]
        assert parse_hex_string("F0 41 10 F7") == [0xF0, 0x41, 0x10, 0xF7]

    def test_parse_comma_separated(self):
        """Comma-separated hex bytes."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0,41,F7") == [0xF0, 0x41, 0xF7]
        assert parse_hex_string("F0, 41, F7") == [0xF0, 0x41, 0xF7]

    def test_parse_0x_prefix(self):
        """Hex bytes with 0x prefix."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("0xF0 0x41") == [0xF0, 0x41]
        assert parse_hex_string("0xF0,0x41,0xF7") == [0xF0, 0x41, 0xF7]

    def test_parse_0x_uppercase_prefix(self):
        """Hex bytes with 0X prefix (uppercase X)."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("0XF0 0X41") == [0xF0, 0x41]

    def test_parse_brackets(self):
        """Hex strings with brackets."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("[F0, 41, 10]") == [0xF0, 0x41, 0x10]
        assert parse_hex_string("{F0 41}") == [0xF0, 0x41]
        assert parse_hex_string("[F0 41 10]") == [0xF0, 0x41, 0x10]

    def test_parse_mixed_delimiters(self):
        """Mixed spaces and commas."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0, 41 10, F7") == [0xF0, 0x41, 0x10, 0xF7]

    def test_parse_tabs_and_newlines(self):
        """Tabs and newlines treated as delimiters."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0\t41\n10") == [0xF0, 0x41, 0x10]
        assert parse_hex_string("F0  41  10") == [0xF0, 0x41, 0x10]

    def test_parse_lowercase(self):
        """Lowercase hex bytes."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("f0 41 10") == [0xF0, 0x41, 0x10]

    def test_parse_mixed_case(self):
        """Mixed case hex bytes."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0 41 1A f7") == [0xF0, 0x41, 0x1A, 0xF7]

    def test_parse_contiguous_no_delimiter_even_length(self):
        """Contiguous hex pairs with no delimiter."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0F1F2") == [0xF0, 0xF1, 0xF2]
        assert parse_hex_string("F041") == [0xF0, 0x41]

    def test_parse_empty_string(self):
        """Empty string returns empty list."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("") == []
        assert parse_hex_string("   ") == []

    def test_parse_single_byte(self):
        """Single hex byte."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0") == [0xF0]
        assert parse_hex_string("0xFF") == [0xFF]

    def test_parse_max_byte_value(self):
        """Maximum byte value 255 (0xFF)."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("FF") == [255]
        assert parse_hex_string("ff") == [255]
        assert parse_hex_string("0xFF") == [255]

    def test_parse_min_byte_value(self):
        """Minimum byte value 0."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("00") == [0]
        assert parse_hex_string("0x00") == [0]

    def test_parse_invalid_hex_character_raises(self):
        """Invalid hex character raises ValueError."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        with pytest.raises(ValueError, match="Invalid hex"):
            parse_hex_string("GG")
        with pytest.raises(ValueError, match="Invalid hex"):
            parse_hex_string("F0 XY")

    def test_parse_byte_value_too_large_raises(self):
        """Byte value > 255 raises ValueError."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        with pytest.raises(ValueError, match="> 255|odd length"):
            parse_hex_string("F0 100")
        with pytest.raises(ValueError, match="> 255|odd length"):
            parse_hex_string("0x100")

    def test_parse_odd_length_contiguous_raises(self):
        """Odd-length contiguous hex without delimiter raises ValueError."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        with pytest.raises(ValueError, match="odd length"):
            parse_hex_string("F0F1F")

    def test_parse_mixed_contiguous_and_spaced(self):
        """Mix of contiguous and spaced tokens."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0F1 41 10") == [0xF0, 0xF1, 0x41, 0x10]


class TestBytesToHex:
    """bytes_to_hex() — convert byte lists to hex strings."""

    def test_bytes_to_hex_default(self):
        """Default formatting: uppercase, space-separated, no prefix."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([0xF0, 0x41, 0x10]) == "F0 41 10"

    def test_bytes_to_hex_uppercase(self):
        """Uppercase hex digits."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([0xF0, 0x41, 0xAB], uppercase=True) == "F0 41 AB"

    def test_bytes_to_hex_lowercase(self):
        """Lowercase hex digits."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([0xF0, 0x41, 0xAB], uppercase=False) == "f0 41 ab"

    def test_bytes_to_hex_comma_separator(self):
        """Custom separator."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([0xF0, 0x41, 0x10], separator=",") == "F0,41,10"
        assert bytes_to_hex([0xF0, 0x41, 0x10], separator=", ") == "F0, 41, 10"

    def test_bytes_to_hex_0x_prefix(self):
        """0x prefix for each byte."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([0xF0, 0x41, 0x10], prefix="0x") == "0xF0 0x41 0x10"

    def test_bytes_to_hex_0x_prefix_comma(self):
        """0x prefix with comma separator."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([0xF0, 0x41], prefix="0x", separator=", ") == "0xF0, 0x41"

    def test_bytes_to_hex_single_byte(self):
        """Single byte."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([0xFF]) == "FF"
        assert bytes_to_hex([0x00]) == "00"

    def test_bytes_to_hex_empty_list(self):
        """Empty list returns empty string."""
        from gamepad_midi_bridge.hex_string_parser import bytes_to_hex

        assert bytes_to_hex([]) == ""

    def test_bytes_to_hex_roundtrip(self):
        """parse_hex_string → bytes_to_hex → parse_hex_string is identity."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string, bytes_to_hex

        original = "F0 41 10 F7"
        bytes_list = parse_hex_string(original)
        back_to_hex = bytes_to_hex(bytes_list)
        reparsed = parse_hex_string(back_to_hex)
        assert reparsed == bytes_list


class TestValidateSysexString:
    """validate_sysex_string() — validate SysEx format."""

    def test_validate_sysex_valid(self):
        """Valid SysEx string."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("F0 7E 7F 06 01 F7")
        assert is_valid is True
        assert error is None

    def test_validate_sysex_valid_lowercase(self):
        """Valid SysEx in lowercase."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("f0 7e 7f 06 01 f7")
        assert is_valid is True
        assert error is None

    def test_validate_sysex_missing_f0(self):
        """SysEx missing F0 start."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("7E 7F 06 01 F7")
        assert is_valid is False
        assert "F0" in error or "start" in error.lower()

    def test_validate_sysex_missing_f7(self):
        """SysEx missing F7 end."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("F0 7E 7F 06 01")
        assert is_valid is False
        assert "F7" in error or "end" in error.lower()

    def test_validate_sysex_interior_byte_too_high(self):
        """Interior byte > 127."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("F0 80 F7")
        assert is_valid is False
        assert "127" in error or "> 127" in error

    def test_validate_sysex_interior_byte_at_boundary(self):
        """Interior byte at 127 boundary (edge case)."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("F0 7F F7")
        assert is_valid is True
        assert error is None

    def test_validate_sysex_empty_string(self):
        """Empty SysEx."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("")
        assert is_valid is False
        assert "Empty" in error or "F0" in error

    def test_validate_sysex_invalid_hex(self):
        """Invalid hex characters."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        is_valid, error = validate_sysex_string("F0 GG F7")
        assert is_valid is False
        assert "Parse" in error or "hex" in error.lower()

    def test_validate_sysex_long_message(self):
        """Valid long SysEx message."""
        from gamepad_midi_bridge.hex_string_parser import validate_sysex_string

        msg = "F0 41 10 42 12 40 01 01 00 00 7F 00 00 01 00 F7"
        is_valid, error = validate_sysex_string(msg)
        assert is_valid is True
        assert error is None


class TestFormatSysex:
    """format_sysex() — pretty-print hex dumps."""

    def test_format_sysex_short(self):
        """Short SysEx (single line)."""
        from gamepad_midi_bridge.hex_string_parser import format_sysex

        result = format_sysex([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])
        assert result == "F0 7E 7F 06 01 F7"

    def test_format_sysex_long_default_chunk(self):
        """Long SysEx, default 16-byte chunks."""
        from gamepad_midi_bridge.hex_string_parser import format_sysex

        # 17 bytes: should split across 2 lines
        bytes_list = list(range(0, 17))
        result = format_sysex(bytes_list)
        lines = result.split("\n")
        assert len(lines) == 2
        assert len(lines[0].split()) == 16  # First line: 16 bytes
        assert len(lines[1].split()) == 1  # Second line: 1 byte

    def test_format_sysex_custom_chunk_size(self):
        """Custom chunk size."""
        from gamepad_midi_bridge.hex_string_parser import format_sysex

        bytes_list = list(range(0, 10))
        result = format_sysex(bytes_list, chunk_size=4)
        lines = result.split("\n")
        assert len(lines) == 3  # 4 + 4 + 2 bytes

    def test_format_sysex_empty(self):
        """Empty byte list."""
        from gamepad_midi_bridge.hex_string_parser import format_sysex

        assert format_sysex([]) == ""

    def test_format_sysex_single_byte(self):
        """Single byte."""
        from gamepad_midi_bridge.hex_string_parser import format_sysex

        assert format_sysex([0xF0]) == "F0"

    def test_format_sysex_uppercase(self):
        """Output is always uppercase."""
        from gamepad_midi_bridge.hex_string_parser import format_sysex

        result = format_sysex([0xAB, 0xCD, 0xEF])
        assert result == "AB CD EF"


class TestFromClipboardFormat:
    """from_clipboard_format() — alias for parse_hex_string."""

    def test_from_clipboard_format_basic(self):
        """Alias works as parse_hex_string."""
        from gamepad_midi_bridge.hex_string_parser import from_clipboard_format

        assert from_clipboard_format("F0 41 10") == [0xF0, 0x41, 0x10]

    def test_from_clipboard_format_comma_separated(self):
        """Handles common clipboard formats."""
        from gamepad_midi_bridge.hex_string_parser import from_clipboard_format

        assert from_clipboard_format("F0,41,10") == [0xF0, 0x41, 0x10]

    def test_from_clipboard_format_brackets(self):
        """Handles bracketed input (common from some tools)."""
        from gamepad_midi_bridge.hex_string_parser import from_clipboard_format

        assert from_clipboard_format("[F0, 41, 10]") == [0xF0, 0x41, 0x10]


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_all_zeros(self):
        """All-zero byte string."""
        from gamepad_midi_bridge.hex_string_parser import (
            parse_hex_string,
            bytes_to_hex,
        )

        assert parse_hex_string("00 00 00") == [0, 0, 0]
        assert bytes_to_hex([0, 0, 0]) == "00 00 00"

    def test_all_ff(self):
        """All 0xFF byte string."""
        from gamepad_midi_bridge.hex_string_parser import (
            parse_hex_string,
            bytes_to_hex,
        )

        assert parse_hex_string("FF FF FF") == [255, 255, 255]
        assert bytes_to_hex([255, 255, 255]) == "FF FF FF"

    def test_leading_trailing_whitespace(self):
        """Leading and trailing whitespace stripped."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("  F0 41 10  ") == [0xF0, 0x41, 0x10]

    def test_extra_internal_whitespace(self):
        """Multiple spaces between tokens."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0    41    10") == [0xF0, 0x41, 0x10]

    def test_case_insensitive_parse(self):
        """Case insensitivity verified end-to-end."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        assert parse_hex_string("F0 41 10") == parse_hex_string("f0 41 10")
        assert parse_hex_string("F0 41 10") == parse_hex_string("F0 41 10")
        assert parse_hex_string("F0 41 AB") == parse_hex_string("f0 41 ab")

    def test_contiguous_with_0x_prefix_pairs(self):
        """Contiguous pairs with 0x prefix on the block."""
        from gamepad_midi_bridge.hex_string_parser import parse_hex_string

        # "0xF0F1" → strip 0x → "F0F1" → parse as pairs
        assert parse_hex_string("0xF0F1F2") == [0xF0, 0xF1, 0xF2]

    def test_many_bytes_roundtrip(self):
        """Large byte list roundtrips correctly."""
        from gamepad_midi_bridge.hex_string_parser import (
            parse_hex_string,
            bytes_to_hex,
        )

        original = list(range(0, 256))
        hex_str = bytes_to_hex(original)
        reparsed = parse_hex_string(hex_str)
        assert reparsed == original
