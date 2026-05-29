"""Tests for preset chain sequencer: walk through presets at configured intervals.

Pure stdlib + dataclasses, no Qt.
"""
from __future__ import annotations

import pytest


class TestChainStep:
    """ChainStep dataclass."""

    def test_chain_step_defaults(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        step = ChainStep(preset_slug="lead")
        assert step.preset_slug == "lead"
        assert step.duration_s == 30.0
        assert step.label == ""

    def test_chain_step_with_label(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        step = ChainStep(preset_slug="pad", duration_s=60.0, label="Ambient Pad")
        assert step.preset_slug == "pad"
        assert step.duration_s == 60.0
        assert step.label == "Ambient Pad"

    def test_chain_step_clamps_duration_below(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        step = ChainStep(preset_slug="test", duration_s=0.1)
        assert step.duration_s == 0.5  # Clamped to minimum

    def test_chain_step_clamps_duration_above(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        step = ChainStep(preset_slug="test", duration_s=10000.0)
        assert step.duration_s == 3600.0  # Clamped to maximum

    def test_chain_step_to_dict(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        step = ChainStep(preset_slug="synth", duration_s=45.0, label="Lead Synth")
        d = step.to_dict()
        assert d["preset_slug"] == "synth"
        assert d["duration_s"] == 45.0
        assert d["label"] == "Lead Synth"

    def test_chain_step_from_dict(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        d = {"preset_slug": "bass", "duration_s": 30.0, "label": "Bass Line"}
        step = ChainStep.from_dict(d)
        assert step.preset_slug == "bass"
        assert step.duration_s == 30.0
        assert step.label == "Bass Line"

    def test_chain_step_from_dict_partial(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        d = {"preset_slug": "drums"}
        step = ChainStep.from_dict(d)
        assert step.preset_slug == "drums"
        assert step.duration_s == 30.0
        assert step.label == ""

    def test_chain_step_roundtrip(self):
        from gamepad_midi_bridge.preset_chain import ChainStep

        orig = ChainStep(preset_slug="Live/intro", duration_s=15.0, label="Intro")
        d = orig.to_dict()
        restored = ChainStep.from_dict(d)
        assert restored.preset_slug == orig.preset_slug
        assert restored.duration_s == orig.duration_s
        assert restored.label == orig.label


class TestPresetChainConfig:
    """PresetChainConfig dataclass."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig

        cfg = PresetChainConfig()
        assert cfg.enabled is False
        assert cfg.steps == []
        assert cfg.loop is True
        assert cfg.crossfade_ms == 0

    def test_config_with_steps(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig, ChainStep

        steps = [
            ChainStep(preset_slug="lead", duration_s=30.0),
            ChainStep(preset_slug="pad", duration_s=60.0),
        ]
        cfg = PresetChainConfig(enabled=True, steps=steps, loop=False)
        assert cfg.enabled is True
        assert len(cfg.steps) == 2
        assert cfg.loop is False

    def test_config_clamps_crossfade_below(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig

        cfg = PresetChainConfig(crossfade_ms=-100)
        assert cfg.crossfade_ms == 0

    def test_config_clamps_crossfade_above(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig

        cfg = PresetChainConfig(crossfade_ms=10000)
        assert cfg.crossfade_ms == 5000

    def test_config_to_dict_empty(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig

        cfg = PresetChainConfig()
        d = cfg.to_dict()
        assert d["enabled"] is False
        assert d["steps"] == []
        assert d["loop"] is True
        assert d["crossfade_ms"] == 0

    def test_config_to_dict_with_steps(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig, ChainStep

        steps = [
            ChainStep(preset_slug="a", duration_s=20.0, label="Step A"),
            ChainStep(preset_slug="b", duration_s=40.0, label="Step B"),
        ]
        cfg = PresetChainConfig(enabled=True, steps=steps, crossfade_ms=500)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert len(d["steps"]) == 2
        assert d["steps"][0]["preset_slug"] == "a"
        assert d["steps"][1]["preset_slug"] == "b"
        assert d["crossfade_ms"] == 500

    def test_config_from_dict_empty(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig

        d = {}
        cfg = PresetChainConfig.from_dict(d)
        assert cfg.enabled is False
        assert cfg.steps == []
        assert cfg.loop is True
        assert cfg.crossfade_ms == 0

    def test_config_from_dict_with_steps(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig

        d = {
            "enabled": True,
            "steps": [
                {"preset_slug": "lead", "duration_s": 30.0, "label": "Lead"},
                {"preset_slug": "pad", "duration_s": 60.0, "label": "Pad"},
            ],
            "loop": False,
            "crossfade_ms": 250,
        }
        cfg = PresetChainConfig.from_dict(d)
        assert cfg.enabled is True
        assert len(cfg.steps) == 2
        assert cfg.steps[0].preset_slug == "lead"
        assert cfg.steps[1].preset_slug == "pad"
        assert cfg.loop is False
        assert cfg.crossfade_ms == 250

    def test_config_roundtrip(self):
        from gamepad_midi_bridge.preset_chain import PresetChainConfig, ChainStep

        orig = PresetChainConfig(
            enabled=True,
            steps=[
                ChainStep(preset_slug="a", duration_s=10.0, label="A"),
                ChainStep(preset_slug="b", duration_s=20.0, label="B"),
            ],
            loop=False,
            crossfade_ms=333,
        )
        d = orig.to_dict()
        restored = PresetChainConfig.from_dict(d)
        assert restored.enabled == orig.enabled
        assert len(restored.steps) == len(orig.steps)
        assert restored.steps[0].preset_slug == orig.steps[0].preset_slug
        assert restored.steps[1].preset_slug == orig.steps[1].preset_slug
        assert restored.loop == orig.loop
        assert restored.crossfade_ms == orig.crossfade_ms


class TestPresetChain:
    """PresetChain sequencer state machine."""

    def test_chain_empty_start_returns_none(self):
        from gamepad_midi_bridge.preset_chain import PresetChain, PresetChainConfig

        cfg = PresetChainConfig()
        chain = PresetChain(cfg=cfg)
        result = chain.start(0.0)
        assert result is None

    def test_chain_empty_current_returns_none(self):
        from gamepad_midi_bridge.preset_chain import PresetChain, PresetChainConfig

        cfg = PresetChainConfig()
        chain = PresetChain(cfg=cfg)
        assert chain.current() is None

    def test_chain_one_step_start_returns_slug(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[ChainStep(preset_slug="lead", duration_s=30.0)]
        )
        chain = PresetChain(cfg=cfg)
        result = chain.start(0.0)
        assert result == "lead"

    def test_chain_one_step_tick_before_duration_returns_none(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[ChainStep(preset_slug="lead", duration_s=30.0)]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)
        result = chain.tick(15.0)  # 15 seconds in, 30 second step
        assert result is None

    def test_chain_three_steps_advances_on_duration(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[
                ChainStep(preset_slug="a", duration_s=10.0),
                ChainStep(preset_slug="b", duration_s=20.0),
                ChainStep(preset_slug="c", duration_s=15.0),
            ]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        # At 5 seconds, still in step a
        assert chain.tick(5.0) is None
        assert chain.current().preset_slug == "a"

        # At 10 seconds, step a complete, advance to b
        result = chain.tick(10.0)
        assert result == "b"
        assert chain.current().preset_slug == "b"

        # At 20 seconds, still in step b
        assert chain.tick(20.0) is None

        # At 30 seconds, step b complete, advance to c
        result = chain.tick(30.0)
        assert result == "c"
        assert chain.current().preset_slug == "c"

    def test_chain_loop_true_wraps_to_zero(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            loop=True,
            steps=[
                ChainStep(preset_slug="a", duration_s=10.0),
                ChainStep(preset_slug="b", duration_s=10.0),
            ],
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        # Complete step a
        chain.tick(10.0)
        assert chain.current().preset_slug == "b"

        # Complete step b, should wrap to a
        result = chain.tick(20.0)
        assert result == "a"
        assert chain.current().preset_slug == "a"

    def test_chain_loop_false_stays_on_last(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            loop=False,
            steps=[
                ChainStep(preset_slug="a", duration_s=10.0),
                ChainStep(preset_slug="b", duration_s=10.0),
            ],
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        # Complete step a
        chain.tick(10.0)
        assert chain.current().preset_slug == "b"

        # Try to complete step b, should stay on b (no advance)
        result = chain.tick(20.0)
        assert result is None  # No advance
        assert chain.current().preset_slug == "b"

        # Much later, still on b
        chain.tick(100.0)
        assert chain.current().preset_slug == "b"

    def test_chain_current_returns_active_step(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[
                ChainStep(preset_slug="x", duration_s=5.0),
                ChainStep(preset_slug="y", duration_s=10.0),
            ]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        assert chain.current().preset_slug == "x"
        chain.advance(5.0)
        assert chain.current().preset_slug == "y"

    def test_chain_advance_explicit_jump(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            loop=True,
            steps=[
                ChainStep(preset_slug="a", duration_s=10.0),
                ChainStep(preset_slug="b", duration_s=10.0),
                ChainStep(preset_slug="c", duration_s=10.0),
            ],
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)
        assert chain.current().preset_slug == "a"

        # Manually advance
        result = chain.advance(5.0)
        assert result == "b"
        assert chain.current().preset_slug == "b"

        # Advance again
        result = chain.advance(7.0)
        assert result == "c"
        assert chain.current().preset_slug == "c"

    def test_chain_reset_clears_state(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[
                ChainStep(preset_slug="a", duration_s=10.0),
                ChainStep(preset_slug="b", duration_s=20.0),
            ]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)
        chain.advance(10.0)

        assert chain.current().preset_slug == "b"
        assert chain._index == 1

        chain.reset()
        assert chain._index == 0
        assert chain._started_at is None
        assert chain._step_started_at is None
        assert chain.current().preset_slug == "a"

    def test_chain_progress_at_start_is_zero(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[ChainStep(preset_slug="a", duration_s=10.0)]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        p = chain.progress(0.0)
        assert p == 0.0

    def test_chain_progress_at_half_duration(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[ChainStep(preset_slug="a", duration_s=10.0)]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        p = chain.progress(5.0)
        assert abs(p - 0.5) < 0.001

    def test_chain_progress_at_end_is_one(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[ChainStep(preset_slug="a", duration_s=10.0)]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        p = chain.progress(10.0)
        assert p == 1.0

    def test_chain_progress_past_end_clamped_to_one(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[ChainStep(preset_slug="a", duration_s=10.0)]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        p = chain.progress(100.0)
        assert p == 1.0

    def test_chain_remaining_decreases_over_time(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[ChainStep(preset_slug="a", duration_s=10.0)]
        )
        chain = PresetChain(cfg=cfg)
        chain.start(0.0)

        remaining_0 = chain.remaining_s(0.0)
        assert remaining_0 == 10.0

        remaining_5 = chain.remaining_s(5.0)
        assert remaining_5 == 5.0

        remaining_10 = chain.remaining_s(10.0)
        assert remaining_10 == 0.0

    def test_chain_total_duration_sums_correctly(self):
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            steps=[
                ChainStep(preset_slug="a", duration_s=10.0),
                ChainStep(preset_slug="b", duration_s=20.0),
                ChainStep(preset_slug="c", duration_s=15.0),
            ]
        )
        chain = PresetChain(cfg=cfg)

        total = chain.total_duration_s()
        assert total == 45.0

    def test_chain_total_duration_empty(self):
        from gamepad_midi_bridge.preset_chain import PresetChain, PresetChainConfig

        cfg = PresetChainConfig()
        chain = PresetChain(cfg=cfg)

        total = chain.total_duration_s()
        assert total == 0.0

    def test_chain_realistic_scenario(self):
        """Simulate a realistic 3-step chain sequence."""
        from gamepad_midi_bridge.preset_chain import (
            PresetChain,
            PresetChainConfig,
            ChainStep,
        )

        cfg = PresetChainConfig(
            enabled=True,
            steps=[
                ChainStep(preset_slug="intro", duration_s=2.0, label="Intro"),
                ChainStep(preset_slug="main", duration_s=3.0, label="Main"),
                ChainStep(preset_slug="outro", duration_s=2.0, label="Outro"),
            ],
            loop=False,
        )
        chain = PresetChain(cfg=cfg)

        # Start at t=0
        assert chain.start(0.0) == "intro"
        assert chain.progress(0.0) == 0.0
        assert chain.remaining_s(0.0) == 2.0

        # Partway through intro at t=1
        assert chain.tick(1.0) is None
        assert chain.progress(1.0) == 0.5

        # Intro complete, advance to main at t=2
        assert chain.tick(2.0) == "main"
        assert chain.current().preset_slug == "main"

        # Partway through main at t=3.5
        assert chain.tick(3.5) is None
        assert abs(chain.progress(3.5) - (1.5 / 3.0)) < 0.001

        # Main complete, advance to outro at t=5
        assert chain.tick(5.0) == "outro"
        assert chain.current().preset_slug == "outro"

        # Outro complete at t=7, no advance (loop=False)
        assert chain.tick(7.0) is None
        assert chain.current().preset_slug == "outro"

        # Total duration is correct
        assert chain.total_duration_s() == 7.0

    def test_chain_progress_no_current_step(self):
        from gamepad_midi_bridge.preset_chain import PresetChain, PresetChainConfig

        cfg = PresetChainConfig()
        chain = PresetChain(cfg=cfg)

        p = chain.progress(0.0)
        assert p == 0.0

    def test_chain_remaining_no_current_step(self):
        from gamepad_midi_bridge.preset_chain import PresetChain, PresetChainConfig

        cfg = PresetChainConfig()
        chain = PresetChain(cfg=cfg)

        r = chain.remaining_s(0.0)
        assert r is None

    def test_chain_advance_empty_returns_none(self):
        from gamepad_midi_bridge.preset_chain import PresetChain, PresetChainConfig

        cfg = PresetChainConfig()
        chain = PresetChain(cfg=cfg)

        result = chain.advance(0.0)
        assert result is None
