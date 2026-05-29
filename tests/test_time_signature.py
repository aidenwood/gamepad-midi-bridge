"""Tests for time signature module."""

import pytest
from gamepad_midi_bridge.time_signature import (
    TimeSignature,
    COMMON_SIGNATURES,
    bar_duration_ms,
    beat_in_bar,
    is_downbeat,
    beats_in_seconds,
    bars_in_seconds,
    next_downbeat_ms,
)


class TestTimeSignatureDataclass:
    """Tests for TimeSignature dataclass."""

    def test_constructor_basic(self):
        """TimeSignature(4, 4) should create a 4/4 time signature."""
        sig = TimeSignature(4, 4)
        assert sig.numerator == 4
        assert sig.denominator == 4

    def test_str_representation(self):
        """__str__ should return 'numerator/denominator' format."""
        assert str(TimeSignature(4, 4)) == "4/4"
        assert str(TimeSignature(3, 4)) == "3/4"
        assert str(TimeSignature(6, 8)) == "6/8"

    def test_numerator_clamping_low(self):
        """Numerator below 1 should clamp to 1."""
        sig = TimeSignature(0, 4)
        assert sig.numerator == 1

    def test_numerator_clamping_high(self):
        """Numerator above 32 should clamp to 32."""
        sig = TimeSignature(50, 4)
        assert sig.numerator == 32

    def test_denominator_valid(self):
        """Valid denominators (1, 2, 4, 8, 16) should be preserved."""
        for denom in [1, 2, 4, 8, 16]:
            sig = TimeSignature(4, denom)
            assert sig.denominator == denom

    def test_denominator_invalid_defaults_to_4(self):
        """Invalid denominator should default to 4."""
        sig = TimeSignature(4, 7)
        assert sig.denominator == 4

    def test_to_dict(self):
        """to_dict should return numerator and denominator."""
        sig = TimeSignature(3, 8)
        data = sig.to_dict()
        assert data["numerator"] == 3
        assert data["denominator"] == 8

    def test_from_dict(self):
        """from_dict should restore time signature from dict."""
        data = {"numerator": 5, "denominator": 4}
        sig = TimeSignature.from_dict(data)
        assert sig.numerator == 5
        assert sig.denominator == 4

    def test_round_trip_serialization(self):
        """Time signature should round-trip through dict serialization."""
        original = TimeSignature(7, 8)
        data = original.to_dict()
        restored = TimeSignature.from_dict(data)
        assert restored.numerator == original.numerator
        assert restored.denominator == original.denominator
        assert str(restored) == str(original)

    def test_from_dict_with_validation(self):
        """from_dict should apply validation during deserialization."""
        data = {"numerator": 50, "denominator": 7}
        sig = TimeSignature.from_dict(data)
        assert sig.numerator == 32  # clamped
        assert sig.denominator == 4  # defaulted


class TestBarDurationMs:
    """Tests for bar_duration_ms function."""

    def test_4_4_at_120_bpm(self):
        """4/4 at 120 BPM should be 2000ms (4 quarter notes)."""
        sig = TimeSignature(4, 4)
        assert bar_duration_ms(sig, 120) == 2000.0

    def test_3_4_at_120_bpm(self):
        """3/4 at 120 BPM should be 1500ms (3 quarter notes)."""
        sig = TimeSignature(3, 4)
        assert bar_duration_ms(sig, 120) == 1500.0

    def test_6_8_at_120_bpm(self):
        """6/8 at 120 BPM should be 1500ms (6 eighth notes)."""
        sig = TimeSignature(6, 8)
        # At 120 BPM: quarter = 500ms, eighth = 250ms
        # 6 eighths = 6 * 250 = 1500ms
        assert bar_duration_ms(sig, 120) == 1500.0

    def test_2_4_at_120_bpm(self):
        """2/4 at 120 BPM should be 1000ms (2 quarter notes)."""
        sig = TimeSignature(2, 4)
        assert bar_duration_ms(sig, 120) == 1000.0

    def test_5_4_at_120_bpm(self):
        """5/4 at 120 BPM should be 2500ms (5 quarter notes)."""
        sig = TimeSignature(5, 4)
        assert bar_duration_ms(sig, 120) == 2500.0

    def test_7_8_at_120_bpm(self):
        """7/8 at 120 BPM should be 1750ms (7 eighth notes)."""
        sig = TimeSignature(7, 8)
        assert bar_duration_ms(sig, 120) == 1750.0

    def test_12_8_at_120_bpm(self):
        """12/8 at 120 BPM should be 3000ms (12 eighth notes)."""
        sig = TimeSignature(12, 8)
        assert bar_duration_ms(sig, 120) == 3000.0

    def test_4_4_at_60_bpm(self):
        """4/4 at 60 BPM should be 4000ms."""
        sig = TimeSignature(4, 4)
        assert bar_duration_ms(sig, 60) == 4000.0

    def test_4_4_at_240_bpm(self):
        """4/4 at 240 BPM should be 1000ms."""
        sig = TimeSignature(4, 4)
        assert bar_duration_ms(sig, 240) == 1000.0


class TestBeatInBar:
    """Tests for beat_in_bar function."""

    def test_at_downbeat(self):
        """At 0ms, should be at beat 0, fraction 0.0."""
        sig = TimeSignature(4, 4)
        beat_idx, frac = beat_in_bar(0, sig, 120)
        assert beat_idx == 0
        assert frac == 0.0

    def test_first_quarter_mark(self):
        """At 500ms (1 quarter), should be at beat 1, fraction 0.0."""
        sig = TimeSignature(4, 4)
        beat_idx, frac = beat_in_bar(500, sig, 120)
        assert beat_idx == 1
        assert frac == 0.0

    def test_half_beat(self):
        """At 750ms (1.5 quarters), should be at beat 1, fraction 0.5."""
        sig = TimeSignature(4, 4)
        beat_idx, frac = beat_in_bar(750, sig, 120)
        assert beat_idx == 1
        assert pytest.approx(frac, abs=0.01) == 0.5

    def test_third_beat(self):
        """At 1000ms (2 quarters), should be at beat 2, fraction 0.0."""
        sig = TimeSignature(4, 4)
        beat_idx, frac = beat_in_bar(1000, sig, 120)
        assert beat_idx == 2
        assert frac == 0.0

    def test_fourth_beat_half(self):
        """At 1750ms (3.5 quarters), should be at beat 3, fraction 0.5."""
        sig = TimeSignature(4, 4)
        beat_idx, frac = beat_in_bar(1750, sig, 120)
        assert beat_idx == 3
        assert pytest.approx(frac, abs=0.01) == 0.5

    def test_wraps_after_bar(self):
        """At 2000ms (full bar), should wrap to beat 0."""
        sig = TimeSignature(4, 4)
        beat_idx, frac = beat_in_bar(2000, sig, 120)
        assert beat_idx == 0
        assert frac == 0.0

    def test_3_4_signature(self):
        """3/4 bar should have 3 beats."""
        sig = TimeSignature(3, 4)
        beat_idx, frac = beat_in_bar(500, sig, 120)
        assert beat_idx == 1
        beat_idx, frac = beat_in_bar(1000, sig, 120)
        assert beat_idx == 2
        beat_idx, frac = beat_in_bar(1500, sig, 120)
        assert beat_idx == 0  # wraps

    def test_6_8_signature(self):
        """6/8 bar should have 6 beats (eighths)."""
        sig = TimeSignature(6, 8)
        # Each beat is 250ms (eighth at 120 BPM)
        beat_idx, frac = beat_in_bar(250, sig, 120)
        assert beat_idx == 1
        beat_idx, frac = beat_in_bar(1500, sig, 120)
        assert beat_idx == 0  # wraps


class TestIsDownbeat:
    """Tests for is_downbeat function."""

    def test_at_start(self):
        """At 0ms, should be a downbeat."""
        sig = TimeSignature(4, 4)
        assert is_downbeat(0, sig, 120) is True

    def test_at_bar_start_2000ms(self):
        """At exactly 2000ms (start of next bar), should be downbeat."""
        sig = TimeSignature(4, 4)
        assert is_downbeat(2000, sig, 120) is True

    def test_midway_through_bar(self):
        """At 500ms (not downbeat), should be False."""
        sig = TimeSignature(4, 4)
        assert is_downbeat(500, sig, 120) is False

    def test_near_downbeat_within_tolerance(self):
        """At 2005ms (5ms after downbeat), should be True with 10ms tolerance."""
        sig = TimeSignature(4, 4)
        assert is_downbeat(2005, sig, 120, tolerance_ms=10) is True

    def test_near_downbeat_outside_tolerance(self):
        """At 2015ms (15ms after downbeat), should be False with 10ms tolerance."""
        sig = TimeSignature(4, 4)
        assert is_downbeat(2015, sig, 120, tolerance_ms=10) is False

    def test_3_4_downbeat(self):
        """In 3/4, downbeat should occur every 1500ms."""
        sig = TimeSignature(3, 4)
        assert is_downbeat(0, sig, 120) is True
        assert is_downbeat(500, sig, 120) is False
        assert is_downbeat(1500, sig, 120) is True

    def test_custom_tolerance(self):
        """Custom tolerance should work correctly."""
        sig = TimeSignature(4, 4)
        assert is_downbeat(25, sig, 120, tolerance_ms=50) is True
        assert is_downbeat(60, sig, 120, tolerance_ms=50) is False


class TestBeatsInSeconds:
    """Tests for beats_in_seconds function."""

    def test_1_second_4_4_120bpm(self):
        """1 second at 4/4, 120 BPM should fit 2 quarter beats."""
        sig = TimeSignature(4, 4)
        assert beats_in_seconds(1.0, sig, 120) == 2

    def test_2_seconds_4_4_120bpm(self):
        """2 seconds at 4/4, 120 BPM should fit 4 quarter beats."""
        sig = TimeSignature(4, 4)
        assert beats_in_seconds(2.0, sig, 120) == 4

    def test_0_5_seconds_4_4_120bpm(self):
        """0.5 seconds at 4/4, 120 BPM should fit 1 quarter beat."""
        sig = TimeSignature(4, 4)
        assert beats_in_seconds(0.5, sig, 120) == 1

    def test_1_second_3_4_120bpm(self):
        """1 second at 3/4, 120 BPM should fit 2 quarter beats."""
        sig = TimeSignature(3, 4)
        assert beats_in_seconds(1.0, sig, 120) == 2

    def test_4_seconds_4_4_120bpm(self):
        """4 seconds at 4/4, 120 BPM should fit 8 quarter beats."""
        sig = TimeSignature(4, 4)
        assert beats_in_seconds(4.0, sig, 120) == 8


class TestBarsInSeconds:
    """Tests for bars_in_seconds function."""

    def test_2_seconds_4_4_120bpm(self):
        """2 seconds at 4/4, 120 BPM should fit 1 bar."""
        sig = TimeSignature(4, 4)
        assert bars_in_seconds(2.0, sig, 120) == 1

    def test_4_seconds_4_4_120bpm(self):
        """4 seconds at 4/4, 120 BPM should fit 2 bars."""
        sig = TimeSignature(4, 4)
        assert bars_in_seconds(4.0, sig, 120) == 2

    def test_1_second_4_4_120bpm(self):
        """1 second at 4/4, 120 BPM should fit 0 complete bars."""
        sig = TimeSignature(4, 4)
        assert bars_in_seconds(1.0, sig, 120) == 0

    def test_3_seconds_3_4_120bpm(self):
        """3 seconds at 3/4, 120 BPM should fit 2 bars (1500ms each)."""
        sig = TimeSignature(3, 4)
        assert bars_in_seconds(3.0, sig, 120) == 2

    def test_8_seconds_4_4_120bpm(self):
        """8 seconds at 4/4, 120 BPM should fit 4 bars."""
        sig = TimeSignature(4, 4)
        assert bars_in_seconds(8.0, sig, 120) == 4


class TestNextDownbeatMs:
    """Tests for next_downbeat_ms function."""

    def test_at_downbeat(self):
        """At 0ms, next downbeat is at full bar duration."""
        sig = TimeSignature(4, 4)
        assert next_downbeat_ms(0, sig, 120) == 2000.0

    def test_at_quarter_mark(self):
        """At 500ms, next downbeat is 1500ms away."""
        sig = TimeSignature(4, 4)
        assert next_downbeat_ms(500, sig, 120) == 1500.0

    def test_near_end_of_bar(self):
        """At 1999ms, next downbeat is 1ms away."""
        sig = TimeSignature(4, 4)
        assert next_downbeat_ms(1999, sig, 120) == 1.0

    def test_at_bar_boundary(self):
        """At 2000ms (next bar), should return full bar duration."""
        sig = TimeSignature(4, 4)
        assert next_downbeat_ms(2000, sig, 120) == 2000.0

    def test_3_4_signature(self):
        """In 3/4, bar is 1500ms."""
        sig = TimeSignature(3, 4)
        assert next_downbeat_ms(0, sig, 120) == 1500.0
        assert next_downbeat_ms(500, sig, 120) == 1000.0
        assert next_downbeat_ms(1500, sig, 120) == 1500.0

    def test_always_positive(self):
        """next_downbeat_ms should always return positive value."""
        sig = TimeSignature(4, 4)
        for elapsed in [0, 100, 500, 1000, 1500, 1999]:
            assert next_downbeat_ms(elapsed, sig, 120) > 0


class TestCommonSignatures:
    """Tests for COMMON_SIGNATURES list."""

    def test_has_seven_signatures(self):
        """COMMON_SIGNATURES should have 7 entries."""
        assert len(COMMON_SIGNATURES) == 7

    def test_contains_4_4(self):
        """Should contain 4/4."""
        assert TimeSignature(4, 4) in COMMON_SIGNATURES

    def test_contains_3_4(self):
        """Should contain 3/4."""
        assert TimeSignature(3, 4) in COMMON_SIGNATURES

    def test_contains_6_8(self):
        """Should contain 6/8."""
        assert TimeSignature(6, 8) in COMMON_SIGNATURES

    def test_contains_5_4(self):
        """Should contain 5/4."""
        assert TimeSignature(5, 4) in COMMON_SIGNATURES

    def test_contains_7_8(self):
        """Should contain 7/8."""
        assert TimeSignature(7, 8) in COMMON_SIGNATURES

    def test_contains_12_8(self):
        """Should contain 12/8."""
        assert TimeSignature(12, 8) in COMMON_SIGNATURES

    def test_contains_2_4(self):
        """Should contain 2/4."""
        assert TimeSignature(2, 4) in COMMON_SIGNATURES

    def test_all_are_time_signature_instances(self):
        """All entries should be TimeSignature instances."""
        for sig in COMMON_SIGNATURES:
            assert isinstance(sig, TimeSignature)
