"""Tests for preset categories and folder management."""
from __future__ import annotations

from pathlib import Path

import pytest

from gamepad_midi_bridge import presets as preset_io


@pytest.fixture
def tmp_presets_dir(tmp_path, monkeypatch) -> Path:
    """Create a temporary presets directory and patch presets_dir()."""
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()
    monkeypatch.setattr(preset_io, "presets_dir", lambda: presets_dir)
    return presets_dir


def test_list_categories_empty(tmp_presets_dir) -> None:
    """Test list_categories returns empty list when no folders exist."""
    categories = preset_io.list_categories()
    assert categories == []


def test_list_categories_returns_folder_names(tmp_presets_dir) -> None:
    """Test list_categories returns top-level folder names."""
    # Create some folders
    (tmp_presets_dir / "Live").mkdir()
    (tmp_presets_dir / "Studio").mkdir()
    (tmp_presets_dir / "Testing").mkdir()

    categories = preset_io.list_categories()
    assert sorted(categories) == ["Live", "Studio", "Testing"]


def test_list_categories_ignores_hidden_folders(tmp_presets_dir) -> None:
    """Test that list_categories ignores hidden folders (starting with .)."""
    (tmp_presets_dir / "Live").mkdir()
    (tmp_presets_dir / ".hidden").mkdir()

    categories = preset_io.list_categories()
    assert categories == ["Live"]


def test_list_presets_includes_nested(tmp_presets_dir) -> None:
    """Test list_presets includes both top-level and nested presets."""
    # Top-level preset
    (tmp_presets_dir / "preset_toplevel.json").write_text("{}")

    # Nested presets
    (tmp_presets_dir / "Live").mkdir()
    (tmp_presets_dir / "Live" / "intro.json").write_text("{}")
    (tmp_presets_dir / "Live" / "chorus.json").write_text("{}")

    presets = preset_io.list_presets()
    assert "preset_toplevel" in presets
    assert "Live/intro" in presets
    assert "Live/chorus" in presets


def test_list_presets_returns_sorted(tmp_presets_dir) -> None:
    """Test list_presets returns sorted list."""
    (tmp_presets_dir / "z_preset.json").write_text("{}")
    (tmp_presets_dir / "a_preset.json").write_text("{}")

    (tmp_presets_dir / "Live").mkdir()
    (tmp_presets_dir / "Live" / "z_song.json").write_text("{}")
    (tmp_presets_dir / "Live" / "a_song.json").write_text("{}")

    presets = preset_io.list_presets()
    assert presets == sorted(presets)


def test_move_preset_to_folder(tmp_presets_dir) -> None:
    """Test moving a top-level preset to a folder."""
    # Create a preset at top level
    (tmp_presets_dir / "my_preset.json").write_text('{"name": "test"}')

    # Move it to a folder
    preset_io.move_preset("my_preset", "Live")

    # Check that it moved
    assert not (tmp_presets_dir / "my_preset.json").exists()
    assert (tmp_presets_dir / "Live" / "my_preset.json").exists()

    # Check that list_presets reflects the move
    presets = preset_io.list_presets()
    assert "my_preset" not in presets
    assert "Live/my_preset" in presets


def test_move_preset_to_toplevel(tmp_presets_dir) -> None:
    """Test moving a nested preset to top-level."""
    # Create a nested preset
    (tmp_presets_dir / "Live").mkdir()
    (tmp_presets_dir / "Live" / "intro.json").write_text('{"name": "intro"}')

    # Move it to top-level
    preset_io.move_preset("Live/intro", "")

    # Check that it moved
    assert not (tmp_presets_dir / "Live" / "intro.json").exists()
    assert (tmp_presets_dir / "intro.json").exists()

    # Check that list_presets reflects the move
    presets = preset_io.list_presets()
    assert "intro" in presets
    assert "Live/intro" not in presets


def test_move_preset_creates_folder(tmp_presets_dir) -> None:
    """Test that move_preset creates the destination folder if needed."""
    # Create a preset at top level
    (tmp_presets_dir / "my_preset.json").write_text("{}")

    # Move to a non-existent folder
    preset_io.move_preset("my_preset", "NewFolder")

    assert (tmp_presets_dir / "NewFolder" / "my_preset.json").exists()


def test_save_preset_nested(tmp_presets_dir) -> None:
    """Test saving a preset to a nested path."""
    from gamepad_midi_bridge.mapping import Mapping

    mapping = Mapping()
    mapping.name = "Live/my_song"

    result = preset_io.save_preset(mapping)

    assert result == tmp_presets_dir / "Live" / "my_song.json"
    assert (tmp_presets_dir / "Live" / "my_song.json").exists()


def test_delete_preset_nested(tmp_presets_dir) -> None:
    """Test deleting a nested preset."""
    # Create a nested preset
    (tmp_presets_dir / "Live").mkdir()
    (tmp_presets_dir / "Live" / "intro.json").write_text("{}")

    # Delete it
    preset_io.delete_preset("Live/intro")

    assert not (tmp_presets_dir / "Live" / "intro.json").exists()
