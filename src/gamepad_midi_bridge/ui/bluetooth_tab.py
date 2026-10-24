"""Bluetooth tab — lists paired/connected controllers, opens system pair UI.

We deliberately don't pair from inside the app. The user has already taught
their OS to trust their controllers; re-implementing that flow would mean
handling auth + LMP fallback + the long tail of dongle quirks for zero
upside. What we DO give them:

    - A view of what's currently paired and which devices are live right now
    - Battery + signal strength where the OS exposes it
    - One click to the OS's Bluetooth settings for pairing new devices
    - A re-scan button so they can refresh without restarting the bridge
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from .. import bluetooth as bt
from .primitives.flow_layout import FlowLayout


REFRESH_INTERVAL_MS = 6000   # background poll cadence


class _ScanSignals(QObject):
    """Signal carrier for _ScanTask. Lives on the GUI thread, so the
    connection to the tab is automatically queued back onto it."""

    finished = Signal(list)


class _ScanTask(QRunnable):
    """Runs bt.list_devices() off the GUI thread.

    The OS device query is a blocking shell-out on Windows and Linux
    (powershell / bluetoothctl) and takes over a second on a cold
    PowerShell start. Calling it from the GUI thread froze the event loop
    on every poll, which showed up as multi-second MIDI latency.

    QRunnable on the global pool rather than a long-lived QThread: there's
    no thread object to own, so a tab that gets garbage-collected without
    an explicit close can't abort the process on teardown.
    """

    def __init__(self, signals: _ScanSignals) -> None:
        super().__init__()
        self._signals = signals

    def run(self) -> None:  # noqa: D102 — Qt override
        try:
            devices = bt.list_devices()
        except Exception:
            devices = []
        try:
            self._signals.finished.emit(devices)
        except RuntimeError:
            # Tab was destroyed while the scan was in flight. Nothing to do.
            pass


class BluetoothTab(QWidget):
    """Surface OS-paired Bluetooth devices, with a deep-link to system settings."""

    status_message = Signal(str)
    # Re-scan button clicked. MainWindow forwards this to BridgeWorker.redetect()
    # so a newly-paired controller gets attached without a Stop/Start cycle.
    rescan_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._supported = bt.is_supported()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        header = QLabel("Bluetooth controllers")
        header.setObjectName("BluetoothHeader")
        outer.addWidget(header)

        sub = QLabel(
            "Pairing happens once in your OS settings — we'll see the "
            "controller as soon as it connects. Battery + signal show "
            "up here when the OS exposes them.\n\n"
            "Tip: If your controller isn't showing up, try:\n"
            "• Check it's powered on and in pairing mode\n"
            "• Click 'Open system Bluetooth settings' to pair it\n"
            "• Re-scan after pairing to refresh the list"
        )
        sub.setObjectName("BluetoothSubLabel")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        # FlowLayout, not QHBoxLayout: these three buttons sum to 509 px, and
        # in a QHBoxLayout that became this whole page's minimum width — the
        # page then needed a horizontal scrollbar on a narrow window. Wrapped,
        # the floor is the widest single button and every control stays put.
        action_row = FlowLayout(h_space=8, v_space=8)
        self._open_settings = QPushButton("Open system Bluetooth settings")
        self._open_settings.setObjectName("PrimaryButton")
        self._open_settings.clicked.connect(self._on_open_settings)
        self._refresh = QPushButton("Re-scan")
        self._refresh.clicked.connect(self.refresh)
        # The OS device list refresh is local UI; ALSO ask the bridge to
        # re-detect its joystick handle so newly-paired controllers get
        # picked up without a Stop/Start cycle.
        self._refresh.clicked.connect(self.rescan_requested.emit)
        self._docs_link = QPushButton("📖 Connection guide")
        self._docs_link.setObjectName("BluetoothDocsLink")
        self._docs_link.clicked.connect(self._on_docs_link)
        action_row.addWidget(self._open_settings)
        action_row.addWidget(self._refresh)
        action_row.addWidget(self._docs_link)
        # No trailing stretch — FlowLayout already left-aligns and wraps; a
        # stretch item would just be another thing to wrap.
        outer.addLayout(action_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self._scroll, 1)

        self._scan_in_flight = False
        self._scan_signals = _ScanSignals(self)
        self._scan_signals.finished.connect(self._on_scan_finished)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(REFRESH_INTERVAL_MS)
        self._poll_timer.timeout.connect(self.refresh)

        # Paint the empty state now; the first real scan runs when the tab is
        # actually shown. Polling the OS for Bluetooth devices while the user
        # is on another tab costs them a shell-out every 6 seconds and buys
        # nothing — nobody can see the result.
        self._render([])

    # ------------------------------------------------------------------ public

    def refresh(self) -> None:
        """Kick off a device scan on the worker thread (no-op if one is running)."""
        if not self._supported:
            self._render([])
            return
        if self._scan_in_flight:
            return
        self._scan_in_flight = True
        QThreadPool.globalInstance().start(_ScanTask(self._scan_signals))

    # ------------------------------------------------------------- lifecycle

    def showEvent(self, event) -> None:  # noqa: N802 — Qt override
        super().showEvent(event)
        self.refresh()
        self._poll_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._poll_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._poll_timer.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------------ slots

    def _on_scan_finished(self, devices: List[bt.BluetoothDevice]) -> None:
        self._scan_in_flight = False
        self._render(devices)
        if self._supported:
            self.status_message.emit(
                f"Bluetooth: {sum(1 for d in devices if d.connected)} connected, "
                f"{len(devices)} paired"
            )

    # ------------------------------------------------------------------ helpers

    def _render(self, devices: List[bt.BluetoothDevice]) -> None:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        if not self._supported:
            self._empty(v, "Bluetooth listing isn't supported on this platform.\n"
                          "Install `pyobjc-framework-IOBluetooth` on macOS to enable.")
        elif not devices:
            self._empty(v, "No paired Bluetooth devices found.\n"
                          "Pair your controller via system settings to see it here.")
        else:
            # Controllers first — they're what the user came here for.
            devices.sort(key=lambda d: (not d.is_controller, not d.connected, d.name.lower()))
            for d in devices:
                v.addWidget(self._device_card(d))

        v.addStretch(1)
        self._scroll.setWidget(container)

    def _empty(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("BluetoothEmptyState")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

    def _device_card(self, d: bt.BluetoothDevice) -> QFrame:
        card = QFrame()
        card.setObjectName("BluetoothPairedDeviceCard")
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel(d.name + ("  ·  controller" if d.is_controller else ""))
        title.setObjectName("BluetoothPairedDeviceTitle")
        left.addWidget(title)

        meta_bits: List[str] = []
        if d.address:
            meta_bits.append(d.address)
        if d.rssi is not None:
            meta_bits.append(f"RSSI {d.rssi} dBm")
        if d.battery_percent is not None:
            meta_bits.append(f"Battery {d.battery_percent}%")
        if meta_bits:
            meta = QLabel(" · ".join(meta_bits))
            meta.setObjectName("BluetoothPairedDeviceMeta")
            left.addWidget(meta)
        h.addLayout(left, 1)

        status = QLabel("Connected" if d.connected else "Paired")
        status.setObjectName("BluetoothPairedDeviceStatus")
        status.setProperty("state", "connected" if d.connected else "paired")
        status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(status)

        return card

    # ------------------------------------------------------------------ actions

    def _on_open_settings(self) -> None:
        if not bt.open_system_settings():
            QMessageBox.warning(
                self, "Couldn't open Bluetooth settings",
                "We couldn't launch your system's Bluetooth pane automatically. "
                "Open it manually and pair the controller — it'll show up here "
                "on the next refresh.",
            )

    def _on_docs_link(self) -> None:
        import webbrowser
        webbrowser.open("https://ps5-midi-bridge.local/docs/installation/connect-bluetooth")
