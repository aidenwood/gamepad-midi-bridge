"""Colour space conversion and palette generation tests."""
import pytest
from gamepad_midi_bridge import color_helpers as ch


class TestRgbToHsv:
    """Test RGB → HSV conversion."""

    def test_pure_red(self):
        """RGB(255, 0, 0) should convert to H=0°, S=1, V=1."""
        h, s, v = ch.rgb_to_hsv(255, 0, 0)
        assert abs(h - 0.0) < 0.1
        assert abs(s - 1.0) < 0.01
        assert abs(v - 1.0) < 0.01

    def test_pure_green(self):
        """RGB(0, 255, 0) should convert to H=120°, S=1, V=1."""
        h, s, v = ch.rgb_to_hsv(0, 255, 0)
        assert abs(h - 120.0) < 0.1
        assert abs(s - 1.0) < 0.01
        assert abs(v - 1.0) < 0.01

    def test_pure_blue(self):
        """RGB(0, 0, 255) should convert to H=240°, S=1, V=1."""
        h, s, v = ch.rgb_to_hsv(0, 0, 255)
        assert abs(h - 240.0) < 0.1
        assert abs(s - 1.0) < 0.01
        assert abs(v - 1.0) < 0.01

    def test_white(self):
        """RGB(255, 255, 255) should have S=0, V=1 (hue undefined)."""
        h, s, v = ch.rgb_to_hsv(255, 255, 255)
        assert abs(s - 0.0) < 0.01
        assert abs(v - 1.0) < 0.01

    def test_black(self):
        """RGB(0, 0, 0) should convert to V=0."""
        h, s, v = ch.rgb_to_hsv(0, 0, 0)
        assert abs(s - 0.0) < 0.01
        assert abs(v - 0.0) < 0.01

    def test_gray(self):
        """RGB(128, 128, 128) should have S=0."""
        h, s, v = ch.rgb_to_hsv(128, 128, 128)
        assert abs(s - 0.0) < 0.01
        # V should be around 0.5
        assert 0.4 < v < 0.6


class TestHsvToRgb:
    """Test HSV → RGB conversion."""

    def test_red_back(self):
        """HSV(0, 1, 1) should convert back to RGB(255, 0, 0)."""
        r, g, b = ch.hsv_to_rgb(0, 1, 1)
        assert r == 255
        assert g == 0
        assert b == 0

    def test_green_back(self):
        """HSV(120, 1, 1) should convert back to RGB(0, 255, 0)."""
        r, g, b = ch.hsv_to_rgb(120, 1, 1)
        assert r == 0
        assert g == 255
        assert b == 0

    def test_blue_back(self):
        """HSV(240, 1, 1) should convert back to RGB(0, 0, 255)."""
        r, g, b = ch.hsv_to_rgb(240, 1, 1)
        assert r == 0
        assert g == 0
        assert b == 255

    def test_white(self):
        """HSV(0, 0, 1) should produce white RGB(255, 255, 255)."""
        r, g, b = ch.hsv_to_rgb(0, 0, 1)
        assert r == 255
        assert g == 255
        assert b == 255

    def test_black(self):
        """HSV(0, 0, 0) should produce black RGB(0, 0, 0)."""
        r, g, b = ch.hsv_to_rgb(0, 0, 0)
        assert r == 0
        assert g == 0
        assert b == 0

    def test_clamp_inputs(self):
        """Inputs should be clamped: h mod 360, s/v clamped 0..1."""
        r, g, b = ch.hsv_to_rgb(380, 1.5, -0.5)
        # 380 mod 360 = 20, clamped s=1, clamped v=0 -> black
        assert (r, g, b) == (0, 0, 0)

    def test_hue_wraps(self):
        """Hue 380° should wrap to 20°."""
        r1, g1, b1 = ch.hsv_to_rgb(380, 1, 1)
        r2, g2, b2 = ch.hsv_to_rgb(20, 1, 1)
        assert (r1, g1, b1) == (r2, g2, b2)


class TestRgbHsvRoundTrip:
    """Test RGB → HSV → RGB preserves colour."""

    def test_round_trip_pure_colours(self):
        """Pure colours should round-trip with minimal loss."""
        test_colours = [
            (255, 0, 0),     # red
            (0, 255, 0),     # green
            (0, 0, 255),     # blue
            (255, 255, 0),   # yellow
            (0, 255, 255),   # cyan
            (255, 0, 255),   # magenta
        ]
        for orig_rgb in test_colours:
            h, s, v = ch.rgb_to_hsv(*orig_rgb)
            back_rgb = ch.hsv_to_rgb(h, s, v)
            # Allow ±1 per channel due to rounding
            for i in range(3):
                assert abs(orig_rgb[i] - back_rgb[i]) <= 1

    def test_round_trip_arbitrary(self):
        """Arbitrary colours should round-trip."""
        test_colours = [(42, 123, 200), (100, 50, 75), (200, 200, 100)]
        for orig_rgb in test_colours:
            h, s, v = ch.rgb_to_hsv(*orig_rgb)
            back_rgb = ch.hsv_to_rgb(h, s, v)
            for i in range(3):
                assert abs(orig_rgb[i] - back_rgb[i]) <= 1


class TestLerpRgb:
    """Test linear RGB interpolation."""

    def test_midpoint_black_to_white(self):
        """Midpoint between black and white should be gray."""
        r, g, b = ch.lerp_rgb((0, 0, 0), (255, 255, 255), 0.5)
        # Should be around (127, 127, 127) or (128, 128, 128)
        assert 125 <= r <= 130
        assert 125 <= g <= 130
        assert 125 <= b <= 130

    def test_start(self):
        """t=0 should return first colour."""
        result = ch.lerp_rgb((10, 20, 30), (100, 150, 200), 0.0)
        assert result == (10, 20, 30)

    def test_end(self):
        """t=1 should return second colour."""
        result = ch.lerp_rgb((10, 20, 30), (100, 150, 200), 1.0)
        assert result == (100, 150, 200)

    def test_clamp_t_low(self):
        """t < 0 should clamp to 0."""
        result = ch.lerp_rgb((0, 0, 0), (255, 255, 255), -0.5)
        assert result == (0, 0, 0)

    def test_clamp_t_high(self):
        """t > 1 should clamp to 1."""
        result = ch.lerp_rgb((0, 0, 0), (255, 255, 255), 1.5)
        assert result == (255, 255, 255)

    def test_quarter(self):
        """t=0.25 should interpolate correctly."""
        result = ch.lerp_rgb((0, 0, 0), (255, 255, 255), 0.25)
        # Should be around (63, 63, 63)
        assert 60 <= result[0] <= 65
        assert 60 <= result[1] <= 65
        assert 60 <= result[2] <= 65


class TestLerpHsv:
    """Test linear HSV interpolation."""

    def test_midpoint_s_and_v(self):
        """Midpoint interpolation should work in HSV space."""
        h, s, v = ch.lerp_hsv((0, 1, 1), (0, 0, 0), 0.5)
        assert abs(h - 0.0) < 0.1
        assert abs(s - 0.5) < 0.01
        assert abs(v - 0.5) < 0.01

    def test_hue_shortest_path_wrap_forward(self):
        """Shortest path from 350° to 10° should go 350 → 0 → 10."""
        h, s, v = ch.lerp_hsv((350, 1, 1), (10, 1, 1), 0.5)
        # Midpoint should be around 0°, not 180°
        assert h < 30.0 or h > 330.0

    def test_hue_shortest_path_wrap_backward(self):
        """Shortest path from 10° to 350° should go 10 → 0 → 350."""
        h, s, v = ch.lerp_hsv((10, 1, 1), (350, 1, 1), 0.5)
        # Midpoint should be around 0° or 360°, not 180°
        assert h < 30.0 or h > 330.0

    def test_start_hsv(self):
        """t=0 should return first colour."""
        result = ch.lerp_hsv((10, 0.5, 0.7), (200, 0.8, 0.9), 0.0)
        assert result == (10, 0.5, 0.7)

    def test_end_hsv(self):
        """t=1 should return second colour."""
        result = ch.lerp_hsv((10, 0.5, 0.7), (200, 0.8, 0.9), 1.0)
        assert result == (200, 0.8, 0.9)

    def test_clamp_t_low_hsv(self):
        """t < 0 should clamp to 0."""
        result = ch.lerp_hsv((0, 1, 1), (180, 0, 0), -0.5)
        assert result == (0, 1, 1)

    def test_clamp_t_high_hsv(self):
        """t > 1 should clamp to 1."""
        result = ch.lerp_hsv((0, 1, 1), (180, 0, 0), 1.5)
        assert result == (180, 0, 0)


class TestComplement:
    """Test complementary colour (180° hue rotation)."""

    def test_red_complement(self):
        """Complement of pure red should be cyan."""
        r, g, b = ch.complement((255, 0, 0))
        # Cyan is roughly (0, 255, 255)
        assert g > 200
        assert b > 200
        assert r < 50

    def test_green_complement(self):
        """Complement of pure green should be magenta."""
        r, g, b = ch.complement((0, 255, 0))
        # Magenta is roughly (255, 0, 255)
        assert r > 200
        assert b > 200
        assert g < 50

    def test_blue_complement(self):
        """Complement of pure blue should be yellow."""
        r, g, b = ch.complement((0, 0, 255))
        # Yellow is roughly (255, 255, 0)
        assert r > 200
        assert g > 200
        assert b < 50

    def test_double_complement(self):
        """Double complement should return to original."""
        orig = (100, 150, 200)
        comp1 = ch.complement(orig)
        comp2 = ch.complement(comp1)
        # Should be very close (within ±2 per channel)
        for i in range(3):
            assert abs(orig[i] - comp2[i]) <= 2


class TestMakePalette:
    """Test colour palette generation."""

    def test_single_colour(self):
        """count=1 should return a single-element list."""
        palette = ch.make_palette((255, 0, 0), 1)
        assert len(palette) == 1
        assert palette[0] == (255, 0, 0)

    def test_multiple_colours(self):
        """count > 1 should return distinct colours."""
        palette = ch.make_palette((255, 0, 0), 4)
        assert len(palette) == 4
        # All colours should be distinct
        assert len(set(palette)) == 4

    def test_count_clamped_low(self):
        """count < 1 should clamp to 1."""
        palette = ch.make_palette((255, 0, 0), 0)
        assert len(palette) == 1

    def test_count_clamped_high(self):
        """count > 32 should clamp to 32."""
        palette = ch.make_palette((255, 0, 0), 100)
        assert len(palette) == 32

    def test_hue_step_default(self):
        """Default hue_step=30 should create colours 30° apart."""
        palette = ch.make_palette((255, 0, 0), 3, hue_step=30.0)
        assert len(palette) == 3
        # First should be red, second ~30° away, third ~60° away
        h1, _, _ = ch.rgb_to_hsv(*palette[0])
        h2, _, _ = ch.rgb_to_hsv(*palette[1])
        h3, _, _ = ch.rgb_to_hsv(*palette[2])
        # Check hue separation (accounting for wrap)
        diff_1_2 = (h2 - h1) % 360.0
        diff_2_3 = (h3 - h2) % 360.0
        assert abs(diff_1_2 - 30.0) < 1.0
        assert abs(diff_2_3 - 30.0) < 1.0

    def test_hue_step_custom(self):
        """Custom hue_step should create colours at that interval."""
        palette = ch.make_palette((0, 255, 0), 2, hue_step=90.0)
        assert len(palette) == 2
        h1, _, _ = ch.rgb_to_hsv(*palette[0])
        h2, _, _ = ch.rgb_to_hsv(*palette[1])
        diff = (h2 - h1) % 360.0
        assert abs(diff - 90.0) < 1.0

    def test_preserves_saturation_value(self):
        """Palette colours should preserve S and V from base."""
        base = (100, 200, 50)
        h_base, s_base, v_base = ch.rgb_to_hsv(*base)
        palette = ch.make_palette(base, 3)
        for colour in palette:
            h, s, v = ch.rgb_to_hsv(*colour)
            assert abs(s - s_base) < 0.02
            assert abs(v - v_base) < 0.02


class TestDarken:
    """Test darkening a colour."""

    def test_darken_default(self):
        """Darken with default factor (0.7) should reduce V."""
        orig = (255, 100, 100)
        darkened = ch.darken(orig)
        h_orig, s_orig, v_orig = ch.rgb_to_hsv(*orig)
        h_dark, s_dark, v_dark = ch.rgb_to_hsv(*darkened)
        assert abs(h_dark - h_orig) < 1.0
        assert abs(s_dark - s_orig) < 0.02
        assert v_dark < v_orig

    def test_darken_custom_factor(self):
        """Darken with custom factor should scale V accordingly."""
        orig = (255, 100, 100)
        darkened = ch.darken(orig, factor=0.5)
        h_orig, s_orig, v_orig = ch.rgb_to_hsv(*orig)
        h_dark, s_dark, v_dark = ch.rgb_to_hsv(*darkened)
        assert abs(v_dark - v_orig * 0.5) < 0.05

    def test_darken_clamp_factor(self):
        """factor < 0 should clamp to 0."""
        darkened = ch.darken((255, 100, 100), factor=-0.5)
        # Should be black
        assert darkened == (0, 0, 0)

    def test_darken_white_to_gray(self):
        """Darkening white should produce gray."""
        result = ch.darken((255, 255, 255), factor=0.5)
        # Should be gray
        assert result[0] == result[1] == result[2]
        assert 100 < result[0] < 150


class TestLighten:
    """Test lightening a colour."""

    def test_lighten_default(self):
        """Lighten with default factor (1.3) should increase V."""
        orig = (100, 100, 200)
        lightened = ch.lighten(orig)
        h_orig, s_orig, v_orig = ch.rgb_to_hsv(*orig)
        h_light, s_light, v_light = ch.rgb_to_hsv(*lightened)
        assert abs(h_light - h_orig) < 1.0
        assert abs(s_light - s_orig) < 0.02
        assert v_light > v_orig

    def test_lighten_custom_factor(self):
        """Lighten with custom factor should scale V accordingly."""
        orig = (100, 100, 200)
        lightened = ch.lighten(orig, factor=1.5)
        h_orig, s_orig, v_orig = ch.rgb_to_hsv(*orig)
        h_light, s_light, v_light = ch.rgb_to_hsv(*lightened)
        # v_light should be min(1.0, v_orig * 1.5), which is capped at 1.0
        expected_v = min(1.0, v_orig * 1.5)
        assert abs(v_light - expected_v) < 0.02

    def test_lighten_cap_at_white(self):
        """Lightening should cap V at 1.0 (white)."""
        lightened = ch.lighten((255, 255, 255), factor=2.0)
        # Should be white
        assert lightened == (255, 255, 255)

    def test_lighten_dark_gray_to_lighter(self):
        """Lightening dark gray should produce lighter gray."""
        # Start with a dark gray (low V)
        orig = (50, 50, 50)
        result = ch.lighten(orig, factor=2.0)
        # Should be lighter than original
        h_orig, s_orig, v_orig = ch.rgb_to_hsv(*orig)
        h_light, s_light, v_light = ch.rgb_to_hsv(*result)
        assert v_light > v_orig


class TestRelativeLuminance:
    """Test sRGB perceptual brightness calculation."""

    def test_white_max_luminance(self):
        """White should have maximum luminance."""
        l = ch.relative_luminance((255, 255, 255))
        assert abs(l - 1.0) < 0.01

    def test_black_min_luminance(self):
        """Black should have minimum luminance."""
        l = ch.relative_luminance((0, 0, 0))
        assert abs(l - 0.0) < 0.01

    def test_luminance_ordering(self):
        """Luminance of different grays should be ordered."""
        l_dark = ch.relative_luminance((50, 50, 50))
        l_mid = ch.relative_luminance((128, 128, 128))
        l_light = ch.relative_luminance((200, 200, 200))
        assert l_dark < l_mid < l_light

    def test_green_brighter_than_red(self):
        """Green (0,255,0) should be brighter than red (255,0,0)."""
        l_red = ch.relative_luminance((255, 0, 0))
        l_green = ch.relative_luminance((0, 255, 0))
        assert l_green > l_red

    def test_luminance_range(self):
        """Luminance should always be in 0..1 range."""
        for r in [0, 100, 200, 255]:
            for g in [0, 100, 200, 255]:
                for b in [0, 100, 200, 255]:
                    l = ch.relative_luminance((r, g, b))
                    assert 0.0 <= l <= 1.0


class TestContrastRatio:
    """Test WCAG contrast ratio calculation."""

    def test_black_on_white(self):
        """Black on white should have contrast ratio of 21."""
        ratio = ch.contrast_ratio((0, 0, 0), (255, 255, 255))
        assert abs(ratio - 21.0) < 0.1

    def test_white_on_black(self):
        """White on black should also have contrast ratio of 21."""
        ratio = ch.contrast_ratio((255, 255, 255), (0, 0, 0))
        assert abs(ratio - 21.0) < 0.1

    def test_same_colour(self):
        """Same colour should have contrast ratio of 1."""
        ratio = ch.contrast_ratio((100, 100, 100), (100, 100, 100))
        assert abs(ratio - 1.0) < 0.01

    def test_symmetric(self):
        """Contrast ratio should be symmetric."""
        ratio_ab = ch.contrast_ratio((50, 50, 50), (200, 200, 200))
        ratio_ba = ch.contrast_ratio((200, 200, 200), (50, 50, 50))
        assert abs(ratio_ab - ratio_ba) < 0.01

    def test_contrast_always_gte_1(self):
        """Contrast ratio should always be >= 1."""
        test_pairs = [
            ((0, 0, 0), (255, 255, 255)),
            ((100, 100, 100), (150, 150, 150)),
            ((255, 0, 0), (0, 255, 0)),
        ]
        for rgb_a, rgb_b in test_pairs:
            ratio = ch.contrast_ratio(rgb_a, rgb_b)
            assert ratio >= 1.0

    def test_contrast_wcag_minimum(self):
        """Some pairs should meet WCAG AA standard (4.5:1 for text)."""
        # Black on white definitely passes
        ratio = ch.contrast_ratio((0, 0, 0), (255, 255, 255))
        assert ratio >= 4.5
