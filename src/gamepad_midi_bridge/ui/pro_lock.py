"""Reusable Pro lock overlay. Drop on top of any Pro-gated panel."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class ProLockOverlay(QWidget):
    """Centered upgrade prompt with title, description, and CTA."""

    activate_clicked = Signal()
    upgrade_clicked = Signal()

    def __init__(self, feature_title: str, description: str,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(14, 15, 18, 240);")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setMaximumWidth(440)
        card.setStyleSheet(
            "background-color: #16181d; border: 1px solid #24262d; "
            "border-radius: 12px; padding: 28px;"
        )

        inner = QVBoxLayout(card)
        inner.setSpacing(12)

        badge = QLabel("PRO")
        badge.setObjectName("ProBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(48)
        badge.setStyleSheet(
            "background-color: #2dd4bf; color: #0e0f12; border-radius: 4px; "
            "padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        inner.addWidget(badge)

        title = QLabel(feature_title)
        title.setObjectName("ProLockTitle")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f7fa;")
        title.setWordWrap(True)
        inner.addWidget(title)

        desc = QLabel(description)
        desc.setObjectName("ProLockSub")
        desc.setStyleSheet("color: #8a9099; font-size: 13px;")
        desc.setWordWrap(True)
        inner.addWidget(desc)

        cta_row = QVBoxLayout()
        cta_row.setSpacing(8)

        upgrade = QPushButton("Upgrade to Pro")
        upgrade.setObjectName("PrimaryButton")
        upgrade.clicked.connect(self.upgrade_clicked.emit)
        cta_row.addWidget(upgrade)

        activate = QPushButton("I have a license key")
        activate.clicked.connect(self.activate_clicked.emit)
        cta_row.addWidget(activate)

        inner.addLayout(cta_row)
        outer.addWidget(card)
