"""Ableton Live Remote Script connector.

Ableton Live loads user-installed Remote Scripts from the User Library:

    macOS  : ~/Music/Ableton/User Library/Remote Scripts/<name>/
    Windows: ~/Documents/Ableton/User Library/Remote Scripts/<name>/

We detect every Live 11+ installation on the machine, then copy our bundled
template folder into place. The script imports `_Framework` at runtime from
Live's bundled Python — we never redistribute Ableton's source.

Live 11+ only. Live 9/10 ran Python 2 and we don't support that.
Linux: Ableton has no native Linux build; skipped for V1.

This connector is free tier — gating Pro-only would block legitimate users.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .base import Connector, HostInstallation, InstallResult


REMOTE_SCRIPT_FOLDER = "Gamepad MIDI Bridge"
TEMPLATE_SUBDIR = "ableton_remote_script"
MIN_MAJOR_VERSION = 11


class AbletonConnector(Connector):
    display_name = "Ableton Live"
    slug = "ableton"
    description = (
        "Install a Remote Script that maps face buttons to clip launch, "
        "sticks to track volume, D-pad to scene nav, and triggers to "
        "master + crossfader. Live 11+ only."
    )

    # ------------------------------------------------ detection

    def detect(self) -> List[HostInstallation]:
        if sys.platform == "darwin":
            return _detect_macos()
        if sys.platform == "win32":
            return _detect_windows()
        # Linux & everything else — no native Live build.
        return []

    # ------------------------------------------------ install

    def install(self, host: HostInstallation) -> InstallResult:
        template = _template_source()
        if not template.exists():
            return InstallResult(
                False, None,
                f"Template missing — {template} not bundled with this build.",
            )

        dest = host.config_dir / REMOTE_SCRIPT_FOLDER
        try:
            host.config_dir.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(template, dest)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't write {dest}: {e}")

        return InstallResult(
            True, dest,
            f"Installed for {host.name}. Restart Live, then pick "
            "'Gamepad MIDI Bridge' in Preferences → Link, Tempo & MIDI.",
        )

    def uninstall(self, host: HostInstallation) -> InstallResult:
        dest = host.config_dir / REMOTE_SCRIPT_FOLDER
        if not dest.exists():
            return InstallResult(True, None, f"Nothing to remove for {host.name}.")
        try:
            shutil.rmtree(dest)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't remove {dest}: {e}")
        return InstallResult(True, dest, f"Removed Remote Script from {host.name}.")

    def is_installed(self, host: HostInstallation) -> bool:
        return (host.config_dir / REMOTE_SCRIPT_FOLDER / "__init__.py").exists()

    def post_install_steps(self, host: HostInstallation) -> str:
        return (
            "1. Restart Ableton Live (or quit and reopen).\n"
            "2. Preferences → Link, Tempo & MIDI → Control Surface dropdown → "
            "pick 'Gamepad MIDI Bridge'.\n"
            "3. Set Input to the bridge's virtual MIDI port. Output isn't needed.\n"
            "4. Save the Live set so the Control Surface assignment persists."
        )


# --------------------------------------------------------------- platform detection

def _detect_macos() -> List[HostInstallation]:
    """Scan /Applications for `Ableton Live N*.app`, read Info.plist for version."""
    import plistlib

    apps_dir = Path("/Applications")
    if not apps_dir.exists():
        return []

    user_remote_scripts = (
        Path.home() / "Music" / "Ableton" / "User Library" / "Remote Scripts"
    )

    found: List[HostInstallation] = []
    pattern = re.compile(r"^Ableton Live (\d+)")
    for app in sorted(apps_dir.iterdir()):
        if not app.name.endswith(".app"):
            continue
        match = pattern.match(app.name)
        if not match:
            continue
        major = int(match.group(1))
        if major < MIN_MAJOR_VERSION:
            continue

        plist_path = app / "Contents" / "Info.plist"
        version = str(major)
        if plist_path.exists():
            try:
                with plist_path.open("rb") as f:
                    info = plistlib.load(f)
                version = str(info.get("CFBundleShortVersionString", major))
            except Exception:
                pass

        found.append(HostInstallation(
            name=app.stem,  # "Ableton Live 11 Suite"
            version=version,
            config_dir=user_remote_scripts,
            extra={"app_path": str(app), "major": major},
        ))
    return found


def _detect_windows() -> List[HostInstallation]:
    """Scan ProgramData for Live installs, read FileVersion via PowerShell."""
    import os

    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    ableton_root = program_data / "Ableton"
    if not ableton_root.exists():
        return []

    user_docs = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
    user_remote_scripts = (
        user_docs / "Ableton" / "User Library" / "Remote Scripts"
    )

    found: List[HostInstallation] = []
    pattern = re.compile(r"^Live (\d+)")
    for child in sorted(ableton_root.iterdir()):
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if not match:
            continue
        major = int(match.group(1))
        if major < MIN_MAJOR_VERSION:
            continue

        exe = _find_live_exe(child)
        version = str(major)
        if exe is not None:
            v = _powershell_file_version(exe)
            if v:
                version = v

        found.append(HostInstallation(
            name=child.name,            # "Live 11 Suite"
            version=version,
            config_dir=user_remote_scripts,
            extra={
                "program_data_dir": str(child),
                "exe": str(exe) if exe else None,
                "major": major,
            },
        ))
    return found


def _find_live_exe(program_data_dir: Path) -> Optional[Path]:
    """Best-effort hunt for `Ableton Live N*.exe` inside the ProgramData folder."""
    for path in program_data_dir.rglob("Ableton Live *.exe"):
        return path
    return None


def _powershell_file_version(exe: Path) -> Optional[str]:
    """Read FileVersion from a Windows exe via PowerShell. Returns None on failure."""
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Item '{exe}').VersionInfo.FileVersion",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = result.stdout.strip()
        return version or None
    except Exception:
        return None


# --------------------------------------------------------------- internals

def _template_source() -> Path:
    return (
        Path(__file__).parent
        / "templates"
        / TEMPLATE_SUBDIR
        / REMOTE_SCRIPT_FOLDER
    )
