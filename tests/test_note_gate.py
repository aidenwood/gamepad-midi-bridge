"""Tests for the note_gate module — fixed-duration note release.

Tests cover all three modes (fixed, min_hold, max_hold), timing edge cases,
serialization, and simultaneous multi-note handling.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_gate import NoteGate, NoteGateConfig


# ─────────────────────────────────────────────────────────────────────
# Config: defaults, clamping, serialization
# ─────────────────────────────────────────────────────────────────────

def test_config_defaults():
    """New config has sensible defaults."""
    cfg = NoteGateConfig()
    assert cfg.enabled is False
    assert cfg.duration_ms == 100
    assert cfg.mode == "fixed"


def test_config_duration_clamped_low():
    """duration_ms < 1 is clamped to 1."""
    cfg = NoteGateConfig(duration_ms=0)
    assert cfg.duration_ms == 1
    cfg = NoteGateConfig(duration_ms=-10)
    assert cfg.duration_ms == 1


def test_config_duration_clamped_high():
    """duration_ms > 10000 is clamped to 10000."""
    cfg = NoteGateConfig(duration_ms=20000)
    assert cfg.duration_ms == 10000
    cfg = NoteGateConfig(duration_ms=11000)
    assert cfg.duration_ms == 10000


def test_config_invalid_mode_defaults_to_fixed():
    """Unknown mode is normalized to 'fixed'."""
    cfg = NoteGateConfig(mode="unknown")
    assert cfg.mode == "fixed"


def test_config_valid_modes():
    """All three valid modes are accepted."""
    for mode in ("fixed", "min_hold", "max_hold"):
        cfg = NoteGateConfig(mode=mode)
        assert cfg.mode == mode


def test_config_to_dict():
    """to_dict() produces a serializable dict."""
    cfg = NoteGateConfig(enabled=True, duration_ms=200, mode="min_hold")
    d = cfg.to_dict()
    assert d == {"enabled": True, "duration_ms": 200, "mode": "min_hold"}


def test_config_from_dict():
    """from_dict() reconstructs a config."""
    d = {"enabled": True, "duration_ms": 200, "mode": "max_hold"}
    cfg = NoteGateConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.duration_ms == 200
    assert cfg.mode == "max_hold"


def test_config_from_dict_missing_keys():
    """from_dict() uses defaults for missing keys."""
    cfg = NoteGateConfig.from_dict({})
    assert cfg.enabled is False
    assert cfg.duration_ms == 100
    assert cfg.mode == "fixed"


def test_config_round_trip():
    """to_dict() followed by from_dict() is lossless."""
    original = NoteGateConfig(enabled=True, duration_ms=250, mode="min_hold")
    d = original.to_dict()
    restored = NoteGateConfig.from_dict(d)
    assert restored.enabled == original.enabled
    assert restored.duration_ms == original.duration_ms
    assert restored.mode == original.mode


# ─────────────────────────────────────────────────────────────────────
# NoteGate: basic functionality
# ─────────────────────────────────────────────────────────────────────

def test_notegate_init():
    """NoteGate initializes with an empty active set."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100)
    gate = NoteGate(cfg)
    assert gate.active_count() == 0


def test_notegate_on_press_registers_note():
    """on_press() registers a note with its start time."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100)
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    assert gate.active_count() == 1


def test_notegate_multiple_presses():
    """Multiple on_press() calls track multiple notes independently."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100)
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    gate.on_press(64, 0.05)
    gate.on_press(67, 0.1)
    assert gate.active_count() == 3


def test_notegate_clear():
    """clear() empties the active set."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100)
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    gate.on_press(64, 0.05)
    assert gate.active_count() == 2
    gate.clear()
    assert gate.active_count() == 0


# ─────────────────────────────────────────────────────────────────────
# NoteGate: FIXED mode
# ─────────────────────────────────────────────────────────────────────

def test_fixed_mode_on_release_always_false():
    """In fixed mode, on_release() always returns False."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # Release immediately (t=0) should return False.
    assert gate.on_release(60, 0.0) is False
    # Release way later should also return False.
    assert gate.on_release(60, 10.0) is False


def test_fixed_mode_tick_before_duration():
    """In fixed mode, tick() returns empty list before duration expires."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At t=0.05 (50 ms), duration not reached.
    released = gate.tick(0.05)
    assert released == []
    assert gate.active_count() == 1


def test_fixed_mode_tick_after_duration():
    """In fixed mode, tick() releases notes after duration expires."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At t=0.15 (150 ms), duration exceeded.
    released = gate.tick(0.15)
    assert released == [60]
    assert gate.active_count() == 0


def test_fixed_mode_tick_exact_duration():
    """Tick at exactly duration_ms is considered "expired"."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At exactly t=0.1 (100 ms).
    released = gate.tick(0.1)
    assert released == [60]


def test_fixed_mode_tick_multiple_times():
    """Calling tick() a second time after release returns empty."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    released1 = gate.tick(0.15)
    assert released1 == [60]
    # Second tick should be empty; note was already removed.
    released2 = gate.tick(0.2)
    assert released2 == []


# ─────────────────────────────────────────────────────────────────────
# NoteGate: MIN_HOLD mode
# ─────────────────────────────────────────────────────────────────────

def test_min_hold_on_release_before_duration():
    """In min_hold, on_release() before duration returns False."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="min_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At t=0.05 (50 ms), before duration.
    assert gate.on_release(60, 0.05) is False


def test_min_hold_on_release_after_duration():
    """In min_hold, on_release() after duration returns True."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="min_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At t=0.15 (150 ms), after duration.
    assert gate.on_release(60, 0.15) is True


def test_min_hold_on_release_exact_duration():
    """In min_hold, on_release() at exactly duration returns True."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="min_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At exactly t=0.1 (100 ms).
    assert gate.on_release(60, 0.1) is True


def test_min_hold_tick_does_nothing():
    """In min_hold, tick() never auto-releases (always returns empty)."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="min_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # Even way past the duration, tick does nothing.
    assert gate.tick(0.5) == []
    assert gate.active_count() == 1


def test_min_hold_caller_must_call_on_release():
    """In min_hold, caller must call on_release() to actually release."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="min_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # Caller waits 150 ms and calls on_release().
    should_release = gate.on_release(60, 0.15)
    assert should_release is True
    # Caller is responsible for actually removing it (if needed for tracking).
    assert gate.active_count() == 1  # Still in the gate; caller removes it.


# ─────────────────────────────────────────────────────────────────────
# NoteGate: MAX_HOLD mode
# ─────────────────────────────────────────────────────────────────────

def test_max_hold_on_release_any_time():
    """In max_hold, on_release() always returns True immediately."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="max_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # Release at t=0 (before duration).
    assert gate.on_release(60, 0.0) is True
    # (Note is still in active_count; caller removes it.)


def test_max_hold_tick_releases_after_duration():
    """In max_hold, tick() releases notes after duration expires."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="max_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # Button held. Tick at t=0.15 (150 ms) releases it.
    released = gate.tick(0.15)
    assert released == [60]
    assert gate.active_count() == 0


def test_max_hold_button_release_wins_if_before_timeout():
    """In max_hold, if button is released before timeout, on_release() wins."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="max_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # Button released at t=0.05 (50 ms, before 100 ms).
    assert gate.on_release(60, 0.05) is True
    # Caller removes the note.


def test_max_hold_timeout_wins_if_button_held():
    """In max_hold, if button is held past timeout, tick() releases it."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="max_hold")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # Button held. Tick at t=0.15 (150 ms) releases despite button still held.
    released = gate.tick(0.15)
    assert released == [60]


# ─────────────────────────────────────────────────────────────────────
# Multi-note scenarios
# ─────────────────────────────────────────────────────────────────────

def test_multiple_notes_independent_timers():
    """Each note has its own independent timer."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)    # t=0
    gate.on_press(64, 0.05)   # t=50ms
    gate.on_press(67, 0.15)   # t=150ms (clearly different from others)
    assert gate.active_count() == 3

    # At t=160ms:
    # - Note 60 was pressed at 0, expires at 100ms. Released.
    # - Note 64 was pressed at 50ms, expires at 150ms. Released.
    # - Note 67 was pressed at 150ms, expires at 250ms. Not released.
    released = gate.tick(0.16)
    assert 60 in released and 64 in released
    assert 67 not in released
    assert gate.active_count() == 1

    # At t=300ms:
    # - Note 67 expires. Released.
    released = gate.tick(0.3)
    assert 67 in released
    assert gate.active_count() == 0


def test_multiple_notes_partial_release():
    """tick() can release a subset of active notes."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    gate.on_press(64, 0.15)  # Pressed 150ms later.
    # At t=150ms: note 60 released, note 64 not yet.
    released = gate.tick(0.15)
    assert 60 in released and 64 not in released


def test_repress_after_release():
    """A note can be pressed again after it's released."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    released = gate.tick(0.15)
    assert 60 in released

    # Now press 60 again.
    gate.on_press(60, 0.2)
    released = gate.tick(0.25)
    assert 60 not in released  # Not yet (only 50ms elapsed).
    released = gate.tick(0.35)
    assert 60 in released  # Now it is (150ms elapsed).


# ─────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────

def test_release_non_existent_note():
    """on_release() for a note not in active set returns True (no-op)."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    result = gate.on_release(99, 0.0)
    assert result is True


def test_very_short_duration():
    """Duration of 1 ms works correctly."""
    cfg = NoteGateConfig(enabled=True, duration_ms=1, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At t=0.001 (1 ms), should be released.
    released = gate.tick(0.001)
    assert 60 in released


def test_very_long_duration():
    """Duration of 10000 ms (max) works correctly."""
    cfg = NoteGateConfig(enabled=True, duration_ms=10000, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # At t=9.9 s, not yet released.
    released = gate.tick(9.9)
    assert released == []
    # At t=10.1 s, released.
    released = gate.tick(10.1)
    assert 60 in released


def test_large_note_numbers():
    """MIDI note numbers up to 127 are handled."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(127, 0.0)
    assert gate.active_count() == 1
    released = gate.tick(0.15)
    assert 127 in released


def test_zero_note_number():
    """Note 0 is valid."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(0, 0.0)
    assert gate.active_count() == 1
    released = gate.tick(0.15)
    assert 0 in released


# ─────────────────────────────────────────────────────────────────────
# Integration: command-line-like verification
# ─────────────────────────────────────────────────────────────────────

def test_manual_integration_fixed_mode():
    """Integration test matching the inline verification example."""
    cfg = NoteGateConfig(enabled=True, duration_ms=100, mode="fixed")
    gate = NoteGate(cfg)
    gate.on_press(60, 0.0)
    # tick at 0.05 (50ms): not yet released.
    assert gate.tick(0.05) == []
    # tick at 0.15 (150ms): released.
    assert gate.tick(0.15) == [60]
