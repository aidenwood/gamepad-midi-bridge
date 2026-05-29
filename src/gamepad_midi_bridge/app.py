"""Application entry point — builds QApplication and shows the main window."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME
from .presets import seed_user_presets_once
from .ui.main_window import MainWindow


def _load_stylesheet() -> str:
    qss = Path(__file__).parent / "ui" / "styles.qss"
    return qss.read_text(encoding="utf-8") if qss.exists() else ""


class _MacOpenUrlFilter(QObject):
    """macOS delivers gmb:// URLs via QFileOpenEvent rather than argv."""

    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self._win = win

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.FileOpen:
            url = event.url().toString() if event.url().isValid() else event.file()
            if url:
                self._win.handle_deep_link(url)
                return True
        return super().eventFilter(watched, event)


def _extract_deep_links(argv: List[str]) -> List[str]:
    """Pull every `gmb://` arg out of argv so we can hand them to the window."""
    return [a for a in argv[1:] if a.startswith("gmb://")]


def run(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv

    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setOrganizationName("Aidxn Design")
    QCoreApplication.setOrganizationDomain("aidxn.com")
    QGuiApplication.setDesktopFileName(APP_ID)

    seed_user_presets_once()

    app = QApplication(argv)
    app.setStyleSheet(_load_stylesheet())

    # Install keyboard event filter if requested
    import os
    if os.environ.get("GMB_KEYBOARD") == "1":
        from .keyboard_bus import install_keyboard_filter
        install_keyboard_filter(app)

    icon_path = Path(__file__).parent / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = MainWindow()

    # Check for background/headless mode (feature #12)
    import os
    background_mode = os.environ.get("GMB_BACKGROUND") == "1"
    if background_mode:
        # Start bridge in background — check if tray is available
        if hasattr(win, "_tray") and win._tray is not None:
            win.hide()
            win._on_start()  # Auto-start the bridge
        else:
            # Tray not available, show window anyway
            import logging
            logging.getLogger("app").warning(
                "System tray not available; showing window instead of headless mode"
            )
            win.show()
    else:
        win.show()

    # Deep-link wiring — argv on Win/Linux, FileOpen event on macOS.
    for link in _extract_deep_links(argv):
        win.handle_deep_link(link)
    if sys.platform == "darwin":
        url_filter = _MacOpenUrlFilter(win)
        app.installEventFilter(url_filter)
        win._mac_url_filter = url_filter  # keep reference alive

    # Hand control to Qt's event loop.
    run_loop = getattr(app, "exec")
    return run_loop()
