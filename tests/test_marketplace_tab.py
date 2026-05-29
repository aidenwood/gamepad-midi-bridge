"""
Tests for MarketplaceTab widget — search, tag filters, sort, result count.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtCore import Qt

from gamepad_midi_bridge.ui.marketplace_tab import MarketplaceTab


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def marketplace_tab(qapp):
    """Create a MarketplaceTab instance."""
    with patch('gamepad_midi_bridge.ui.marketplace_tab.QNetworkAccessManager'):
        tab = MarketplaceTab()
        tab._presets = [
            {
                "id": "preset-1",
                "title": "Neon Vibes",
                "description": "Glowy MIDI mapping for Resolume",
                "author": {"display_name": "Alex", "github_handle": "alex-dev"},
                "host_target": "resolume",
                "device_target": "dualsense",
                "downloads": 150,
                "rating": 4.8,
                "tags": ["neon", "resolume", "visual"],
            },
            {
                "id": "preset-2",
                "title": "Dark Mode",
                "description": "Minimal MIDI for Ableton",
                "author": {"display_name": "Chris", "github_handle": "chris-beats"},
                "host_target": "ableton",
                "device_target": "dualsense",
                "downloads": 320,
                "rating": 4.9,
                "tags": ["minimal", "ableton", "dark"],
            },
            {
                "id": "preset-3",
                "title": "Synth Alchemy",
                "description": "Complex MIDI for TouchDesigner",
                "author": {"display_name": "Sam", "github_handle": "sam-sync"},
                "host_target": "touchdesigner",
                "device_target": "xbox",
                "downloads": 89,
                "rating": 4.5,
                "tags": ["synth", "touchdesigner", "advanced"],
            },
        ]
        yield tab


def test_marketplace_tab_creation(marketplace_tab):
    """MarketplaceTab creation doesn't crash."""
    assert marketplace_tab is not None
    assert marketplace_tab._presets is not None
    assert marketplace_tab._visible_presets == []


def test_search_filter_title(marketplace_tab):
    """Search filters presets by title (case-insensitive)."""
    marketplace_tab._search.setText("neon")
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["title"] == "Neon Vibes"


def test_search_filter_description(marketplace_tab):
    """Search filters presets by description."""
    marketplace_tab._search.setText("minimal")
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["title"] == "Dark Mode"


def test_search_filter_author(marketplace_tab):
    """Search filters presets by author name."""
    marketplace_tab._search.setText("chris")
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["title"] == "Dark Mode"


def test_search_filter_tags(marketplace_tab):
    """Search filters presets by tags."""
    marketplace_tab._search.setText("synth")
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["title"] == "Synth Alchemy"


def test_search_case_insensitive(marketplace_tab):
    """Search is case-insensitive."""
    marketplace_tab._search.setText("DARK")
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["title"] == "Dark Mode"


def test_tag_chip_toggle_single(marketplace_tab):
    """Clicking a tag chip filters to that tag."""
    marketplace_tab._toggle_tag_filter("neon")
    assert "neon" in marketplace_tab._selected_tags
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["tags"] == ["neon", "resolume", "visual"]


def test_tag_chip_toggle_deselect(marketplace_tab):
    """Clicking a selected tag chip deselects it."""
    marketplace_tab._toggle_tag_filter("neon")
    marketplace_tab._toggle_tag_filter("neon")
    assert "neon" not in marketplace_tab._selected_tags
    assert len(marketplace_tab._visible_presets) == 3


def test_tag_chip_toggle_multiple(marketplace_tab):
    """Multiple tag chips require preset to match at least one."""
    marketplace_tab._toggle_tag_filter("neon")
    marketplace_tab._toggle_tag_filter("minimal")
    # Presets matching either neon OR minimal
    assert len(marketplace_tab._visible_presets) == 2


def test_sort_newest(marketplace_tab):
    """Sort by newest (descending ID)."""
    marketplace_tab._set_sort("newest")
    assert len(marketplace_tab._visible_presets) == 3
    # IDs: preset-1, preset-2, preset-3; reverse sort
    assert marketplace_tab._visible_presets[0]["id"] == "preset-3"


def test_sort_downloads(marketplace_tab):
    """Sort by most downloads."""
    marketplace_tab._set_sort("downloads")
    assert marketplace_tab._visible_presets[0]["downloads"] == 320
    assert marketplace_tab._visible_presets[-1]["downloads"] == 89


def test_sort_rating(marketplace_tab):
    """Sort by highest rating."""
    marketplace_tab._set_sort("rating")
    assert marketplace_tab._visible_presets[0]["rating"] == 4.9
    assert marketplace_tab._visible_presets[-1]["rating"] == 4.5


def test_sort_name(marketplace_tab):
    """Sort by name A-Z."""
    marketplace_tab._set_sort("name")
    assert marketplace_tab._visible_presets[0]["title"] == "Dark Mode"
    assert marketplace_tab._visible_presets[1]["title"] == "Neon Vibes"
    assert marketplace_tab._visible_presets[2]["title"] == "Synth Alchemy"


def test_host_filter(marketplace_tab):
    """Host filter narrows results."""
    marketplace_tab._host_combo.setCurrentIndex(1)  # Resolume
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["host_target"] == "resolume"


def test_device_filter(marketplace_tab):
    """Device filter narrows results."""
    marketplace_tab._device_combo.setCurrentIndex(2)  # Xbox
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["device_target"] == "xbox"


def test_combined_filters(marketplace_tab):
    """Host + device + search + tag filters work together."""
    marketplace_tab._search.setText("MIDI")
    marketplace_tab._host_combo.setCurrentIndex(2)  # Ableton
    marketplace_tab._toggle_tag_filter("minimal")
    assert len(marketplace_tab._visible_presets) == 1
    assert marketplace_tab._visible_presets[0]["title"] == "Dark Mode"


def test_result_count_display(marketplace_tab):
    """Result count updates correctly."""
    marketplace_tab._cache_fetched_at = 1.0
    marketplace_tab._search.setText("neon")
    marketplace_tab._refresh_visible()
    marketplace_tab._render_list()
    # Status label shows "Showing 1 of 3 presets"
    assert "1 of 3" in marketplace_tab._status_label.text()


def test_empty_results_on_no_match(marketplace_tab):
    """Empty message when search has no results."""
    marketplace_tab._search.setText("xyz-nonexistent")
    marketplace_tab._refresh_visible()
    assert len(marketplace_tab._visible_presets) == 0


def test_tag_chips_built_from_all_presets(marketplace_tab):
    """Tag chips are built from all _presets, not just _visible."""
    marketplace_tab._search.setText("neon")
    marketplace_tab._refresh_visible()
    # Visible is 1, but tag chips should show all unique tags from _presets
    marketplace_tab._build_tag_chips()
    # Check that tag chips layout has chips (more than just the stretch)
    chip_count = marketplace_tab._tag_chips_layout.count() - 1  # -1 for stretch
    assert chip_count > 0, "Tag chips should be rendered"
