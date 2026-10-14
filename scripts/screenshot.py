#!/usr/bin/env python3
"""Offscreen screenshot harness — render the real MainWindow to a PNG without
a display, so design work can be eyeballed and iterated headlessly.

Why offscreen: this is a native Qt app, not a web page, so Playwright / browser
tools don't apply. ``QT_QPA_PLATFORM=offscreen`` builds the genuine widget tree
with the genuine styles.qss theme and grabs it to an image — deterministic, no
WindowServer needed, runs over SSH / CI.

Usage:
    .venv/bin/python scripts/screenshot.py --out /tmp/win.png
    .venv/bin/python scripts/screenshot.py --tab Visualise --size 1440x900 --out /tmp/vis.png
    .venv/bin/python scripts/screenshot.py --console --out /tmp/console.png
    .venv/bin/python scripts/screenshot.py --theme dark --tab Mapping --out /tmp/map.png

Notes:
- Demo input is forced on (GMB_DEMO=1) so no controller is required.
- Pass --tab with the visible tab label (Live, Visualise, Mapping, Templates,
  Presets, Nodes, ...). Matching is case-insensitive substring.
"""
from __future__ import annotations

import argparse
import os
import sys

# MUST be set before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GMB_DEMO", "1")

REPO_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if REPO_SRC not in sys.path:
    sys.path.insert(0, REPO_SRC)


def _settle(app, passes: int = 8) -> None:
    """Pump the event loop a few times so layouts compute real geometry."""
    for _ in range(passes):
        app.processEvents()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/gmb_shot.png")
    ap.add_argument("--size", default="1280x800", help="WxH")
    ap.add_argument("--tab", default=None, help="switch to this tab label before grabbing")
    ap.add_argument("--theme", default="system", choices=["system", "dark", "light"])
    ap.add_argument("--console", action="store_true", help="open the bottom log console")
    args = ap.parse_args()

    w, h = (int(x) for x in args.size.lower().split("x"))

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTabWidget
    from gamepad_midi_bridge.ui.theme import apply_theme

    # Neutralise every modal so construction never blocks offscreen:
    # crash-recovery prompt, onboarding wizard, error boxes, etc.
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QDialog.exec = lambda self, *a, **k: 0
    QDialog.exec_ = lambda self, *a, **k: 0

    from gamepad_midi_bridge.ui.main_window import MainWindow

    QCoreApplication.setApplicationName("Universal Controller MIDI")
    QCoreApplication.setOrganizationName("Aidxn Design")
    QCoreApplication.setOrganizationDomain("aidxn.com")

    app = QApplication([])
    apply_theme(app, args.theme)

    win = MainWindow()
    win.resize(w, h)
    _settle(app)

    if args.console and hasattr(win, "_log_console"):
        try:
            win._log_console.set_collapsed(False)
        except Exception as e:  # noqa: BLE001
            print(f"[screenshot] could not open console: {e}", file=sys.stderr)
        _settle(app)

    if args.tab:
        target = args.tab.lower()
        switched = False
        for tabw in win.findChildren(QTabWidget):
            for i in range(tabw.count()):
                if target in tabw.tabText(i).lower():
                    tabw.setCurrentIndex(i)
                    switched = True
                    break
            if switched:
                break
        if not switched:
            labels = [
                tabw.tabText(i)
                for tabw in win.findChildren(QTabWidget)
                for i in range(tabw.count())
            ]
            print(f"[screenshot] tab '{args.tab}' not found. Available: {labels}", file=sys.stderr)
        _settle(app)

    _settle(app, passes=4)
    pix = win.grab()
    ok = pix.save(args.out)
    print(f"[screenshot] {'saved' if ok else 'FAILED'} {args.out} ({pix.width()}x{pix.height()})")
    # Hard-exit to skip the PySide6/Shiboken teardown segfault path.
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    main()
