"""Preset manager tab. Pro feature — list/save/load/delete JSON presets."""
from __future__ import annotations

from typing import Optional
from pathlib import Path
import os

from PySide6.QtCore import Qt, Signal
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
from .setlist_dialog import SetlistDialog
from .snapshot_dialog import SnapshotDialog


class PresetManager(QWidget):
    upgrade_clicked = Signal()
    activate_clicked = Signal()
    preset_loaded = Signal(Mapping)
    selection_changed = Signal(dict)
    mapping_changed = Signal(Mapping)

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
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        v.addWidget(self._list, 1)

        row = QHBoxLayout()
        self._load_btn = QPushButton("Load")
        self._save_btn = QPushButton("Save current as…")
        self._delete_btn = QPushButton("Delete")
        self._compare_btn = QPushButton("Compare presets…")
        self._export_btn = QPushButton("Export cheat sheet")
        self._snapshots_btn = QPushButton("Snapshots…")
        self._setlist_btn = QPushButton("Setlist…")
        self._load_btn.clicked.connect(self._on_load)
        self._save_btn.clicked.connect(self._on_save)
        self._delete_btn.clicked.connect(self._on_delete)
        self._compare_btn.clicked.connect(self._on_compare)
        self._export_btn.clicked.connect(self._on_export_cheatsheet)
        self._snapshots_btn.clicked.connect(self._on_snapshots)
        self._setlist_btn.clicked.connect(self._on_setlist)
        row.addWidget(self._load_btn)
        row.addWidget(self._save_btn)
        row.addWidget(self._delete_btn)
        row.addWidget(self._compare_btn)
        row.addWidget(self._export_btn)
        row.addWidget(self._snapshots_btn)
        row.addWidget(self._setlist_btn)
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
        """Populate list with presets grouped by category (folder)."""
        self._list.clear()
        categories = preset_io.list_categories()
        all_presets = preset_io.list_presets()
        
        # Show presets grouped by folder
        # First, add presets from each category as a header with child items
        for category in categories:
            cat_item = self._list.addItem(f"📁 {category}")
            cat_idx = self._list.count() - 1
            # Add presets in this category
            for preset_name in all_presets:
                if "/" in preset_name and preset_name.split("/")[0] == category:
                    self._list.addItem(f"  └ {preset_name.split('/', 1)[1]}")
        
        # Then add top-level presets
        for preset_name in all_presets:
            if "/" not in preset_name:
                self._list.addItem(preset_name)

    def refresh_lock(self) -> None:
        self._stack.setCurrentIndex(0 if is_pro() else 1)
    def _clean_preset_name(self, raw_name: str) -> str:
        """Extract actual preset name from display text with decorations."""
        preset_name = raw_name.strip()
        if preset_name.startswith("📁 "):
            return ""  # Skip category headers
        if preset_name.startswith("  └ "):
            return preset_name[4:]  # Remove indent marker
        return preset_name


    # ------------------------------------------------------------------ actions

    def _on_list_selection_changed(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        raw_name = item.text()
        # Clean up display decorations from preset name
        preset_name = raw_name.strip()
        if preset_name.startswith("📁 "):
            return  # Skip category headers
        if preset_name.startswith("  └ "):
            preset_name = preset_name[4:]  # Remove indent marker
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
        preset_name = self._clean_preset_name(item.text())
        if not preset_name:
            return
        mapping = preset_io.load_preset(preset_name)
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
        preset_name = self._clean_preset_name(item.text())
        if not preset_name:
            return
        preset_io.delete_preset(preset_name)
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

    def _on_setlist(self) -> None:
        """Open SetlistDialog. OK saves to mapping.setlist and emits mapping_changed."""
        mapping = self._get_current()
        dlg = SetlistDialog(mapping, self)
        dlg.mapping_changed.connect(self.mapping_changed.emit)
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


    def _on_context_menu(self, position) -> None:
        """Show context menu with Move to folder option."""
        item = self._list.itemAt(position)
        if item is None:
            return
        
        preset_name = self._clean_preset_name(item.text())
        if not preset_name:
            return
        
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        
        # Move to folder action
        move_action = menu.addAction("Move to folder…")
        move_action.triggered.connect(lambda: self._move_preset_to_folder(preset_name))

        # Export as docs action
        docs_action = menu.addAction("Export as docs…")
        docs_action.triggered.connect(lambda: self._on_export_docs(preset_name))

        menu.exec(self._list.mapToGlobal(position))

    def _move_preset_to_folder(self, preset_name: str) -> None:
        """Show dialog to move preset to a folder."""
        categories = preset_io.list_categories()
        
        from PySide6.QtWidgets import QInputDialog
        
        items = ["(Top-level)"] + categories
        folder, ok = QInputDialog.getItem(
            self,
            "Move preset to folder",
            "Select folder:",
            items,
            0,
            False
        )
        
        if not ok:
            return

        target_folder = "" if folder == "(Top-level)" else folder
        try:
            preset_io.move_preset(preset_name, target_folder)
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Move failed",
                f"Could not move preset:\n{exc}",
            )

    def _on_export_docs(self, preset_name: str) -> None:
        """Export *preset_name* as a Markdown documentation file."""
        from pathlib import Path
        from .. import mapping_docs as docs_mod

        try:
            mapping = preset_io.load_preset(preset_name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", f"Could not load preset:\n{exc}")
            return

        safe_name = preset_name.replace("/", "-").replace(" ", "_") or "mapping"
        default_path = str(Path.home() / "Desktop" / f"{safe_name}.md")
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export mapping as docs",
            default_path,
            "Markdown Files (*.md)",
        )
        if not dest:
            return
        try:
            md = docs_mod.render_mapping_docs(mapping)
            Path(dest).write_text(md, encoding="utf-8")
            QMessageBox.information(
                self,
                "Docs exported",
                f"Saved to:\n{dest}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", f"Could not write file:\n{exc}")