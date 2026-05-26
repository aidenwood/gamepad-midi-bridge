"""Settings tab — MIDI channel, deadzone, poll rate, calibrate button.

These are free-tier features; the heavier customisation lives in the mapping editor.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..license import is_pro
from ..mapping import Mapping


class SettingsPanel(QWidget):
    settings_changed = Signal(Mapping)
    recalibrate_clicked = Signal()

    def __init__(self, mapping: Mapping, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mapping = mapping
        self._building = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(16)

        # MIDI group
        midi_group = QGroupBox("MIDI")
        midi_form = QFormLayout(midi_group)
        self._channel = QSpinBox()
        self._channel.setRange(1, 16)
        self._channel.setValue(mapping.midi_channel + 1)
        self._channel.valueChanged.connect(self._emit)
        midi_form.addRow("Channel", self._channel)

        # Input group
        input_group = QGroupBox("Input")
        input_form = QFormLayout(input_group)
        self._deadzone = QDoubleSpinBox()
        self._deadzone.setRange(0.0, 0.5)
        self._deadzone.setSingleStep(0.01)
        self._deadzone.setDecimals(2)
        self._deadzone.setValue(mapping.deadzone)
        self._deadzone.valueChanged.connect(self._emit)
        input_form.addRow("Stick deadzone", self._deadzone)

        self._poll = QSpinBox()
        self._poll.setRange(30, 500)
        self._poll.setSingleStep(10)
        self._poll.setValue(mapping.poll_hz)
        self._poll.setSuffix(" Hz")
        self._poll.valueChanged.connect(self._emit)
        input_form.addRow("Poll rate", self._poll)

        # Stick corners group — Pro feature, edge-quantized stick buttons.
        pro_suffix = "" if is_pro() else " — Pro"
        corners_group = QGroupBox(f"Stick corners{pro_suffix}")
        corners_form = QFormLayout(corners_group)
        self._left_corners = self._build_corner_combo(mapping.left_stick_corners)
        corners_form.addRow("Left stick corners", self._left_corners)
        self._right_corners = self._build_corner_combo(mapping.right_stick_corners)
        corners_form.addRow("Right stick corners", self._right_corners)

        # Touchpad group — Pro feature, XY surface → two CCs.
        touchpad_group = QGroupBox(f"Touchpad{pro_suffix}")
        touchpad_form = QFormLayout(touchpad_group)
        self._touchpad_enabled = QCheckBox("Enable touchpad as XY MIDI surface")
        self._touchpad_enabled.setChecked(mapping.touchpad.enabled)
        self._touchpad_enabled.toggled.connect(self._emit)
        touchpad_form.addRow(self._touchpad_enabled)

        self._touchpad_x_cc = QSpinBox()
        self._touchpad_x_cc.setRange(0, 127)
        self._touchpad_x_cc.setValue(mapping.touchpad.x_cc)
        self._touchpad_x_cc.valueChanged.connect(self._emit)
        touchpad_form.addRow("X CC", self._touchpad_x_cc)

        self._touchpad_y_cc = QSpinBox()
        self._touchpad_y_cc.setRange(0, 127)
        self._touchpad_y_cc.setValue(mapping.touchpad.y_cc)
        self._touchpad_y_cc.valueChanged.connect(self._emit)
        touchpad_form.addRow("Y CC", self._touchpad_y_cc)

        self._touchpad_require_contact = QCheckBox("Only send while finger is on pad")
        self._touchpad_require_contact.setChecked(mapping.touchpad.require_contact)
        self._touchpad_require_contact.toggled.connect(self._emit)
        touchpad_form.addRow(self._touchpad_require_contact)

        # Adaptive triggers (DualSense L2/R2 force-feedback) — Pro feature.
        haptics_group = QGroupBox(f"Adaptive triggers{pro_suffix}")
        haptics_form = QFormLayout(haptics_group)
        self._l2_effect = self._build_effect_combo(mapping.l2_haptic_effect)
        haptics_form.addRow("L2 feel", self._l2_effect)
        self._r2_effect = self._build_effect_combo(mapping.r2_haptic_effect)
        haptics_form.addRow("R2 feel", self._r2_effect)

        # Calibration group
        calib_group = QGroupBox("Calibration")
        calib_layout = QVBoxLayout(calib_group)
        calib_layout.addWidget(QLabel(
            "Re-runs the auto-calibration sweep. Useful if you swap controllers "
            "or your sticks start drifting mid-set."
        ))
        row = QHBoxLayout()
        recalib = QPushButton("Re-calibrate sticks")
        recalib.clicked.connect(self.recalibrate_clicked.emit)
        row.addWidget(recalib)
        row.addStretch(1)
        calib_layout.addLayout(row)

        outer.addWidget(midi_group)
        outer.addWidget(input_group)
        outer.addWidget(corners_group)
        outer.addWidget(touchpad_group)
        outer.addWidget(haptics_group)
        outer.addWidget(calib_group)
        outer.addStretch(1)

        # Gate Pro-only groups when no license is active.
        pro = is_pro()
        corners_group.setEnabled(pro)
        touchpad_group.setEnabled(pro)
        haptics_group.setEnabled(pro)

        self._building = False

    # Adaptive-trigger effects in the order shown to the user. Stored on the
    # mapping as lowercase strings; "off" round-trips to None internally.
    _EFFECT_LABELS = [
        ("Off",       None),
        ("Feedback",  "feedback"),
        ("Weapon",    "weapon"),
        ("Vibration", "vibration"),
        ("Bow",       "bow"),
        ("Galloping", "galloping"),
        ("Machine",   "machine"),
    ]

    def _build_effect_combo(self, current_value: Optional[str]) -> QComboBox:
        combo = QComboBox()
        for label, _ in self._EFFECT_LABELS:
            combo.addItem(label)
        # Find the index matching the current mapping value.
        for i, (_, value) in enumerate(self._EFFECT_LABELS):
            if value == current_value:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self._emit)
        return combo

    def _build_corner_combo(self, cfg) -> QComboBox:
        """Dropdown for stick-corner mode. Index → (enabled, n)."""
        combo = QComboBox()
        combo.addItem("Off")
        combo.addItem("4 corners")
        combo.addItem("8 corners")
        combo.addItem("16 corners")
        if cfg.enabled:
            combo.setCurrentIndex({4: 1, 8: 2, 16: 3}.get(cfg.n, 2))
        else:
            combo.setCurrentIndex(0)
        combo.currentIndexChanged.connect(self._emit)
        return combo

    def _emit(self, *_args) -> None:
        if self._building:
            return
        self._mapping.midi_channel = self._channel.value() - 1
        self._mapping.deadzone = self._deadzone.value()
        self._mapping.poll_hz = self._poll.value()

        # Stick corners — index 0 = Off, 1..3 = 4/8/16 corners.
        self._apply_corner_combo(self._left_corners, self._mapping.left_stick_corners)
        self._apply_corner_combo(self._right_corners, self._mapping.right_stick_corners)

        # Touchpad XY surface.
        tp = self._mapping.touchpad
        tp.enabled = self._touchpad_enabled.isChecked()
        tp.x_cc = self._touchpad_x_cc.value()
        tp.y_cc = self._touchpad_y_cc.value()
        tp.require_contact = self._touchpad_require_contact.isChecked()

        # Adaptive-trigger effects.
        self._mapping.l2_haptic_effect = self._EFFECT_LABELS[self._l2_effect.currentIndex()][1]
        self._mapping.r2_haptic_effect = self._EFFECT_LABELS[self._r2_effect.currentIndex()][1]

        self.settings_changed.emit(self._mapping)

    @staticmethod
    def _apply_corner_combo(combo: QComboBox, cfg) -> None:
        idx = combo.currentIndex()
        if idx == 0:
            cfg.enabled = False
            return
        cfg.enabled = True
        cfg.n = {1: 4, 2: 8, 3: 16}[idx]
        cfg.ensure_notes()
