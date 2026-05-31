"""Main window — status header + tabbed body. Owns the BridgeController."""
from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSplitter, QStackedLayout, QVBoxLayout, QWidget, QMenu,
)

from typing import Dict, List, Optional

from .. import APP_NAME, __version__, telemetry, autobackup
from ..controller_history import seen_controllers, mark_seen

_log = logging.getLogger(__name__)
from ..controller import available_count
from ..license import activate_from_string, is_pro, state as license_state
from ..mapping import Mapping
from ..multi import MultiBridgeController, desired_slot_count
from ..portable import export_pack, import_pack
from ..updater import UpdateChecker, UpdateInfo
from .calibration_dialog import CalibrationDialog
from .test_wizard import ControllerTestWizard
from .bluetooth_tab import BluetoothTab
from .connectors_tab import ConnectorsTab
from .controller_meter import ControllerMeter
from .help_tab import HelpTab
from .axis_scope import AxisScope
from .inspector import (
    INSPECTOR_WIDTH, Inspector, render_mapping_selection, render_marketplace_selection,
    render_live_selection, render_connector_selection, render_preset_file_selection,
)
from .inspector_renderers import (
    render_trigger_editor,
    render_stick_editor,
    render_touchpad_editor,
    render_button_editor,
    render_hat_editor,
    render_mapping_globals,
)
from .log_console import LogConsole
from .logo_view_3d import BgLogo3DView
from .mapping_editor import MappingEditor
from .midi_log_panel import MidiLogPanel
from .marketplace_tab import MarketplaceTab
from .onboarding import OnboardingWizard, is_first_launch, mark_complete
from .preset_manager import PresetManager
from .shortcuts_dialog import ShortcutsDialog
from .reconnect_overlay import ReconnectOverlay
from .settings_panel import SettingsPanel
from .template_builder_tab import TemplateBuilderTab
from .command_palette import Command, CommandPalette
from .tray import TrayController, is_available as tray_available
from .visualise_tab import VisualiseTab
from .hud_overlay import HudOverlay
from .responsive_tab_widget import ResponsiveTabWidget


from .about_tab import AboutTab
UPGRADE_URL = "https://midi.aidxn.com/"
RECOVERY_URL = "https://midi.aidxn.com/recover"
CHANGELOG_URL = "https://midi.aidxn.com/changelog"

_BG3D_CONFIG_KEY = "bg_3d_on"


def _read_bg3d_state() -> bool:
    """Read persisted 3D background toggle. Default OFF."""
    from ..paths import config_path
    path = config_path()
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get(_BG3D_CONFIG_KEY, False))
    except Exception:
        return False


def _write_bg3d_state(on: bool) -> None:
    from ..paths import config_path
    path = config_path()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[_BG3D_CONFIG_KEY] = bool(on)
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


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
        # Default size for first launch; the actual floor is enforced below
        # so users can collapse the window into a thin status strip.
        self.resize(820, 640)
        self.setMinimumSize(380, 280)
        # Enable drag-and-drop for preset/pack import
        self.setAcceptDrops(True)

        # Crash recovery: check if app exited cleanly last time
        autobackup.mark_unclean_startup()
        if not autobackup.was_clean_shutdown() and autobackup.latest_autosave() is not None:
            # Show recovery dialog
            reply = QMessageBox.question(
                self,
                "Recover unsaved work?",
                "Looks like the app didn't close cleanly last time. "
                "Restore your last mapping?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                recovered = autobackup.load_latest_autosave()
                if recovered is not None:
                    self._mapping = recovered
                else:
                    self._mapping = _load_last_mapping()
            else:
                self._mapping = _load_last_mapping()
        else:
            self._mapping = _load_last_mapping()
        # MultiBridgeController behaves identically to the old single
        # BridgeController when only one slot is active — see multi.py.
        self._multi = MultiBridgeController(self)
        self._bridge = self._multi.primary()
        self._calibration_dialog = None
        self._test_wizard = None
        self._activity_timer = QTimer(self)
        self._activity_timer.setSingleShot(True)
        self._activity_timer.timeout.connect(self._fade_activity)

        # Debounced autosave for mapping changes (500ms, single-shot).
        self._mapping_save_timer = QTimer(self)
        self._mapping_save_timer.setSingleShot(True)
        self._mapping_save_timer.setInterval(500)
        self._mapping_save_timer.timeout.connect(self._on_mapping_save_timeout)

        # MIDI throughput counter — incremented on midi_sent and flushed to
        # the status bar at 2Hz so the user can see a live rate without the
        # text flickering at 100Hz.
        self._midi_count = 0
        self._rate_timer = QTimer(self)
        self._rate_timer.setInterval(500)
        self._rate_timer.timeout.connect(self._flush_rate)
        self._rate_timer.start()
        # Registry to track live scope widgets so bridge signals can feed them.
        # Keyed by (inspector_id, axis_idx) → AxisScope widget.
        self._live_scope_widgets: Dict[tuple, Optional[AxisScope]] = {}

        central = QWidget()
        self.setCentralWidget(central)

        # Build the native menu bar (File / Edit / View / Help)
        self._build_menu_bar()

        # --- Background 3D visualiser layer (conditional) ---
        # When the 3D logo is active we stack it under a translucent chrome
        # layer via QStackedLayout(StackAll). When 3D is OFF (GMB_NO_3D=1 or
        # BgLogo3DView fails to construct), we use a plain opaque chrome
        # widget directly on a vertical layout — no stack, no translucency.
        # Translucent ancestors on macOS prevent Qt from clearing pixels
        # before each paint, which was the root cause of all the ghost-text
        # / smeared-tab / doubled-logo bugs.
        # 3D background is now OPT-IN via GMB_ENABLE_3D=1. The QtWebEngineCore
        # (Chromium) used to render the GLB has crashed for the user with
        # EXC_BAD_ACCESS in the CrBrowserMain thread on launch — happens during
        # NetworkConfigWatcher/NetworkService init. Defaulting to no-3D means
        # the app launches reliably for everyone; users who want the spinning
        # logo can set GMB_ENABLE_3D=1 to opt back in. GMB_NO_3D=1 still works
        # as an explicit disable (back-compat).
        import os as _os_3d
        _three_d_enabled = (
            _os_3d.environ.get("GMB_ENABLE_3D") == "1"
            and _os_3d.environ.get("GMB_NO_3D") != "1"
        )

        bg_3d_widget: Optional[QWidget] = None
        if _three_d_enabled:
            try:
                bg_3d_widget = BgLogo3DView(parent=central, opacity=0.3)
                bg_3d_widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            except Exception as _e_3d:
                import logging as _log_3d
                _log_3d.getLogger("ui").warning(
                    "BgLogo3DView failed (%s); falling back to opaque chrome", _e_3d
                )
                bg_3d_widget = None

        if bg_3d_widget is not None:
            # 3D path: stack the bg + translucent chrome.
            self._bg_3d = bg_3d_widget
            stack = QStackedLayout(central)
            stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
            stack.setContentsMargins(0, 0, 0, 0)
            stack.addWidget(self._bg_3d)
            chrome_widget = QWidget(central)
            chrome_widget.setAttribute(Qt.WA_TranslucentBackground, True)
            stack.addWidget(chrome_widget)
            stack.setCurrentIndex(1)
        else:
            # No 3D path: opaque chrome on a plain QVBoxLayout. This kills
            # the ghost-text bug for every descendant widget.
            # NOTE: a plain QWidget does NOT honour ``background-color`` from
            # its own stylesheet unless ``WA_StyledBackground`` is set — that's
            # why the ghost-text bug kept reappearing. QFrame paints its
            # background from QSS by default, so we use that here.
            self._bg_3d = None
            chrome_widget = QFrame(central)
            chrome_widget.setObjectName("ChromeWidget")
            chrome_widget.setAutoFillBackground(True)
            chrome_widget.setAttribute(Qt.WA_StyledBackground, True)
            chrome_widget.setStyleSheet(
                "QFrame#ChromeWidget { background-color: #0c0d10; }"
            )
            outer = QVBoxLayout(central)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
            outer.addWidget(chrome_widget)

        root = QVBoxLayout(chrome_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_status_bar())
        self._update_banner = self._build_update_banner()
        root.addWidget(self._update_banner)

        # Layout:
        #   body_splitter (vertical)
        #     ├── content_splitter (horizontal): tabs | side panel
        #     └── log console (collapsible from its own header AND via the
        #         status-bar Console toggle)
        # The side panel holds a secondary ControllerMeter so the user can keep
        # an eye on live controller activity while editing on any tab (mapping,
        # presets, marketplace, etc). Hidden by default — toggled via the
        # status-bar Split button.
        body_splitter = QSplitter(Qt.Vertical)
        # 6 px handle — visual styling comes from the global styles.qss
        # ``QSplitter::handle`` rule so every splitter looks identical.
        body_splitter.setHandleWidth(6)
        # Children NOT collapsible — dragging the handle should resize,
        # not snap-to-zero. Collapse/expand goes through each panel's
        # toggle button instead (which we wire to setSizes below).
        body_splitter.setChildrenCollapsible(False)

        # Figma-style workspace layout:
        #   content_splitter (horizontal): [ inspector_a | workspace_a | workspace_b | inspector_b ]
        # workspace_b is hidden unless Split is on; both inspectors are hidden
        # until the user clicks the Inspect button (or makes a selection that
        # auto-opens it). This lets each side of a split keep its own
        # context-properties pane — Figma-style.
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(6)
        content_splitter.setChildrenCollapsible(False)

        # Workspace A — the primary tabs.
        self._workspace_a = self._build_tabs()
        # Workspace B — the secondary live-preview panel (this is the
        # original "split" content: a controller meter alongside the tabs).
        self._side_panel = self._build_side_panel()

        # Inspectors, one per workspace. Each is registered with renderers
        # for mapping, marketplace, and live control selections.
        self._inspector_a = Inspector(label="INSPECTOR")
        self._inspector_b = Inspector(label="INSPECTOR · B")
        for insp in (self._inspector_a, self._inspector_b):
            insp.register_renderer("mapping", render_mapping_selection)
            insp.register_renderer("marketplace", render_marketplace_selection)
            insp.register_renderer("live", render_live_selection)
            insp.register_renderer("connectors", render_connector_selection)
            insp.register_renderer("presets", render_preset_file_selection)
            # Config-aware renderers for trigger / stick / touchpad axis rows.
            insp.register_renderer("mapping_trigger", render_trigger_editor)
            insp.register_renderer("mapping_stick", render_stick_editor)
            insp.register_renderer("mapping_touchpad", render_touchpad_editor)
            # Button and hat editors
            insp.register_renderer("button_editor", render_button_editor)
            insp.register_renderer("hat_editor", render_hat_editor)
            # Top-level Mapping globals inspector (Settings button in mapping editor)
            insp.register_renderer("mapping_globals", render_mapping_globals)
            insp.setVisible(False)

        content_splitter.addWidget(self._workspace_a)
        content_splitter.addWidget(self._inspector_a)
        content_splitter.addWidget(self._side_panel)
        content_splitter.addWidget(self._inspector_b)
        # Tabs stretch, side panel + inspectors are fixed-ish.
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        content_splitter.setStretchFactor(2, 0)
        content_splitter.setStretchFactor(3, 0)
        content_splitter.setSizes([1000, INSPECTOR_WIDTH, 320, INSPECTOR_WIDTH])
        self._content_splitter = content_splitter
        self._side_panel.setVisible(False)  # split mode off by default

        body_splitter.addWidget(content_splitter)
        self._log_console = LogConsole()
        # Minimum height = header strip only (36 px). Lets the user drag the
        # handle down to "just header visible" but no further. Collapse via
        # toggle button uses the same 36 px.
        self._log_console.setMinimumHeight(48)
        body_splitter.addWidget(self._log_console)

        # MIDI Activity Log Panel — scrolling MIDI message feed
        self._midi_log_panel = MidiLogPanel()
        self._midi_log_panel.setMinimumHeight(48)
        body_splitter.addWidget(self._midi_log_panel)

        body_splitter.setStretchFactor(0, 1)
        body_splitter.setStretchFactor(1, 0)
        body_splitter.setStretchFactor(2, 0)
        self._body_splitter = body_splitter
        # Apply initial splitter sizes from each panel's persisted collapsed
        # state. ``_set_bottom_panel_sizes`` is the single sizing path used by
        # toggle buttons too.
        self._set_bottom_panel_sizes()

        # Each panel's toggle button emits collapse_changed → we recompute
        # the splitter layout. Splitter handle drags still work independently.
        self._log_console.collapse_changed.connect(
            lambda _collapsed: self._set_bottom_panel_sizes()
        )
        self._midi_log_panel.collapse_changed.connect(
            lambda _collapsed: self._set_bottom_panel_sizes()
        )
        root.addWidget(body_splitter, 1)

        # Wire the status-bar toggle buttons (created earlier inside
        # _build_status_bar but not yet hooked up — chicken-and-egg with the
        # console + side_panel widgets being constructed after the bar).
        self._split_btn.setChecked(False)
        self._split_btn.clicked.connect(self._toggle_split_view)
        self._console_btn.setChecked(not self._log_console.is_collapsed())
        self._console_btn.clicked.connect(self._toggle_console)
        self._inspect_btn.setChecked(False)
        self._inspect_btn.clicked.connect(self._toggle_inspector)
        # Two-way binding: closing an inspector via its X reflects in the toggle.
        self._inspector_a.visibility_changed.connect(self._on_inspector_visibility)
        self._inspector_b.visibility_changed.connect(self._on_inspector_visibility)

        # 3D background toggle — persisted, default OFF.
        _bg3d_on = _read_bg3d_state()
        self._3d_btn.setChecked(_bg3d_on and self._bg_3d is not None)
        self._3d_btn.setEnabled(self._bg_3d is not None)
        self._3d_btn.clicked.connect(self._toggle_3d)
        # Apply persisted state now: only show_bg() if it was on last session
        # AND the 3D widget actually exists (skipped if GMB_NO_3D=1 / failed init).
        if self._bg_3d is not None:
            if _bg3d_on:
                self._bg_3d.show_bg()
            else:
                self._bg_3d.setVisible(False)

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

        # Cmd-K / Ctrl-K — command palette.
        palette_sc = QShortcut(QKeySequence("Ctrl+K"), self)
        palette_sc.setContext(Qt.ApplicationShortcut)
        palette_sc.activated.connect(self._open_command_palette)

        # Ctrl+Shift+P — panic (all notes off).
        panic_sc = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        panic_sc.setContext(Qt.ApplicationShortcut)
        panic_sc.activated.connect(self._on_panic)

        # Tray icon — optional, depends on platform support.
        self._tray: Optional[TrayController] = None
        if tray_available():
            from pathlib import Path
            icon = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
            self._tray = TrayController(icon, self)
            self._tray.start_requested.connect(self._on_start)
            self._tray.stop_requested.connect(self._on_stop)
            self._tray.show_requested.connect(self._show_from_tray)
            self._tray.command_palette_requested.connect(self._open_command_palette)
            self._tray.latency_test_requested.connect(self._on_latency_test)
            self._tray.about_requested.connect(self._menu_show_about)
            self._tray.quit_requested.connect(self._quit_from_tray)

        # HUD overlay — always-on-top status widget for tray/background mode.
        # Created lazily when the user enables it; destroyed when disabled.
        self._hud: Optional[HudOverlay] = None
        # Restore persisted visibility preference.
        if HudOverlay.read_visible():
            self._toggle_hud(True)

        # Auto-backup of the mapping every 60 seconds
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(60_000)
        self._autosave_timer.timeout.connect(self._autosave_tick)
        self._autosave_timer.start()

        # ---- Auto-reconnect overlay ----
        # Instantiated once; kept hidden until a disconnect happens while the
        # bridge is running.  The overlay lives as a direct child of the
        # centralWidget so it can cover the full chrome area.
        self._reconnect_overlay = ReconnectOverlay(self.centralWidget())
        self._reconnect_overlay.cancel_requested.connect(self._on_reconnect_cancelled)
        self._reconnect_overlay.retry_requested.connect(self._on_reconnect_retry)
        # 1-second retry ticker — fires each tick while the overlay is counting.
        self._reconnect_retry_timer = QTimer(self)
        self._reconnect_retry_timer.setInterval(1000)
        self._reconnect_retry_timer.timeout.connect(self._on_reconnect_tick)

        # Esc dismisses the overlay (spec §6).
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.setContext(Qt.ApplicationShortcut)
        esc_shortcut.activated.connect(self._on_reconnect_esc)

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

    def _build_menu_bar(self) -> None:
        """Build the native menu bar with File, Edit, View, and Help menus."""
        menubar = self.menuBar()

        # ---- File Menu ----
        file_menu = menubar.addMenu("&File")

        # Open preset (Cmd-O)
        open_action = file_menu.addAction("&Open preset...")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._menu_open_preset)

        # Save preset (Cmd-S)
        save_action = file_menu.addAction("&Save preset")
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._menu_save_preset)

        # Save preset as (Cmd-Shift-S)
        save_as_action = file_menu.addAction("Save preset &as...")
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._menu_save_preset_as)

        file_menu.addSeparator()

        # Export pack
        export_action = file_menu.addAction("&Export pack...")
        export_action.triggered.connect(self._on_export_pack)

        # Import pack
        import_action = file_menu.addAction("&Import pack...")
        import_action.triggered.connect(self._on_import_pack)

        file_menu.addSeparator()

        # Quit (Cmd-Q)
        quit_action = file_menu.addAction("&Quit")
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self._quit_from_tray)

        # ---- Edit Menu ----
        edit_menu = menubar.addMenu("&Edit")

        # Undo (Cmd-Z) — disabled for now, TODO
        undo_action = edit_menu.addAction("&Undo")
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.setEnabled(False)
        undo_action.setToolTip("Coming soon")

        # Redo — disabled for now, TODO
        redo_action = edit_menu.addAction("&Redo")
        redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        redo_action.setEnabled(False)
        redo_action.setToolTip("Coming soon")

        edit_menu.addSeparator()

        # Preferences (Cmd-,)
        prefs_action = edit_menu.addAction("&Preferences")
        prefs_action.setShortcut(QKeySequence("Ctrl+,"))
        prefs_action.triggered.connect(self._focus_settings_tab)

        # ---- View Menu ----
        view_menu = menubar.addMenu("&View")

        # Toggle Split (Cmd-Alt-S)
        split_action = view_menu.addAction("Toggle &Split")
        split_action.setShortcut(QKeySequence("Ctrl+Alt+S"))
        split_action.triggered.connect(self._toggle_split_view)

        # Toggle Console (Cmd-Alt-C)
        console_action = view_menu.addAction("Toggle &Console")
        console_action.setShortcut(QKeySequence("Ctrl+Alt+C"))
        console_action.triggered.connect(self._toggle_console)

        # Toggle Inspector (Cmd-Alt-I)
        inspector_action = view_menu.addAction("Toggle &Inspector")
        inspector_action.setShortcut(QKeySequence("Ctrl+Alt+I"))
        inspector_action.triggered.connect(self._toggle_inspector)

        # Toggle 3D (Cmd-Alt-3)
        bg3d_action = view_menu.addAction("Toggle &3D")
        bg3d_action.setShortcut(QKeySequence("Ctrl+Alt+3"))
        bg3d_action.triggered.connect(self._toggle_3d)

        # HUD overlay — checkable; toggle creates/destroys the overlay.
        self._hud_action = view_menu.addAction("Show &HUD overlay")
        self._hud_action.setCheckable(True)
        self._hud_action.setChecked(HudOverlay.read_visible())
        self._hud_action.triggered.connect(self._toggle_hud)

        view_menu.addSeparator()

        # Command palette (Cmd-K)
        palette_action = view_menu.addAction("Show &command palette")
        palette_action.setShortcut(QKeySequence("Ctrl+K"))
        palette_action.triggered.connect(self._open_command_palette)

        # ---- Help Menu ----
        help_menu = menubar.addMenu("&Help")

        # User guide
        guide_action = help_menu.addAction("User &guide")
        guide_action.triggered.connect(self._menu_open_user_guide)

        # Keyboard shortcuts
        shortcuts_action = help_menu.addAction("Keyboard &shortcuts")
        shortcuts_action.triggered.connect(self._menu_show_keyboard_shortcuts)

        # Report bug
        bug_action = help_menu.addAction("&Report bug")
        bug_action.triggered.connect(self._menu_report_bug)

        help_menu.addSeparator()

        # About
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._menu_show_about)

    def _menu_open_preset(self) -> None:
        """File > Open preset"""
        # Delegate to the PresetManager's load dialog if available
        if hasattr(self, "_presets") and self._presets is not None:
            self._presets._on_load()

    def _menu_save_preset(self) -> None:
        """File > Save preset"""
        # Delegate to the PresetManager's save dialog if available
        if hasattr(self, "_presets") and self._presets is not None:
            self._presets._on_save()

    def _menu_save_preset_as(self) -> None:
        """File > Save preset as"""
        # Delegate to the PresetManager's save-as dialog if available
        if hasattr(self, "_presets") and self._presets is not None:
            # Save As is typically the same as Save in the PresetManager
            self._presets._on_save()

    def _menu_open_user_guide(self) -> None:
        """Help > User guide"""
        webbrowser.open("https://midi.aidxn.com/docs")

    def _menu_show_keyboard_shortcuts(self) -> None:
        """Help > Keyboard shortcuts"""
        dialog = ShortcutsDialog(self)
        dialog.exec()

    def _menu_report_bug(self) -> None:
        """Help > Report bug"""
        webbrowser.open("https://github.com/aidenwood/gamepad-midi-bridge/issues")

    def _menu_show_about(self) -> None:
        """Help > About"""
        # Find and focus the About tab
        tabs = getattr(self, "_tabs_ref", None)
        if tabs is None:
            return
        for i in range(tabs.count()):
            if tabs.tabText(i) == "About":
                tabs.setCurrentIndex(i)
                return

    def _build_status_bar(self) -> QFrame:
        # Responsive status bar — wide window → single row; narrow window →
        # two rows so buttons never overflow off-screen. ``_arrange_status_bar``
        # below moves widgets between the two row layouts based on width.
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setAutoFillBackground(True)
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setStyleSheet(
            "QFrame#StatusBar { background-color: #0e0f12; "
            "border-bottom: 1px solid #1c1e25; }"
        )
        # Initial fixed height is the wide-mode value — adjusted by
        # ``_arrange_status_bar`` if/when the window is narrow.
        bar.setFixedHeight(64)
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(16, 8, 14, 8)
        outer.setSpacing(6)

        self._status_row1_layout = QHBoxLayout()
        self._status_row1_layout.setContentsMargins(0, 0, 0, 0)
        self._status_row1_layout.setSpacing(10)

        self._status_row2_widget = QWidget()
        self._status_row2_layout = QHBoxLayout(self._status_row2_widget)
        self._status_row2_layout.setContentsMargins(0, 0, 0, 0)
        self._status_row2_layout.setSpacing(10)
        self._status_row2_widget.setVisible(False)  # wide mode default

        outer.addLayout(self._status_row1_layout)
        outer.addWidget(self._status_row2_widget)

        # ---- Title column (wrapped in a QWidget so it can be re-parented) ----
        self._title_col_widget = QWidget()
        title_col = QVBoxLayout(self._title_col_widget)
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)
        self._status_title = QLabel("Idle")
        self._status_title.setObjectName("StatusTitle")
        self._status_title.setStyleSheet(
            "color: #f5f7fa; font-size: 13px; font-weight: 600;"
        )
        self._status_title.setMinimumHeight(18)
        self._status_sub = QLabel("Plug in a controller and click Start.")
        self._status_sub.setObjectName("StatusSub")
        self._status_sub.setStyleSheet("color: #5a606b; font-size: 11px;")
        self._status_sub.setMinimumHeight(16)
        title_col.addWidget(self._status_title)
        title_col.addWidget(self._status_sub)

        self._rate_label = QLabel("")
        self._rate_label.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-family: ui-monospace, Menlo, monospace;"
        )
        self._rate_label.setMinimumWidth(70)
        self._rate_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._activity_dot = QLabel("●")
        self._activity_dot.setObjectName("ActivityDot")
        self._activity_dot.setStyleSheet("color: #2c313b; font-size: 14px;")

        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("PrimaryButton")
        self._start_btn.setMinimumWidth(96)
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._on_start)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("StopButton")
        self._stop_btn.setMinimumWidth(84)
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)

        self._panic_btn = QPushButton("PANIC")
        self._panic_btn.setObjectName("PanicButton")
        self._panic_btn.setMinimumWidth(96)
        self._panic_btn.setFixedHeight(36)
        self._panic_btn.setEnabled(False)
        self._panic_btn.setToolTip("Send all notes off (Ctrl+Shift+P)")
        self._panic_btn.setStyleSheet(
            "QPushButton#PanicButton { color: #f97316; font-weight: 700; }"
        )
        self._panic_btn.clicked.connect(self._on_panic)

        # Layout toggles — Split (side panel) + Console (bottom pane).
        # Click handlers wired in __init__ once dependent widgets exist.
        self._status_divider1 = QFrame()
        self._status_divider1.setFrameShape(QFrame.VLine)
        self._status_divider1.setStyleSheet("color: #2c313b;")

        self._split_btn = QPushButton("Split")
        self._split_btn.setObjectName("LayoutToggle")
        self._split_btn.setCheckable(True)
        self._split_btn.setToolTip("Show controller meter alongside the current tab")
        self._split_btn.setMinimumWidth(72)
        self._split_btn.setFixedHeight(32)

        self._console_btn = QPushButton("Console")
        self._console_btn.setObjectName("LayoutToggle")
        self._console_btn.setCheckable(True)
        self._console_btn.setToolTip("Show or hide the log console at the bottom of the window")
        self._console_btn.setMinimumWidth(92)
        self._console_btn.setFixedHeight(32)

        self._inspect_btn = QPushButton("Inspect")
        self._inspect_btn.setObjectName("LayoutToggle")
        self._inspect_btn.setCheckable(True)
        self._inspect_btn.setToolTip(
            "Open the right-hand inspector — context properties for the selected item"
        )
        self._inspect_btn.setMinimumWidth(88)
        self._inspect_btn.setFixedHeight(32)

        self._3d_btn = QPushButton("3D")
        self._3d_btn.setObjectName("LayoutToggle")
        self._3d_btn.setCheckable(True)
        self._3d_btn.setToolTip(
            "Show a rotating 3D controller behind the app UI"
        )
        self._3d_btn.setMinimumWidth(52)
        self._3d_btn.setFixedHeight(32)

        # Font-scale cluster — A− / A+ so users can size the UI for their
        # screen resolution. Persists across launches via the config file.
        self._font_smaller_btn = QPushButton("A−")
        self._font_smaller_btn.setObjectName("LayoutToggle")
        self._font_smaller_btn.setToolTip("Decrease UI text size")
        self._font_smaller_btn.setFixedSize(40, 32)
        self._font_smaller_btn.clicked.connect(
            lambda: self._adjust_font_scale(-0.1)
        )
        self._font_larger_btn = QPushButton("A+")
        self._font_larger_btn.setObjectName("LayoutToggle")
        self._font_larger_btn.setToolTip("Increase UI text size")
        self._font_larger_btn.setFixedSize(40, 32)
        self._font_larger_btn.clicked.connect(
            lambda: self._adjust_font_scale(+0.1)
        )

        self._status_divider2 = QFrame()
        self._status_divider2.setFrameShape(QFrame.VLine)
        self._status_divider2.setStyleSheet("color: #2c313b;")

        self._record_btn = QPushButton("● Record")
        self._record_btn.setObjectName("RecordButton")
        self._record_btn.setCheckable(True)
        self._record_btn.setToolTip(
            "Record a macro — captures every MIDI message you send. "
            "Click again to stop and name the macro."
        )
        self._record_btn.setMinimumWidth(108)
        self._record_btn.setFixedHeight(36)
        self._record_btn.setStyleSheet(
            "QPushButton#RecordButton { color: #8a9099; }"
            "QPushButton#RecordButton:checked { color: #ef4444; font-weight: 700; }"
        )
        self._record_btn.clicked.connect(self._on_record_toggled)

        # Populate row layouts via the responsive arranger. Initial mode is
        # decided once the window has been sized — call once with current
        # width so we don't start empty.
        self._status_bar = bar
        self._status_bar_compact = None  # force first arrange to apply
        self._arrange_status_bar(self.width() if self.width() > 100 else 1280)
        return bar

    # Status bar mode-switch threshold. Below this, buttons wrap to row 2.
    _STATUS_BAR_COMPACT_WIDTH = 980

    def _arrange_status_bar(self, width: int) -> None:
        """Switch the status bar between single-row (wide) and two-row
        (narrow) layouts so buttons never overflow off-screen."""
        if not hasattr(self, "_status_row1_layout"):
            return  # bar not built yet
        compact = width < self._STATUS_BAR_COMPACT_WIDTH
        if compact == self._status_bar_compact:
            return
        self._status_bar_compact = compact

        # Strip both rows clean (preserves the underlying widgets — Qt
        # re-parents them when we addWidget below).
        for layout in (self._status_row1_layout, self._status_row2_layout):
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)

        if compact:
            # Row 1: status + activity + start/stop/panic
            self._status_row1_layout.addWidget(self._title_col_widget, 1)
            self._status_row1_layout.addWidget(self._rate_label)
            self._status_row1_layout.addWidget(self._activity_dot)
            self._status_row1_layout.addWidget(self._start_btn)
            self._status_row1_layout.addWidget(self._stop_btn)
            self._status_row1_layout.addWidget(self._panic_btn)
            # Row 2: toggles + record (right-aligned)
            self._status_row2_layout.addStretch(1)
            self._status_row2_layout.addWidget(self._split_btn)
            self._status_row2_layout.addWidget(self._console_btn)
            self._status_row2_layout.addWidget(self._inspect_btn)
            self._status_row2_layout.addWidget(self._3d_btn)
            self._status_row2_layout.addWidget(self._font_smaller_btn)
            self._status_row2_layout.addWidget(self._font_larger_btn)
            self._status_row2_layout.addWidget(self._status_divider2)
            self._status_row2_layout.addWidget(self._record_btn)
            self._status_row2_widget.setVisible(True)
            # Hide divider1 — it separated start/panic from toggles in wide
            # mode; in compact mode the row break is the separator.
            self._status_divider1.setVisible(False)
            self._status_bar.setFixedHeight(116)
        else:
            # Everything in row 1
            self._status_row1_layout.addWidget(self._title_col_widget, 1)
            self._status_row1_layout.addWidget(self._rate_label)
            self._status_row1_layout.addWidget(self._activity_dot)
            self._status_row1_layout.addWidget(self._start_btn)
            self._status_row1_layout.addWidget(self._stop_btn)
            self._status_row1_layout.addWidget(self._panic_btn)
            self._status_divider1.setVisible(True)
            self._status_row1_layout.addWidget(self._status_divider1)
            self._status_row1_layout.addWidget(self._split_btn)
            self._status_row1_layout.addWidget(self._console_btn)
            self._status_row1_layout.addWidget(self._inspect_btn)
            self._status_row1_layout.addWidget(self._3d_btn)
            self._status_row1_layout.addWidget(self._font_smaller_btn)
            self._status_row1_layout.addWidget(self._font_larger_btn)
            self._status_row1_layout.addWidget(self._status_divider2)
            self._status_row1_layout.addWidget(self._record_btn)
            self._status_row2_widget.setVisible(False)
            self._status_bar.setFixedHeight(64)

    # Font-scale clamp + step. Lets users size the UI for their resolution.
    _FONT_SCALE_MIN = 0.80
    _FONT_SCALE_MAX = 1.60
    _FONT_SCALE_STEP = 0.10
    _FONT_BASE_PT = 13  # matches styles.qss QWidget { font-size: 13px; }

    def _adjust_font_scale(self, delta: float) -> None:
        """Bump app font scale by *delta* (e.g. +0.1 or -0.1) and apply.

        Two-pronged because Qt's CSS cascade beats ``QApplication.setFont``
        for any widget that has an explicit ``font-size:`` in its
        stylesheet — and styles.qss is full of them. We:

        1. Re-load styles.qss, regex-replace every ``font-size: Npx`` with
           the scaled value, and re-apply via ``app.setStyleSheet``.
        2. Also bump ``QApplication.font()`` so widgets without an explicit
           QSS font-size pick up the new size.
        """
        current = getattr(self, "_font_scale", 1.0)
        new_scale = max(
            self._FONT_SCALE_MIN,
            min(self._FONT_SCALE_MAX, round(current + delta, 2)),
        )
        if new_scale == current:
            return
        self._font_scale = new_scale
        self._apply_font_scale()
        # Persist via the config file shared with other UI prefs.
        from ..paths import config_path
        import json
        path = config_path()
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["font_scale"] = new_scale
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _apply_font_scale(self) -> None:
        """Re-apply the current ``_font_scale`` to the global stylesheet
        and default application font."""
        import re
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont
        from .theme import load_theme_qss
        app = QApplication.instance()
        if app is None:
            return
        scale = getattr(self, "_font_scale", 1.0)
        qss = load_theme_qss("system")

        def _scale_px(match):
            try:
                n = int(match.group(1))
            except ValueError:
                return match.group(0)
            return f"font-size: {max(1, round(n * scale))}px"

        scaled_qss = re.sub(r"font-size:\s*(\d+)px", _scale_px, qss)
        app.setStyleSheet(scaled_qss)
        f: QFont = app.font()
        f.setPointSizeF(self._FONT_BASE_PT * scale)
        app.setFont(f)
        # Many widgets set their own inline stylesheet at construction with
        # an explicit font-size. Walk the widget tree and patch any inline
        # ``font-size: Npx`` we find — same regex, but only on widgets that
        # have ever called setStyleSheet themselves.
        self._patch_inline_font_sizes(scale)

    def _patch_inline_font_sizes(self, scale: float) -> None:
        """Walk every descendant widget and rescale any inline-stylesheet
        ``font-size: Npx`` it has set, preserving the original size as a
        dynamic property so future adjustments scale from the base value."""
        import re
        from PySide6.QtWidgets import QApplication, QWidget
        pattern = re.compile(r"font-size:\s*(\d+)px")

        def _rescale(match):
            n = int(match.group(1))
            return f"font-size: {max(1, round(n * scale))}px"

        for w in QApplication.allWidgets():
            qss = w.styleSheet()
            if not qss or "font-size" not in qss:
                continue
            base = w.property("_baseStyleSheet")
            if base is None:
                base = qss
                w.setProperty("_baseStyleSheet", base)
            scaled = pattern.sub(_rescale, base)
            if scaled != qss:
                w.setStyleSheet(scaled)

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

    def _build_side_panel(self) -> QWidget:
        """Side panel — secondary view docked to the right of the tabs, with
        a dropdown to pick which tab content to mirror. Lazy-builds each
        option on first selection so we don't pay the cost up-front for
        views the user never opens.

        ``_side_meter`` (the Live Preview ControllerMeter) is the default and
        is constructed eagerly so it can be wired into bridge signals from
        ``_wire_signals``.
        """
        from PySide6.QtWidgets import QComboBox, QStackedWidget

        wrap = QWidget()
        wrap.setMinimumWidth(320)
        wrap.setMaximumWidth(560)
        v = QVBoxLayout(wrap)
        v.setContentsMargins(12, 14, 14, 14)
        v.setSpacing(8)

        # Dropdown — pick which secondary view to show.
        picker_row = QHBoxLayout()
        picker_row.setSpacing(8)
        header = QLabel("SPLIT VIEW")
        header.setStyleSheet(
            "color: #5a606b; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1.4px;"
        )
        picker_row.addWidget(header)
        picker_row.addStretch(1)

        self._split_view_picker = QComboBox()
        self._split_view_picker.setFixedHeight(28)
        self._split_view_picker.setStyleSheet(
            "QComboBox { color: #c2c6cc; background-color: #0e0f12; "
            "border: 1px solid #2c313b; border-radius: 4px; "
            "padding: 2px 8px; font-size: 12px; }"
            "QComboBox::drop-down { border: none; }"
        )
        picker_row.addWidget(self._split_view_picker)
        v.addLayout(picker_row)

        # Stacked content — lazy-built per option. Each entry in
        # ``_split_view_factories`` is (label, factory) — the factory is
        # called the first time that option is picked.
        self._split_view_stack = QStackedWidget()
        v.addWidget(self._split_view_stack, 1)

        # Eagerly build the Live Preview so _wire_signals can attach.
        self._side_meter = ControllerMeter()
        self._side_meter.selection_changed.connect(
            lambda p: self.push_inspector_selection("live", p)
        )
        live_idx = self._split_view_stack.addWidget(self._side_meter)

        # Lazy options — built on first selection.
        self._split_view_factories: dict[str, callable] = {}
        self._split_view_indices: dict[str, int] = {"Live Preview": live_idx}

        def _add_lazy(label: str, factory) -> None:
            self._split_view_picker.addItem(label)
            self._split_view_factories[label] = factory

        self._split_view_picker.addItem("Live Preview")
        _add_lazy("Visualise", lambda: VisualiseTab())
        _add_lazy("Bluetooth", lambda: BluetoothTab())
        _add_lazy("Connectors", lambda: ConnectorsTab())
        _add_lazy("Help", lambda: HelpTab())

        self._split_view_picker.currentTextChanged.connect(self._on_split_view_changed)
        return wrap

    def _on_split_view_changed(self, label: str) -> None:
        """Show the chosen view in the split panel — lazy-build on first pick."""
        if label not in self._split_view_indices:
            factory = self._split_view_factories.get(label)
            if factory is None:
                return
            widget = factory()
            self._split_view_indices[label] = self._split_view_stack.addWidget(widget)
        self._split_view_stack.setCurrentIndex(self._split_view_indices[label])

    def _toggle_split_view(self) -> None:
        """Show / hide the right-hand workspace (side panel + its own
        inspector). When split is off, only workspace A and inspector A are
        usable — the right pair collapses to zero width."""
        visible = self._split_btn.isChecked()
        self._side_panel.setVisible(visible)
        # Inspector B follows the split toggle — opening split with the
        # inspector toggle on reveals BOTH inspectors, one per side.
        if visible and self._inspect_btn.isChecked():
            self._inspector_b.show_panel()
        elif not visible:
            self._inspector_b.hide_panel()
        self._rebalance_content_splitter()

    def _toggle_console(self) -> None:
        """Show / hide the bottom log console. Mirrors the console's own
        internal toggle (header arrow) so either control reflects the same
        state. Persists across launches via the console's config."""
        want_open = self._console_btn.isChecked()
        # `set_collapsed(True)` hides the body but keeps the header strip
        # visible — matches what the in-console toggle does and preserves
        # discoverability (the user can still see CONSOLE | ▾ at the bottom).
        self._log_console.set_collapsed(not want_open)

    # Header strip height when a bottom panel is collapsed. Matches the
    # ``setFixedHeight(36)`` used inside ``LogConsole._build_header`` and
    # ``MidiLogPanel._build_header``.
    _COLLAPSED_PANEL_PX = 48
    _OPEN_CONSOLE_PX = 200
    _OPEN_MIDI_PX = 200

    def _set_bottom_panel_sizes(self) -> None:
        """Recompute QSplitter sizes for the bottom dock.

        Single source of truth for log-console + MIDI-activity sizing. Called
        on every panel toggle (and once at startup). Deferred via
        ``QTimer.singleShot(0, ...)`` so it runs after Qt's pending layout
        pass — calling ``setSizes`` mid-layout can be silently dropped if
        the splitter hasn't finished allocating its initial geometry yet.
        """
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_bottom_panel_sizes)
        # Keep the status-bar Console toggle in sync immediately.
        if hasattr(self, "_console_btn"):
            self._console_btn.setChecked(not self._log_console.is_collapsed())

    def _apply_bottom_panel_sizes(self) -> None:
        if not hasattr(self, "_body_splitter"):
            return
        console_h = (
            self._COLLAPSED_PANEL_PX
            if self._log_console.is_collapsed()
            else self._OPEN_CONSOLE_PX
        )
        midi_h = (
            self._COLLAPSED_PANEL_PX
            if self._midi_log_panel.is_collapsed()
            else self._OPEN_MIDI_PX
        )
        # Use the splitter's actual current height; fall back to the parent
        # widget if the splitter hasn't been sized yet.
        total = self._body_splitter.height()
        if total <= 0:
            parent = self._body_splitter.parentWidget()
            total = parent.height() if parent is not None else 720
        total = max(total, 240)
        content_h = max(160, total - console_h - midi_h)
        self._body_splitter.setSizes([content_h, console_h, midi_h])

    def _toggle_inspector(self) -> None:
        """Show / hide the right inspector(s). When split is on, both
        inspectors flip together; otherwise only inspector A is involved."""
        want_open = self._inspect_btn.isChecked()
        if want_open:
            self._inspector_a.show_panel()
            if self._split_btn.isChecked():
                self._inspector_b.show_panel()
        else:
            self._inspector_a.hide_panel()
            self._inspector_b.hide_panel()
        self._rebalance_content_splitter()

    def _toggle_3d(self) -> None:
        """Show / hide the 3D background visualiser. Persists to config.
        No-op when GMB_NO_3D=1 (self._bg_3d is None)."""
        if self._bg_3d is None:
            return
        want_on = self._3d_btn.isChecked()
        if want_on:
            self._bg_3d.show_bg()
        else:
            self._bg_3d.hide_bg()
        _write_bg3d_state(want_on)

    def _on_inspector_visibility(self, _visible: bool) -> None:
        """Keep the status-bar Inspect toggle in sync when an inspector is
        closed via its own × button. The button reflects "any inspector open"."""
        any_visible = self._inspector_a.isVisible() or self._inspector_b.isVisible()
        if self._inspect_btn.isChecked() != any_visible:
            self._inspect_btn.setChecked(any_visible)
        self._rebalance_content_splitter()

    def _toggle_hud(self, visible: bool) -> None:
        """Create or destroy the HUD overlay and persist the preference."""
        HudOverlay.write_visible(visible)
        # Keep menu action in sync regardless of how this was called.
        if hasattr(self, "_hud_action"):
            self._hud_action.setChecked(visible)
        if visible:
            if self._hud is None:
                self._hud = HudOverlay()
                # Seed current state so the HUD isn't stale on first show.
                self._hud.set_preset(getattr(self._mapping, "name", "—") or "—")
                self._hud.set_status(self._stop_btn.isEnabled())
            self._hud.show()
        else:
            if self._hud is not None:
                self._hud.hide()
                self._hud.deleteLater()
                self._hud = None

    def _rebalance_content_splitter(self) -> None:
        """Recompute pane widths after a visibility toggle so panels don't
        appear at 0px or compress workspace A unfairly."""
        sizes = []
        # workspace A — always visible, takes whatever's left.
        sizes.append(1)
        # inspector A — fixed if visible, else 0.
        sizes.append(INSPECTOR_WIDTH if self._inspector_a.isVisible() else 0)
        # side panel (workspace B content) — fixed-ish if visible, else 0.
        sizes.append(320 if self._side_panel.isVisible() else 0)
        # inspector B — fixed if visible, else 0.
        sizes.append(INSPECTOR_WIDTH if self._inspector_b.isVisible() else 0)
        # Scale workspace A to fill remaining width.
        total = max(800, self.width())
        used = sum(sizes[1:])
        sizes[0] = max(400, total - used)
        self._content_splitter.setSizes(sizes)

    # ============================================================== inspector
    # External API for tabs to push their selection into the inspector(s).
    # Workspace A always gets the selection; workspace B mirrors when split
    # is on (so the user can compare the same item across both sides).

    def push_inspector_selection(self, tab_name: str, payload: Optional[dict]) -> None:
        self._inspector_a.set_selection(tab_name, payload)
        if self._split_btn.isChecked():
            self._inspector_b.set_selection(tab_name, payload)
        # Auto-open the inspector on first selection so the user sees the
        # payload immediately — same UX as Figma.
        if payload is not None and not self._inspect_btn.isChecked():
            self._inspect_btn.setChecked(True)
            self._toggle_inspector()
        # Hook the live oscilloscope scope if this is a "live" tab selection with an axis.
        if tab_name == "live" and payload and payload.get("kind", "").lower() in ("axis", "stick", "trigger"):
            self._update_live_scope(self._inspector_a, payload)
            if self._split_btn.isChecked():
                self._update_live_scope(self._inspector_b, payload)
        if self._split_btn.isChecked():
            self._inspector_b.set_selection(tab_name, payload)
        # Auto-open the inspector on first selection so the user sees the
        # payload immediately — same UX as Figma.
        if payload is not None and not self._inspect_btn.isChecked():
            self._inspect_btn.setChecked(True)
            self._toggle_inspector()

    def _on_mapping_selection(self, payload: dict) -> None:
        """Route a MappingEditor selection to the matching inspector renderer.

        Trigger/stick/touchpad/button/hat rows carry a config dataclass or channel override —
        dispatch those to the dedicated renderers. Plain axes fall back to the generic
        "mapping" key-value renderer.
        """
        kind = payload.get("kind", "")
        if kind == "trigger":
            tab = "mapping_trigger"
        elif kind == "stick":
            tab = "mapping_stick"
        elif kind == "touchpad":
            tab = "mapping_touchpad"
        elif kind == "button_editor":
            tab = "button_editor"
        elif kind == "hat_editor":
            tab = "hat_editor"
        elif kind == "mapping_globals":
            tab = "mapping_globals"
        else:
            tab = "mapping"
        self.push_inspector_selection(tab, payload)

    def _on_mapping_changed(self) -> None:
        """Debounced handler: restart the 500ms timer whenever the mapping
        mutates. Only persist when the timer finally expires (user stops
        dragging/tweaking).
        """
        self._mapping_save_timer.stop()
        self._mapping_save_timer.start()

    def _on_mapping_save_timeout(self) -> None:
        """Persist the mapping to disk after debounce window expires."""
        _save_last_mapping(self._mapping)

    def _build_tabs(self) -> ResponsiveTabWidget:
        tabs = ResponsiveTabWidget()

        # Live tab — primary meter always present. Secondary meter + Pro
        # nudge banner are hidden until a second controller is wired in.
        self._meter = ControllerMeter()
        self._meter.selection_changed.connect(
            lambda p: self.push_inspector_selection("live", p)
        )
        self._meter2 = ControllerMeter()
        self._meter2.setVisible(False)
        self._live_splitter = QSplitter(Qt.Horizontal)
        self._live_splitter.setHandleWidth(6)
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
        tabs.addTab(self._scrollable(self._visualise), "Visualise")

        self._mapping_editor = MappingEditor(self._mapping)
        self._mapping_editor.set_worker(self._bridge.worker)
        self._mapping_editor.upgrade_clicked.connect(self._open_upgrade)
        self._mapping_editor.activate_clicked.connect(self._enter_license_key)
        # Forward row clicks into the right-hand inspector (Figma pattern).
        # Trigger/stick/touchpad rows get a richer renderer; everything else
        # falls back to the generic key-value mapping renderer.
        self._mapping_editor.selection_changed.connect(
            self._on_mapping_selection
        )
        # Debounced persistence on config mutations in the inspector.
        self._mapping_editor.mapping_changed.connect(self._on_mapping_changed)
        tabs.addTab(self._scrollable(self._mapping_editor), "Mapping")

        # Templates — visual mapping builder + multi-format exporter.
        # Sits between Mapping (Pro table view) and Presets so users can
        # iterate visually then save the result alongside their named presets.
        self._template_builder = TemplateBuilderTab(self._mapping)
        self._template_builder.mapping_changed.connect(self._on_template_mapping_changed)
        tabs.addTab(self._scrollable(self._template_builder), "Templates")

        self._presets = PresetManager(lambda: self._mapping)
        self._presets.upgrade_clicked.connect(self._open_upgrade)
        self._presets.activate_clicked.connect(self._enter_license_key)
        self._presets.preset_loaded.connect(self._on_preset_loaded)
        self._presets.mapping_changed.connect(self._on_preset_mapping_changed)
        self._presets.selection_changed.connect(
            lambda p: self.push_inspector_selection("presets", p)
        )
        tabs.addTab(self._scrollable(self._presets), "Presets")

        self._marketplace = MarketplaceTab()
        self._marketplace.preset_chosen.connect(self._on_preset_loaded)
        self._marketplace.status_message.connect(self._on_status)
        self._marketplace.selection_changed.connect(
            lambda p: self.push_inspector_selection("marketplace", p)
        )
        tabs.addTab(self._marketplace, "Marketplace")

        self._connectors = ConnectorsTab()
        self._connectors.status_message.connect(self._on_status)
        self._connectors.selection_changed.connect(
            lambda p: self.push_inspector_selection("connectors", p)
        )
        self._connectors.test_note_requested.connect(self._on_test_note)
        tabs.addTab(self._connectors, "Connectors")

        self._bluetooth = BluetoothTab()
        self._bluetooth.status_message.connect(self._on_status)
        tabs.addTab(self._bluetooth, "Bluetooth")

        self._settings = SettingsPanel(self._mapping)
        self._settings.settings_changed.connect(self._on_settings_changed)
        self._settings.recalibrate_clicked.connect(self._on_recalibrate)
        self._settings.multi_mode_changed.connect(self._on_multi_mode_changed)
        tabs.addTab(self._scrollable(self._settings), "Settings")

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

    def _scrollable(self, widget: QWidget) -> QWidget:
        """Wrap a tab in a scroll area so it shrinks gracefully on narrow
        windows. Tabs that already self-scroll (Marketplace, Connectors,
        Bluetooth) opt out by being added directly with `addTab`.
        """
        from PySide6.QtWidgets import QScrollArea
        area = QScrollArea()
        area.setWidget(widget)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        # Horizontal scrollbar as needed — vertical always available.
        return area

    def _wrap_padded(self, widget: QWidget) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(20, 20, 20, 20)
        v.addWidget(widget)
        return wrap

    def _build_about_tab(self) -> QWidget:
        """Build the About tab using the polished AboutTab widget with Pro features."""
        self._tier_label = QLabel()
        about_tab = AboutTab(
            tier_label_widget=self._tier_label,
            on_upgrade=self._open_upgrade,
            on_enter_license=self._enter_license_key,
            on_export_pack=self._on_export_pack,
            on_import_pack=self._on_import_pack,
            refresh_tier=self._refresh_tier_label,
        )
        self._refresh_tier_label()
        return about_tab

    def _update_live_scope(self, inspector, payload: dict) -> None:
        """Hook a newly-rendered AxisScope widget to bridge axis_value signals.

        When the user selects an axis in the Live tab, the inspector renders
        a new AxisScope widget. This method finds that widget inside the
        inspector's body and connects it to the bridge worker's axis_value
        signal so live updates flow in at 100 Hz, repainting at 30 Hz internally.
        """
        axis_idx = payload.get("index", -1)
        if not isinstance(axis_idx, int) or axis_idx < 0:
            return

        # Try to find the freshly-rendered scope widget by its objectName.
        scope: Optional[AxisScope] = None
        body = inspector._body_host
        if body is not None:
            for child in body.findChildren(AxisScope):
                if child.objectName() == f"LiveScope_{axis_idx}":
                    scope = child
                    break

        if scope is None:
            return

        # Unsubscribe the old scope (if any) for this axis.
        inspector_id = id(inspector)
        old_scope = self._live_scope_widgets.get((inspector_id, axis_idx))
        if old_scope is not None:
            try:
                self._bridge.worker.axis_value.disconnect(old_scope.add_sample)
            except Exception:
                pass

        # Subscribe the new scope to axis updates.
        self._live_scope_widgets[(inspector_id, axis_idx)] = scope
        self._bridge.worker.axis_value.connect(
            lambda idx, val, s=scope: s.add_sample(val) if idx == axis_idx else None
        )

    # ============================================================== signal wiring

    def _wire_signals(self) -> None:
        # Slot 0 wiring is byte-identical to V1.1 — keeps the single-controller
        # path unchanged. Slot 1 wiring is deferred until configure() actually
        # spins up a second bridge.
        self._wire_bridge_to_meter(self._bridge, self._meter, primary=True)
        # Side-panel meter mirrors the primary bridge so the user can keep
        # an eye on live controller activity while editing on any tab.
        # `primary=False` keeps it out of the shared status-bar wiring loop.
        self._wire_bridge_to_meter(self._bridge, self._side_meter, primary=False)
        # Mirror primary bridge activity into the bottom console.
        self._log_console.attach_bridge_signals(self._bridge.worker)
        # Feed the Visualise tab from the same primary worker.
        self._visualise.attach_bridge_signals(self._bridge.worker)
        # Wire MIDI message details to the activity log panel
        self._bridge.worker.midi_message.connect(self._on_midi_message)

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
        # Feature #15: Program Change → preset hot-swap (primary bridge only).
        if primary:
            w.preset_change_requested.connect(self._on_pc_preset_requested)
            # Setlist mode: step-through signal (primary bridge only).
            w.setlist_step.connect(self._on_setlist_step)

    # ============================================================== slots

    # ============================================================== macro recorder

    def _on_record_toggled(self) -> None:
        """Toggle macro recording on/off via the status-bar Record button."""
        if self._record_btn.isChecked():
            # Start recording
            self._bridge.worker.start_recording()
            self._on_status("Recording macro — perform your actions now")
        else:
            # Stop — ask for a name and save
            macro = self._bridge.worker.stop_recording()
            if not macro.events:
                self._record_btn.setChecked(False)
                self._on_status("Recording cancelled — no MIDI messages captured")
                return
            name, ok = QInputDialog.getText(
                self,
                "Save Macro",
                "Macro name:",
                text=f"Macro {len(self._mapping.macros) + 1}",
            )
            if ok and name.strip():
                macro.name = name.strip()
                self._mapping.macros.append(macro)
                self._on_mapping_changed()
                self._on_status(
                    f"Macro \"{macro.name}\" saved — "
                    f"{len(macro.events)} events, {macro.duration_ms} ms"
                )
            else:
                self._on_status("Macro discarded")

    # ============================================================== bridge start/stop

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
        self._panic_btn.setEnabled(True)
        self._status_title.setText("Starting…")
        self._status_sub.setText("Detecting controller and opening MIDI port.")

        # Calibration dialog shows immediately and follows worker signals.
        self._calibration_dialog = CalibrationDialog(self)
        self._multi.start()

    def _on_stop(self) -> None:
        self._multi.stop()
        self._stop_btn.setEnabled(False)

    def _on_panic(self) -> None:
        """Send all notes off on every channel."""
        if self._bridge is not None:
            self._bridge.worker.panic()

    def _on_test_note(self) -> None:
        """Send a test MIDI note to verify connector DAW connectivity."""
        if self._bridge is not None:
            self._bridge.worker.send_test_note(channel=0, note=60, velocity=100, duration_ms=200)

    def _on_latency_test(self) -> None:
        """Run a latency test to measure bridge roundtrip time."""
        if not self._stop_btn.isEnabled():
            QMessageBox.information(
                self, "Start the bridge first",
                "Latency testing requires the bridge to be running. "
                "Click Start, then try again.",
            )
            return
        if self._bridge is not None and self._bridge.worker is not None:
            self._bridge.worker.run_latency_test()
            self._on_status("Latency test running…")

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
        if self._hud is not None:
            self._hud.set_status(True)
            self._hud.set_preset(getattr(self._mapping, "name", "—") or "—")
        if self._calibration_dialog and not self._calibration_dialog.isVisible():
            # Dialog already closed by user — nothing to do.
            self._calibration_dialog = None

    def _on_stopped(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._panic_btn.setEnabled(False)
        self._refresh_status_idle()
        self._meter.set_connected(False)
        if self._tray is not None:
            self._tray.set_running(False)
        if self._hud is not None:
            self._hud.set_status(False)

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Bridge error", message)
        self._on_stopped()

    def _on_controller_info(self, info) -> None:
        if info is None:
            self._meter.set_connected(False)
            # Only start the reconnect flow if the bridge was actively running
            # AND auto-reconnect is enabled in the current mapping.
            if (self._stop_btn.isEnabled()
                    and self._mapping.auto_reconnect_enabled
                    and not self._reconnect_overlay.isVisible()):
                self._start_reconnect_flow()
        else:
            self._meter.set_connected(True, info.name)
            # If the overlay is counting/retrying, a non-None info means
            # reconnect succeeded — notify the overlay and stop retrying.
            if self._reconnect_overlay.isVisible():
                self._reconnect_retry_timer.stop()
                self._reconnect_overlay.notify_success()
            
            # Test wizard on first-time controller connect
            if (not self._mapping.config.get("controller_test_wizard_disabled", False)
                    and info.name not in seen_controllers()):
                QTimer.singleShot(800, lambda: self._run_test_wizard(info.name))

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

    def _run_test_wizard(self, controller_name: str) -> None:
        """Launch the test wizard for a new controller."""
        if self._bridge.worker is None or self._bridge.worker.controller_info is None:
            return
        
        info = self._bridge.worker.controller_info
        self._test_wizard = ControllerTestWizard(info, self)
        self._test_wizard.wizard_complete.connect(
            lambda missing: self._on_wizard_complete(controller_name, missing)
        )
        self._test_wizard.show()

    def _on_wizard_complete(self, controller_name: str, missing: list) -> None:
        """Record controller as seen after wizard completion."""
        mark_seen(controller_name)
        if self._test_wizard:
            self._test_wizard.deleteLater()
            self._test_wizard = None

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
        if self._hud is not None:
            self._hud.set_preset(mapping.name or "—")

    def _on_preset_mapping_changed(self, mapping: Mapping) -> None:
        """Setlist (and future dialogs) on the Presets tab saved edits to the mapping.

        Apply the updated mapping to the bridge and persist it. No dialog —
        the user already confirmed in the originating dialog.
        """
        self._mapping = mapping
        self._multi.apply_mapping(mapping)
        self._mapping_editor.set_mapping(mapping)
        _save_last_mapping(mapping)

    def _on_pc_preset_requested(self, slug: str) -> None:
        """Feature #15: DAW sent a Program Change — load the matching preset.

        Runs on the GUI thread (queued connection from the rtmidi callback
        thread). Silent if the slug doesn't resolve so a mis-mapped PC number
        doesn't interrupt a live performance with a dialog.
        """
        from . import presets as _presets
        mapping = _presets.load_preset_by_slug(slug)
        if mapping is None:
            self._on_status(f"PC hot-swap: preset '{slug}' not found")
            return
        self._mapping = mapping
        self._multi.apply_mapping(mapping)
        self._mapping_editor.set_mapping(mapping)
        _save_last_mapping(mapping)
        self._on_status(f"PC hot-swap: loaded '{mapping.name}'")

    def _on_setlist_step(self, slug: str, index: int, total: int) -> None:
        """Setlist mode: Next/Prev button pressed — load the indicated preset.

        Runs on the GUI thread (queued connection from the bridge worker).
        Silent if the slug doesn't resolve so a mis-configured setlist doesn't
        interrupt a live performance with a dialog.
        """
        from .. import presets as _presets
        mapping = _presets.load_preset_by_slug(slug)
        if mapping is None:
            self._on_status(f"Setlist: preset '{slug}' not found ({index + 1}/{total})")
            return
        self._mapping = mapping
        self._multi.apply_mapping(mapping)
        self._mapping_editor.set_mapping(mapping)
        _save_last_mapping(mapping)
        self._on_status(
            f"Setlist: {index + 1}/{total} — loaded '{mapping.name}'"
        )

    def _on_corner_triggered(self, side: str, kind: str, sector: int) -> None:
        # Flash the activity dot and surface the event in the status subtitle.
        if kind == "on":
            self._status_sub.setText(f"Corner {side}{sector} → MIDI note fired")
        self._on_midi_sent()

    # ============================================================== auto-reconnect

    def _start_reconnect_flow(self) -> None:
        """Begin the auto-reconnect loop after a controller drop."""
        _log.info("Auto-reconnect: controller lost — starting retry loop")
        self._status_sub.setText("Controller disconnected — retrying…")
        self._reconnect_overlay.start_countdown()
        self._reconnect_retry_timer.start()
        # Trigger an immediate first retry without waiting 1 second.
        self._attempt_reconnect()

    def _on_reconnect_tick(self) -> None:
        """Called every second while the overlay is counting. Try to restart."""
        # Only attempt while the overlay is still in counting state (it may have
        # already timed out and moved to FAILED, in which case we stop the timer).
        if not self._reconnect_overlay.isVisible():
            self._reconnect_retry_timer.stop()
            return
        self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        """Try to spin the bridge back up via a fresh start cycle."""
        try:
            # Gracefully stop any partially-running bridge state before restarting.
            self._multi.stop()
            slot_count = self._multi.configure(
                self._mapping, self._settings.current_multi_mode(),
            )
            self._bridge = self._multi.primary()
            self._sync_live_layout(slot_count)
            self._multi.start()
        except Exception as e:
            _log.debug("Auto-reconnect attempt failed: %s", e)

    def _on_reconnect_cancelled(self) -> None:
        """User dismissed the overlay — stop the retry ticker and go idle."""
        self._reconnect_retry_timer.stop()
        self._multi.stop()
        self._on_stopped()

    def _on_reconnect_retry(self) -> None:
        """User clicked Retry from the FAILED state — reset and try again."""
        self._attempt_reconnect()

    def _on_reconnect_esc(self) -> None:
        """Esc key — only acts if the overlay is visible."""
        if self._reconnect_overlay.isVisible():
            self._reconnect_overlay.dismiss()

    def _flush_rate(self) -> None:
        # Convert the half-second tally to a per-second rate, round to nearest 10.
        rate = self._midi_count * 2
        if rate > 0:
            rounded = (rate // 10) * 10 if rate >= 30 else rate
            self._rate_label.setText(f"{rounded}/s")
        elif self._rate_label.text():
            self._rate_label.setText("")
        if self._hud is not None:
            self._hud.set_throughput(rate)
        self._midi_count = 0

    def _on_midi_sent(self) -> None:
        self._midi_count += 1
        self._activity_dot.setStyleSheet("color: #2dd4bf; font-size: 18px;")
        self._activity_timer.start(120)

    def _fade_activity(self) -> None:
        self._activity_dot.setStyleSheet("color: #2c313b; font-size: 18px;")

    def _on_midi_message(self, direction: str, channel: int, status: int, data1: int, data2: int, label: str) -> None:
        """Handle MIDI message detail from the bridge for the activity log."""
        if direction == "sent":
            self._midi_log_panel.append_sent(channel, label, data1, data2)
        elif direction == "received":
            self._midi_log_panel.append_received(channel, label, data1, data2)

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

    def _autosave_tick(self) -> None:
        '''Background task: save a timestamped snapshot of the current mapping
        and prune old backups. Wrapped in try/except so disk errors never break
        the app.'''
        try:
            autobackup.save_snapshot(self._mapping)
            autobackup.prune_old_snapshots(keep=30)
        except Exception:
            # Silently fail — this is a background task, not critical
            pass

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


    # ============================================================== command palette

    def _register_palette_commands(self) -> List[Command]:
        """Build the full command list. Called fresh each time the palette opens
        so dynamic entries (e.g. preset names) are always current."""
        cmds: List[Command] = []

        # ---- Bridge control ----
        cmds.append(Command("Start bridge", "Start MIDI bridging", self._on_start))
        cmds.append(Command("Stop bridge", "Stop MIDI bridging", self._on_stop))
        cmds.append(Command("Panic — all notes off", "Send all notes off (emergency stop)", self._on_panic))
        cmds.append(Command("Toggle bridge", "Start or stop the bridge", self._toggle_bridge))

        # ---- Layout toggles ----
        cmds.append(Command(
            "Toggle Split view", "Show/hide the side controller meter",
            lambda: (self._split_btn.setChecked(not self._split_btn.isChecked()),
                     self._toggle_split_view()),
        ))
        cmds.append(Command(
            "Toggle Console", "Show/hide the log console",
            lambda: (self._console_btn.setChecked(not self._console_btn.isChecked()),
                     self._toggle_console()),
        ))
        cmds.append(Command(
            "Toggle Inspector", "Show/hide the right-hand inspector panel",
            lambda: (self._inspect_btn.setChecked(not self._inspect_btn.isChecked()),
                     self._toggle_inspector()),
        ))
        cmds.append(Command(
            "Toggle 3D background", "Show/hide the rotating 3D controller",
            lambda: (self._3d_btn.setChecked(not self._3d_btn.isChecked()),
                     self._toggle_3d()),
        ))

        # ---- Tab navigation ----
        tab_names = [
            "Live", "Visualise", "Mapping", "Templates", "Presets",
            "Marketplace", "Connectors", "Bluetooth", "Settings", "Help", "About",
        ]
        tabs = getattr(self, "_tabs_ref", None)
        if tabs is not None:
            for name in tab_names:
                def _switch(n=name, t=tabs):
                    for i in range(t.count()):
                        if t.tabText(i) == n:
                            t.setCurrentIndex(i)
                            break
                cmds.append(Command(f"Switch to {name}", f"Open the {name} tab", _switch))

        # ---- Presets ----
        from .. import presets as preset_io
        for slug in preset_io.list_presets():
            def _load(s=slug):
                mapping = preset_io.load_preset_by_slug(s)
                if mapping is not None:
                    self._on_preset_loaded(mapping)
            cmds.append(Command(f"Load preset: {slug}", "Load this saved preset", _load))

        cmds.append(Command(
            "Save preset as snapshot",
            "Save the current mapping as a timestamped snapshot",
            lambda: (autobackup.save_snapshot(self._mapping),
                     self._on_status("Snapshot saved")),
        ))

        # ---- Licensing ----
        cmds.append(Command("Recover license", "Open the license recovery page",
                            lambda: webbrowser.open(RECOVERY_URL)))
        cmds.append(Command("Enter license key", "Activate a Pro license",
                            self._enter_license_key))
        cmds.append(Command("Upgrade to Pro", "Open the store page",
                            self._open_upgrade))

        # ---- Settings and tools ----
        cmds.append(Command("Open Settings", "Jump to the Settings tab",
                            self._focus_settings_tab))
        cmds.append(Command("Recalibrate sticks",
                            "Run stick dead-zone calibration against the live controller",
                            self._on_recalibrate))
        cmds.append(Command("Export crash bundle",
                            "Export a zip of crash logs for bug reports",
                            self._on_export_crash_bundle))
        cmds.append(Command("Export cheat sheet",
                            "Export the current mapping as a PDF cheat sheet",
                            self._on_export_cheatsheet_cmd))
        cmds.append(Command("Run marketplace seed",
                            "Re-seed bundled starter presets (admin)",
                            self._on_marketplace_seed))

        return cmds

    def _open_command_palette(self) -> None:
        """Instantiate and show the command palette (modal)."""
        commands = self._register_palette_commands()
        palette = CommandPalette(commands, parent=self)
        palette.exec()

    # ---- palette action helpers ----

    def _on_export_crash_bundle(self) -> None:
        from ..crash_reporter import export_bundle
        try:
            path = export_bundle()
            QMessageBox.information(
                self, "Crash bundle exported",
                f"Bundle saved to:\n{path}\n\nAttach this file to a bug report.",
            )
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _on_export_cheatsheet_cmd(self) -> None:
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog
        from .. import cheatsheet as cheatsheet_mod

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_"
                            for c in self._mapping.name) or "mapping"
        default = str(Path.home() / "Desktop" / f"{safe_name}_cheatsheet.pdf")
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export cheat sheet", default, "PDF (*.pdf)",
        )
        if dest:
            try:
                cheatsheet_mod.render_cheatsheet(self._mapping, Path(dest))
                self._on_status(f"Cheat sheet saved: {dest}")
            except Exception as e:
                QMessageBox.warning(self, "Export failed", str(e))

    def _on_marketplace_seed(self) -> None:
        from ..presets import seed_user_presets_once
        from ..paths import presets_dir
        marker = presets_dir() / ".seeded"
        if marker.exists():
            marker.unlink()
        n = seed_user_presets_once()
        self._on_status(f"Marketplace seed: {n} preset(s) restored")

    # ============================================================== resize

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        # Reflow the status bar between 1-row (wide) and 2-row (narrow)
        # modes whenever the window changes width.
        self._arrange_status_bar(event.size().width())

    # ============================================================== close

    def closeEvent(self, event: QCloseEvent) -> None:
        _save_last_mapping(self._mapping)
        self._multi.shutdown()
        autobackup.mark_clean_shutdown()
        event.accept()

    # ============================================================== drag-drop

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag if any dropped file is .json or .gmbpack."""
        mime = event.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            for url in urls:
                path_str = url.toLocalFile()
                if path_str:
                    ext = Path(path_str).suffix.lower()
                    if ext in {'.json', '.gmbpack'}:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Import dropped preset/pack files."""
        mime = event.mimeData()
        if not mime.hasUrls():
            return

        imported_presets = 0
        imported_packs = 0
        errors = []

        for url in mime.urls():
            path_str = url.toLocalFile()
            if not path_str:
                continue

            path = Path(path_str)
            ext = path.suffix.lower()

            try:
                if ext == '.json':
                    # Load as a mapping
                    data = json.loads(path.read_text(encoding='utf-8'))
                    mapping = Mapping.from_dict(data)
                    self._mapping_editor.set_mapping(mapping)
                    imported_presets += 1
                elif ext == '.gmbpack':
                    # Use the existing import_pack handler
                    imported_mapping, report = import_pack(path)
                    if imported_mapping:
                        self._mapping_editor.set_mapping(imported_mapping)
                        imported_packs += 1
                    else:
                        imported_packs += 1
            except Exception as e:
                errors.append(f"{path.name}: {str(e)}")

        # Show summary
        summary_parts = []
        if imported_presets:
            summary_parts.append(f"{imported_presets} preset(s)")
        if imported_packs:
            summary_parts.append(f"{imported_packs} pack(s)")

        if summary_parts:
            msg = f"Imported {', '.join(summary_parts)}"
            if errors:
                msg += f"\n\nFailed: {len(errors)}"
                for err in errors:
                    msg += f"\n  • {err}"
                QMessageBox.warning(self, "Import complete", msg)
            else:
                self._on_status(msg)
        elif errors:
            QMessageBox.warning(
                self, "Import failed",
                f"Could not import files:\n" + "\n".join(f"  • {e}" for e in errors)
            )
