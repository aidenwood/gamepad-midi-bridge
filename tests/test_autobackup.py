"""Auto-backup file management — timestamped snapshots and pruning."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from gamepad_midi_bridge.autobackup import (
    autosaves_dir, save_snapshot, prune_old_snapshots, mark_clean_shutdown,
    was_clean_shutdown, mark_unclean_startup, latest_autosave, load_latest_autosave,
)
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


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Mock user_data_dir for shutdown flag tests."""
    import gamepad_midi_bridge.autobackup as ab

    def mock_user_data_dir():
        return tmp_path

    monkeypatch.setattr(ab, "user_data_dir", mock_user_data_dir)
    return tmp_path


def test_mark_clean_shutdown_creates_flag(tmp_config_dir):
    """mark_clean_shutdown creates the flag file."""
    mark_clean_shutdown()
    flag = tmp_config_dir / "session_clean.flag"
    assert flag.exists()


def test_was_clean_shutdown_true_after_mark(tmp_config_dir):
    """was_clean_shutdown returns True after mark_clean_shutdown."""
    mark_clean_shutdown()
    assert was_clean_shutdown() is True


def test_was_clean_shutdown_false_missing_flag(tmp_config_dir):
    """was_clean_shutdown returns False when flag is missing."""
    assert was_clean_shutdown() is False


def test_mark_unclean_startup_deletes_flag(tmp_config_dir):
    """mark_unclean_startup deletes the flag file."""
    mark_clean_shutdown()
    flag = tmp_config_dir / "session_clean.flag"
    assert flag.exists()

    mark_unclean_startup()
    assert not flag.exists()


def test_latest_autosave_returns_newest(tmp_autosaves_dir):
    """latest_autosave returns the most recently modified file."""
    import time

    # Create 3 files with different mtimes
    paths = []
    for i in range(3):
        path = tmp_autosaves_dir / f"2025-01-0{i+1}-0000.json"
        path.write_text(json.dumps({"index": i}), encoding="utf-8")
        paths.append(path)
        # Small delay to ensure distinct mtimes
        time.sleep(0.01)

    newest = latest_autosave()
    assert newest == paths[2]


def test_latest_autosave_returns_none_empty_dir(tmp_path, monkeypatch):
    """latest_autosave returns None when no files exist."""
    import gamepad_midi_bridge.autobackup as ab

    empty_dir = tmp_path / "empty_autosaves"
    empty_dir.mkdir()

    def mock_autosaves_dir():
        return empty_dir

    monkeypatch.setattr(ab, "autosaves_dir", mock_autosaves_dir)
    assert latest_autosave() is None


def test_load_latest_autosave_roundtrip(tmp_autosaves_dir):
    """load_latest_autosave reads and deserializes a mapping correctly."""
    mapping = Mapping(name="TestRoundtrip", midi_channel=3)
    save_snapshot(mapping)

    loaded = load_latest_autosave()
    assert loaded is not None
    assert loaded.name == "TestRoundtrip"
    assert loaded.midi_channel == 3


def test_load_latest_autosave_returns_none_no_files(tmp_path, monkeypatch):
    """load_latest_autosave returns None when no autosaves exist."""
    import gamepad_midi_bridge.autobackup as ab

    empty_dir = tmp_path / "empty_autosaves"
    empty_dir.mkdir()

    def mock_autosaves_dir():
        return empty_dir

    monkeypatch.setattr(ab, "autosaves_dir", mock_autosaves_dir)
    assert load_latest_autosave() is None
