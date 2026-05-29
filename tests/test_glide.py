"""Glide/portamento helper tests."""
from __future__ import annotations

import math

import pytest

from gamepad_midi_bridge.glide import Glider, GlideConfig


def test_first_set_target_snaps_current():
    """First set_target snaps current to target."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(100, 0.0)
    assert g.value_at(0.0) == 100


def test_second_set_target_glides():
    """Second set_target with glide_time 1.0: value_at midway returns midpoint."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    # At midpoint (t=0.5), progress=0.5, so value should be ~50.
    value = g.value_at(0.5)
    assert value is not None
    assert abs(value - 50.0) < 0.01


def test_glide_disabled_snaps_immediately():
    """Disabled config: value_at returns target immediately."""
    cfg = GlideConfig(enabled=False, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    assert g.value_at(0.5) == 100


def test_glide_time_zero_snaps_immediately():
    """glide_time = 0: value_at returns target immediately."""
    cfg = GlideConfig(enabled=True, glide_time_s=0.0)
    g = Glider(cfg)
    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    assert g.value_at(0.5) == 100


def test_is_settled_after_duration():
    """is_settled True after glide duration elapsed."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    assert not g.is_settled(0.5)
    assert g.is_settled(1.0)
    assert g.is_settled(1.5)


def test_is_settled_during_glide():
    """is_settled False during glide."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    assert not g.is_settled(0.1)
    assert not g.is_settled(0.5)
    assert not g.is_settled(0.99)


def test_exponential_mode_faster_initial():
    """Exponential mode reaches target asymptotically — closer at progress=0.5 than linear."""
    cfg_exp = GlideConfig(enabled=True, glide_time_s=1.0, mode="exponential")
    cfg_lin = GlideConfig(enabled=True, glide_time_s=1.0, mode="linear")
    g_exp = Glider(cfg_exp)
    g_lin = Glider(cfg_lin)

    g_exp.set_target(0, 0.0)
    g_exp.set_target(100, 0.0)

    g_lin.set_target(0, 0.0)
    g_lin.set_target(100, 0.0)

    val_exp = g_exp.value_at(0.5)
    val_lin = g_lin.value_at(0.5)

    assert val_exp is not None and val_lin is not None
    # Exponential should reach target faster at 0.5.
    assert val_exp > val_lin


def test_snap_jumps_immediately():
    """snap() jumps immediately."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    g.snap(50)
    assert g.value_at(0.5) == 50
    assert g.is_settled(0.5)


def test_reset_clears_state():
    """reset() clears state."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    g.reset()
    assert g.current is None
    assert g.target is None
    assert g.source_value is None
    assert g.target_set_at is None
    assert g.value_at(0.5) is None


def test_clamp_glide_time_too_low():
    """glide_time -1 → 0.001."""
    cfg = GlideConfig(glide_time_s=-1.0)
    assert cfg.glide_time_s == 0.001


def test_clamp_glide_time_too_high():
    """glide_time 10 → 5.0."""
    cfg = GlideConfig(glide_time_s=10.0)
    assert cfg.glide_time_s == 5.0


def test_roundtrip_serialization():
    """to_dict / from_dict round-trip."""
    cfg1 = GlideConfig(enabled=True, glide_time_s=0.5, mode="exponential")
    d = cfg1.to_dict()
    cfg2 = GlideConfig.from_dict(d)
    assert cfg2.enabled == cfg1.enabled
    assert cfg2.glide_time_s == cfg1.glide_time_s
    assert cfg2.mode == cfg1.mode


def test_descending_glide():
    """Descending glide (target < source) interpolates correctly."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(100, 0.0)
    g.set_target(0, 0.0)
    value = g.value_at(0.5)
    assert value is not None
    assert abs(value - 50.0) < 0.01


def test_target_unchanged_stable():
    """Target unchanged → value_at returns target stably."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    g.set_target(100, 0.0)
    # Same target, multiple times.
    g.set_target(100, 1.0)
    assert g.value_at(1.5) == 100
    assert g.value_at(2.0) == 100


def test_unknown_mode_defaults_to_linear():
    """Unknown mode string defaults to linear."""
    cfg = GlideConfig(mode="unknown_mode")
    assert cfg.mode == "linear"


def test_value_at_before_first_set_target():
    """value_at returns None if never set_target."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)
    assert g.value_at(0.0) is None


def test_multiple_glides_sequential():
    """Multiple sequential glides work correctly."""
    cfg = GlideConfig(enabled=True, glide_time_s=1.0)
    g = Glider(cfg)

    g.set_target(0, 0.0)
    g.set_target(100, 0.0)
    assert g.value_at(0.5) is not None
    assert abs(g.value_at(0.5) - 50.0) < 0.01

    # After settled, set new target.
    g.set_target(50, 1.0)
    val_1_5 = g.value_at(1.5)
    assert val_1_5 is not None
    # Progress = 0.5, so should be halfway between 100 and 50.
    assert abs(val_1_5 - 75.0) < 0.01
