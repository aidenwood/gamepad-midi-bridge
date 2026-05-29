"""
About tab — logo, version, tagline, links, acknowledgements, build info, easter egg.
"""
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
import webbrowser

from .. import APP_NAME, __version__


def get_build_info() -> dict:
    """Return build metadata: git hash, build date, platform."""
    info = {
        "version": __version__,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "build_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "git_hash": None,
    }

    try:
        git_dir = Path(__file__).parent.parent.parent.parent / ".git"
        if git_dir.exists():
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=git_dir.parent,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                info["git_hash"] = result.stdout.strip()
    except Exception:
        pass

    return info


class AboutTab(QWidget):
    """Polished About tab with logo, links, dependencies, build info, and easter egg.

    Can optionally be configured with Pro/license callbacks for a full-featured tab.
    """

    def __init__(
        self,
        tier_label_widget: Optional[QLabel] = None,
        on_upgrade: Optional[callable] = None,
        on_enter_license: Optional[callable] = None,
        on_export_pack: Optional[callable] = None,
        on_import_pack: Optional[callable] = None,
        refresh_tier: Optional[callable] = None,
    ):
        super().__init__()
        self.logo_clicks = 0
        self.logo_click_timer: Optional[QTimer] = None
        self.easter_egg_window: Optional[QWidget] = None

        # Optional Pro/config callbacks
        self.tier_label_widget = tier_label_widget
        self.on_upgrade = on_upgrade
        self.on_enter_license = on_enter_license
        self.on_export_pack = on_export_pack
        self.on_import_pack = on_import_pack
        self.refresh_tier = refresh_tier

        self._init_ui()

    def _init_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 28, 28, 28)
        v.setSpacing(16)

        # ======== Logo (centred) ========
        logo_container = QHBoxLayout()
        logo_label = QLabel()
        icon_path = Path(__file__).parent.parent / "resources" / "icon.png"
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            # Scale to 120x120 at 2x DPI (240x240 native)
            scaled = pixmap.scaledToWidth(240, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled)
        logo_label.setCursor(Qt.PointingHandCursor)
        logo_label.mousePressEvent = lambda _: self._on_logo_click()
        logo_container.addStretch(1)
        logo_container.addWidget(logo_label)
        logo_container.addStretch(1)
        v.addLayout(logo_container)

        # ======== Title + tagline (centred) ========
        title = QLabel(APP_NAME)
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #f5f7fa;")
        v.addWidget(title)

        tagline = QLabel("Turn any gamepad into a MIDI controller.")
        tagline.setStyleSheet("color: #8a9099; font-size: 14px;")
        tagline.setAlignment(Qt.AlignCenter)
        v.addWidget(tagline)

        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: #666; font-size: 12px;")
        version_label.setAlignment(Qt.AlignCenter)
        v.addWidget(version_label)

        v.addSpacing(8)

        # ======== Created by ========
        created_by = QLabel("Created by Aidxn Design — Brisbane, Australia")
        created_by.setStyleSheet("color: #8a9099; font-size: 12px;")
        created_by.setAlignment(Qt.AlignCenter)
        v.addWidget(created_by)

        v.addSpacing(20)

        # ======== Links row ========
        links_layout = QHBoxLayout()
        links_layout.addStretch(1)

        def link_button(text: str, url: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setFlat(True)
            btn.setStyleSheet("color: #42a5f5; text-decoration: underline;")
            btn.clicked.connect(lambda: webbrowser.open(url))
            return btn

        links_layout.addWidget(link_button("Website", "https://store.aidxn.com"))
        links_layout.addSpacing(8)
        links_layout.addWidget(link_button("GitHub", "https://github.com/aidenwood/PS5-MIDI-Bridge"))
        links_layout.addSpacing(8)
        links_layout.addWidget(link_button("Twitter/X", "https://twitter.com/aidxn"))
        links_layout.addSpacing(8)
        links_layout.addWidget(link_button("Email", "mailto:support@aidxn.com"))

        links_layout.addStretch(1)
        v.addLayout(links_layout)

        v.addSpacing(20)

        # ======== Acknowledgements (collapsible via toggle) ========
        ack_header = QPushButton("▶ Open source acknowledgements")
        ack_header.setFlat(True)
        ack_header.setStyleSheet("color: #f5f7fa; font-weight: 700; text-align: left;")
        v.addWidget(ack_header)

        ack_container = QWidget()
        ack_layout = QVBoxLayout(ack_container)
        ack_layout.setContentsMargins(16, 8, 0, 0)

        deps = [
            ("Three.js", "3D viewer used in the online marketplace", "https://threejs.org"),
            ("PySide6", "Qt Python bindings for the desktop UI", "https://www.qt.io/qt-for-python"),
            ("pygame", "Gamepad polling and input handling", "https://www.pygame.org"),
            ("python-rtmidi", "MIDI output to host sequencers", "https://python-rtmidi.readthedocs.io"),
            ("Pydantic", "Configuration validation and serialization", "https://docs.pydantic.dev"),
            ("psutil", "System monitoring for performance metrics", "https://psutil.readthedocs.io"),
        ]

        for name, desc, url in deps:
            dep_layout = QHBoxLayout()
            dep_name = QPushButton(name)
            dep_name.setFlat(True)
            dep_name.setStyleSheet("color: #42a5f5; text-decoration: underline; text-align: left;")
            dep_name.clicked.connect(lambda checked=False, u=url: webbrowser.open(u))
            dep_layout.addWidget(dep_name)
            dep_desc = QLabel(desc)
            dep_desc.setStyleSheet("color: #8a9099; font-size: 11px;")
            dep_layout.addWidget(dep_desc)
            dep_layout.addStretch(1)
            ack_layout.addLayout(dep_layout)

        v.addWidget(ack_container)

        # Toggle visibility
        ack_container.setVisible(False)
        def toggle_ack():
            ack_container.setVisible(not ack_container.isVisible())
            ack_header.setText(("▼ " if ack_container.isVisible() else "▶ ") + "Open source acknowledgements")
        ack_header.clicked.connect(toggle_ack)

        v.addSpacing(20)

        # ======== Pro / License section (optional) ========
        if self.on_upgrade or self.on_enter_license:
            if self.tier_label_widget:
                v.addWidget(self.tier_label_widget)

            row = QHBoxLayout()
            if self.on_upgrade:
                upgrade = QPushButton("Upgrade to Pro")
                upgrade.setObjectName("PrimaryButton")
                upgrade.clicked.connect(self.on_upgrade)
                row.addWidget(upgrade)
            if self.on_enter_license:
                activate = QPushButton("Enter license key")
                activate.clicked.connect(self.on_enter_license)
                row.addWidget(activate)
            row.addStretch(1)
            v.addLayout(row)

            recovery_row = QHBoxLayout()
            recover = QPushButton("Lost your license key?")
            recover.clicked.connect(lambda: webbrowser.open("https://store.aidxn.com/recover"))
            recover.setFlat(True)
            recover.setStyleSheet("color: #8a9099; text-align: left;")
            recovery_row.addWidget(recover)

            changelog = QPushButton("Release notes")
            changelog.clicked.connect(lambda: webbrowser.open("https://store.aidxn.com/changelog"))
            changelog.setFlat(True)
            changelog.setStyleSheet("color: #8a9099; text-align: left;")
            recovery_row.addWidget(changelog)
            recovery_row.addStretch(1)
            v.addLayout(recovery_row)

            v.addSpacing(16)

        # ======== Config pack section (optional) ========
        if self.on_export_pack or self.on_import_pack:
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
            if self.on_export_pack:
                export_btn = QPushButton("Export config…")
                export_btn.clicked.connect(self.on_export_pack)
                portable_row.addWidget(export_btn)
            if self.on_import_pack:
                import_btn = QPushButton("Import config…")
                import_btn.clicked.connect(self.on_import_pack)
                portable_row.addWidget(import_btn)
            portable_row.addStretch(1)
            v.addLayout(portable_row)

            v.addSpacing(16)

        # ======== Build info ========
        build_info = get_build_info()
        build_section = QLabel("BUILD INFO")
        build_section.setStyleSheet("color: #8a9099; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        v.addWidget(build_section)

        build_items = [
            ("Platform", build_info["platform"]),
            ("Python", build_info["python"]),
            ("Build Date", build_info["build_date"]),
        ]
        if build_info["git_hash"]:
            build_items.append(("Git Hash", build_info["git_hash"]))

        for key, val in build_items:
            row = QHBoxLayout()
            key_label = QLabel(f"{key}:")
            key_label.setStyleSheet("color: #8a9099; font-size: 11px; font-weight: 700; width: 80px;")
            val_label = QLabel(val)
            val_label.setStyleSheet("color: #b8bcc4; font-size: 11px; font-family: monospace;")
            row.addWidget(key_label)
            row.addWidget(val_label)
            row.addStretch(1)
            v.addLayout(row)

        v.addStretch(1)

    def _on_logo_click(self) -> None:
        """Easter egg: click logo 5 times to open a console window."""
        self.logo_clicks += 1

        # Reset counter if user waits > 2 seconds between clicks
        if self.logo_click_timer is not None:
            self.logo_click_timer.stop()
        self.logo_click_timer = QTimer()
        self.logo_click_timer.setSingleShot(True)
        self.logo_click_timer.timeout.connect(self._reset_logo_clicks)
        self.logo_click_timer.start(2000)

        if self.logo_clicks >= 5:
            self._open_easter_egg()
            self.logo_clicks = 0

    def _reset_logo_clicks(self) -> None:
        """Reset click counter."""
        self.logo_clicks = 0

    def _open_easter_egg(self) -> None:
        """Show a fun console-style easter egg window."""
        if self.easter_egg_window is not None:
            self.easter_egg_window.raise_()
            self.easter_egg_window.activateWindow()
            return

        egg = QWidget()
        egg.setWindowTitle("🎮 SECRET CONSOLE")
        egg.setGeometry(100, 100, 600, 300)

        layout = QVBoxLayout(egg)
        layout.setContentsMargins(16, 16, 16, 16)

        console = QLabel()
        console_text = (
            "> You found the secret console!\n"
            "> well done, mate. here's your egg:\n\n"
            "🥚 you're legendary\n\n"
            "> feeling brave? check out the github repo\n"
            "> or tweet @aidxn with what you built\n\n"
            "> cheers for using universal controller midi\n"
            "> –aiden\n\n"
        )
        console.setText(console_text)
        console.setStyleSheet(
            "background-color: #0a0e27; color: #00d084; font-family: monospace; "
            "font-size: 12px; padding: 12px; border-radius: 4px;"
        )
        console.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(console)

        close_btn = QPushButton("Close (or press ESC)")
        close_btn.clicked.connect(egg.close)
        layout.addWidget(close_btn)

        egg.keyPressEvent = lambda event: (
            egg.close() if event.key() == Qt.Key_Escape else None
        )

        self.easter_egg_window = egg
        egg.destroyed.connect(lambda: setattr(self, 'easter_egg_window', None))
        egg.show()
