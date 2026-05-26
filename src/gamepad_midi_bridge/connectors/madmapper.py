"""MadMapper custom MIDI device descriptor connector.

MadMapper's .map workspace files own a project — surgically rewriting one
would mangle the user's content. The safer integration is a custom MIDI
device descriptor in MadMapper's Devices folder. MadMapper scans that folder
on launch and exposes any device it finds in Preferences → MIDI, so our
'Universal Controller MIDI' shows up as a first-class controller the user can
right-click → Learn MIDI against.

Install paths:
    macOS  : ~/Documents/MadMapper/Devices/Universal Controller MIDI.mmidi
    Windows: %USERPROFILE%\\Documents\\MadMapper\\Devices\\Universal Controller MIDI.mmidi

Detection:
    macOS  : /Applications/MadMapper*.app, version from Info.plist
    Windows: C:\\Program Files\\MadMapper*\\

Min version 5 — earlier builds used a different devices schema.

Confidence note: the .mmidi schema is partially documented; we ship a plausible
XML descriptor based on observed MadMapper factory devices. If MadMapper
rejects it, users can still copy the included starter as a hand-edit base.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from .base import Connector, HostInstallation, InstallResult, documents_dir


DEVICE_FILENAME = "Universal Controller MIDI.mmidi"
TEMPLATE_FILENAME = "madmapper_device.mmidi"
MIN_MAJOR_VERSION = 5


class MadMapperConnector(Connector):
    display_name = "MadMapper"
    slug = "madmapper"
    description = (
        "Drop a custom MIDI device descriptor into MadMapper's Devices folder. "
        "The gamepad then appears as a named controller in Preferences → MIDI, "
        "ready for right-click → Learn MIDI against any surface control."
    )

    # ------------------------------------------------ detection

    def detect(self) -> List[HostInstallation]:
        if sys.platform == "darwin":
            return _detect_macos()
        if sys.platform == "win32":
            return _detect_windows()
        return []

    # ------------------------------------------------ install

    def install(self, host: HostInstallation) -> InstallResult:
        template = _template_path(TEMPLATE_FILENAME)
        if not template.exists():
            return InstallResult(
                False, None,
                f"Template missing — {template.name} not bundled with this build.",
            )

        try:
            host.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't create {host.config_dir}: {e}")

        dest = host.config_dir / DEVICE_FILENAME
        try:
            shutil.copyfile(template, dest)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't write {dest}: {e}")

        return InstallResult(
            True, dest,
            f"Installed for {host.name}. Restart MadMapper — the gamepad now "
            "appears in Preferences → MIDI as 'Universal Controller MIDI'.",
        )

    def uninstall(self, host: HostInstallation) -> InstallResult:
        dest = host.config_dir / DEVICE_FILENAME
        if not dest.exists():
            return InstallResult(True, None, f"Nothing to remove for {host.name}.")
        try:
            dest.unlink()
        except Exception as e:
            return InstallResult(False, None, f"Couldn't remove {dest}: {e}")
        return InstallResult(True, dest, f"Removed device descriptor from {host.name}.")

    def is_installed(self, host: HostInstallation) -> bool:
        return (host.config_dir / DEVICE_FILENAME).exists()

    def post_install_steps(self, host: HostInstallation) -> str:
        return (
            "1. Restart MadMapper (it scans Devices/ on launch).\n"
            "2. Preferences → MIDI → the device 'Universal Controller MIDI' "
            "appears in the list. Enable it.\n"
            "3. On any surface or control, right-click → Learn MIDI, then "
            "move the gamepad control you want to bind.\n"
            "4. Save the .map project so the mapping persists."
        )


# --------------------------------------------------------------- platform detection

def _detect_macos() -> List[HostInstallation]:
    """Scan /Applications for MadMapper*.app, read Info.plist for version."""
    import plistlib

    apps_dir = Path("/Applications")
    if not apps_dir.exists():
        return []

    config_dir = documents_dir() / "MadMapper" / "Devices"

    found: List[HostInstallation] = []
    pattern = re.compile(r"^MadMapper(.*)\.app$")
    for app in sorted(apps_dir.iterdir()):
        match = pattern.match(app.name)
        if not match:
            continue

        plist_path = app / "Contents" / "Info.plist"
        version = match.group(1).strip(" -_") or "unknown"
        major = _parse_major(version)
        if plist_path.exists():
            try:
                with plist_path.open("rb") as f:
                    info = plistlib.load(f)
                version = str(info.get("CFBundleShortVersionString", version))
                major = _parse_major(version) or major
            except Exception:
                pass

        if major is not None and major < MIN_MAJOR_VERSION:
            continue

        found.append(HostInstallation(
            name=app.stem,
            version=version,
            config_dir=config_dir,
            extra={"app_path": str(app), "major": major},
        ))
    return found


def _detect_windows() -> List[HostInstallation]:
    """Scan Program Files for MadMapper* install folders."""
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    if not program_files.exists():
        return []

    config_dir = documents_dir() / "MadMapper" / "Devices"

    found: List[HostInstallation] = []
    pattern = re.compile(r"^MadMapper(.*)$")
    for child in sorted(program_files.iterdir()):
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if not match:
            continue
        version = match.group(1).strip(" -_") or "unknown"
        major = _parse_major(version)
        if major is not None and major < MIN_MAJOR_VERSION:
            continue
        found.append(HostInstallation(
            name=child.name,
            version=version,
            config_dir=config_dir,
            extra={"install_dir": str(child), "major": major},
        ))
    return found


def _parse_major(version_str: str) -> Optional[int]:
    match = re.search(r"(\d+)", version_str)
    if not match:
        return None
    return int(match.group(1))


# --------------------------------------------------------------- internals

def _template_path(filename: str) -> Path:
    return Path(__file__).parent / "templates" / filename
