"""Tests for CC snapshot capture and restoration.

CcSnapshotStore tracks live CC values across channels and allows capture/restore
of named snapshots. Pure stdlib, no Qt.
"""
from __future__ import annotations

import json
import time

import pytest


class TestCcSnapshot:
    """CcSnapshot dataclass — serialize/deserialize."""

    def test_snapshot_default_construction(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshot
        snap = CcSnapshot()
        assert snap.name == ""
        assert snap.created_at_s == 0.0
        assert snap.values == {}

    def test_snapshot_with_values(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshot
        snap = CcSnapshot(
            name="test",
            created_at_s=12345.0,
            values={(1, 7): 100, (2, 11): 64}
        )
        assert snap.name == "test"
        assert snap.created_at_s == 12345.0
        assert snap.values == {(1, 7): 100, (2, 11): 64}

    def test_snapshot_to_dict(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshot
        snap = CcSnapshot(
            name="vol+exp",
            created_at_s=12345.0,
            values={(1, 7): 100, (1, 11): 80}
        )
        d = snap.to_dict()
        assert d["name"] == "vol+exp"
        assert d["created_at_s"] == 12345.0
        assert "1_7" in d["values"]
        assert d["values"]["1_7"] == 100
        assert d["values"]["1_11"] == 80

    def test_snapshot_from_dict(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshot
        d = {
            "name": "restore",
            "created_at_s": 99999.0,
            "values": {"1_7": 50, "2_11": 75}
        }
        snap = CcSnapshot.from_dict(d)
        assert snap.name == "restore"
        assert snap.created_at_s == 99999.0
        assert snap.values == {(1, 7): 50, (2, 11): 75}

    def test_snapshot_round_trip(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshot
        original = CcSnapshot(
            name="round",
            created_at_s=55555.0,
            values={(1, 7): 100, (2, 11): 80, (16, 127): 1}
        )
        d = original.to_dict()
        restored = CcSnapshot.from_dict(d)
        assert restored.name == original.name
        assert restored.created_at_s == original.created_at_s
        assert restored.values == original.values


class TestCcSnapshotConfig:
    """CcSnapshotConfig — clamp max_snapshots on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotConfig
        cfg = CcSnapshotConfig()
        assert cfg.max_snapshots == 16
        assert cfg.auto_capture_on_preset_change is False

    def test_config_clamp_max_snapshots_below_one(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotConfig
        cfg = CcSnapshotConfig(max_snapshots=0)
        assert cfg.max_snapshots == 1
        cfg = CcSnapshotConfig(max_snapshots=-5)
        assert cfg.max_snapshots == 1

    def test_config_clamp_max_snapshots_above_256(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotConfig
        cfg = CcSnapshotConfig(max_snapshots=300)
        assert cfg.max_snapshots == 256
        cfg = CcSnapshotConfig(max_snapshots=1000)
        assert cfg.max_snapshots == 256

    def test_config_no_clamp_in_range(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotConfig
        cfg = CcSnapshotConfig(max_snapshots=50)
        assert cfg.max_snapshots == 50

    def test_config_to_dict(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotConfig
        cfg = CcSnapshotConfig(max_snapshots=20, auto_capture_on_preset_change=True)
        d = cfg.to_dict()
        assert d["max_snapshots"] == 20
        assert d["auto_capture_on_preset_change"] is True

    def test_config_from_dict(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotConfig
        d = {"max_snapshots": 32, "auto_capture_on_preset_change": True}
        cfg = CcSnapshotConfig.from_dict(d)
        assert cfg.max_snapshots == 32
        assert cfg.auto_capture_on_preset_change is True

    def test_config_round_trip(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotConfig
        original = CcSnapshotConfig(max_snapshots=24, auto_capture_on_preset_change=True)
        d = original.to_dict()
        restored = CcSnapshotConfig.from_dict(d)
        assert restored.max_snapshots == original.max_snapshots
        assert restored.auto_capture_on_preset_change == original.auto_capture_on_preset_change


class TestCcSnapshotStore:
    """CcSnapshotStore — observe, capture, list, find, delete, restore."""

    def test_store_default_construction(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        assert len(store.list_snapshots()) == 0
        assert store.find("nonexistent") is None

    def test_store_observe_updates_live(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        snap = store.capture("test")
        assert snap.values == {(1, 7): 100}

    def test_store_observe_multiple_ccs(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.observe(1, 11, 80)
        store.observe(2, 7, 50)
        snap = store.capture("multi")
        assert len(snap.values) == 3
        assert snap.values[(1, 7)] == 100
        assert snap.values[(1, 11)] == 80
        assert snap.values[(2, 7)] == 50

    def test_store_observe_clamp_channel(self):
        """Channel clamped to 1..16."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(0, 7, 100)
        store.observe(17, 7, 50)
        snap = store.capture("clamp_ch")
        assert (1, 7) in snap.values
        assert (16, 7) in snap.values

    def test_store_observe_clamp_cc(self):
        """CC clamped to 0..127."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, -1, 100)
        store.observe(1, 128, 50)
        snap = store.capture("clamp_cc")
        assert snap.values[(1, 0)] == 100
        assert snap.values[(1, 127)] == 50

    def test_store_observe_clamp_value(self):
        """CC value clamped to 0..127."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, -10)
        store.observe(1, 11, 200)
        snap = store.capture("clamp_val")
        assert snap.values[(1, 7)] == 0
        assert snap.values[(1, 11)] == 127

    def test_store_capture_creates_snapshot(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        snap = store.capture("first")
        assert snap.name == "first"
        assert snap.values == {(1, 7): 100}
        assert len(store.list_snapshots()) == 1

    def test_store_capture_with_timestamp(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        snap = store.capture("with_ts", now_s=12345.0)
        assert snap.created_at_s == 12345.0

    def test_store_capture_auto_timestamp(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        before = time.time()
        snap = store.capture("auto_ts")
        after = time.time()
        assert before <= snap.created_at_s <= after

    def test_store_capture_deep_copy(self):
        """Modifying live after capture doesn't affect snapshot."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        snap = store.capture("snap1")
        store.observe(1, 7, 50)
        assert snap.values[(1, 7)] == 100
        snap2 = store.capture("snap2")
        assert snap2.values[(1, 7)] == 50

    def test_store_list_snapshots_is_copy(self):
        """Mutating list doesn't affect internal store."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("first")
        lst = store.list_snapshots()
        lst.clear()
        assert len(store.list_snapshots()) == 1

    def test_store_find_returns_snapshot(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("test_snap")
        found = store.find("test_snap")
        assert found is not None
        assert found.name == "test_snap"
        assert found.values == {(1, 7): 100}

    def test_store_find_nonexistent_returns_none(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        assert store.find("missing") is None

    def test_store_delete_removes_snapshot(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("snap1")
        assert store.delete("snap1") is True
        assert store.find("snap1") is None
        assert len(store.list_snapshots()) == 0

    def test_store_delete_nonexistent_returns_false(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        assert store.delete("missing") is False

    def test_store_delete_one_of_many(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("snap1")
        store.observe(1, 11, 80)
        store.capture("snap2")
        assert store.delete("snap1") is True
        assert len(store.list_snapshots()) == 1
        assert store.find("snap2") is not None

    def test_store_max_snapshots_truncates_oldest(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig(max_snapshots=3)
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 1)
        store.capture("snap1")
        store.observe(1, 7, 2)
        store.capture("snap2")
        store.observe(1, 7, 3)
        store.capture("snap3")
        store.observe(1, 7, 4)
        store.capture("snap4")
        assert store.find("snap1") is None
        assert store.find("snap4") is not None
        assert len(store.list_snapshots()) == 3

    def test_store_restore_messages_empty_snapshot(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        msgs = store.restore_messages("empty")
        assert msgs == []

    def test_store_restore_messages_nonexistent(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        msgs = store.restore_messages("missing")
        assert msgs == []

    def test_store_restore_messages_single_cc(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("snap")
        msgs = store.restore_messages("snap")
        assert len(msgs) == 1
        assert msgs[0][0] == 0xB0
        assert msgs[0][1] == 7
        assert msgs[0][2] == 100

    def test_store_restore_messages_channel_encoding(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.observe(16, 7, 50)
        store.capture("snap")
        msgs = store.restore_messages("snap")
        assert len(msgs) == 2
        ch1_msg = [m for m in msgs if m[0] == 0xB0][0]
        ch16_msg = [m for m in msgs if m[0] == 0xBF][0]
        assert ch1_msg[1] == 7 and ch1_msg[2] == 100
        assert ch16_msg[1] == 7 and ch16_msg[2] == 50

    def test_store_restore_messages_multiple_ccs(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.observe(1, 11, 80)
        store.observe(1, 64, 127)
        store.capture("snap")
        msgs = store.restore_messages("snap")
        assert len(msgs) == 3
        ccs = sorted([m[1] for m in msgs])
        assert ccs == [7, 11, 64]

    def test_store_diff_identical(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.observe(1, 11, 80)
        store.capture("snap")
        diff = store.diff("snap")
        assert diff == {}

    def test_store_diff_changed_value(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("snap")
        store.observe(1, 7, 50)
        diff = store.diff("snap")
        assert (1, 7) in diff
        assert diff[(1, 7)] == (50, 100)

    def test_store_diff_added_live_cc(self):
        """Diff includes CCs added to live after snapshot."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("snap")
        store.observe(1, 11, 80)
        diff = store.diff("snap")
        assert (1, 11) in diff
        assert diff[(1, 11)] == (80, 0)

    def test_store_diff_removed_live_cc(self):
        """Diff reports missing live CC as (0, snapshot_value)."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.observe(1, 11, 80)
        store.capture("snap")
        store.clear_live()
        store.observe(1, 7, 100)
        diff = store.diff("snap")
        assert (1, 11) in diff
        assert diff[(1, 11)] == (0, 80)

    def test_store_diff_nonexistent_snapshot(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        diff = store.diff("missing")
        assert diff == {}

    def test_store_clear_snapshots(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.capture("snap1")
        store.capture("snap2")
        assert len(store.list_snapshots()) == 2
        store.clear_snapshots()
        assert len(store.list_snapshots()) == 0

    def test_store_clear_live(self):
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)
        store.observe(1, 7, 100)
        store.observe(1, 11, 80)
        store.clear_live()
        snap = store.capture("empty")
        assert snap.values == {}

    def test_store_complete_workflow(self):
        """End-to-end: observe, capture, restore, diff."""
        from gamepad_midi_bridge.cc_snapshot import CcSnapshotStore, CcSnapshotConfig
        cfg = CcSnapshotConfig()
        store = CcSnapshotStore(cfg)

        store.observe(1, 7, 100)
        store.observe(1, 11, 80)
        store.capture("State1")

        store.observe(1, 7, 50)
        store.observe(1, 11, 100)
        store.capture("State2")

        diff = store.diff("State1")
        assert diff[(1, 7)] == (50, 100)
        assert diff[(1, 11)] == (100, 80)

        msgs = store.restore_messages("State1")
        assert len(msgs) == 2
        restore_vals = {m[1]: m[2] for m in msgs}
        assert restore_vals[7] == 100
        assert restore_vals[11] == 80
