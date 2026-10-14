"""Windows-only helper-app auto-launch.

Revives the auto-launch from the original prototype
(`docs/origin/ps5_calibrated_bridge.py` → `ensure_running`): make sure the
helper apps the MIDI pipeline leans on are actually running before we open a
port, so non-technical users don't have to start them by hand.

- **loopMIDI** carries the virtual MIDI port — always attempted (it's harmless
  to launch if installed).
- **DS4Windows** is OPT-IN. It re-presents a DualSense as an XInput pad, which
  helps SDL read sticks/buttons reliably — but it also *masks the raw HID
  device* that `dualsense.py` needs for adaptive triggers, touchpad and gyro.
  So launching it can cost you "more of the controller", not add it. Off by
  default; enable via config key ``launch_ds4windows``.

Everything here is best-effort: it never raises into the bridge and never
blocks (no fixed sleeps — the caller polls the port itself). No-op off Windows.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional

from .proc import CREATE_NO_WINDOW, no_window_kwargs

log = logging.getLogger("gamepad_midi_bridge.windows_sidecar")


@dataclass(frozen=True)
class HelperApp:
    label: str
    process_name: str            # as it appears in tasklist, e.g. "loopMIDI.exe"
    candidate_paths: tuple       # absolute .exe paths to try, in order


def _pf() -> str:
    return os.environ.get("ProgramFiles", r"C:\Program Files")


def _pf86() -> str:
    return os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")


def loopmidi_app() -> HelperApp:
    return HelperApp(
        label="loopMIDI",
        process_name="loopMIDI.exe",
        candidate_paths=(
            os.path.join(_pf86(), "Tobias Erichsen", "loopMIDI", "loopMIDI.exe"),
            os.path.join(_pf(), "Tobias Erichsen", "loopMIDI", "loopMIDI.exe"),
        ),
    )


def ds4windows_app() -> HelperApp:
    return HelperApp(
        label="DS4Windows",
        process_name="DS4Windows.exe",
        candidate_paths=(
            os.path.join(_pf(), "DS4Windows", "DS4Windows.exe"),
            os.path.join(_pf86(), "DS4Windows", "DS4Windows.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "DS4Windows", "DS4Windows.exe"),
        ),
    )


def _first_existing(paths) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _default_is_running(process_name: str) -> bool:
    """True if `process_name` shows in tasklist. Mirrors the original prototype."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
            **no_window_kwargs(),
        )
        return process_name.lower() in (result.stdout or "").lower()
    except Exception:
        return False


def ensure_helper(
    app: HelperApp,
    *,
    is_running: Callable[[str], bool] = _default_is_running,
    launcher: Optional[Callable[[str], None]] = None,
) -> str:
    """Ensure one helper is running. Returns a status string for logging/UI.

    `is_running` and `launcher` are injectable so the decision logic is testable
    without a real Windows box.
    """
    if is_running(app.process_name):
        return f"{app.label}: already running"
    exe = _first_existing(app.candidate_paths)
    if exe is None:
        return f"{app.label}: not installed"
    try:
        if launcher is not None:
            launcher(exe)
        else:
            # CREATE_NEW_PROCESS_GROUP so the helper doesn't die with us;
            # CREATE_NO_WINDOW so a console-mode helper can't flash a black
            # window over the user's DAW. Neither affects a GUI helper's
            # own windows (loopMIDI / DS4Windows still show normally).
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            subprocess.Popen(
                [exe],
                creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            )
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to launch %s: %s", app.label, e)
        return f"{app.label}: launch failed ({e})"
    return f"{app.label}: launched"


def ensure_helpers_running(
    launch_ds4: bool = False,
    *,
    is_running: Callable[[str], bool] = _default_is_running,
    launcher: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """Launch loopMIDI (always) and optionally DS4Windows. No-op off Windows.

    Returns a list of per-helper status strings. Never raises.
    """
    if sys.platform != "win32":
        return []
    apps = [loopmidi_app()]
    if launch_ds4:
        apps.append(ds4windows_app())
    statuses = []
    for app in apps:
        status = ensure_helper(app, is_running=is_running, launcher=launcher)
        statuses.append(status)
        log.info(status)
    return statuses
