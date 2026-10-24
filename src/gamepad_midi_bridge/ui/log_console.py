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

from .panel_metrics import HEADER_MIN_PX, header_height_for


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


# Severity bucket per level tag, used to colour the status-bar Console
# button so an error is visible WITHOUT the console being open. Customers
# were sending screen recordings instead of the log because nothing on
# screen told them the console had anything worth reading.
TAG_SEVERITY = {
    "·": "info",
    " ": "info",
    "!": "warning",
    "✕": "error",
}
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


class _ClickableFrame(QFrame):
    """QFrame that emits ``clicked`` when its bare surface is released.

    Clicks on child widgets (Clear button, ▾ toggle, etc.) are consumed by
    those widgets first and never reach ``mouseReleaseEvent`` here — so the
    bar can be a click target without stealing events from its own buttons.
    """
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


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
    # Emitted per appended line with its severity ("info"/"warning"/"error").
    # MainWindow uses it to pulse + colour the status-bar Console button.
    activity = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._signaller = _LogSignaller()
        self._signaller.line.connect(self._append_line)
        self._handler = _GuiLogHandler(self._signaller)
        self._handler.setLevel(logging.INFO)

        self._collapsed = not _read_open_state()
        self._unseen_severity: Optional[str] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_body(), 1)
        # Same top-pin as MidiLogPanel — see the note there.
        outer.addStretch(0)

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

    def set_collapsed_silent(self, collapsed: bool) -> None:
        """Match collapse state to a live splitter drag WITHOUT emitting
        collapse_changed. Emitting would re-run the splitter's snap-to-fixed-size
        and undo the drag — so dragging a collapsed panel open would show an
        empty centred header instead of the body. This shows/hides the body to
        track the drag and persists the new open-state."""
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._apply_collapsed()
        _write_open_state(not self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_compact(self, compact: bool) -> None:
        """Narrow-pane presentation of the header — mirrors MidiLogPanel.

        Nothing is removed: "Clear" keeps its slot and its action, it just
        loses the word, so the control is still one click away at any width.
        """
        compact = bool(compact)
        if compact == getattr(self, "_compact", None):
            return
        self._compact = compact
        self._clear_btn.setText("✕" if compact else "Clear")
        self._clear_btn.setToolTip("Clear the console")
        self.refresh_header_height()
        # See MidiLogPanel.set_compact — a cached layout minimum would keep
        # the old, wider floor and the compaction would buy no width.
        self._header_bar.layout().invalidate()
        if self.layout() is not None:
            self.layout().invalidate()
        self.updateGeometry()

    # ============================================================== helpers

    def _build_header(self) -> QFrame:
        bar = _ClickableFrame()
        # No border-top — the QSplitter handle above us is the visual divider.
        # Styling lives in styles.qss → "BOTTOM CONSOLE PANEL HEADER".
        bar.setObjectName("LogConsoleHeader")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        # Height is set at the END of this method from the populated
        # layout's own sizeHint — a hardcoded 36 clips the title once the
        # A+/A- buttons scale the app font. See panel_metrics.
        self._header_bar = bar
        bar.setCursor(Qt.PointingHandCursor)
        # Click anywhere on the header (not on a child button) to toggle.
        # Doubles the toggle target — the small ▾ arrow alone is too easy to
        # miss with a controller in your other hand.
        bar.clicked.connect(self.toggle_collapsed)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 5, 8, 5)
        h.setSpacing(8)

        title = QLabel("CONSOLE")
        title.setObjectName("LogConsoleTitle")
        title.setMinimumHeight(20)
        self._header_title = title
        h.addWidget(title)
        h.addStretch(1)

        clear = QPushButton("Clear")
        clear.setObjectName("LogConsoleClearButton")
        clear.setFlat(True)
        clear.setFixedHeight(26)
        clear.clicked.connect(self.clear)
        self._clear_btn = clear
        h.addWidget(clear)

        self._toggle_btn = QPushButton("▾")
        self._toggle_btn.setObjectName("LogConsoleToggleButton")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedSize(28, 26)
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        h.addWidget(self._toggle_btn)

        bar.setFixedHeight(header_height_for(title, h))
        return bar

    def _build_body(self) -> QPlainTextEdit:
        body = QPlainTextEdit()
        body.setObjectName("LogConsoleBody")
        body.setReadOnly(True)
        body.setMaximumBlockCount(MAX_LINES)
        body.setFrameStyle(QFrame.NoFrame)
        font = QFont("SF Mono")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(11)
        body.setFont(font)
        self._body = body
        return body

    def header_height(self) -> int:
        """Current header height in px — the collapsed height of this panel.

        MainWindow sizes the bottom splitter from this instead of a hardcoded
        36 so the header can never be clipped at a larger font scale.
        """
        bar = getattr(self, "_header_bar", None)
        return bar.height() if bar is not None else HEADER_MIN_PX

    def refresh_header_height(self) -> None:
        """Re-measure after a font-scale change so the header still fits."""
        bar = getattr(self, "_header_bar", None)
        title = getattr(self, "_header_title", None)
        if bar is not None and title is not None:
            bar.setFixedHeight(header_height_for(title, bar.layout()))
        self.setMinimumHeight(self.header_height())

    def _apply_collapsed(self) -> None:
        # NOTE: the parent ``QSplitter`` owns sizing — see
        # ``MainWindow._set_bottom_panel_sizes``. Self-imposed setMaximumHeight
        # fights the splitter's drag re-layout and causes flicker.
        self._toggle_btn.setText("▴" if self._collapsed else "▾")
        self._body.setVisible(not self._collapsed)
        if not self._collapsed:
            # Opening the console counts as reading it.
            self._unseen_severity = None

    def clear(self) -> None:
        self._body.clear()

    # ---- internal hooks ----------------------------------------------------

    def highest_unseen_severity(self) -> Optional[str]:
        """Worst severity logged since the console was last opened, or None."""
        return self._unseen_severity

    def clear_unseen(self) -> None:
        """Forget the unseen-severity high-water mark (console was read)."""
        self._unseen_severity = None

    def _note_severity(self, tag: str) -> str:
        severity = TAG_SEVERITY.get(tag, "info")
        # Only track a high-water mark while collapsed — if the panel is open
        # the user is already looking at the lines.
        if self._collapsed:
            current = self._unseen_severity
            if current is None or SEVERITY_RANK[severity] > SEVERITY_RANK[current]:
                self._unseen_severity = severity
        return severity

    def _append_line(self, tag: str, text: str) -> None:
        # appendPlainText handles maximumBlockCount trimming for us.
        self._body.appendPlainText(f"{tag} {text}")
        self.activity.emit(self._note_severity(tag))
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
