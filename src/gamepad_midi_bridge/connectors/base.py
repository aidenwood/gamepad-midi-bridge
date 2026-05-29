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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


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


# How old (in seconds) an installed file can be before we flag it as stale.
STALE_THRESHOLD_SECONDS: int = 30 * 24 * 60 * 60  # 30 days


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

    # ------------------------------------------------ self-test

    def _installed_file(self, host: HostInstallation) -> Optional[Path]:
        """Return the primary installed file path, or None if not applicable.

        Subclasses override this to point at the canonical file that
        verify() should probe. The default returns None which causes
        verify() to fall back to is_installed().
        """
        return None

    def verify(
        self,
        host: HostInstallation,
        stale_threshold: int = STALE_THRESHOLD_SECONDS,
    ) -> Tuple[str, str]:
        """Run a multi-step probe against the installed integration.

        Returns a (status, details) pair where status is one of:
            'verified'  — file present and mtime within threshold
            'outdated'  — file present but older than stale_threshold seconds
            'missing'   — file not present

        Args:
            host: the installation to verify.
            stale_threshold: seconds beyond which a file is considered stale.
        """
        # 1. Resolve which file to probe.
        target = self._installed_file(host)
        if target is None:
            # Fall back: just check is_installed().
            try:
                present = self.is_installed(host)
            except Exception as exc:
                return "missing", f"is_installed() raised: {exc}"
            if not present:
                return "missing", f"Integration not found under {host.config_dir}"
            return "verified", f"Installed (path check only) — {host.config_dir}"

        # 2. Check the path exists.
        if not target.exists():
            return "missing", f"Expected file not found: {target}"

        # 3. Check mtime.
        try:
            age = time.time() - target.stat().st_mtime
        except OSError as exc:
            return "missing", f"Could not stat {target}: {exc}"

        if age > stale_threshold:
            days = int(age // 86400)
            return (
                "outdated",
                f"File exists but hasn't been updated in {days} day(s): {target}",
            )

        return "verified", f"Installed and up-to-date: {target}"

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
