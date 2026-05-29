"""Preset manager tab. Pro feature — list/save/load/delete JSON presets."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QMessageBox,
    QPushButton, QStackedLayout, QVBoxLayout, QWidget,
)

from .. import presets as preset_io
from ..license import is_pro
from ..mapping import Mapping
from .pro_lock import ProLockOverlay


class PresetManager(QWidget):
    upgrade_clicked = Signal()
    activate_clicked = Signal()
    preset_loaded = Signal(Mapping)

    def __init__(self, current_mapping_provider, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._get_current = current_mapping_provider

        self._stack = QStackedLayout(self)

        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        v.addWidget(QLabel("Saved presets"))
        self._list = QListWidget()
        v.addWidget(self._list, 1)

        row = QHBoxLayout()
        self._load_btn = QPushButton("Load")
        self._save_btn = QPushButton("Save current as…")
        self._delete_btn = QPushButton("Delete")
        self._export_btn = QPushButton("Export cheat sheet")
        self._load_btn.clicked.connect(self._on_load)
        self._save_btn.clicked.connect(self._on_save)
        self._delete_btn.clicked.connect(self._on_delete)
        self._export_btn.clicked.connect(self._on_export_cheatsheet)
        row.addWidget(self._load_btn)
        row.addWidget(self._save_btn)
        row.addWidget(self._delete_btn)
        row.addWidget(self._export_btn)
        row.addStretch(1)
        v.addLayout(row)

        self._stack.addWidget(content)

        self._lock = ProLockOverlay(
            "Preset Library",
            "Save unlimited mappings — one per song, per genre, per project. "
            "Hot-swap between them with one click.",
        )
        self._lock.upgrade_clicked.connect(self.upgrade_clicked.emit)
        self._lock.activate_clicked.connect(self.activate_clicked.emit)
        self._stack.addWidget(self._lock)

        self.refresh()
        self.refresh_lock()

    def refresh(self) -> None:
        self._list.clear()
        for name in preset_io.list_presets():
            self._list.addItem(name)

    def refresh_lock(self) -> None:
        self._stack.setCurrentIndex(0 if is_pro() else 1)

    # ------------------------------------------------------------------ actions

    def _on_load(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        mapping = preset_io.load_preset(item.text())
        self.preset_loaded.emit(mapping)

    def _on_save(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        if not ok or not name.strip():
            return
        mapping = self._get_current()
        mapping.name = name.strip()
        preset_io.save_preset(mapping)
        self.refresh()

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        preset_io.delete_preset(item.text())
        self.refresh()

    def _on_export_cheatsheet(self) -> None:
        from pathlib import Path
        from .. import cheatsheet as cheatsheet_mod

        mapping = self._get_current()
        safe_name = mapping.name.replace(" ", "_").replace("/", "-") or "mapping"
        default_path = str(
            Path.home() / "Desktop" / f"{safe_name}_cheatsheet.pdf"
        )
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export cheat sheet",
            default_path,
            "PDF Files (*.pdf)",
        )
        if not dest:
            return
        try:
            cheatsheet_mod.render_cheatsheet(mapping, Path(dest))
            QMessageBox.information(
                self,
                "Cheat sheet exported",
                f"Saved to:\n{dest}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Export failed",
                f"Could not write PDF:\n{exc}",
            )
