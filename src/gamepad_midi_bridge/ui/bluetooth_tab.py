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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from .. import bluetooth as bt


REFRESH_INTERVAL_MS = 6000   # background poll cadence


class BluetoothTab(QWidget):
    """Surface OS-paired Bluetooth devices, with a deep-link to system settings."""

    status_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._supported = bt.is_supported()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        header = QLabel("Bluetooth controllers")
        header.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f7fa;")
        outer.addWidget(header)

        sub = QLabel(
            "Pairing happens once in your OS settings — we'll see the "
            "controller as soon as it connects. Battery + signal show "
            "up here when the OS exposes them."
        )
        sub.setStyleSheet("color: #8a9099;")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        action_row = QHBoxLayout()
        self._open_settings = QPushButton("Open system Bluetooth settings")
        self._open_settings.setObjectName("PrimaryButton")
        self._open_settings.clicked.connect(self._on_open_settings)
        self._refresh = QPushButton("Re-scan")
        self._refresh.clicked.connect(self.refresh)
        action_row.addWidget(self._open_settings)
        action_row.addWidget(self._refresh)
        action_row.addStretch(1)
        outer.addLayout(action_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self._scroll, 1)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(REFRESH_INTERVAL_MS)
        self._poll_timer.timeout.connect(self.refresh)

        # Initial paint + start polling. The 250 ms delay gives the GUI thread
        # a moment to lay out the rest of the window before our first OS call.
        QTimer.singleShot(250, self.refresh)
        self._poll_timer.start()

    # ------------------------------------------------------------------ public

    def refresh(self) -> None:
        devices = bt.list_devices() if self._supported else []
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
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #8a9099; padding: 40px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

    def _device_card(self, d: bt.BluetoothDevice) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #16181d; border: 1px solid #24262d; "
            "border-radius: 8px; }"
        )
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel(d.name + ("  ·  controller" if d.is_controller else ""))
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f7fa;")
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
            meta.setStyleSheet("color: #8a9099; font-size: 12px;")
            left.addWidget(meta)
        h.addLayout(left, 1)

        status = QLabel("Connected" if d.connected else "Paired")
        status.setStyleSheet(
            "color: #2dd4bf; font-weight: 600;" if d.connected
            else "color: #8a9099;"
        )
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
