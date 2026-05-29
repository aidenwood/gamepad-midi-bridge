"""Tests for theme management — dark/light/system detection."""
from __future__ import annotations

import pytest
from gamepad_midi_bridge.ui.theme import (
    THEMES,
    detect_system_theme,
    load_theme_qss,
)
from gamepad_midi_bridge.mapping import Mapping


class TestThemeDetection:
    """Test system theme detection."""

    def test_detect_system_theme_returns_valid_value(self) -> None:
        """System theme detection returns 'dark' or 'light'."""
        result = detect_system_theme()
        assert result in ("dark", "light")

    def test_detect_system_theme_is_string(self) -> None:
        """System theme detection returns a string."""
        result = detect_system_theme()
        assert isinstance(result, str)


class TestThemeQss:
    """Test QSS stylesheet loading."""

    def test_load_theme_qss_dark_returns_content(self) -> None:
        """Dark theme QSS file exists and returns non-empty content."""
        qss = load_theme_qss("dark")
        assert isinstance(qss, str)
        assert len(qss) > 0
        assert "QWidget" in qss

    def test_load_theme_qss_light_returns_content(self) -> None:
        """Light theme QSS file exists and returns non-empty content."""
        qss = load_theme_qss("light")
        assert isinstance(qss, str)
        assert len(qss) > 0
        assert "QWidget" in qss

    def test_load_theme_qss_system_resolves_to_valid_qss(self) -> None:
        """System theme detection resolves to either dark or light QSS."""
        qss = load_theme_qss("system")
        assert isinstance(qss, str)
        assert len(qss) > 0
        # Should contain QWidget definitions
        assert "QWidget" in qss

    def test_load_theme_qss_all_themes(self) -> None:
        """All defined themes return non-empty QSS."""
        for theme in THEMES:
            qss = load_theme_qss(theme)
            assert len(qss) > 0, f"Theme '{theme}' returned empty QSS"


class TestMappingTheme:
    """Test theme field on Mapping."""

    def test_mapping_theme_defaults_to_system(self) -> None:
        """New Mapping instances default to 'system' theme."""
        mapping = Mapping()
        assert mapping.theme == "system"

    def test_mapping_theme_to_dict_dark(self) -> None:
        """Dark theme is preserved in to_dict()."""
        mapping = Mapping(theme="dark")
        data = mapping.to_dict()
        assert data["theme"] == "dark"

    def test_mapping_theme_to_dict_light(self) -> None:
        """Light theme is preserved in to_dict()."""
        mapping = Mapping(theme="light")
        data = mapping.to_dict()
        assert data["theme"] == "light"

    def test_mapping_theme_to_dict_system(self) -> None:
        """System theme is preserved in to_dict()."""
        mapping = Mapping(theme="system")
        data = mapping.to_dict()
        assert data["theme"] == "system"

    def test_mapping_theme_from_dict_defaults_to_system(self) -> None:
        """Mapping.from_dict defaults theme to 'system' when missing."""
        data = {"name": "Test"}
        mapping = Mapping.from_dict(data)
        assert mapping.theme == "system"

    def test_mapping_theme_is_valid_choice(self) -> None:
        """Mapping.theme is always one of the valid choices."""
        for theme in THEMES:
            mapping = Mapping(theme=theme)
            assert mapping.theme in THEMES


class TestThemeConstants:
    """Test theme constants."""

    def test_themes_contains_expected_values(self) -> None:
        """THEMES constant contains dark, light, and system."""
        assert "dark" in THEMES
        assert "light" in THEMES
        assert "system" in THEMES

    def test_themes_is_tuple(self) -> None:
        """THEMES is a tuple."""
        assert isinstance(THEMES, tuple)
