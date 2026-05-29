"""
Tests for AboutTab widget.
"""
import pytest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt

from gamepad_midi_bridge.ui.about_tab import AboutTab, get_build_info


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_about_tab_creation(qapp):
    """AboutTab creation doesn't crash."""
    tab = AboutTab()
    assert tab is not None
    assert tab.logo_clicks == 0
    assert tab.easter_egg_window is None


def test_about_tab_with_callbacks(qapp):
    """AboutTab with all optional callbacks initializes correctly."""
    tier_label = QLabel("Free")
    
    def dummy(): pass
    
    tab = AboutTab(
        tier_label_widget=tier_label,
        on_upgrade=dummy,
        on_enter_license=dummy,
        on_export_pack=dummy,
        on_import_pack=dummy,
        refresh_tier=dummy,
    )
    assert tab.tier_label_widget is tier_label
    assert tab.on_upgrade == dummy
    assert tab.on_enter_license == dummy


def test_logo_file_exists():
    """Logo file path resolves."""
    icon_path = (
        Path(__file__).parent.parent / "src" / "gamepad_midi_bridge" / "resources" / "icon.png"
    )
    assert icon_path.exists(), f"Icon not found at {icon_path}"


def test_easter_egg_counter_increments(qapp):
    """Easter egg counter increments on logo clicks."""
    tab = AboutTab()
    
    # Find the logo label and click it (via the stored counter)
    assert tab.logo_clicks == 0
    
    tab._on_logo_click()
    assert tab.logo_clicks == 1
    
    tab._on_logo_click()
    assert tab.logo_clicks == 2


def test_build_info_populated():
    """Build-info function returns a populated dict."""
    info = get_build_info()
    
    assert "version" in info
    assert "platform" in info
    assert "python" in info
    assert "build_date" in info
    assert "git_hash" in info
    
    # All required fields should have non-empty string values (except git_hash which may be None)
    assert isinstance(info["version"], str)
    assert len(info["version"]) > 0
    assert isinstance(info["platform"], str)
    assert len(info["platform"]) > 0
    assert isinstance(info["python"], str)
    assert len(info["python"]) > 0
    assert isinstance(info["build_date"], str)
    assert len(info["build_date"]) > 0
