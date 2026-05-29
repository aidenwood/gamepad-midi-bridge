"""Tests for sustain release tail manager.

SustainReleaseTail delays note-off messages for natural decay.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestPendingReleaseRoundTrip:
    """PendingRelease serialization round-trip."""

    def test_to_dict_and_from_dict(self):
        """to_dict() → from_dict() preserves all fields."""
        from gamepad_midi_bridge.sustain_release_tail import PendingRelease

        original = PendingRelease(note=60, channel=3, fire_at_s=1.234)
        data = original.to_dict()
        restored = PendingRelease.from_dict(data)

        assert restored.note == 60
        assert restored.channel == 3
        assert restored.fire_at_s == 1.234

    def test_to_dict_keys(self):
        """to_dict() returns expected keys."""
        from gamepad_midi_bridge.sustain_release_tail import PendingRelease

        entry = PendingRelease(note=64, channel=5, fire_at_s=2.5)
        data = entry.to_dict()

        assert set(data.keys()) == {"note", "channel", "fire_at_s"}
        assert data["note"] == 64
        assert data["channel"] == 5
        assert data["fire_at_s"] == 2.5

    def test_from_dict_missing_keys_use_defaults(self):
        """from_dict() handles missing keys with sensible defaults."""
        from gamepad_midi_bridge.sustain_release_tail import PendingRelease

        restored = PendingRelease.from_dict({})
        assert restored.note == 0
        assert restored.channel == 0
        assert restored.fire_at_s == 0.0


class TestSustainTailConfigRoundTrip:
    """SustainTailConfig serialization round-trip."""

    def test_to_dict_and_from_dict(self):
        """to_dict() → from_dict() preserves all fields with clamping."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        original = SustainTailConfig(
            enabled=True, tail_ms=250.0, random_jitter_ms=50.0, seed=42
        )
        data = original.to_dict()
        restored = SustainTailConfig.from_dict(data)

        assert restored.enabled is True
        assert restored.tail_ms == 250.0
        assert restored.random_jitter_ms == 50.0
        assert restored.seed == 42

    def test_to_dict_keys(self):
        """to_dict() returns expected keys."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        cfg = SustainTailConfig(enabled=True, tail_ms=300.0, seed=99)
        data = cfg.to_dict()

        assert set(data.keys()) == {"enabled", "tail_ms", "random_jitter_ms", "seed"}

    def test_from_dict_missing_keys_use_defaults(self):
        """from_dict() handles missing keys with dataclass defaults."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        restored = SustainTailConfig.from_dict({})
        assert restored.enabled is False
        assert restored.tail_ms == 200.0
        assert restored.random_jitter_ms == 0.0
        assert restored.seed is None

    def test_from_dict_partial_keys(self):
        """from_dict() merges provided keys with defaults."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        restored = SustainTailConfig.from_dict({"enabled": True, "tail_ms": 150.0})
        assert restored.enabled is True
        assert restored.tail_ms == 150.0
        assert restored.random_jitter_ms == 0.0
        assert restored.seed is None


class TestSustainTailConfigClamping:
    """SustainTailConfig clamping behavior."""

    def test_clamp_tail_ms_below_min(self):
        """tail_ms < 1 clamped to 1."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        cfg = SustainTailConfig(tail_ms=0.5)
        assert cfg.tail_ms == 1.0

    def test_clamp_tail_ms_above_max(self):
        """tail_ms > 10000 clamped to 10000."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        cfg = SustainTailConfig(tail_ms=15000.0)
        assert cfg.tail_ms == 10000.0

    def test_clamp_random_jitter_ms_below_min(self):
        """random_jitter_ms < 0 clamped to 0."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        cfg = SustainTailConfig(random_jitter_ms=-10.0)
        assert cfg.random_jitter_ms == 0.0

    def test_clamp_random_jitter_ms_above_max(self):
        """random_jitter_ms > 500 clamped to 500."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        cfg = SustainTailConfig(random_jitter_ms=1000.0)
        assert cfg.random_jitter_ms == 500.0

    def test_clamp_both_values(self):
        """Both tail_ms and random_jitter_ms clamped correctly."""
        from gamepad_midi_bridge.sustain_release_tail import SustainTailConfig

        cfg = SustainTailConfig(tail_ms=-5.0, random_jitter_ms=600.0)
        assert cfg.tail_ms == 1.0
        assert cfg.random_jitter_ms == 500.0


class TestSustainReleaseTailBasics:
    """Basic SustainReleaseTail operations."""

    def test_init_stores_config(self):
        """__init__ stores the config."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=300.0)
        srt = SustainReleaseTail(cfg)

        assert srt.cfg is cfg
        assert srt.cfg.enabled is True
        assert srt.cfg.tail_ms == 300.0

    def test_init_empty_pending_list(self):
        """__init__ creates empty pending list."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig()
        srt = SustainReleaseTail(cfg)

        assert srt.pending_count() == 0

    def test_queue_release_when_enabled(self):
        """queue_release() with enabled=True appends to pending."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=200.0)
        srt = SustainReleaseTail(cfg)

        entry = srt.queue_release(note=60, channel=1, now_s=0.0)

        assert entry.note == 60
        assert entry.channel == 1
        assert entry.fire_at_s == 0.2  # now_s=0 + 200ms
        assert srt.pending_count() == 1

    def test_queue_release_when_disabled(self):
        """queue_release() with enabled=False returns entry but doesn't queue."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=False, tail_ms=200.0)
        srt = SustainReleaseTail(cfg)

        entry = srt.queue_release(note=60, channel=1, now_s=0.5)

        assert entry.note == 60
        assert entry.channel == 1
        # Entry fire_at_s matches now_s when disabled.
        assert entry.fire_at_s == 0.5
        # But it's not added to pending.
        assert srt.pending_count() == 0

    def test_pop_ready_before_fire_time_returns_empty(self):
        """pop_ready() before fire_at_s returns []."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(note=60, channel=0, now_s=0.0)
        # fire_at_s = 0.1

        ready = srt.pop_ready(now_s=0.05)
        assert len(ready) == 0
        assert srt.pending_count() == 1

    def test_pop_ready_at_fire_time_returns_entry(self):
        """pop_ready() at fire_at_s returns entry."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(note=60, channel=0, now_s=0.0)
        # fire_at_s = 0.1

        ready = srt.pop_ready(now_s=0.1)
        assert len(ready) == 1
        assert ready[0].note == 60
        assert ready[0].channel == 0
        assert srt.pending_count() == 0

    def test_pop_ready_after_fire_time_returns_entry(self):
        """pop_ready() after fire_at_s returns entry."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(note=60, channel=0, now_s=0.0)
        # fire_at_s = 0.1

        ready = srt.pop_ready(now_s=0.2)
        assert len(ready) == 1
        assert ready[0].note == 60
        assert srt.pending_count() == 0

    def test_pending_count_tracks_queue_size(self):
        """pending_count() reflects current queue size."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        assert srt.pending_count() == 0

        srt.queue_release(60, 0, 0.0)
        assert srt.pending_count() == 1

        srt.queue_release(64, 0, 0.0)
        assert srt.pending_count() == 2

        srt.pop_ready(0.2)
        assert srt.pending_count() == 0

    def test_flush_all_returns_and_clears(self):
        """flush_all() returns all pending and clears queue."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(60, 0, 0.0)
        srt.queue_release(64, 0, 0.0)
        srt.queue_release(67, 0, 0.0)

        flushed = srt.flush_all()
        assert len(flushed) == 3
        assert srt.pending_count() == 0

    def test_clear_empties_pending(self):
        """clear() empties the pending list."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(60, 0, 0.0)
        srt.queue_release(64, 0, 0.0)

        srt.clear()
        assert srt.pending_count() == 0

    def test_next_fire_at_empty_returns_none(self):
        """next_fire_at() returns None when pending is empty."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        assert srt.next_fire_at() is None

    def test_next_fire_at_returns_earliest(self):
        """next_fire_at() returns the earliest fire_at_s."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(60, 0, 0.0)  # fire_at_s = 0.1
        srt.queue_release(64, 0, 0.05)  # fire_at_s = 0.15
        srt.queue_release(67, 0, 0.1)  # fire_at_s = 0.2

        # Earliest is 0.1.
        assert srt.next_fire_at() == 0.1


class TestMultiNoteOrdering:
    """Multiple notes fire in time order, not insertion order."""

    def test_pop_ready_multiple_notes_sorted_by_fire_at_s(self):
        """pop_ready() returns multiple notes sorted by fire_at_s."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        # Insert in non-temporal order.
        srt.queue_release(64, 0, 0.05)  # fire_at_s = 0.15
        srt.queue_release(60, 0, 0.0)  # fire_at_s = 0.1
        srt.queue_release(67, 0, 0.1)  # fire_at_s = 0.2

        ready = srt.pop_ready(now_s=0.3)

        assert len(ready) == 3
        # Should be sorted by fire_at_s.
        assert ready[0].note == 60  # fire_at_s = 0.1
        assert ready[1].note == 64  # fire_at_s = 0.15
        assert ready[2].note == 67  # fire_at_s = 0.2

    def test_pop_ready_partial_ready_sorted(self):
        """pop_ready() with partial matches sorts matched entries."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(64, 0, 0.05)  # fire_at_s = 0.15
        srt.queue_release(60, 0, 0.0)  # fire_at_s = 0.1
        srt.queue_release(67, 0, 0.1)  # fire_at_s = 0.2

        # Only 60 and 64 are ready.
        ready = srt.pop_ready(now_s=0.18)

        assert len(ready) == 2
        assert ready[0].note == 60  # fire_at_s = 0.1
        assert ready[1].note == 64  # fire_at_s = 0.15
        # 67 still pending.
        assert srt.pending_count() == 1


class TestRandomJitterReproducibility:
    """Random jitter with seed is reproducible."""

    def test_jitter_with_seed_reproducible(self):
        """Same seed produces same jitter across instances."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg1 = SustainTailConfig(
            enabled=True, tail_ms=100.0, random_jitter_ms=50.0, seed=42
        )
        srt1 = SustainReleaseTail(cfg1)
        entry1 = srt1.queue_release(60, 0, 0.0)

        cfg2 = SustainTailConfig(
            enabled=True, tail_ms=100.0, random_jitter_ms=50.0, seed=42
        )
        srt2 = SustainReleaseTail(cfg2)
        entry2 = srt2.queue_release(60, 0, 0.0)

        # Same seed, same note, same config → same fire_at_s.
        assert entry1.fire_at_s == entry2.fire_at_s

    def test_jitter_different_seed_different_values(self):
        """Different seeds produce different jitter."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg1 = SustainTailConfig(
            enabled=True, tail_ms=100.0, random_jitter_ms=50.0, seed=42
        )
        srt1 = SustainReleaseTail(cfg1)
        entry1 = srt1.queue_release(60, 0, 0.0)

        cfg2 = SustainTailConfig(
            enabled=True, tail_ms=100.0, random_jitter_ms=50.0, seed=99
        )
        srt2 = SustainReleaseTail(cfg2)
        entry2 = srt2.queue_release(60, 0, 0.0)

        # Different seeds (likely) produce different fire_at_s.
        # Note: there's a tiny chance they're equal, but vanishingly small.
        assert entry1.fire_at_s != entry2.fire_at_s

    def test_jitter_without_seed_varies(self):
        """Without seed, different calls produce (likely) different jitter."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=100.0, random_jitter_ms=50.0)

        srt1 = SustainReleaseTail(cfg)
        entry1 = srt1.queue_release(60, 0, 0.0)

        srt2 = SustainReleaseTail(cfg)
        entry2 = srt2.queue_release(60, 0, 0.0)

        # Without seed, likely different fire_at_s (not guaranteed, but very likely).
        # We'll just check that both are within expected range.
        base_fire_at_s = 0.0 + 100.0 / 1000.0  # 0.1
        jitter_range = 50.0 / 1000.0  # ±0.05

        assert base_fire_at_s - jitter_range <= entry1.fire_at_s <= base_fire_at_s + jitter_range
        assert base_fire_at_s - jitter_range <= entry2.fire_at_s <= base_fire_at_s + jitter_range

    def test_jitter_range_within_bounds(self):
        """Jitter keeps fire_at_s within expected bounds."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(
            enabled=True, tail_ms=200.0, random_jitter_ms=100.0, seed=42
        )
        srt = SustainReleaseTail(cfg)

        base_fire_at_s = 0.0 + 200.0 / 1000.0  # 0.2
        jitter_range = 100.0 / 1000.0  # ±0.1

        for _ in range(10):
            entry = srt.queue_release(60, 0, 0.0)
            # fire_at_s should be within [0.1, 0.3].
            assert base_fire_at_s - jitter_range <= entry.fire_at_s <= base_fire_at_s + jitter_range


class TestIntegration:
    """Integration: queue, pop, manage a realistic scenario."""

    def test_realistic_scenario_multiple_notes(self):
        """Realistic: queue notes, pop some, queue more, pop all."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=200.0)
        srt = SustainReleaseTail(cfg)

        # Queue 3 notes at t=0.
        srt.queue_release(60, 0, 0.0)  # fire_at_s = 0.2
        srt.queue_release(64, 0, 0.0)  # fire_at_s = 0.2
        srt.queue_release(67, 0, 0.0)  # fire_at_s = 0.2

        assert srt.pending_count() == 3

        # At t=0.1, nothing ready yet.
        ready_at_01 = srt.pop_ready(0.1)
        assert len(ready_at_01) == 0
        assert srt.pending_count() == 3

        # Queue more notes at t=0.1 with different tail.
        cfg2 = SustainTailConfig(enabled=True, tail_ms=100.0)
        srt.cfg = cfg2
        srt.queue_release(72, 0, 0.1)  # fire_at_s = 0.2
        srt.queue_release(76, 0, 0.1)  # fire_at_s = 0.2

        assert srt.pending_count() == 5

        # At t=0.25, all 5 should be ready.
        ready_at_025 = srt.pop_ready(0.25)
        assert len(ready_at_025) == 5
        assert srt.pending_count() == 0

    def test_panic_flush_on_shutdown(self):
        """Panic flush: return all pending notes immediately."""
        from gamepad_midi_bridge.sustain_release_tail import (
            SustainTailConfig,
            SustainReleaseTail,
        )

        cfg = SustainTailConfig(enabled=True, tail_ms=1000.0)
        srt = SustainReleaseTail(cfg)

        srt.queue_release(60, 0, 0.0)
        srt.queue_release(64, 0, 0.0)
        srt.queue_release(67, 0, 0.0)

        # Panic: immediate flush (e.g., app shutdown).
        flushed = srt.flush_all()
        assert len(flushed) == 3
        assert srt.pending_count() == 0
