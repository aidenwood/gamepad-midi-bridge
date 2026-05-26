"""Main window — status header + tabbed body. Owns the BridgeController."""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from ..bridge import BridgeController
from ..license import activate_from_string, is_pro, state as license_state
from ..mapping import Mapping
from ..updater import UpdateChecker, UpdateInfo
from .calibration_dialog import CalibrationDialog
from .connectors_tab import ConnectorsTab
from .controller_meter import ControllerMeter
from .mapping_editor import MappingEditor
from .preset_manager import PresetManager
from .settings_panel import SettingsPanel


UPGRADE_URL = "https://store.aidxn.com/gamepad-midi-bridge"
RECOVERY_URL = "https://store.aidxn.com/recover"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(820, 640)

        self._mapping = Mapping()
        self._bridge = BridgeController(self)
        self._calibration_dialog = None
        self._activity_timer = QTimer(self)
        self._activity_timer.setSingleShot(True)
        self._activity_timer.timeout.connect(self._fade_activity)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_status_bar())
        self._update_banner = self._build_update_banner()
        root.addWidget(self._update_banner)
        root.addWidget(self._build_tabs(), 1)

        self._wire_signals()
        self._refresh_status_idle()

        # Background update check. Silent on failure or opt-out.
        self._updater = UpdateChecker(self)
        self._updater.update_available.connect(self._on_update_available)
        QTimer.singleShot(1500, self._updater.check_async)

    # ============================================================== ui builders

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 14, 18, 14)
        h.setSpacing(14)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._status_title = QLabel("Idle")
        self._status_title.setObjectName("StatusTitle")
        self._status_sub = QLabel("Plug in a controller and click Start.")
        self._status_sub.setObjectName("StatusSub")
        title_col.addWidget(self._status_title)
        title_col.addWidget(self._status_sub)
        h.addLayout(title_col, 1)

        self._activity_dot = QLabel("●")
        self._activity_dot.setObjectName("ActivityDot")
        self._activity_dot.setStyleSheet("color: #2c313b; font-size: 18px;")
        h.addWidget(self._activity_dot)

        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("PrimaryButton")
        self._start_btn.setMinimumWidth(110)
        self._start_btn.clicked.connect(self._on_start)
        h.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("StopButton")
        self._stop_btn.setMinimumWidth(90)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        h.addWidget(self._stop_btn)

        return bar

    def _build_update_banner(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            "background-color: #1f3a36; border-bottom: 1px solid #2dd4bf;"
        )
        bar.setVisible(False)
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 8, 18, 8)
        h.setSpacing(10)

        self._update_label = QLabel("")
        self._update_label.setStyleSheet("color: #2dd4bf; font-weight: 500;")
        h.addWidget(self._update_label, 1)

        self._update_open = QPushButton("Release notes")
        self._update_open.setStyleSheet("color: #0e0f12; background-color: #2dd4bf;")
        h.addWidget(self._update_open)

        dismiss = QPushButton("Dismiss")
        dismiss.setFlat(True)
        dismiss.setStyleSheet("color: #2dd4bf;")
        dismiss.clicked.connect(lambda: bar.setVisible(False))
        h.addWidget(dismiss)
        return bar

    def _on_update_available(self, info: UpdateInfo) -> None:
        self._update_label.setText(
            f"v{info.latest} is available — you're on v{__version__}."
        )
        # Re-wire the open button to this specific release's URL.
        try:
            self._update_open.clicked.disconnect()
        except Exception:
            pass
        url = info.notes_url or info.download_url or UPGRADE_URL
        self._update_open.clicked.connect(lambda: webbrowser.open(url))
        self._update_banner.setVisible(True)

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self._meter = ControllerMeter()
        tabs.addTab(self._wrap_padded(self._meter), "Live")

        self._mapping_editor = MappingEditor(self._mapping)
        self._mapping_editor.upgrade_clicked.connect(self._open_upgrade)
        self._mapping_editor.activate_clicked.connect(self._enter_license_key)
        tabs.addTab(self._mapping_editor, "Mapping")

        self._presets = PresetManager(lambda: self._mapping)
        self._presets.upgrade_clicked.connect(self._open_upgrade)
        self._presets.activate_clicked.connect(self._enter_license_key)
        self._presets.preset_loaded.connect(self._on_preset_loaded)
        tabs.addTab(self._presets, "Presets")

        self._connectors = ConnectorsTab()
        self._connectors.status_message.connect(self._on_status)
        tabs.addTab(self._connectors, "Connectors")

        self._settings = SettingsPanel(self._mapping)
        self._settings.settings_changed.connect(self._on_settings_changed)
        self._settings.recalibrate_clicked.connect(self._on_recalibrate)
        tabs.addTab(self._settings, "Settings")

        about_tab = self._build_about_tab()
        tabs.addTab(about_tab, "About")

        return tabs

    def _wrap_padded(self, widget: QWidget) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(20, 20, 20, 20)
        v.addWidget(widget)
        return wrap

    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(28, 28, 28, 28)
        v.setSpacing(10)

        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f7fa;")
        v.addWidget(title)

        sub = QLabel(f"v{__version__} · Aidxn Design")
        sub.setStyleSheet("color: #8a9099;")
        v.addWidget(sub)

        v.addSpacing(16)
        self._tier_label = QLabel()
        v.addWidget(self._tier_label)

        row = QHBoxLayout()
        upgrade = QPushButton("Upgrade to Pro")
        upgrade.setObjectName("PrimaryButton")
        upgrade.clicked.connect(self._open_upgrade)
        activate = QPushButton("Enter license key")
        activate.clicked.connect(self._enter_license_key)
        row.addWidget(upgrade)
        row.addWidget(activate)
        row.addStretch(1)
        v.addLayout(row)

        recovery_row = QHBoxLayout()
        recover = QPushButton("Lost your license key?")
        recover.clicked.connect(lambda: webbrowser.open(RECOVERY_URL))
        recover.setFlat(True)
        recover.setStyleSheet("color: #8a9099; text-align: left;")
        recovery_row.addWidget(recover)
        recovery_row.addStretch(1)
        v.addLayout(recovery_row)

        v.addStretch(1)
        self._refresh_tier_label()
        return w

    # ============================================================== signal wiring

    def _wire_signals(self) -> None:
        w = self._bridge.worker
        w.status.connect(self._on_status)
        w.started.connect(self._on_started)
        w.stopped.connect(self._on_stopped)
        w.error.connect(self._on_error)
        w.controller_info.connect(self._on_controller_info)
        w.calibration_progress.connect(self._on_calibration_progress)
        w.calibration_done.connect(self._on_calibration_done)
        w.axis_value.connect(self._meter.on_axis)
        w.button_state.connect(self._meter.on_button)
        w.hat_state.connect(self._meter.on_hat)
        w.midi_sent.connect(self._on_midi_sent)
        # V1.1 DualSense extras — meter setters are defined in controller_meter.py
        w.battery_changed.connect(self._meter.on_battery)
        w.touchpad_xy.connect(self._meter.on_touchpad)
        w.transport_changed.connect(self._meter.on_transport)
        w.corner_triggered.connect(self._on_corner_triggered)

    # ============================================================== slots

    def _on_start(self) -> None:
        self._bridge.worker.set_mapping(self._mapping)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_title.setText("Starting…")
        self._status_sub.setText("Detecting controller and opening MIDI port.")

        # Calibration dialog shows immediately and follows worker signals.
        self._calibration_dialog = CalibrationDialog(self)
        self._bridge.start()

    def _on_stop(self) -> None:
        self._bridge.stop()
        self._stop_btn.setEnabled(False)

    def _on_started(self, controller_name: str, port_name: str) -> None:
        self._status_title.setText("Bridging")
        self._status_sub.setText(f"{controller_name}  →  {port_name}")
        if self._calibration_dialog and not self._calibration_dialog.isVisible():
            # Dialog already closed by user — nothing to do.
            self._calibration_dialog = None

    def _on_stopped(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._refresh_status_idle()
        self._meter.set_connected(False)

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Bridge error", message)
        self._on_stopped()

    def _on_controller_info(self, info) -> None:
        if info is None:
            self._meter.set_connected(False)
        else:
            self._meter.set_connected(True, info.name)

    def _on_calibration_progress(self, fraction: float) -> None:
        if self._calibration_dialog is not None:
            if not self._calibration_dialog.isVisible():
                self._calibration_dialog.show()
            self._calibration_dialog.on_progress(fraction)

    def _on_calibration_done(self, offsets, severe, significant) -> None:
        if self._calibration_dialog is not None:
            if not self._calibration_dialog.isVisible():
                self._calibration_dialog.show()
            self._calibration_dialog.on_done(offsets, severe, significant)

    def _on_status(self, text: str) -> None:
        # Mirror engine status into the subtitle line.
        self._status_sub.setText(text)

    def _on_settings_changed(self, mapping: Mapping) -> None:
        # Live-apply to the worker so changes take effect without restart.
        self._mapping = mapping
        self._bridge.worker.set_mapping(mapping)

    def _on_recalibrate(self) -> None:
        if not self._stop_btn.isEnabled():
            QMessageBox.information(
                self, "Start the bridge first",
                "Calibration runs against the live controller. Click Start, "
                "then re-calibrate from Settings.",
            )
            return
        self._calibration_dialog = CalibrationDialog(self)
        self._bridge.recalibrate()

    def _on_preset_loaded(self, mapping: Mapping) -> None:
        self._mapping = mapping
        self._bridge.worker.set_mapping(mapping)
        self._mapping_editor.set_mapping(mapping)
        QMessageBox.information(self, "Preset loaded", f"Loaded '{mapping.name}'.")

    def _on_corner_triggered(self, side: str, kind: str, sector: int) -> None:
        # Flash the activity dot and surface the event in the status subtitle.
        if kind == "on":
            self._status_sub.setText(f"Corner {side}{sector} → MIDI note fired")
        self._on_midi_sent()

    def _on_midi_sent(self) -> None:
        self._activity_dot.setStyleSheet("color: #2dd4bf; font-size: 18px;")
        self._activity_timer.start(120)

    def _fade_activity(self) -> None:
        self._activity_dot.setStyleSheet("color: #2c313b; font-size: 18px;")

    # ============================================================== licensing

    def _open_upgrade(self) -> None:
        webbrowser.open(UPGRADE_URL)

    def _enter_license_key(self) -> None:
        key, ok = QInputDialog.getMultiLineText(
            self, "Enter license key",
            "Paste the license key you received via email:",
        )
        if not ok or not key.strip():
            return
        new_state = activate_from_string(key)
        if new_state.is_pro:
            QMessageBox.information(
                self, "Pro unlocked",
                f"Thanks{'!' if not new_state.email else f', {new_state.email}!'} "
                "All Pro features are now enabled.",
            )
        else:
            QMessageBox.warning(
                self, "Invalid license",
                f"Could not activate: {new_state.reason or 'unknown error'}",
            )
        self._mapping_editor.refresh_lock()
        self._presets.refresh_lock()
        self._refresh_tier_label()

    def _refresh_tier_label(self) -> None:
        s = license_state()
        if s.is_pro:
            self._tier_label.setText(
                f"<b style='color:#2dd4bf'>Pro</b> · licensed to {s.email or 'you'}"
            )
        else:
            self._tier_label.setText(
                "<b style='color:#8a9099'>Free</b> — Pro unlocks the mapping editor and preset library."
            )

    # ============================================================== misc

    # ============================================================== deep links

    def handle_deep_link(self, url: str) -> None:
        """React to a `gmb://` URL — e.g. one-click preset install from the
        marketplace. URL shapes we support so far:

            gmb://activate?key=<license_blob>
            gmb://import?preset=<base64url(json)>
            gmb://import?id=<marketplace_id>   (fetches from the store API)
        """
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(url)
        if parsed.scheme != "gmb":
            return
        action = parsed.netloc or parsed.path.lstrip("/")
        params = parse_qs(parsed.query)

        if action == "activate":
            keys = params.get("key", [])
            if keys:
                self._activate_with_blob(keys[0])
        elif action == "import":
            blob_params = params.get("preset", [])
            if blob_params:
                self._import_preset_blob(blob_params[0])
            # marketplace `id` fetch handled when the marketplace API ships

    def _activate_with_blob(self, blob: str) -> None:
        new_state = activate_from_string(blob)
        if new_state.is_pro:
            QMessageBox.information(self, "Pro unlocked",
                                    "License activated from store link.")
        else:
            QMessageBox.warning(self, "Activation failed",
                                f"Could not activate: {new_state.reason}")
        self._mapping_editor.refresh_lock()
        self._presets.refresh_lock()
        self._refresh_tier_label()

    def _import_preset_blob(self, b64url_json: str) -> None:
        import base64
        import json
        try:
            raw = base64.urlsafe_b64decode(b64url_json.encode("ascii"))
            data = json.loads(raw.decode("utf-8"))
            mapping = Mapping.from_dict(data)
            self._on_preset_loaded(mapping)
        except Exception as e:
            QMessageBox.warning(self, "Import failed",
                                f"Couldn't decode preset: {e}")

    def _refresh_status_idle(self) -> None:
        if is_pro():
            self._status_title.setText("Idle · Pro")
        else:
            self._status_title.setText("Idle")
        self._status_sub.setText("Plug in a controller and click Start.")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._bridge.shutdown()
        event.accept()
