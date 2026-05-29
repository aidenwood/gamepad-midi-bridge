"""Tests for the chord_progression module — cycle through chord shapes on demand or timer.

Pure stdlib implementation for stateful chord progressions. Tests cover:
- Empty progression handling
- Single and multi-step firing and wrapping
- Loop vs. non-loop behavior
- Manual advance and reset
- Auto-advance with tick()
- Configuration serialization and clamping
- MIDI note/velocity/channel/label preservation
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import chord_progression as cp


class TestChordStepSerialization:
    """ChordStep to_dict / from_dict round-trip."""

    def test_chord_step_round_trip_preserves_notes_velocity_channel_label(self):
        """Serialize and deserialize a ChordStep preserves all fields."""
        step = cp.ChordStep(
            notes=[60, 64, 67],
            velocity=100,
            channel=1,
            label="Cmaj",
        )
        data = step.to_dict()
        restored = cp.ChordStep.from_dict(data)
        assert restored.notes == [60, 64, 67]
        assert restored.velocity == 100
        assert restored.channel == 1
        assert restored.label == "Cmaj"

    def test_chord_step_round_trip_with_none_channel(self):
        """Serializing with channel=None preserves None."""
        step = cp.ChordStep(notes=[60, 64, 67], velocity=100, channel=None, label="Cmaj")
        data = step.to_dict()
        restored = cp.ChordStep.from_dict(data)
        assert restored.channel is None

    def test_chord_step_velocity_clamped_on_deserialize(self):
        """Velocity outside 1..127 is clamped."""
        data = {"notes": [60], "velocity": 200, "channel": None, "label": "test"}
        step = cp.ChordStep.from_dict(data)
        assert step.velocity == 127

        data = {"notes": [60], "velocity": 0, "channel": None, "label": "test"}
        step = cp.ChordStep.from_dict(data)
        assert step.velocity == 1

    def test_chord_step_notes_clamped_on_deserialize(self):
        """Notes outside 0..127 are clamped."""
        data = {"notes": [-1, 60, 200], "velocity": 100, "channel": None, "label": "test"}
        step = cp.ChordStep.from_dict(data)
        assert step.notes == [0, 60, 127]

    def test_chord_step_channel_clamped_on_deserialize(self):
        """Channel outside 1..16 (or None) is clamped."""
        data = {"notes": [60], "velocity": 100, "channel": 20, "label": "test"}
        step = cp.ChordStep.from_dict(data)
        assert step.channel == 16

        data = {"notes": [60], "velocity": 100, "channel": 0, "label": "test"}
        step = cp.ChordStep.from_dict(data)
        assert step.channel == 1


class TestChordProgressionConfigSerialization:
    """ChordProgressionConfig to_dict / from_dict round-trip."""

    def test_config_round_trip_preserves_steps_and_settings(self):
        """Serialize and deserialize config preserves steps and settings."""
        cfg = cp.ChordProgressionConfig(
            enabled=True,
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
            loop=False,
            auto_advance_ms=1000,
        )
        data = cfg.to_dict()
        restored = cp.ChordProgressionConfig.from_dict(data)
        assert restored.enabled is True
        assert len(restored.steps) == 2
        assert restored.steps[0].label == "Cmaj"
        assert restored.steps[1].label == "Fmaj"
        assert restored.loop is False
        assert restored.auto_advance_ms == 1000

    def test_config_auto_advance_ms_clamped_on_deserialize(self):
        """auto_advance_ms outside 0..60000 is clamped."""
        data = {
            "enabled": True,
            "steps": [],
            "loop": True,
            "auto_advance_ms": 100000,
        }
        cfg = cp.ChordProgressionConfig.from_dict(data)
        assert cfg.auto_advance_ms == 60000

        data["auto_advance_ms"] = -100
        cfg = cp.ChordProgressionConfig.from_dict(data)
        assert cfg.auto_advance_ms == 0


class TestChordProgressionEmptySteps:
    """Empty progression behavior."""

    def test_empty_progression_current_returns_none(self):
        """No steps → current() returns None."""
        cfg = cp.ChordProgressionConfig(steps=[])
        prog = cp.ChordProgression(cfg)
        assert prog.current() is None

    def test_empty_progression_fire_returns_none(self):
        """No steps → fire() returns None without advancing."""
        cfg = cp.ChordProgressionConfig(steps=[])
        prog = cp.ChordProgression(cfg)
        result = prog.fire(0.0)
        assert result is None

    def test_empty_progression_advance_does_nothing(self):
        """No steps → advance() is a no-op."""
        cfg = cp.ChordProgressionConfig(steps=[])
        prog = cp.ChordProgression(cfg)
        prog.advance()
        assert prog.index == 0


class TestChordProgressionSingleStep:
    """Single-step progression behavior."""

    def test_single_step_fire_returns_same_step_when_loop_true(self):
        """Single step with loop=True → fire returns step, stays on step 0."""
        step = cp.ChordStep(notes=[60, 64, 67], label="Cmaj")
        cfg = cp.ChordProgressionConfig(steps=[step], loop=True)
        prog = cp.ChordProgression(cfg)
        result1 = prog.fire(0.0)
        assert result1.label == "Cmaj"
        assert prog.index == 0  # Still on step 0 (wrapped)
        result2 = prog.fire(0.1)
        assert result2.label == "Cmaj"
        assert prog.index == 0

    def test_single_step_fire_returns_same_step_when_loop_false(self):
        """Single step with loop=False → fire returns step, stays on step 0."""
        step = cp.ChordStep(notes=[60, 64, 67], label="Cmaj")
        cfg = cp.ChordProgressionConfig(steps=[step], loop=False)
        prog = cp.ChordProgression(cfg)
        result1 = prog.fire(0.0)
        assert result1.label == "Cmaj"
        assert prog.index == 0  # Can't advance beyond single step


class TestChordProgressionMultiStep:
    """Multi-step progression and wrapping."""

    def test_three_step_progression_fires_in_order_then_wraps_with_loop_true(self):
        """3 steps with loop=True → fires 0, 1, 2, then 0 again."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
                cp.ChordStep(notes=[67, 71, 74], label="Gmaj"),
            ],
            loop=True,
        )
        prog = cp.ChordProgression(cfg)

        # Fire and check sequence
        assert prog.fire(0.0).label == "Cmaj"
        assert prog.index == 1
        assert prog.fire(0.1).label == "Fmaj"
        assert prog.index == 2
        assert prog.fire(0.2).label == "Gmaj"
        assert prog.index == 0  # Wrapped
        assert prog.fire(0.3).label == "Cmaj"
        assert prog.index == 1

    def test_three_step_progression_stays_on_last_with_loop_false(self):
        """3 steps with loop=False → fires 0, 1, 2, then stays on 2."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
                cp.ChordStep(notes=[67, 71, 74], label="Gmaj"),
            ],
            loop=False,
        )
        prog = cp.ChordProgression(cfg)

        assert prog.fire(0.0).label == "Cmaj"
        assert prog.index == 1
        assert prog.fire(0.1).label == "Fmaj"
        assert prog.index == 2
        assert prog.fire(0.2).label == "Gmaj"
        assert prog.index == 2  # Stayed on last
        assert prog.fire(0.3).label == "Gmaj"
        assert prog.index == 2  # Still on last


class TestChordProgressionAdvance:
    """Manual advance() without firing."""

    def test_advance_moves_to_next_step(self):
        """advance() shifts index without returning a step."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
            loop=True,
        )
        prog = cp.ChordProgression(cfg)
        assert prog.index == 0
        prog.advance()
        assert prog.index == 1
        prog.advance()
        assert prog.index == 0  # Wrapped

    def test_advance_respects_loop_false(self):
        """advance() with loop=False stays on last step."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
            loop=False,
        )
        prog = cp.ChordProgression(cfg)
        prog.advance()
        assert prog.index == 1
        prog.advance()
        assert prog.index == 1  # Stayed on last


class TestChordProgressionReset:
    """Reset to initial state."""

    def test_reset_returns_index_to_zero(self):
        """reset() sets index to 0."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
                cp.ChordStep(notes=[67, 71, 74], label="Gmaj"),
            ],
        )
        prog = cp.ChordProgression(cfg)
        prog.fire(0.0)
        prog.fire(0.1)
        assert prog.index == 2
        prog.reset()
        assert prog.index == 0

    def test_reset_clears_last_fired_at(self):
        """reset() sets last_fired_at to None."""
        cfg = cp.ChordProgressionConfig(
            steps=[cp.ChordStep(notes=[60, 64, 67], label="Cmaj")],
        )
        prog = cp.ChordProgression(cfg)
        prog.fire(1.5)
        assert prog.last_fired_at == 1.5
        prog.reset()
        assert prog.last_fired_at is None


class TestChordProgressionTick:
    """Auto-advance via tick()."""

    def test_tick_returns_none_if_auto_advance_ms_is_zero(self):
        """auto_advance_ms=0 → tick() always returns None (manual only)."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
            auto_advance_ms=0,
        )
        prog = cp.ChordProgression(cfg)
        prog.fire(0.0)
        result = prog.tick(10.0)  # 10 seconds later
        assert result is None
        assert prog.index == 1  # Didn't advance

    def test_tick_returns_none_if_last_fired_at_is_none(self):
        """last_fired_at is None → tick() returns None."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
            auto_advance_ms=1000,
        )
        prog = cp.ChordProgression(cfg)
        # Never fired, so last_fired_at is None
        result = prog.tick(1.0)
        assert result is None

    def test_tick_advances_when_timeout_elapses(self):
        """After auto_advance_ms elapses, tick() advances and returns new index."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
                cp.ChordStep(notes=[67, 71, 74], label="Gmaj"),
            ],
            auto_advance_ms=1000,  # 1 second
        )
        prog = cp.ChordProgression(cfg)
        prog.fire(0.0)  # last_fired_at = 0.0, index = 1
        assert prog.index == 1

        # 0.5s later, not enough time
        result = prog.tick(0.5)
        assert result is None
        assert prog.index == 1

        # 1.0s later, timeout reached
        result = prog.tick(1.0)
        assert result == 2  # Returns new index
        assert prog.index == 2
        assert prog.last_fired_at == 1.0

    def test_tick_updates_last_fired_at_after_advance(self):
        """tick() updates last_fired_at when advancing."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
            auto_advance_ms=500,
        )
        prog = cp.ChordProgression(cfg)
        prog.fire(0.0)
        assert prog.last_fired_at == 0.0

        prog.tick(0.5)
        assert prog.last_fired_at == 0.5

    def test_tick_multiple_auto_advances_in_sequence(self):
        """Multiple ticks with adequate spacing advance through sequence."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
                cp.ChordStep(notes=[67, 71, 74], label="Gmaj"),
            ],
            auto_advance_ms=1000,
            loop=True,
        )
        prog = cp.ChordProgression(cfg)
        prog.fire(0.0)  # index = 1

        prog.tick(1.0)  # Advance
        assert prog.index == 2

        prog.tick(2.0)  # Advance
        assert prog.index == 0  # Wrapped

        prog.tick(3.0)  # Advance
        assert prog.index == 1


class TestChordProgressionCurrent:
    """current() method."""

    def test_current_returns_step_at_index(self):
        """current() returns the ChordStep at current index."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
        )
        prog = cp.ChordProgression(cfg)
        assert prog.current().label == "Cmaj"
        prog.advance()
        assert prog.current().label == "Fmaj"

    def test_current_returns_none_if_steps_empty(self):
        """current() with no steps returns None."""
        cfg = cp.ChordProgressionConfig(steps=[])
        prog = cp.ChordProgression(cfg)
        assert prog.current() is None


class TestChordProgressionEdgeCases:
    """Edge cases and integration tests."""

    def test_fire_updates_last_fired_at(self):
        """fire() updates last_fired_at to now_s."""
        cfg = cp.ChordProgressionConfig(
            steps=[cp.ChordStep(notes=[60, 64, 67], label="Cmaj")],
        )
        prog = cp.ChordProgression(cfg)
        assert prog.last_fired_at is None
        prog.fire(0.5)
        assert prog.last_fired_at == 0.5
        prog.fire(1.5)
        assert prog.last_fired_at == 1.5

    def test_default_chord_step_has_empty_notes(self):
        """ChordStep with no args has empty notes list."""
        step = cp.ChordStep()
        assert step.notes == []
        assert step.velocity == 100
        assert step.channel is None
        assert step.label == ""

    def test_default_config_has_disabled_progression(self):
        """ChordProgressionConfig defaults to enabled=False."""
        cfg = cp.ChordProgressionConfig()
        assert cfg.enabled is False
        assert cfg.steps == []
        assert cfg.loop is True
        assert cfg.auto_advance_ms == 0

    def test_progression_with_many_steps(self):
        """Progression with 12 steps (chromatic scale) works."""
        steps = [
            cp.ChordStep(notes=[60 + i], label=f"step_{i}") for i in range(12)
        ]
        cfg = cp.ChordProgressionConfig(steps=steps, loop=True)
        prog = cp.ChordProgression(cfg)

        for i in range(12):
            step = prog.fire(0.0)
            assert step.label == f"step_{i}"

        # One more fire should wrap
        step = prog.fire(0.0)
        assert step.label == "step_0"

    def test_fire_before_tick_establishes_auto_advance_baseline(self):
        """tick() after fire() uses fire's timestamp as baseline."""
        cfg = cp.ChordProgressionConfig(
            steps=[
                cp.ChordStep(notes=[60, 64, 67], label="Cmaj"),
                cp.ChordStep(notes=[65, 69, 72], label="Fmaj"),
            ],
            auto_advance_ms=1000,
        )
        prog = cp.ChordProgression(cfg)
        prog.fire(5.0)  # last_fired_at = 5.0
        assert prog.index == 1

        prog.tick(5.5)  # Only 0.5s elapsed
        assert prog.index == 1  # Not yet

        prog.tick(6.0)  # 1.0s elapsed
        assert prog.index == 0  # Advanced
