"""Auto-reconnect overlay widget.

Shown over the main window whenever the primary controller drops mid-session.
State machine:

  HIDDEN ──► COUNTING (on disconnect, if auto_reconnect_enabled)
  COUNTING ──► SUCCESS (controller_info non-None within timeout)
  COUNTING ──► FAILED  (30 s elapsed with no reconnect)
  SUCCESS  ──► HIDDEN  (after 2-second flash)
  FAILED   ──► COUNTING (user clicks Retry)
  COUNTING ──► HIDDEN  (user clicks Cancel / presses Esc)
  FAILED   ──► HIDDEN  (user clicks Cancel / presses Esc)

The widget is frameless and overlaid on top of its parent (MainWindow).  It
resizes itself in resizeEvent so it always fills the parent exactly.
"""
from __future__ import annotations

import logging
from enum import Enum, auto

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
    Signal,
    Qt,
)
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .accessibility import prefers_reduced_motion

_log = logging.getLogger(__name__)

# How many seconds before giving up entirely.
_TIMEOUT_SECS = 30
# How long to show the "RECONNECTED" success flash before hiding.
_SUCCESS_FLASH_MS = 2000
# Fade-out duration in ms.
_FADE_MS = 400


class _State(Enum):
    HIDDEN = auto()
    COUNTING = auto()
    SUCCESS = auto()
    FAILED = auto()


class ReconnectOverlay(QWidget):
    """Semi-transparent dark overlay with countdown + state transitions."""

    # Emitted when the user asks to cancel the reconnect loop early.
    cancel_requested = Signal()
    # Emitted when the user clicks Retry from the FAILED state.
    retry_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._state = _State.HIDDEN
        self._seconds_left = _TIMEOUT_SECS

        # ----- styling -----
        self.setObjectName("ReconnectOverlay")
        self.setStyleSheet(
            "QWidget#ReconnectOverlay {"
            "  background: rgba(10, 11, 14, 200);"
            "}"
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.hide()

        # ----- layout -----
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        inner = QVBoxLayout()
        inner.setSpacing(12)
        inner.setContentsMargins(32, 32, 32, 32)
        outer.addLayout(inner)

        self._title = QLabel("Controller lost")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet(
            "color: #f5f7fa; font-size: 26px; font-weight: 700;"
        )
        inner.addWidget(self._title)

        self._subtitle = QLabel("")
        self._subtitle.setAlignment(Qt.AlignCenter)
        self._subtitle.setStyleSheet(
            "color: #8a9099; font-size: 14px;"
        )
        inner.addWidget(self._subtitle)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setObjectName("PrimaryButton")
        self._retry_btn.setMinimumWidth(90)
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(self._on_retry)
        btn_row.addWidget(self._retry_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("StopButton")
        self._cancel_btn.setMinimumWidth(90)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch(1)
        inner.addLayout(btn_row)

        outer.addStretch(1)

        # ----- opacity animation for fade-out -----
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(_FADE_MS)
        self._fade_anim.setEasingCurve(QEasingCurve.OutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)

        # ----- countdown timer (1-second ticks) -----
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        # ----- success auto-hide timer -----
        self._success_timer = QTimer(self)
        self._success_timer.setSingleShot(True)
        self._success_timer.setInterval(_SUCCESS_FLASH_MS)
        self._success_timer.timeout.connect(self._begin_fade)

    # ---------------------------------------------------------------- public API

    def start_countdown(self) -> None:
        """Begin the reconnect countdown. Call when a disconnect is detected."""
        self._stop_timers()
        self._seconds_left = _TIMEOUT_SECS
        self._state = _State.COUNTING
        self._opacity_effect.setOpacity(1.0)
        self._fade_anim.stop()
        self._apply_counting_ui()
        self._resize_to_parent()
        self.show()
        self.raise_()
        self._tick_timer.start()
        _log.debug("ReconnectOverlay: countdown started")

    def notify_success(self) -> None:
        """Call when the bridge reconnects successfully."""
        if self._state not in (_State.COUNTING, _State.FAILED):
            return
        self._stop_timers()
        self._state = _State.SUCCESS
        self._apply_success_ui()
        self._success_timer.start()
        _log.debug("ReconnectOverlay: reconnected")

    def dismiss(self) -> None:
        """Programmatically hide — same effect as user pressing Cancel."""
        self._on_cancel()

    # ---------------------------------------------------------------- internal slots

    def _on_tick(self) -> None:
        self._seconds_left -= 1
        if self._seconds_left <= 0:
            self._stop_timers()
            self._state = _State.FAILED
            self._apply_failed_ui()
            _log.debug("ReconnectOverlay: timed out")
            return
        # Update subtitle with new countdown value
        self._subtitle.setText(f"Retrying in {self._seconds_left}s…")

    def _on_retry(self) -> None:
        self._seconds_left = _TIMEOUT_SECS
        self._state = _State.COUNTING
        self._apply_counting_ui()
        self._tick_timer.start()
        self.retry_requested.emit()

    def _on_cancel(self) -> None:
        self._stop_timers()
        self._state = _State.HIDDEN
        self.cancel_requested.emit()
        self._begin_fade()

    def _begin_fade(self) -> None:
        self._fade_anim.stop()
        if prefers_reduced_motion():
            # Skip animation; go straight to hidden
            self._opacity_effect.setOpacity(0.0)
            self._on_fade_finished()
        else:
            self._fade_anim.setStartValue(float(self._opacity_effect.opacity()))
            self._fade_anim.setEndValue(0.0)
            self._fade_anim.start()

    def _on_fade_finished(self) -> None:
        if self._opacity_effect.opacity() <= 0.01:
            self.hide()
            self._opacity_effect.setOpacity(1.0)

    def _stop_timers(self) -> None:
        self._tick_timer.stop()
        self._success_timer.stop()

    # ---------------------------------------------------------------- UI state

    def _apply_counting_ui(self) -> None:
        self._title.setText("Controller lost")
        self._title.setStyleSheet(
            "color: #f5f7fa; font-size: 26px; font-weight: 700;"
        )
        self._subtitle.setText(f"Retrying in {self._seconds_left}s…")
        self._subtitle.setStyleSheet("color: #8a9099; font-size: 14px;")
        self._retry_btn.setVisible(False)
        self._cancel_btn.setVisible(True)

    def _apply_success_ui(self) -> None:
        self._title.setText("✓  Reconnected")
        self._title.setStyleSheet(
            "color: #2dd4bf; font-size: 26px; font-weight: 700;"
        )
        self._subtitle.setText("")
        self._retry_btn.setVisible(False)
        self._cancel_btn.setVisible(False)

    def _apply_failed_ui(self) -> None:
        self._title.setText("✗  Connection failed")
        self._title.setStyleSheet(
            "color: #f59e0b; font-size: 26px; font-weight: 700;"
        )
        self._subtitle.setText(
            "Could not reconnect within 30 seconds."
        )
        self._subtitle.setStyleSheet("color: #8a9099; font-size: 14px;")
        self._retry_btn.setVisible(True)
        self._cancel_btn.setVisible(True)

    # ---------------------------------------------------------------- geometry

    def _resize_to_parent(self) -> None:
        if self.parent() is not None:
            self.setGeometry(self.parent().rect())

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._resize_to_parent()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        """Close overlay on Esc key."""
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
            event.accept()
        else:
            super().keyPressEvent(event)
