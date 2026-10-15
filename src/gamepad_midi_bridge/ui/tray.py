"""System tray / menu bar icon.

Lets users keep the bridge running with no main window taking up space.
Right-click → status block, then Start / Stop / Panic / Show / Quit.
Double-click brings the main window forward.

The top of the menu is a read-only status block (disabled QActions used as
labels): running state, which controller is attached, and which MIDI port
we're sending to. The port line carries a warning marker when we fell back
to a downstream port instead of a loopMIDI one, because that's the state
where a user hears notes but their DAW gets nothing — and the main window
may be minimised to the tray when it happens.

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
    panic_requested = Signal()
    about_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon_path: Optional[Path], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.tray = QSystemTrayIcon(parent)
        if icon_path is not None and icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        self.tray.setToolTip("Universal Controller MIDI")
        self._running = False
        self._fallback = False

        menu = QMenu()

        # ---- status block (labels, not actions) ----
        self._status = QAction("Idle", menu)
        self._status.setEnabled(False)
        menu.addAction(self._status)

        self._controller = QAction("No controller", menu)
        self._controller.setEnabled(False)
        menu.addAction(self._controller)

        self._port = QAction("No MIDI port", menu)
        self._port.setEnabled(False)
        menu.addAction(self._port)

        menu.addSeparator()

        self._start = QAction("Start bridging", menu)
        self._start.triggered.connect(self.start_requested.emit)
        menu.addAction(self._start)

        self._stop = QAction("Stop bridging", menu)
        self._stop.triggered.connect(self.stop_requested.emit)
        self._stop.setEnabled(False)
        menu.addAction(self._stop)

        # Panic belongs here, not buried: a stuck note with the window hidden
        # in the tray is exactly when you need all-notes-off and can't get to
        # the main window quickly.
        self._panic = QAction("Panic — all notes off", menu)
        self._panic.triggered.connect(self.panic_requested.emit)
        self._panic.setEnabled(False)
        menu.addAction(self._panic)

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
        self._panic.setEnabled(running)
        self._running = running
        self._status.setText("● Bridging" if running else "○ Idle")
        if not running:
            self._controller.setText("No controller")
            self._port.setText("No MIDI port")
            self._fallback = False
        self._refresh_tooltip()

    def set_status(self, controller: str = "", port: str = "",
                   fallback: bool = False) -> None:
        """Update the read-only status block.

        ``fallback`` means the MIDI backend landed on a downstream port
        (e.g. the Windows GS synth) rather than a routable virtual port.
        """
        if controller:
            self._controller.setText(controller)
        if port:
            self._port.setText(("⚠ " + port + " — not your DAW") if fallback
                               else ("→ " + port))
        self._fallback = fallback
        self._refresh_tooltip()

    def _refresh_tooltip(self) -> None:
        """Tooltip mirrors the menu — on Windows it's the hover text users
        get without opening the menu at all."""
        if not getattr(self, "_running", False):
            self.tray.setToolTip("Universal Controller MIDI — idle")
            return
        bits = ["Universal Controller MIDI — bridging"]
        ctrl = self._controller.text()
        if ctrl and ctrl != "No controller":
            bits.append(ctrl)
        port = self._port.text()
        if port and port != "No MIDI port":
            bits.append(port)
        if getattr(self, "_fallback", False):
            bits.append("Not routing to a DAW — install loopMIDI")
        self.tray.setToolTip("\n".join(bits))

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Double-click on Win/Linux, single click on mac's menu-bar item.
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_requested.emit()


def is_available() -> bool:
    """Some Linux desktops have no tray support — gate visibility on this."""
    return QSystemTrayIcon.isSystemTrayAvailable()
