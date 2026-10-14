"""Crash dialog — the thing the user actually sees when the app dies.

Before this existed, an unhandled exception wrote a report to
``user_data_dir/crashes/`` and that was it. On Windows that is invisible:
``build.py`` passes ``--noconsole``, so PyInstaller sets ``sys.stdout`` and
``sys.stderr`` to ``None`` and the "Crash report saved to ..." line in
``crash_reporter.install_hook`` goes nowhere. The app just vanishes and the
user has nothing to send us.

This module shows a modal dialog with the full traceback in a selectable box
plus three ways to get it to us:

  * **Email developer** — opens the user's mail client with the report
    pre-filled, addressed to ``SUPPORT_EMAIL``.
  * **Copy details** — the whole report onto the clipboard.
  * **Open crash folder** — reveals the ``.txt`` for drag-and-drop.

Qt is imported lazily by the caller (``crash_reporter.install_hook``) so the
headless and CLI paths never pay for it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .help_tab import SUPPORT_EMAIL

# Windows caps a `mailto:` URL at roughly 2 KB — anything longer and the shell
# silently refuses to open the mail client, which looks to the user exactly
# like the button is broken. Budget well under that and point at the on-disk
# file for the rest.
_MAILTO_BODY_LIMIT = 1400


def _mailto_url(report_text: str, report_path: Path | None, version: str) -> QUrl:
    """Build a `mailto:` for SUPPORT_EMAIL with a truncated report inline."""
    body_head = (
        "Hi - Universal Controller MIDI crashed. Details below.\n\n"
        "What I was doing when it happened:\n"
        "  (anything you can tell us here helps - feel free to delete this line)\n\n"
    )

    trimmed = report_text
    if len(trimmed) > _MAILTO_BODY_LIMIT:
        trimmed = trimmed[:_MAILTO_BODY_LIMIT] + "\n... (truncated)"

    body_tail = ""
    if report_path is not None:
        body_tail = f"\n\nFull report file (attach it if you can):\n{report_path}\n"

    body = body_head + "----- crash report -----\n" + trimmed + body_tail
    subject = f"Universal Controller MIDI crash - v{version}"
    return QUrl(
        f"mailto:{SUPPORT_EMAIL}"
        f"?subject={quote(subject)}"
        f"&body={quote(body)}"
    )


class CrashDialog(QDialog):
    """Modal "it crashed, here's how to tell us" window."""

    def __init__(
        self,
        report_text: str,
        report_path: Path | None,
        version: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._report_text = report_text
        self._report_path = report_path
        self._version = version

        self.setWindowTitle("Universal Controller MIDI - crash")
        self.setMinimumSize(640, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        headline = QLabel("Universal Controller MIDI hit an error and has to close.")
        headline_font = headline.font()
        headline_font.setPointSize(headline_font.pointSize() + 3)
        headline_font.setBold(True)
        headline.setFont(headline_font)
        headline.setWordWrap(True)
        layout.addWidget(headline)

        blurb = QLabel(
            "Sorry about that. The details below tell us exactly what went wrong - "
            "send them over and we'll fix it. Nothing is sent anywhere automatically."
        )
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        details = QPlainTextEdit(report_text)
        details.setReadOnly(True)
        details.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFont("Menlo" if sys.platform == "darwin" else "Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)
        details.setFont(mono)
        layout.addWidget(details, stretch=1)

        if report_path is not None:
            saved = QLabel(f"Saved to: {report_path}")
            saved.setWordWrap(True)
            layout.addWidget(saved)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        email_btn = QPushButton(f"Email developer ({SUPPORT_EMAIL})")
        email_btn.setDefault(True)
        email_btn.clicked.connect(self._on_email)
        buttons.addWidget(email_btn)

        copy_btn = QPushButton("Copy details")
        copy_btn.clicked.connect(self._on_copy)
        buttons.addWidget(copy_btn)

        if report_path is not None:
            folder_btn = QPushButton("Open crash folder")
            folder_btn.clicked.connect(self._on_open_folder)
            buttons.addWidget(folder_btn)

        buttons.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)

        layout.addLayout(buttons)

        self._copy_btn = copy_btn

    # ---- button handlers -------------------------------------------------

    def _on_email(self) -> None:
        url = _mailto_url(self._report_text, self._report_path, self._version)
        opened = QDesktopServices.openUrl(url)
        if not opened:
            # No mail client registered (common on a fresh Windows install).
            # Copying is the next best thing - tell them where to send it.
            self._on_copy()
            self._copy_btn.setText(f"Copied - email it to {SUPPORT_EMAIL}")

    def _on_copy(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._report_text)
            self._copy_btn.setText("Copied")

    def _on_open_folder(self) -> None:
        if self._report_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._report_path.parent)))


def show_crash_dialog(
    report_text: str,
    report_path: Path | None,
    version: str,
) -> None:
    """Show the dialog, creating a QApplication if the crash beat Qt to it.

    Safe to call from ``sys.excepthook``: every failure mode here is swallowed
    by the caller, because a crash handler that crashes helps nobody.
    """
    app = QApplication.instance()
    owns_app = False
    if app is None:
        # The exception fired before (or during) QApplication construction -
        # the exact case for a Windows launch failure. Build a throwaway one
        # purely to host the dialog.
        app = QApplication(sys.argv[:1])
        owns_app = True

    dialog = CrashDialog(report_text, report_path, version)
    dialog.exec()

    if owns_app:
        app.quit()
