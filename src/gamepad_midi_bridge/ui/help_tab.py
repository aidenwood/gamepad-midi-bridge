"""In-app Help tab — keyboard shortcuts, FAQ, troubleshooting, and links.

Lives next to About in the tabbed body. The point is to answer the obvious
"how do I…?" questions without forcing users out to the website. Shortcuts
declared here own their own QShortcut instances (ApplicationShortcut scope)
and emit signals back to MainWindow, so the cheat sheet in the UI always
reflects what is actually wired.
"""
from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Callable, List, Tuple

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from ..crash_reporter import crash_dir
from ..logger import log_path
from ..paths import user_data_dir
from ..updater import UpdateChecker

# 3D logo widget — optional. QtWebEngineWidgets isn't a hard dep on every
# build platform; wrap the import so a missing module doesn't take the
# whole Help tab down.
try:
    from .logo_view_3d import Logo3DView
    _LOGO_3D_AVAILABLE = True
except Exception:
    Logo3DView = None  # type: ignore[assignment]
    _LOGO_3D_AVAILABLE = False


CHANGELOG_URL = "https://store.aidxn.com/changelog"
ISSUES_URL = "https://github.com/aidenwood/gamepad-midi-bridge/issues"
SUPPORT_EMAIL = "support@aidxn.com"

DOCS_LINKS = {
    "Getting started": "https://store.aidxn.com/docs/getting-started",
    "Connect a controller": "https://store.aidxn.com/docs/connect-controller",
    "Map your first preset": "https://store.aidxn.com/docs/map-preset",
    "Stage performance tips": "https://store.aidxn.com/docs/stage-performance",
    "Troubleshoot Bluetooth": "https://store.aidxn.com/docs/troubleshoot-bluetooth",
}


# Card chrome reused across all sections. Keeping the colours inline (rather
# than in styles.qss) avoids leaking a generic "Card" object name that other
# tabs might collide with.
_CARD_STYLE = (
    "QFrame#HelpCard {"
    "  background-color: #16181d;"
    "  border: 1px solid #24262d;"
    "  border-radius: 10px;"
    "}"
)


def _section_title(text: str) -> QLabel:
    """Small uppercase label used as a section heading inside a card."""
    label = QLabel(text)
    label.setStyleSheet(
        "color: #8a9099; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
    )
    return label


def _make_card() -> Tuple[QFrame, QVBoxLayout]:
    """Build an empty styled card frame and return (frame, inner_layout)."""
    card = QFrame()
    card.setObjectName("HelpCard")
    card.setStyleSheet(_CARD_STYLE)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(10)
    return card, layout


class _FaqItem(QFrame):
    """Click-to-expand FAQ row. Uses a flat button as the header so the whole
    row reacts to a click without us having to swap in a custom mouse handler."""

    def __init__(self, question: str, answer: str) -> None:
        super().__init__()
        self.setStyleSheet(
            "QFrame { background-color: #11131a; border: 1px solid #1f232b;"
            " border-radius: 8px; }"
        )

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._toggle = QPushButton(self._format_header(question, expanded=False))
        self._toggle.setFlat(True)
        self._toggle.setCursor(Qt.PointingHandCursor)
        self._toggle.setStyleSheet(
            "QPushButton { text-align: left; padding: 12px 14px;"
            " background: transparent; border: none; color: #e6e8eb;"
            " font-weight: 500; }"
            "QPushButton:hover { color: #2dd4bf; }"
        )
        self._toggle.clicked.connect(self._on_toggle)
        v.addWidget(self._toggle)

        self._answer = QLabel(answer)
        self._answer.setWordWrap(True)
        self._answer.setStyleSheet(
            "color: #c2c6cc; padding: 0 14px 14px 14px; font-size: 12px;"
        )
        self._answer.setVisible(False)
        v.addWidget(self._answer)

        self._question = question

    @staticmethod
    def _format_header(question: str, expanded: bool) -> str:
        # Caret stays in the same gutter so adjacent rows align visually.
        caret = "−" if expanded else "+"
        return f"  {caret}   {question}"

    def _on_toggle(self) -> None:
        expanded = not self._answer.isVisible()
        self._answer.setVisible(expanded)
        self._toggle.setText(self._format_header(self._question, expanded))


class HelpTab(QWidget):
    """Self-contained help surface. Emits signals for actions that MainWindow
    already knows how to perform, so we never reach across UI boundaries."""

    # MainWindow wires these up — keeping the coupling one-way means HelpTab
    # can be unit-tested without instantiating the full app.
    toggle_bridge_requested = Signal()
    quit_requested = Signal()
    open_settings_requested = Signal()
    hide_window_requested = Signal()
    recalibrate_requested = Signal()
    run_test_wizard_requested = Signal()
    run_latency_test_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._updater: UpdateChecker | None = None
        self._build_ui()
        self._install_shortcuts()

    # ============================================================== ui

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(28, 28, 28, 28)
        v.setSpacing(18)

        # Hero row: title + sub on the left, rotating 3D logo on the right
        # (when WebEngine is available). Falls back to title-only otherwise.
        hero = QHBoxLayout()
        hero.setContentsMargins(0, 0, 0, 0)
        hero.setSpacing(20)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(8)
        title = QLabel("Help")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f7fa;")
        hero_text.addWidget(title)
        sub = QLabel(
            "Answers to the questions we hear most. If something is missing, "
            "email support — we read every message."
        )
        sub.setStyleSheet("color: #8a9099;")
        sub.setWordWrap(True)
        hero_text.addWidget(sub)
        hero_text.addStretch(1)
        hero.addLayout(hero_text, stretch=1)

        if _LOGO_3D_AVAILABLE and Logo3DView is not None:
            try:
                self._logo3d = Logo3DView()
                self._logo3d.setFixedSize(220, 200)
                self._logo3d.setStyleSheet("background: transparent; border: 0;")
                hero.addWidget(self._logo3d, alignment=Qt.AlignTop | Qt.AlignRight)
            except Exception:
                # Widget construction can fail on systems where QtWebEngine
                # is present but the Chromium runtime isn't initialised yet
                # (e.g. running before QApplication is fully set up). Quietly
                # skip — the rest of the Help tab still renders.
                self._logo3d = None

        v.addLayout(hero)

        v.addWidget(self._build_quick_links_card())
        v.addWidget(self._build_shortcuts_card())
        v.addWidget(self._build_faq_card())
        v.addWidget(self._build_troubleshooting_card())
        v.addWidget(self._build_links_card())
        v.addWidget(self._build_actions_card())
        v.addWidget(self._build_version_card())

        v.addStretch(1)

    def _build_quick_links_card(self) -> QFrame:
        card, layout = _make_card()
        layout.addWidget(_section_title("QUICK LINKS"))

        # 5 doc links as a grid (2x3)
        grid = QHBoxLayout()
        grid.setSpacing(10)
        for i, (label, url) in enumerate(DOCS_LINKS.items()):
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, u=url: webbrowser.open(u))
            btn.setStyleSheet(
                "QPushButton { "
                "  background-color: #11131a; border: 1px solid #1f232b; "
                "  border-radius: 6px; padding: 8px 12px; color: #e6e8eb; "
                "  font-size: 11px; "
                "} "
                "QPushButton:hover { background-color: #16181d; border-color: #2dd4bf; }"
            )
            grid.addWidget(btn)
            if (i + 1) % 3 == 0:
                layout.addLayout(grid)
                grid = QHBoxLayout()
                grid.setSpacing(10)
        # Add remaining buttons if any
        if (len(DOCS_LINKS) % 3) != 0:
            grid.addStretch(1)
            layout.addLayout(grid)

        return card

    def _build_shortcuts_card(self) -> QFrame:
        card, layout = _make_card()
        layout.addWidget(_section_title("KEYBOARD SHORTCUTS"))

        rows: List[Tuple[str, str]] = [
            (self._mod_label("Enter"), "Toggle bridging from any tab"),
            (self._mod_label("Q"), "Quit"),
            (self._mod_label(","), "Open Settings"),
            (self._mod_label("W"), "Hide window (background to tray)"),
            (self._mod_label("R"), "Re-calibrate sticks"),
        ]
        for combo, action in rows:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(14)

            key_label = QLabel(combo)
            key_label.setStyleSheet(
                "color: #2dd4bf; font-family: 'SF Mono', Menlo, Consolas, monospace;"
                " font-size: 12px; background: #11131a; border: 1px solid #1f232b;"
                " border-radius: 4px; padding: 4px 8px;"
            )
            key_label.setMinimumWidth(140)
            key_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            row.addWidget(key_label)

            desc = QLabel(action)
            desc.setStyleSheet("color: #e6e8eb;")
            desc.setWordWrap(True)
            row.addWidget(desc, 1)

            layout.addLayout(row)
        return card

    def _build_faq_card(self) -> QFrame:
        card, layout = _make_card()
        layout.addWidget(_section_title("FAQ"))

        entries: List[Tuple[str, str]] = [
            (
                "Where does the virtual MIDI port appear?",
                "On macOS and Linux, anything subscribing to the IAC/ALSA bus "
                "sees it instantly. On Windows you'll need loopMIDI installed "
                "once; the bridge will detect it.",
            ),
            (
                "Why are some features greyed out?",
                "Those are Pro features. Unlock them via Settings → About → "
                "Upgrade to Pro, or paste a license key in About → Enter "
                "license key.",
            ),
            (
                "Does my controller need to be plugged in over USB?",
                "Bluetooth works for input + battery + touchpad. Adaptive "
                "trigger haptics require USB on Windows/Linux; macOS routes "
                "through Apple's GameController framework on either bus.",
            ),
            (
                "What if my stick still drifts after calibration?",
                "Auto-calibration fixes a fixed-offset drift. If your sticks "
                "jitter around at rest, the hardware is worn and needs "
                "physical repair — software can't help.",
            ),
            (
                "Can I run the bridge without the GUI?",
                "Yes: `gamepad-midi-bridge --headless` from a terminal. The "
                "last-used mapping is loaded automatically.",
            ),
        ]
        for q, a in entries:
            layout.addWidget(_FaqItem(q, a))
        return card

    def _build_troubleshooting_card(self) -> QFrame:
        card, layout = _make_card()
        layout.addWidget(_section_title("TROUBLESHOOTING"))

        bullets: List[str] = [
            "Controller not detected? Quit, reconnect, relaunch. Pygame can "
            "miss hot-plugs on macOS.",
            "No sound from your DAW? Check the DAW's MIDI input enable list "
            "— virtual ports are off by default in Ableton.",
            "Adaptive triggers not feeling anything on macOS? Install "
            "`pyobjc-framework-GameController` in your Python env.",
            "Bridge crashed? Find the report in "
            "`~/Library/Application Support/Universal Controller MIDI/crashes/` "
            "(mac) or equivalent on your OS — attach when filing a bug.",
        ]
        for text in bullets:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            dot = QLabel("•")
            dot.setStyleSheet("color: #2dd4bf; font-size: 14px;")
            dot.setAlignment(Qt.AlignTop)
            row.addWidget(dot)
            body = QLabel(text)
            body.setWordWrap(True)
            body.setStyleSheet("color: #c2c6cc; font-size: 12px;")
            row.addWidget(body, 1)
            layout.addLayout(row)
        return card

    def _build_links_card(self) -> QFrame:
        card, layout = _make_card()
        layout.addWidget(_section_title("LINKS"))

        note = QLabel(
            "Logs and crash reports help us diagnose tricky issues — attach "
            "them when emailing support."
        )
        note.setStyleSheet("color: #8a9099; font-size: 12px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self._link_button(
            "Open log file", lambda: self._reveal_path(log_path())
        ))
        row1.addWidget(self._link_button(
            "Open crash folder", lambda: self._reveal_path(crash_dir())
        ))
        row1.addStretch(1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(self._link_button(
            "Release notes", lambda: webbrowser.open(CHANGELOG_URL)
        ))
        row2.addWidget(self._link_button(
            "Email support", self._open_support_mail
        ))
        row2.addWidget(self._link_button(
            "GitHub issues", lambda: webbrowser.open(ISSUES_URL)
        ))
        row2.addStretch(1)
        layout.addLayout(row2)

        return card

    def _build_actions_card(self) -> QFrame:
        card, layout = _make_card()
        layout.addWidget(_section_title("ACTIONS"))

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self._link_button(
            "Open user data folder", self._open_user_data_folder
        ))
        row1.addWidget(self._link_button(
            "Open log file", lambda: self._open_log_file()
        ))
        row1.addStretch(1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(self._link_button(
            "Run controller test wizard", lambda: self.run_test_wizard_requested.emit()
        ))
        row2.addWidget(self._link_button(
            "Run latency test", lambda: self.run_latency_test_requested.emit()
        ))
        row2.addWidget(self._link_button(
            "Check for updates", self._check_for_updates
        ))
        row2.addStretch(1)
        layout.addLayout(row2)

        return card

    def _build_version_card(self) -> QFrame:
        card, layout = _make_card()
        layout.addWidget(_section_title("VERSION INFO"))

        import platform
        from PySide6 import __version__ as pyside_version

        rows: List[Tuple[str, str]] = [
            ("App version", __version__),
            ("Python", f"{sys.version.split()[0]}"),
            ("Qt", pyside_version),
            ("Platform", platform.platform().split("-")[0]),
        ]
        for label, value in rows:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(14)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #8a9099; font-weight: 500; min-width: 100px;")
            row.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet("color: #e6e8eb; font-family: 'SF Mono', Menlo, Consolas, monospace;")
            row.addWidget(val)
            row.addStretch(1)
            layout.addLayout(row)

        return card

    def _link_button(self, text: str, handler: Callable[[], None]) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(handler)
        return btn

    # ============================================================== shortcuts

    def _install_shortcuts(self) -> None:
        """Register application-scope shortcuts. Each one emits a signal so
        MainWindow keeps full authority over what 'quit' or 'open settings'
        actually mean. Cmd+Enter is already wired in MainWindow; we mirror it
        here so the cheat-sheet description and the live binding stay in sync
        — Qt happily fires both, the bridge toggle is idempotent enough that
        the duplicate is harmless."""
        bindings: List[Tuple[str, Signal]] = [
            ("Ctrl+Return", self.toggle_bridge_requested),
            ("Ctrl+Q", self.quit_requested),
            ("Ctrl+,", self.open_settings_requested),
            ("Ctrl+W", self.hide_window_requested),
            ("Ctrl+R", self.recalibrate_requested),
        ]
        self._shortcuts: List[QShortcut] = []
        for sequence, signal in bindings:
            sc = QShortcut(QKeySequence(sequence), self)
            sc.setContext(Qt.ApplicationShortcut)
            # Lambdas capture `signal` by default-arg trick to avoid late binding.
            sc.activated.connect(lambda s=signal: s.emit())
            self._shortcuts.append(sc)

    # ============================================================== helpers

    @staticmethod
    def _mod_label(key: str) -> str:
        """Render the modifier the way each platform's users actually read it.
        Qt's `Ctrl` already maps to ⌘ on macOS at the keybinding layer; this is
        purely cosmetic for the cheat sheet."""
        import sys
        if sys.platform == "darwin":
            return f"⌘ + {key}"
        return f"Ctrl + {key}"

    @staticmethod
    def _reveal_path(path: Path) -> None:
        """Open a file or folder in the OS file manager. Falls back to opening
        the parent directory if the target file does not exist yet (fresh
        installs won't have a log written until the first session)."""
        target = path if path.exists() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    @staticmethod
    def _open_support_mail() -> None:
        subject = f"{APP_NAME} - v{__version__}"
        # `webbrowser.open` handles mailto: on every platform we ship to.
        webbrowser.open(f"mailto:{SUPPORT_EMAIL}?subject={subject}")

    @staticmethod
    def _open_user_data_folder() -> bool:
        """Open the user data directory in the system file manager.
        Returns True on success, False on failure."""
        try:
            path = str(user_data_dir())
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            return False

    @staticmethod
    def _open_log_file() -> bool:
        """Open the log file in the system default text editor.
        Returns True on success, False on failure."""
        try:
            path = log_path()
            # If log doesn't exist, open parent folder instead
            if not path.exists():
                if sys.platform == "darwin":
                    subprocess.Popen(["open", str(path.parent)])
                elif sys.platform == "win32":
                    os.startfile(str(path.parent))
                else:
                    subprocess.Popen(["xdg-open", str(path.parent)])
                return True

            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            elif sys.platform == "win32":
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
            return True
        except Exception:
            return False

    def _check_for_updates(self) -> None:
        """Manually trigger an update check."""
        try:
            if self._updater is None:
                self._updater = UpdateChecker()
            self._updater.check()
        except Exception:
            # If UpdateChecker fails to instantiate or check, just open the
            # changelog URL so user can check manually.
            webbrowser.open(CHANGELOG_URL)
