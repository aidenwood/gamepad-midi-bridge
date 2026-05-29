"""System tray / menu bar icon.

Lets users keep the bridge running with no main window taking up space.
Right-click → Start / Stop / Show window / Quit. Double-click brings the
main window forward.

On macOS this lives in the menu bar (top right). On Windows it's the
system tray (bottom right). On Linux it depends on the DE — works on KDE
+ Gnome with TopIcons / equivalent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayController(QObject):
    """Tray icon + menu. Hands events back to the main window via signals."""

    start_requested = Signal()
    stop_requested = Signal()
    show_requested = Signal()
    command_palette_requested = Signal()
    latency_test_requested = Signal()
    about_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon_path: Optional[Path], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.tray = QSystemTrayIcon(parent)
        if icon_path is not None and icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        self.tray.setToolTip("Universal Controller MIDI")

        menu = QMenu()
        self._start = QAction("Start bridging", menu)
        self._start.triggered.connect(self.start_requested.emit)
        menu.addAction(self._start)

        self._stop = QAction("Stop bridging", menu)
        self._stop.triggered.connect(self.stop_requested.emit)
        self._stop.setEnabled(False)
        menu.addAction(self._stop)

        menu.addSeparator()

        show = QAction("Show window", menu)
        show.triggered.connect(self.show_requested.emit)
        menu.addAction(show)

        menu.addSeparator()

        # Command palette
        palette = QAction("Open command palette", menu)
        palette.triggered.connect(self.command_palette_requested.emit)
        menu.addAction(palette)

        # Run latency test
        latency = QAction("Run latency test", menu)
        latency.triggered.connect(self.latency_test_requested.emit)
        menu.addAction(latency)

        menu.addSeparator()

        # About
        about = QAction("About...", menu)
        about.triggered.connect(self.about_requested.emit)
        menu.addAction(about)

        menu.addSeparator()

        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def set_running(self, running: bool) -> None:
        self._start.setEnabled(not running)
        self._stop.setEnabled(running)
        self.tray.setToolTip(
            "Universal Controller MIDI — bridging" if running
            else "Universal Controller MIDI — idle"
        )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Double-click on Win/Linux, single click on mac's menu-bar item.
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_requested.emit()


def is_available() -> bool:
    """Some Linux desktops have no tray support — gate visibility on this."""
    return QSystemTrayIcon.isSystemTrayAvailable()
