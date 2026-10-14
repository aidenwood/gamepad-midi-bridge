"""Tests for Bluetooth tab widget and system settings launcher."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch, call

import pytest

from gamepad_midi_bridge import bluetooth as bt


class TestBluetoothDeviceBasics:
    """Dataclass and filtering logic (no Qt needed)."""

    def test_bluetooth_device_creation(self):
        """BluetoothDevice can be instantiated with all fields."""
        d = bt.BluetoothDevice(
            name="DualSense",
            address="aa:bb:cc:dd:ee:ff",
            connected=True,
            paired=True,
            is_controller=True,
            rssi=-50,
            battery_percent=85,
        )
        assert d.name == "DualSense"
        assert d.address == "aa:bb:cc:dd:ee:ff"
        assert d.connected is True
        assert d.paired is True
        assert d.is_controller is True
        assert d.rssi == -50
        assert d.battery_percent == 85

    def test_looks_like_controller_true_cases(self):
        """Identifies common gamepad patterns."""
        assert bt.looks_like_controller("DualSense Controller")
        assert bt.looks_like_controller("Xbox Wireless Controller")
        assert bt.looks_like_controller("Joy-Con (L)")
        assert bt.looks_like_controller("Switch Pro Controller")
        assert bt.looks_like_controller("Stadia Controller")
        assert bt.looks_like_controller("GENERIC GAMEPAD")

    def test_looks_like_controller_false_cases(self):
        """Non-controller devices return False."""
        assert not bt.looks_like_controller("Bose SoundLink")
        assert not bt.looks_like_controller("Apple Magic Keyboard")
        assert not bt.looks_like_controller("Generic Mouse")
        assert not bt.looks_like_controller("Unknown Device")


class TestPlatformSupport:
    """is_supported() returns True/False per platform availability."""

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "darwin")
    def test_macos_supported_with_iobt(self):
        """macOS returns True if IOBluetooth is importable."""
        # Mock the IOBluetooth import to succeed
        mock_iobt = MagicMock()
        with patch.dict("sys.modules", {"IOBluetooth": mock_iobt}):
            # is_supported will try to import IOBluetooth and succeed
            result = bt.is_supported()
            assert result is True

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    def test_windows_supported_with_powershell(self, mock_which):
        """Windows returns True if powershell.exe is found."""
        mock_which.return_value = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        assert bt.is_supported() is True

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    def test_windows_unsupported_no_powershell(self, mock_which):
        """Windows returns False if powershell is missing."""
        mock_which.return_value = None
        assert bt.is_supported() is False

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "linux")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    def test_linux_supported_with_bluetoothctl(self, mock_which):
        """Linux returns True if bluetoothctl is found."""
        mock_which.return_value = "/usr/bin/bluetoothctl"
        assert bt.is_supported() is True

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "linux")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    def test_linux_unsupported_no_bluetoothctl(self, mock_which):
        """Linux returns False if bluetoothctl is missing."""
        mock_which.return_value = None
        assert bt.is_supported() is False


class TestOpenSystemSettings:
    """open_system_settings() launches the correct platform-specific command."""

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "darwin")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_macos_opens_settings(self, mock_popen):
        """macOS opens x-apple.systempreferences URL."""
        bt.open_system_settings()
        mock_popen.assert_called_once_with([
            "open", "x-apple.systempreferences:com.apple.BluetoothSettings",
        ])

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "darwin")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_macos_returns_true_on_success(self, mock_popen):
        """open_system_settings returns True when Popen succeeds."""
        assert bt.open_system_settings() is True

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "darwin")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_macos_returns_false_on_exception(self, mock_popen):
        """open_system_settings returns False when Popen raises."""
        mock_popen.side_effect = Exception("Popen failed")
        assert bt.open_system_settings() is False

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_windows_opens_settings(self, mock_popen):
        """Windows opens ms-settings:bluetooth URI with no console window."""
        bt.open_system_settings()
        assert mock_popen.call_count == 1
        args, kwargs = mock_popen.call_args
        assert args[0] == ["cmd", "/c", "start", "ms-settings:bluetooth"]
        # CREATE_NO_WINDOW — without it `cmd` flashes a black console over
        # whatever the user is doing. See proc.no_window_kwargs().
        assert kwargs["creationflags"] & 0x08000000

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_windows_returns_true_on_success(self, mock_popen):
        """Windows open_system_settings returns True on success."""
        assert bt.open_system_settings() is True

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_windows_returns_false_on_exception(self, mock_popen):
        """Windows open_system_settings returns False on exception."""
        mock_popen.side_effect = OSError("cmd not found")
        assert bt.open_system_settings() is False

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "linux")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_linux_tries_gnome_control_center_first(self, mock_popen, mock_which):
        """Linux tries gnome-control-center first."""
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd
        bt.open_system_settings()
        # Should have called Popen with gnome-control-center + bluetooth
        assert mock_popen.called

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "linux")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_linux_falls_back_to_blueman_manager(self, mock_popen, mock_which):
        """Linux falls back to blueman-manager if gnome-control-center fails."""
        call_count = [0]

        def which_side_effect(cmd):
            # First call is gnome-control-center (exists), second is blueman-manager (fails)
            if cmd == "gnome-control-center":
                return None  # Not found
            if cmd == "blueman-manager":
                return "/usr/bin/blueman-manager"
            return None

        mock_which.side_effect = which_side_effect

        def popen_side_effect(cmd):
            # gnome-control-center fails, blueman-manager succeeds
            if "blueman-manager" in cmd:
                return MagicMock()
            raise Exception("Failed")

        mock_popen.side_effect = popen_side_effect

        result = bt.open_system_settings()
        assert result is True

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "linux")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.Popen")
    def test_linux_returns_false_when_all_fail(self, mock_popen, mock_which):
        """Linux returns False if all launchers fail."""
        mock_which.return_value = None  # No commands found
        assert bt.open_system_settings() is False

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "freebsd")
    def test_unsupported_platform_returns_false(self):
        """Unsupported platform returns False."""
        assert bt.open_system_settings() is False


class TestListDevices:
    """list_devices() returns correct device list per platform."""

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "darwin")
    @patch("gamepad_midi_bridge.bluetooth._mac_list_devices")
    def test_mac_list_devices_called(self, mock_mac_list):
        """list_devices routes to _mac_list_devices on Darwin."""
        mock_mac_list.return_value = []
        result = bt.list_devices()
        mock_mac_list.assert_called_once()
        assert result == []

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32")
    @patch("gamepad_midi_bridge.bluetooth._win_list_devices")
    def test_win_list_devices_called(self, mock_win_list):
        """list_devices routes to _win_list_devices on Windows."""
        mock_win_list.return_value = []
        result = bt.list_devices()
        mock_win_list.assert_called_once()
        assert result == []

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "linux")
    @patch("gamepad_midi_bridge.bluetooth._linux_list_devices")
    def test_linux_list_devices_called(self, mock_linux_list):
        """list_devices routes to _linux_list_devices on Linux."""
        mock_linux_list.return_value = []
        result = bt.list_devices()
        mock_linux_list.assert_called_once()
        assert result == []

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "freebsd")
    def test_unsupported_platform_returns_empty_list(self):
        """Unsupported platform returns empty device list."""
        result = bt.list_devices()
        assert result == []

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "linux")
    @patch("gamepad_midi_bridge.bluetooth._linux_list_devices")
    def test_list_devices_catches_exception(self, mock_linux_list):
        """list_devices catches exceptions and returns []."""
        mock_linux_list.side_effect = Exception("Device list error")
        result = bt.list_devices()
        assert result == []


class TestBluetoothTabUI:
    """Tests for the Bluetooth tab widget itself."""

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_bluetooth_tab_creation(self):
        """BluetoothTab widget can be instantiated."""
        from PySide6.QtWidgets import QApplication
        from gamepad_midi_bridge.ui.bluetooth_tab import BluetoothTab

        app = QApplication.instance() or QApplication([])
        tab = BluetoothTab()
        assert tab is not None
        assert tab._supported is not None

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_bluetooth_tab_has_buttons(self):
        """BluetoothTab has Open Settings, Re-scan, and Docs buttons."""
        from PySide6.QtWidgets import QApplication
        from gamepad_midi_bridge.ui.bluetooth_tab import BluetoothTab

        app = QApplication.instance() or QApplication([])
        tab = BluetoothTab()
        assert hasattr(tab, "_open_settings")
        assert hasattr(tab, "_refresh")
        assert hasattr(tab, "_docs_link")

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_bluetooth_tab_refresh_emits_signal(self):
        """Calling refresh() emits status_message signal."""
        from PySide6.QtWidgets import QApplication
        from gamepad_midi_bridge.ui.bluetooth_tab import BluetoothTab

        app = QApplication.instance() or QApplication([])
        tab = BluetoothTab()

        signal_fired = []

        def capture_signal(msg):
            signal_fired.append(msg)

        tab.status_message.connect(capture_signal)
        tab.refresh()
        # refresh() now scans on the thread pool, so drain it before asserting.
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()
        assert len(signal_fired) > 0 or not tab._supported


class TestWindowsConsoleSuppression:
    """Regression: a windowed Windows build must never spawn a visible console.

    The app shells out to powershell/cmd/tasklist. Without CREATE_NO_WINDOW,
    Windows allocates a console for each call and flashes it over the user's
    DAW — every 6 seconds, because the Bluetooth tab polls.
    """

    def test_no_window_kwargs_empty_off_windows(self):
        """POSIX gets {} so call sites can splat unconditionally."""
        from gamepad_midi_bridge import proc
        with patch("gamepad_midi_bridge.proc.sys.platform", "darwin"):
            assert proc.no_window_kwargs() == {}

    def test_no_window_kwargs_sets_create_no_window(self):
        """Windows gets CREATE_NO_WINDOW."""
        from gamepad_midi_bridge import proc
        with patch("gamepad_midi_bridge.proc.sys.platform", "win32"):
            kwargs = proc.no_window_kwargs()
        assert kwargs["creationflags"] & proc.CREATE_NO_WINDOW

    @patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32")
    @patch("gamepad_midi_bridge.bluetooth.shutil.which")
    @patch("gamepad_midi_bridge.bluetooth.subprocess.run")
    def test_win_list_devices_hides_console(self, mock_run, mock_which):
        """The 6-second Bluetooth poll must not flash a PowerShell window."""
        mock_which.return_value = "powershell.exe"
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        bt.list_devices()
        _, kwargs = mock_run.call_args
        assert kwargs.get("creationflags", 0) & 0x08000000


class TestWindowsDeviceFiltering:
    """Regression: only paired remote devices count, not every PnP node.

    `Get-PnpDevice -Class Bluetooth` also returns the radio, the BTHENUM/
    BTHLE enumerators and one child node per advertised service. Counting
    those is how a laptop with two controllers reported "20 connected,
    20 paired".
    """

    PNP_SAMPLE = [
        # Real paired peripherals — keep.
        {"FriendlyName": "Xbox Wireless Controller",
         "Status": "OK",
         "InstanceId": r"BTHENUM\DEV_AABBCCDDEEFF\7&1234&0&AABBCCDDEEFF_C00000000"},
        {"FriendlyName": "Bose SoundLink",
         "Status": "Unknown",
         "InstanceId": r"BTHENUM\DEV_112233445566\7&1234&0&112233445566_C00000000"},
        # Per-service child nodes of the SAME controller — drop.
        {"FriendlyName": "Bluetooth Device (Personal Area Network)",
         "Status": "OK",
         "InstanceId": r"BTHENUM\{00001124-0000-1000-8000-00805f9b34fb}_LOCALMFG&0000\7&1&0"},
        {"FriendlyName": "Bluetooth Device (RFCOMM Protocol TDI)",
         "Status": "OK",
         "InstanceId": r"BTHENUM\{00001101-0000-1000-8000-00805f9b34fb}_VID&0001_PID&0001\8&1"},
        # The radio and the enumerators themselves — drop.
        {"FriendlyName": "Intel(R) Wireless Bluetooth(R)",
         "Status": "OK",
         "InstanceId": r"USB\VID_8087&PID_0026\5&1"},
        {"FriendlyName": "Microsoft Bluetooth Enumerator",
         "Status": "OK",
         "InstanceId": r"BTH\MS_BTHBRB\7&1&0"},
    ]

    def _run(self):
        import json
        with patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32"), \
             patch("gamepad_midi_bridge.bluetooth.shutil.which",
                   return_value="powershell.exe"), \
             patch("gamepad_midi_bridge.bluetooth.subprocess.run",
                   return_value=MagicMock(
                       returncode=0,
                       stdout=json.dumps(self.PNP_SAMPLE))):
            return bt.list_devices()

    def test_drops_radios_enumerators_and_service_nodes(self):
        """Six PnP rows collapse to the two actual paired peripherals."""
        devices = self._run()
        assert [d.name for d in devices] == [
            "Xbox Wireless Controller", "Bose SoundLink",
        ]

    def test_parses_mac_and_connected_state(self):
        """MAC comes off the InstanceId; Status drives `connected`."""
        pad, speaker = self._run()
        assert pad.address == "aa:bb:cc:dd:ee:ff"
        assert pad.connected is True
        assert pad.is_controller is True
        assert speaker.connected is False
        assert speaker.is_controller is False

    def test_deduplicates_same_mac(self):
        """A controller exposing both a classic and an LE node counts once."""
        import json
        dupe = self.PNP_SAMPLE[:1] + [{
            "FriendlyName": "Xbox Wireless Controller",
            "Status": "OK",
            "InstanceId": r"BTHLEDEVICE\DEV_AABBCCDDEEFF\9&1",
        }]
        with patch("gamepad_midi_bridge.bluetooth.sys.platform", "win32"), \
             patch("gamepad_midi_bridge.bluetooth.shutil.which",
                   return_value="powershell.exe"), \
             patch("gamepad_midi_bridge.bluetooth.subprocess.run",
                   return_value=MagicMock(returncode=0, stdout=json.dumps(dupe))):
            devices = bt.list_devices()
        assert len(devices) == 1


def _has_qapp() -> bool:
    """Check if PySide6 is available."""
    try:
        from PySide6.QtWidgets import QApplication
        return True
    except ImportError:
        return False
