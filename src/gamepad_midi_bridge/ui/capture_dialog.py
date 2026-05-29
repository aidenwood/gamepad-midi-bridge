"""CaptureDialog — modal that listens to BridgeWorker signals and returns the
first matching input index.  Kind is one of "button" | "axis" | "hat".
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)


class CaptureDialog(QDialog):
    """Press-to-capture wizard modal.

    Opens over the mapping editor and waits for the user to press a controller
    input.  When a matching input is detected the dialog auto-closes with
    ``QDialog.Accepted`` and ``self.captured_index`` holds the raw index value:

    * ``"button"`` → ``int``  (button index, 0-based)
    * ``"axis"``   → ``int``  (axis index)
    * ``"hat"``    → ``str``  (direction string, e.g. ``"up"``)

    If *worker* is ``None`` the dialog still opens and allows cancellation;
    it just never auto-accepts (graceful degradation when the bridge hasn't
    started yet).
    """

    # Axis magnitude threshold — avoids triggering on minor stick drift.
    _AXIS_THRESHOLD = 0.5

    def __init__(self, worker, kind: str, parent=None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._kind = kind
        self.captured_index = None  # populated on accept

        self.setWindowTitle("Capture Input")
        self.setModal(True)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )
        self.setMinimumWidth(320)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 20)
        v.setSpacing(16)

        # Instruction label.
        if kind == "button":
            instruction = "Press any button on your controller."
        elif kind == "axis":
            instruction = "Move any stick or trigger past 50%."
        else:  # hat
            instruction = "Press any D-pad direction."

        instr = QLabel(instruction)
        instr.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f7fa;")
        instr.setWordWrap(True)
        instr.setAlignment(Qt.AlignCenter)
        v.addWidget(instr)

        # Live preview label.
        self._preview = QLabel("Waiting…")
        self._preview.setStyleSheet(
            "font-size: 12px; color: #8a9099; font-family: ui-monospace, Menlo, monospace;"
        )
        self._preview.setAlignment(Qt.AlignCenter)
        v.addWidget(self._preview)

        # Cancel button.
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setMinimumWidth(80)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        v.addLayout(btn_row)

        # Esc → reject.
        from PySide6.QtGui import QKeySequence, QShortcut
        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self.reject)

        # Connect worker signals.
        self._connect_worker()

    # ------------------------------------------------------------------ private

    def _connect_worker(self) -> None:
        if self._worker is None:
            return
        if self._kind == "button":
            self._worker.button_state.connect(self._on_button)
        elif self._kind == "axis":
            self._worker.axis_value.connect(self._on_axis)
        else:  # hat
            self._worker.hat_state.connect(self._on_hat)

    def _disconnect_worker(self) -> None:
        if self._worker is None:
            return
        try:
            if self._kind == "button":
                self._worker.button_state.disconnect(self._on_button)
            elif self._kind == "axis":
                self._worker.axis_value.disconnect(self._on_axis)
            else:
                self._worker.hat_state.disconnect(self._on_hat)
        except RuntimeError:
            # Already disconnected — safe to ignore.
            pass

    def _capture(self, index, label: str) -> None:
        """Store the captured value, update the preview, then close."""
        self.captured_index = index
        self._preview.setText(f"Captured: {label}")
        # Brief flash so the user sees the result before the dialog closes.
        QTimer.singleShot(300, self.accept)

    # ------------------------------------------------------------------ slots

    def _on_button(self, idx: int, pressed: bool) -> None:
        if not pressed:
            return
        self._disconnect_worker()
        self._capture(idx, f"Button {idx}")

    def _on_axis(self, idx: int, value: float) -> None:
        if abs(value) < self._AXIS_THRESHOLD:
            return
        self._disconnect_worker()
        self._capture(idx, f"Axis {idx}")

    def _on_hat(self, direction: str, active: bool) -> None:
        if not active:
            return
        self._disconnect_worker()
        self._capture(direction, f"D-pad {direction}")

    # ------------------------------------------------------------------ overrides

    def accept(self) -> None:
        self._disconnect_worker()
        super().accept()

    def reject(self) -> None:
        self._disconnect_worker()
        super().reject()
