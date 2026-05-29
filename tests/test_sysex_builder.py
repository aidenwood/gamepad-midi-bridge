"""Tests for SysEx message builder module."""

import pytest
from gamepad_midi_bridge.sysex_builder import (
    SYSEX_START,
    SYSEX_END,
    MANUFACTURERS,
    validate_payload,
    wrap,
    universal_device_inquiry,
    gm_reset,
    gm2_reset,
    gs_reset,
    xg_reset,
    program_change_with_bank,
    roland_checksum,
    roland_data_set,
)


class TestConstants:
    """Tests for module-level constants."""

    def test_sysex_start_value(self):
        """SYSEX_START should be 0xF0 (240)."""
        assert SYSEX_START == 0xF0
        assert SYSEX_START == 240

    def test_sysex_end_value(self):
        """SYSEX_END should be 0xF7 (247)."""
        assert SYSEX_END == 0xF7
        assert SYSEX_END == 247

    def test_manufacturers_contains_expected_names(self):
        """MANUFACTURERS dict should contain common manufacturers."""
        assert "roland" in MANUFACTURERS
        assert "yamaha" in MANUFACTURERS
        assert "korg" in MANUFACTURERS
        assert "akai" in MANUFACTURERS
        assert "alesis" in MANUFACTURERS
        assert "novation" in MANUFACTURERS
        assert "elektron" in MANUFACTURERS
        assert "universal_non_realtime" in MANUFACTURERS
        assert "universal_realtime" in MANUFACTURERS

    def test_manufacturers_values_are_valid(self):
        """All manufacturer IDs should be 0-127 (7-bit)."""
        for name, mid in MANUFACTURERS.items():
            assert 0 <= mid <= 127, f"{name} has invalid ID: {mid}"


class TestValidatePayload:
    """Tests for validate_payload function."""

    def test_validate_empty_list(self):
        """Empty payload is valid."""
        validate_payload([])

    def test_validate_zero_byte(self):
        """Byte value 0 is valid."""
        validate_payload([0])

    def test_validate_max_byte(self):
        """Byte value 127 is valid (maximum 7-bit)."""
        validate_payload([127])

    def test_validate_mixed_valid_bytes(self):
        """Mixed valid bytes 0-127 are valid."""
        validate_payload([0, 1, 64, 127])

    def test_reject_byte_128(self):
        """Byte value 128 should raise ValueError."""
        with pytest.raises(ValueError, match="must be 0-127"):
            validate_payload([128])

    def test_reject_byte_255(self):
        """Byte value 255 should raise ValueError."""
        with pytest.raises(ValueError, match="must be 0-127"):
            validate_payload([255])

    def test_reject_negative_byte(self):
        """Negative byte should raise ValueError."""
        with pytest.raises(ValueError, match="must be 0-127"):
            validate_payload([-1])

    def test_reject_non_integer(self):
        """Non-integer value should raise ValueError."""
        with pytest.raises(ValueError, match="must be 0-127"):
            validate_payload([1.5])

    def test_error_message_includes_index(self):
        """Error message should include byte index."""
        with pytest.raises(ValueError, match="index 2"):
            validate_payload([0, 1, 200])


class TestWrap:
    """Tests for wrap function."""

    def test_wrap_empty_payload(self):
        """Wrapping empty payload should add only start/end."""
        result = wrap([])
        assert result == [SYSEX_START, SYSEX_END]

    def test_wrap_single_byte(self):
        """Wrapping single byte payload."""
        result = wrap([0x7E])
        assert result == [SYSEX_START, 0x7E, SYSEX_END]

    def test_wrap_multi_byte_payload(self):
        """Wrapping multi-byte payload."""
        result = wrap([0x7E, 0x7F, 0x09, 0x01])
        assert result == [SYSEX_START, 0x7E, 0x7F, 0x09, 0x01, SYSEX_END]

    def test_wrap_returns_new_list(self):
        """wrap should return a new list, not mutate input."""
        original = [0x7E, 0x7F]
        result = wrap(original)
        # Verify input wasn't mutated
        assert original == [0x7E, 0x7F]
        # Verify result is a new object
        assert result is not original
        # Verify result has start/end
        assert result[0] == SYSEX_START
        assert result[-1] == SYSEX_END

    def test_wrap_rejects_byte_above_127(self):
        """wrap should reject payload with bytes > 127."""
        with pytest.raises(ValueError, match="must be 0-127"):
            wrap([128])

    def test_wrap_rejects_negative_byte(self):
        """wrap should reject negative bytes."""
        with pytest.raises(ValueError, match="must be 0-127"):
            wrap([-1])


class TestUniversalDeviceInquiry:
    """Tests for universal_device_inquiry function."""

    def test_default_device_id(self):
        """Default inquiry should use device ID 0x7F (all)."""
        result = universal_device_inquiry()
        # [F0, 7E, 7F, 06, 01, F7]
        assert result == [0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]

    def test_custom_device_id(self):
        """Inquiry with custom device ID should use that ID."""
        result = universal_device_inquiry(device_id=0x10)
        # [F0, 7E, 10, 06, 01, F7]
        assert result == [0xF0, 0x7E, 0x10, 0x06, 0x01, 0xF7]

    def test_inquiry_length_is_6_bytes(self):
        """Inquiry message should always be 6 bytes."""
        assert len(universal_device_inquiry()) == 6

    def test_starts_with_sysex_start(self):
        """Message should start with SYSEX_START."""
        result = universal_device_inquiry()
        assert result[0] == SYSEX_START

    def test_ends_with_sysex_end(self):
        """Message should end with SYSEX_END."""
        result = universal_device_inquiry()
        assert result[-1] == SYSEX_END

    def test_contains_universal_non_realtime(self):
        """Message should use universal non-realtime manufacturer ID."""
        result = universal_device_inquiry()
        assert result[1] == MANUFACTURERS["universal_non_realtime"]
        assert result[1] == 0x7E


class TestGmReset:
    """Tests for gm_reset function."""

    def test_gm_reset_message(self):
        """GM reset should return standard sequence."""
        result = gm_reset()
        # [F0, 7E, 7F, 09, 01, F7]
        assert result == [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7]

    def test_gm_reset_length(self):
        """GM reset message should be 6 bytes."""
        assert len(gm_reset()) == 6

    def test_gm_reset_uses_universal_realtime(self):
        """GM reset should use universal realtime ID."""
        result = gm_reset()
        assert result[1] == MANUFACTURERS["universal_non_realtime"]

    def test_gm_reset_has_correct_system_on_id(self):
        """GM reset should have correct system on message ID (09)."""
        result = gm_reset()
        assert result[3] == 0x09


class TestGm2Reset:
    """Tests for gm2_reset function."""

    def test_gm2_reset_message(self):
        """GM2 reset should return standard sequence."""
        result = gm2_reset()
        # [F0, 7E, 7F, 09, 03, F7]
        assert result == [0xF0, 0x7E, 0x7F, 0x09, 0x03, 0xF7]

    def test_gm2_reset_length(self):
        """GM2 reset message should be 6 bytes."""
        assert len(gm2_reset()) == 6

    def test_gm2_differs_from_gm1(self):
        """GM2 reset should differ from GM1 reset in one byte."""
        gm1 = gm_reset()
        gm2 = gm2_reset()
        # Should be same length
        assert len(gm1) == len(gm2)
        # Should differ only in last data byte (before F7)
        assert gm1[-2] == 0x01  # GM1
        assert gm2[-2] == 0x03  # GM2


class TestGsReset:
    """Tests for gs_reset function."""

    def test_gs_reset_starts_with_f0(self):
        """GS reset should start with F0."""
        result = gs_reset()
        assert result[0] == SYSEX_START

    def test_gs_reset_ends_with_f7(self):
        """GS reset should end with F7."""
        result = gs_reset()
        assert result[-1] == SYSEX_END

    def test_gs_reset_is_11_bytes(self):
        """GS reset message should be 11 bytes total."""
        result = gs_reset()
        assert len(result) == 11

    def test_gs_reset_contains_roland_id(self):
        """GS reset should use Roland manufacturer ID."""
        result = gs_reset()
        assert result[1] == MANUFACTURERS["roland"]
        assert result[1] == 0x41

    def test_gs_reset_contains_device_id(self):
        """GS reset should include device ID 0x10."""
        result = gs_reset()
        assert result[2] == 0x10

    def test_gs_reset_contains_model_id(self):
        """GS reset should include model ID 0x42 (SC-55 family)."""
        result = gs_reset()
        assert result[3] == 0x42

    def test_gs_reset_contains_command_id(self):
        """GS reset should have command ID 0x12 (data set 1)."""
        result = gs_reset()
        assert result[4] == 0x12

    def test_gs_reset_has_valid_checksum(self):
        """GS reset checksum should be valid."""
        result = gs_reset()
        # Extract address and data (excluding F0, 41, 10, 42, 12, checksum, F7)
        address_and_data = result[5:-2]
        expected_checksum = roland_checksum(address_and_data)
        actual_checksum = result[-2]
        assert actual_checksum == expected_checksum


class TestXgReset:
    """Tests for xg_reset function."""

    def test_xg_reset_starts_with_f0(self):
        """XG reset should start with F0."""
        result = xg_reset()
        assert result[0] == SYSEX_START

    def test_xg_reset_ends_with_f7(self):
        """XG reset should end with F7."""
        result = xg_reset()
        assert result[-1] == SYSEX_END

    def test_xg_reset_is_9_bytes(self):
        """XG reset message should be 9 bytes total."""
        result = xg_reset()
        assert len(result) == 9

    def test_xg_reset_contains_yamaha_id(self):
        """XG reset should use Yamaha manufacturer ID."""
        result = xg_reset()
        assert result[1] == MANUFACTURERS["yamaha"]
        assert result[1] == 0x43

    def test_xg_reset_contains_device_id(self):
        """XG reset should include device ID 0x10."""
        result = xg_reset()
        assert result[2] == 0x10

    def test_xg_reset_message_sequence(self):
        """XG reset should have correct message ID sequence."""
        result = xg_reset()
        # [F0, 43, 10, 4C, 00, 00, 7E, 00, F7]
        assert result[3] == 0x4C
        assert result[4] == 0x00
        assert result[5] == 0x00
        assert result[6] == 0x7E
        assert result[7] == 0x00


class TestProgramChangeWithBank:
    """Tests for program_change_with_bank function."""

    def test_returns_three_messages(self):
        """Should return exactly 3 messages."""
        result = program_change_with_bank(program=0, msb=0, lsb=0)
        assert len(result) == 3

    def test_default_channel_is_1(self):
        """Default should use channel 1 (status byte 0xB0/0xC0)."""
        result = program_change_with_bank(program=0, msb=0, lsb=0)
        # Channel 1 = 0xB0 for CC, 0xC0 for PC
        assert result[0][0] == 0xB0  # Bank Select MSB
        assert result[1][0] == 0xB0  # Bank Select LSB
        assert result[2][0] == 0xC0  # Program Change

    def test_bank_select_msb_message(self):
        """First message should be Bank Select MSB."""
        result = program_change_with_bank(program=5, msb=10, lsb=20)
        assert len(result[0]) == 3
        assert result[0][0] == 0xB0  # CC message on channel 1
        assert result[0][1] == 0x00  # CC 0 = Bank Select MSB
        assert result[0][2] == 10    # MSB value

    def test_bank_select_lsb_message(self):
        """Second message should be Bank Select LSB."""
        result = program_change_with_bank(program=5, msb=10, lsb=20)
        assert len(result[1]) == 3
        assert result[1][0] == 0xB0  # CC message on channel 1
        assert result[1][1] == 0x20  # CC 32 = Bank Select LSB
        assert result[1][2] == 20    # LSB value

    def test_program_change_message(self):
        """Third message should be Program Change."""
        result = program_change_with_bank(program=5, msb=10, lsb=20)
        assert len(result[2]) == 2
        assert result[2][0] == 0xC0  # PC message on channel 1
        assert result[2][1] == 5     # Program number

    def test_channel_16_encoding(self):
        """Channel 16 should encode to 0xBF/0xCF."""
        result = program_change_with_bank(
            program=0, msb=0, lsb=0, channel=16
        )
        assert result[0][0] == 0xBF  # 0xB0 | 15
        assert result[1][0] == 0xBF
        assert result[2][0] == 0xCF  # 0xC0 | 15

    def test_channel_8_encoding(self):
        """Channel 8 should encode to 0xB7/0xC7."""
        result = program_change_with_bank(
            program=0, msb=0, lsb=0, channel=8
        )
        assert result[0][0] == 0xB7  # 0xB0 | 7
        assert result[1][0] == 0xB7
        assert result[2][0] == 0xC7  # 0xC0 | 7

    def test_reject_invalid_program(self):
        """Invalid program number should raise ValueError."""
        with pytest.raises(ValueError, match="program must be 0-127"):
            program_change_with_bank(program=128, msb=0, lsb=0)

    def test_reject_negative_program(self):
        """Negative program should raise ValueError."""
        with pytest.raises(ValueError, match="program must be 0-127"):
            program_change_with_bank(program=-1, msb=0, lsb=0)

    def test_reject_invalid_msb(self):
        """Invalid MSB should raise ValueError."""
        with pytest.raises(ValueError, match="msb must be 0-127"):
            program_change_with_bank(program=0, msb=128, lsb=0)

    def test_reject_invalid_lsb(self):
        """Invalid LSB should raise ValueError."""
        with pytest.raises(ValueError, match="lsb must be 0-127"):
            program_change_with_bank(program=0, msb=0, lsb=128)

    def test_reject_invalid_channel_zero(self):
        """Channel 0 should raise ValueError."""
        with pytest.raises(ValueError, match="channel must be 1-16"):
            program_change_with_bank(program=0, msb=0, lsb=0, channel=0)

    def test_reject_invalid_channel_17(self):
        """Channel 17 should raise ValueError."""
        with pytest.raises(ValueError, match="channel must be 1-16"):
            program_change_with_bank(program=0, msb=0, lsb=0, channel=17)


class TestRolandChecksum:
    """Tests for roland_checksum function."""

    def test_checksum_all_zeros(self):
        """Checksum of [0, 0, 0] should be 0."""
        assert roland_checksum([0, 0, 0]) == 0

    def test_checksum_0x7f(self):
        """Checksum of [0, 0x7F] should be 1."""
        # sum = 0x7F = 127
        # (128 - (127 % 128)) % 128 = (128 - 127) % 128 = 1
        assert roland_checksum([0, 0x7F]) == 1

    def test_checksum_single_byte(self):
        """Checksum of single byte."""
        # [0x40] -> sum=64 -> (128-64)%128 = 64
        assert roland_checksum([0x40]) == 64

    def test_checksum_two_bytes(self):
        """Checksum of two bytes."""
        # [0x40, 0x00] -> sum=64 -> (128-64)%128 = 64
        assert roland_checksum([0x40, 0x00]) == 64

    def test_checksum_is_7bit(self):
        """Checksum should always be 0-127."""
        for data in [[], [0], [127], [64, 64], [0x7F, 0x7F, 0x7F]]:
            checksum = roland_checksum(data)
            assert 0 <= checksum <= 127


class TestRolandDataSet:
    """Tests for roland_data_set function."""

    def test_simple_data_set(self):
        """Data set with single-byte address."""
        result = roland_data_set(
            model_id=0x42, address=[0x10], data=[0x7F]
        )
        # Should start with F0, contain 41, 10, 42, 12, end with F7
        assert result[0] == SYSEX_START
        assert result[-1] == SYSEX_END
        assert result[1] == 0x41  # Roland
        assert result[2] == 0x10  # Device ID
        assert result[3] == 0x42  # Model ID
        assert result[4] == 0x12  # Command (data set)

    def test_multi_byte_address(self):
        """Data set with multi-byte address."""
        result = roland_data_set(
            model_id=0x42, address=[0x10, 0x20, 0x30], data=[0x7F]
        )
        # Address bytes should be in payload
        assert result[5] == 0x10
        assert result[6] == 0x20
        assert result[7] == 0x30

    def test_multi_byte_data(self):
        """Data set with multiple data bytes."""
        result = roland_data_set(
            model_id=0x42, address=[0x10], data=[0x7F, 0x40, 0x00]
        )
        # Data bytes should follow address
        assert result[6] == 0x7F
        assert result[7] == 0x40
        assert result[8] == 0x00

    def test_data_set_includes_checksum(self):
        """Data set should include computed checksum before F7."""
        result = roland_data_set(
            model_id=0x42, address=[0x10], data=[0x00]
        )
        # Extract address and data (excluding headers and checksum/F7)
        address_data = result[5:-2]
        expected_checksum = roland_checksum(address_data)
        actual_checksum = result[-2]
        assert actual_checksum == expected_checksum

    def test_reject_empty_address(self):
        """Empty address should raise ValueError."""
        with pytest.raises(ValueError, match="address must be 1-4 bytes"):
            roland_data_set(model_id=0x42, address=[], data=[0x7F])

    def test_reject_address_too_long(self):
        """Address > 4 bytes should raise ValueError."""
        with pytest.raises(ValueError, match="address must be 1-4 bytes"):
            roland_data_set(
                model_id=0x42,
                address=[0x10, 0x20, 0x30, 0x40, 0x50],
                data=[0x7F],
            )

    def test_reject_empty_data(self):
        """Empty data should raise ValueError."""
        with pytest.raises(ValueError, match="data cannot be empty"):
            roland_data_set(model_id=0x42, address=[0x10], data=[])

    def test_custom_device_id(self):
        """Custom device ID should be in message."""
        result = roland_data_set(
            model_id=0x42, address=[0x10], data=[0x7F], device_id=0x20
        )
        assert result[2] == 0x20

    def test_is_valid_sysex(self):
        """Result should be valid SysEx (starts with F0, ends with F7)."""
        result = roland_data_set(
            model_id=0x42, address=[0x10], data=[0x7F]
        )
        assert result[0] == SYSEX_START
        assert result[-1] == SYSEX_END
        # All data bytes should be 7-bit
        for byte in result[1:-1]:
            assert 0 <= byte <= 127


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_gm_reset_is_valid_sysex(self):
        """GM reset should produce valid SysEx."""
        result = gm_reset()
        validate_payload(result[1:-1])  # Check payload (excluding F0/F7)

    def test_gs_reset_checksum_validity(self):
        """GS reset checksum should be valid."""
        result = gs_reset()
        payload = result[5:-2]  # Address and data
        expected = roland_checksum(payload)
        actual = result[-2]
        assert actual == expected

    def test_program_change_all_channels(self):
        """Program change should work for all 16 channels."""
        for channel in range(1, 17):
            result = program_change_with_bank(
                program=0, msb=0, lsb=0, channel=channel
            )
            assert len(result) == 3
            # Verify channel encoding
            assert (result[0][0] & 0x0F) == channel - 1
            assert (result[2][0] & 0x0F) == channel - 1
