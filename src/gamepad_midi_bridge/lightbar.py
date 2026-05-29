"""DualSense lightbar colour helpers.

Pure data + helper utilities for per-preset LED configuration.
No Qt, no hardware writes. The actual lightbar write happens in dualsense.py.
"""

from typing import Tuple, Dict


def clamp_byte(v: int) -> int:
    """Clamp an integer to 0..255 range."""
    return max(0, min(255, int(v)))


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert hex colour string to (r, g, b) tuple.

    Accepts "#RRGGBB" or "RRGGBB" format.
    Raises ValueError on invalid input.
    """
    s = hex_str.strip()
    # Remove leading # if present
    if s.startswith("#"):
        s = s[1:]

    # Validate length and characters
    if len(s) != 6:
        raise ValueError(f"Invalid hex colour: {hex_str} (expected 6 hex digits)")

    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (r, g, b)
    except ValueError as e:
        raise ValueError(f"Invalid hex colour: {hex_str}") from e


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (r, g, b) to uppercase hex string with leading #."""
    r = clamp_byte(r)
    g = clamp_byte(g)
    b = clamp_byte(b)
    return f"#{r:02X}{g:02X}{b:02X}"


def apply_to_mapping(mapping, hex_str: str, enabled: bool = True) -> None:
    """Mutate a Mapping object's lightbar_* fields from a hex colour.

    Args:
        mapping: Mapping instance to modify
        hex_str: hex colour string ("#RRGGBB" or "RRGGBB")
        enabled: whether to enable the lightbar
    """
    r, g, b = hex_to_rgb(hex_str)
    mapping.lightbar_enabled = enabled
    mapping.lightbar_red = r
    mapping.lightbar_green = g
    mapping.lightbar_blue = b


def current_color(mapping) -> str:
    """Return the current lightbar colour as hex string."""
    return rgb_to_hex(
        mapping.lightbar_red,
        mapping.lightbar_green,
        mapping.lightbar_blue
    )


# Common preset colours
PRESET_COLOURS: Dict[str, str] = {
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "purple": "#9D00FF",
    "pink": "#FF00C8",
    "orange": "#FF6A00",
    "cyan": "#00FFFF",
    "white": "#FFFFFF",
    "off": "#000000",
}
