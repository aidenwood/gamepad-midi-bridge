"""Tests for SettingsPanel — smoke, theme persistence, telemetry toggle."""
from __future__ import annotations

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gamepad_midi_bridge.mapping import Mapping


def _qapp():
    """Return (or create) the singleton QApplication."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv[:1])


def _has_pyside6() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
        return True
    except ImportError:
        return False


_skip_no_qt = pytest.mark.skipif(not _has_pyside6(), reason="PySide6 not available")


# ─── instantiation ────────────────────────────────────────────────────────────

@_skip_no_qt
class TestSettingsPanelInstantiation:
    """SettingsPanel can be created without crashing."""

    def test_creates_without_crash(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        assert panel is not None

    def test_has_settings_changed_signal(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        assert hasattr(panel, "settings_changed")

    def test_has_multi_mode_changed_signal(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        assert hasattr(panel, "multi_mode_changed")

    def test_has_recalibrate_clicked_signal(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        assert hasattr(panel, "recalibrate_clicked")

    def test_channel_spinbox_reflects_mapping(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        m = Mapping(midi_channel=4)
        panel = SettingsPanel(m)
        assert panel._channel.value() == 5  # 0-indexed → 1-indexed

    def test_poll_spinbox_reflects_mapping(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        m = Mapping(poll_hz=200)
        panel = SettingsPanel(m)
        assert panel._poll.value() == 200

    def test_deadzone_spinbox_reflects_mapping(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        m = Mapping(deadzone=0.10)
        panel = SettingsPanel(m)
        assert abs(panel._deadzone_spin.value() - 0.10) < 1e-9

    def test_auto_reconnect_checkbox_reflects_mapping(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        m = Mapping(auto_reconnect_enabled=False)
        panel = SettingsPanel(m)
        assert panel._auto_reconnect.isChecked() is False

    def test_feedback_guard_checkbox_reflects_mapping(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        m = Mapping()
        # guard_feedback_loop defaults True on HapticInputConfig
        assert m.haptic_input.guard_feedback_loop is True
        panel = SettingsPanel(m)
        assert panel._feedback_guard.isChecked() is True


# ─── theme persistence ────────────────────────────────────────────────────────

@_skip_no_qt
class TestThemePersistence:
    """Theme combo change stores the setting via QSettings and updates mapping."""

    def test_theme_combo_change_updates_mapping(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        from gamepad_midi_bridge.ui.theme import apply_theme

        m = Mapping(theme="system")
        panel = SettingsPanel(m)
        # Switch to "Dark" (index 1)
        with patch("gamepad_midi_bridge.ui.settings_panel.apply_theme") as mock_apply:
            panel._theme.setCurrentIndex(1)  # Dark
            assert m.theme == "dark"

    def test_theme_combo_change_persists_to_qsettings(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel

        panel = SettingsPanel(Mapping())
        with patch("gamepad_midi_bridge.ui.settings_panel.apply_theme"):
            panel._theme.setCurrentIndex(2)  # Light
        assert panel._qs.value("appearance/theme") == "light"

    def test_theme_combo_change_calls_apply_theme(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel

        panel = SettingsPanel(Mapping())
        with patch("gamepad_midi_bridge.ui.settings_panel.apply_theme") as mock_apply:
            panel._theme.setCurrentIndex(1)  # Dark
            mock_apply.assert_called_once()

    def test_theme_combo_emits_settings_changed(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel

        panel = SettingsPanel(Mapping())
        fired = []
        panel.settings_changed.connect(lambda m: fired.append(m.theme))
        with patch("gamepad_midi_bridge.ui.settings_panel.apply_theme"):
            panel._theme.setCurrentIndex(2)  # Light
        assert fired and fired[-1] == "light"

    def test_theme_light_index_maps_to_correct_data(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        panel._theme.setCurrentIndex(2)
        assert panel._theme.currentData() == "light"

    def test_theme_dark_index_maps_to_correct_data(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        panel._theme.setCurrentIndex(1)
        assert panel._theme.currentData() == "dark"


# ─── telemetry toggle ─────────────────────────────────────────────────────────

@_skip_no_qt
class TestTelemetryToggle:
    """Telemetry checkbox calls telemetry.set_enabled with the correct flag."""

    def test_telemetry_enable_calls_set_enabled_true(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        from gamepad_midi_bridge import telemetry

        with patch.object(telemetry, "is_enabled", return_value=False):
            panel = SettingsPanel(Mapping())
            with patch.object(telemetry, "set_enabled") as mock_set:
                panel._anon_stats.setChecked(True)
                mock_set.assert_called_once_with(True)

    def test_telemetry_disable_calls_set_enabled_false(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        from gamepad_midi_bridge import telemetry

        with patch.object(telemetry, "is_enabled", return_value=True):
            panel = SettingsPanel(Mapping())
            with patch.object(telemetry, "set_enabled") as mock_set:
                panel._anon_stats.setChecked(False)
                mock_set.assert_called_once_with(False)

    def test_telemetry_checkbox_initialises_from_is_enabled(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        from gamepad_midi_bridge import telemetry

        with patch.object(telemetry, "is_enabled", return_value=True):
            panel = SettingsPanel(Mapping())
            assert panel._anon_stats.isChecked() is True

    def test_telemetry_checkbox_init_false_when_disabled(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        from gamepad_midi_bridge import telemetry

        with patch.object(telemetry, "is_enabled", return_value=False):
            panel = SettingsPanel(Mapping())
            assert panel._anon_stats.isChecked() is False


# ─── MIDI channel wiring ──────────────────────────────────────────────────────

@_skip_no_qt
class TestMidiChannelWiring:
    """Changing the channel spinbox mutates the mapping immediately."""

    def test_channel_spinbox_updates_mapping_on_change(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        m = Mapping(midi_channel=0)
        panel = SettingsPanel(m)
        panel._channel.setValue(8)
        assert m.midi_channel == 7  # 8 displayed → 7 zero-indexed

    def test_channel_change_emits_settings_changed(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        fired = []
        panel.settings_changed.connect(lambda _: fired.append(True))
        panel._channel.setValue(5)
        assert fired


# ─── deadzone wiring ─────────────────────────────────────────────────────────

@_skip_no_qt
class TestDeadzoneSlider:
    """Deadzone slider and spinbox stay in sync and update the mapping."""

    def test_slider_moves_spinbox(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        panel._deadzone_slider.setValue(100)  # 100/1000 = 0.1
        assert abs(panel._deadzone_spin.value() - 0.1) < 1e-9

    def test_spinbox_moves_slider(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        panel._deadzone_spin.setValue(0.15)
        assert panel._deadzone_slider.value() == 150

    def test_deadzone_clamped_to_0_20(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        # Slider max is 200 → 0.20
        assert panel._deadzone_slider.maximum() == 200
        assert panel._deadzone_spin.maximum() == 0.20

    def test_deadzone_spinbox_updates_mapping(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        m = Mapping()
        panel = SettingsPanel(m)
        panel._deadzone_spin.setValue(0.12)
        assert abs(m.deadzone - 0.12) < 1e-9


# ─── font size persistence ────────────────────────────────────────────────────

@_skip_no_qt
class TestFontSizePersistence:
    """Font size combo persists to QSettings under appearance/font_pt."""

    def test_font_size_change_persists(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        # Pick "Large" (index 2 = 14pt)
        panel._font_size.setCurrentIndex(2)
        assert int(panel._qs.value("appearance/font_pt")) == 14

    def test_font_size_small_persists(self, tmp_user_data) -> None:
        _qapp()
        from gamepad_midi_bridge.ui.settings_panel import SettingsPanel
        panel = SettingsPanel(Mapping())
        panel._font_size.setCurrentIndex(0)  # Small = 10pt
        assert int(panel._qs.value("appearance/font_pt")) == 10
