"""Tests for Euclidean rhythm generator (Bjorklund's algorithm).

15+ test cases covering edge cases, classic patterns, rotation, density, and
stateless step advancement.
"""

import pytest
from dataclasses import asdict

from gamepad_midi_bridge.euclidean import (
    bjorklund,
    rotate,
    density,
    EuclideanPattern,
)


class TestBjorklund:
    """Test Bjorklund's algorithm for Euclidean rhythm generation."""

    def test_tresillo_pattern(self):
        """E(3, 8) = [1,0,0,1,0,0,1,0] (classic tresillo rhythm)."""
        assert bjorklund(3, 8) == [1, 0, 0, 1, 0, 0, 1, 0]

    def test_cuban_cinquillo_pattern(self):
        """E(5, 8) = [1,0,1,0,1,0,1,1] (evenly distributed 5 pulses over 8 steps)."""
        assert bjorklund(5, 8) == [1, 0, 1, 0, 1, 0, 1, 1]

    def test_four_on_floor(self):
        """E(4, 4) = [1,1,1,1] (four on the floor, all pulses)."""
        assert bjorklund(4, 4) == [1, 1, 1, 1]

    def test_all_zeros(self):
        """E(0, 8) = [0,0,0,0,0,0,0,0] (no pulses)."""
        assert bjorklund(0, 8) == [0, 0, 0, 0, 0, 0, 0, 0]

    def test_clamp_pulses_to_steps(self):
        """E(8, 4) = [1,1,1,1] (pulses >= steps clamps to all 1s)."""
        assert bjorklund(8, 4) == [1, 1, 1, 1]

    def test_single_pulse(self):
        """E(1, 8) = [1,0,0,0,0,0,0,0] (single pulse)."""
        assert bjorklund(1, 8) == [1, 0, 0, 0, 0, 0, 0, 0]

    def test_half_filled(self):
        """E(4, 8) = [1,0,1,0,1,0,1,0] (half filled, evenly distributed)."""
        result = bjorklund(4, 8)
        assert result == [1, 0, 1, 0, 1, 0, 1, 0]

    def test_negative_pulses_invalid(self):
        """E(-1, 8) returns [] (invalid: negative pulses)."""
        assert bjorklund(-1, 8) == []

    def test_zero_steps_invalid(self):
        """E(3, 0) returns [] (invalid: zero steps)."""
        assert bjorklund(3, 0) == []

    def test_negative_steps_invalid(self):
        """E(3, -1) returns [] (invalid: negative steps)."""
        assert bjorklund(3, -1) == []

    def test_length_correctness(self):
        """Returned pattern always has length = steps."""
        for steps in [1, 4, 8, 16, 32]:
            for pulses in [0, steps // 2, steps]:
                result = bjorklund(pulses, steps)
                assert len(result) == steps


class TestRotate:
    """Test rhythm rotation by offset."""

    def test_rotate_right_by_one(self):
        """rotate([1,0,0,1,0,0,1,0], 1) shifts right by 1."""
        pattern = [1, 0, 0, 1, 0, 0, 1, 0]
        assert rotate(pattern, 1) == [0, 1, 0, 0, 1, 0, 0, 1]

    def test_rotate_left_by_one(self):
        """rotate with negative offset shifts left."""
        pattern = [1, 0, 0, 1, 0, 0, 1, 0]
        assert rotate(pattern, -1) == [0, 0, 1, 0, 0, 1, 0, 1]

    def test_rotate_by_zero(self):
        """rotate(..., 0) returns unchanged pattern."""
        pattern = [1, 0, 0, 1]
        assert rotate(pattern, 0) == [1, 0, 0, 1]

    def test_rotate_full_cycle(self):
        """rotate by full length returns original pattern."""
        pattern = [1, 0, 0, 1, 0, 0, 1, 0]
        assert rotate(pattern, 8) == pattern

    def test_rotate_wraps_negative(self):
        """Negative offsets wrap around correctly."""
        pattern = [1, 0, 0, 1]
        # -1 is same as 3 (rotate right by 3)
        assert rotate(pattern, -1) == rotate(pattern, 3)

    def test_rotate_empty_pattern(self):
        """rotate([], offset) returns []."""
        assert rotate([], 1) == []
        assert rotate([], -1) == []

    def test_rotate_preserves_length(self):
        """Rotation always preserves pattern length."""
        pattern = [1, 0, 1, 0, 1, 0]
        for offset in range(-10, 11):
            assert len(rotate(pattern, offset)) == len(pattern)


class TestDensity:
    """Test rhythm fill density calculation."""

    def test_half_filled(self):
        """density([1,0,1,0]) = 0.5."""
        assert density([1, 0, 1, 0]) == 0.5

    def test_full_filled(self):
        """density([1,1,1,1]) = 1.0."""
        assert density([1, 1, 1, 1]) == 1.0

    def test_empty_filled(self):
        """density([0,0,0,0]) = 0.0."""
        assert density([0, 0, 0, 0]) == 0.0

    def test_one_third_filled(self):
        """density([1,0,0,1,0,0,1,0,0]) ≈ 0.333."""
        result = density([1, 0, 0, 1, 0, 0, 1, 0, 0])
        assert abs(result - 1 / 3) < 0.001

    def test_empty_pattern(self):
        """density([]) = 0.0."""
        assert density([]) == 0.0

    def test_single_pulse(self):
        """density([1,0,0,0]) = 0.25."""
        assert density([1, 0, 0, 0]) == 0.25


class TestEuclideanPattern:
    """Test EuclideanPattern dataclass and methods."""

    def test_create_pattern(self):
        """Create a basic EuclideanPattern."""
        pattern = EuclideanPattern(pulses=3, steps=8)
        assert pattern.pulses == 3
        assert pattern.steps == 8
        assert pattern.rotation == 0
        assert pattern.note == 60
        assert pattern.velocity == 100
        assert pattern.channel == 1

    def test_custom_midi_params(self):
        """EuclideanPattern accepts custom MIDI parameters."""
        pattern = EuclideanPattern(
            pulses=5,
            steps=16,
            rotation=2,
            note=72,
            velocity=80,
            channel=3,
        )
        assert pattern.note == 72
        assert pattern.velocity == 80
        assert pattern.channel == 3

    def test_to_steps_no_rotation(self):
        """to_steps() with no rotation returns base Bjorklund."""
        pattern = EuclideanPattern(pulses=3, steps=8, rotation=0)
        assert pattern.to_steps() == [1, 0, 0, 1, 0, 0, 1, 0]

    def test_to_steps_with_rotation(self):
        """to_steps() applies rotation to base pattern."""
        pattern = EuclideanPattern(pulses=3, steps=8, rotation=1)
        base = [1, 0, 0, 1, 0, 0, 1, 0]
        expected = [0, 1, 0, 0, 1, 0, 0, 1]  # base rotated right by 1
        assert pattern.to_steps() == expected

    def test_to_steps_respects_pulses_steps(self):
        """to_steps() uses pulses and steps, not defaults."""
        p1 = EuclideanPattern(pulses=5, steps=8)
        p2 = EuclideanPattern(pulses=4, steps=8)
        assert p1.to_steps() != p2.to_steps()

    def test_next_step_fires_on_pulse(self):
        """next_step(0) on tresillo fires (step 0 has pulse)."""
        pattern = EuclideanPattern(pulses=3, steps=8, rotation=0)
        fires, next_step = pattern.next_step(0)
        assert fires is True
        assert next_step == 1

    def test_next_step_silent_on_rest(self):
        """next_step(1) on tresillo is silent (step 1 is rest)."""
        pattern = EuclideanPattern(pulses=3, steps=8, rotation=0)
        fires, next_step = pattern.next_step(1)
        assert fires is False
        assert next_step == 2

    def test_next_step_wraps(self):
        """next_step(7) on 8-step pattern wraps to 0."""
        pattern = EuclideanPattern(pulses=3, steps=8)
        fires, next_step = pattern.next_step(7)
        assert next_step == 0

    def test_next_step_sequence(self):
        """next_step advances through pattern sequentially."""
        pattern = EuclideanPattern(pulses=4, steps=4)  # [1,1,1,1]
        current = 0
        for expected_fires in [True, True, True, True]:
            fires, current = pattern.next_step(current)
            assert fires is expected_fires

    def test_next_step_wraps_sequence(self):
        """next_step on tresillo completes full cycle and wraps."""
        pattern = EuclideanPattern(pulses=3, steps=8)
        expected_pattern = [1, 0, 0, 1, 0, 0, 1, 0]

        current = 0
        for expected_pulse in expected_pattern:
            fires, current = pattern.next_step(current)
            assert fires is bool(expected_pulse)

        # After full cycle, wraps to 0
        assert current == 0

    def test_asdict_roundtrip(self):
        """EuclideanPattern can be serialized via asdict."""
        original = EuclideanPattern(
            pulses=5, steps=16, rotation=3, note=64, velocity=90, channel=2
        )
        data = asdict(original)
        reconstructed = EuclideanPattern(**data)
        assert reconstructed == original

    def test_stateless_next_step(self):
        """next_step is stateless: same input always gives same output."""
        pattern = EuclideanPattern(pulses=3, steps=8)
        fires1, next1 = pattern.next_step(0)
        fires2, next2 = pattern.next_step(0)
        assert fires1 == fires2 and next1 == next2


class TestIntegration:
    """Integration tests for full Euclidean workflow."""

    def test_classic_patterns_play_correctly(self):
        """Classic patterns generate expected rhythms."""
        tresillo = EuclideanPattern(3, 8)
        cinquillo = EuclideanPattern(5, 8)
        assert tresillo.to_steps() == [1, 0, 0, 1, 0, 0, 1, 0]
        assert cinquillo.to_steps() == [1, 0, 1, 0, 1, 0, 1, 1]

    def test_rotation_changes_phase(self):
        """Rotating pattern changes phase without changing density."""
        p0 = EuclideanPattern(3, 8, rotation=0)
        p1 = EuclideanPattern(3, 8, rotation=1)
        p2 = EuclideanPattern(3, 8, rotation=2)

        d0 = density(p0.to_steps())
        d1 = density(p1.to_steps())
        d2 = density(p2.to_steps())

        # Density unchanged by rotation
        assert abs(d0 - d1) < 0.001
        assert abs(d1 - d2) < 0.001

        # But patterns are different
        assert p0.to_steps() != p1.to_steps()
        assert p1.to_steps() != p2.to_steps()

    def test_midi_metadata_preserved(self):
        """MIDI metadata (note, velocity, channel) independent of rhythm."""
        p1 = EuclideanPattern(3, 8, note=60, velocity=100, channel=1)
        p2 = EuclideanPattern(3, 8, note=72, velocity=80, channel=3)

        # Same rhythm
        assert p1.to_steps() == p2.to_steps()

        # Different MIDI
        assert p1.note != p2.note
        assert p1.velocity != p2.velocity
        assert p1.channel != p2.channel

    def test_play_through_full_pattern(self):
        """Simulate playing through a pattern multiple times."""
        pattern = EuclideanPattern(3, 8)
        rhythm = pattern.to_steps()

        current = 0
        played_notes = []
        for _ in range(16):  # Play twice through
            fires, current = pattern.next_step(current)
            if fires:
                played_notes.append(current - 1)

        # Should have 6 fires in 16 steps (3 fires per 8 steps, twice)
        assert len(played_notes) == 6
