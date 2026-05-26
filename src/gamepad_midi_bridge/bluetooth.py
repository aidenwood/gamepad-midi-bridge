"""Bluetooth device discovery — controller-friendly subset.

We deliberately don't try to pair classic-Bluetooth HID devices ourselves.
The OS handles that safely and the user has already done it once for every
controller they own — re-doing it from inside our app is friction with no
upside. What we DO provide:

    1. A list of paired/connected Bluetooth controllers + their status
    2. RSSI / battery / connection state where the OS exposes it
    3. A button that opens the system Bluetooth settings so the user can
       pair a new device through the trusted OS UI

macOS implementation uses IOBluetooth via PyObjC (lazy-loaded; gracefully
no-ops if PyObjC isn't installed).  Windows uses `Get-PnpDevice` PowerShell
queries.  Linux uses `bluetoothctl`.  Each platform implementation lives
behind the same `list_devices()` API so the UI layer doesn't care.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BluetoothDevice:
    name: str
    address: str               # canonical MAC: aa:bb:cc:dd:ee:ff
    connected: bool
    paired: bool
    is_controller: bool        # heuristic: name matches a known controller pattern
    rssi: Optional[int] = None
    battery_percent: Optional[int] = None
    transport: str = "bluetooth"


CONTROLLER_HINTS = (
    "dualsense", "dualshock", "wireless controller",
    "xbox", "x-input", "x-box",
    "joycon", "joy-con", "switch pro",
    "stadia", "gamepad",
)


def looks_like_controller(name: str) -> bool:
    lc = name.lower()
    return any(hint in lc for hint in CONTROLLER_HINTS)


# --------------------------------------------------------------- macOS


def _mac_list_devices() -> List[BluetoothDevice]:
    """Query IOBluetooth via PyObjC. Returns [] if PyObjC isn't installed or
    macOS hasn't granted the app Bluetooth permission yet."""
    try:
        from IOBluetooth import IOBluetoothDevice  # type: ignore
    except Exception:
        return []

    devices: List[BluetoothDevice] = []
    try:
        # macOS will SIGABRT the process at this call if the bundle's
        # Info.plist is missing NSBluetoothAlwaysUsageDescription. We
        # patch the plist in build.py — but if a stray dev build sneaks
        # through, the wrapping try/except at least logs the failure
        # rather than tearing the GUI down.
        paired_array = IOBluetoothDevice.pairedDevices()
    except Exception as exc:  # pragma: no cover — hardware-dependent path
        print(f"IOBluetooth pairedDevices() failed: {exc}")
        return []
    if paired_array is None:
        return devices
    for d in paired_array:
        try:
            name = str(d.name() or d.nameOrAddress() or "Unknown")
            address = str(d.addressString() or "").lower().replace("-", ":")
            connected = bool(d.isConnected())
            rssi = None
            if connected:
                try:
                    rssi = int(d.rawRSSI())
                except Exception:
                    rssi = None
            devices.append(BluetoothDevice(
                name=name,
                address=address,
                connected=connected,
                paired=True,
                is_controller=looks_like_controller(name),
                rssi=rssi,
            ))
        except Exception:
            continue
    return devices


def _mac_open_settings() -> bool:
    """Open the System Settings Bluetooth pane via the well-known URL."""
    try:
        subprocess.Popen([
            "open", "x-apple.systempreferences:com.apple.BluetoothSettings",
        ])
        return True
    except Exception:
        return False


# --------------------------------------------------------------- Windows


def _win_list_devices() -> List[BluetoothDevice]:
    """PowerShell + Get-PnpDevice — surface every BTHENUM device + status."""
    ps = shutil.which("powershell.exe") or shutil.which("powershell")
    if ps is None:
        return []
    try:
        result = subprocess.run(
            [ps, "-NoProfile", "-Command",
             "Get-PnpDevice -Class Bluetooth | "
             "Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    import json
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    devices: List[BluetoothDevice] = []
    for entry in data:
        name = str(entry.get("FriendlyName") or "Unknown")
        status = str(entry.get("Status") or "").lower()
        instance = str(entry.get("InstanceId") or "")
        # InstanceId looks like BTHENUM\Dev_AABBCCDDEEFF... — pull the MAC.
        address = ""
        for token in instance.replace("\\", "_").split("_"):
            if len(token) == 12 and all(c in "0123456789abcdefABCDEF" for c in token):
                address = ":".join(token.lower()[i:i+2] for i in range(0, 12, 2))
                break
        devices.append(BluetoothDevice(
            name=name,
            address=address,
            connected=("ok" in status or "started" in status),
            paired=True,
            is_controller=looks_like_controller(name),
        ))
    return devices


def _win_open_settings() -> bool:
    try:
        subprocess.Popen(["cmd", "/c", "start", "ms-settings:bluetooth"])
        return True
    except Exception:
        return False


# --------------------------------------------------------------- Linux


def _linux_list_devices() -> List[BluetoothDevice]:
    """Shell out to bluetoothctl. Skips silently when the binary isn't present."""
    if shutil.which("bluetoothctl") is None:
        return []
    try:
        listed = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True, text=True, timeout=5,
        ).stdout.splitlines()
    except Exception:
        return []

    devices: List[BluetoothDevice] = []
    for line in listed:
        # Format: "Device aa:bb:cc:dd:ee:ff Friendly Name Here"
        parts = line.strip().split(" ", 2)
        if len(parts) < 3 or parts[0] != "Device":
            continue
        address, name = parts[1].lower(), parts[2]
        connected = False
        try:
            info = subprocess.run(
                ["bluetoothctl", "info", address],
                capture_output=True, text=True, timeout=5,
            ).stdout
            connected = "Connected: yes" in info
        except Exception:
            pass
        devices.append(BluetoothDevice(
            name=name,
            address=address,
            connected=connected,
            paired=True,
            is_controller=looks_like_controller(name),
        ))
    return devices


def _linux_open_settings() -> bool:
    """Best-effort: try the common DE launchers."""
    for cmd in (("gnome-control-center", "bluetooth"),
                ("blueman-manager",),
                ("systemsettings5", "kcm_bluetooth")):
        binary = shutil.which(cmd[0])
        if binary:
            try:
                subprocess.Popen(list(cmd))
                return True
            except Exception:
                continue
    return False


# --------------------------------------------------------------- public


def list_devices() -> List[BluetoothDevice]:
    """Best-effort cross-platform device list. Returns [] if support unavailable."""
    try:
        if sys.platform == "darwin":
            return _mac_list_devices()
        if sys.platform == "win32":
            return _win_list_devices()
        if sys.platform.startswith("linux"):
            return _linux_list_devices()
    except Exception:
        return []
    return []


def open_system_settings() -> bool:
    """Open the OS's Bluetooth settings pane. Returns True if a launcher fired."""
    if sys.platform == "darwin":
        return _mac_open_settings()
    if sys.platform == "win32":
        return _win_open_settings()
    if sys.platform.startswith("linux"):
        return _linux_open_settings()
    return False


def is_supported() -> bool:
    """Whether we expect device listing to actually work on this platform."""
    if sys.platform == "darwin":
        try:
            import IOBluetooth  # type: ignore  # noqa: F401
            return True
        except Exception:
            return False
    if sys.platform == "win32":
        return shutil.which("powershell.exe") is not None
    if sys.platform.startswith("linux"):
        return shutil.which("bluetoothctl") is not None
    return False
