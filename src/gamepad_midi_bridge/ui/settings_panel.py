"""Settings tab — restructured into five clear QGroupBox sections.

Sections:
  1. APPEARANCE      — theme, font size, reduce motion
  2. AUDIO + MIDI    — channel, poll rate, feedback-loop guard
  3. CONTROLLER      — auto-reconnect, test wizard, deadzone
  4. PRIVACY         — telemetry, update-check, license info, export crash bundle
  5. DANGER ZONE     — clear snapshots, clear autosaves, reset to defaults, sign out
"""
from __future__ import annotations

import json
import shutil
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .primitives import UIButton, UILabel, UIInput, UISpinBox, UIDoubleSpinBox

from ..license import is_pro, state as license_state, deactivate as license_deactivate
from ..mapping import Mapping
from ..midi_input import INPUT_PORT_NAME
from ..paths import config_path, user_data_dir
from ..updater import set_opt_in as set_update_opt_in, set_channel as set_update_channel, _get_channel as get_update_channel
from .. import telemetry
from ..crash_reporter import export_bundle
from .haptic_input_dialog import HapticInputDialog
from .theme import apply_theme

_QSETTINGS_ORG = "ucmd"
_QSETTINGS_APP = "gamepad-midi-bridge"


def _read_update_opt_in() -> bool:
    path = config_path()
    if not path.exists():
        return True
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("check_for_updates", True))
    except Exception:
        return True


def _read_multi_mode() -> str:
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


def _note(text: str) -> UILabel:
    return UILabel(text, variant="caption")


class SettingsPanel(QWidget):
    settings_changed = Signal(Mapping)
    recalibrate_clicked = Signal()
    multi_mode_changed = Signal(str)  # "off" | "auto" | "force_two"

    _MULTI_MODE_KEY = "multi_controller_mode"
    _MULTI_MODE_LABELS = [
        ("Off (single controller)", "off"),
        ("Auto (use both if Pro)",  "auto"),
        ("Force two (Pro-only)",    "force_two"),
    ]

    _EFFECT_LABELS = [
        ("Off",       None),
        ("Feedback",  "feedback"),
        ("Weapon",    "weapon"),
        ("Vibration", "vibration"),
        ("Bow",       "bow"),
        ("Galloping", "galloping"),
        ("Machine",   "machine"),
    ]

    _FONT_SIZES = [
        ("Small",  10),
        ("Medium", 12),
        ("Large",  14),
    ]

    _UPDATE_CHANNELS = [
        ("Stable", "stable"),
        ("Beta", "beta"),
        ("Dev", "dev"),
    ]

    def __init__(self, mapping: Mapping, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mapping = mapping
        self._building = True
        self._qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        self._control_label_cache: dict[QGroupBox, list[str]] = {}
        self._groups_in_order: list[QGroupBox] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── search bar ─────────────────────────────────────────────────────
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(20, 12, 20, 8)
        search_layout.setSpacing(0)

        self._search_input = UIInput("Search settings…")
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)
        root.addWidget(search_container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        root.addWidget(scroll)

        inner = QWidget()
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(16)
        scroll.setWidget(inner)

        pro = is_pro()
        pro_suffix = "" if pro else " — Pro"

        # ── 1. APPEARANCE ──────────────────────────────────────────────────
        app_group = QGroupBox("Appearance")
        app_form = QFormLayout(app_group)

        self._theme = QComboBox()
        self._theme.addItem("System", "system")
        self._theme.addItem("Dark",   "dark")
        self._theme.addItem("Light",  "light")
        for i in range(self._theme.count()):
            if self._theme.itemData(i) == mapping.theme:
                self._theme.setCurrentIndex(i)
                break
        self._theme.currentIndexChanged.connect(self._on_theme_changed)
        app_form.addRow("Theme", self._theme)

        self._font_size = QComboBox()
        saved_pt = int(self._qs.value("appearance/font_pt", 12))
        for label, pt in self._FONT_SIZES:
            self._font_size.addItem(label, pt)
        for i, (_, pt) in enumerate(self._FONT_SIZES):
            if pt == saved_pt:
                self._font_size.setCurrentIndex(i)
                break
        self._font_size.currentIndexChanged.connect(self._on_font_size_changed)
        app_form.addRow("Font size", self._font_size)

        self._reduce_motion = QCheckBox("Reduce motion / animations")
        self._reduce_motion.setChecked(
            self._qs.value("appearance/reduce_motion", False, type=bool)
        )
        self._reduce_motion.toggled.connect(self._on_reduce_motion_changed)
        app_form.addRow(self._reduce_motion)

        # ── 2. AUDIO + MIDI ────────────────────────────────────────────────
        midi_group = QGroupBox("Audio + MIDI")
        midi_form = QFormLayout(midi_group)

        self._channel = UISpinBox()
        self._channel.setRange(1, 16)
        self._channel.setValue(mapping.midi_channel + 1)
        self._channel.valueChanged.connect(self._emit)
        midi_form.addRow("Default MIDI channel", self._channel)

        self._poll = UISpinBox()
        self._poll.setRange(30, 500)
        self._poll.setSingleStep(10)
        self._poll.setValue(mapping.poll_hz)
        self._poll.setSuffix(" Hz")
        self._poll.valueChanged.connect(self._emit)
        midi_form.addRow("Default poll rate", self._poll)

        self._feedback_guard = QCheckBox("MIDI feedback-loop guard")
        self._feedback_guard.setChecked(mapping.haptic_input.guard_feedback_loop)
        self._feedback_guard.toggled.connect(self._emit)
        midi_form.addRow(self._feedback_guard)
        midi_form.addRow(_note(
            "Ignores incoming CCs that match what we just sent — prevents "
            "runaway loops when the DAW echoes back on port %r." % INPUT_PORT_NAME
        ))

        multi_group = QGroupBox("Multi-controller%s" % pro_suffix)
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
        multi_form.addRow(_note(
            "Auto turns on a second slot when a second controller is detected. "
            "Each slot gets its own MIDI port + channel."
        ))
        multi_group.setEnabled(pro)

        osc_group = QGroupBox("OSC output%s" % pro_suffix)
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

        self._osc_host = UIInput("127.0.0.1")
        self._osc_host.setText(mapping.osc.host)
        self._osc_host.editingFinished.connect(self._emit)
        osc_form.addRow("Host", self._osc_host)

        self._osc_port = UISpinBox()
        self._osc_port.setRange(1, 65535)
        self._osc_port.setValue(mapping.osc.port)
        self._osc_port.valueChanged.connect(self._emit)
        osc_form.addRow("Port", self._osc_port)

        osc_form.addRow(_note(
            "Address-per-control mapping lives in your preset JSON. "
            "Resolume listens on 7000 by default; TouchDesigner / MadMapper are user-configured."
        ))
        ping_btn = UIButton("Send /gmb/ping (test the route)", variant="secondary")
        ping_btn.clicked.connect(self._on_osc_ping)
        osc_form.addRow(ping_btn)
        osc_group.setEnabled(pro)

        # ── 3. CONTROLLER ──────────────────────────────────────────────────
        ctrl_group = QGroupBox("Controller")
        ctrl_form = QFormLayout(ctrl_group)

        self._auto_reconnect = QCheckBox("Auto-reconnect on disconnect")
        self._auto_reconnect.setChecked(mapping.auto_reconnect_enabled)
        self._auto_reconnect.toggled.connect(self._emit)
        ctrl_form.addRow(self._auto_reconnect)

        self._test_wizard = QCheckBox("Run controller-test wizard on first connect")
        self._test_wizard.setChecked(
            self._qs.value("controller/test_wizard_on_first_connect", True, type=bool)
        )
        self._test_wizard.toggled.connect(self._on_test_wizard_changed)
        ctrl_form.addRow(self._test_wizard)

        dz_row = QHBoxLayout()
        self._deadzone_slider = QSlider(Qt.Orientation.Horizontal)
        self._deadzone_slider.setRange(0, 200)   # /1000 → 0..0.200
        self._deadzone_slider.setValue(int(mapping.deadzone * 1000))
        self._deadzone_spin = UIDoubleSpinBox()
        self._deadzone_spin.setRange(0.0, 0.20)
        self._deadzone_spin.setSingleStep(0.005)
        self._deadzone_spin.setDecimals(3)
        self._deadzone_spin.setValue(mapping.deadzone)
        self._deadzone_spin.setFixedWidth(80)
        self._deadzone_slider.valueChanged.connect(
            lambda v: self._deadzone_spin.setValue(v / 1000.0)
        )
        self._deadzone_spin.valueChanged.connect(
            lambda v: self._deadzone_slider.setValue(int(v * 1000))
        )
        self._deadzone_spin.valueChanged.connect(self._emit)
        dz_row.addWidget(self._deadzone_slider)
        dz_row.addWidget(self._deadzone_spin)
        ctrl_form.addRow("Default deadzone", dz_row)

        corners_group = QGroupBox("Stick corners%s" % pro_suffix)
        corners_form = QFormLayout(corners_group)
        self._left_corners = self._build_corner_combo(mapping.left_stick_corners)
        corners_form.addRow("Left stick corners", self._left_corners)
        self._right_corners = self._build_corner_combo(mapping.right_stick_corners)
        corners_form.addRow("Right stick corners", self._right_corners)
        corners_group.setEnabled(pro)

        touchpad_group = QGroupBox("Touchpad%s" % pro_suffix)
        touchpad_form = QFormLayout(touchpad_group)
        self._touchpad_enabled = QCheckBox("Enable touchpad as XY MIDI surface")
        self._touchpad_enabled.setChecked(mapping.touchpad.enabled)
        self._touchpad_enabled.toggled.connect(self._emit)
        touchpad_form.addRow(self._touchpad_enabled)

        self._touchpad_x_cc = UISpinBox()
        self._touchpad_x_cc.setRange(0, 127)
        self._touchpad_x_cc.setValue(mapping.touchpad.x_cc)
        self._touchpad_x_cc.valueChanged.connect(self._emit)
        touchpad_form.addRow("X CC", self._touchpad_x_cc)

        self._touchpad_y_cc = UISpinBox()
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
        touchpad_group.setEnabled(pro)

        haptics_group = QGroupBox("Adaptive triggers%s" % pro_suffix)
        haptics_form = QFormLayout(haptics_group)
        self._l2_effect = self._build_effect_combo(mapping.l2_haptic_effect)
        haptics_form.addRow("L2 feel", self._l2_effect)
        self._r2_effect = self._build_effect_combo(mapping.r2_haptic_effect)
        haptics_form.addRow("R2 feel", self._r2_effect)

        self._haptic_in_enabled = QCheckBox("Respond to incoming MIDI (haptic-in)")
        self._haptic_in_enabled.setChecked(mapping.haptic_input.enabled)
        self._haptic_in_enabled.toggled.connect(self._emit)
        haptics_form.addRow(self._haptic_in_enabled)

        port_hint = UILabel(
            "Listen port: <code>%s</code> — point your DAW's MIDI output here." % INPUT_PORT_NAME,
            variant="caption",
        )
        port_hint.setTextFormat(Qt.TextFormat.RichText)
        haptics_form.addRow(port_hint)

        bindings_row = QHBoxLayout()
        manage_btn = UIButton("Manage bindings…", variant="secondary")
        manage_btn.clicked.connect(self._open_haptic_bindings_dialog)
        bindings_row.addWidget(manage_btn)
        bindings_row.addStretch(1)
        haptics_form.addRow(bindings_row)
        haptics_group.setEnabled(pro)

        calib_group = QGroupBox("Calibration")
        calib_layout = QVBoxLayout(calib_group)
        calib_layout.addWidget(_note(
            "Re-runs the auto-calibration sweep. Useful if you swap controllers "
            "or your sticks start drifting mid-set."
        ))
        recalib_row = QHBoxLayout()
        recalib = UIButton("Re-calibrate sticks", variant="secondary")
        recalib.clicked.connect(self.recalibrate_clicked.emit)
        recalib_row.addWidget(recalib)
        recalib_row.addStretch(1)
        calib_layout.addLayout(recalib_row)

        # ── 4. PRIVACY ─────────────────────────────────────────────────────
        privacy_group = QGroupBox("Privacy")
        privacy_form = QFormLayout(privacy_group)

        self._anon_stats = QCheckBox("Send anonymous usage stats (opt-in)")
        self._anon_stats.setChecked(telemetry.is_enabled())
        self._anon_stats.toggled.connect(self._on_telemetry_opt_changed)
        privacy_form.addRow(self._anon_stats)

        self._check_updates = QCheckBox("Check for updates on startup")
        self._check_updates.setChecked(_read_update_opt_in())
        self._check_updates.toggled.connect(self._on_update_opt_changed)

        self._update_channel = QComboBox()
        for label, _ in self._UPDATE_CHANNELS:
            self._update_channel.addItem(label)
        current_channel = get_update_channel()
        for i, (label, ch) in enumerate(self._UPDATE_CHANNELS):
            if ch == current_channel:
                self._update_channel.setCurrentIndex(i)
                break
        self._update_channel.currentIndexChanged.connect(self._on_update_channel_changed)
        privacy_form.addRow("Update channel", self._update_channel)
        privacy_form.addRow(self._check_updates)

        privacy_form.addRow(_note(
            "Usage stats are off by default and never include preset content or "
            "controller serial numbers. Update checks fire once per launch — no "
            "personal data leaves the machine. Stable = releases only, Beta = beta/rc builds, Dev = all pre-releases."
        ))

        ls = license_state()
        if ls.is_pro and ls.email:
            lic_text = "License: Pro · %s" % ls.email
        elif ls.is_pro:
            lic_text = "License: Pro"
        else:
            lic_text = "License: Free tier"
        lic_label = UILabel(lic_text, variant="caption")
        privacy_form.addRow("", lic_label)

        export_row = QHBoxLayout()
        export_btn = UIButton("Export crash bundle…", variant="secondary")
        export_btn.clicked.connect(self._on_export_bundle)
        export_row.addWidget(export_btn)
        export_row.addStretch(1)
        privacy_form.addRow(export_row)

        # ── 5. DANGER ZONE ─────────────────────────────────────────────────
        danger_group = QGroupBox("Danger Zone")
        danger_form = QFormLayout(danger_group)
        danger_group.setStyleSheet(
            "QGroupBox { border: 1px solid #c0392b; border-radius: 4px; }"
            "QGroupBox::title { color: #c0392b; }"
        )

        clear_snaps_btn = UIButton("Clear all snapshots", variant="danger")
        clear_snaps_btn.clicked.connect(self._on_clear_snapshots)
        danger_form.addRow(clear_snaps_btn)

        clear_saves_btn = UIButton("Clear autosaves", variant="danger")
        clear_saves_btn.clicked.connect(self._on_clear_autosaves)
        danger_form.addRow(clear_saves_btn)

        reset_btn = UIButton("Reset to factory defaults", variant="danger")
        reset_btn.clicked.connect(self._on_reset_to_defaults)
        danger_form.addRow(reset_btn)

        sign_out_btn = UIButton("Sign out (deactivate license)", variant="danger")
        sign_out_btn.clicked.connect(self._on_sign_out)
        if not ls.is_pro:
            sign_out_btn.setEnabled(False)
        danger_form.addRow(sign_out_btn)

        # ── layout ─────────────────────────────────────────────────────────
        groups = [
            app_group, midi_group, multi_group, osc_group, ctrl_group,
            corners_group, touchpad_group, haptics_group, calib_group,
            privacy_group, danger_group
        ]
        for g in groups:
            outer.addWidget(g)
            self._groups_in_order.append(g)
        outer.addStretch(1)

        # ── populate label cache ──────────────────────────────────────────
        self._cache_control_labels()

        self._building = False

    # ── search filtering ─────────────────────────────────────────────────────

    def _cache_control_labels(self) -> None:
        """Extract all form labels from each group for search matching."""
        for group in self._groups_in_order:
            layout = group.layout()
            if not isinstance(layout, QFormLayout):
                # For non-form layouts (e.g., calib_group), collect checkbox/button text
                labels: list[str] = [group.title()]
                self._traverse_widgets(layout, labels)
                self._control_label_cache[group] = labels
            else:
                labels = [group.title()]
                # Extract form row labels
                for i in range(layout.rowCount()):
                    label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                    if label_item:
                        widget = label_item.widget()
                        if isinstance(widget, QLabel):
                            text = widget.text()
                            if text and not text.startswith("color:"):
                                labels.append(text)
                        elif isinstance(widget, QCheckBox):
                            labels.append(widget.text())
                    field_item = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                    if field_item:
                        widget = field_item.widget()
                        if isinstance(widget, QCheckBox):
                            labels.append(widget.text())
                self._control_label_cache[group] = labels

    def _traverse_widgets(self, layout, labels: list[str]) -> None:
        """Recursively extract text from widgets in a layout."""
        if layout is None:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, QCheckBox):
                    labels.append(widget.text())
                elif isinstance(widget, QPushButton):
                    labels.append(widget.text())
                elif isinstance(widget, QLabel):
                    text = widget.text()
                    if text and len(text) > 3:
                        labels.append(text)
                nested = item.layout()
                if nested:
                    self._traverse_widgets(nested, labels)

    def _on_search_changed(self, query: str) -> None:
        """Filter groups by matching label text."""
        query_lower = query.lower().strip()
        for group in self._groups_in_order:
            labels = self._control_label_cache.get(group, [])
            is_match = any(query_lower in label.lower() for label in labels)
            if query_lower == "":
                # Empty search: show everything normally
                group.setStyleSheet("")
                group.setGraphicsEffect(None)
            elif is_match:
                # Highlight matching group
                group.setStyleSheet(
                    "QGroupBox { border: 2px solid #1abc9c; border-radius: 4px; }"
                    "QGroupBox::title { font-weight: bold; color: #1abc9c; }"
                )
            else:
                # Dim non-matching group
                group.setStyleSheet(
                    "QGroupBox { border: 1px solid #bdc3c7; border-radius: 4px; opacity: 0.3; }"
                    "QGroupBox::title { color: #7f8c8d; }"
                )

    # ── combo builders ────────────────────────────────────────────────────────

    def _build_effect_combo(self, current_value: Optional[str]) -> QComboBox:
        combo = QComboBox()
        for label, _ in self._EFFECT_LABELS:
            combo.addItem(label)
        for i, (_, value) in enumerate(self._EFFECT_LABELS):
            if value == current_value:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self._emit)
        return combo

    def _build_corner_combo(self, cfg) -> QComboBox:
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

    # ── emit ──────────────────────────────────────────────────────────────────

    def _emit(self, *_args) -> None:
        if self._building:
            return
        m = self._mapping
        m.midi_channel = self._channel.value() - 1
        m.deadzone = self._deadzone_spin.value()
        m.poll_hz = self._poll.value()
        m.auto_reconnect_enabled = self._auto_reconnect.isChecked()

        self._apply_corner_combo(self._left_corners, m.left_stick_corners)
        self._apply_corner_combo(self._right_corners, m.right_stick_corners)

        tp = m.touchpad
        tp.enabled = self._touchpad_enabled.isChecked()
        tp.x_cc = self._touchpad_x_cc.value()
        tp.y_cc = self._touchpad_y_cc.value()
        tp.require_contact = self._touchpad_require_contact.isChecked()
        tp.two_finger = self._touchpad_two_finger.isChecked()

        m.l2_haptic_effect = self._EFFECT_LABELS[self._l2_effect.currentIndex()][1]
        m.r2_haptic_effect = self._EFFECT_LABELS[self._r2_effect.currentIndex()][1]

        m.haptic_input.enabled = self._haptic_in_enabled.isChecked()
        m.haptic_input.guard_feedback_loop = self._feedback_guard.isChecked()

        osc = m.osc
        osc.enabled = self._osc_enabled.isChecked()
        osc.mode = self._osc_mode.currentData() or "alongside"
        osc.host = self._osc_host.text().strip() or "127.0.0.1"
        osc.port = self._osc_port.value()

        self.settings_changed.emit(m)

    # ── change handlers ───────────────────────────────────────────────────────

    def _on_theme_changed(self, _idx: int) -> None:
        if self._building:
            return
        theme = self._theme.currentData()
        if theme:
            self._mapping.theme = theme
            app = QApplication.instance()
            if app:
                apply_theme(app, theme)
            self._qs.setValue("appearance/theme", theme)
            self._emit()

    def _on_font_size_changed(self, _idx: int) -> None:
        if self._building:
            return
        pt = self._font_size.currentData()
        self._qs.setValue("appearance/font_pt", pt)
        app = QApplication.instance()
        if app:
            f = app.font()
            f.setPointSize(pt)
            app.setFont(f)

    def _on_reduce_motion_changed(self, checked: bool) -> None:
        if self._building:
            return
        self._qs.setValue("appearance/reduce_motion", checked)

    def _on_test_wizard_changed(self, checked: bool) -> None:
        if self._building:
            return
        self._qs.setValue("controller/test_wizard_on_first_connect", checked)

    def _on_update_opt_changed(self, checked: bool) -> None:
        if self._building:
            return
        set_update_opt_in(checked)

    def _on_update_channel_changed(self, index: int) -> None:
        if self._building:
            return
        _, channel = self._UPDATE_CHANNELS[index]
        try:
            set_update_channel(channel)
        except ValueError:
            pass

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

    def _open_haptic_bindings_dialog(self) -> None:
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
                "Sent /gmb/ping to %s:%d\n\n"
                "Check Resolume's OSC monitor (Preferences -> OSC -> "
                "Input devices) or TouchDesigner's OSC In CHOP to confirm receipt." % (host, port),
            )
        else:
            QMessageBox.warning(self, "OSC ping failed",
                                "Couldn't send to %s:%d." % (host, port))

    def _on_export_bundle(self) -> None:
        try:
            bundle_path = export_bundle()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Crash bundle exported",
                "Bundle saved to:\n%s\n\nAttach this file to a bug report." % bundle_path
            )
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export failed",
                                "Could not export crash bundle:\n%s" % e)

    # ── danger zone ───────────────────────────────────────────────────────────

    def _on_clear_snapshots(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Clear snapshots",
            "Delete all snapshots? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        d = user_data_dir() / "snapshots"
        if d.exists():
            shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
        QMessageBox.information(self, "Done", "All snapshots cleared.")

    def _on_clear_autosaves(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Clear autosaves",
            "Delete all autosaves? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        d = user_data_dir() / "autosaves"
        if d.exists():
            shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
        QMessageBox.information(self, "Done", "All autosaves cleared.")

    def _on_reset_to_defaults(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Reset to factory defaults",
            "Reset all settings to factory defaults? "
            "Your presets and license are preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._qs.clear()
        fresh = Mapping()
        self._building = True
        self._theme.setCurrentIndex(0)          # system
        self._font_size.setCurrentIndex(1)      # medium
        self._reduce_motion.setChecked(False)
        self._channel.setValue(fresh.midi_channel + 1)
        self._poll.setValue(fresh.poll_hz)
        self._feedback_guard.setChecked(fresh.haptic_input.guard_feedback_loop)
        self._auto_reconnect.setChecked(fresh.auto_reconnect_enabled)
        self._test_wizard.setChecked(True)
        self._deadzone_spin.setValue(fresh.deadzone)
        self._building = False
        for attr in ("midi_channel", "deadzone", "poll_hz", "auto_reconnect_enabled"):
            setattr(self._mapping, attr, getattr(fresh, attr))
        self.settings_changed.emit(self._mapping)
        QMessageBox.information(self, "Done", "Settings reset to factory defaults.")

    def _on_sign_out(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Sign out",
            "Deactivate this license? You can re-enter your key at any time.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        license_deactivate()
        QMessageBox.information(self, "Signed out", "License deactivated.")

    # ── helpers ───────────────────────────────────────────────────────────────

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
