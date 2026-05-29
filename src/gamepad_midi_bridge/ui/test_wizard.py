"""Controller test wizard — walks user through button/axis/hat validation."""
from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
    QScrollArea, QFrame,
)
from PySide6.QtGui import QFont, QColor

_log = logging.getLogger(__name__)


class ControllerTestWizard(QDialog):
    """Multi-step wizard to validate all inputs on first-time controller connect."""

    wizard_complete = Signal(list)  # Emits list of missing inputs

    def __init__(
        self,
        controller_info,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Controller Test Wizard")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        self._controller_info = controller_info
        self._received_inputs: set[str] = set()
        self._missing_inputs: List[str] = []

        # Build step list: buttons, axes, hats
        self._steps = []
        for i in range(controller_info.num_buttons):
            self._steps.append(("button", i, f"Button {i}"))
        for i in range(controller_info.num_axes):
            self._steps.append(("axis", i, f"Axis {i}"))
        for i in range(controller_info.num_hats):
            self._steps.append(("hat", i, f"Hat {i}"))

        self._current_step_idx = 0

        # Layout
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(16)

        # Title
        title = QLabel("Test Your Controller")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #f5f7fa;")
        v.addWidget(title)

        # Subtitle
        sub = QLabel(f"Connected: {controller_info.name}")
        sub.setStyleSheet("color: #8a9099;")
        v.addWidget(sub)

        # Progress
        self._progress = QLabel()
        self._progress.setStyleSheet("color: #8a9099; padding: 8px 0;")
        v.addWidget(self._progress)

        # Current step display
        step_frame = QFrame()
        step_frame.setStyleSheet(
            "QFrame { border: 1px solid #4a4f59; border-radius: 6px; padding: 16px; }"
        )
        step_layout = QVBoxLayout(step_frame)
        step_layout.setContentsMargins(0, 0, 0, 0)

        self._step_label = QLabel()
        step_font = QFont()
        step_font.setPointSize(14)
        step_font.setBold(True)
        self._step_label.setFont(step_font)
        self._step_label.setStyleSheet("color: #f5f7fa;")
        step_layout.addWidget(self._step_label)

        self._step_checkmark = QLabel()
        self._step_checkmark.setStyleSheet("color: #4ade80; font-size: 20px;")
        step_layout.addWidget(self._step_checkmark, alignment=Qt.AlignCenter)

        v.addWidget(step_frame, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._skip_btn = QPushButton("Skip This")
        self._skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(self._skip_btn)

        btn_layout.addStretch()

        self._next_btn = QPushButton("Waiting…")
        self._next_btn.setObjectName("PrimaryButton")
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._on_next)
        btn_layout.addWidget(self._next_btn)

        self._finish_btn = QPushButton("Finish & Save")
        self._finish_btn.setObjectName("PrimaryButton")
        self._finish_btn.setEnabled(False)
        self._finish_btn.setVisible(False)
        self._finish_btn.clicked.connect(self._on_finish)
        btn_layout.addWidget(self._finish_btn)

        v.addLayout(btn_layout)

        self._update_step_display()

    def _update_step_display(self) -> None:
        """Refresh the current step UI."""
        if self._current_step_idx >= len(self._steps):
            self._show_summary()
            return

        step_type, step_idx, step_label = self._steps[self._current_step_idx]

        self._step_label.setText(f"Press/Move: {step_label}")
        self._progress.setText(
            f"Step {self._current_step_idx + 1} of {len(self._steps)}"
        )

        # Check if already received
        step_key = f"{step_type}_{step_idx}"
        if step_key in self._received_inputs:
            self._step_checkmark.setText("✓")
            self._next_btn.setEnabled(True)
            self._next_btn.setText("Next")
        else:
            self._step_checkmark.setText("")
            self._next_btn.setEnabled(False)
            self._next_btn.setText("Waiting…")

    def _on_skip(self) -> None:
        """Skip the current step and record as missing."""
        step_type, step_idx, step_label = self._steps[self._current_step_idx]
        step_key = f"{step_type}_{step_idx}"
        self._missing_inputs.append(step_label)
        self._current_step_idx += 1
        self._update_step_display()

    def _on_next(self) -> None:
        """Advance to next step."""
        self._current_step_idx += 1
        self._update_step_display()

    def _show_summary(self) -> None:
        """Show final summary and offer to save."""
        self._skip_btn.setEnabled(False)
        self._next_btn.setVisible(False)
        self._finish_btn.setVisible(True)
        self._finish_btn.setEnabled(True)

        step_label = "All steps complete!" if not self._missing_inputs else (
            f"Complete (missing: {', '.join(self._missing_inputs)})"
        )
        self._step_label.setText(step_label)
        self._step_checkmark.setText("✓" if not self._missing_inputs else "!")
        self._progress.setText("")

    def _on_finish(self) -> None:
        """Emit the result and close."""
        self.wizard_complete.emit(self._missing_inputs)
        self.accept()

    def record_input(self, input_type: str, input_idx: int) -> None:
        """Called by the bridge when a button/axis/hat is received."""
        step_key = f"{input_type}_{input_idx}"
        if step_key not in self._received_inputs:
            self._received_inputs.add(step_key)

            # If this is the current step, enable the Next button
            if (self._current_step_idx < len(self._steps)
                    and self._steps[self._current_step_idx][0] == input_type
                    and self._steps[self._current_step_idx][1] == input_idx):
                self._update_step_display()
