"""Settings tab — MIDI channel, deadzone, poll rate, calibrate button.

These are free-tier features; the heavier customisation lives in the mapping editor.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

import json

from ..license import is_pro
from ..mapping import Mapping
from ..midi_input import INPUT_PORT_NAME
from ..paths import config_path
from ..updater import set_opt_in as set_update_opt_in
from .. import telemetry
from ..crash_reporter import export_bundle
from .haptic_input_dialog import HapticInputDialog


def _read_update_opt_in() -> bool:
    path = config_path()
    if not path.exists():
        return True
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("check_for_updates", True))
    except Exception:
        return True


def _read_multi_mode() -> str:
    """Persisted "Active controllers" choice — defaults to off so the V1.1
    single-controller flow is preserved for everyone, free or Pro."""
    path = config_path()
    if not path.exists():
        return "off"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get(
            "multi_controller_mode", "off",
        ))
    except Exception:
        return "off"


def _write_multi_mode(mode: str) -> None:
    path = config_path()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["multi_controller_mode"] = mode
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


class SettingsPanel(QWidget):
    settings_changed = Signal(Mapping)
    recalibrate_clicked = Signal()
    multi_mode_changed = Signal(str)  # "off" | "auto" | "force_two"

    # Stored on the user's config file so the choice persists across launches.
    _MULTI_MODE_KEY = "multi_controller_mode"
    _MULTI_MODE_LABELS = [
        ("Off (single controller)", "off"),
        ("Auto (use both if Pro)",  "auto"),
        ("Force two (Pro-only)",    "force_two"),
    ]

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

        # Multi-controller group — Pro feature. Lives near the MIDI block so
        # users discover it next to the channel selector.
        pro = is_pro()
        pro_suffix = "" if pro else " — Pro"
        multi_group = QGroupBox(f"Multi-controller{pro_suffix}")
        multi_form = QFormLayout(multi_group)
        self._multi_mode = QComboBox()
        for label, _ in self._MULTI_MODE_LABELS:
            self._multi_mode.addItem(label)
        current_mode = _read_multi_mode()
        for i, (_, value) in enumerate(self._MULTI_MODE_LABELS):
            if value == current_mode:
                self._multi_mode.setCurrentIndex(i)
                break
        self._multi_mode.currentIndexChanged.connect(self._on_multi_mode_changed)
        multi_form.addRow("Active controllers", self._multi_mode)
        multi_note = QLabel(
            "Auto turns on a second slot when a second controller is "
            "detected. Each slot gets its own MIDI port + channel."
        )
        multi_note.setStyleSheet("color: #5a606b; font-size: 11px;")
        multi_note.setWordWrap(True)
        multi_form.addRow(multi_note)
        multi_group.setEnabled(pro)

        # Stick corners group — Pro feature, edge-quantized stick buttons.
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

        self._touchpad_two_finger = QCheckBox(
            "Two-finger mode (send 2nd finger to CC 18/19)"
        )
        self._touchpad_two_finger.setChecked(mapping.touchpad.two_finger)
        self._touchpad_two_finger.toggled.connect(self._emit)
        touchpad_form.addRow(self._touchpad_two_finger)

        # Adaptive triggers (DualSense L2/R2 force-feedback) — Pro feature.
        haptics_group = QGroupBox(f"Adaptive triggers{pro_suffix}")
        haptics_form = QFormLayout(haptics_group)
        self._l2_effect = self._build_effect_combo(mapping.l2_haptic_effect)
        haptics_form.addRow("L2 feel", self._l2_effect)
        self._r2_effect = self._build_effect_combo(mapping.r2_haptic_effect)
        haptics_form.addRow("R2 feel", self._r2_effect)

        # Haptic-in (incoming MIDI → trigger pulses). Headline V1.1c feature.
        self._haptic_in_enabled = QCheckBox("Respond to incoming MIDI (haptic-in)")
        self._haptic_in_enabled.setChecked(mapping.haptic_input.enabled)
        self._haptic_in_enabled.toggled.connect(self._emit)
        haptics_form.addRow(self._haptic_in_enabled)

        port_hint = QLabel(
            f"Listen port: <code>{INPUT_PORT_NAME}</code> — point your DAW's "
            "MIDI output here."
        )
        port_hint.setTextFormat(Qt.RichText)
        port_hint.setStyleSheet("color: #5a606b; font-size: 11px;")
        port_hint.setWordWrap(True)
        haptics_form.addRow(port_hint)

        bindings_row = QHBoxLayout()
        manage_btn = QPushButton("Manage bindings…")
        manage_btn.clicked.connect(self._open_haptic_bindings_dialog)
        bindings_row.addWidget(manage_btn)
        bindings_row.addStretch(1)
        haptics_form.addRow(bindings_row)

        # OSC output — Pro feature, lives alongside the MIDI port.
        osc_group = QGroupBox(f"OSC output{pro_suffix}")
        osc_form = QFormLayout(osc_group)
        self._osc_enabled = QCheckBox("Send OSC packets alongside MIDI")
        self._osc_enabled.setChecked(mapping.osc.enabled)
        self._osc_enabled.toggled.connect(self._emit)
        osc_form.addRow(self._osc_enabled)

        self._osc_mode = QComboBox()
        for label, value in (("Alongside MIDI", "alongside"), ("OSC only", "only")):
            self._osc_mode.addItem(label, value)
        idx = max(0, [self._osc_mode.itemData(i) for i in range(self._osc_mode.count())]
                     .index(mapping.osc.mode) if mapping.osc.mode in
                     ("alongside", "only") else 0)
        self._osc_mode.setCurrentIndex(idx)
        self._osc_mode.currentIndexChanged.connect(self._emit)
        osc_form.addRow("Mode", self._osc_mode)

        self._osc_host = QLineEdit(mapping.osc.host)
        self._osc_host.setPlaceholderText("127.0.0.1")
        self._osc_host.editingFinished.connect(self._emit)
        osc_form.addRow("Host", self._osc_host)

        self._osc_port = QSpinBox()
        self._osc_port.setRange(1, 65535)
        self._osc_port.setValue(mapping.osc.port)
        self._osc_port.valueChanged.connect(self._emit)
        osc_form.addRow("Port", self._osc_port)

        osc_note = QLabel(
            "Address-per-control mapping lives in your preset JSON for now. "
            "Resolume listens on 7000 by default; TouchDesigner / MadMapper "
            "are user-configured."
        )
        osc_note.setStyleSheet("color: #5a606b; font-size: 11px;")
        osc_note.setWordWrap(True)
        osc_form.addRow(osc_note)

        ping_btn = QPushButton("Send /gmb/ping (test the route)")
        ping_btn.clicked.connect(self._on_osc_ping)
        osc_form.addRow(ping_btn)

        # Privacy / telemetry — opt-in only, never gated.
        privacy_group = QGroupBox("Privacy")
        privacy_form = QFormLayout(privacy_group)
        self._check_updates = QCheckBox("Check for updates on startup")
        self._check_updates.setChecked(_read_update_opt_in())
        self._check_updates.toggled.connect(self._on_update_opt_changed)
        privacy_form.addRow(self._check_updates)

        self._anon_stats = QCheckBox("Send anonymous usage stats (opt-in)")
        self._anon_stats.setChecked(telemetry.is_enabled())
        self._anon_stats.toggled.connect(self._on_telemetry_opt_changed)
        privacy_form.addRow(self._anon_stats)

        privacy_note = QLabel(
            "Updates check fires once per launch, no personal data. "
            "Usage stats are off by default and never include preset content."
        )
        privacy_note.setStyleSheet("color: #5a606b; font-size: 11px;")
        privacy_note.setWordWrap(True)
        privacy_form.addRow(privacy_note)

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
        
        # Export crash bundle button
        export_row = QHBoxLayout()
        export_btn = QPushButton("Export crash bundle")
        export_btn.clicked.connect(self._on_export_bundle)
        export_row.addWidget(export_btn)
        export_row.addStretch(1)
        calib_layout.addLayout(export_row)

        outer.addWidget(midi_group)
        outer.addWidget(multi_group)
        outer.addWidget(input_group)
        outer.addWidget(corners_group)
        outer.addWidget(touchpad_group)
        outer.addWidget(haptics_group)
        outer.addWidget(osc_group)
        outer.addWidget(privacy_group)
        outer.addWidget(calib_group)
        outer.addStretch(1)

        # Gate Pro-only groups when no license is active.
        corners_group.setEnabled(pro)
        touchpad_group.setEnabled(pro)
        haptics_group.setEnabled(pro)
        osc_group.setEnabled(pro)

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
        tp.two_finger = self._touchpad_two_finger.isChecked()

        # Adaptive-trigger effects.
        self._mapping.l2_haptic_effect = self._EFFECT_LABELS[self._l2_effect.currentIndex()][1]
        self._mapping.r2_haptic_effect = self._EFFECT_LABELS[self._r2_effect.currentIndex()][1]

        # Haptic-in enabled flag — bindings are edited via dialog, not here.
        self._mapping.haptic_input.enabled = self._haptic_in_enabled.isChecked()

        # OSC output.
        osc = self._mapping.osc
        osc.enabled = self._osc_enabled.isChecked()
        osc.mode = self._osc_mode.currentData() or "alongside"
        osc.host = self._osc_host.text().strip() or "127.0.0.1"
        osc.port = self._osc_port.value()

        self.settings_changed.emit(self._mapping)

    def _open_haptic_bindings_dialog(self) -> None:
        """Open the bindings editor. Mutates the live mapping in place on
        OK then re-emits settings_changed so the bridge picks the new list
        up without a restart."""
        dlg = HapticInputDialog(self._mapping.haptic_input, parent=self)
        if dlg.exec():
            self._mapping.haptic_input.bindings = dlg.bindings()
            self._mapping.haptic_input.listen_channel = dlg.listen_channel()
            self.settings_changed.emit(self._mapping)

    def _on_osc_ping(self) -> None:
        from ..osc_backend import OscSender
        host = self._osc_host.text().strip() or "127.0.0.1"
        port = self._osc_port.value()
        s = OscSender(host=host, port=port)
        ok = s.ping()
        s.close()
        from PySide6.QtWidgets import QMessageBox
        if ok:
            QMessageBox.information(
                self, "OSC ping sent",
                f"Sent /gmb/ping → {host}:{port}\n\n"
                "Check Resolume's OSC monitor (Preferences → OSC → "
                "Input devices) or TouchDesigner's OSC In CHOP to "
                "confirm receipt.",
            )
        else:
            QMessageBox.warning(self, "OSC ping failed",
                                f"Couldn't send to {host}:{port}.")

    def _on_update_opt_changed(self, checked: bool) -> None:
        if self._building:
            return
        set_update_opt_in(checked)

    def _on_telemetry_opt_changed(self, checked: bool) -> None:
        if self._building:
            return
        telemetry.set_enabled(checked)

    def _on_multi_mode_changed(self, _idx: int) -> None:
        if self._building:
            return
        mode = self._MULTI_MODE_LABELS[self._multi_mode.currentIndex()][1]
        _write_multi_mode(mode)
        self.multi_mode_changed.emit(mode)

    def current_multi_mode(self) -> str:
        return self._MULTI_MODE_LABELS[self._multi_mode.currentIndex()][1]

    @staticmethod
    def _apply_corner_combo(combo: QComboBox, cfg) -> None:
        idx = combo.currentIndex()
        if idx == 0:
            cfg.enabled = False
            return
        cfg.enabled = True
        cfg.n = {1: 4, 2: 8, 3: 16}[idx]
        cfg.ensure_notes()

    def _on_export_bundle(self) -> None:
        """Export a crash bundle and show confirmation."""
        try:
            bundle_path = export_bundle()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Crash bundle exported",
                f"Bundle saved to:\n{bundle_path}\n\nAttach this file to a bug report."
            )
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Export failed",
                f"Could not export crash bundle:\n{e}"
            )
