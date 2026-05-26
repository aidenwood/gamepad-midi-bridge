"""Connector base class.

A Connector represents one host application we can auto-configure (Resolume,
Ableton Live, TouchDesigner, etc.). The bridge ships a registry of available
connectors; each one detects whether the host is installed, where its config
lives, and writes/removes our integration files.

Connectors run user-side only — they never reach into the user's project files,
just into the host's well-known shortcut / script directories.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class HostInstallation:
    """One detected install of a host application (e.g. Resolume Arena 7)."""
    name: str                # "Resolume Arena 7"
    version: str             # "7"
    config_dir: Path         # where we write our integration file
    extra: dict              # connector-specific data


@dataclass
class InstallResult:
    success: bool
    written_path: Optional[Path]
    message: str             # what to tell the user (success or failure)


class Connector:
    """Subclass per host application."""

    # Display name shown in the Connectors tab. Override.
    display_name: str = "Generic Connector"
    # Short identifier used in storage/logging. Override.
    slug: str = "generic"
    # One-line marketing description shown in the UI.
    description: str = ""
    # Marks features that only Pro can install (most templates are free).
    pro_only: bool = False

    # ------------------------------------------------ detection

    def detect(self) -> List[HostInstallation]:
        """Return every installation of the host found on this machine."""
        raise NotImplementedError

    # ------------------------------------------------ install / uninstall

    def install(self, host: HostInstallation) -> InstallResult:
        """Write the integration file(s) into the host's config directory."""
        raise NotImplementedError

    def uninstall(self, host: HostInstallation) -> InstallResult:
        """Remove anything install() wrote."""
        raise NotImplementedError

    def is_installed(self, host: HostInstallation) -> bool:
        """Whether our integration is currently present for `host`."""
        raise NotImplementedError

    # ------------------------------------------------ user instructions

    def post_install_steps(self, host: HostInstallation) -> str:
        """One-paragraph guidance for the user after install() succeeds."""
        return "Done — open the host application to use the new mapping."


# --------------------------------------------------------------- platform helpers

def documents_dir() -> Path:
    """Cross-platform 'Documents' folder. Resolume + many hosts park config here."""
    if sys.platform == "win32":
        import os
        # %USERPROFILE%\Documents — modern Windows always exposes this.
        profile = Path(os.environ.get("USERPROFILE", Path.home()))
        return profile / "Documents"
    # macOS and Linux both honour ~/Documents.
    return Path.home() / "Documents"
