"""Render the main window in every tab to PNG via offscreen Qt.

Run on any platform that has a working Qt offscreen plugin (built into
PySide6). Output goes to docs/screenshots/. Used by the store landing
page and README — re-run after material UI changes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Force offscreen platform before any Qt imports so this script works
# in CI without a display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Make `src/` importable when run from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402


# Tabs we want a clean shot of, paired with the filename slug.
TABS = [
    ("Live", "live"),
    ("Visualise", "visualise"),
    ("Mapping", "mapping"),
    ("Templates", "templates"),
    ("Presets", "presets"),
    ("Marketplace", "marketplace"),
    ("Connectors", "connectors"),
    ("Bluetooth", "bluetooth"),
    ("Settings", "settings"),
    ("Help", "help"),
    ("About", "about"),
]

OUTPUT_DIR = ROOT / "docs" / "screenshots"
SHOT_SIZE = QSize(960, 720)


def main() -> int:
    # Reset any persisted mapping so screenshots show the default state
    # rather than whatever the dev was last poking at.
    from gamepad_midi_bridge.paths import last_mapping_path
    if last_mapping_path().exists():
        last_mapping_path().unlink()

    # Suppress the first-launch wizard so screenshots show the main UI.
    from gamepad_midi_bridge.ui.onboarding import mark_complete
    mark_complete()

    app = QApplication(sys.argv)
    # Apply the same stylesheet the live app uses so the screenshots show
    # the real dark theme.
    qss = ROOT / "src" / "gamepad_midi_bridge" / "ui" / "styles.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))

    from gamepad_midi_bridge.ui.main_window import MainWindow
    win = MainWindow()
    win.resize(960, 880)        # tall enough for the Settings stack
    win.show()
    # Let the layout do a full pass before we ask any tab to paint.
    for _ in range(5):
        app.processEvents()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tabs: QTabWidget = win.findChild(QTabWidget)
    if tabs is None:
        print("No QTabWidget found in MainWindow")
        return 1

    label_to_index = {tabs.tabText(i): i for i in range(tabs.count())}
    for label, slug in TABS:
        if label not in label_to_index:
            print(f"Skipping {label} — tab missing")
            continue
        tabs.setCurrentIndex(label_to_index[label])
        app.processEvents()
        # Let layout settle for the more expensive tabs (Marketplace fetch, etc).
        for _ in range(3):
            app.processEvents()
        pixmap: QPixmap = win.grab()
        out = OUTPUT_DIR / f"tab-{slug}.png"
        pixmap.save(str(out))
        print(f"Wrote {out.relative_to(ROOT)} ({pixmap.width()}x{pixmap.height()})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
