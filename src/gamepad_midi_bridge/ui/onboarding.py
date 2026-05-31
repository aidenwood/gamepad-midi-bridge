"""First-launch onboarding wizard.

Ten-step modal: welcome, controller detect, MIDI probe, connector picker,
calibration primer, trigger modes, adaptive haptics, polar stick mode,
multi-zone touchpad, done. Why isolated module: one-shot UI that PyInstaller
can drop from hot paths, keeps main_window focused on steady-state UX.
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
from ..midi_backend import MidiPortError, close_port, open_port
from ..paths import config_path
from ..telemetry import send_event


LOOPMIDI_URL = "https://www.tobias-erichsen.de/software/loopmidi.html"
ONBOARDING_FLAG = "onboarding_complete"


# ============================================================== persistence

def _read_config() -> dict:
    # Best-effort read — empty dict on any failure so a corrupt config can't
    # block first-launch flow.
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def is_first_launch() -> bool:
    """True until mark_complete() writes the flag. Missing key counts as first."""
    return not bool(_read_config().get(ONBOARDING_FLAG, False))


def mark_complete() -> None:
    """Persist the flag so the wizard never reappears on this machine."""
    cfg = _read_config()
    cfg[ONBOARDING_FLAG] = True
    config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _set_state(widget: QWidget, state: str) -> None:
    """Set the ``state`` dynamic property and re-polish so the QSS rule
    (e.g. ``QLabel#OnboardingStatus[state="ok"]``) re-evaluates."""
    widget.setProperty("state", state)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# ============================================================== wizard

class OnboardingWizard(QDialog):
    """Modal ten-step wizard. Emits `onboarding_complete` when done and
    `start_requested` if the user wants the bridge to fire immediately."""

    onboarding_complete = Signal()
    start_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        worker=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setModal(True)
        self.setFixedSize(640, 480)

        self._controller_detected = False
        self._steps_completed = 0
        self._installed_slugs: List[str] = []
        # Probe port lives until cleanup so the bridge can claim a fresh one.
        self._test_port = None
        # Optional reference to the running bridge worker — used by "Try it
        # now" callbacks in the v2/v3/v4/v5 feature steps.
        self._worker = worker

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)
        for builder in (
            self._build_welcome, self._build_controller, self._build_midi,
            self._build_connectors, self._build_calibration,
            self._build_trigger_modes, self._build_adaptive_haptics,
            self._build_polar_stick, self._build_multizone_touchpad,
            self._build_done,
        ):
            self._stack.addWidget(builder())

        root.addWidget(self._build_footer())
        self._update_footer()
        send_event("onboarding_started")

    # ============================================================== steps

    def _build_welcome(self) -> QWidget:
        return self._page(
            "Turn your gamepad into a MIDI controller.",
            "Three minutes to set up. Skip if you've done this dance before.\n\n"
            "We'll find your controller, open a virtual MIDI port, wire up the "
            "hosts you use, and calibrate your sticks. Nothing leaves your machine.",
        )

    def _build_controller(self) -> QWidget:
        page, v = self._page_shell("Looking for your controller…")
        self._controller_status = QLabel("Scanning…")
        self._controller_status.setObjectName("OnboardingStatus")
        self._controller_status.setWordWrap(True)
        v.addWidget(self._controller_status)

        hint = QLabel(
            "Works with PS5 DualSense, Xbox, Switch Pro, and most generic "
            "gamepads. USB or Bluetooth — your call."
        )
        hint.setObjectName("OnboardingHint")
        hint.setWordWrap(True)
        v.addWidget(hint)

        retry = QPushButton("Scan again")
        retry.clicked.connect(self._poll_controller)
        v.addWidget(retry, alignment=Qt.AlignLeft)
        v.addStretch(1)
        # Defer first poll so the page paints before pygame churns.
        QTimer.singleShot(150, self._poll_controller)
        return page

    def _build_midi(self) -> QWidget:
        page, v = self._page_shell("Opening a virtual MIDI port…")
        self._midi_status = QLabel("Probing the MIDI backend…")
        self._midi_status.setObjectName("OnboardingStatus")
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
        page, v = self._page_shell("Pick the hosts you'll perform with.")
        sub = QLabel(
            "We'll write a small mapping file into each host's config folder. "
            "You can manage these later from the Connectors tab."
        )
        sub.setObjectName("OnboardingHint")
        sub.setWordWrap(True)
        v.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        rows = QVBoxLayout(inner)
        rows.setContentsMargins(0, 8, 0, 0)
        rows.setSpacing(8)
        for connector in all_connectors():
            rows.addWidget(self._build_connector_row(connector))
        rows.addStretch(1)
        scroll.setWidget(inner)
        v.addWidget(scroll, 1)
        return page

    def _build_connector_row(self, connector) -> QWidget:
        row = QFrame()
        row.setObjectName("OnboardingConnectorRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(12)

        check = QCheckBox(connector.display_name)
        check.setObjectName("OnboardingConnectorCheck")
        h.addWidget(check)

        desc = QLabel(connector.description or "")
        desc.setObjectName("OnboardingConnectorDesc")
        desc.setWordWrap(True)
        h.addWidget(desc, 1)

        install_btn = QPushButton("Install")
        install_btn.setObjectName("PrimaryButton")
        status = QLabel("")
        status.setObjectName("OnboardingConnectorStatus")
        h.addWidget(status)
        h.addWidget(install_btn)

        # Disable install when host isn't detected so we don't promise a no-op.
        try:
            hosts = connector.detect()
        except Exception:
            hosts = []
        if not hosts:
            install_btn.setEnabled(False)
            status.setText("not detected")
            _set_state(status, "missing")

        def do_install() -> None:
            check.setChecked(True)
            ok = 0
            for host in hosts:
                try:
                    res = connector.install(host)
                except Exception as e:
                    res = type("R", (), {"success": False, "message": str(e)})()
                if getattr(res, "success", False):
                    ok += 1
            if ok:
                status.setText("installed")
                install_btn.setEnabled(False)
                self._installed_slugs.append(connector.slug)
                send_event("onboarding_connector_installed", connector=connector.slug)
            else:
                status.setText("failed — see Connectors tab")
                _set_state(status, "error")

        install_btn.clicked.connect(do_install)
        return row

    def _build_calibration(self) -> QWidget:
        return self._page(
            "Stick calibration runs at Start.",
            "When you hit Start Bridging, keep your hands off the controller for "
            "two seconds. We sample resting position to compensate for drift "
            "automatically — most modern sticks need it.\n\n"
            "If a stick is too far gone for software compensation, we'll flag it.",
        )

    def _build_trigger_modes(self) -> QWidget:
        page, v = self._page_shell("Try the new trigger modes")
        intro = QLabel(
            "L2 and R2 now have four output modes — pick per-trigger in the "
            "Mapping tab:"
        )
        intro.setObjectName("OnboardingBody")
        intro.setWordWrap(True)
        v.addWidget(intro)

        modes = [
            ("linear",   "0 → 127 as you depress (default). Direct, musical."),
            ("ceiling",  "Jumps to 127 at a configurable threshold. Great for "
                         "on/off switches that live on a trigger."),
            ("inverted", "127 → 0 as you depress. Feed reverse-swell "
                         "effects or upward filter sweeps."),
            ("latch",    "Each full press toggles between 0 and 127. Use it to "
                         "hold a sustain pedal note hands-free."),
        ]
        for slug, desc in modes:
            row = QFrame()
            row.setObjectName("OnboardingTriggerModeRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 8, 12, 8)
            h.setSpacing(10)
            name_lbl = QLabel(slug)
            name_lbl.setObjectName("OnboardingTriggerModeName")
            name_lbl.setFixedWidth(64)
            h.addWidget(name_lbl)
            desc_lbl = QLabel(desc)
            desc_lbl.setObjectName("OnboardingTriggerModeDesc")
            desc_lbl.setWordWrap(True)
            h.addWidget(desc_lbl, 1)
            v.addWidget(row)

        v.addStretch(1)
        btn_row = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.setObjectName("OnboardingSkipLink")
        skip.setFlat(True)
        skip.clicked.connect(self._go_next)
        btn_row.addWidget(skip)
        btn_row.addStretch(1)
        try_btn = QPushButton("Try it now — open L2 in Mapping editor")
        try_btn.setObjectName("PrimaryButton")
        try_btn.clicked.connect(self._try_trigger_modes)
        btn_row.addWidget(try_btn)
        v.addLayout(btn_row)
        return page

    def _build_adaptive_haptics(self) -> QWidget:
        page, v = self._page_shell("Adaptive triggers feel music")
        body = QLabel(
            "New in v1.1 — the bridge is now bidirectional. Incoming MIDI notes "
            "can drive adaptive-trigger resistance on a PS5 DualSense in real time. "
            "A kick on channel 10 thumps your L2; a snare hits your R2.\n\n"
            "Enable it under Settings → Haptics → MIDI → Trigger. Works over USB "
            "and Bluetooth. Your DAW plays the notes; your hands feel them."
        )
        body.setObjectName("OnboardingBody")
        body.setWordWrap(True)
        v.addWidget(body)

        tip = QLabel("Requires a PS5 DualSense controller. Xbox and generic pads receive no haptic signal.")
        tip.setObjectName("OnboardingHint")
        tip.setWordWrap(True)
        v.addWidget(tip)

        v.addStretch(1)
        btn_row = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.setObjectName("OnboardingSkipLink")
        skip.setFlat(True)
        skip.clicked.connect(self._go_next)
        btn_row.addWidget(skip)
        btn_row.addStretch(1)
        try_btn = QPushButton("Try it now — open Haptics settings")
        try_btn.setObjectName("PrimaryButton")
        try_btn.clicked.connect(self._try_adaptive_haptics)
        btn_row.addWidget(try_btn)
        v.addLayout(btn_row)
        return page

    def _build_polar_stick(self) -> QWidget:
        page, v = self._page_shell("Polar stick mode")
        body = QLabel(
            "Instead of cartesian X/Y axes, you can read either stick in polar "
            "coordinates — the angle drives one CC and the magnitude drives another. "
            "Sweep a filter by rotating the stick; control wet/dry by how far you "
            "push it."
        )
        body.setObjectName("OnboardingBody")
        body.setWordWrap(True)
        v.addWidget(body)

        # Simple ASCII diagram as a styled label
        diagram = QLabel(
            "  angle  →  CC 1  (0 – 127, full rotation)\n"
            "  magnitude  →  CC 2  (0 = centre, 127 = full push)"
        )
        diagram.setObjectName("OnboardingPolarDiagram")
        v.addWidget(diagram)

        hint = QLabel(
            "Enable per-stick in Mapping → Axes → Left Stick / Right Stick → "
            "Mode → Polar."
        )
        hint.setObjectName("OnboardingHint")
        hint.setWordWrap(True)
        v.addWidget(hint)

        v.addStretch(1)
        btn_row = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.setObjectName("OnboardingSkipLink")
        skip.setFlat(True)
        skip.clicked.connect(self._go_next)
        btn_row.addWidget(skip)
        btn_row.addStretch(1)
        try_btn = QPushButton("Try it now — open Axes editor")
        try_btn.setObjectName("PrimaryButton")
        try_btn.clicked.connect(self._try_polar_stick)
        btn_row.addWidget(try_btn)
        v.addLayout(btn_row)
        return page

    def _build_multizone_touchpad(self) -> QWidget:
        page, v = self._page_shell("Multi-zone touchpad")
        body = QLabel(
            "The DualSense touchpad can now be split into a drum-pad grid. "
            "Touch top-left, top-right, bottom-left, or bottom-right — each zone "
            "fires its own MIDI note."
        )
        body.setObjectName("OnboardingBody")
        body.setWordWrap(True)
        v.addWidget(body)

        tip = QLabel(
            "Tip — load the Drum Pad template and map the zones to ride + "
            "open hi-hat + crash for a hands-free cymbal extension."
        )
        tip.setObjectName("OnboardingHint")
        tip.setWordWrap(True)
        v.addWidget(tip)

        v.addStretch(1)
        btn_row = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.setObjectName("OnboardingSkipLink")
        skip.setFlat(True)
        skip.clicked.connect(self._go_next)
        btn_row.addWidget(skip)
        btn_row.addStretch(1)
        try_btn = QPushButton("Try it now — load Drum Pad template")
        try_btn.setObjectName("PrimaryButton")
        try_btn.clicked.connect(self._try_drum_pad_template)
        btn_row.addWidget(try_btn)
        v.addLayout(btn_row)
        return page

    def _build_done(self) -> QWidget:
        page, v = self._page_shell("You're ready.", big=True)
        body = QLabel(
            "Hit Start Bridging when you want to perform. Tweak mappings, "
            "browse presets, and add connectors from the main window any time."
        )
        body.setObjectName("OnboardingBody")
        body.setWordWrap(True)
        v.addWidget(body)
        v.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self._finish_without_start)
        row.addWidget(close)
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
        bar.setObjectName("OnboardingFooter")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(10)

        self._skip_btn = QPushButton("Skip setup")
        self._skip_btn.setObjectName("OnboardingSkipLink")
        self._skip_btn.setFlat(True)
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
        # Final step has its own CTAs — hide footer Next to avoid double primaries.
        on_final = idx == self._stack.count() - 1
        self._next_btn.setVisible(not on_final)
        self._skip_btn.setVisible(not on_final)

    # ============================================================== polling

    def _poll_controller(self) -> None:
        # Tear reader down after each probe so SDL state doesn't leak.
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
            _set_state(self._controller_status, "error")
        else:
            self._controller_detected = True
            self._controller_status.setText(
                f"{info.name} connected. {info.num_axes} axes, "
                f"{info.num_buttons} buttons."
            )
            _set_state(self._controller_status, "ok")

    def _poll_midi(self) -> None:
        # Probe-then-release. On Windows surfaces missing loopMIDI so we can
        # point at the download instead of failing silently.
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
            _set_state(self._midi_status, "ok")
            self._loopmidi_btn.setVisible(False)
        except MidiPortError as e:
            self._midi_status.setText(str(e))
            _set_state(self._midi_status, "error")
            self._loopmidi_btn.setVisible(sys.platform == "win32")

    # ============================================================== nav + finish

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

    # ============================================================= feature CTAs

    def _try_trigger_modes(self) -> None:
        """Open the mapping editor pre-selected on the L2 trigger axis (index 4)."""
        send_event("onboarding_try_trigger_modes")
        self._go_next()
        if self._worker is not None:
            try:
                self._worker.open_axis_editor(axis_index=4)
            except Exception:
                pass  # Worker not in a state to handle it — no crash

    def _try_adaptive_haptics(self) -> None:
        """Open the Haptics settings panel."""
        send_event("onboarding_try_adaptive_haptics")
        self._go_next()
        if self._worker is not None:
            try:
                self._worker.open_settings(tab="haptics")
            except Exception:
                pass

    def _try_polar_stick(self) -> None:
        """Open the Axes editor for the left stick."""
        send_event("onboarding_try_polar_stick")
        self._go_next()
        if self._worker is not None:
            try:
                self._worker.open_axis_editor(axis_index=0)
            except Exception:
                pass

    def _try_drum_pad_template(self) -> None:
        """Load the Drum Pad template via the worker."""
        from ..templates import TEMPLATES_BY_SLUG
        send_event("onboarding_try_drum_pad_template")
        self._go_next()
        if self._worker is not None:
            try:
                mapping = TEMPLATES_BY_SLUG["drum-pad"].build_mapping()
                self._worker.load_mapping(mapping)
            except Exception:
                pass

    def _emit_complete_event(self) -> None:
        send_event(
            "onboarding_complete",
            steps_completed=self._steps_completed + 1,
            controller_detected=self._controller_detected,
        )

    def _cleanup_test_port(self) -> None:
        # Release probe port — rtmidi virtual ports collide on the same name,
        # so the bridge needs a clean slate when the user clicks Start.
        if self._test_port is not None:
            close_port(self._test_port)
            self._test_port = None

    # ============================================================== helpers

    def _page(self, title: str, body: str) -> QWidget:
        page, v = self._page_shell(title, big=True)
        b = QLabel(body)
        b.setObjectName("OnboardingBody")
        b.setWordWrap(True)
        v.addWidget(b)
        v.addStretch(1)
        return page

    def _page_shell(self, title: str, big: bool = False) -> tuple[QWidget, QVBoxLayout]:
        # Shared title+layout scaffold so per-step builders stay short.
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 36, 36, 36)
        v.setSpacing(14)
        h = QLabel(title)
        h.setObjectName("OnboardingHeadingBig" if big else "OnboardingHeading")
        h.setWordWrap(True)
        v.addWidget(h)
        return page, v

    def closeEvent(self, event) -> None:  # noqa: D401 — Qt override
        # Window-close == skip. Marks complete so we never re-prompt on next launch.
        self._cleanup_test_port()
        if is_first_launch():
            send_event("onboarding_skipped", step=self._stack.currentIndex())
            mark_complete()
        event.accept()
