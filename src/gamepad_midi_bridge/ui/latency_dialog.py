"""Latency self-test dialog.

Opens a wizard that prompts the user to press controller buttons and records
controller-input -> MIDI-send latency over N samples, then shows stats.

Usage::

    dlg = LatencyDialog(bridge_worker, parent=self)
    dlg.exec()
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import latency_test as _lt

_TARGET_SAMPLES = 10

# Visual rules for every widget in this dialog live in styles.qss under the
# "LATENCY DIALOG" section. Each widget below is tagged with the matching
# objectName.


class LatencyDialog(QDialog):
    """Wizard dialog -- guides user through a 10-sample latency measurement.

    The dialog activates test mode on the BridgeWorker by setting its
    ``_latency_test_active`` flag, then polls the LatencyTracker singleton
    via a QTimer to update the live counter.  Once TARGET_SAMPLES are
    collected it switches to the results view.

    Parameters
    ----------
    bridge_worker:
        The live BridgeWorker instance (may be None for headless / tests --
        the dialog degrades gracefully and shows zeroed results).
    parent:
        Optional Qt parent widget.
    """

    def __init__(self, bridge_worker=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker = bridge_worker
        self._tracker = _lt.tracker()

        self.setWindowTitle("Latency self-test")
        self.setObjectName("LatencyDialog")
        self.setMinimumWidth(380)

        self._build_ui()
        self._start_test()

    # ------------------------------------------------------------------
    # UI construction

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Title
        title = QLabel("Latency self-test")
        title.setObjectName("LatencyDialogTitle")
        root.addWidget(title)

        sub = QLabel("Measures controller button -> MIDI output latency.")
        sub.setObjectName("LatencyDialogSub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # Instruction card
        self._instruction_card = QWidget()
        self._instruction_card.setObjectName("LatencyDialogCard")
        self._instruction_card.setAttribute(Qt.WA_StyledBackground, True)
        ic_layout = QVBoxLayout(self._instruction_card)
        ic_layout.setContentsMargins(0, 0, 0, 0)
        ic_layout.setSpacing(10)

        prompt = QLabel("Press any mapped button NOW.")
        prompt.setObjectName("LatencyDialogPrompt")
        ic_layout.addWidget(prompt)

        self._counter_label = QLabel(f"Samples: 0 / {_TARGET_SAMPLES}")
        self._counter_label.setObjectName("LatencyDialogCounter")
        ic_layout.addWidget(self._counter_label)

        root.addWidget(self._instruction_card)

        # Results card (hidden until complete)
        self._results_card = QWidget()
        self._results_card.setObjectName("LatencyDialogCard")
        self._results_card.setAttribute(Qt.WA_StyledBackground, True)
        rc_layout = QVBoxLayout(self._results_card)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(6)

        section_lbl = QLabel("RESULTS")
        section_lbl.setObjectName("LatencyDialogSectionLabel")
        rc_layout.addWidget(section_lbl)

        self._mean_label = QLabel("Mean:    --")
        self._min_label  = QLabel("Min:     --")
        self._max_label  = QLabel("Max:     --")
        self._std_label  = QLabel("Std dev: --")
        for lbl in (self._mean_label, self._min_label,
                    self._max_label, self._std_label):
            lbl.setObjectName("LatencyDialogResultLabel")
            rc_layout.addWidget(lbl)

        self._results_card.setVisible(False)
        root.addWidget(self._results_card)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        self._run_again_btn = QPushButton("Run again")
        self._run_again_btn.clicked.connect(self._start_test)
        self._run_again_btn.setVisible(False)
        btn_row.addWidget(self._run_again_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        root.addLayout(btn_row)

        # Poll timer -- checks tracker at ~60 Hz while test is running
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(16)
        self._poll_timer.timeout.connect(self._poll)

    # ------------------------------------------------------------------
    # Test lifecycle

    def _start_test(self) -> None:
        """Reset state, activate bridge test mode, start polling."""
        self._tracker.reset()
        self._counter_label.setText(f"Samples: 0 / {_TARGET_SAMPLES}")
        self._results_card.setVisible(False)
        self._instruction_card.setVisible(True)
        self._run_again_btn.setVisible(False)

        if self._worker is not None:
            self._worker._latency_test_active = True

        self._poll_timer.start()

    def _finish_test(self) -> None:
        """Deactivate bridge test mode and display results."""
        self._poll_timer.stop()

        if self._worker is not None:
            self._worker._latency_test_active = False

        mean = self._tracker.mean_ms()
        mn   = self._tracker.min_ms()
        mx   = self._tracker.max_ms()
        std  = self._tracker.std_ms()

        def _fmt(v: Optional[float]) -> str:
            return f"{v:.2f} ms" if v is not None else "--"

        self._mean_label.setText(f"Mean:    {_fmt(mean)}")
        self._min_label.setText( f"Min:     {_fmt(mn)}")
        self._max_label.setText( f"Max:     {_fmt(mx)}")
        self._std_label.setText( f"Std dev: {_fmt(std)}")

        self._instruction_card.setVisible(False)
        self._results_card.setVisible(True)
        self._run_again_btn.setVisible(True)

    # ------------------------------------------------------------------
    # Poll slot

    @Slot()
    def _poll(self) -> None:
        """Check tracker sample count; update counter or finish."""
        n = len(self._tracker.samples)
        self._counter_label.setText(f"Samples: {n} / {_TARGET_SAMPLES}")
        if n >= _TARGET_SAMPLES:
            self._finish_test()

    # ------------------------------------------------------------------
    # Cleanup

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._poll_timer.stop()
        if self._worker is not None:
            self._worker._latency_test_active = False
        super().closeEvent(event)
