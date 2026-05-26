"""Connectors tab — auto-install MIDI maps into host applications.

One row per (connector, detected host installation). Empty state shown when
nothing is detected so users know the connector exists but couldn't find a
matching app.
"""
from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from .. import telemetry
from ..connectors import Connector, HostInstallation, all_connectors


class ConnectorsTab(QWidget):
    """List + install/uninstall every detected host on this machine."""

    status_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._connectors = all_connectors()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        header = QLabel("Auto-map your gamepad into the apps you use.")
        header.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f7fa;")
        outer.addWidget(header)

        sub = QLabel(
            "Each connector writes a ready-made MIDI map into the host's "
            "config folder. No restart required for Resolume; Ableton needs "
            "a Control Surface re-pick."
        )
        sub.setStyleSheet("color: #8a9099;")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        # Refresh button (cheap — just calls each connector's detect())
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        refresh = QPushButton("Re-scan for hosts")
        refresh.clicked.connect(self.refresh)
        action_row.addWidget(refresh)
        outer.addLayout(action_row)

        # Scrollable list of detected installations
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self._scroll, 1)

        self._rebuild_list()

    # ---------------------------------------------------------------- public

    def refresh(self) -> None:
        self._rebuild_list()
        self.status_message.emit("Re-scanned host applications.")

    # ---------------------------------------------------------------- helpers

    def _rebuild_list(self) -> None:
        host_pairs = self._enumerate_hosts()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if not host_pairs:
            empty = QLabel(
                "No supported host applications detected.\n\n"
                "Currently supported: Resolume Arena 7-9.\n"
                "Open the app you want to connect once so it creates its "
                "Documents folder, then come back here and click Re-scan."
            )
            empty.setStyleSheet("color: #8a9099; padding: 40px;")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            for connector, host in host_pairs:
                layout.addWidget(self._host_row(connector, host))

        layout.addStretch(1)
        self._scroll.setWidget(container)

    def _enumerate_hosts(self) -> List[Tuple[Connector, HostInstallation]]:
        pairs: List[Tuple[Connector, HostInstallation]] = []
        for c in self._connectors:
            try:
                for h in c.detect():
                    pairs.append((c, h))
            except Exception:
                # Bad connector shouldn't break the whole tab.
                pass
        return pairs

    def _host_row(self, connector: Connector, host: HostInstallation) -> QFrame:
        installed = False
        try:
            installed = connector.is_installed(host)
        except Exception:
            pass

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #16181d; border: 1px solid #24262d; "
            "border-radius: 8px; padding: 14px; }"
        )
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(14)

        # Left column — name + description
        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel(f"{host.name}")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f7fa;")
        sub = QLabel(connector.description)
        sub.setStyleSheet("color: #8a9099; font-size: 12px;")
        sub.setWordWrap(True)
        path = QLabel(str(host.config_dir))
        path.setStyleSheet("color: #5a606b; font-size: 11px;")
        path.setWordWrap(True)
        left.addWidget(title)
        left.addWidget(sub)
        left.addWidget(path)
        h.addLayout(left, 1)

        # Right column — status + actions
        right = QVBoxLayout()
        right.setSpacing(6)
        status = QLabel("Installed ✓" if installed else "Not installed")
        status.setStyleSheet(
            "color: #2dd4bf; font-weight: 600;" if installed
            else "color: #8a9099;"
        )
        status.setAlignment(Qt.AlignRight)
        right.addWidget(status)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        install_btn = QPushButton("Reinstall" if installed else "Install")
        install_btn.setObjectName("PrimaryButton")
        install_btn.clicked.connect(lambda: self._on_install(connector, host))
        button_row.addWidget(install_btn)
        if installed:
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda: self._on_uninstall(connector, host))
            button_row.addWidget(remove_btn)
        right.addLayout(button_row)
        h.addLayout(right)

        return card

    # ---------------------------------------------------------------- actions

    def _on_install(self, connector: Connector, host: HostInstallation) -> None:
        result = connector.install(host)
        if result.success:
            telemetry.send_event("connector_installed",
                                 connector=connector.slug,
                                 host_version=host.version)
            QMessageBox.information(
                self, f"{connector.display_name} installed",
                f"{result.message}\n\n{connector.post_install_steps(host)}",
            )
        else:
            QMessageBox.warning(self, "Install failed", result.message)
        self._rebuild_list()

    def _on_uninstall(self, connector: Connector, host: HostInstallation) -> None:
        result = connector.uninstall(host)
        if not result.success:
            QMessageBox.warning(self, "Remove failed", result.message)
        self._rebuild_list()
