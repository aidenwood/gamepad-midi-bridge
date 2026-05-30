"""Background update check.

On startup we hit `midi.aidxn.com/api/version` on a worker thread and emit
a signal back to the GUI if a newer version is available. The user can opt
out via the config file — the check is a courtesy, not a phone-home.

Endpoint shape (server-side, JSON):
    {
        "latest": "0.2.0",
        "notes_url": "https://midi.aidxn.com/changelog#v0-2-0",
        "download_url": "https://midi.aidxn.com/download",
        "minimum_supported": "0.1.0"
    }

We never auto-download anything. The banner only links the user to the
release notes — they install the new version themselves.

Release channels (stable/beta/dev):
  - Stable: only v1.2.0 (no pre-release suffix)
  - Beta: v1.2.0-beta.N, v1.2.0-rc.N, and stable
  - Dev: all tags including v1.2.0-dev.N
"""
from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, Signal

from . import __version__
from .paths import config_path


UPDATE_URL = "https://midi.aidxn.com/api/version"
TIMEOUT_SEC = 6   # short — don't block startup if the API is slow


@dataclass
class UpdateInfo:
    latest: str
    notes_url: str
    download_url: str
    minimum_supported: Optional[str] = None


class UpdateChecker(QObject):
    """Runs an HTTP fetch on a background thread, emits result on the GUI thread."""

    update_available = Signal(object)   # UpdateInfo
    no_update = Signal()                # current is latest
    check_failed = Signal(str)          # human-readable reason

    def check_async(self) -> None:
        if not _user_opted_in():
            return
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            req = urllib.request.Request(
                UPDATE_URL,
                headers={"User-Agent": f"gamepad-midi-bridge/{__version__}"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            self.check_failed.emit(str(e))
            return
        except Exception as e:
            self.check_failed.emit(f"Parse error: {e}")
            return

        try:
            info = UpdateInfo(
                latest=str(payload["latest"]),
                notes_url=str(payload.get("notes_url", "")),
                download_url=str(payload.get("download_url", "")),
                minimum_supported=payload.get("minimum_supported"),
            )
        except KeyError as e:
            self.check_failed.emit(f"Missing field: {e}")
            return

        channel = _get_channel()
        if _is_version_allowed(info.latest, channel) and _is_newer(info.latest, __version__):
            self.update_available.emit(info)
        else:
            self.no_update.emit()


# --------------------------------------------------------------- helpers


def _user_opted_in() -> bool:
    """Read the config file for an explicit opt-out. Default is opt-in."""
    path = config_path()
    if not path.exists():
        return True
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        return bool(cfg.get("check_for_updates", True))
    except Exception:
        return True


def _get_channel() -> str:
    """Read update channel from config. Default is 'stable'."""
    path = config_path()
    if not path.exists():
        return "stable"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        return str(cfg.get("update_channel", "stable"))
    except Exception:
        return "stable"


def set_opt_in(enabled: bool) -> None:
    """Persist the opt-in flag."""
    path = config_path()
    cfg: dict = {}
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    cfg["check_for_updates"] = bool(enabled)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def set_channel(channel: str) -> None:
    """Persist the update channel."""
    if channel not in ("stable", "beta", "dev"):
        raise ValueError(f"Invalid channel: {channel}")
    path = config_path()
    cfg: dict = {}
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    cfg["update_channel"] = channel
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _is_version_allowed(version: str, channel: str) -> bool:
    """Check if version tag matches the selected release channel.

    Args:
        version: version string (e.g. "1.2.0", "1.2.0-beta.1", "1.2.0-rc.2")
        channel: "stable" | "beta" | "dev"

    Returns:
        True if the version is allowed for the channel, False otherwise.
    """
    # Extract pre-release suffix if present: "1.2.0-beta.1" → "beta.1"
    match = re.match(r"^v?\d+\.\d+\.\d+(?:-(.+))?$", version)
    if not match:
        return False  # invalid version format

    suffix = match.group(1)  # None if no pre-release, else the suffix

    if channel == "stable":
        # Only allow versions with no pre-release suffix
        return suffix is None
    elif channel == "beta":
        # Allow beta, rc, and stable (no suffix)
        if suffix is None:
            return True
        return suffix.startswith("beta") or suffix.startswith("rc")
    elif channel == "dev":
        # Allow everything
        return True
    else:
        return False


def _is_newer(remote: str, local: str) -> bool:
    """Best-effort semver-ish comparison. Treats non-numeric parts as 0."""
    def tup(v: str) -> tuple:
        parts = []
        for chunk in v.split("."):
            try:
                parts.append(int("".join(c for c in chunk if c.isdigit()) or "0"))
            except ValueError:
                parts.append(0)
        return tuple(parts)
    return tup(remote) > tup(local)
