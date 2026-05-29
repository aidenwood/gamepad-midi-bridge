"""Inspector renderers for TriggerConfig, StickConfig, TouchpadConfig, and Mapping globals.

Each renderer function receives a payload dict and returns a populated QWidget
whose form controls are live-wired to mutate the config dataclass in place.
Changes take effect immediately for the next bridge tick — no save/apply needed.

Payload shapes expected:
  Trigger:        { "kind": "trigger",        "label": str, "config": TriggerConfig, ... }
  Stick:          { "kind": "stick",           "label": str, "config": StickConfig,   ... }
  Touchpad:       { "kind": "touchpad",        "label": str, "config": TouchpadConfig, ... }
  MappingGlobals: { "kind": "mapping_globals", "label": str, "mapping": Mapping,
                    "on_change": Callable }
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
    QLineEdit,
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


def render_button_editor(payload: dict) -> QWidget:
    """Inspector editor for button MIDI note + channel + gate options.

    Form controls:
      - note spinbox (0..127) — maps to mapping.buttons[idx]
      - channel spinbox (-1 = default, 0..15) — maps to mapping.button_channels[idx]
      - gate_button spinbox (-1 = no gate, 0..31) — in mapping.button_configs[idx]
      - gate_release_value spinbox (0..127) — in mapping.button_configs[idx]

    Callbacks mutate the mapping object in place and emit on_change to persist.
    """
    from ..mapping import ButtonConfig

    idx = payload.get("index")
    note = payload.get("note")
    label = str(payload.get("label", f"Button {idx}"))
    channel = payload.get("channel", -1)
    mapping = payload.get("_mapping")  # Reference to the Mapping instance
    config = payload.get("config")  # ButtonConfig or None
    on_change = payload.get("on_change")

    # Try to extract int index
    try:
        idx_int = int(idx) if idx else 0
    except (ValueError, TypeError):
        idx_int = 0

    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)

    v.addWidget(_title(label))
    v.addWidget(_chip("button", "#ec4899", "rgba(236,72,153,0.12)", "rgba(236,72,153,0.3)"))
    v.addWidget(_divider())

    # ── MIDI assignment ──
    v.addWidget(_section("MIDI NOTE"))

    try:
        note_val = int(note) if note else 60
    except (ValueError, TypeError):
        note_val = 60

    def _on_note_changed(val: int) -> None:
        if mapping is not None:
            mapping.buttons[idx_int] = val
        if on_change:
            on_change()

    note_sb = _make_int_spinbox(0, 127, note_val, _on_note_changed)
    note_sb.setToolTip("MIDI note (0=C-1 … 60=C4 … 127=G9)")
    v.addWidget(_spinbox_row("MIDI Note", note_sb))

    # ── channel override ──
    v.addWidget(_divider())
    v.addWidget(_section("CHANNEL"))

    try:
        channel_val = int(channel) if channel != "-1" else -1
    except (ValueError, TypeError):
        channel_val = -1

    def _on_channel_changed(val: int) -> None:
        if mapping is not None:
            if val < 0:
                mapping.button_channels.pop(idx_int, None)
            else:
                mapping.button_channels[idx_int] = val
        if on_change:
            on_change()

    channel_sb = _make_int_spinbox(-1, 15, channel_val, _on_channel_changed)
    channel_sb.setSpecialValueText("default")
    channel_sb.setToolTip("Channel override: -1 = use default, 0-15 = specific channel")
    v.addWidget(_spinbox_row("Channel (−1 = default)", channel_sb))

    # ── gate ──
    v.addWidget(_divider())
    v.addWidget(_section("GATE"))

    gate_init = -1 if config is None or config.gate_button is None else config.gate_button

    def _on_gate_button_changed(val: int) -> None:
        if mapping is not None:
            if val < 0:
                # No gate — remove or clear
                mapping.button_configs.pop(idx_int, None)
            else:
                # Create or update ButtonConfig
                if idx_int not in mapping.button_configs:
                    mapping.button_configs[idx_int] = ButtonConfig()
                mapping.button_configs[idx_int].gate_button = val
        if on_change:
            on_change()

    gate_sb = _make_int_spinbox(-1, 31, gate_init, _on_gate_button_changed)
    gate_sb.setSpecialValueText("none")
    gate_sb.setToolTip("Button index that must be held for this button to send MIDI. -1 = no gate")
    v.addWidget(_spinbox_row("Gate button (−1 = off)", gate_sb))

    # Gate release value — only meaningful when gate is set
    gate_release_init = 0 if config is None else config.gate_release_value

    def _on_release_changed(val: int) -> None:
        if mapping is not None and idx_int in mapping.button_configs:
            mapping.button_configs[idx_int].gate_release_value = val
        if on_change:
            on_change()

    release_sb = _make_int_spinbox(0, 127, gate_release_init, _on_release_changed)
    release_sb.setToolTip("Velocity sent once when gate releases. 0 = note-off")
    release_sb.setEnabled(gate_init >= 0)

    # Wire gate spinbox to enable/disable release spinbox
    def _on_gate_change(val: int) -> None:
        release_sb.setEnabled(val >= 0)
        _on_gate_button_changed(val)

    try:
        gate_sb.valueChanged.disconnect()
    except Exception:
        pass
    gate_sb.valueChanged.connect(_on_gate_change)

    v.addWidget(_spinbox_row("Release velocity", release_sb))

    v.addStretch(1)
    return wrap


def render_hat_editor(payload: dict) -> QWidget:
    """Inspector editor for D-pad (hat) MIDI note + channel options.

    Form controls:
      - note spinbox (0..127) — maps to mapping.hats[key]
      - channel spinbox (-1 = default, 0..15) — maps to mapping.hat_channels[key]

    No gate options for hats (they're directional, not toggles).
    Callbacks mutate the mapping object in place and emit on_change to persist.
    """
    key = payload.get("index")
    note = payload.get("note")
    label = str(payload.get("label", f"D-pad {key}"))
    channel = payload.get("channel", -1)
    mapping = payload.get("_mapping")  # Reference to the Mapping instance
    on_change = payload.get("on_change")

    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)

    v.addWidget(_title(label))
    v.addWidget(_chip("d-pad", "#06b6d4", "rgba(6,182,212,0.12)", "rgba(6,182,212,0.3)"))
    v.addWidget(_divider())

    # ── MIDI assignment ──
    v.addWidget(_section("MIDI NOTE"))

    try:
        note_val = int(note) if note else 60
    except (ValueError, TypeError):
        note_val = 60

    def _on_note_changed(val: int) -> None:
        if mapping is not None:
            mapping.hats[key] = val
        if on_change:
            on_change()

    note_sb = _make_int_spinbox(0, 127, note_val, _on_note_changed)
    note_sb.setToolTip("MIDI note (0=C-1 … 60=C4 … 127=G9)")
    v.addWidget(_spinbox_row("MIDI Note", note_sb))

    # ── channel override ──
    v.addWidget(_divider())
    v.addWidget(_section("CHANNEL"))

    try:
        channel_val = int(channel) if channel != "-1" else -1
    except (ValueError, TypeError):
        channel_val = -1

    def _on_channel_changed(val: int) -> None:
        if mapping is not None:
            if val < 0:
                mapping.hat_channels.pop(key, None)
            else:
                mapping.hat_channels[key] = val
        if on_change:
            on_change()

    channel_sb = _make_int_spinbox(-1, 15, channel_val, _on_channel_changed)
    channel_sb.setSpecialValueText("default")
    channel_sb.setToolTip("Channel override: -1 = use default, 0-15 = specific channel")
    v.addWidget(_spinbox_row("Channel (−1 = default)", channel_sb))

    v.addStretch(1)
    return wrap


# ──────────────────────────────────────────────────────── mapping globals renderer

def render_mapping_globals(payload: dict) -> QWidget:
    """Inspector editor for all top-level Mapping config variables.

    Payload shape:
      { "kind": "mapping_globals", "label": str, "mapping": Mapping,
        "on_change": Callable[[], None] }

    Sections:
      CORE           — name, midi_channel, deadzone, poll_hz
      PORT           — port_name_override, auto_reconnect_enabled
      BATTERY ALERT  — enabled, threshold_percent, note, velocity, channel_override
      HAPTIC INPUT   — enabled, guard_feedback_loop, listen_channel
      SHIFT LAYER    — enabled, shift_button
      A/B COMPARE    — enabled, ab_compare_button, ab_b_preset_slug
      PROGRAM CHANGE — enabled, listen_channel

    Every control mutates the Mapping in place; on_change fires after each
    mutation so the autosave debounce in main_window picks it up.
    """
    from .. import presets as _presets

    mapping = payload.get("mapping")
    on_change = payload.get("on_change")

    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)

    # ── header ──────────────────────────────────────────────────────────────
    title_lbl = QLabel("Mapping settings")
    title_lbl.setStyleSheet("color: #f5f7fa; font-size: 15px; font-weight: 600;")
    v.addWidget(title_lbl)

    if mapping is not None:
        preset_sub = QLabel(mapping.name)
        preset_sub.setStyleSheet("color: #8a9099; font-size: 11px; margin-bottom: 2px;")
        v.addWidget(preset_sub)

    v.addWidget(_divider())

    if mapping is None:
        v.addWidget(QLabel("No mapping attached."))
        v.addStretch(1)
        return wrap

    def _fire() -> None:
        if on_change:
            on_change()

    # ── CORE ─────────────────────────────────────────────────────────────────
    v.addWidget(_section("CORE"))

    # name
    name_edit = QLineEdit(mapping.name)
    name_edit.setPlaceholderText("Preset name")
    name_edit.setStyleSheet(
        "background: #0e0f12; color: #c2c6cc; border: 1px solid #24262d; "
        "padding: 3px 6px;"
    )
    def _on_name(text: str) -> None:
        mapping.name = text
        _fire()
    name_edit.textChanged.connect(_on_name)
    v.addWidget(_spinbox_row("Name", name_edit))

    # midi_channel  0..15
    ch_sb = _make_int_spinbox(0, 15, mapping.midi_channel, lambda _v: None)
    ch_sb.setToolTip("Global MIDI channel (0–15). Individual controls can override.")
    def _on_ch(val: int) -> None:
        mapping.midi_channel = val
        _fire()
    ch_sb.valueChanged.connect(_on_ch)
    v.addWidget(_spinbox_row("MIDI channel", ch_sb))

    # deadzone  0.00..0.50
    dz_dsb = QDoubleSpinBox()
    dz_dsb.setRange(0.0, 0.5)
    dz_dsb.setSingleStep(0.01)
    dz_dsb.setDecimals(2)
    dz_dsb.setValue(mapping.deadzone)
    dz_dsb.setStyleSheet(
        "background: #0e0f12; color: #c2c6cc; border: 1px solid #24262d;"
    )
    dz_dsb.setToolTip("Post-calibration stick deadzone (0.00–0.50). 0.05 is a safe default.")
    def _on_dz(val: float) -> None:
        mapping.deadzone = val
        _fire()
    dz_dsb.valueChanged.connect(_on_dz)
    v.addWidget(_spinbox_row("Deadzone", dz_dsb))

    # poll_hz  50..200
    hz_sb = _make_int_spinbox(50, 200, mapping.poll_hz, lambda _v: None)
    hz_sb.setToolTip("Controller polling rate in Hz (50–200). 100 is the default.")
    def _on_hz(val: int) -> None:
        mapping.poll_hz = val
        _fire()
    hz_sb.valueChanged.connect(_on_hz)
    v.addWidget(_spinbox_row("Poll Hz", hz_sb))

    # ── PORT ──────────────────────────────────────────────────────────────────
    v.addWidget(_divider())
    v.addWidget(_section("PORT"))

    port_edit = QLineEdit(mapping.port_name_override or "")
    port_edit.setPlaceholderText("default")
    port_edit.setStyleSheet(
        "background: #0e0f12; color: #c2c6cc; border: 1px solid #24262d; "
        "padding: 3px 6px;"
    )
    port_edit.setToolTip(
        "Leave empty to use the default MIDI port. "
        "Set to a specific port name to override per-preset."
    )
    def _on_port(text: str) -> None:
        mapping.port_name_override = text or None
        _fire()
    port_edit.textChanged.connect(_on_port)
    v.addWidget(_spinbox_row("Port override", port_edit))

    reconnect_chk = QCheckBox()
    reconnect_chk.setChecked(mapping.auto_reconnect_enabled)
    reconnect_chk.setToolTip(
        "Show countdown overlay and retry when the controller disconnects mid-performance."
    )
    def _on_reconnect(state: int) -> None:
        mapping.auto_reconnect_enabled = bool(state)
        _fire()
    reconnect_chk.stateChanged.connect(_on_reconnect)
    v.addWidget(_check_row("Auto-reconnect", reconnect_chk))

    # ── BATTERY ALERT ─────────────────────────────────────────────────────────
    v.addWidget(_divider())
    v.addWidget(_section("BATTERY ALERT"))

    ba = mapping.battery_alert

    ba_enabled_chk = QCheckBox()
    ba_enabled_chk.setChecked(ba.enabled)
    ba_enabled_chk.setToolTip("Fire a MIDI note when DualSense battery drops below threshold.")
    def _on_ba_enabled(state: int) -> None:
        ba.enabled = bool(state)
        _fire()
    ba_enabled_chk.stateChanged.connect(_on_ba_enabled)
    v.addWidget(_check_row("Enabled", ba_enabled_chk))

    ba_thresh_sb = _make_int_spinbox(1, 100, ba.threshold_percent, lambda _v: None)
    ba_thresh_sb.setToolTip("Battery % that triggers the alert note.")
    def _on_ba_thresh(val: int) -> None:
        ba.threshold_percent = val
        _fire()
    ba_thresh_sb.valueChanged.connect(_on_ba_thresh)
    v.addWidget(_spinbox_row("Threshold %", ba_thresh_sb))

    ba_note_sb = _make_int_spinbox(0, 127, ba.note, lambda _v: None)
    ba_note_sb.setToolTip("MIDI note fired on low-battery event.")
    def _on_ba_note(val: int) -> None:
        ba.note = val
        _fire()
    ba_note_sb.valueChanged.connect(_on_ba_note)
    v.addWidget(_spinbox_row("Note", ba_note_sb))

    ba_vel_sb = _make_int_spinbox(0, 127, ba.velocity, lambda _v: None)
    ba_vel_sb.setToolTip("Velocity of the battery alert note.")
    def _on_ba_vel(val: int) -> None:
        ba.velocity = val
        _fire()
    ba_vel_sb.valueChanged.connect(_on_ba_vel)
    v.addWidget(_spinbox_row("Velocity", ba_vel_sb))

    _ba_ch_init = ba.channel_override if ba.channel_override is not None else -1
    ba_ch_sb = _make_int_spinbox(-1, 15, _ba_ch_init, lambda _v: None)
    ba_ch_sb.setSpecialValueText("default")
    ba_ch_sb.setToolTip("Channel for the battery alert note. -1 = use the global MIDI channel.")
    def _on_ba_ch(val: int) -> None:
        ba.channel_override = None if val < 0 else val
        _fire()
    ba_ch_sb.valueChanged.connect(_on_ba_ch)
    v.addWidget(_spinbox_row("Channel (−1 = default)", ba_ch_sb))

    # ── HAPTIC INPUT ──────────────────────────────────────────────────────────
    v.addWidget(_divider())
    v.addWidget(_section("HAPTIC INPUT"))

    hi = mapping.haptic_input

    hi_enabled_chk = QCheckBox()
    hi_enabled_chk.setChecked(hi.enabled)
    hi_enabled_chk.setToolTip(
        "Open a virtual MIDI input port and route incoming notes/CCs to DualSense "
        "adaptive-trigger haptics. Manage per-binding rules in the full editor."
    )
    def _on_hi_enabled(state: int) -> None:
        hi.enabled = bool(state)
        _fire()
    hi_enabled_chk.stateChanged.connect(_on_hi_enabled)
    v.addWidget(_check_row("Enabled", hi_enabled_chk))

    hi_guard_chk = QCheckBox()
    hi_guard_chk.setChecked(hi.guard_feedback_loop)
    hi_guard_chk.setToolTip(
        "Detect when the DAW echoes our outbound CCs back and drop them to prevent "
        "a feedback loop between the haptic input and MIDI output."
    )
    def _on_hi_guard(state: int) -> None:
        hi.guard_feedback_loop = bool(state)
        _fire()
    hi_guard_chk.stateChanged.connect(_on_hi_guard)
    v.addWidget(_check_row("Guard feedback loop", hi_guard_chk))

    hi_ch_sb = _make_int_spinbox(-1, 15, hi.listen_channel, lambda _v: None)
    hi_ch_sb.setSpecialValueText("any")
    hi_ch_sb.setToolTip("MIDI channel to listen on for haptic bindings. -1 = any channel.")
    def _on_hi_ch(val: int) -> None:
        hi.listen_channel = val
        _fire()
    hi_ch_sb.valueChanged.connect(_on_hi_ch)
    v.addWidget(_spinbox_row("Listen channel", hi_ch_sb))

    # ── SHIFT LAYER ───────────────────────────────────────────────────────────
    v.addWidget(_divider())
    v.addWidget(_section("SHIFT LAYER"))

    sl = mapping.shift_layer

    sl_enabled_chk = QCheckBox()
    sl_enabled_chk.setChecked(sl.enabled)
    sl_enabled_chk.setToolTip(
        "Hold the shift button to swap the active mapping for an overlay layer. "
        "Per-binding shift overrides are configured in the Mapping table."
    )
    def _on_sl_enabled(state: int) -> None:
        sl.enabled = bool(state)
        _fire()
    sl_enabled_chk.stateChanged.connect(_on_sl_enabled)
    v.addWidget(_check_row("Enabled", sl_enabled_chk))

    sl_btn_sb = _make_int_spinbox(-1, 31, sl.shift_button, lambda _v: None)
    sl_btn_sb.setSpecialValueText("(unset)")
    sl_btn_sb.setToolTip("Button index held to activate the shift layer. -1 = unset.")
    def _on_sl_btn(val: int) -> None:
        sl.shift_button = val
        _fire()
    sl_btn_sb.valueChanged.connect(_on_sl_btn)
    v.addWidget(_spinbox_row("Shift button", sl_btn_sb))

    # ── A/B COMPARE ───────────────────────────────────────────────────────────
    v.addWidget(_divider())
    v.addWidget(_section("A/B COMPARE"))

    ab_enabled_chk = QCheckBox()
    ab_enabled_chk.setChecked(mapping.ab_compare_enabled)
    ab_enabled_chk.setToolTip(
        "Hold the compare button to temporarily swap to the B preset. "
        "Releases snap back to this (A) mapping."
    )
    def _on_ab_enabled(state: int) -> None:
        mapping.ab_compare_enabled = bool(state)
        _fire()
    ab_enabled_chk.stateChanged.connect(_on_ab_enabled)
    v.addWidget(_check_row("Enabled", ab_enabled_chk))

    ab_btn_sb = _make_int_spinbox(-1, 31, mapping.ab_compare_button, lambda _v: None)
    ab_btn_sb.setSpecialValueText("(unset)")
    ab_btn_sb.setToolTip("Button held to activate the B preset.")
    def _on_ab_btn(val: int) -> None:
        mapping.ab_compare_button = val
        _fire()
    ab_btn_sb.valueChanged.connect(_on_ab_btn)
    v.addWidget(_spinbox_row("Compare button", ab_btn_sb))

    # B preset slug combo — populated from the preset library
    ab_combo = QComboBox()
    ab_combo.setStyleSheet(
        "background: #0e0f12; color: #c2c6cc; border: 1px solid #24262d;"
    )
    ab_combo.addItem("(none)", None)
    for slug in _presets.list_presets():
        ab_combo.addItem(slug, slug)
    _current_slug = mapping.ab_b_preset_slug or ""
    _ab_idx = ab_combo.findData(_current_slug) if _current_slug else 0
    ab_combo.setCurrentIndex(max(0, _ab_idx))
    def _on_ab_preset(_index: int) -> None:
        slug = ab_combo.currentData()
        mapping.ab_b_preset_slug = slug or None
        _fire()
    ab_combo.currentIndexChanged.connect(_on_ab_preset)
    v.addWidget(_combo_row("B preset", ab_combo))

    # ── PROGRAM CHANGE ────────────────────────────────────────────────────────
    v.addWidget(_divider())
    v.addWidget(_section("PROGRAM CHANGE"))

    pc = mapping.program_change

    pc_enabled_chk = QCheckBox()
    pc_enabled_chk.setChecked(pc.enabled)
    pc_enabled_chk.setToolTip(
        "When enabled, incoming MIDI Program Change messages load the bound preset. "
        "Add per-PC bindings in the Mapping table."
    )
    def _on_pc_enabled(state: int) -> None:
        pc.enabled = bool(state)
        _fire()
    pc_enabled_chk.stateChanged.connect(_on_pc_enabled)
    v.addWidget(_check_row("Enabled", pc_enabled_chk))

    pc_ch_sb = _make_int_spinbox(-1, 15, pc.listen_channel, lambda _v: None)
    pc_ch_sb.setSpecialValueText("any")
    pc_ch_sb.setToolTip(
        "MIDI channel to listen on for Program Change messages. -1 = any channel."
    )
    def _on_pc_ch(val: int) -> None:
        pc.listen_channel = val
        _fire()
    pc_ch_sb.valueChanged.connect(_on_pc_ch)
    v.addWidget(_spinbox_row("Listen channel", pc_ch_sb))

    v.addSpacing(8)
    hint = QLabel(
        "Per-PC bindings (PC# → preset slug) are managed in the Mapping editor table."
    )
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #5a606b; font-size: 10px; font-style: italic;")
    v.addWidget(hint)

    v.addStretch(1)
    return wrap
