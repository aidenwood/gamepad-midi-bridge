"""Tests for the Help tab."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gamepad_midi_bridge.ui.help_tab import HelpTab


def _qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _has_pyside6() -> bool:
    try:
        from PySide6.QtWidgets import QApplication
        return True
    except ImportError:
        return False


skip_no_qt = pytest.mark.skipif(not _has_pyside6(), reason="PySide6 not available")


# ---------------------------------------------------------------------------
# HelpTab instantiation
# ---------------------------------------------------------------------------

@skip_no_qt
def test_help_tab_creation() -> None:
    """Test that HelpTab can be created without crashing."""
    _qapp()
    help_tab = HelpTab()
    assert help_tab is not None
    assert help_tab.isVisible() is False  # Widget created but not shown
    help_tab.close()


@skip_no_qt
def test_help_tab_has_signals() -> None:
    """Test that HelpTab has the expected signals."""
    _qapp()
    help_tab = HelpTab()
    assert hasattr(help_tab, "toggle_bridge_requested")
    assert hasattr(help_tab, "quit_requested")
    assert hasattr(help_tab, "open_settings_requested")
    assert hasattr(help_tab, "hide_window_requested")
    assert hasattr(help_tab, "recalibrate_requested")
    assert hasattr(help_tab, "run_test_wizard_requested")
    help_tab.close()


# ---------------------------------------------------------------------------
# Helper method tests
# ---------------------------------------------------------------------------

def test_open_user_data_folder_returns_bool() -> None:
    """Test that _open_user_data_folder returns a boolean."""
    with patch("gamepad_midi_bridge.ui.help_tab.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = HelpTab._open_user_data_folder()
        assert isinstance(result, bool)
        assert result is True


def test_open_user_data_folder_on_darwin() -> None:
    """Test opening user data folder on macOS."""
    with patch("gamepad_midi_bridge.ui.help_tab.sys.platform", "darwin"):
        with patch("gamepad_midi_bridge.ui.help_tab.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            HelpTab._open_user_data_folder()
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "open"


def test_open_user_data_folder_on_windows() -> None:
    """Test opening user data folder on Windows."""
    import os as os_module
    if not hasattr(os_module, 'startfile'):
        pytest.skip("os.startfile not available on non-Windows platforms")
    with patch("gamepad_midi_bridge.ui.help_tab.sys.platform", "win32"):
        with patch("gamepad_midi_bridge.ui.help_tab.os.startfile") as mock_startfile:
            HelpTab._open_user_data_folder()
            mock_startfile.assert_called_once()


def test_open_user_data_folder_on_linux() -> None:
    """Test opening user data folder on Linux."""
    with patch("gamepad_midi_bridge.ui.help_tab.sys.platform", "linux"):
        with patch("gamepad_midi_bridge.ui.help_tab.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            HelpTab._open_user_data_folder()
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "xdg-open"


def test_open_user_data_folder_exception_handling() -> None:
    """Test that _open_user_data_folder returns False on exception."""
    with patch("gamepad_midi_bridge.ui.help_tab.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = Exception("Test error")
        result = HelpTab._open_user_data_folder()
        assert result is False


def test_open_log_file_returns_bool(tmp_user_data) -> None:
    """Test that _open_log_file returns a boolean."""
    with patch("gamepad_midi_bridge.ui.help_tab.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = HelpTab._open_log_file()
        assert isinstance(result, bool)
        assert result is True


def test_open_log_file_exception_handling() -> None:
    """Test that _open_log_file returns False on exception."""
    with patch("gamepad_midi_bridge.ui.help_tab.log_path") as mock_log_path:
        mock_log_path.side_effect = Exception("Test error")
        result = HelpTab._open_log_file()
        assert result is False


@skip_no_qt
def test_check_for_updates_initializes_updater() -> None:
    """Test that _check_for_updates initializes UpdateChecker if needed."""
    _qapp()
    help_tab = HelpTab()
    with patch("gamepad_midi_bridge.ui.help_tab.UpdateChecker") as mock_updater_class:
        mock_updater = MagicMock()
        mock_updater_class.return_value = mock_updater

        help_tab._check_for_updates()

        mock_updater_class.assert_called_once()
        mock_updater.check.assert_called_once()
    help_tab.close()


@skip_no_qt
def test_check_for_updates_reuses_updater() -> None:
    """Test that _check_for_updates reuses the same UpdateChecker instance."""
    _qapp()
    help_tab = HelpTab()
    with patch("gamepad_midi_bridge.ui.help_tab.UpdateChecker") as mock_updater_class:
        mock_updater = MagicMock()
        mock_updater_class.return_value = mock_updater

        help_tab._check_for_updates()
        help_tab._check_for_updates()

        # Should only be called once (reused)
        mock_updater_class.assert_called_once()
        # check() called twice
        assert mock_updater.check.call_count == 2
    help_tab.close()
