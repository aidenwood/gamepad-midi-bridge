"""Tests for the named-snapshot module (gamepad_midi_bridge.snapshots)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from gamepad_midi_bridge import snapshots as snap_mod
from gamepad_midi_bridge.snapshots import (
    delete_snapshot,
    list_snapshots,
    load_snapshot,
    save_snapshot,
    slugify,
)
from gamepad_midi_bridge.mapping import Mapping


# ---------------------------------------------------------------------------
# Fixture — redirect _snapshots_dir to a tmp directory
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_snap_dir(tmp_path, monkeypatch):
    """Patch _snapshots_dir so all snapshot I/O goes to a temp directory."""
    snap_path = tmp_path / "snapshots"
    snap_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(snap_mod, "_snapshots_dir", lambda: snap_path)
    return snap_path


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert slugify("Live set v1") == "live-set-v1"


def test_slugify_strips_specials():
    assert slugify("Studio / version!") == "studio-version"


def test_slugify_trims_hyphens():
    assert slugify("  !!hello world!!  ") == "hello-world"


def test_slugify_empty_returns_snapshot():
    assert slugify("") == "snapshot"
    assert slugify("!!!") == "snapshot"


def test_slugify_already_clean():
    assert slugify("backup-2025") == "backup-2025"


# ---------------------------------------------------------------------------
# save_snapshot
# ---------------------------------------------------------------------------

def test_save_snapshot_writes_file(tmp_snap_dir):
    mapping = Mapping(name="Live set v1", midi_channel=3)
    path = save_snapshot(mapping, "Live set v1")

    assert path.exists()
    assert path.suffix == ".json"
    assert path.parent == tmp_snap_dir


def test_save_snapshot_atomic_no_tmp_left(tmp_snap_dir):
    """No .tmp file should survive after a successful write."""
    mapping = Mapping(name="Test", midi_channel=0)
    save_snapshot(mapping, "Test")

    tmp_files = list(tmp_snap_dir.glob("*.tmp"))
    assert tmp_files == []


def test_save_snapshot_embeds_human_name(tmp_snap_dir):
    mapping = Mapping(name="ignored", midi_channel=0)
    path = save_snapshot(mapping, "My Custom Name!")

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw.get("_snapshot_name") == "My Custom Name!"


def test_save_snapshot_slug_filename(tmp_snap_dir):
    mapping = Mapping(name="X", midi_channel=0)
    path = save_snapshot(mapping, "Studio Version 2")

    assert path.name == "studio-version-2.json"


def test_save_snapshot_overwrites_same_slug(tmp_snap_dir):
    mapping_a = Mapping(name="A", midi_channel=1)
    mapping_b = Mapping(name="B", midi_channel=9)
    save_snapshot(mapping_a, "set")
    save_snapshot(mapping_b, "set")

    files = list(tmp_snap_dir.glob("*.json"))
    assert len(files) == 1

    raw = json.loads(files[0].read_text(encoding="utf-8"))
    assert raw["midi_channel"] == 9


def test_save_snapshot_returns_path(tmp_snap_dir):
    mapping = Mapping(name="X", midi_channel=0)
    result = save_snapshot(mapping, "my snapshot")
    assert isinstance(result, Path)
    assert result.exists()


# ---------------------------------------------------------------------------
# list_snapshots
# ---------------------------------------------------------------------------

def test_list_snapshots_empty(tmp_snap_dir):
    assert list_snapshots() == []


def test_list_snapshots_returns_all(tmp_snap_dir):
    for name in ("First", "Second", "Third"):
        save_snapshot(Mapping(name=name), name)

    infos = list_snapshots()
    assert len(infos) == 3


def test_list_snapshots_sorted_mtime_desc(tmp_snap_dir):
    """Create snapshots with known mtimes and verify descending order."""
    names = ["alpha", "beta", "gamma"]
    paths = []
    for name in names:
        p = save_snapshot(Mapping(name=name), name)
        paths.append(p)

    # Force known ascending mtimes: alpha=100, beta=200, gamma=300
    base_mtime = 1_700_000_000
    for i, p in enumerate(paths):
        os.utime(str(p), (base_mtime + i * 100, base_mtime + i * 100))

    infos = list_snapshots()
    slugs = [s.slug for s in infos]
    assert slugs == ["gamma", "beta", "alpha"]


def test_list_snapshots_info_fields(tmp_snap_dir):
    mapping = Mapping(name="My Preset", midi_channel=5)
    save_snapshot(mapping, "My Preset")

    infos = list_snapshots()
    assert len(infos) == 1
    info = infos[0]
    assert info.slug == "my-preset"
    assert info.name == "My Preset"
    assert info.mtime > 0
    assert info.size > 0


def test_list_snapshots_skips_corrupt_file(tmp_snap_dir):
    """A corrupt JSON file should not crash list_snapshots."""
    bad = tmp_snap_dir / "corrupt.json"
    bad.write_text("not valid json {{{", encoding="utf-8")

    save_snapshot(Mapping(name="good"), "good")
    infos = list_snapshots()

    slugs = [s.slug for s in infos]
    assert "good" in slugs
    assert "corrupt" not in slugs


# ---------------------------------------------------------------------------
# load_snapshot
# ---------------------------------------------------------------------------

def test_load_snapshot_round_trips_mapping(tmp_snap_dir):
    original = Mapping(name="Round trip", midi_channel=7, poll_hz=200)
    save_snapshot(original, "Round trip")

    loaded = load_snapshot("round-trip")
    assert loaded is not None
    assert loaded.name == "Round trip"
    assert loaded.midi_channel == 7
    assert loaded.poll_hz == 200


def test_load_snapshot_missing_returns_none(tmp_snap_dir):
    result = load_snapshot("does-not-exist")
    assert result is None


def test_load_snapshot_corrupt_returns_none(tmp_snap_dir):
    bad = tmp_snap_dir / "bad.json"
    bad.write_text("{{{{", encoding="utf-8")

    result = load_snapshot("bad")
    assert result is None


def test_load_snapshot_strips_private_key(tmp_snap_dir):
    """_snapshot_name meta-key must not leak into the returned Mapping."""
    save_snapshot(Mapping(name="X"), "my snap")
    loaded = load_snapshot("my-snap")
    assert loaded is not None
    # Mapping has no _snapshot_name attribute — just verify it loads cleanly
    assert not hasattr(loaded, "_snapshot_name")


# ---------------------------------------------------------------------------
# delete_snapshot
# ---------------------------------------------------------------------------

def test_delete_snapshot_removes_file(tmp_snap_dir):
    save_snapshot(Mapping(name="ToDelete"), "ToDelete")
    assert (tmp_snap_dir / "todelete.json").exists()

    result = delete_snapshot("todelete")
    assert result is True
    assert not (tmp_snap_dir / "todelete.json").exists()


def test_delete_snapshot_missing_returns_false(tmp_snap_dir):
    result = delete_snapshot("ghost")
    assert result is False


def test_delete_snapshot_not_in_list_afterwards(tmp_snap_dir):
    save_snapshot(Mapping(name="A"), "A")
    save_snapshot(Mapping(name="B"), "B")

    delete_snapshot("a")
    slugs = [s.slug for s in list_snapshots()]
    assert "a" not in slugs
    assert "b" in slugs
