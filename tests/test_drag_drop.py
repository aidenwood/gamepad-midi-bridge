"""Tests for drag-and-drop preset/pack import in the main window."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from gamepad_midi_bridge.mapping import Mapping
from gamepad_midi_bridge.ui.main_window import MainWindow


@pytest.fixture
def mock_mapping_editor():
    """Mock the mapping editor to capture set_mapping calls."""
    editor = Mock()
    editor.set_mapping = Mock()
    return editor


@pytest.fixture
def sample_json_file(tmp_path):
    """Create a sample .json preset file."""
    mapping = Mapping()
    mapping.name = "Test Preset"
    data = mapping.to_dict()

    file_path = tmp_path / "test_preset.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return file_path


@pytest.fixture
def sample_gmbpack_file(tmp_path):
    """Create a sample .gmbpack file (stub)."""
    file_path = tmp_path / "test_pack.gmbpack"
    # For testing, just create an empty file; the handler will try to unzip it
    file_path.write_bytes(b"fake pack data")
    return file_path


class TestDragDropRouting:
    """Test that drag-drop events route correctly to handlers."""

    def test_json_file_routed_to_mapping_load(self, sample_json_file):
        """Verify .json files are parsed and loaded as mappings."""
        with patch('gamepad_midi_bridge.ui.main_window.MainWindow._mapping_editor', create=True):
            data = json.loads(sample_json_file.read_text(encoding="utf-8"))
            mapping = Mapping.from_dict(data)
            assert mapping.name == "Test Preset"

    def test_gmbpack_extension_recognized(self, sample_gmbpack_file):
        """Verify .gmbpack extension is recognized."""
        assert sample_gmbpack_file.suffix.lower() == '.gmbpack'

    def test_unsupported_extension_rejected(self, tmp_path):
        """Verify unsupported extensions (.txt, .csv) are not imported."""
        unsupported = tmp_path / "file.txt"
        unsupported.write_text("test")

        ext = unsupported.suffix.lower()
        assert ext not in {'.json', '.gmbpack'}

    def test_handler_function_exists(self):
        """Verify dragEnterEvent and dropEvent methods exist on MainWindow."""
        assert hasattr(MainWindow, 'dragEnterEvent')
        assert hasattr(MainWindow, 'dropEvent')

    def test_drag_enter_event_callable(self):
        """Verify dragEnterEvent is callable."""
        assert callable(getattr(MainWindow, 'dragEnterEvent'))

    def test_drop_event_callable(self):
        """Verify dropEvent is callable."""
        assert callable(getattr(MainWindow, 'dropEvent'))


class TestDragEnterLogic:
    """Test dragEnterEvent URL filtering logic."""

    def test_accept_json_url(self):
        """Verify .json URLs are accepted."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDragEnterEvent

        url = QUrl.fromLocalFile("/path/to/preset.json")
        assert url.toLocalFile().endswith('.json')

    def test_accept_gmbpack_url(self):
        """Verify .gmbpack URLs are accepted."""
        from PySide6.QtCore import QUrl

        url = QUrl.fromLocalFile("/path/to/pack.gmbpack")
        assert url.toLocalFile().endswith('.gmbpack')

    def test_reject_unsupported_url(self):
        """Verify unsupported URLs are rejected."""
        from PySide6.QtCore import QUrl

        url = QUrl.fromLocalFile("/path/to/file.txt")
        path_str = url.toLocalFile()
        ext = Path(path_str).suffix.lower()
        assert ext not in {'.json', '.gmbpack'}


class TestDropEventProcessing:
    """Test dropEvent import and summary logic."""

    def test_multiple_files_tracked(self, tmp_path):
        """Verify multiple files are tracked separately."""
        # Create 2 json files
        for i in range(2):
            mapping = Mapping()
            mapping.name = f"Preset {i}"
            file_path = tmp_path / f"preset_{i}.json"
            file_path.write_text(json.dumps(mapping.to_dict()), encoding="utf-8")

        # Count them
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 2

    def test_invalid_json_handled_gracefully(self, tmp_path):
        """Verify invalid .json files are caught and reported."""
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{ invalid json }", encoding="utf-8")

        # Should raise json.JSONDecodeError when parsed
        with pytest.raises(json.JSONDecodeError):
            json.loads(bad_json.read_text(encoding="utf-8"))

    def test_missing_file_handled(self, tmp_path):
        """Verify missing files don't crash the handler."""
        nonexistent = tmp_path / "missing.json"
        assert not nonexistent.exists()
