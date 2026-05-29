"""Preset manager tab. Pro feature — list/save/load/delete JSON presets."""
from __future__ import annotations

from typing import Optional
from pathlib import Path
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QMessageBox,
    QPushButton, QStackedLayout, QVBoxLayout, QWidget,
)

from .. import presets as preset_io
from .. import snapshots as snap_io
from ..license import is_pro
from ..mapping import Mapping
from .diff_dialog import DiffDialog
from .pro_lock import ProLockOverlay
from .snapshot_dialog import SnapshotDialog


class PresetManager(QWidget):
    upgrade_clicked = Signal()
    activate_clicked = Signal()
    preset_loaded = Signal(Mapping)
    selection_changed = Signal(dict)

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
        self._list.itemClicked.connect(self._on_list_selection_changed)
        v.addWidget(self._list, 1)

        row = QHBoxLayout()
        self._load_btn = QPushButton("Load")
        self._save_btn = QPushButton("Save current as…")
        self._delete_btn = QPushButton("Delete")
        self._compare_btn = QPushButton("Compare presets…")
        self._export_btn = QPushButton("Export cheat sheet")
        self._snapshots_btn = QPushButton("Snapshots…")
        self._load_btn.clicked.connect(self._on_load)
        self._save_btn.clicked.connect(self._on_save)
        self._delete_btn.clicked.connect(self._on_delete)
        self._compare_btn.clicked.connect(self._on_compare)
        self._export_btn.clicked.connect(self._on_export_cheatsheet)
        self._snapshots_btn.clicked.connect(self._on_snapshots)
        row.addWidget(self._load_btn)
        row.addWidget(self._save_btn)
        row.addWidget(self._delete_btn)
        row.addWidget(self._compare_btn)
        row.addWidget(self._export_btn)
        row.addWidget(self._snapshots_btn)
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

    def _on_list_selection_changed(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        preset_name = item.text()
        try:
            # Get file path and stats
            from .. import paths
            preset_path = paths.preset_path(preset_name)
            mtime = preset_path.stat().st_mtime if preset_path.exists() else 0
            size = preset_path.stat().st_size if preset_path.exists() else 0
            # Format mtime as ISO-like string
            from datetime import datetime
            dt = datetime.fromtimestamp(mtime)
            mtime_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            size_str = f"{size} bytes" if size < 1024 else f"{size // 1024} KB"
            self.selection_changed.emit({
                "kind": "preset_file",
                "slug": preset_name.replace(" ", "_").lower(),
                "name": preset_name,
                "mtime": mtime_str,
                "size": size_str,
                "label": preset_name,
            })
        except Exception:
            pass

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

    def _on_compare(self) -> None:
        """Open a dialog to pick two presets and compare them."""
        presets = preset_io.list_presets()
        if len(presets) < 2:
            QMessageBox.information(
                self,
                "Compare presets",
                "Need at least 2 presets to compare.",
            )
            return

        # Picker dialog with two dropdowns
        picker = QDialog(self)
        picker.setWindowTitle("Compare presets")
        picker.resize(400, 150)

        layout = QVBoxLayout(picker)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Preset A picker
        layout.addWidget(QLabel("Preset A (left):"))
        combo_a = QComboBox()
        combo_a.addItems(presets)
        layout.addWidget(combo_a)

        # Preset B picker
        layout.addWidget(QLabel("Preset B (right):"))
        combo_b = QComboBox()
        combo_b.addItems(presets)
        if len(presets) > 1:
            combo_b.setCurrentIndex(1)
        layout.addWidget(combo_b)

        # OK / Cancel
        layout.addStretch(1)
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Compare")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(picker.accept)
        cancel_btn.clicked.connect(picker.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        if picker.exec() != QDialog.Accepted:
            return

        # Load presets and show diff
        name_a = combo_a.currentText()
        name_b = combo_b.currentText()
        mapping_a = preset_io.load_preset(name_a)
        mapping_b = preset_io.load_preset(name_b)

        if mapping_a and mapping_b:
            diff_dialog = DiffDialog(mapping_a, mapping_b, name_a, name_b, self)
            diff_dialog.exec()

    def _on_snapshots(self) -> None:
        """Open the SnapshotDialog. Restore applies the mapping via preset_loaded."""
        dlg = SnapshotDialog(self._get_current, self)
        dlg.restore_requested.connect(self._on_snapshot_restore)
        dlg.exec()

    def _on_snapshot_restore(self, slug: str) -> None:
        mapping = snap_io.load_snapshot(slug)
        if mapping is not None:
            self.preset_loaded.emit(mapping)

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
