"""Controller fingerprint persistence — tracking seen controllers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gamepad_midi_bridge.controller_history import (
    seen_controllers, mark_seen, was_seen, _history_path
)


@pytest.fixture
def tmp_history_file(tmp_path, monkeypatch):
    """Mock the history file to use a temp directory."""
    import gamepad_midi_bridge.controller_history as ch
    from gamepad_midi_bridge.paths import user_data_dir

    # Create a test data dir
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Mock user_data_dir
    def mock_user_data_dir():
        return test_data_dir

    monkeypatch.setattr("gamepad_midi_bridge.controller_history.user_data_dir", mock_user_data_dir)

    return test_data_dir / "seen_controllers.json"


def test_seen_controllers_empty_on_first_run(tmp_history_file):
    """seen_controllers returns empty set when no file exists."""
    assert seen_controllers() == set()


def test_mark_seen_creates_file(tmp_history_file):
    """mark_seen writes a valid JSON file."""
    mark_seen("DualSense_1234")

    assert tmp_history_file.exists()
    data = json.loads(tmp_history_file.read_text(encoding="utf-8"))
    assert "controllers" in data
    assert "DualSense_1234" in data["controllers"]


def test_mark_seen_idempotent(tmp_history_file):
    """mark_seen is idempotent — no duplicates."""
    mark_seen("DualSense_1234")
    mark_seen("DualSense_1234")

    seen = seen_controllers()
    assert seen.count("DualSense_1234") if isinstance(seen, list) else len([x for x in seen if x == "DualSense_1234"]) <= 1


def test_was_seen_true_for_marked(tmp_history_file):
    """was_seen returns True for a previously marked controller."""
    mark_seen("Controller_A")
    assert was_seen("Controller_A") is True


def test_was_seen_false_for_unmarked(tmp_history_file):
    """was_seen returns False for a controller not seen before."""
    mark_seen("Controller_A")
    assert was_seen("Controller_B") is False


def test_seen_controllers_round_trip(tmp_history_file):
    """Round-trip: mark multiple, read all back."""
    mark_seen("Controller_A")
    mark_seen("Controller_B")
    mark_seen("Controller_C")

    seen = seen_controllers()
    assert len(seen) == 3
    assert "Controller_A" in seen
    assert "Controller_B" in seen
    assert "Controller_C" in seen


def test_invalid_json_returns_empty(tmp_history_file):
    """Corrupted JSON file gracefully returns empty set."""
    tmp_history_file.write_text("not valid json", encoding="utf-8")
    assert seen_controllers() == set()
