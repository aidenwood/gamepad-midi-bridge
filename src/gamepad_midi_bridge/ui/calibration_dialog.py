"""Non-modal calibration toast, driven by BridgeWorker progress signals."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .tokens import SHELL_PURPLE, SHELL_TEAL, SHELL_TEAL_FG, TEXT_PRIMARY


class CalibrationToast(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CalibrationToast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAccessibleName("Controller stick calibration")
        self._dismiss = QTimer(self)
        self._dismiss.setSingleShot(True)
        self._dismiss.timeout.connect(self.hide)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)
        self._title = QLabel("Keep your hands off the sticks")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)
        self._result = QLabel("Sampling their resting position to compensate for stick drift…")
        self._result.setWordWrap(True)
        layout.addWidget(self._result)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        layout.addWidget(self._bar)
        close = QPushButton("Dismiss")
        close.clicked.connect(self.hide)
        layout.addWidget(close, alignment=Qt.AlignRight)
        self._highlight(True)
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()

    def _highlight(self, active: bool) -> None:
        bg, fg = (SHELL_TEAL, SHELL_TEAL_FG) if active else (SHELL_PURPLE, TEXT_PRIMARY)
        self.setStyleSheet(
            f"QFrame#CalibrationToast {{ background: {bg}; border: 2px solid {SHELL_TEAL};"
            "border-radius: 10px; }"
            f"QFrame#CalibrationToast QLabel {{ color: {fg}; background: transparent; border: none; }}"
            "QFrame#CalibrationToast QProgressBar { border: none; background: #203F5B; }"
            f"QFrame#CalibrationToast QProgressBar::chunk {{ background: {fg}; }}"
            f"QFrame#CalibrationToast QPushButton {{ color: {fg}; background: transparent;"
            "border: none; padding: 3px 8px; }"
        )
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setFixedWidth(max(1, min(440, parent.width() - 24)))
        self.adjustSize()
        workspace = getattr(parent.window(), "_body_splitter", None)
        top = workspace.mapTo(parent, QPoint()).y() + 12 if workspace is not None else 12
        self.move(max(0, (parent.width() - self.width()) // 2), max(12, top))
        self.raise_()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Resize and watched is self.parentWidget():
            self.place()
        return super().eventFilter(watched, event)

    def on_progress(self, fraction: float) -> None:
        self._dismiss.stop()
        self._bar.setValue(round(max(0.0, min(fraction, 1.0)) * 100))
        if not self.isVisible():
            self.show()
        self.place()

    def on_done(self, offsets: dict[int, float], severe: list[int], significant: list[int]) -> None:
        self._bar.setValue(100)
        self._bar.hide()
        self._highlight(False)
        if severe:
            self._title.setText("Severe stick drift detected")
            self._result.setText(
                "Calibration finished. Significant drift remains; the controller may need repair."
            )
        elif significant:
            self._title.setText("Stick drift compensated")
            self._result.setText("Calibration finished. You can use the controller now.")
        else:
            self._title.setText("Sticks ready")
            self._result.setText("Resting position checked and minor drift compensated.")
        self.setToolTip(
            "Offsets: "
            + ", ".join(f"axis {axis}: {value:+.3f}" for axis, value in sorted(offsets.items()))
        )
        self.show()
        self.place()
        self._dismiss.start(10_000 if severe else 5_000)


# Keep the internal import compatible; this is a QFrame, never a modal dialog.
CalibrationDialog = CalibrationToast
