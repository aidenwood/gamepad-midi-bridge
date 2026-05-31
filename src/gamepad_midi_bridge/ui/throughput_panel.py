"""MIDI throughput dashboard — 60-second history sparklines for inbound/outbound rate."""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


# Palette — match visualise_tab.py + controller_meter.py
OUTBOUND_COLOR = QColor("#2dd4bf")  # teal
INBOUND_COLOR = QColor("#ff9800")   # orange
PEAK_COLOR = QColor("#fbbf24")      # amber
PANEL_BG = QColor("#13151a")
GRID_LINE = QColor("#1f232b")
TEXT_DIM = QColor("#8a9099")
TEXT_BRIGHT = QColor("#f5f7fa")


class ThroughputPanel(QWidget):
    """Rich MIDI throughput panel: dual sparklines + numeric readouts + peak markers.

    Maintains a 60-second ring buffer of (timestamp_s, outbound_per_sec, inbound_per_sec).
    Draws:
      - Two sparklines (teal outbound, orange inbound) side-by-side or stacked
      - Numeric readout: "Out: 142/s  Peak: 211"
      - Numeric readout: "In: 0/s  Peak: 5"
      - Grid lines at 25/50/75% of vertical range
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(120)
        self.setObjectName("ThroughputPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Ring buffer: (timestamp_s, outbound_per_sec, inbound_per_sec)
        # Capacity 60 → 1 entry per second, 60s history
        self._history: Deque[Tuple[float, float, float]] = deque(maxlen=60)

        # Peak tracking
        self._peak_out = 0
        self._peak_in = 0
        self._peak_out_ts = 0.0
        self._peak_in_ts = 0.0

        # Current values for numeric display
        self._current_out = 0
        self._current_in = 0

    def tick(self, outbound_count: int, inbound_count: int) -> None:
        """Called every 1 second with message counts for this interval.

        Args:
            outbound_count: Number of outbound MIDI messages sent in the last second.
            inbound_count: Number of inbound MIDI messages received in the last second.
        """
        import time
        ts = time.time()

        self._current_out = outbound_count
        self._current_in = inbound_count

        # Update peaks
        if outbound_count > self._peak_out:
            self._peak_out = outbound_count
            self._peak_out_ts = ts

        if inbound_count > self._peak_in:
            self._peak_in = inbound_count
            self._peak_in_ts = ts

        # Append to ring buffer
        self._history.append((ts, float(outbound_count), float(inbound_count)))

        self.update()

    def reset(self) -> None:
        """Clear history and peak tracking."""
        self._history.clear()
        self._peak_out = 0
        self._peak_in = 0
        self._peak_out_ts = 0.0
        self._peak_in_ts = 0.0
        self._current_out = 0
        self._current_in = 0
        self.update()

    def paintEvent(self, _event) -> None:
        """Paint the panel: sparklines + numeric readouts + grid."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        margin = 12

        # Background
        p.fillRect(0, 0, w, h, PANEL_BG)

        # Numeric readout area: top-left and top-right
        # Format: "Out: 142/s  Peak: 211" and "In: 0/s  Peak: 5"
        readout_h = 16
        p.setPen(QPen(TEXT_BRIGHT))
        p.setFont(QFont("ui-monospace, Menlo, monospace", 10, QFont.Bold))

        out_text = f"Out: {self._current_out}/s  Peak: {self._peak_out}"
        in_text = f"In: {self._current_in}/s  Peak: {self._peak_in}"

        p.drawText(margin, margin, w - 2 * margin, readout_h, Qt.AlignLeft, out_text)
        p.drawText(margin, margin + readout_h, w - 2 * margin, readout_h, Qt.AlignLeft, in_text)

        # Sparkline area: rest of the widget
        sparkline_top = margin + 2 * readout_h + 4
        sparkline_h = h - sparkline_top - margin
        sparkline_w = w - 2 * margin

        if sparkline_h < 20 or len(self._history) < 2:
            return

        # Draw grid lines at 25/50/75% of vertical range
        max_val = max(self._peak_out, self._peak_in) if self._peak_out or self._peak_in else 10
        if max_val == 0:
            max_val = 10

        p.setPen(QPen(GRID_LINE, 1, Qt.DashLine))
        grid_y = [0.25, 0.50, 0.75]
        for pct in grid_y:
            y = sparkline_top + sparkline_h * (1.0 - pct)
            p.drawLine(margin, int(y), w - margin, int(y))

        # Draw sparklines
        # Split sparkline area into two halves: top for outbound, bottom for inbound
        sparkline_out_h = sparkline_h / 2
        sparkline_in_h = sparkline_h / 2

        self._draw_sparkline(
            p, margin, sparkline_top, sparkline_w, sparkline_out_h,
            [v[1] for v in self._history], OUTBOUND_COLOR, max_val
        )

        self._draw_sparkline(
            p, margin, sparkline_top + sparkline_out_h, sparkline_w, sparkline_in_h,
            [v[2] for v in self._history], INBOUND_COLOR, max_val
        )

    def _draw_sparkline(
        self,
        p: QPainter,
        x: int,
        y: int,
        w: int,
        h: int,
        values: list[float],
        color: QColor,
        max_val: float,
    ) -> None:
        """Draw a single sparkline strip.

        Args:
            p: Painter.
            x, y: Top-left corner of sparkline area.
            w, h: Width and height.
            values: List of values (older to newer, right-aligned).
            color: Sparkline color.
            max_val: Maximum value for scaling.
        """
        if len(values) < 2 or max_val == 0:
            return

        # Draw as a filled polygon from baseline up
        points = []

        # Baseline at bottom
        x_step = w / (len(values) - 1) if len(values) > 1 else w
        for i, val in enumerate(values):
            px = x + i * x_step
            # Normalize to [0, 1] then scale to pixel height
            norm = min(val / max_val, 1.0)
            py = y + h - (norm * h)
            points.append(QPointF(px, py))

        # Close the polygon at the baseline
        if points:
            points.append(QPointF(x + (len(values) - 1) * x_step, y + h))
            points.append(QPointF(x, y + h))

            p.setBrush(QBrush(color))
            p.setPen(QPen(color, 1.5))
            p.drawPolygon(points)
