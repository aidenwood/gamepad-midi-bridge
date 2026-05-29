"""CurveSparkline — a tiny 100×40 response-curve preview widget.

Draws the shaped response curve for a stick axis (or trigger) live as the
user edits deadzone / clamp / curve / amount in the inspector.  Redraws only
when `set_params` is called, so it never burns CPU between edits.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget

from ..shaping import apply_stick_shape, apply_curve

_TEAL = QColor("#5eead4")
_GRID = QColor("#24262d")
_REF  = QColor("#3a3c45")
_DOT  = QColor("#5eead4")
_BG   = QColor("#0e0f12")

_NUM_SAMPLES = 50


class CurveSparkline(QWidget):
    """100×40 sparkline that visualises the response curve for a stick or trigger axis.

    Params:
        inner_deadzone  (float 0..1)  — stick only; trigger mode ignores it
        outer_clamp     (float 0..1)  — stick only
        curve           (str)         — "linear" | "exponential" | "logarithmic" | "s-curve"
        curve_amount    (float 0..1)
        mode            (str)         — "stick" (default) or "trigger"

    Call `set_params(**kwargs)` to update any subset of the above; the widget
    invalidates and schedules a repaint automatically.

    For *trigger* mode (mode="trigger") the sparkline shows `apply_curve`
    directly on a 0..1 input, since trigger shaping in the app is mode-based
    (linear/ceiling/inverted/latch) rather than curve-based — so this just
    shows the plain curve shape for informational context.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(100, 40)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

        # Default params match StickConfig defaults.
        self._inner_deadzone: float = 0.05
        self._outer_clamp: float = 0.0
        self._curve: str = "linear"
        self._curve_amount: float = 0.5
        self._mode: str = "stick"

        # Cached polyline — rebuilt in set_params, consumed in paintEvent.
        self._path: QPainterPath | None = None
        self._rebuild_path()

    # ------------------------------------------------------------------ public

    def set_params(
        self,
        *,
        inner_deadzone: float | None = None,
        outer_clamp: float | None = None,
        curve: str | None = None,
        curve_amount: float | None = None,
        mode: str | None = None,
    ) -> None:
        """Update one or more shaping parameters and schedule a repaint."""
        changed = False
        if inner_deadzone is not None and inner_deadzone != self._inner_deadzone:
            self._inner_deadzone = float(inner_deadzone)
            changed = True
        if outer_clamp is not None and outer_clamp != self._outer_clamp:
            self._outer_clamp = float(outer_clamp)
            changed = True
        if curve is not None and curve != self._curve:
            self._curve = str(curve)
            changed = True
        if curve_amount is not None and curve_amount != self._curve_amount:
            self._curve_amount = float(curve_amount)
            changed = True
        if mode is not None and mode != self._mode:
            self._mode = str(mode)
            changed = True
        if changed:
            self._rebuild_path()
            self.update()

    # Property accessors for test introspection.
    @property
    def inner_deadzone(self) -> float:
        return self._inner_deadzone

    @property
    def outer_clamp(self) -> float:
        return self._outer_clamp

    @property
    def curve(self) -> str:
        return self._curve

    @property
    def curve_amount(self) -> float:
        return self._curve_amount

    @property
    def mode(self) -> str:
        return self._mode

    # ----------------------------------------------------------------- private

    def _sample_curve(self) -> List[tuple[float, float]]:
        """Return 50 (input, output) pairs in [0..1]×[0..1].

        For stick mode: sample the positive half of apply_stick_shape.
        For trigger mode: sample apply_curve directly (no deadzone/clamp).
        """
        pts: List[tuple[float, float]] = []
        n = _NUM_SAMPLES
        for i in range(n + 1):
            t = i / n  # 0..1 input
            if self._mode == "trigger":
                y = apply_curve(t, self._curve, self._curve_amount)
            else:
                # apply_stick_shape takes a -1..1 input; we use the positive half.
                raw = apply_stick_shape(
                    t,
                    inner_deadzone=self._inner_deadzone,
                    outer_clamp=self._outer_clamp,
                    curve=self._curve,
                    curve_amount=self._curve_amount,
                )
                # raw is -1..1; for positive input it's non-negative.
                y = max(0.0, min(1.0, raw))
            pts.append((t, y))
        return pts

    def _rebuild_path(self) -> None:
        """Build a QPainterPath from sampled points (widget coords)."""
        w = self.width()
        h = self.height()
        pad = 4  # pixel padding inside the widget

        def to_widget(tx: float, ty: float) -> QPointF:
            px = pad + tx * (w - 2 * pad)
            # y-axis is flipped: output=1 is top, output=0 is bottom.
            py = (h - pad) - ty * (h - 2 * pad)
            return QPointF(px, py)

        pts = self._sample_curve()
        path = QPainterPath()
        p0 = to_widget(pts[0][0], pts[0][1])
        path.moveTo(p0)
        for tx, ty in pts[1:]:
            path.lineTo(to_widget(tx, ty))
        self._path = path

    def paintEvent(self, _event) -> None:  # noqa: N802
        w = self.width()
        h = self.height()
        pad = 4

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(0, 0, w, h, _BG)

        # Grid — 3 vertical + 3 horizontal dashed lines
        grid_pen = QPen(_GRID, 1, Qt.DashLine)
        painter.setPen(grid_pen)
        for frac in (0.25, 0.5, 0.75):
            x = int(pad + frac * (w - 2 * pad))
            painter.drawLine(x, pad, x, h - pad)
            y = int((h - pad) - frac * (h - 2 * pad))
            painter.drawLine(pad, y, w - pad, y)

        # 1:1 reference diagonal (dimmer)
        ref_pen = QPen(_REF, 1, Qt.SolidLine)
        painter.setPen(ref_pen)
        painter.drawLine(pad, h - pad, w - pad, pad)

        # Curve polyline
        if self._path:
            curve_pen = QPen(_TEAL, 1.5, Qt.SolidLine)
            curve_pen.setCapStyle(Qt.RoundCap)
            curve_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(curve_pen)
            painter.drawPath(self._path)

        # Endpoint dots
        dot_pen = QPen(_TEAL, 1)
        painter.setPen(dot_pen)
        painter.setBrush(_TEAL)
        dot_r = 2.5
        # (0, 0) → bottom-left
        painter.drawEllipse(QPointF(pad, h - pad), dot_r, dot_r)
        # (1, 1) → top-right
        painter.drawEllipse(QPointF(w - pad, pad), dot_r, dot_r)

        painter.end()

    def resizeEvent(self, _event) -> None:  # noqa: N802
        """Rebuild path cache whenever the widget size changes."""
        self._rebuild_path()
