"""Tests for lightbar.py — DualSense LED colour helpers."""

import pytest
from gamepad_midi_bridge.lightbar import (
    clamp_byte,
    hex_to_rgb,
    rgb_to_hex,
    apply_to_mapping,
    current_color,
    PRESET_COLOURS,
)
from gamepad_midi_bridge.mapping import Mapping


class TestClampByte:
    """Tests for clamp_byte(v: int) -> int."""

    def test_clamp_byte_negative(self):
        """Clamp negative values to 0."""
        assert clamp_byte(-1) == 0
        assert clamp_byte(-100) == 0

    def test_clamp_byte_in_range(self):
        """Values in range 0..255 pass through."""
        assert clamp_byte(0) == 0
        assert clamp_byte(127) == 127
        assert clamp_byte(255) == 255

    def test_clamp_byte_over_255(self):
        """Values > 255 clamp to 255."""
        assert clamp_byte(256) == 255
        assert clamp_byte(1000) == 255


class TestHexToRgb:
    """Tests for hex_to_rgb(hex_str: str) -> Tuple[int, int, int]."""

    def test_hex_to_rgb_with_hash(self):
        """Parse hex string with leading #."""
        assert hex_to_rgb("#FF0000") == (255, 0, 0)
        assert hex_to_rgb("#00FF00") == (0, 255, 0)
        assert hex_to_rgb("#0000FF") == (0, 0, 255)

    def test_hex_to_rgb_without_hash(self):
        """Parse hex string without leading #."""
        assert hex_to_rgb("FF0000") == (255, 0, 0)
        assert hex_to_rgb("00FF00") == (0, 255, 0)

    def test_hex_to_rgb_lowercase(self):
        """Lowercase hex digits are accepted."""
        assert hex_to_rgb("#ff0000") == (255, 0, 0)
        assert hex_to_rgb("ff0000") == (255, 0, 0)

    def test_hex_to_rgb_mixed_case(self):
        """Mixed case hex digits are accepted."""
        assert hex_to_rgb("#FfAaBb") == (255, 170, 187)

    def test_hex_to_rgb_with_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        assert hex_to_rgb("  #FF0000  ") == (255, 0, 0)

    def test_hex_to_rgb_invalid_length(self):
        """Invalid length raises ValueError."""
        with pytest.raises(ValueError, match="Invalid hex colour"):
            hex_to_rgb("#FFF")
        with pytest.raises(ValueError, match="Invalid hex colour"):
            hex_to_rgb("#FFFF00FF")  # 8 hex digits after stripping #

    def test_hex_to_rgb_invalid_characters(self):
        """Non-hex characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid hex colour"):
            hex_to_rgb("#GGGGGG")
        with pytest.raises(ValueError, match="Invalid hex colour"):
            hex_to_rgb("#12345Z")

    def test_hex_to_rgb_examples(self):
        """Test common colour values."""
        assert hex_to_rgb("#FF0000") == (255, 0, 0)    # red
        assert hex_to_rgb("#00FF00") == (0, 255, 0)    # green
        assert hex_to_rgb("#0000FF") == (0, 0, 255)    # blue
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)  # white
        assert hex_to_rgb("#000000") == (0, 0, 0)      # black


class TestRgbToHex:
    """Tests for rgb_to_hex(r: int, g: int, b: int) -> str."""

    def test_rgb_to_hex_basic(self):
        """Basic colour conversions."""
        assert rgb_to_hex(255, 0, 0) == "#FF0000"
        assert rgb_to_hex(0, 255, 0) == "#00FF00"
        assert rgb_to_hex(0, 0, 255) == "#0000FF"

    def test_rgb_to_hex_white_and_black(self):
        """White and black conversions."""
        assert rgb_to_hex(255, 255, 255) == "#FFFFFF"
        assert rgb_to_hex(0, 0, 0) == "#000000"

    def test_rgb_to_hex_mixed_values(self):
        """Mixed RGB values."""
        assert rgb_to_hex(255, 128, 64) == "#FF8040"
        assert rgb_to_hex(100, 150, 200) == "#6496C8"

    def test_rgb_to_hex_clamps_negative(self):
        """Negative values are clamped to 0."""
        assert rgb_to_hex(-10, -20, -30) == "#000000"
        assert rgb_to_hex(-1, 128, 255) == "#0080FF"

    def test_rgb_to_hex_clamps_over_255(self):
        """Values over 255 are clamped to 255."""
        assert rgb_to_hex(256, 500, 1000) == "#FFFFFF"
        assert rgb_to_hex(300, 255, 100) == "#FFFF64"

    def test_rgb_to_hex_uppercase(self):
        """Output is always uppercase."""
        assert rgb_to_hex(255, 0, 0)[0] == "#"
        assert all(c.isupper() or c.isdigit() or c == "#" for c in rgb_to_hex(170, 187, 204))

    def test_rgb_to_hex_round_trip(self):
        """hex_to_rgb and rgb_to_hex round-trip correctly."""
        test_cases = [
            "#FF0000",
            "#00FF00",
            "#0000FF",
            "#FFFFFF",
            "#000000",
            "#FF8040",
            "#6496C8",
        ]
        for hex_in in test_cases:
            r, g, b = hex_to_rgb(hex_in)
            hex_out = rgb_to_hex(r, g, b)
            assert hex_out == hex_in


class TestApplyToMapping:
    """Tests for apply_to_mapping(mapping, hex_str, enabled)."""

    def test_apply_to_mapping_sets_fields(self):
        """apply_to_mapping mutates the mapping object."""
        mapping = Mapping()
        apply_to_mapping(mapping, "#FF0000", enabled=True)
        assert mapping.lightbar_enabled is True
        assert mapping.lightbar_red == 255
        assert mapping.lightbar_green == 0
        assert mapping.lightbar_blue == 0

    def test_apply_to_mapping_disabled(self):
        """apply_to_mapping with enabled=False."""
        mapping = Mapping()
        apply_to_mapping(mapping, "#FF8000", enabled=False)
        assert mapping.lightbar_enabled is False
        assert mapping.lightbar_red == 255
        assert mapping.lightbar_green == 128
        assert mapping.lightbar_blue == 0

    def test_apply_to_mapping_default_enabled(self):
        """apply_to_mapping defaults enabled=True."""
        mapping = Mapping()
        apply_to_mapping(mapping, "#00FF00")
        assert mapping.lightbar_enabled is True

    def test_apply_to_mapping_invalid_hex(self):
        """apply_to_mapping raises on invalid hex."""
        mapping = Mapping()
        with pytest.raises(ValueError):
            apply_to_mapping(mapping, "#INVALID")


class TestCurrentColor:
    """Tests for current_color(mapping) -> str."""

    def test_current_color_from_mapping(self):
        """current_color reads lightbar_* fields from mapping."""
        mapping = Mapping(
            lightbar_red=255,
            lightbar_green=0,
            lightbar_blue=0
        )
        assert current_color(mapping) == "#FF0000"

    def test_current_color_default(self):
        """current_color on default mapping returns black."""
        mapping = Mapping()
        assert current_color(mapping) == "#000000"

    def test_current_color_after_apply(self):
        """current_color reads the colour set by apply_to_mapping."""
        mapping = Mapping()
        apply_to_mapping(mapping, "#9D00FF")  # purple
        assert current_color(mapping) == "#9D00FF"

    def test_current_color_mixed_values(self):
        """current_color with various RGB values."""
        mapping = Mapping(
            lightbar_red=100,
            lightbar_green=150,
            lightbar_blue=200
        )
        assert current_color(mapping) == "#6496C8"


class TestMappingIntegration:
    """Tests for Mapping.to_dict / from_dict with lightbar fields."""

    def test_mapping_defaults(self):
        """Mapping defaults have lightbar disabled."""
        mapping = Mapping()
        assert mapping.lightbar_enabled is False
        assert mapping.lightbar_red == 0
        assert mapping.lightbar_green == 0
        assert mapping.lightbar_blue == 0
        assert mapping.player_led_bitmask == 0

    def test_mapping_to_dict_includes_lightbar(self):
        """Mapping.to_dict includes lightbar fields."""
        mapping = Mapping(
            lightbar_enabled=True,
            lightbar_red=255,
            lightbar_green=128,
            lightbar_blue=64,
            player_led_bitmask=0b10101  # 21 in decimal
        )
        d = mapping.to_dict()
        assert d["lightbar_enabled"] is True
        assert d["lightbar_red"] == 255
        assert d["lightbar_green"] == 128
        assert d["lightbar_blue"] == 64
        assert d["player_led_bitmask"] == 21

    def test_mapping_from_dict_preserves_lightbar(self):
        """Mapping.from_dict reads and clamps lightbar fields."""
        data = {
            "lightbar_enabled": True,
            "lightbar_red": 255,
            "lightbar_green": 128,
            "lightbar_blue": 64,
            "player_led_bitmask": 15,
        }
        mapping = Mapping.from_dict(data)
        assert mapping.lightbar_enabled is True
        assert mapping.lightbar_red == 255
        assert mapping.lightbar_green == 128
        assert mapping.lightbar_blue == 64
        assert mapping.player_led_bitmask == 15

    def test_mapping_from_dict_clamps_rgb(self):
        """Mapping.from_dict clamps out-of-range RGB values."""
        data = {
            "lightbar_red": 300,
            "lightbar_green": -50,
            "lightbar_blue": 128,
        }
        mapping = Mapping.from_dict(data)
        assert mapping.lightbar_red == 255
        assert mapping.lightbar_green == 0
        assert mapping.lightbar_blue == 128

    def test_mapping_from_dict_clamps_player_led_bitmask(self):
        """Mapping.from_dict clamps player_led_bitmask to 0..31."""
        data = {"player_led_bitmask": 100}
        mapping = Mapping.from_dict(data)
        assert mapping.player_led_bitmask == 31

        data = {"player_led_bitmask": -10}
        mapping = Mapping.from_dict(data)
        assert mapping.player_led_bitmask == 0

    def test_mapping_round_trip(self):
        """Mapping can be serialized and deserialized with lightbar fields."""
        mapping1 = Mapping(
            name="test_preset",
            lightbar_enabled=True,
            lightbar_red=200,
            lightbar_green=100,
            lightbar_blue=50,
            player_led_bitmask=0b11011,
        )
        d = mapping1.to_dict()
        mapping2 = Mapping.from_dict(d)
        assert mapping2.name == "test_preset"
        assert mapping2.lightbar_enabled is True
        assert mapping2.lightbar_red == 200
        assert mapping2.lightbar_green == 100
        assert mapping2.lightbar_blue == 50
        assert mapping2.player_led_bitmask == 0b11011

    def test_mapping_from_dict_missing_lightbar_fields(self):
        """Mapping.from_dict defaults lightbar fields if missing."""
        data = {"name": "old_preset"}  # no lightbar fields
        mapping = Mapping.from_dict(data)
        assert mapping.lightbar_enabled is False
        assert mapping.lightbar_red == 0
        assert mapping.lightbar_green == 0
        assert mapping.lightbar_blue == 0
        assert mapping.player_led_bitmask == 0


class TestPresetColours:
    """Tests for PRESET_COLOURS constant."""

    def test_preset_colours_keys(self):
        """PRESET_COLOURS contains expected colour names."""
        expected_keys = {
            "red", "green", "blue", "purple", "pink", "orange",
            "cyan", "white", "off"
        }
        assert set(PRESET_COLOURS.keys()) == expected_keys

    def test_preset_colours_values_are_valid_hex(self):
        """All PRESET_COLOURS values are valid hex strings."""
        for name, hex_val in PRESET_COLOURS.items():
            # Should not raise
            r, g, b = hex_to_rgb(hex_val)
            # Verify it round-trips
            assert rgb_to_hex(r, g, b) == hex_val

    def test_preset_colours_red(self):
        """red preset is pure red."""
        r, g, b = hex_to_rgb(PRESET_COLOURS["red"])
        assert (r, g, b) == (255, 0, 0)

    def test_preset_colours_off(self):
        """off preset is black."""
        r, g, b = hex_to_rgb(PRESET_COLOURS["off"])
        assert (r, g, b) == (0, 0, 0)

    def test_preset_colours_purple(self):
        """purple preset is correct."""
        r, g, b = hex_to_rgb(PRESET_COLOURS["purple"])
        assert (r, g, b) == (157, 0, 255)
