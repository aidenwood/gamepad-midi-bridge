"""Subprocess helpers that keep Windows console windows off the user's screen.

On Windows, a GUI app built with PyInstaller's `--windowed` flag has no
console of its own. The moment it shells out to a console binary
(`powershell.exe`, `tasklist`, `cmd`), Windows allocates a brand-new
console window, flashes it on top of whatever the user is doing, and
steals focus. Do that on a 6-second poll timer and you've made the app
unusable next to a DAW.

`no_window_kwargs()` returns the creationflags + STARTUPINFO that suppress
it, and an empty dict everywhere else, so call sites stay one-liners:

    subprocess.run([...], capture_output=True, text=True, **no_window_kwargs())
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any, Dict

# subprocess.CREATE_NO_WINDOW only exists on Windows; hardcode the value so
# this module imports cleanly on macOS/Linux.
CREATE_NO_WINDOW = 0x08000000


def no_window_kwargs() -> Dict[str, Any]:
    """subprocess kwargs that stop a console window appearing on Windows.

    Returns {} on macOS/Linux so call sites can splat it unconditionally.
    We gate on `hasattr(subprocess, "STARTUPINFO")` rather than on
    sys.platform alone — tests monkeypatch sys.platform to "win32" while
    still running on a POSIX box, and STARTUPINFO simply doesn't exist there.
    """
    if sys.platform != "win32":
        return {}
    if not hasattr(subprocess, "STARTUPINFO"):
        return {"creationflags": CREATE_NO_WINDOW}

    startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    startupinfo.wShowWindow = subprocess.SW_HIDE  # type: ignore[attr-defined]
    return {
        "creationflags": CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }
