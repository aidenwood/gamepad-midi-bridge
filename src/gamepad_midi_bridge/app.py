"""Application entry point — builds QApplication and shows the main window."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME
from .presets import seed_user_presets_once
from .ui.main_window import MainWindow
from .ui.theme import apply_theme


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


_DEEP_LINK_PREFIXES = ("gmb://", "gamepad-midi-bridge://")


def _extract_deep_links(argv: List[str]) -> List[str]:
    """Pull every deep-link URL out of argv. Accepts both the short ``gmb://``
    scheme and the long ``gamepad-midi-bridge://`` alias."""
    return [a for a in argv[1:] if a.startswith(_DEEP_LINK_PREFIXES)]


def run(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv

    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setOrganizationName("Aidxn Design")
    QCoreApplication.setOrganizationDomain("aidxn.com")
    QGuiApplication.setApplicationDisplayName(APP_NAME)
    QGuiApplication.setDesktopFileName(APP_ID)

    seed_user_presets_once()

    app = QApplication(argv)

    # Ctrl-C from a terminal launch: Qt's event loop otherwise swallows SIGINT,
    # and when it does surface, KeyboardInterrupt unwinds into Python's finaliser
    # — which segfaults sweeping live Qt wrappers (QSlider/QDoubleSpinBox) in
    # Shiboken. Restore the OS default handler so Ctrl-C terminates the process
    # immediately, before any finalisation runs. Belt to console_entry's braces.
    import signal
    try:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    except (ValueError, OSError):
        pass  # not the main thread / unsupported platform — non-fatal

    # Load the default theme (system). Will be overridden by MainWindow
    # after loading the current preset's theme preference.
    apply_theme(app, "system")

    # Install keyboard and mouse event filters if requested
    import os
    if os.environ.get("GMB_KEYBOARD") == "1":
        from .keyboard_bus import install_keyboard_filter
        install_keyboard_filter(app)
    if os.environ.get("GMB_MOUSE") == "1":
        from .mouse_bus import install_mouse_filter
        install_mouse_filter(app)

    icon_path = Path(__file__).parent / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Main-thread SDL event pump — needed for HIDAPI on macOS to actually
    # deliver HID reports for Bluetooth-paired controllers. SDL's HIDAPI
    # backend hooks IOHIDManager callbacks, which only fire on the thread
    # that initialized the video subsystem (the main thread). The bridge
    # worker calls pygame.event.pump() from its own QThread, but those
    # calls don't service the main-thread callbacks — so axes + buttons
    # stay frozen at attach time forever even though the controller shows
    # as connected. ~120Hz pump on the main thread fixes it.
    _sdl_pump_timer = QTimer()
    _sdl_pump_timer.setInterval(8)
    def _pump_sdl_events() -> None:
        try:
            import pygame
            if pygame.get_init():
                pygame.event.pump()
        except Exception:
            pass
    _sdl_pump_timer.timeout.connect(_pump_sdl_events)
    _sdl_pump_timer.start()

    win = MainWindow()
    # Keep the pump timer alive for the lifetime of the window.
    win._sdl_pump_timer = _sdl_pump_timer

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

    # ── UI smoke mode ────────────────────────────────────────────────
    # GMB_UI_SMOKE=<png path> shows the window, waits for layout to
    # settle, saves a screenshot and quits. Exists because the UI was
    # being changed blind: every verification went through the user
    # launching the app and describing what they saw, which is slow and
    # loses detail. MainWindow starts real timers and threads, so an
    # offscreen render that never returns is not an option — this quits
    # itself. See also GMB_UI_SMOKE's dialog suppression in main_window.
    _smoke_path = os.environ.get("GMB_UI_SMOKE")
    if _smoke_path:
        from PySide6.QtCore import QTimer as _QTimer

        def _grab_and_quit() -> None:
            try:
                if os.environ.get("GMB_UI_SMOKE_LEARN"):
                    btn = getattr(win, "_nodeview_btn", None)
                    if btn is not None:
                        btn.setChecked(True)
                        app.processEvents()
                if os.environ.get("GMB_UI_SMOKE_GEOM"):
                    def _dump(w, depth=0, name=""):
                        g = w.geometry()
                        print(f"[geom] {'  '*depth}{name or type(w).__name__} "
                              f"x={g.x()} y={g.y()} w={g.width()} h={g.height()} "
                              f"vis={w.isVisible()}")
                    for attr in ("_body_splitter", "_bottom_splitter",
                                 "_midi_log_panel", "_log_console"):
                        obj = getattr(win, attr, None)
                        if obj is not None:
                            _dump(obj, 0, attr)
                            for ch in obj.children():
                                if hasattr(ch, "geometry") and hasattr(ch, "isVisible"):
                                    _dump(ch, 1)
                win.grab().save(_smoke_path)
                print(f"[ui-smoke] saved {_smoke_path}")
            except Exception as exc:  # noqa: BLE001 — diagnostics only
                print(f"[ui-smoke] failed: {exc}")
            app.quit()

        _QTimer.singleShot(
            int(os.environ.get("GMB_UI_SMOKE_DELAY_MS", "1800")),
            _grab_and_quit,
        )

    # Hand control to Qt's event loop.
    run_loop = getattr(app, "exec")
    rc = run_loop()

    # Hard-exit the INSTANT the event loop ends — do NOT tear anything down.
    #
    # Every crash we've seen is Shiboken's destructionVisitor sweeping a Qt
    # wrapper (QSlider, QDoubleSpinBox, …) whose C++ side is being deleted —
    # a SIGSEGV in QObject::~QObject. ANY teardown triggers it: the old
    # ``win.deleteLater() + processEvents() + gc.collect()`` dance here did it
    # in-process, BEFORE the os._exit guards downstream could run; and letting
    # Python finalise does it too. MainWindow.closeEvent + autobackup's
    # mark_clean_shutdown already ran inside the loop, so nothing is left to
    # flush. A hard process exit skips all widget/wrapper destruction and
    # Python finalisers; the OS reclaims memory cleanly. This is the single
    # chokepoint every launch path funnels through, so it kills the whole class.
    import os as _os
    sys.stdout.flush()
    sys.stderr.flush()
    _os._exit(rc if rc is not None else 0)
