"""REAPER KeyMap connector.

Reaper exposes MIDI-to-action bindings via .ReaperKeyMap files — a plain-text
format documented at https://forum.cockos.com/showthread.php?t=240625 . Each
line takes the form:

    KEY <flags> <key> <action_id> <section>

For MIDI bindings, flags include MIDI-mode bits (0xC1 for CC, 0xA1 for note),
key holds the CC/note number, and section is 0 (main).

Install paths:
    macOS  : ~/Library/Application Support/REAPER/KeyMaps/Gamepad MIDI Bridge.ReaperKeyMap
    Windows: %APPDATA%\\REAPER\\KeyMaps\\Gamepad MIDI Bridge.ReaperKeyMap
    Linux  : ~/.config/REAPER/KeyMaps/Gamepad MIDI Bridge.ReaperKeyMap

Reaper has a native Linux build, so we handle all three platforms.

Confidence note: KeyMap flag bytes for MIDI bindings are partially documented;
the exact action IDs are stable but the flag encoding for CC vs note-on varies
slightly between Reaper versions. Users may need to re-import via Actions →
Show actions list → Key bindings → Import.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Optional

from .base import Connector, HostInstallation, InstallResult


KEYMAP_FILENAME = "Gamepad MIDI Bridge.ReaperKeyMap"
TEMPLATE_FILENAME = "reaper_default.ReaperKeyMap"


class ReaperConnector(Connector):
    display_name = "REAPER"
    slug = "reaper"
    description = (
        "Drop a KeyMap into REAPER's KeyMaps folder. Import via Actions → "
        "Show actions list → Key bindings tab → Import. Maps face buttons to "
        "track record-arm, triggers to master/crossfader, transport keys to "
        "Play/Stop/Loop/Metronome/Record."
    )

    # ------------------------------------------------ detection

    def detect(self) -> List[HostInstallation]:
        if sys.platform == "darwin":
            return _detect_macos()
        if sys.platform == "win32":
            return _detect_windows()
        return _detect_linux()

    # ------------------------------------------------ install

    def install(self, host: HostInstallation) -> InstallResult:
        try:
            host.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't create {host.config_dir}: {e}")

        template = _template_path(TEMPLATE_FILENAME)
        if not template.exists():
            return InstallResult(
                False, None,
                f"Template missing — {template.name} not bundled with this build.",
            )

        dest = host.config_dir / KEYMAP_FILENAME
        try:
            dest.write_text(template.read_text(), encoding="utf-8")
        except Exception as e:
            return InstallResult(False, None, f"Couldn't write {dest}: {e}")

        return InstallResult(
            True, dest,
            f"Installed for {host.name}. Open REAPER → Actions → Show "
            "actions list → Key bindings tab → Import — then pick the file.",
        )

    def uninstall(self, host: HostInstallation) -> InstallResult:
        dest = host.config_dir / KEYMAP_FILENAME
        if not dest.exists():
            return InstallResult(True, None, f"Nothing to remove for {host.name}.")
        try:
            dest.unlink()
        except Exception as e:
            return InstallResult(False, None, f"Couldn't remove {dest}: {e}")
        return InstallResult(True, dest, f"Removed KeyMap from {host.name}.")

    def is_installed(self, host: HostInstallation) -> bool:
        return (host.config_dir / KEYMAP_FILENAME).exists()

    def post_install_steps(self, host: HostInstallation) -> str:
        return (
            "1. Open REAPER.\n"
            "2. Actions → Show actions list (or press '?').\n"
            "3. Switch to the 'Key bindings and mouse modifiers' tab.\n"
            "4. Click 'Import/export' → 'Import bindings…' → pick the file "
            f"'{KEYMAP_FILENAME}'.\n"
            "5. Preferences → MIDI Devices → enable the bridge virtual port "
            "as a control surface (Control mode: MIDI)."
        )


# --------------------------------------------------------------- platform detection

def _detect_macos() -> List[HostInstallation]:
    """Scan /Applications for REAPER*.app, version from Info.plist."""
    import plistlib

    apps_dir = Path("/Applications")
    if not apps_dir.exists():
        return []

    config_dir = (
        Path.home() / "Library" / "Application Support" / "REAPER" / "KeyMaps"
    )

    found: List[HostInstallation] = []
    pattern = re.compile(r"^REAPER.*\.app$", re.IGNORECASE)
    for app in sorted(apps_dir.iterdir()):
        if not pattern.match(app.name):
            continue
        plist_path = app / "Contents" / "Info.plist"
        version = "unknown"
        if plist_path.exists():
            try:
                with plist_path.open("rb") as f:
                    info = plistlib.load(f)
                version = str(info.get("CFBundleShortVersionString", "unknown"))
            except Exception:
                pass
        found.append(HostInstallation(
            name=app.stem,
            version=version,
            config_dir=config_dir,
            extra={"app_path": str(app)},
        ))
    return found


def _detect_windows() -> List[HostInstallation]:
    """Look for the standard REAPER install + KeyMaps under %APPDATA%."""
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    exe = program_files / "REAPER (x64)" / "reaper.exe"
    if not exe.exists():
        # Try the 32-bit path as a fallback.
        exe = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "REAPER" / "reaper.exe"
        if not exe.exists():
            return []

    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    config_dir = appdata / "REAPER" / "KeyMaps"

    return [HostInstallation(
        name="REAPER",
        version=_powershell_file_version(exe) or "unknown",
        config_dir=config_dir,
        extra={"exe": str(exe)},
    )]


def _detect_linux() -> List[HostInstallation]:
    """Check the standard ~/.config/REAPER location."""
    reaper_config = Path.home() / ".config" / "REAPER"
    if not reaper_config.exists():
        return []
    config_dir = reaper_config / "KeyMaps"
    return [HostInstallation(
        name="REAPER (Linux)",
        version="unknown",
        config_dir=config_dir,
        extra={"config_root": str(reaper_config)},
    )]


def _powershell_file_version(exe: Path) -> Optional[str]:
    """Read FileVersion from a Windows exe via PowerShell. None on failure."""
    import subprocess
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

def _template_path(filename: str) -> Path:
    return Path(__file__).parent / "templates" / filename
