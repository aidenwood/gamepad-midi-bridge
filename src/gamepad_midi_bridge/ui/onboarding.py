"""First-launch onboarding wizard.

Walks a fresh user through the four things that have to be true before the
bridge can fire a single MIDI note:

    1. The app is welcomed (sets expectations, kills the blank-slate moment).
    2. A controller is physically connected (pygame can see it).
    3. A virtual MIDI port can be opened (on Windows that means loopMIDI).
    4. At least one connector template has been installed in a host.
    5. Stick calibration baseline is captured (handled live by the bridge).

We deliberately keep the wizard read-only with respect to mappings/presets —
its job is environment readiness, not configuration. Anything beyond the bare
minimum is left for the main window's tabs.

Why a dedicated module: the wizard is one-shot UI that should never load on
subsequent launches. Keeping it isolated means PyInstaller can drop it from
hot paths, and the main_window stays focused on steady-state UX.
"""
from __future__ import annotations

import json
import sys
import webbrowser
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import APP_NAME
from ..connectors import all_connectors
from ..controller import ControllerReader
from ..midi_backend import MidiPortError, open_port, close_port
from ..paths import config_path
from ..telemetry import send_event


LOOPMIDI_URL = "https://www.tobias-erichsen.de/software/loopmidi.html"
ONBOARDING_FLAG = "onboarding_complete"


# ============================================================== persistence

def _read_config() -> dict:
    """Best-effort read of the shared config blob. Empty dict on any failure
    so a corrupt config can't block first-launch flow."""
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_config(cfg: dict) -> None:
    config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def is_first_launch() -> bool:
    """True when the onboarding flag has never been set. Any falsy value (missing
    key, explicit false) is treated as first launch — we only suppress when the
    user has explicitly completed the wizard at least once."""
    return not bool(_read_config().get(ONBOARDING_FLAG, False))


def mark_complete() -> None:
    """Write the flag so we never show the wizard again on this machine."""
    cfg = _read_config()
    cfg[ONBOARDING_FLAG] = True
    _write_config(cfg)


# ============================================================== wizard

class OnboardingWizard(QDialog):
    """Modal six-step wizard. Emits `onboarding_complete` on success and
    `start_requested` if the user wants the bridge to fire immediately."""

    onboarding_complete = Signal()
    start_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setModal(True)
        self.setFixedSize(640, 480)

        self._controller_detected = False
        self._steps_completed = 0
        self._installed_slugs: List[str] = []
        # Holds the test port so we can close it cleanly when the wizard exits.
        self._test_port = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # Steps are added in display order so indexes match the spec.
        self._stack.addWidget(self._build_welcome())        # 0
        self._stack.addWidget(self._build_controller())     # 1
        self._stack.addWidget(self._build_midi())           # 2
        self._stack.addWidget(self._build_connectors())     # 3
        self._stack.addWidget(self._build_calibration())    # 4
        self._stack.addWidget(self._build_done())           # 5

        root.addWidget(self._build_footer())
        self._update_footer()

        send_event("onboarding_started")

    # ============================================================== steps

    def _build_welcome(self) -> QWidget:
        return self._page(
            title="Turn your gamepad into a MIDI controller.",
            body=(
                "Three minutes to set up. Skip if you've done this dance before.\n\n"
                "We'll find your controller, open a virtual MIDI port, wire up the "
                "hosts you use, and calibrate your sticks. Nothing leaves your machine."
            ),
        )

    def _build_controller(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 36, 36, 36)
        v.setSpacing(14)

        heading = QLabel("Looking for your controller…")
        heading.setStyleSheet("font-size: 18px; font-weight: 600; color: #f5f7fa;")
        v.addWidget(heading)

        self._controller_status = QLabel("Scanning…")
        self._controller_status.setStyleSheet("color: #c2c6cc;")
        self._controller_status.setWordWrap(True)
        v.addWidget(self._controller_status)

        hint = QLabel(
            "Works with PS5 DualSense, Xbox, Switch Pro, and most generic gamepads. "
            "USB or Bluetooth — your call."
        )
        hint.setStyleSheet("color: #8a9099; font-size: 12px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        retry = QPushButton("Scan again")
        retry.clicked.connect(self._poll_controller)
        v.addWidget(retry, alignment=Qt.AlignLeft)

        v.addStretch(1)
        # Defer the first poll so the page actually paints before pygame churns.
        QTimer.singleShot(150, self._poll_controller)
        return page

    def _build_midi(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 36, 36, 36)
        v.setSpacing(14)

        heading = QLabel("Opening a virtual MIDI port…")
        heading.setStyleSheet("font-size: 18px; font-weight: 600; color: #f5f7fa;")
        v.addWidget(heading)

        self._midi_status = QLabel("Probing the MIDI backend…")
        self._midi_status.setStyleSheet("color: #c2c6cc;")
        self._midi_status.setWordWrap(True)
        v.addWidget(self._midi_status)

        self._loopmidi_btn = QPushButton("Download loopMIDI")
        self._loopmidi_btn.clicked.connect(lambda: webbrowser.open(LOOPMIDI_URL))
        self._loopmidi_btn.setVisible(False)
        v.addWidget(self._loopmidi_btn, alignment=Qt.AlignLeft)

        retry = QPushButton("Try again")
        retry.clicked.connect(self._poll_midi)
        v.addWidget(retry, alignment=Qt.AlignLeft)

        v.addStretch(1)
        QTimer.singleShot(150, self._poll_midi)
        return page

    def _build_connectors(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 36, 36, 36)
        v.setSpacing(10)

        heading = QLabel("Pick the hosts you'll perform with.")
        heading.setStyleSheet("font-size: 18px; font-weight: 600; color: #f5f7fa;")
        v.addWidget(heading)

        sub = QLabel(
            "We'll write a small mapping file into each host's config folder. "
            "You can manage these later from the Connectors tab."
        )
        sub.setStyleSheet("color: #8a9099;")
        sub.setWordWrap(True)
        v.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        rows = QVBoxLayout(inner)
        rows.setContentsMargins(0, 8, 0, 0)
        rows.setSpacing(8)

        # Build one row per connector. Each row owns its own install button so the
        # user can opt in selectively without ticking a checkbox first.
        for connector in all_connectors():
            rows.addWidget(self._build_connector_row(connector))
        rows.addStretch(1)

        scroll.setWidget(inner)
        v.addWidget(scroll, 1)
        return page

    def _build_connector_row(self, connector) -> QWidget:
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background-color: #16181d; border: 1px solid #24262d; "
            "border-radius: 6px; }"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(12)

        check = QCheckBox(connector.display_name)
        check.setStyleSheet("color: #f5f7fa; font-weight: 500;")
        h.addWidget(check)

        desc = QLabel(connector.description or "")
        desc.setStyleSheet("color: #8a9099; font-size: 12px;")
        desc.setWordWrap(True)
        h.addWidget(desc, 1)

        install_btn = QPushButton("Install")
        install_btn.setObjectName("PrimaryButton")

        status_label = QLabel("")
        status_label.setStyleSheet("color: #2dd4bf; font-size: 12px;")
        h.addWidget(status_label)
        h.addWidget(install_btn)

        # Disable up-front when nothing's detected so users aren't promised
        # a no-op install. We still let them tick the box for visibility.
        hosts = []
        try:
            hosts = connector.detect()
        except Exception:
            hosts = []
        if not hosts:
            install_btn.setEnabled(False)
            status_label.setText("not detected")
            status_label.setStyleSheet("color: #8a9099; font-size: 12px;")

        def do_install() -> None:
            check.setChecked(True)
            successes = 0
            for host in hosts:
                try:
                    res = connector.install(host)
                except Exception as e:
                    res = type("R", (), {"success": False, "message": str(e)})()
                if getattr(res, "success", False):
                    successes += 1
            if successes:
                status_label.setText("installed")
                install_btn.setEnabled(False)
                self._installed_slugs.append(connector.slug)
                send_event("onboarding_connector_installed", connector=connector.slug)
            else:
                status_label.setText("failed — see Connectors tab")
                status_label.setStyleSheet("color: #f97373; font-size: 12px;")

        install_btn.clicked.connect(do_install)
        return row

    def _build_calibration(self) -> QWidget:
        return self._page(
            title="Stick calibration runs at Start.",
            body=(
                "When you hit Start Bridging, keep your hands off the controller "
                "for two seconds. We sample resting position to compensate for drift "
                "automatically — most modern sticks need it.\n\n"
                "If a stick is too far gone for software compensation, we'll flag it."
            ),
        )

    def _build_done(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 36, 36, 36)
        v.setSpacing(14)

        heading = QLabel("You're ready.")
        heading.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f7fa;")
        v.addWidget(heading)

        body = QLabel(
            "Hit Start Bridging when you want to perform. Tweak mappings, browse "
            "presets, and add connectors from the main window any time."
        )
        body.setStyleSheet("color: #c2c6cc;")
        body.setWordWrap(True)
        v.addWidget(body)

        v.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        finish_only = QPushButton("Close")
        finish_only.clicked.connect(self._finish_without_start)
        row.addWidget(finish_only)

        start = QPushButton("Start Bridging")
        start.setObjectName("PrimaryButton")
        start.setMinimumWidth(160)
        start.clicked.connect(self._finish_and_start)
        row.addWidget(start)
        v.addLayout(row)
        return page

    # ============================================================== footer

    def _build_footer(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            "background-color: #16181d; border-top: 1px solid #24262d;"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(10)

        self._skip_btn = QPushButton("Skip setup")
        self._skip_btn.setFlat(True)
        self._skip_btn.setStyleSheet("color: #8a9099;")
        self._skip_btn.clicked.connect(self._on_skip)
        h.addWidget(self._skip_btn)

        h.addStretch(1)

        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._go_back)
        h.addWidget(self._back_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("PrimaryButton")
        self._next_btn.setMinimumWidth(110)
        self._next_btn.clicked.connect(self._go_next)
        h.addWidget(self._next_btn)
        return bar

    def _update_footer(self) -> None:
        idx = self._stack.currentIndex()
        self._back_btn.setEnabled(idx > 0)
        # Final step uses its own buttons — hide the footer Next to avoid
        # double CTAs racing each other.
        on_final = idx == self._stack.count() - 1
        self._next_btn.setVisible(not on_final)
        self._skip_btn.setVisible(not on_final)

    # ============================================================== polling

    def _poll_controller(self) -> None:
        """Probe pygame for a connected joystick. Cheap enough to call on
        demand; we tear the reader down each time so we don't leak SDL state."""
        reader = ControllerReader()
        info = None
        try:
            info = reader.detect()
        finally:
            reader.close()
        if info is None:
            self._controller_detected = False
            self._controller_status.setText(
                "Plug in your PS5 or Xbox controller and we'll continue."
            )
            self._controller_status.setStyleSheet("color: #f97373;")
        else:
            self._controller_detected = True
            self._controller_status.setText(
                f"{info.name} connected. {info.num_axes} axes, "
                f"{info.num_buttons} buttons."
            )
            self._controller_status.setStyleSheet("color: #2dd4bf;")

    def _poll_midi(self) -> None:
        """Open and immediately discard a virtual MIDI port. On Windows this
        surfaces the missing-loopMIDI case so we can point the user at the
        download link instead of failing silently."""
        # Close any previous probe before opening a new one — rtmidi will
        # happily collide with itself otherwise.
        if self._test_port is not None:
            close_port(self._test_port)
            self._test_port = None
        try:
            opened = open_port()
            self._test_port = opened
            self._midi_status.setText(
                f"Virtual MIDI port live: {opened.name}. Anything listening on "
                "this port now hears your gamepad."
            )
            self._midi_status.setStyleSheet("color: #2dd4bf;")
            self._loopmidi_btn.setVisible(False)
        except MidiPortError as e:
            self._midi_status.setText(str(e))
            self._midi_status.setStyleSheet("color: #f97373;")
            # Only Windows users need loopMIDI; hide the button elsewhere.
            self._loopmidi_btn.setVisible(sys.platform == "win32")

    # ============================================================== nav

    def _go_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx < self._stack.count() - 1:
            self._stack.setCurrentIndex(idx + 1)
            self._steps_completed = max(self._steps_completed, idx + 1)
            self._update_footer()

    def _go_back(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._update_footer()

    def _on_skip(self) -> None:
        send_event("onboarding_skipped", step=self._stack.currentIndex())
        self._cleanup_test_port()
        mark_complete()
        self.reject()

    def _finish_without_start(self) -> None:
        self._emit_complete_event()
        self._cleanup_test_port()
        mark_complete()
        self.onboarding_complete.emit()
        self.accept()

    def _finish_and_start(self) -> None:
        self._emit_complete_event()
        self._cleanup_test_port()
        mark_complete()
        self.onboarding_complete.emit()
        self.start_requested.emit()
        self.accept()

    def _emit_complete_event(self) -> None:
        send_event(
            "onboarding_complete",
            steps_completed=self._steps_completed + 1,
            controller_detected=self._controller_detected,
        )

    def _cleanup_test_port(self) -> None:
        """Release the probe port so the bridge can claim a fresh one when the
        user clicks Start — rtmidi virtual ports collide on the same name."""
        if self._test_port is not None:
            close_port(self._test_port)
            self._test_port = None

    # ============================================================== helpers

    def _page(self, title: str, body: str) -> QWidget:
        """Simple title+body page used for the welcome and calibration steps."""
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 36, 36, 36)
        v.setSpacing(16)
        h = QLabel(title)
        h.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f7fa;")
        h.setWordWrap(True)
        v.addWidget(h)
        b = QLabel(body)
        b.setStyleSheet("color: #c2c6cc; font-size: 13px;")
        b.setWordWrap(True)
        v.addWidget(b)
        v.addStretch(1)
        return page

    def closeEvent(self, event) -> None:  # noqa: D401 — Qt override
        # Treat window-close as skip so we never leak the probe port and never
        # re-prompt on next launch after the user dismissed us.
        self._cleanup_test_port()
        if is_first_launch():
            send_event("onboarding_skipped", step=self._stack.currentIndex())
            mark_complete()
        event.accept()
