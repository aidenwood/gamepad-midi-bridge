"""Theme management — dark/light/system detection and stylesheet loading."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal

ThemeType = Literal["dark", "light", "system"]
THEMES = ("dark", "light", "system")


def detect_system_theme() -> str:
    """
    Detect the OS dark-mode preference.

    Returns "dark" or "light".
    Falls back to "dark" on any error.

    - macOS: `defaults read -g AppleInterfaceStyle` → "Dark*" ⟹ dark
    - Linux (GNOME): `gsettings get org.gnome.desktop.interface color-scheme` → "prefer-dark" ⟹ dark
    - Windows: winreg HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme
    """
    try:
        if sys.platform == "darwin":
            # macOS
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip().startswith("Dark"):
                return "dark"
            return "light"
        elif sys.platform == "linux":
            # Try GNOME settings
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and "prefer-dark" in result.stdout:
                return "dark"
            return "light"
        elif sys.platform == "win32":
            # Windows Registry check
            import winreg
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                ) as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    return "light" if value == 1 else "dark"
            except Exception:
                return "dark"
    except Exception:
        pass
    return "dark"


def load_theme_qss(theme: str) -> str:
    """
    Load QSS stylesheet for the given theme.

    theme: one of "dark", "light", "system"
    Returns the QSS file contents as a string.
    """
    if theme == "system":
        theme = detect_system_theme()

    qss_name = f"styles_{theme}.qss" if theme != "dark" else "styles.qss"
    qss_path = Path(__file__).parent / qss_name

    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


def apply_theme(app, theme: str) -> None:
    """
    Apply the QSS stylesheet for the given theme to the QApplication.

    app: QApplication instance
    theme: one of "dark", "light", "system"
    """
    qss = load_theme_qss(theme)
    if qss:
        app.setStyleSheet(qss)
