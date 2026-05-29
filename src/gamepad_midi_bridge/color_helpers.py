"""Color space conversions and palette generation.

Pure mathematical utilities for RGB ↔ HSV conversion, blending, and palette generation.
No Qt, no hardware writes. Used for UI palette generation and dynamic lightbar colour shifts.
"""

from math import ceil
from typing import Tuple, List


def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB to HSV colour space.

    Args:
        r: Red component (0..255)
        g: Green component (0..255)
        b: Blue component (0..255)

    Returns:
        Tuple of (h, s, v) where:
        - h: Hue (0..360 degrees)
        - s: Saturation (0..1)
        - v: Value/Brightness (0..1)
    """
    # Normalize RGB to 0..1 range
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    max_c = max(r_norm, g_norm, b_norm)
    min_c = min(r_norm, g_norm, b_norm)
    delta = max_c - min_c

    # Calculate V (brightness)
    v = max_c

    # Calculate S (saturation)
    if max_c == 0:
        s = 0.0
    else:
        s = delta / max_c

    # Calculate H (hue)
    if delta == 0:
        h = 0.0
    elif max_c == r_norm:
        h = (60.0 * (((g_norm - b_norm) / delta) % 6)) % 360.0
    elif max_c == g_norm:
        h = (60.0 * ((b_norm - r_norm) / delta + 2)) % 360.0
    else:  # max_c == b_norm
        h = (60.0 * ((r_norm - g_norm) / delta + 4)) % 360.0

    return (h, s, v)


def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """Convert HSV to RGB colour space.

    Args:
        h: Hue (0..360 degrees, wraps modulo 360)
        s: Saturation (0..1, clamped)
        v: Value/Brightness (0..1, clamped)

    Returns:
        Tuple of (r, g, b) with each component in 0..255 as int.
    """
    # Clamp and normalize inputs
    h = h % 360.0
    s = max(0.0, min(1.0, s))
    v = max(0.0, min(1.0, v))

    c = v * s  # Chroma
    h_prime = h / 60.0
    x = c * (1.0 - abs((h_prime % 2) - 1.0))

    if h_prime < 1.0:
        r_prime, g_prime, b_prime = c, x, 0.0
    elif h_prime < 2.0:
        r_prime, g_prime, b_prime = x, c, 0.0
    elif h_prime < 3.0:
        r_prime, g_prime, b_prime = 0.0, c, x
    elif h_prime < 4.0:
        r_prime, g_prime, b_prime = 0.0, x, c
    elif h_prime < 5.0:
        r_prime, g_prime, b_prime = x, 0.0, c
    else:
        r_prime, g_prime, b_prime = c, 0.0, x

    m = v - c
    r = int(round((r_prime + m) * 255.0))
    g = int(round((g_prime + m) * 255.0))
    b = int(round((b_prime + m) * 255.0))

    return (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b))
    )


def lerp_rgb(
    a: Tuple[int, int, int],
    b: Tuple[int, int, int],
    t: float
) -> Tuple[int, int, int]:
    """Linear interpolation between two RGB colours.

    Args:
        a: First RGB colour (r, g, b)
        b: Second RGB colour (r, g, b)
        t: Interpolation parameter (clamped to 0..1, where 0 = a, 1 = b)

    Returns:
        Interpolated RGB colour.
    """
    t = max(0.0, min(1.0, t))
    r = int(a[0] + (b[0] - a[0]) * t)
    g = int(a[1] + (b[1] - a[1]) * t)
    b = int(a[2] + (b[2] - a[2]) * t)
    return (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b))
    )


def lerp_hsv(
    a: Tuple[float, float, float],
    b: Tuple[float, float, float],
    t: float
) -> Tuple[float, float, float]:
    """Linear interpolation between two HSV colours.

    Takes the shortest path around the hue wheel. For example, interpolating
    between hue 350 and hue 10 will go 350 → 0, not 350 → 360 → 10.

    Args:
        a: First HSV colour (h, s, v)
        b: Second HSV colour (h, s, v)
        t: Interpolation parameter (clamped to 0..1, where 0 = a, 1 = b)

    Returns:
        Interpolated HSV colour.
    """
    t = max(0.0, min(1.0, t))

    h_a, s_a, v_a = a
    h_b, s_b, v_b = b

    # Shortest hue path: if delta > 180, go the other way
    h_delta = h_b - h_a
    if h_delta > 180.0:
        h_delta -= 360.0
    elif h_delta < -180.0:
        h_delta += 360.0

    h = (h_a + h_delta * t) % 360.0
    s = s_a + (s_b - s_a) * t
    v = v_a + (v_b - v_a) * t

    return (h, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))


def complement(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Return the complementary colour (180° hue rotation).

    Args:
        rgb: RGB colour (r, g, b)

    Returns:
        Complementary RGB colour.
    """
    h, s, v = rgb_to_hsv(rgb[0], rgb[1], rgb[2])
    h_complement = (h + 180.0) % 360.0
    return hsv_to_rgb(h_complement, s, v)


def make_palette(
    base_rgb: Tuple[int, int, int],
    count: int,
    hue_step: float = 30.0
) -> List[Tuple[int, int, int]]:
    """Generate a colour palette by stepping hue around the wheel.

    Preserves saturation and value from the base colour.

    Args:
        base_rgb: Base RGB colour to generate from
        count: Number of colours in palette (clamped to 1..32)
        hue_step: Hue step in degrees between consecutive colours (default: 30.0)

    Returns:
        List of RGB colours.
    """
    count = max(1, min(32, count))
    h, s, v = rgb_to_hsv(base_rgb[0], base_rgb[1], base_rgb[2])

    palette = []
    for i in range(count):
        h_new = (h + i * hue_step) % 360.0
        palette.append(hsv_to_rgb(h_new, s, v))

    return palette


def darken(rgb: Tuple[int, int, int], factor: float = 0.7) -> Tuple[int, int, int]:
    """Darken a colour by reducing its value (brightness).

    Args:
        rgb: RGB colour (r, g, b)
        factor: Multiplication factor for V (0..1, default: 0.7 for 30% darker)

    Returns:
        Darkened RGB colour.
    """
    factor = max(0.0, min(1.0, factor))
    h, s, v = rgb_to_hsv(rgb[0], rgb[1], rgb[2])
    v = v * factor
    return hsv_to_rgb(h, s, v)


def lighten(rgb: Tuple[int, int, int], factor: float = 1.3) -> Tuple[int, int, int]:
    """Lighten a colour by increasing its value (brightness).

    Args:
        rgb: RGB colour (r, g, b)
        factor: Multiplication factor for V (clamped at 1.0, default: 1.3 for 30% lighter)

    Returns:
        Lightened RGB colour (capped at white).
    """
    factor = max(0.0, factor)
    h, s, v = rgb_to_hsv(rgb[0], rgb[1], rgb[2])
    v = min(1.0, v * factor)
    return hsv_to_rgb(h, s, v)


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate perceptual brightness using sRGB luminance formula.

    Uses the standard sRGB relative luminance calculation with gamma correction:
    L = 0.2126 * R + 0.7152 * G + 0.0722 * B (with gamma correction applied).

    Args:
        rgb: RGB colour (r, g, b)

    Returns:
        Relative luminance as float in 0..1 range.
    """
    def gamma_correct(c: float) -> float:
        """Apply sRGB gamma correction to normalized component."""
        if c <= 0.03928:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4

    r = gamma_correct(rgb[0] / 255.0)
    g = gamma_correct(rgb[1] / 255.0)
    b = gamma_correct(rgb[2] / 255.0)

    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(
    rgb_a: Tuple[int, int, int],
    rgb_b: Tuple[int, int, int]
) -> float:
    """Calculate WCAG contrast ratio between two colours.

    Returns the contrast ratio as defined by WCAG 2.1:
    (L_lighter + 0.05) / (L_darker + 0.05)

    Args:
        rgb_a: First RGB colour
        rgb_b: Second RGB colour

    Returns:
        Contrast ratio as float in 1..21 range.
    """
    l_a = relative_luminance(rgb_a)
    l_b = relative_luminance(rgb_b)

    l_lighter = max(l_a, l_b)
    l_darker = min(l_a, l_b)

    return (l_lighter + 0.05) / (l_darker + 0.05)
