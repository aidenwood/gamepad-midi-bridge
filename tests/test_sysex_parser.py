"""Tests for SysEx message parser module."""

import pytest

from gamepad_midi_bridge.sysex_parser import (
    ParsedSysex,
    parse_sysex,
    is_valid_sysex,
    extract_payload,
)


class TestParsedSysexDataclass:
    """Tests for ParsedSysex dataclass."""

    def test_default_construction(self):
        """ParsedSysex should construct with defaults."""
        result = ParsedSysex()
        assert result.manufacturer_id is None
        assert result.manufacturer_name is None
        assert result.device_id is None
        assert result.payload == []
        assert result.message_type == "unknown"
        assert result.valid is True
        assert result.error is None

    def test_to_dict_round_trip(self):
        """to_dict and from_dict should round-trip."""
        original = ParsedSysex(
            manufacturer_id=0x41,
            manufacturer_name="roland",
            device_id=0x10,
            payload=[0x42, 0x12],
            message_type="roland_data_set",
            valid=True,
            error=None
        )
        d = original.to_dict()
        restored = ParsedSysex.from_dict(d)
        assert restored == original

    def test_from_dict_with_error(self):
        """from_dict should preserve error messages."""
        d = {
            "manufacturer_id": None,
            "manufacturer_name": None,
            "device_id": None,
            "payload": [],
            "message_type": "unknown",
            "valid": False,
            "error": "Missing F7"
        }
        parsed = ParsedSysex.from_dict(d)
        assert parsed.valid is False
        assert parsed.error == "Missing F7"


class TestParseSysexBasics:
    """Tests for parse_sysex basic structure validation."""

    def test_parse_empty_message(self):
        """Empty message should be invalid."""
        result = parse_sysex([])
        assert result.valid is False
        assert "Empty message" in result.error

    def test_parse_missing_f0_start(self):
        """Message without F0 start should be invalid."""
        result = parse_sysex([0x7E, 0x7F, 0xF7])
        assert result.valid is False
        assert "start (F0)" in result.error

    def test_parse_missing_f7_end(self):
        """Message without F7 end should be invalid."""
        result = parse_sysex([0xF0, 0x7E, 0x7F])
        assert result.valid is False
        assert "end (F7)" in result.error

    def test_parse_byte_above_127(self):
        """Payload byte > 127 should be invalid."""
        result = parse_sysex([0xF0, 0x7E, 128, 0xF7])
        assert result.valid is False
        assert "Invalid data byte" in result.error

    def test_parse_negative_byte(self):
        """Negative byte should be invalid."""
        result = parse_sysex([0xF0, 0x7E, -1, 0xF7])
        assert result.valid is False
        assert "Invalid data byte" in result.error

    def test_parse_minimal_valid_sysex(self):
        """Just [F0, F7] should be valid."""
        result = parse_sysex([0xF0, 0xF7])
        assert result.valid is True
        assert result.payload == []
        assert result.manufacturer_id is None
        assert result.message_type == "unknown"
        assert result.error is None


class TestManufacturerIdentification:
    """Tests for manufacturer ID and name extraction."""

    def test_universal_non_realtime_id(self):
        """0x7E should be identified as universal_non_realtime."""
        result = parse_sysex([0xF0, 0x7E, 0x7F, 0xF7])
        assert result.valid is True
        assert result.manufacturer_id == 0x7E
        assert result.manufacturer_name == "universal_non_realtime"

    def test_universal_realtime_id(self):
        """0x7F should be identified as universal_realtime."""
        result = parse_sysex([0xF0, 0x7F, 0x00, 0xF7])
        assert result.valid is True
        assert result.manufacturer_id == 0x7F
        assert result.manufacturer_name == "universal_realtime"

    def test_roland_manufacturer_id(self):
        """0x41 should be identified as roland."""
        result = parse_sysex([0xF0, 0x41, 0x10, 0xF7])
        assert result.valid is True
        assert result.manufacturer_id == 0x41
        assert result.manufacturer_name == "roland"

    def test_yamaha_manufacturer_id(self):
        """0x43 should be identified as yamaha."""
        result = parse_sysex([0xF0, 0x43, 0x10, 0xF7])
        assert result.valid is True
        assert result.manufacturer_id == 0x43
        assert result.manufacturer_name == "yamaha"

    def test_unknown_manufacturer_id(self):
        """Unknown manufacturer ID should have None name."""
        result = parse_sysex([0xF0, 0x55, 0x7F, 0xF7])
        assert result.valid is True
        assert result.manufacturer_id == 0x55
        assert result.manufacturer_name is None


class TestDeviceIdExtraction:
    """Tests for device ID extraction."""

    def test_device_id_from_second_byte(self):
        """Device ID should be extracted from second payload byte."""
        result = parse_sysex([0xF0, 0x41, 0x10, 0x42, 0xF7])
        assert result.valid is True
        assert result.manufacturer_id == 0x41
        assert result.device_id == 0x10

    def test_device_id_with_universal(self):
        """Device ID in universal message should be extracted."""
        result = parse_sysex([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])
        assert result.valid is True
        assert result.device_id == 0x7F

    def test_no_device_id_single_byte_payload(self):
        """Single-byte payload should have None device_id."""
        result = parse_sysex([0xF0, 0x43, 0xF7])
        assert result.valid is True
        assert result.manufacturer_id == 0x43
        assert result.device_id is None


class TestMessageTypeIdentification:
    """Tests for message type recognition."""

    def test_gm_reset_identification(self):
        """[F0, 7E, 7F, 09, 01, F7] should be identified as gm_reset."""
        result = parse_sysex([0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7])
        assert result.valid is True
        assert result.message_type == "gm_reset"

    def test_gm2_reset_identification(self):
        """[F0, 7E, 7F, 09, 03, F7] should be identified as gm2_reset."""
        result = parse_sysex([0xF0, 0x7E, 0x7F, 0x09, 0x03, 0xF7])
        assert result.valid is True
        assert result.message_type == "gm2_reset"

    def test_universal_device_inquiry_identification(self):
        """[F0, 7E, *, 06, 01, F7] should be identified as device_inquiry."""
        result = parse_sysex([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])
        assert result.valid is True
        assert result.message_type == "device_inquiry"

    def test_device_inquiry_response_identification(self):
        """[F0, 7E, *, 06, 02, ...] should be identified as device_inquiry_response."""
        # Typical response: [F0, 7E, device_id, 06, 02, ...]
        result = parse_sysex([0xF0, 0x7E, 0x10, 0x06, 0x02, 0x41, 0x00, 0xF7])
        assert result.valid is True
        assert result.message_type == "device_inquiry_response"

    def test_roland_data_set_identification(self):
        """[F0, 41, *, 42, 12, ...] should be identified as roland_data_set."""
        # GS reset: [F0, 41, 10, 42, 12, 40, 00, 7F, 00, 41, F7]
        result = parse_sysex(
            [0xF0, 0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41, 0xF7]
        )
        assert result.valid is True
        assert result.message_type == "roland_data_set"

    def test_yamaha_xg_reset_identification(self):
        """[F0, 43, 10, 4C, 00, 00, 7E, 00, F7] should be identified as xg_reset."""
        result = parse_sysex(
            [0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00, 0xF7]
        )
        assert result.valid is True
        assert result.message_type == "xg_reset"

    def test_unknown_message_type(self):
        """Unknown pattern should be identified as unknown."""
        result = parse_sysex([0xF0, 0x55, 0x00, 0x00, 0xF7])
        assert result.valid is True
        assert result.message_type == "unknown"


class TestPayloadExtraction:
    """Tests for payload extraction."""

    def test_extract_payload_minimal(self):
        """Payload of [F0, F7] should be empty."""
        result = parse_sysex([0xF0, 0xF7])
        assert result.payload == []

    def test_extract_payload_single_byte(self):
        """Payload with single byte should be extracted."""
        result = parse_sysex([0xF0, 0x7E, 0xF7])
        assert result.payload == [0x7E]

    def test_extract_payload_multi_byte(self):
        """Payload with multiple bytes should be extracted."""
        result = parse_sysex([0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7])
        assert result.payload == [0x7E, 0x7F, 0x09, 0x01]

    def test_extract_payload_from_gm_reset(self):
        """GM reset payload should be extracted correctly."""
        result = parse_sysex([0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7])
        assert result.payload == [0x7E, 0x7F, 0x09, 0x01]

    def test_extract_payload_from_roland_data_set(self):
        """Roland data set payload should include all bytes between F0 and F7."""
        msg = [0xF0, 0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41, 0xF7]
        result = parse_sysex(msg)
        assert result.payload == [0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41]


class TestIsValidSysex:
    """Tests for is_valid_sysex convenience function."""

    def test_is_valid_sysex_valid_message(self):
        """Valid SysEx should return True."""
        assert is_valid_sysex([0xF0, 0x7E, 0x7F, 0xF7]) is True

    def test_is_valid_sysex_missing_f0(self):
        """Missing F0 should return False."""
        assert is_valid_sysex([0x7E, 0x7F, 0xF7]) is False

    def test_is_valid_sysex_missing_f7(self):
        """Missing F7 should return False."""
        assert is_valid_sysex([0xF0, 0x7E, 0x7F]) is False

    def test_is_valid_sysex_byte_over_127(self):
        """Byte > 127 should return False."""
        assert is_valid_sysex([0xF0, 0x7E, 128, 0xF7]) is False

    def test_is_valid_sysex_empty(self):
        """Empty message should return False."""
        assert is_valid_sysex([]) is False


class TestExtractPayloadFunction:
    """Tests for extract_payload convenience function."""

    def test_extract_payload_valid_message(self):
        """extract_payload should return payload from valid message."""
        payload = extract_payload([0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7])
        assert payload == [0x7E, 0x7F, 0x09, 0x01]

    def test_extract_payload_invalid_message(self):
        """extract_payload should return [] for invalid message."""
        payload = extract_payload([0x7E, 0x7F, 0xF7])  # Missing F0
        assert payload == []

    def test_extract_payload_missing_f7(self):
        """extract_payload should return [] if F7 is missing."""
        payload = extract_payload([0xF0, 0x7E, 0x7F])
        assert payload == []

    def test_extract_payload_byte_over_127(self):
        """extract_payload should return [] if any byte > 127."""
        payload = extract_payload([0xF0, 0x7E, 255, 0xF7])
        assert payload == []


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_parse_all_common_resets(self):
        """Should correctly parse all common reset message types."""
        messages = {
            "gm_reset": [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7],
            "gm2_reset": [0xF0, 0x7E, 0x7F, 0x09, 0x03, 0xF7],
            "xg_reset": [0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00, 0xF7],
            "roland_data_set": [0xF0, 0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41, 0xF7],
        }
        for expected_type, msg_bytes in messages.items():
            result = parse_sysex(msg_bytes)
            assert result.valid is True, f"Failed to parse {expected_type}"
            assert result.message_type == expected_type, \
                f"Expected {expected_type}, got {result.message_type}"

    def test_round_trip_serialization(self):
        """ParsedSysex should round-trip through to_dict/from_dict."""
        parsed = parse_sysex([0xF0, 0x41, 0x10, 0x42, 0xF7])
        d = parsed.to_dict()
        restored = ParsedSysex.from_dict(d)
        assert restored == parsed
        assert restored.manufacturer_id == 0x41
        assert restored.manufacturer_name == "roland"
        assert restored.device_id == 0x10
