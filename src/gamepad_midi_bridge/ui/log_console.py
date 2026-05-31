"""Expandable log console — dock-style panel at the bottom of the main window.

Streams two parallel feeds:
    1. Python logging records (everything the app emits at INFO+)
    2. Bridge engine signals — controller events, MIDI dispatch, errors

Designed to be collapsible. QSplitter handles the sizing; the toggle button
in the header just calls `set_collapsed`. State persists across launches via
the config file so power users get their preferred layout back.

Tail-only design: we keep the last 2000 lines and drop the rest. Audio/MIDI
sessions can spit thousands of messages a minute; we don't want the GUI
locking up because someone left it running for two hours.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from ..paths import config_path


MAX_LINES = 2000
CONFIG_KEY = "log_console_open"


# Color per log level — applied as a prefix tag rather than rich text so we
# stay cheap (rich text + 100 lines/sec = janky GUI).
LEVEL_TAG = {
    logging.DEBUG:   "·",
    logging.INFO:    " ",
    logging.WARNING: "!",
    logging.ERROR:   "✕",
    logging.CRITICAL:"✕",
}


class _LogSignaller(QObject):
    """Bridge from the (possibly background-thread) logging handler to the GUI thread."""
    line = Signal(str, str)   # level_tag, formatted_text


class _GuiLogHandler(logging.Handler):
    """logging.Handler that emits a Qt signal per record."""

    def __init__(self, signaller: _LogSignaller) -> None:
        super().__init__()
        self._signaller = signaller

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            tag = LEVEL_TAG.get(record.levelno, " ")
            text = f"{ts} {record.name} | {record.getMessage()}"
            self._signaller.line.emit(tag, text)
        except Exception:
            # Never let logging crash the app.
            pass


class LogConsole(QWidget):
    """Collapsible bottom-of-window log console.

    Connect a BridgeWorker via `attach_bridge_signals(worker)` to mirror its
    activity into the console. Standard Python logging is always streamed
    once `install_root_handler()` has been called.
    """

    # Emitted on collapse/expand. MainWindow recomputes splitter sizes.
    collapse_changed = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._signaller = _LogSignaller()
        self._signaller.line.connect(self._append_line)
        self._handler = _GuiLogHandler(self._signaller)
        self._handler.setLevel(logging.INFO)

        self._collapsed = not _read_open_state()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_body(), 1)

        # Apply initial collapsed state without flashing the body.
        self._apply_collapsed()

    # ============================================================== public API

    def install_root_handler(self) -> None:
        """Attach the Qt-bridging handler to the root logger.

        Idempotent — safe to call multiple times; only one handler ever lands.
        Call this once from main_window.py after the console exists.
        """
        root = logging.getLogger()
        if self._handler not in root.handlers:
            root.addHandler(self._handler)
            # The app's main logger module configures the file handler; we
            # don't want to lower the root level if it's already INFO+.

    def attach_bridge_signals(self, worker) -> None:
        """Mirror BridgeWorker activity into the console."""
        worker.status.connect(lambda s: self._log("info", "bridge", s))
        worker.error.connect(lambda s: self._log("error", "bridge", s))
        worker.started.connect(
            lambda name, port: self._log("info", "bridge",
                                         f"started — {name} → {port}"))
        worker.stopped.connect(lambda: self._log("info", "bridge", "stopped"))
        worker.controller_info.connect(self._on_controller_info)
        worker.battery_changed.connect(self._on_battery)
        worker.transport_changed.connect(
            lambda wired: self._log("info", "bridge",
                                    "transport: USB" if wired else "transport: BT"))
        worker.corner_triggered.connect(
            lambda side, kind, sector: self._log(
                "info", "bridge", f"corner {side}{sector} {kind}"))

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._apply_collapsed()
        _write_open_state(not self._collapsed)
        self.collapse_changed.emit(self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._apply_collapsed()
        self.collapse_changed.emit(self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    # ============================================================== helpers

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            "background-color: #16181d; border-top: 1px solid #24262d;"
        )
        bar.setFixedHeight(30)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 2, 8, 2)
        h.setSpacing(8)

        title = QLabel("CONSOLE")
        title.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1px;"
        )
        h.addWidget(title)
        h.addStretch(1)

        clear = QPushButton("Clear")
        clear.setFlat(True)
        clear.setStyleSheet("color: #8a9099; font-size: 11px; padding: 2px 8px;")
        clear.clicked.connect(self.clear)
        h.addWidget(clear)

        self._toggle_btn = QPushButton("▾")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedWidth(28)
        self._toggle_btn.setStyleSheet(
            "color: #c2c6cc; font-size: 14px; padding: 0; margin: 0;"
        )
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        h.addWidget(self._toggle_btn)

        return bar

    def _build_body(self) -> QPlainTextEdit:
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setMaximumBlockCount(MAX_LINES)
        body.setFrameStyle(QFrame.NoFrame)
        body.setStyleSheet(
            "background-color: #0e0f12; color: #c2c6cc; "
            "selection-background-color: #1f3a36;"
        )
        font = QFont("SF Mono")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(11)
        body.setFont(font)
        self._body = body
        return body

    def _apply_collapsed(self) -> None:
        # NOTE: the parent ``QSplitter`` owns sizing — see
        # ``MainWindow._set_bottom_panel_sizes``. Self-imposed setMaximumHeight
        # fights the splitter's drag re-layout and causes flicker.
        self._toggle_btn.setText("▴" if self._collapsed else "▾")
        self._body.setVisible(not self._collapsed)

    def clear(self) -> None:
        self._body.clear()

    # ---- internal hooks ----------------------------------------------------

    def _append_line(self, tag: str, text: str) -> None:
        # appendPlainText handles maximumBlockCount trimming for us.
        self._body.appendPlainText(f"{tag} {text}")
        # Auto-scroll to the bottom if we're already near it (so scroll-back
        # doesn't get yanked away when new lines arrive).
        bar = self._body.verticalScrollBar()
        if bar.maximum() - bar.value() < 40:
            self._body.moveCursor(QTextCursor.End)

    def _log(self, level: str, source: str, message: str) -> None:
        levelno = {
            "debug": logging.DEBUG, "info": logging.INFO,
            "warning": logging.WARNING, "error": logging.ERROR,
        }.get(level, logging.INFO)
        record = logging.LogRecord(
            name=source, level=levelno, pathname="", lineno=0,
            msg=message, args=(), exc_info=None,
        )
        self._handler.emit(record)

    def _on_controller_info(self, info) -> None:
        if info is None:
            self._log("warning", "bridge", "no controller detected")
            return
        self._log("info", "bridge",
                  f"controller: {info.name} — {info.num_buttons}b, "
                  f"{info.num_axes}a, {info.num_hats}h")

    def _on_battery(self, percent: int, charging: bool, full: bool) -> None:
        flag = ""
        if charging:
            flag = " ⚡"
        elif full:
            flag = " ✓"
        self._log("info", "bridge", f"battery: {percent}%{flag}")


# ----------------------------------------------------------------- persistence


def _read_open_state() -> bool:
    """Was the console open last time? Default closed so first launch is calm."""
    path = config_path()
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get(CONFIG_KEY, False))
    except Exception:
        return False


def _write_open_state(open_: bool) -> None:
    path = config_path()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[CONFIG_KEY] = bool(open_)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
