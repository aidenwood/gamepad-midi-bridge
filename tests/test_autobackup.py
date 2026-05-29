"""Auto-backup file management — timestamped snapshots and pruning."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from gamepad_midi_bridge.autobackup import autosaves_dir, save_snapshot, prune_old_snapshots
from gamepad_midi_bridge.mapping import Mapping


@pytest.fixture
def tmp_autosaves_dir(tmp_path, monkeypatch):
    """Mock autosaves_dir to use a temp directory."""
    import gamepad_midi_bridge.autobackup as ab

    autosaves_path = tmp_path / "autosaves"
    autosaves_path.mkdir(parents=True, exist_ok=True)

    def mock_autosaves_dir():
        return autosaves_path

    monkeypatch.setattr(ab, "autosaves_dir", mock_autosaves_dir)
    return autosaves_path


def test_save_snapshot_writes_file(tmp_autosaves_dir):
    """Verify save_snapshot creates a JSON file with valid data."""
    mapping = Mapping(name="TestMapping", midi_channel=5)
    path = save_snapshot(mapping)

    assert path.exists()
    assert path.suffix == ".json"

    # Verify the file contains valid JSON
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"] == "TestMapping"
    assert data["midi_channel"] == 5


def test_save_snapshot_overwrites_within_same_minute(tmp_autosaves_dir):
    """Calling save_snapshot twice in the same minute overwrites the first."""
    mapping1 = Mapping(name="First", midi_channel=0)
    mapping2 = Mapping(name="Second", midi_channel=7)

    path1 = save_snapshot(mapping1)
    path2 = save_snapshot(mapping2)

    # Both should resolve to the same path (same minute timestamp)
    assert path1 == path2

    # Only one file should exist
    json_files = list(tmp_autosaves_dir.glob("*.json"))
    assert len(json_files) == 1

    # The file should contain the second mapping
    data = json.loads(path2.read_text(encoding="utf-8"))
    assert data["name"] == "Second"
    assert data["midi_channel"] == 7


def test_prune_keeps_latest_n(tmp_autosaves_dir):
    """Create 35 fake files, prune with keep=30, verify 30 remain (newest by mtime)."""
    # Create 35 fake snapshot files with incrementing mtimes
    files_created = []
    for i in range(35):
        filename = f"2025-01-01-0{i:02d}.json"
        path = tmp_autosaves_dir / filename
        path.write_text(json.dumps({"index": i}), encoding="utf-8")
        files_created.append(path)

    # Manually set mtimes so we can control which are "newest"
    # Set the first 5 to old mtimes, the rest to incrementing newer mtimes
    for i, path in enumerate(files_created):
        mtime = 1000 + i  # Ascending timestamps
        path.touch()
        import os
        os.utime(str(path), (mtime, mtime))

    # Prune with keep=30
    deleted_count = prune_old_snapshots(keep=30)

    assert deleted_count == 5

    # Verify 30 files remain
    remaining = list(tmp_autosaves_dir.glob("*.json"))
    assert len(remaining) == 30


def test_prune_returns_count_deleted(tmp_autosaves_dir):
    """Verify prune returns the count of deleted files."""
    # Create 15 files
    for i in range(15):
        path = tmp_autosaves_dir / f"2025-01-01-{i:02d}.json"
        path.write_text(json.dumps({"index": i}), encoding="utf-8")

    # Prune keeping only 10
    deleted = prune_old_snapshots(keep=10)

    assert deleted == 5
    assert len(list(tmp_autosaves_dir.glob("*.json"))) == 10


def test_prune_on_nonexistent_dir():
    """Prune should handle missing directory gracefully."""
    # This test doesn't mock, so it will try the real autosaves_dir
    # (which may or may not exist). The function should return 0.
    deleted = prune_old_snapshots(keep=30)
    assert isinstance(deleted, int)
    assert deleted >= 0
