"""Opt-in anonymous usage stats.

Default OFF. Only sends:
    - app version
    - OS name + major version
    - which connectors were installed (Resolume/Ableton)
    - aggregate session length

Never sends:
    - mapping contents
    - preset names or JSON
    - controller serial numbers
    - IP-identifiable information (Netlify edge strips IP from the bucket)
    - timing data that could correlate to a specific user

We piggyback on `paths.config_path()` so the opt-in flag is in the same
file as the update-check preference. No second config to manage.
"""
from __future__ import annotations

import json
import platform
import threading
import urllib.error
import urllib.request
from typing import Any, Dict

from . import __version__
from .paths import config_path


TELEMETRY_URL = "https://midi.aidxn.com/api/telemetry"
TIMEOUT_SEC = 4


def is_enabled() -> bool:
    """Default OFF — must be flipped on in Settings."""
    path = config_path()
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("telemetry_enabled", False))
    except Exception:
        return False


def set_enabled(enabled: bool) -> None:
    path = config_path()
    cfg: dict = {}
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    cfg["telemetry_enabled"] = bool(enabled)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def send_event(event: str, **fields: Any) -> None:
    """Fire-and-forget event send. No-ops when disabled."""
    if not is_enabled():
        return
    payload: Dict[str, Any] = {
        "event": event,
        "app_version": __version__,
        "os": platform.system(),
        "os_version": platform.release(),
    }
    payload.update(fields)
    threading.Thread(target=_post, args=(payload,), daemon=True).start()


def _post(payload: Dict[str, Any]) -> None:
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"gamepad-midi-bridge/{__version__}",
            },
        )
        urllib.request.urlopen(req, timeout=TIMEOUT_SEC).read()
    except urllib.error.URLError:
        pass
    except Exception:
        pass
