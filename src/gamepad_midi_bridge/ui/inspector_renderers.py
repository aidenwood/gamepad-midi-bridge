"""Inspector renderers for TriggerConfig, StickConfig, and TouchpadConfig.

Each renderer function receives a payload dict and returns a populated QWidget
whose form controls are live-wired to mutate the config dataclass in place.
Changes take effect immediately for the next bridge tick — no save/apply needed.

Payload shapes expected:
  Trigger:  { "kind": "trigger", "label": str, "config": TriggerConfig, ... }
  Stick:    { "kind": "stick",   "label": str, "config": StickConfig,   ... }
  Touchpad: { "kind": "touchpad","label": str, "config": TouchpadConfig, ... }
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..shaping import TRIGGER_MODES
from .curve_sparkline import CurveSparkline

# Curves shared by StickConfig and TouchpadConfig
_CURVES = ("linear", "exponential", "logarithmic", "s-curve")


# ──────────────────────────────────────────────────────────────────── helpers

def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #8a9099; font-size: 10px; font-weight: 700; "
        "letter-spacing: 1.2px; margin-top: 10px;"
    )
    return lbl


def _title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #f5f7fa; font-size: 15px; font-weight: 600;")
    return lbl


def _chip(text: str, color: str = "#5eead4", bg: str = "rgba(45,212,191,0.12)",
          border: str = "rgba(45,212,191,0.3)") -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"color: {color}; background: {bg}; border: 1px solid {border}; "
        "border-radius: 999px; padding: 3px 10px; font-size: 10px; "
        "font-weight: 700; letter-spacing: 1.2px;"
    )
    lbl.setMaximumWidth(100)
    return lbl


def _row_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #8a9099; font-size: 11px;")
    lbl.setMinimumWidth(118)
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #1c1e25;")
    return line


def _make_combo(options: tuple, current: str,
                on_change: Callable[[str], None]) -> QComboBox:
    cb = QComboBox()
    for opt in options:
        cb.addItem(opt)
    idx = cb.findText(current)
    if idx >= 0:
        cb.setCurrentIndex(idx)
    cb.currentTextChanged.connect(on_change)
    return cb


def _make_int_slider(lo: int, hi: int, value: int,
                     on_change: Callable[[int], None],
                     enabled: bool = True) -> QSlider:
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    s.setEnabled(enabled)
    s.valueChanged.connect(on_change)
    return s


def _make_float_slider(lo_cents: int, hi_cents: int, value_cents: int,
                       on_change: Callable[[int], None],
                       enabled: bool = True) -> QSlider:
    """Slider that stores hundredths (0–100 → 0.00–1.00)."""
    s = QSlider(Qt.Horizontal)
    s.setRange(lo_cents, hi_cents)
    s.setValue(value_cents)
    s.setEnabled(enabled)
    s.valueChanged.connect(on_change)
    return s


def _make_int_spinbox(lo: int, hi: int, value: int,
                      on_change: Callable[[int], None]) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(value)
    sb.setStyleSheet("background: #0e0f12; color: #c2c6cc; border: 1px solid #24262d;")
    sb.valueChanged.connect(on_change)
    return sb


def _slider_row(label: str, widget: QWidget, value_lbl_text: str = "") -> tuple:
    """Returns (row_widget, value_label) for live value display next to a slider."""
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addWidget(_row_label(label))
    h.addWidget(widget, 1)
    val_lbl = QLabel(value_lbl_text)
    val_lbl.setStyleSheet(
        "color: #c2c6cc; font-size: 11px; font-family: ui-monospace, Menlo, monospace;"
    )
    val_lbl.setMinimumWidth(34)
    val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    h.addWidget(val_lbl)
    return row, val_lbl


def _combo_row(label: str, cb: QComboBox) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addWidget(_row_label(label))
    h.addWidget(cb, 1)
    return row


def _check_row(label: str, cb: QCheckBox) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addWidget(_row_label(label))
    h.addWidget(cb)
    h.addStretch(1)
    return row


def _spinbox_row(label: str, sb: QWidget) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addWidget(_row_label(label))
    h.addWidget(sb)
    h.addStretch(1)
    return row


def _sparkline_row(sparkline: "CurveSparkline", label: str = "Preview") -> QWidget:
    """Embed a CurveSparkline with a small label to its left."""
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 4, 0, 4)
    h.setSpacing(6)
    lbl = _row_label(label)
    h.addWidget(lbl)
    h.addStretch(1)
    h.addWidget(sparkline)
    return row


# ──────────────────────────────────────────────────────────────────── renderers

def render_trigger_editor(payload: dict) -> QWidget:
    """Inspector editor for TriggerConfig (L2 / R2).

    Form controls:
      - mode dropdown  (linear / ceiling / inverted / latch)
      - ceiling slider (0..127, enabled only in "ceiling" mode)
      - latch_threshold slider (0.00..1.00, enabled only in "latch" mode)
      - gate_button spinbox (−1 = none, 0..31 = button index)
      - gate_release_value slider (0..127)
    """
    cfg = payload.get("config")
    label = str(payload.get("label", "Trigger"))
    on_change = payload.get("on_change")  # Callback to emit when config mutates

    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)

    v.addWidget(_title(label))
    v.addWidget(_chip("trigger", "#fb923c", "rgba(251,146,60,0.12)", "rgba(251,146,60,0.3)"))
    v.addWidget(_divider())

    if cfg is None:
        v.addWidget(QLabel("No config attached."))
        v.addStretch(1)
        return wrap

    # ── mode ──
    v.addWidget(_section("SHAPING"))
    def _on_mode_combo(t: str) -> None:
        setattr(cfg, "mode", t)
        if on_change:
            on_change()
    mode_cb = _make_combo(TRIGGER_MODES, cfg.mode, _on_mode_combo)
    mode_cb.setToolTip(
        "linear: Continuous 0→127 ramp (default). "
        "ceiling: Caps max output to CC value below. "
        "inverted: Rest=127, press=0 (polarity flip). "
        "latch: Toggle on threshold cross (push-to-on, release-to-off with hysteresis)."
    )

    # ── ceiling ──
    ceil_enabled = cfg.mode == "ceiling"
    def _on_ceil(val: int) -> None:
        setattr(cfg, "ceiling", val)
        if on_change:
            on_change()
    ceil_slider = _make_int_slider(0, 127, cfg.ceiling, _on_ceil, enabled=ceil_enabled)
    ceil_slider.setToolTip("Max CC value when mode is 'Ceiling' (0 = mute, 127 = full)")
    ceil_row, ceil_val = _slider_row("Ceiling CC", ceil_slider, str(cfg.ceiling))

    # ── latch threshold ──
    latch_enabled = cfg.mode == "latch"
    latch_init = int(round(cfg.latch_threshold * 100))
    def _on_latch(val: int) -> None:
        setattr(cfg, "latch_threshold", val / 100.0)
        if on_change:
            on_change()
    latch_slider = _make_float_slider(0, 100, latch_init, _on_latch, enabled=latch_enabled)
    latch_slider.setToolTip("Pressure level (0.00–1.00) where latch flips on/off with ±0.025 hysteresis")
    latch_row, latch_val = _slider_row("Latch threshold", latch_slider,
                                       f"{cfg.latch_threshold:.2f}")

    # Live value labels
    ceil_slider.valueChanged.connect(lambda val: ceil_val.setText(str(val)))
    latch_slider.valueChanged.connect(
        lambda val: latch_val.setText(f"{val / 100:.2f}")
    )

    # ── sparkline (trigger mode preview) ──
    # Trigger uses mode-based shaping, not apply_stick_shape.  We show a plain
    # apply_curve preview so the user gets visual feedback when they switch modes.
    # For "latch" (toggle, no continuous curve) we hide the sparkline.
    trig_sparkline = CurveSparkline()
    trig_sparkline.set_params(mode="trigger")
    trig_sparkline_row = _sparkline_row(trig_sparkline)
    trig_sparkline_row.setVisible(cfg.mode != "latch")

    # Enable/disable dependent sliders when mode changes
    def _on_mode_change(text: str) -> None:
        setattr(cfg, "mode", text)
        ceil_slider.setEnabled(text == "ceiling")
        latch_slider.setEnabled(text == "latch")
        trig_sparkline_row.setVisible(text != "latch")
        if on_change:
            on_change()

    # Disconnect the simple setter and reconnect with the richer one
    try:
        mode_cb.currentTextChanged.disconnect()
    except Exception:
        pass
    mode_cb.currentTextChanged.connect(_on_mode_change)

    v.addWidget(_combo_row("Mode", mode_cb))
    v.addWidget(ceil_row)
    v.addWidget(latch_row)
    v.addWidget(trig_sparkline_row)

    # ── gate ──
    v.addWidget(_divider())
    v.addWidget(_section("GATE"))

    # gate_button: -1 means "no gate" in the UI (maps to None in the dataclass)
    gate_init = -1 if cfg.gate_button is None else cfg.gate_button

    def _on_gate_button_changed(val: int) -> None:
        cfg.gate_button = None if val < 0 else val
        if on_change:
            on_change()

    gate_sb = _make_int_spinbox(-1, 31, gate_init, _on_gate_button_changed)
    gate_sb.setSpecialValueText("none")
    gate_sb.setToolTip("Button index that must be held for this trigger to send MIDI. -1 = no gate")
    v.addWidget(_spinbox_row("Gate button (−1 = off)", gate_sb))

    def _on_release(val: int) -> None:
        setattr(cfg, "gate_release_value", val)
        if on_change:
            on_change()
    release_slider = _make_int_slider(0, 127, cfg.gate_release_value, _on_release)
    release_slider.setToolTip("CC value sent once when gate releases. 0 = silence the receiver")
    release_row, release_val = _slider_row("Release value", release_slider,
                                           str(cfg.gate_release_value))
    release_slider.valueChanged.connect(lambda val: release_val.setText(str(val)))
    v.addWidget(release_row)

    v.addStretch(1)
    return wrap


def render_stick_editor(payload: dict) -> QWidget:
    """Inspector editor for StickConfig (left / right stick).

    Form controls:
      - inner_deadzone slider (0.00..0.50)
      - outer_clamp slider (0.00..0.50)
      - curve dropdown (linear / exponential / logarithmic / s-curve)
      - curve_amount slider (0.00..1.00)
      - polar_mode checkbox
      - polar_angle_cc spinbox (enabled when polar_mode)
      - polar_mag_cc spinbox (enabled when polar_mode)
    """
    cfg = payload.get("config")
    label = str(payload.get("label", "Stick"))
    on_change = payload.get("on_change")  # Callback to emit when config mutates

    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)

    v.addWidget(_title(label))
    v.addWidget(_chip("stick", "#818cf8", "rgba(129,140,248,0.12)", "rgba(129,140,248,0.3)"))
    v.addWidget(_divider())

    if cfg is None:
        v.addWidget(QLabel("No config attached."))
        v.addStretch(1)
        return wrap

    # ── deadzones ──
    v.addWidget(_section("DEADZONE"))

    dz_init = int(round(cfg.inner_deadzone * 100))
    def _on_dz(val: int) -> None:
        setattr(cfg, "inner_deadzone", val / 100.0)
        stick_sparkline.set_params(inner_deadzone=val / 100.0)
        if on_change:
            on_change()
    dz_slider = _make_float_slider(0, 50, dz_init, _on_dz)
    dz_slider.setToolTip("Magnitudes below this snap to 0 (centre, in 0.00–0.50 range)")
    dz_row, dz_val = _slider_row("Inner deadzone", dz_slider, f"{cfg.inner_deadzone:.2f}")
    dz_slider.valueChanged.connect(lambda val: dz_val.setText(f"{val / 100:.2f}"))
    v.addWidget(dz_row)

    oc_init = int(round(cfg.outer_clamp * 100))
    def _on_oc(val: int) -> None:
        setattr(cfg, "outer_clamp", val / 100.0)
        stick_sparkline.set_params(outer_clamp=val / 100.0)
        if on_change:
            on_change()
    oc_slider = _make_float_slider(0, 50, oc_init, _on_oc)
    oc_slider.setToolTip("Top fraction of stick travel that pegs to ±1 (0 = no clamp, 0.50 = full)")
    oc_row, oc_val = _slider_row("Outer clamp", oc_slider, f"{cfg.outer_clamp:.2f}")
    oc_slider.valueChanged.connect(lambda val: oc_val.setText(f"{val / 100:.2f}"))
    v.addWidget(oc_row)

    # ── curve ──
    v.addWidget(_divider())
    v.addWidget(_section("RESPONSE CURVE"))

    # Sparkline lives here, between section header and controls.
    stick_sparkline = CurveSparkline()
    stick_sparkline.set_params(
        inner_deadzone=cfg.inner_deadzone,
        outer_clamp=cfg.outer_clamp,
        curve=cfg.curve,
        curve_amount=cfg.curve_amount,
        mode="stick",
    )
    v.addWidget(_sparkline_row(stick_sparkline))

    def _on_curve(t: str) -> None:
        setattr(cfg, "curve", t)
        stick_sparkline.set_params(curve=t)
        if on_change:
            on_change()
    curve_cb = _make_combo(_CURVES, cfg.curve, _on_curve)
    curve_cb.setToolTip(
        "linear: Proportional response (default). exponential: Fast near start, slow near end. "
        "logarithmic: Slow near start, fast near end. s-curve: Slow ends, fast middle."
    )
    v.addWidget(_combo_row("Curve", curve_cb))

    ca_init = int(round(cfg.curve_amount * 100))
    def _on_ca(val: int) -> None:
        setattr(cfg, "curve_amount", val / 100.0)
        stick_sparkline.set_params(curve_amount=val / 100.0)
        if on_change:
            on_change()
    ca_slider = _make_float_slider(0, 100, ca_init, _on_ca)
    ca_slider.setToolTip("Strength of the curve (0.00 = linear, 1.00 = full curve applied)")
    ca_row, ca_val = _slider_row("Curve amount", ca_slider, f"{cfg.curve_amount:.2f}")
    ca_slider.valueChanged.connect(lambda val: ca_val.setText(f"{val / 100:.2f}"))
    v.addWidget(ca_row)

    # ── polar ──
    v.addWidget(_divider())
    v.addWidget(_section("POLAR MODE"))

    polar_chk = QCheckBox()
    polar_chk.setChecked(cfg.polar_mode)

    def _on_angle(val: int) -> None:
        setattr(cfg, "polar_angle_cc", val)
        if on_change:
            on_change()
    def _on_mag(val: int) -> None:
        setattr(cfg, "polar_mag_cc", val)
        if on_change:
            on_change()
    angle_sb = _make_int_spinbox(0, 127, cfg.polar_angle_cc, _on_angle)
    angle_sb.setToolTip("CC number for the angle when polar_mode is on (0–127)")
    mag_sb = _make_int_spinbox(0, 127, cfg.polar_mag_cc, _on_mag)
    mag_sb.setToolTip("CC number for the magnitude when polar_mode is on (0–127)")

    # Enable CC spinboxes only when polar mode is on
    angle_sb.setEnabled(cfg.polar_mode)
    mag_sb.setEnabled(cfg.polar_mode)

    def _on_polar(state: int) -> None:
        on = bool(state)
        cfg.polar_mode = on
        angle_sb.setEnabled(on)
        mag_sb.setEnabled(on)
        if on_change:
            on_change()

    polar_chk.setToolTip("Emit (angle, magnitude) as 2 CCs instead of (X, Y)")
    polar_chk.stateChanged.connect(_on_polar)

    v.addWidget(_check_row("Polar mode", polar_chk))
    v.addWidget(_spinbox_row("Angle CC", angle_sb))
    v.addWidget(_spinbox_row("Magnitude CC", mag_sb))

    v.addStretch(1)
    return wrap


def render_touchpad_editor(payload: dict) -> QWidget:
    """Inspector editor for TouchpadConfig.

    Form controls:
      - mode dropdown (absolute / relative)
      - click_to_arm checkbox
      - inner_deadzone slider (0.00..0.49)
      - x_curve + x_curve_amount
      - y_curve + y_curve_amount
    """
    cfg = payload.get("config")
    label = str(payload.get("label", "Touchpad"))
    on_change = payload.get("on_change")  # Callback to emit when config mutates

    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)

    v.addWidget(_title(label))
    v.addWidget(_chip("touchpad", "#a78bfa", "rgba(167,139,250,0.12)", "rgba(167,139,250,0.3)"))
    v.addWidget(_divider())

    if cfg is None:
        v.addWidget(QLabel("No config attached."))
        v.addStretch(1)
        return wrap

    # ── mode + arm ──
    v.addWidget(_section("BEHAVIOUR"))

    def _on_tp_mode(t: str) -> None:
        setattr(cfg, "mode", t)
        if on_change:
            on_change()
    mode_cb = _make_combo(("absolute", "relative"), cfg.mode, _on_tp_mode)
    v.addWidget(_combo_row("Mode", mode_cb))

    arm_chk = QCheckBox()
    arm_chk.setChecked(cfg.click_to_arm)
    def _on_arm(s: int) -> None:
        setattr(cfg, "click_to_arm", bool(s))
        if on_change:
            on_change()
    arm_chk.stateChanged.connect(_on_arm)
    v.addWidget(_check_row("Click to arm", arm_chk))

    # ── deadzone ──
    v.addWidget(_divider())
    v.addWidget(_section("DEADZONE"))

    dz_init = int(round(cfg.inner_deadzone * 100))
    def _on_tp_dz(val: int) -> None:
        setattr(cfg, "inner_deadzone", val / 100.0)
        if on_change:
            on_change()
    dz_slider = _make_float_slider(0, 49, dz_init, _on_tp_dz)
    dz_row, dz_val = _slider_row("Inner deadzone", dz_slider, f"{cfg.inner_deadzone:.2f}")
    dz_slider.valueChanged.connect(lambda val: dz_val.setText(f"{val / 100:.2f}"))
    v.addWidget(dz_row)

    # ── X curve ──
    v.addWidget(_divider())
    v.addWidget(_section("X AXIS CURVE"))

    x_sparkline = CurveSparkline()
    x_sparkline.set_params(curve=cfg.x_curve, curve_amount=cfg.x_curve_amount, mode="trigger")
    v.addWidget(_sparkline_row(x_sparkline, "X preview"))

    def _on_xcurve(t: str) -> None:
        setattr(cfg, "x_curve", t)
        x_sparkline.set_params(curve=t)
        if on_change:
            on_change()
    xcurve_cb = _make_combo(_CURVES, cfg.x_curve, _on_xcurve)
    v.addWidget(_combo_row("X curve", xcurve_cb))

    xca_init = int(round(cfg.x_curve_amount * 100))
    def _on_xca(val: int) -> None:
        setattr(cfg, "x_curve_amount", val / 100.0)
        x_sparkline.set_params(curve_amount=val / 100.0)
        if on_change:
            on_change()
    xca_slider = _make_float_slider(0, 100, xca_init, _on_xca)
    xca_row, xca_val = _slider_row("X amount", xca_slider, f"{cfg.x_curve_amount:.2f}")
    xca_slider.valueChanged.connect(lambda val: xca_val.setText(f"{val / 100:.2f}"))
    v.addWidget(xca_row)

    # ── Y curve ──
    v.addWidget(_divider())
    v.addWidget(_section("Y AXIS CURVE"))

    y_sparkline = CurveSparkline()
    y_sparkline.set_params(curve=cfg.y_curve, curve_amount=cfg.y_curve_amount, mode="trigger")
    v.addWidget(_sparkline_row(y_sparkline, "Y preview"))

    def _on_ycurve(t: str) -> None:
        setattr(cfg, "y_curve", t)
        y_sparkline.set_params(curve=t)
        if on_change:
            on_change()
    ycurve_cb = _make_combo(_CURVES, cfg.y_curve, _on_ycurve)
    v.addWidget(_combo_row("Y curve", ycurve_cb))

    yca_init = int(round(cfg.y_curve_amount * 100))
    def _on_yca(val: int) -> None:
        setattr(cfg, "y_curve_amount", val / 100.0)
        y_sparkline.set_params(curve_amount=val / 100.0)
        if on_change:
            on_change()
    yca_slider = _make_float_slider(0, 100, yca_init, _on_yca)
    yca_row, yca_val = _slider_row("Y amount", yca_slider, f"{cfg.y_curve_amount:.2f}")
    yca_slider.valueChanged.connect(lambda val: yca_val.setText(f"{val / 100:.2f}"))
    v.addWidget(yca_row)

    v.addStretch(1)
    return wrap
