"""Main window — status header + tabbed body. Owns the BridgeController."""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from typing import Optional

from .. import APP_NAME, __version__, telemetry
from ..controller import available_count
from ..license import activate_from_string, is_pro, state as license_state
from ..mapping import Mapping
from ..multi import MultiBridgeController, desired_slot_count
from ..portable import export_pack, import_pack
from ..updater import UpdateChecker, UpdateInfo
from .calibration_dialog import CalibrationDialog
from .bluetooth_tab import BluetoothTab
from .connectors_tab import ConnectorsTab
from .controller_meter import ControllerMeter
from .help_tab import HelpTab
from .log_console import LogConsole
from .mapping_editor import MappingEditor
from .marketplace_tab import MarketplaceTab
from .onboarding import OnboardingWizard, is_first_launch, mark_complete
from .preset_manager import PresetManager
from .settings_panel import SettingsPanel
from .template_builder_tab import TemplateBuilderTab
from .tray import TrayController, is_available as tray_available
from .visualise_tab import VisualiseTab


UPGRADE_URL = "https://store.aidxn.com/gamepad-midi-bridge"
RECOVERY_URL = "https://store.aidxn.com/recover"
CHANGELOG_URL = "https://store.aidxn.com/changelog"


def _load_last_mapping() -> Mapping:
    """Restore the user's last mapping if it was persisted, otherwise defaults."""
    import json
    from ..paths import last_mapping_path
    path = last_mapping_path()
    if path.exists():
        try:
            return Mapping.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return Mapping()


def _save_last_mapping(mapping: Mapping) -> None:
    import json
    from ..paths import last_mapping_path
    try:
        last_mapping_path().write_text(
            json.dumps(mapping.to_dict(), indent=2), encoding="utf-8",
        )
    except Exception:
        pass


def _anonymise(controller_name: str) -> str:
    """Strip serial-ish noise from a controller name before sending in telemetry."""
    lc = controller_name.lower()
    if "dualsense" in lc:
        return "dualsense"
    if "xbox" in lc or "x-input" in lc:
        return "xbox"
    if "dualshock" in lc:
        return "dualshock"
    return "other"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(820, 640)

        self._mapping = _load_last_mapping()
        # MultiBridgeController behaves identically to the old single
        # BridgeController when only one slot is active — see multi.py.
        self._multi = MultiBridgeController(self)
        self._bridge = self._multi.primary()
        self._calibration_dialog = None
        self._activity_timer = QTimer(self)
        self._activity_timer.setSingleShot(True)
        self._activity_timer.timeout.connect(self._fade_activity)

        # MIDI throughput counter — incremented on midi_sent and flushed to
        # the status bar at 2Hz so the user can see a live rate without the
        # text flickering at 100Hz.
        self._midi_count = 0
        self._rate_timer = QTimer(self)
        self._rate_timer.setInterval(500)
        self._rate_timer.timeout.connect(self._flush_rate)
        self._rate_timer.start()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_status_bar())
        self._update_banner = self._build_update_banner()
        root.addWidget(self._update_banner)

        # Tabs over a collapsible log console. QSplitter lets the user drag
        # the divide; the console respects its own collapsed flag on launch.
        body_splitter = QSplitter(Qt.Vertical)
        body_splitter.setHandleWidth(2)
        body_splitter.setChildrenCollapsible(False)
        body_splitter.addWidget(self._build_tabs())
        self._log_console = LogConsole()
        body_splitter.addWidget(self._log_console)
        body_splitter.setStretchFactor(0, 1)
        body_splitter.setStretchFactor(1, 0)
        body_splitter.setSizes([640, 1 if self._log_console.is_collapsed() else 200])
        root.addWidget(body_splitter, 1)

        # Stream stdlib logging + bridge activity into the console.
        self._log_console.install_root_handler()

        self._wire_signals()
        self._refresh_status_idle()

        # Background update check. Silent on failure or opt-out.
        self._updater = UpdateChecker(self)
        self._updater.update_available.connect(self._on_update_available)
        QTimer.singleShot(1500, self._updater.check_async)

        # Global shortcuts — Cmd/Ctrl+Enter toggles the bridge from anywhere
        # in the app (handy when the user is mid-edit in the mapping tab).
        toggle = QShortcut(QKeySequence("Ctrl+Return"), self)
        toggle.setContext(Qt.ApplicationShortcut)
        toggle.activated.connect(self._toggle_bridge)

        # Tray icon — optional, depends on platform support.
        self._tray: Optional[TrayController] = None
        if tray_available():
            from pathlib import Path
            icon = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
            self._tray = TrayController(icon, self)
            self._tray.start_requested.connect(self._on_start)
            self._tray.stop_requested.connect(self._on_stop)
            self._tray.show_requested.connect(self._show_from_tray)
            self._tray.quit_requested.connect(self._quit_from_tray)

        # First-launch onboarding. Deferred so the main window paints before the
        # modal appears — keeps the welcome moment from feeling like a blocker.
        self._onboarding_wizard: OnboardingWizard | None = None
        if is_first_launch():
            QTimer.singleShot(500, self._show_onboarding)

    # ============================================================== onboarding

    def _show_onboarding(self) -> None:
        """Run the first-launch wizard. Wires its completion signals so a user
        who clicks Start Bridging skips straight into the live bridge without a
        second click on the main window."""
        wizard = OnboardingWizard(self)
        self._onboarding_wizard = wizard
        wizard.start_requested.connect(self._on_start)
        # mark_complete is also called inside the wizard, but we belt-and-brace
        # here in case a subclass ever short-circuits the wizard's own writes.
        wizard.onboarding_complete.connect(mark_complete)
        wizard.exec()
        self._onboarding_wizard = None

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

        self._rate_label = QLabel("")
        self._rate_label.setStyleSheet("color: #5a606b; font-size: 11px;")
        self._rate_label.setMinimumWidth(70)
        h.addWidget(self._rate_label)

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

        # Live tab — primary meter always present. Secondary meter + Pro
        # nudge banner are hidden until a second controller is wired in.
        self._meter = ControllerMeter()
        self._meter2 = ControllerMeter()
        self._meter2.setVisible(False)
        self._live_splitter = QSplitter(Qt.Horizontal)
        self._live_splitter.addWidget(self._meter)
        self._live_splitter.addWidget(self._meter2)
        self._live_splitter.setChildrenCollapsible(False)

        live_wrap = QWidget()
        live_v = QVBoxLayout(live_wrap)
        live_v.setContentsMargins(20, 20, 20, 20)
        live_v.setSpacing(8)
        self._pro_nudge = QLabel(
            "Pro: a 2nd controller is connected — unlock multi-controller "
            "to use both at once."
        )
        self._pro_nudge.setStyleSheet(
            "color: #facc15; background: #2a2410; padding: 8px 12px; "
            "border-radius: 6px; font-size: 12px;"
        )
        self._pro_nudge.setVisible(False)
        live_v.addWidget(self._pro_nudge)
        live_v.addWidget(self._live_splitter, 1)
        tabs.addTab(live_wrap, "Live")

        # Visualise tab — richer post-setup view with sparklines + heatmap.
        # Sits between Live (minimal) and Mapping (configuration) so the
        # natural left-to-right reading order is observe → analyse → configure.
        self._visualise = VisualiseTab()
        tabs.addTab(self._visualise, "Visualise")

        self._mapping_editor = MappingEditor(self._mapping)
        self._mapping_editor.upgrade_clicked.connect(self._open_upgrade)
        self._mapping_editor.activate_clicked.connect(self._enter_license_key)
        tabs.addTab(self._mapping_editor, "Mapping")

        # Templates — visual mapping builder + multi-format exporter.
        # Sits between Mapping (Pro table view) and Presets so users can
        # iterate visually then save the result alongside their named presets.
        self._template_builder = TemplateBuilderTab(self._mapping)
        self._template_builder.mapping_changed.connect(self._on_template_mapping_changed)
        tabs.addTab(self._template_builder, "Templates")

        self._presets = PresetManager(lambda: self._mapping)
        self._presets.upgrade_clicked.connect(self._open_upgrade)
        self._presets.activate_clicked.connect(self._enter_license_key)
        self._presets.preset_loaded.connect(self._on_preset_loaded)
        tabs.addTab(self._presets, "Presets")

        self._marketplace = MarketplaceTab()
        self._marketplace.preset_chosen.connect(self._on_preset_loaded)
        self._marketplace.status_message.connect(self._on_status)
        tabs.addTab(self._marketplace, "Marketplace")

        self._connectors = ConnectorsTab()
        self._connectors.status_message.connect(self._on_status)
        tabs.addTab(self._connectors, "Connectors")

        self._bluetooth = BluetoothTab()
        self._bluetooth.status_message.connect(self._on_status)
        tabs.addTab(self._bluetooth, "Bluetooth")

        self._settings = SettingsPanel(self._mapping)
        self._settings.settings_changed.connect(self._on_settings_changed)
        self._settings.recalibrate_clicked.connect(self._on_recalibrate)
        self._settings.multi_mode_changed.connect(self._on_multi_mode_changed)
        tabs.addTab(self._settings, "Settings")

        # Help tab — owns its own QShortcut instances and signals them back
        # up so MainWindow keeps a single source of truth for app actions.
        self._tabs_ref = tabs
        self._help = HelpTab()
        self._help.toggle_bridge_requested.connect(self._toggle_bridge)
        self._help.quit_requested.connect(self._quit_from_tray)
        self._help.open_settings_requested.connect(self._focus_settings_tab)
        self._help.hide_window_requested.connect(self.hide)
        self._help.recalibrate_requested.connect(self._on_recalibrate)
        tabs.addTab(self._help, "Help")

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

        changelog = QPushButton("Release notes")
        changelog.clicked.connect(lambda: webbrowser.open(CHANGELOG_URL))
        changelog.setFlat(True)
        changelog.setStyleSheet("color: #8a9099; text-align: left;")
        recovery_row.addWidget(changelog)

        recovery_row.addStretch(1)
        v.addLayout(recovery_row)

        # Portable config row — export/import everything as a single file
        v.addSpacing(16)
        portable_label = QLabel("CONFIG PACK")
        portable_label.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        v.addWidget(portable_label)
        portable_note = QLabel(
            "Bundle your mapping + presets + Pro license into a single "
            ".gmbpack file. Useful for moving rigs between machines."
        )
        portable_note.setStyleSheet("color: #8a9099; font-size: 12px;")
        portable_note.setWordWrap(True)
        v.addWidget(portable_note)
        portable_row = QHBoxLayout()
        export_btn = QPushButton("Export config…")
        export_btn.clicked.connect(self._on_export_pack)
        import_btn = QPushButton("Import config…")
        import_btn.clicked.connect(self._on_import_pack)
        portable_row.addWidget(export_btn)
        portable_row.addWidget(import_btn)
        portable_row.addStretch(1)
        v.addLayout(portable_row)

        v.addStretch(1)
        self._refresh_tier_label()
        return w

    # ============================================================== signal wiring

    def _wire_signals(self) -> None:
        # Slot 0 wiring is byte-identical to V1.1 — keeps the single-controller
        # path unchanged. Slot 1 wiring is deferred until configure() actually
        # spins up a second bridge.
        self._wire_bridge_to_meter(self._bridge, self._meter, primary=True)
        # Mirror primary bridge activity into the bottom console.
        self._log_console.attach_bridge_signals(self._bridge.worker)
        # Feed the Visualise tab from the same primary worker.
        self._visualise.attach_bridge_signals(self._bridge.worker)

    def _wire_bridge_to_meter(self, bridge, meter, primary: bool) -> None:
        w = bridge.worker
        # Only the primary bridge feeds the shared status header — otherwise
        # slot 2's chatter would overwrite slot 1's title text. Slot 2 still
        # owns its own meter + activity dot via midi_sent.
        if primary:
            w.status.connect(self._on_status)
            w.started.connect(self._on_started)
            w.stopped.connect(self._on_stopped)
            w.error.connect(self._on_error)
            w.calibration_progress.connect(self._on_calibration_progress)
            w.calibration_done.connect(self._on_calibration_done)
            w.corner_triggered.connect(self._on_corner_triggered)
            w.controller_info.connect(self._on_controller_info)
        else:
            # Secondary still surfaces errors as toasts so a misbehaving slot
            # isn't silently dropped on the floor.
            w.error.connect(self._on_error)
            w.controller_info.connect(
                lambda info, m=meter: m.set_connected(info is not None,
                                                     info.name if info else "")
            )
        w.axis_value.connect(meter.on_axis)
        w.button_state.connect(meter.on_button)
        w.hat_state.connect(meter.on_hat)
        w.midi_sent.connect(self._on_midi_sent)
        # V1.1 DualSense extras — meter setters are defined in controller_meter.py
        w.battery_changed.connect(meter.on_battery)
        w.touchpad_xy.connect(meter.on_touchpad)
        w.transport_changed.connect(meter.on_transport)

    # ============================================================== slots

    def _on_start(self) -> None:
        # Re-evaluate slot count every start — handles "user plugged in a 2nd
        # controller and switched the mode without restarting the app".
        try:
            slot_count = self._multi.configure(
                self._mapping, self._settings.current_multi_mode(),
            )
        except RuntimeError as e:
            QMessageBox.warning(self, "Multi-controller error", str(e))
            return
        self._bridge = self._multi.primary()
        self._sync_live_layout(slot_count)

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_title.setText("Starting…")
        self._status_sub.setText("Detecting controller and opening MIDI port.")

        # Calibration dialog shows immediately and follows worker signals.
        self._calibration_dialog = CalibrationDialog(self)
        self._multi.start()

    def _on_stop(self) -> None:
        self._multi.stop()
        self._stop_btn.setEnabled(False)

    def _sync_live_layout(self, slot_count: int) -> None:
        """Show/hide the secondary meter + Pro nudge based on hardware + tier.

        Called from _on_start (after configure) and from the multi-mode combo.
        Wires slot-1 signals lazily on the first activation so the wiring code
        runs exactly once per BridgeController instance.
        """
        secondary = self._multi.secondary()
        if secondary is not None and not getattr(secondary, "_wired", False):
            self._wire_bridge_to_meter(secondary, self._meter2, primary=False)
            secondary._wired = True  # type: ignore[attr-defined]

        show_two = slot_count >= 2
        self._meter2.setVisible(show_two)
        # Pro nudge: free tier sees 2 controllers but only the first activates.
        detected = available_count()
        self._pro_nudge.setVisible(
            (not is_pro()) and detected >= 2 and slot_count == 1
        )

    def _on_multi_mode_changed(self, _mode: str) -> None:
        """Re-evaluate slot visibility live so users see immediate feedback
        when flipping the combo, even while the bridge is stopped."""
        try:
            target = desired_slot_count(_mode)
        except RuntimeError:
            # force_two with <2 controllers — surfaced on Start, not here.
            target = 1
        self._sync_live_layout(target if self._stop_btn.isEnabled() else 1)

    def _on_started(self, controller_name: str, port_name: str) -> None:
        self._status_title.setText("Bridging")
        self._status_sub.setText(f"{controller_name}  →  {port_name}")
        telemetry.send_event("bridge_started",
                             controller=_anonymise(controller_name))
        if self._tray is not None:
            self._tray.set_running(True)
        if self._calibration_dialog and not self._calibration_dialog.isVisible():
            # Dialog already closed by user — nothing to do.
            self._calibration_dialog = None

    def _on_stopped(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._refresh_status_idle()
        self._meter.set_connected(False)
        if self._tray is not None:
            self._tray.set_running(False)

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
        # Live-apply to every active slot so multi-controller users see edits
        # propagate without restarting the bridge.
        self._mapping = mapping
        self._multi.apply_mapping(mapping)
        _save_last_mapping(mapping)

    def _on_template_mapping_changed(self, mapping: Mapping) -> None:
        """Template builder edits — forward to live bridge + persist.

        Same shape as _on_settings_changed but skips re-pushing to the
        settings panel (which uses live spin widgets the builder doesn't own).
        """
        self._mapping = mapping
        self._multi.apply_mapping(mapping)
        _save_last_mapping(mapping)

    def _on_recalibrate(self) -> None:
        if not self._stop_btn.isEnabled():
            QMessageBox.information(
                self, "Start the bridge first",
                "Calibration runs against the live controller. Click Start, "
                "then re-calibrate from Settings.",
            )
            return
        self._calibration_dialog = CalibrationDialog(self)
        self._multi.recalibrate()

    def _on_preset_loaded(self, mapping: Mapping) -> None:
        self._mapping = mapping
        self._multi.apply_mapping(mapping)
        self._mapping_editor.set_mapping(mapping)
        _save_last_mapping(mapping)
        QMessageBox.information(self, "Preset loaded", f"Loaded '{mapping.name}'.")

    def _on_corner_triggered(self, side: str, kind: str, sector: int) -> None:
        # Flash the activity dot and surface the event in the status subtitle.
        if kind == "on":
            self._status_sub.setText(f"Corner {side}{sector} → MIDI note fired")
        self._on_midi_sent()

    def _flush_rate(self) -> None:
        # Convert the half-second tally to a per-second rate, round to nearest 10.
        rate = self._midi_count * 2
        if rate > 0:
            rounded = (rate // 10) * 10 if rate >= 30 else rate
            self._rate_label.setText(f"{rounded}/s")
        elif self._rate_label.text():
            self._rate_label.setText("")
        self._midi_count = 0

    def _on_midi_sent(self) -> None:
        self._midi_count += 1
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
            telemetry.send_event("license_activated")
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

    # ============================================================== multi-controller

    def _on_multi_mode_changed(self, mode: str) -> None:
        """User flipped the 'Active controllers' combo in Settings."""
        slots = self._multi.configure(self._mapping, mode)
        self._bridge = self._multi.primary()
        telemetry.send_event("multi_mode_set", mode=mode, slots=slots)

    # ============================================================== shortcuts

    def _toggle_bridge(self) -> None:
        if self._stop_btn.isEnabled():
            self._on_stop()
        else:
            self._on_start()

    def _focus_settings_tab(self) -> None:
        """Jump focus to the Settings tab. Wired from the Help-tab shortcut so
        Cmd/Ctrl+, behaves like the platform-standard Preferences hotkey."""
        tabs = getattr(self, "_tabs_ref", None)
        if tabs is None:
            return
        for i in range(tabs.count()):
            if tabs.tabText(i) == "Settings":
                tabs.setCurrentIndex(i)
                return

    # ============================================================== tray helpers

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        from PySide6.QtWidgets import QApplication
        self._multi.shutdown()
        QApplication.instance().quit()

    # ============================================================== portable config

    def _on_export_pack(self) -> None:
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog

        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export config pack", "gamepad-midi-bridge.gmbpack",
            "Config Pack (*.gmbpack)",
        )
        if not path_str:
            return
        try:
            report = export_pack(Path(path_str), self._mapping)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        telemetry.send_event("config_exported", preset_count=report.preset_count)
        QMessageBox.information(
            self, "Config exported",
            f"Saved {report.preset_count} preset(s) and your current mapping"
            + (" + license" if report.license_present else "") + ".",
        )

    def _on_import_pack(self) -> None:
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog

        path_str, _ = QFileDialog.getOpenFileName(
            self, "Import config pack", "",
            "Config Pack (*.gmbpack)",
        )
        if not path_str:
            return
        # Ask separately about license — it's the most invasive piece.
        replace_license = False
        try:
            from ..portable import list_contents
            contents = list_contents(Path(path_str))
            if "license.key" in contents:
                resp = QMessageBox.question(
                    self, "Replace license?",
                    "This pack includes a license key. Replace your current one?",
                )
                replace_license = resp == QMessageBox.Yes
        except Exception as e:
            QMessageBox.warning(self, "Import failed", str(e))
            return

        try:
            mapping, report = import_pack(Path(path_str), replace_license=replace_license)
        except Exception as e:
            QMessageBox.warning(self, "Import failed", str(e))
            return

        if mapping is not None:
            self._on_preset_loaded(mapping)
        self._presets.refresh()
        telemetry.send_event("config_imported", preset_count=report.preset_count)
        QMessageBox.information(
            self, "Config imported",
            f"Restored {report.preset_count} preset(s)"
            + (" and license" if replace_license and report.license_present else "")
            + (" — created with v" + report.creator_version if report.creator_version else "")
            + ".",
        )

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
        _save_last_mapping(self._mapping)
        self._multi.shutdown()
        event.accept()
