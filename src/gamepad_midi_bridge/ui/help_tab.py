"""In-app Help tab — keyboard shortcuts, FAQ, troubleshooting, and links.

Lives next to About in the tabbed body. The point is to answer the obvious
"how do I…?" questions without forcing users out to the website. Shortcuts
declared here own their own QShortcut instances (ApplicationShortcut scope)
and emit signals back to MainWindow, so the cheat sheet in the UI always
reflects what is actually wired.
"""
from __future__ import annotations

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


CHANGELOG_URL = "https://store.aidxn.com/changelog"
ISSUES_URL = "https://github.com/aidenwood/gamepad-midi-bridge/issues"
SUPPORT_EMAIL = "support@aidxn.com"


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

    def __init__(self) -> None:
        super().__init__()
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

        title = QLabel("Help")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f7fa;")
        v.addWidget(title)

        sub = QLabel(
            "Answers to the questions we hear most. If something is missing, "
            "email support — we read every message."
        )
        sub.setStyleSheet("color: #8a9099;")
        sub.setWordWrap(True)
        v.addWidget(sub)

        v.addWidget(self._build_shortcuts_card())
        v.addWidget(self._build_faq_card())
        v.addWidget(self._build_troubleshooting_card())
        v.addWidget(self._build_links_card())

        v.addStretch(1)

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
