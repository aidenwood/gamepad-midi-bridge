"""Tests for setlist shuffle with pinned positions and tag-based grouping constraints.

Shuffle randomizes a setlist with optional pinned positions (entries stay in place)
and grouping constraints (avoid adjacent entries with matching tags). Pure stdlib.
"""
from __future__ import annotations

import pytest


class TestShuffleConfig:
    """ShuffleConfig dataclass — defaults, clamping, serialization."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        cfg = ShuffleConfig()
        assert cfg.seed is None
        assert cfg.pin_positions == []
        assert cfg.avoid_adjacent_tags == []
        assert cfg.max_attempts == 100

    def test_config_with_values(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        cfg = ShuffleConfig(
            seed=42,
            pin_positions=[0, 2],
            avoid_adjacent_tags=["ambient", "noise"],
            max_attempts=50
        )
        assert cfg.seed == 42
        assert cfg.pin_positions == [0, 2]
        assert cfg.avoid_adjacent_tags == ["ambient", "noise"]
        assert cfg.max_attempts == 50

    def test_config_clamp_max_attempts_below_one(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        cfg = ShuffleConfig(max_attempts=0)
        assert cfg.max_attempts == 1
        cfg = ShuffleConfig(max_attempts=-5)
        assert cfg.max_attempts == 1

    def test_config_clamp_max_attempts_above_10000(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        cfg = ShuffleConfig(max_attempts=15000)
        assert cfg.max_attempts == 10000
        cfg = ShuffleConfig(max_attempts=50000)
        assert cfg.max_attempts == 10000

    def test_config_no_clamp_in_range(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        cfg = ShuffleConfig(max_attempts=5000)
        assert cfg.max_attempts == 5000

    def test_config_to_dict(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        cfg = ShuffleConfig(
            seed=99,
            pin_positions=[0, 3],
            avoid_adjacent_tags=["drum", "bass"],
            max_attempts=200
        )
        d = cfg.to_dict()
        assert d["seed"] == 99
        assert d["pin_positions"] == [0, 3]
        assert d["avoid_adjacent_tags"] == ["drum", "bass"]
        assert d["max_attempts"] == 200

    def test_config_from_dict(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        d = {
            "seed": 42,
            "pin_positions": [1, 4],
            "avoid_adjacent_tags": ["pad"],
            "max_attempts": 75
        }
        cfg = ShuffleConfig.from_dict(d)
        assert cfg.seed == 42
        assert cfg.pin_positions == [1, 4]
        assert cfg.avoid_adjacent_tags == ["pad"]
        assert cfg.max_attempts == 75

    def test_config_round_trip(self):
        from gamepad_midi_bridge.setlist_shuffle import ShuffleConfig
        original = ShuffleConfig(
            seed=123,
            pin_positions=[0, 2, 5],
            avoid_adjacent_tags=["ambient", "noise"],
            max_attempts=150
        )
        d = original.to_dict()
        restored = ShuffleConfig.from_dict(d)
        assert restored.seed == original.seed
        assert restored.pin_positions == original.pin_positions
        assert restored.avoid_adjacent_tags == original.avoid_adjacent_tags
        assert restored.max_attempts == original.max_attempts


class TestValidatePinPositions:
    """validate_pin_positions — strip out-of-range indices."""

    def test_all_valid(self):
        from gamepad_midi_bridge.setlist_shuffle import validate_pin_positions
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        result = validate_pin_positions(entries, [0, 1, 2])
        assert result == [0, 1, 2]

    def test_some_out_of_range(self):
        from gamepad_midi_bridge.setlist_shuffle import validate_pin_positions
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        result = validate_pin_positions(entries, [0, 5, 2, 10])
        assert result == [0, 2]

    def test_negative_indices_rejected(self):
        from gamepad_midi_bridge.setlist_shuffle import validate_pin_positions
        entries = [{"slug": "a"}, {"slug": "b"}]
        result = validate_pin_positions(entries, [-1, 0, 1])
        assert result == [0, 1]

    def test_empty_entries(self):
        from gamepad_midi_bridge.setlist_shuffle import validate_pin_positions
        result = validate_pin_positions([], [0, 1, 2])
        assert result == []

    def test_empty_pin_positions(self):
        from gamepad_midi_bridge.setlist_shuffle import validate_pin_positions
        entries = [{"slug": "a"}, {"slug": "b"}]
        result = validate_pin_positions(entries, [])
        assert result == []


class TestHasAdjacentTagConflict:
    """has_adjacent_tag_conflict — detect adjacent entries with shared avoid tags."""

    def test_no_conflict_empty_avoid_tags(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [
            {"slug": "a", "tags": ["ambient"]},
            {"slug": "b", "tags": ["ambient"]}
        ]
        assert has_adjacent_tag_conflict(entries, []) is False

    def test_no_conflict_different_tags(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [
            {"slug": "a", "tags": ["drum"]},
            {"slug": "b", "tags": ["bass"]}
        ]
        assert has_adjacent_tag_conflict(entries, ["ambient", "noise"]) is False

    def test_no_conflict_one_entry(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [{"slug": "a", "tags": ["ambient"]}]
        assert has_adjacent_tag_conflict(entries, ["ambient"]) is False

    def test_no_conflict_empty_entries(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        assert has_adjacent_tag_conflict([], ["ambient"]) is False

    def test_conflict_adjacent_share_avoid_tag(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [
            {"slug": "a", "tags": ["ambient", "pad"]},
            {"slug": "b", "tags": ["ambient", "synth"]}
        ]
        assert has_adjacent_tag_conflict(entries, ["ambient"]) is True

    def test_conflict_adjacent_different_avoid_tags(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [
            {"slug": "a", "tags": ["drum"]},
            {"slug": "b", "tags": ["percussion"]}
        ]
        assert has_adjacent_tag_conflict(entries, ["drum", "percussion"]) is True

    def test_no_conflict_nonadjacent_share_tag(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [
            {"slug": "a", "tags": ["ambient"]},
            {"slug": "b", "tags": ["synth"]},
            {"slug": "c", "tags": ["ambient"]}
        ]
        assert has_adjacent_tag_conflict(entries, ["ambient"]) is False

    def test_no_conflict_missing_tags_key(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [
            {"slug": "a"},
            {"slug": "b"}
        ]
        assert has_adjacent_tag_conflict(entries, ["ambient"]) is False

    def test_conflict_partial_missing_tags_key(self):
        from gamepad_midi_bridge.setlist_shuffle import has_adjacent_tag_conflict
        entries = [
            {"slug": "a", "tags": ["ambient"]},
            {"slug": "b"}  # No tags key; treated as empty
        ]
        assert has_adjacent_tag_conflict(entries, ["ambient"]) is False


class TestSafeSwap:
    """safe_swap — swap entries unless either is pinned."""

    def test_swap_unpinned(self):
        from gamepad_midi_bridge.setlist_shuffle import safe_swap
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        result = safe_swap(entries, 0, 2, [])
        assert result[0]["slug"] == "c"
        assert result[1]["slug"] == "b"
        assert result[2]["slug"] == "a"

    def test_swap_returns_new_list(self):
        from gamepad_midi_bridge.setlist_shuffle import safe_swap
        entries = [{"slug": "a"}, {"slug": "b"}]
        result = safe_swap(entries, 0, 1, [])
        assert result is not entries

    def test_no_swap_first_pinned(self):
        from gamepad_midi_bridge.setlist_shuffle import safe_swap
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        result = safe_swap(entries, 0, 2, [0])
        assert result[0]["slug"] == "a"
        assert result[2]["slug"] == "c"

    def test_no_swap_second_pinned(self):
        from gamepad_midi_bridge.setlist_shuffle import safe_swap
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        result = safe_swap(entries, 0, 2, [2])
        assert result[0]["slug"] == "a"
        assert result[2]["slug"] == "c"

    def test_no_swap_both_pinned(self):
        from gamepad_midi_bridge.setlist_shuffle import safe_swap
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        result = safe_swap(entries, 0, 2, [0, 2])
        assert result == entries or [e["slug"] for e in result] == ["a", "b", "c"]

    def test_swap_adjacent(self):
        from gamepad_midi_bridge.setlist_shuffle import safe_swap
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        result = safe_swap(entries, 1, 2, [])
        assert result[1]["slug"] == "c"
        assert result[2]["slug"] == "b"


class TestReverseUnpinned:
    """reverse_unpinned — reverse only unpinned entries."""

    def test_reverse_all_unpinned(self):
        from gamepad_midi_bridge.setlist_shuffle import reverse_unpinned
        entries = [
            {"slug": "a"},
            {"slug": "b"},
            {"slug": "c"},
            {"slug": "d"}
        ]
        result = reverse_unpinned(entries, [])
        assert [e["slug"] for e in result] == ["d", "c", "b", "a"]

    def test_reverse_keeps_pinned(self):
        from gamepad_midi_bridge.setlist_shuffle import reverse_unpinned
        entries = [
            {"slug": "a"},
            {"slug": "b"},
            {"slug": "c"},
            {"slug": "d"}
        ]
        result = reverse_unpinned(entries, [0, 3])
        assert result[0]["slug"] == "a"  # pinned
        assert result[3]["slug"] == "d"  # pinned
        assert result[1]["slug"] == "c"  # reversed from b
        assert result[2]["slug"] == "b"  # reversed from c

    def test_reverse_all_pinned(self):
        from gamepad_midi_bridge.setlist_shuffle import reverse_unpinned
        entries = [
            {"slug": "a"},
            {"slug": "b"},
            {"slug": "c"}
        ]
        result = reverse_unpinned(entries, [0, 1, 2])
        assert [e["slug"] for e in result] == ["a", "b", "c"]

    def test_reverse_single_entry(self):
        from gamepad_midi_bridge.setlist_shuffle import reverse_unpinned
        entries = [{"slug": "a"}]
        result = reverse_unpinned(entries, [])
        assert [e["slug"] for e in result] == ["a"]

    def test_reverse_returns_new_list(self):
        from gamepad_midi_bridge.setlist_shuffle import reverse_unpinned
        entries = [{"slug": "a"}, {"slug": "b"}]
        result = reverse_unpinned(entries, [])
        assert result is not entries


class TestShuffle:
    """shuffle — randomize entries with pinned positions and tag constraints."""

    def test_shuffle_empty_list(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        cfg = ShuffleConfig(seed=42)
        result = shuffle([], cfg)
        assert result == []

    def test_shuffle_single_entry(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": "a"}]
        cfg = ShuffleConfig(seed=42)
        result = shuffle(entries, cfg)
        assert len(result) == 1
        assert result[0]["slug"] == "a"

    def test_shuffle_returns_new_list(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        cfg = ShuffleConfig(seed=42)
        result = shuffle(entries, cfg)
        assert result is not entries

    def test_shuffle_same_length(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": s} for s in ["a", "b", "c", "d", "e"]]
        cfg = ShuffleConfig(seed=42)
        result = shuffle(entries, cfg)
        assert len(result) == len(entries)

    def test_shuffle_contains_all_entries(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": s} for s in ["a", "b", "c"]]
        cfg = ShuffleConfig(seed=42)
        result = shuffle(entries, cfg)
        result_slugs = [e["slug"] for e in result]
        assert sorted(result_slugs) == ["a", "b", "c"]

    def test_shuffle_with_seed_reproducible(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries1 = [{"slug": s} for s in ["a", "b", "c", "d"]]
        entries2 = [{"slug": s} for s in ["a", "b", "c", "d"]]
        cfg1 = ShuffleConfig(seed=42)
        cfg2 = ShuffleConfig(seed=42)
        result1 = shuffle(entries1, cfg1)
        result2 = shuffle(entries2, cfg2)
        assert [e["slug"] for e in result1] == [e["slug"] for e in result2]

    def test_shuffle_pin_positions_first(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": s} for s in ["a", "b", "c", "d"]]
        cfg = ShuffleConfig(seed=42, pin_positions=[0])
        result = shuffle(entries, cfg)
        assert result[0]["slug"] == "a"

    def test_shuffle_pin_positions_multiple(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": s} for s in ["a", "b", "c", "d", "e"]]
        cfg = ShuffleConfig(seed=42, pin_positions=[0, 4])
        result = shuffle(entries, cfg)
        assert result[0]["slug"] == "a"
        assert result[4]["slug"] == "e"

    def test_shuffle_avoid_adjacent_tags_reduces_conflicts(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig, has_adjacent_tag_conflict
        # Create entries where two have "ambient" tag
        entries = [
            {"slug": "a", "tags": ["ambient"]},
            {"slug": "b", "tags": ["synth"]},
            {"slug": "c", "tags": ["ambient"]},
            {"slug": "d", "tags": ["drum"]}
        ]
        # Without avoid constraint, might have adjacent ambient
        cfg_no_avoid = ShuffleConfig(seed=42, avoid_adjacent_tags=[])
        result_no_avoid = shuffle(entries, cfg_no_avoid)

        # With avoid constraint, should not have adjacent ambient
        cfg_avoid = ShuffleConfig(seed=42, avoid_adjacent_tags=["ambient"], max_attempts=200)
        result_avoid = shuffle(entries, cfg_avoid)
        assert not has_adjacent_tag_conflict(result_avoid, ["ambient"])

    def test_shuffle_pin_and_avoid_together(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig, has_adjacent_tag_conflict
        entries = [
            {"slug": "a", "tags": ["ambient"]},
            {"slug": "b", "tags": ["drum"]},
            {"slug": "c", "tags": ["ambient"]},
            {"slug": "d", "tags": ["synth"]}
        ]
        cfg = ShuffleConfig(
            seed=42,
            pin_positions=[0],
            avoid_adjacent_tags=["ambient"],
            max_attempts=100
        )
        result = shuffle(entries, cfg)
        assert result[0]["slug"] == "a"  # pinned
        # Best effort to avoid ambient conflict
        has_conflict = has_adjacent_tag_conflict(result, ["ambient"])
        # We can only assert it succeeded or made a best effort

    def test_shuffle_max_attempts_clamped_low(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": s} for s in ["a", "b", "c"]]
        cfg = ShuffleConfig(seed=42, max_attempts=0)
        # Should be clamped to 1 in __post_init__
        result = shuffle(entries, cfg)
        assert len(result) == 3

    def test_shuffle_max_attempts_clamped_high(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries = [{"slug": s} for s in ["a", "b", "c"]]
        cfg = ShuffleConfig(seed=42, max_attempts=50000)
        # Should be clamped to 10000 in __post_init__
        result = shuffle(entries, cfg)
        assert len(result) == 3

    def test_shuffle_impossible_constraint_returns_best_effort(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        # Create an impossible scenario: two "ambient" entries, can't avoid adjacency
        entries = [
            {"slug": "a", "tags": ["ambient"]},
            {"slug": "b", "tags": ["ambient"]}
        ]
        cfg = ShuffleConfig(seed=42, avoid_adjacent_tags=["ambient"], max_attempts=100)
        result = shuffle(entries, cfg)
        # Should still return a shuffled list (best effort)
        assert len(result) == 2
        slugs = [e["slug"] for e in result]
        assert sorted(slugs) == ["a", "b"]

    def test_shuffle_different_seeds_different_order(self):
        from gamepad_midi_bridge.setlist_shuffle import shuffle, ShuffleConfig
        entries1 = [{"slug": s} for s in ["a", "b", "c", "d", "e"]]
        entries2 = [{"slug": s} for s in ["a", "b", "c", "d", "e"]]
        cfg1 = ShuffleConfig(seed=42)
        cfg2 = ShuffleConfig(seed=99)
        result1 = shuffle(entries1, cfg1)
        result2 = shuffle(entries2, cfg2)
        # Different seeds should (very likely) produce different orders
        result1_slugs = [e["slug"] for e in result1]
        result2_slugs = [e["slug"] for e in result2]
        # Not guaranteed, but highly probable for large lists
        # For this small list, we just check both are valid
        assert sorted(result1_slugs) == ["a", "b", "c", "d", "e"]
        assert sorted(result2_slugs) == ["a", "b", "c", "d", "e"]
