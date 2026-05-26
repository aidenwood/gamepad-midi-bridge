"""TouchDesigner MIDI mapping connector.

TouchDesigner doesn't have a single config-file format we can drop a binary
template into without owning the project file. The realistic free-tier
integration is a JSON descriptor the user imports via the Palette MIDI Mapper
component — it tells TD which CCs/notes map to which named gamepad controls so
the user can wire them into their network without guessing channel/CC numbers.

Install path (same Documents subfolder on mac + win):

    macOS  : ~/Documents/Derivative/TouchDesigner/Components/MIDI Maps/
    Windows: %USERPROFILE%\\Documents\\Derivative\\TouchDesigner\\Components\\MIDI Maps\\

Detection:
    macOS  : /Applications/TouchDesigner.app, version from Info.plist
    Windows: C:\\Program Files\\Derivative\\TouchDesigner*\\

Min version 2022 — earlier builds shipped a different Palette layout.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from .base import Connector, HostInstallation, InstallResult, documents_dir


DESCRIPTOR_FILENAME = "gamepad_midi_bridge.tdmap.json"
TEMPLATE_FILENAME = "touchdesigner_default.json"
MIN_YEAR_VERSION = 2022


class TouchDesignerConnector(Connector):
    display_name = "TouchDesigner"
    slug = "touchdesigner"
    description = (
        "Drop a MIDI map descriptor into TouchDesigner's Components folder. "
        "Import via Palette → MIDI Mapper. Names every gamepad control so you "
        "can wire CHOPs and DATs without memorising CC numbers."
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

        dest = host.config_dir / DESCRIPTOR_FILENAME
        try:
            shutil.copyfile(template, dest)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't write {dest}: {e}")

        return InstallResult(
            True, dest,
            f"Installed for {host.name}. Open TouchDesigner and import the "
            "descriptor via Palette → MIDI Mapper.",
        )

    def uninstall(self, host: HostInstallation) -> InstallResult:
        dest = host.config_dir / DESCRIPTOR_FILENAME
        if not dest.exists():
            return InstallResult(True, None, f"Nothing to remove for {host.name}.")
        try:
            dest.unlink()
        except Exception as e:
            return InstallResult(False, None, f"Couldn't remove {dest}: {e}")
        return InstallResult(True, dest, f"Removed descriptor from {host.name}.")

    def is_installed(self, host: HostInstallation) -> bool:
        return (host.config_dir / DESCRIPTOR_FILENAME).exists()

    def post_install_steps(self, host: HostInstallation) -> str:
        return (
            "1. Open TouchDesigner.\n"
            "2. Drag the gamepad_midi_bridge.tdmap.json file into the network "
            "(or import via Palette → MIDI Mapper).\n"
            "3. Connect the mididevice DAT to your bridge virtual MIDI port "
            "(Dialogs → MIDI Device Mapper).\n"
            "4. The CHOP/DAT references inside resolve to the named gamepad "
            "controls — wire them into your patch."
        )


# --------------------------------------------------------------- platform detection

def _detect_macos() -> List[HostInstallation]:
    """Look for TouchDesigner.app under /Applications, read Info.plist version."""
    import plistlib

    app = Path("/Applications/TouchDesigner.app")
    if not app.exists():
        return []

    plist_path = app / "Contents" / "Info.plist"
    version = "unknown"
    year_major: Optional[int] = None
    if plist_path.exists():
        try:
            with plist_path.open("rb") as f:
                info = plistlib.load(f)
            version = str(info.get("CFBundleShortVersionString", "unknown"))
            year_major = _parse_td_year(version)
        except Exception:
            pass

    if year_major is not None and year_major < MIN_YEAR_VERSION:
        return []

    config_dir = (
        documents_dir() / "Derivative" / "TouchDesigner" / "Components" / "MIDI Maps"
    )
    return [HostInstallation(
        name=f"TouchDesigner {version}",
        version=version,
        config_dir=config_dir,
        extra={"app_path": str(app), "year": year_major},
    )]


def _detect_windows() -> List[HostInstallation]:
    """Scan Program Files\\Derivative for any TouchDesigner* install."""
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    derivative_root = program_files / "Derivative"
    if not derivative_root.exists():
        return []

    config_dir = (
        documents_dir() / "Derivative" / "TouchDesigner" / "Components" / "MIDI Maps"
    )

    found: List[HostInstallation] = []
    pattern = re.compile(r"^TouchDesigner(.*)$")
    for child in sorted(derivative_root.iterdir()):
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if not match:
            continue
        version_str = match.group(1).strip(" -_") or "unknown"
        year_major = _parse_td_year(version_str)
        if year_major is not None and year_major < MIN_YEAR_VERSION:
            continue
        found.append(HostInstallation(
            name=child.name,
            version=version_str,
            config_dir=config_dir,
            extra={"install_dir": str(child), "year": year_major},
        ))
    return found


def _parse_td_year(version_str: str) -> Optional[int]:
    """Pull the year-major (e.g. 2023 from '2023.11600') out of a version string."""
    match = re.search(r"(20\d{2})", version_str)
    if not match:
        return None
    return int(match.group(1))


# --------------------------------------------------------------- internals

def _template_path(filename: str) -> Path:
    return Path(__file__).parent / "templates" / filename
