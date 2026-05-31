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
        # All visual rules in styles.qss → "PRO LOCK OVERLAY" section.
        self.setObjectName("ProLockOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("ProLockCard")
        card.setMaximumWidth(440)

        inner = QVBoxLayout(card)
        inner.setSpacing(12)

        badge = QLabel("PRO")
        badge.setObjectName("ProBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(48)
        inner.addWidget(badge)

        title = QLabel(feature_title)
        title.setObjectName("ProLockTitle")
        title.setWordWrap(True)
        inner.addWidget(title)

        desc = QLabel(description)
        desc.setObjectName("ProLockSub")
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
