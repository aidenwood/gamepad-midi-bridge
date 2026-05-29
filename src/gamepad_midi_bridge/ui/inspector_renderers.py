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
    mode_cb = _make_combo(TRIGGER_MODES, cfg.mode, lambda t: setattr(cfg, "mode", t))

    # ── ceiling ──
    ceil_enabled = cfg.mode == "ceiling"
    ceil_slider = _make_int_slider(0, 127, cfg.ceiling,
                                   lambda val: setattr(cfg, "ceiling", val),
                                   enabled=ceil_enabled)
    ceil_row, ceil_val = _slider_row("Ceiling CC", ceil_slider, str(cfg.ceiling))

    # ── latch threshold ──
    latch_enabled = cfg.mode == "latch"
    latch_init = int(round(cfg.latch_threshold * 100))
    latch_slider = _make_float_slider(0, 100, latch_init,
                                      lambda val: setattr(cfg, "latch_threshold", val / 100.0),
                                      enabled=latch_enabled)
    latch_row, latch_val = _slider_row("Latch threshold", latch_slider,
                                       f"{cfg.latch_threshold:.2f}")

    # Live value labels
    ceil_slider.valueChanged.connect(lambda val: ceil_val.setText(str(val)))
    latch_slider.valueChanged.connect(
        lambda val: latch_val.setText(f"{val / 100:.2f}")
    )

    # Enable/disable dependent sliders when mode changes
    def _on_mode_change(text: str) -> None:
        setattr(cfg, "mode", text)
        ceil_slider.setEnabled(text == "ceiling")
        latch_slider.setEnabled(text == "latch")

    # Disconnect the simple setter and reconnect with the richer one
    try:
        mode_cb.currentTextChanged.disconnect()
    except Exception:
        pass
    mode_cb.currentTextChanged.connect(_on_mode_change)

    v.addWidget(_combo_row("Mode", mode_cb))
    v.addWidget(ceil_row)
    v.addWidget(latch_row)

    # ── gate ──
    v.addWidget(_divider())
    v.addWidget(_section("GATE"))

    # gate_button: -1 means "no gate" in the UI (maps to None in the dataclass)
    gate_init = -1 if cfg.gate_button is None else cfg.gate_button

    def _on_gate_button(val: int) -> None:
        cfg.gate_button = None if val < 0 else val

    gate_sb = _make_int_spinbox(-1, 31, gate_init, _on_gate_button)
    gate_sb.setSpecialValueText("none")
    v.addWidget(_spinbox_row("Gate button (−1 = off)", gate_sb))

    release_slider = _make_int_slider(0, 127, cfg.gate_release_value,
                                      lambda val: setattr(cfg, "gate_release_value", val))
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
    dz_slider = _make_float_slider(0, 50, dz_init,
                                   lambda val: setattr(cfg, "inner_deadzone", val / 100.0))
    dz_row, dz_val = _slider_row("Inner deadzone", dz_slider, f"{cfg.inner_deadzone:.2f}")
    dz_slider.valueChanged.connect(lambda val: dz_val.setText(f"{val / 100:.2f}"))
    v.addWidget(dz_row)

    oc_init = int(round(cfg.outer_clamp * 100))
    oc_slider = _make_float_slider(0, 50, oc_init,
                                   lambda val: setattr(cfg, "outer_clamp", val / 100.0))
    oc_row, oc_val = _slider_row("Outer clamp", oc_slider, f"{cfg.outer_clamp:.2f}")
    oc_slider.valueChanged.connect(lambda val: oc_val.setText(f"{val / 100:.2f}"))
    v.addWidget(oc_row)

    # ── curve ──
    v.addWidget(_divider())
    v.addWidget(_section("RESPONSE CURVE"))

    curve_cb = _make_combo(_CURVES, cfg.curve, lambda t: setattr(cfg, "curve", t))
    v.addWidget(_combo_row("Curve", curve_cb))

    ca_init = int(round(cfg.curve_amount * 100))
    ca_slider = _make_float_slider(0, 100, ca_init,
                                   lambda val: setattr(cfg, "curve_amount", val / 100.0))
    ca_row, ca_val = _slider_row("Curve amount", ca_slider, f"{cfg.curve_amount:.2f}")
    ca_slider.valueChanged.connect(lambda val: ca_val.setText(f"{val / 100:.2f}"))
    v.addWidget(ca_row)

    # ── polar ──
    v.addWidget(_divider())
    v.addWidget(_section("POLAR MODE"))

    polar_chk = QCheckBox()
    polar_chk.setChecked(cfg.polar_mode)

    angle_sb = _make_int_spinbox(0, 127, cfg.polar_angle_cc,
                                 lambda val: setattr(cfg, "polar_angle_cc", val))
    mag_sb = _make_int_spinbox(0, 127, cfg.polar_mag_cc,
                               lambda val: setattr(cfg, "polar_mag_cc", val))

    # Enable CC spinboxes only when polar mode is on
    angle_sb.setEnabled(cfg.polar_mode)
    mag_sb.setEnabled(cfg.polar_mode)

    def _on_polar(state: int) -> None:
        on = bool(state)
        cfg.polar_mode = on
        angle_sb.setEnabled(on)
        mag_sb.setEnabled(on)

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

    mode_cb = _make_combo(("absolute", "relative"), cfg.mode,
                          lambda t: setattr(cfg, "mode", t))
    v.addWidget(_combo_row("Mode", mode_cb))

    arm_chk = QCheckBox()
    arm_chk.setChecked(cfg.click_to_arm)
    arm_chk.stateChanged.connect(lambda s: setattr(cfg, "click_to_arm", bool(s)))
    v.addWidget(_check_row("Click to arm", arm_chk))

    # ── deadzone ──
    v.addWidget(_divider())
    v.addWidget(_section("DEADZONE"))

    dz_init = int(round(cfg.inner_deadzone * 100))
    dz_slider = _make_float_slider(0, 49, dz_init,
                                   lambda val: setattr(cfg, "inner_deadzone", val / 100.0))
    dz_row, dz_val = _slider_row("Inner deadzone", dz_slider, f"{cfg.inner_deadzone:.2f}")
    dz_slider.valueChanged.connect(lambda val: dz_val.setText(f"{val / 100:.2f}"))
    v.addWidget(dz_row)

    # ── X curve ──
    v.addWidget(_divider())
    v.addWidget(_section("X AXIS CURVE"))

    xcurve_cb = _make_combo(_CURVES, cfg.x_curve, lambda t: setattr(cfg, "x_curve", t))
    v.addWidget(_combo_row("X curve", xcurve_cb))

    xca_init = int(round(cfg.x_curve_amount * 100))
    xca_slider = _make_float_slider(0, 100, xca_init,
                                    lambda val: setattr(cfg, "x_curve_amount", val / 100.0))
    xca_row, xca_val = _slider_row("X amount", xca_slider, f"{cfg.x_curve_amount:.2f}")
    xca_slider.valueChanged.connect(lambda val: xca_val.setText(f"{val / 100:.2f}"))
    v.addWidget(xca_row)

    # ── Y curve ──
    v.addWidget(_divider())
    v.addWidget(_section("Y AXIS CURVE"))

    ycurve_cb = _make_combo(_CURVES, cfg.y_curve, lambda t: setattr(cfg, "y_curve", t))
    v.addWidget(_combo_row("Y curve", ycurve_cb))

    yca_init = int(round(cfg.y_curve_amount * 100))
    yca_slider = _make_float_slider(0, 100, yca_init,
                                    lambda val: setattr(cfg, "y_curve_amount", val / 100.0))
    yca_row, yca_val = _slider_row("Y amount", yca_slider, f"{cfg.y_curve_amount:.2f}")
    yca_slider.valueChanged.connect(lambda val: yca_val.setText(f"{val / 100:.2f}"))
    v.addWidget(yca_row)

    v.addStretch(1)
    return wrap
