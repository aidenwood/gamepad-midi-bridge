"""Tests for per-control activity heatmap tracking.

ControlHeatmap records how many times each control (button, axis, trigger, etc.)
fires during a session and provides heatmap-ready data structures. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestControlHit:
    """ControlHit dataclass — serialize/deserialize."""

    def test_hit_default_construction(self):
        from gamepad_midi_bridge.control_heatmap import ControlHit
        hit = ControlHit(control_type="button", control_id="button.0")
        assert hit.control_type == "button"
        assert hit.control_id == "button.0"
        assert hit.count == 0
        assert hit.last_at is None

    def test_hit_with_count_and_timestamp(self):
        from gamepad_midi_bridge.control_heatmap import ControlHit
        hit = ControlHit(
            control_type="axis",
            control_id="left_stick_x",
            count=42,
            last_at=12345.6,
        )
        assert hit.control_type == "axis"
        assert hit.control_id == "left_stick_x"
        assert hit.count == 42
        assert hit.last_at == 12345.6

    def test_hit_to_dict(self):
        from gamepad_midi_bridge.control_heatmap import ControlHit
        hit = ControlHit(
            control_type="trigger",
            control_id="L2",
            count=10,
            last_at=99999.0,
        )
        d = hit.to_dict()
        assert d["control_type"] == "trigger"
        assert d["control_id"] == "L2"
        assert d["count"] == 10
        assert d["last_at"] == 99999.0

    def test_hit_from_dict(self):
        from gamepad_midi_bridge.control_heatmap import ControlHit
        d = {
            "control_type": "hat",
            "control_id": "dpad_up",
            "count": 5,
            "last_at": 55555.5,
        }
        hit = ControlHit.from_dict(d)
        assert hit.control_type == "hat"
        assert hit.control_id == "dpad_up"
        assert hit.count == 5
        assert hit.last_at == 55555.5

    def test_hit_round_trip(self):
        from gamepad_midi_bridge.control_heatmap import ControlHit
        original = ControlHit(
            control_type="touchpad",
            control_id="touchpad.0",
            count=123,
            last_at=77777.7,
        )
        d = original.to_dict()
        restored = ControlHit.from_dict(d)
        assert restored.control_type == original.control_type
        assert restored.control_id == original.control_id
        assert restored.count == original.count
        assert restored.last_at == original.last_at

    def test_hit_from_dict_missing_last_at_becomes_none(self):
        from gamepad_midi_bridge.control_heatmap import ControlHit
        d = {
            "control_type": "button",
            "control_id": "button.1",
            "count": 3,
        }
        hit = ControlHit.from_dict(d)
        assert hit.last_at is None

    def test_hit_from_dict_none_last_at_stays_none(self):
        from gamepad_midi_bridge.control_heatmap import ControlHit
        d = {
            "control_type": "button",
            "control_id": "button.2",
            "count": 7,
            "last_at": None,
        }
        hit = ControlHit.from_dict(d)
        assert hit.last_at is None


class TestControlHeatmapConfig:
    """ControlHeatmapConfig — clamp parameters on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        assert cfg.max_controls == 100

    def test_config_clamp_max_controls_below_10(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig
        cfg = ControlHeatmapConfig(max_controls=5)
        assert cfg.max_controls == 10
        cfg = ControlHeatmapConfig(max_controls=0)
        assert cfg.max_controls == 10

    def test_config_clamp_max_controls_above_10000(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig
        cfg = ControlHeatmapConfig(max_controls=10001)
        assert cfg.max_controls == 10000
        cfg = ControlHeatmapConfig(max_controls=99999)
        assert cfg.max_controls == 10000

    def test_config_no_clamp_max_controls_in_range(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig
        cfg = ControlHeatmapConfig(max_controls=500)
        assert cfg.max_controls == 500

    def test_config_to_dict(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig
        cfg = ControlHeatmapConfig(max_controls=250)
        d = cfg.to_dict()
        assert d["max_controls"] == 250

    def test_config_from_dict(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig
        d = {"max_controls": 500}
        cfg = ControlHeatmapConfig.from_dict(d)
        assert cfg.max_controls == 500

    def test_config_round_trip(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig
        original = ControlHeatmapConfig(max_controls=750)
        d = original.to_dict()
        restored = ControlHeatmapConfig.from_dict(d)
        assert restored.max_controls == original.max_controls


class TestControlHeatmap:
    """ControlHeatmap — record, query, and export activity data."""

    def test_empty_total_hits_zero(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        assert hm.total_hits() == 0

    def test_empty_unique_controls_zero(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        assert hm.unique_controls() == 0

    def test_empty_top_n_returns_empty_list(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        assert hm.top_n(5) == []

    def test_empty_bottom_n_returns_empty_list(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        assert hm.bottom_n(5) == []

    def test_record_single_creates_hit(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        assert hm.total_hits() == 1
        assert hm.unique_controls() == 1

    def test_record_twice_same_control_increments_count(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.0", 1001.0)
        assert hm.total_hits() == 2
        assert hm.unique_controls() == 1
        hit = hm.get_hit("button.0")
        assert hit is not None
        assert hit.count == 2

    def test_record_different_controls_increases_unique(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.1", 1001.0)
        hm.record("axis", "left_stick_x", 1002.0)
        assert hm.total_hits() == 3
        assert hm.unique_controls() == 3

    def test_top_n_sorts_descending(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.0", 1001.0)
        hm.record("button", "button.0", 1002.0)
        hm.record("button", "button.1", 1003.0)
        hm.record("button", "button.1", 1004.0)
        hm.record("button", "button.2", 1005.0)
        top = hm.top_n(3)
        assert len(top) == 3
        assert top[0].count == 3  # button.0
        assert top[1].count == 2  # button.1
        assert top[2].count == 1  # button.2

    def test_top_n_returns_fewer_if_not_enough_controls(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.1", 1001.0)
        top = hm.top_n(5)
        assert len(top) == 2

    def test_bottom_n_sorts_ascending(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.0", 1001.0)
        hm.record("button", "button.0", 1002.0)
        hm.record("button", "button.1", 1003.0)
        hm.record("button", "button.1", 1004.0)
        hm.record("button", "button.2", 1005.0)
        bottom = hm.bottom_n(3)
        assert len(bottom) == 3
        assert bottom[0].count == 1  # button.2
        assert bottom[1].count == 2  # button.1
        assert bottom[2].count == 3  # button.0

    def test_bottom_n_excludes_zero_count(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        # Manually insert a hit with count=0 (shouldn't happen in normal use,
        # but we want to be defensive)
        from gamepad_midi_bridge.control_heatmap import ControlHit
        hm._hits["button.zero"] = ControlHit(
            control_type="button",
            control_id="button.zero",
            count=0,
            last_at=1000.0,
        )
        hm.record("button", "button.1", 1001.0)
        hm.record("button", "button.1", 1002.0)
        bottom = hm.bottom_n(5)
        assert len(bottom) == 1
        assert bottom[0].control_id == "button.1"

    def test_by_type_filters_correctly(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.1", 1001.0)
        hm.record("axis", "left_stick_x", 1002.0)
        hm.record("axis", "right_stick_y", 1003.0)
        hm.record("trigger", "L2", 1004.0)
        buttons = hm.by_type("button")
        assert len(buttons) == 2
        assert all(h.control_type == "button" for h in buttons)
        axes = hm.by_type("axis")
        assert len(axes) == 2
        triggers = hm.by_type("trigger")
        assert len(triggers) == 1

    def test_by_type_returns_empty_if_no_matches(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        touchpads = hm.by_type("touchpad")
        assert len(touchpads) == 0

    def test_to_heatmap_returns_flat_dict(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.0", 1001.0)
        hm.record("button", "button.1", 1002.0)
        heatmap = hm.to_heatmap()
        assert heatmap == {"button.0": 2, "button.1": 1}

    def test_get_hit_returns_existing(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hit = hm.get_hit("button.0")
        assert hit is not None
        assert hit.control_id == "button.0"
        assert hit.count == 1

    def test_get_hit_returns_none_if_not_found(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hit = hm.get_hit("button.99")
        assert hit is None

    def test_all_hits_returns_copy(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.1", 1001.0)
        all_hits = hm.all_hits()
        assert len(all_hits) == 2
        assert "button.0" in all_hits
        assert "button.1" in all_hits
        # Verify it's a copy, not the original dict
        all_hits["button.2"] = None
        assert "button.2" not in hm._hits

    def test_max_controls_eviction_by_oldest_last_at(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig(max_controls=13)
        hm = ControlHeatmap(cfg)
        # Add 13 controls, all under max
        for i in range(13):
            hm.record("button", f"button.{i}", 1000.0 + i)
        assert hm.unique_controls() == 13
        # Add a 14th, should evict button.0 (oldest)
        hm.record("button", "button.99", 2000.0)
        assert hm.unique_controls() == 13
        assert hm.get_hit("button.0") is None
        assert hm.get_hit("button.1") is not None
        assert hm.get_hit("button.99") is not None

    def test_max_controls_eviction_prefers_none_last_at(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmapConfig, ControlHeatmap, ControlHit
        cfg = ControlHeatmapConfig(max_controls=12)
        hm = ControlHeatmap(cfg)
        # Manually create a hit with last_at=None
        hm._hits["orphan"] = ControlHit(
            control_type="button",
            control_id="orphan",
            count=0,
            last_at=None,
        )
        # Fill up to max_controls
        for i in range(11):
            hm.record("button", f"button.{i}", 1000.0 + i)
        assert hm.unique_controls() == 12
        # Add a 13th, should evict the orphan (last_at=None) first
        hm.record("button", "button.new", 2000.0)
        assert hm.unique_controls() == 12
        assert hm.get_hit("orphan") is None
        assert hm.get_hit("button.0") is not None
        assert hm.get_hit("button.new") is not None

    def test_last_at_updates_on_every_record(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hit = hm.get_hit("button.0")
        assert hit.last_at == 1000.0
        hm.record("button", "button.0", 2000.0)
        hit = hm.get_hit("button.0")
        assert hit.last_at == 2000.0
        hm.record("button", "button.0", 1500.0)
        hit = hm.get_hit("button.0")
        assert hit.last_at == 1500.0

    def test_clear(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        hm.record("button", "button.0", 1000.0)
        hm.record("button", "button.1", 1001.0)
        assert hm.unique_controls() == 2
        hm.clear()
        assert hm.unique_controls() == 0
        assert hm.total_hits() == 0
        assert hm.get_hit("button.0") is None

    def test_mixed_control_types_workflow(self):
        from gamepad_midi_bridge.control_heatmap import ControlHeatmap, ControlHeatmapConfig
        cfg = ControlHeatmapConfig()
        hm = ControlHeatmap(cfg)
        # Simulate a realistic session: mixed button, axis, trigger activity
        hm.record("button", "X", 0.0)
        hm.record("button", "X", 0.1)
        hm.record("button", "Square", 0.2)
        hm.record("axis", "left_stick_x", 0.3)
        hm.record("axis", "left_stick_x", 0.4)
        hm.record("axis", "left_stick_x", 0.5)
        hm.record("trigger", "L2", 0.6)
        hm.record("trigger", "L2", 0.7)
        hm.record("trigger", "R2", 0.8)

        assert hm.total_hits() == 9
        assert hm.unique_controls() == 5
        assert hm.get_hit("X").count == 2
        assert hm.get_hit("left_stick_x").count == 3
        assert hm.get_hit("L2").count == 2
        assert hm.get_hit("R2").count == 1
        assert hm.get_hit("Square").count == 1

        # Check top controls
        top_3 = hm.top_n(3)
        assert top_3[0].control_id == "left_stick_x"
        assert top_3[0].count == 3

        # Check by type
        buttons = hm.by_type("button")
        assert len(buttons) == 2
        triggers = hm.by_type("trigger")
        assert len(triggers) == 2

        # Check heatmap export
        heatmap = hm.to_heatmap()
        assert len(heatmap) == 5
        assert heatmap["left_stick_x"] == 3
