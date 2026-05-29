"""Note pool random picker — all modes, seeding, and edge cases."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_pool import NotePoolConfig, NotePool


class TestNotePoolConfig:
    """NotePoolConfig dataclass — serialization and clamping."""

    def test_defaults(self):
        """Default config is disabled with empty pool."""
        cfg = NotePoolConfig()
        assert cfg.enabled is False
        assert cfg.notes == []
        assert cfg.weights == []
        assert cfg.mode == "random"
        assert cfg.no_repeat_window == 0
        assert cfg.seed is None

    def test_to_dict_round_trip(self):
        """to_dict and from_dict preserve config."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            weights=[1.0, 1.0, 2.0],
            mode="weighted_random",
            no_repeat_window=2,
            seed=42,
        )
        data = cfg.to_dict()
        cfg2 = NotePoolConfig.from_dict(data)
        assert cfg2 == cfg

    def test_notes_clamped_0_to_127(self):
        """Notes are clamped to MIDI range on deserialize."""
        cfg = NotePoolConfig.from_dict({
            "notes": [-10, 60, 200],
        })
        assert cfg.notes == [0, 60, 127]

    def test_weights_clamped_to_non_negative(self):
        """Weights are clamped to >= 0 on deserialize."""
        cfg = NotePoolConfig.from_dict({
            "weights": [-5.0, 1.5, 0.0],
        })
        assert cfg.weights == [0.0, 1.5, 0.0]

    def test_no_repeat_window_clamped_0_to_32(self):
        """no_repeat_window is clamped to 0..32."""
        cfg1 = NotePoolConfig.from_dict({"no_repeat_window": -5})
        assert cfg1.no_repeat_window == 0

        cfg2 = NotePoolConfig.from_dict({"no_repeat_window": 50})
        assert cfg2.no_repeat_window == 32

        cfg3 = NotePoolConfig.from_dict({"no_repeat_window": 16})
        assert cfg3.no_repeat_window == 16

    def test_unknown_mode_defaults_to_random(self):
        """Unknown mode in from_dict stays as-is (NotePool handles fallback)."""
        cfg = NotePoolConfig.from_dict({"mode": "unknown"})
        assert cfg.mode == "unknown"


class TestNotePoolEmptyAndDisabled:
    """Empty and disabled pool edge cases."""

    def test_empty_pool_returns_none(self):
        """Empty note pool returns None."""
        cfg = NotePoolConfig(enabled=True, notes=[])
        pool = NotePool(cfg)
        assert pool.pick() is None

    def test_disabled_pool_returns_none(self):
        """Disabled pool returns None regardless of notes."""
        cfg = NotePoolConfig(enabled=False, notes=[60, 64])
        pool = NotePool(cfg)
        assert pool.pick() is None


class TestRandomMode:
    """Random picking with and without no_repeat_window."""

    def test_random_mode_returns_notes_in_pool(self):
        """Random mode returns notes from the pool."""
        cfg = NotePoolConfig(enabled=True, notes=[60, 64, 67], mode="random", seed=42)
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(30)]
        assert all(note in cfg.notes for note in picks)
        assert set(picks) == set(cfg.notes)  # All notes appear

    def test_random_seeded_reproducible(self):
        """Same seed gives same sequence."""
        cfg1 = NotePoolConfig(enabled=True, notes=[60, 64, 67], mode="random", seed=12345)
        pool1 = NotePool(cfg1)
        seq1 = [pool1.pick() for _ in range(20)]

        cfg2 = NotePoolConfig(enabled=True, notes=[60, 64, 67], mode="random", seed=12345)
        pool2 = NotePool(cfg2)
        seq2 = [pool2.pick() for _ in range(20)]

        assert seq1 == seq2

    def test_random_no_repeat_window_prevents_consecutive(self):
        """no_repeat_window=1 prevents repeating the same note consecutively."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64],
            mode="random",
            no_repeat_window=1,
            seed=42,
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(100)]

        for i in range(1, len(picks)):
            # Note at i should not match note at i-1
            assert picks[i] != picks[i - 1]

    def test_random_no_repeat_window_larger_than_pool(self):
        """If no_repeat_window > pool size, still eventually picks (after retry limit)."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60],
            mode="random",
            no_repeat_window=10,
            seed=42,
        )
        pool = NotePool(cfg)
        # With 1 note and window=10, it should fallback and still return the note
        picks = [pool.pick() for _ in range(10)]
        assert all(n == 60 for n in picks)

    def test_random_mode_with_zero_window_allows_repeats(self):
        """no_repeat_window=0 allows repeating notes."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60],
            mode="random",
            no_repeat_window=0,
            seed=42,
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(5)]
        assert all(n == 60 for n in picks)


class TestWeightedRandomMode:
    """Weighted random distribution."""

    def test_weighted_random_respects_weights(self):
        """Weighted random respects weight distribution."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            weights=[10.0, 0.0, 10.0],  # 60 and 67, never 64
            mode="weighted_random",
            seed=42,
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(100)]
        assert 64 not in picks
        assert 60 in picks and 67 in picks

    def test_weighted_random_mismatched_weights_uses_equal(self):
        """If weights length != notes length, use equal weights."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            weights=[1.0],  # Mismatched
            mode="weighted_random",
            seed=42,
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(30)]
        # All notes should appear with roughly equal probability
        assert set(picks) == set(cfg.notes)

    def test_weighted_random_empty_weights_uses_equal(self):
        """If weights empty, use equal weights."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            weights=[],
            mode="weighted_random",
            seed=42,
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(30)]
        assert set(picks) == set(cfg.notes)


class TestRoundRobinMode:
    """Round-robin cycling."""

    def test_round_robin_cycles_in_order(self):
        """Round-robin returns notes in order, wrapping around."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            mode="round_robin",
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(9)]
        assert picks == [60, 64, 67, 60, 64, 67, 60, 64, 67]

    def test_round_robin_single_note(self):
        """Round-robin with single note always returns that note."""
        cfg = NotePoolConfig(enabled=True, notes=[72], mode="round_robin")
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(5)]
        assert picks == [72, 72, 72, 72, 72]


class TestShuffleBagMode:
    """Shuffle-bag (each note once per refill)."""

    def test_shuffle_bag_each_note_once_then_refill(self):
        """Shuffle-bag returns each note once per refill."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            mode="shuffle_bag",
            seed=42,
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(9)]

        # First 3 picks should be all three notes (in shuffled order)
        assert set(picks[0:3]) == set(cfg.notes)
        # Next 3 picks should be all three notes again
        assert set(picks[3:6]) == set(cfg.notes)
        # Last 3 picks should be all three notes again
        assert set(picks[6:9]) == set(cfg.notes)

    def test_shuffle_bag_single_note(self):
        """Shuffle-bag with single note always returns that note."""
        cfg = NotePoolConfig(enabled=True, notes=[72], mode="shuffle_bag")
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(5)]
        assert picks == [72, 72, 72, 72, 72]


class TestStateManagement:
    """Reset and set_seed."""

    def test_reset_clears_state(self):
        """reset() clears _recent, _bag, _index."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            mode="random",
            no_repeat_window=2,
            seed=42,
        )
        pool = NotePool(cfg)
        # Generate some picks
        [pool.pick() for _ in range(5)]
        assert len(pool._recent) > 0

        pool.reset()
        assert pool._recent == []
        assert pool._bag == []
        assert pool._index == 0

    def test_set_seed_reseed_and_reset(self):
        """set_seed() re-seeds RNG and resets state."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            mode="random",
            seed=42,
        )
        pool = NotePool(cfg)
        seq1 = [pool.pick() for _ in range(10)]

        # Re-seed with same seed
        pool.set_seed(42)
        seq2 = [pool.pick() for _ in range(10)]

        assert seq1 == seq2


class TestUnknownMode:
    """Unknown modes fall back to random."""

    def test_unknown_mode_falls_back_to_random(self):
        """Unknown mode is treated as random."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67],
            mode="nonexistent_mode",
            seed=42,
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(30)]
        assert all(note in cfg.notes for note in picks)


class TestIntegration:
    """Integration tests spanning multiple modes and scenarios."""

    def test_single_note_pool(self):
        """Single-note pool always returns that note."""
        for mode in ["random", "round_robin", "shuffle_bag", "weighted_random"]:
            cfg = NotePoolConfig(enabled=True, notes=[60], mode=mode)
            pool = NotePool(cfg)
            picks = [pool.pick() for _ in range(5)]
            assert all(n == 60 for n in picks)

    def test_enabled_flag_overrides_all(self):
        """Disabled pool always returns None, regardless of pool size or mode."""
        cfg = NotePoolConfig(
            enabled=False,
            notes=[60, 64, 67],
            mode="round_robin",
        )
        pool = NotePool(cfg)
        picks = [pool.pick() for _ in range(5)]
        assert all(n is None for n in picks)

    def test_round_trip_serialization_with_all_fields(self):
        """Full serialization round-trip preserves all fields."""
        cfg = NotePoolConfig(
            enabled=True,
            notes=[60, 64, 67, 72],
            weights=[1.0, 2.0, 3.0, 4.0],
            mode="shuffle_bag",
            no_repeat_window=3,
            seed=999,
        )
        data = cfg.to_dict()
        cfg2 = NotePoolConfig.from_dict(data)

        assert cfg == cfg2

        # Both should produce same picks with same seed
        pool1 = NotePool(cfg)
        pool2 = NotePool(cfg2)
        seq1 = [pool1.pick() for _ in range(20)]
        seq2 = [pool2.pick() for _ in range(20)]
        assert seq1 == seq2
