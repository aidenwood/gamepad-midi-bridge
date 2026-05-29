"""Accessibility utilities — reduce motion + platform-level preferences.

Provides a single source of truth for motion preference checks across the app.
Reads from QSettings (user pref) and OS-level accessibility settings.
"""
from __future__ import annotations

import platform
import subprocess
from PySide6.QtCore import QSettings

_QSETTINGS_ORG = "ucmd"
_QSETTINGS_APP = "gamepad-midi-bridge"


def reduce_motion_enabled() -> bool:
    """Read user preference from QSettings (appearance/reduce_motion)."""
    qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
    return qs.value("appearance/reduce_motion", False, type=bool)


def prefers_reduced_motion() -> bool:
    """Return True if user has reduce motion enabled OR OS-level setting is on.

    Checks:
    - QSettings: appearance/reduce_motion
    - macOS: defaults read com.apple.universalaccess reduceMotion
    - Windows: SystemParametersInfo SPI_GETCLIENTAREAANIMATION
    - Linux: gtk-enable-animations GSettings

    Returns True if ANY setting prefers reduced motion.
    """
    # User preference
    if reduce_motion_enabled():
        return True

    # OS-level checks
    system = platform.system()

    if system == "Darwin":  # macOS
        try:
            result = subprocess.run(
                ["defaults", "read", "com.apple.universalaccess", "reduceMotion"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.returncode == 0 and result.stdout.strip() == "1"
        except Exception:
            return False

    elif system == "Windows":
        try:
            import ctypes
            SPI_GETCLIENTAREAANIMATION = 0x1026
            disabled = ctypes.c_bool()
            result = ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(disabled), 0
            )
            return result != 0 and not disabled.value
        except Exception:
            return False

    elif system == "Linux":
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-enable-animations"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            # gsettings returns "true" or "false" as strings
            return result.returncode == 0 and "false" in result.stdout.lower()
        except Exception:
            return False

    return False
