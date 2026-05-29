"""Resolume Arena MIDI shortcuts connector.

Resolume stores MIDI maps as XML files inside the user's Documents folder.
Directory name is uppercase `MIDI` (verified against factory installs on mac):

    macOS  : ~/Documents/Resolume Arena N/Shortcuts/MIDI/<name>.xml
    Windows: %USERPROFILE%\\Documents\\Resolume Arena N\\Shortcuts\\MIDI\\<name>.xml

Where `N` is the major version (7, 8, 9). We scan for any such folder and
write our XML template into each. Resolume re-reads the directory each time
the user opens the Shortcuts menu, so no restart is needed; the user just
picks our preset from the menu.

The actual XML template lives at `templates/resolume_default.xml`. A research
sub-agent is responsible for keeping that schema accurate.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import List

from .base import Connector, HostInstallation, InstallResult, documents_dir


SHORTCUT_FILENAME = "Universal Controller MIDI.xml"
TEMPLATE_FILENAME = "resolume_default.xml"
MINIMAL_TEMPLATE_FILENAME = "resolume_minimal.xml"


class ResolumeConnector(Connector):
    display_name = "Resolume Arena"
    slug = "resolume"
    description = (
        "Drop a MIDI map into Resolume's Shortcuts folder. Pick it from "
        "Shortcuts → Application Map. Auto-mapped: face buttons → clip launch, "
        "sticks → layer transform, triggers → speed + crossfader."
    )

    # ------------------------------------------------ detection

    def detect(self) -> List[HostInstallation]:
        """Find every Resolume Arena N folder under ~/Documents."""
        docs = documents_dir()
        if not docs.exists():
            return []

        found: List[HostInstallation] = []
        # Resolume folder names look like "Resolume Arena 7", "Resolume Arena 8".
        # Some users have "Resolume Avenue N" — same XML schema, treat the same.
        pattern = re.compile(r"^Resolume (Arena|Avenue) (\d+)$")
        for child in sorted(docs.iterdir()):
            if not child.is_dir():
                continue
            match = pattern.match(child.name)
            if not match:
                continue
            shortcuts_dir = child / "Shortcuts" / "Midi"
            found.append(HostInstallation(
                name=child.name,
                version=match.group(2),
                config_dir=shortcuts_dir,
                extra={"edition": match.group(1)},
            ))
        return found

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

        dest = host.config_dir / SHORTCUT_FILENAME
        try:
            shutil.copyfile(template, dest)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't write {dest}: {e}")

        return InstallResult(
            True, dest,
            f"Installed for {host.name}. Open Resolume and pick "
            "'Universal Controller MIDI' from Shortcuts → Application Map.",
        )

    def uninstall(self, host: HostInstallation) -> InstallResult:
        dest = host.config_dir / SHORTCUT_FILENAME
        if not dest.exists():
            return InstallResult(True, None, f"Nothing to remove for {host.name}.")
        try:
            dest.unlink()
        except Exception as e:
            return InstallResult(False, None, f"Couldn't remove {dest}: {e}")
        return InstallResult(True, dest, f"Removed shortcut from {host.name}.")

    def is_installed(self, host: HostInstallation) -> bool:
        return (host.config_dir / SHORTCUT_FILENAME).exists()

    def _installed_file(self, host: HostInstallation) -> Path:
        return host.config_dir / SHORTCUT_FILENAME

    def post_install_steps(self, host: HostInstallation) -> str:
        return (
            "1. Open Resolume.\n"
            "2. Go to Shortcuts → Application Map.\n"
            "3. Pick 'Universal Controller MIDI'.\n"
            "4. Make sure Resolume's MIDI input is set to the bridge "
            "virtual port (Preferences → MIDI)."
        )


# --------------------------------------------------------------- internals


def _template_path(filename: str) -> Path:
    return Path(__file__).parent / "templates" / filename
