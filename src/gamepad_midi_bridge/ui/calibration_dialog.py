"""Calibration progress dialog. Driven by BridgeWorker signals."""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)


class CalibrationDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibrating sticks")
        self.setModal(True)
        self.setMinimumWidth(420)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(14)

        title = QLabel("Keep your hands off the controller")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #f5f7fa;")
        v.addWidget(title)

        sub = QLabel("Sampling resting position to compensate for stick drift…")
        sub.setStyleSheet("color: #8a9099;")
        sub.setWordWrap(True)
        v.addWidget(sub)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        v.addWidget(self._bar)

        self._result = QLabel("")
        self._result.setWordWrap(True)
        self._result.setStyleSheet("color: #c2c6cc; padding-top: 8px;")
        v.addWidget(self._result)

        self._close_btn = QPushButton("OK")
        self._close_btn.setObjectName("PrimaryButton")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        v.addWidget(self._close_btn, alignment=Qt.AlignRight)

    def on_progress(self, fraction: float) -> None:
        self._bar.setValue(int(fraction * 100))

    def on_done(self, offsets: Dict[int, float], severe: List[int], significant: List[int]) -> None:
        self._bar.setValue(100)
        parts = []
        if severe:
            parts.append(
                f"⚠ Severe drift on axes {', '.join(str(a) for a in severe)} "
                "(>0.30). Controller may need physical repair."
            )
        if significant:
            parts.append(
                f"Compensating noticeable drift on axes {', '.join(str(a) for a in significant)}."
            )
        if not parts:
            parts.append("Sticks look clean — minor drift compensated.")
        parts.append("")
        parts.append("Offsets: " + ", ".join(
            f"axis {a}: {v:+.3f}" for a, v in sorted(offsets.items())
        ))
        self._result.setText("\n".join(parts))
        self._close_btn.setEnabled(True)
