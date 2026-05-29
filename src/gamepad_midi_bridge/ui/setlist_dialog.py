"""SetlistDialog — build and manage an ordered preset step-through list.

Lets performers pre-arrange a sequence of presets (e.g. intro → verse → drop →
outro) and designate two controller buttons to step Next/Prev through the list
at show time. BridgeWorker.setlist_step fires on each button press; the main
window loads and applies the preset.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from .. import presets as preset_io
from ..mapping import Mapping, SetlistConfig


class SetlistDialog(QDialog):
    """Dialog for editing the mapping's SetlistConfig.

    Emits `mapping_changed` with the updated Mapping when the user clicks OK.
    """

    mapping_changed = Signal(Mapping)

    def __init__(self, mapping: Mapping, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mapping = mapping
        sl = mapping.setlist

        self.setWindowTitle("Setlist")
        self.resize(480, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # --- Enabled checkbox ---
        self._enabled_cb = QCheckBox("Enable setlist mode")
        self._enabled_cb.setChecked(sl.enabled)
        layout.addWidget(self._enabled_cb)

        # --- Name ---
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit(sl.name)
        name_row.addWidget(self._name_edit, 1)
        layout.addLayout(name_row)

        # --- Preset list ---
        layout.addWidget(QLabel("Preset order (drag to reorder):"))
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        for slug in sl.presets:
            self._list.addItem(QListWidgetItem(slug))
        layout.addWidget(self._list, 1)

        # Add / Remove preset
        list_btns = QHBoxLayout()
        self._preset_combo = QComboBox()
        available = preset_io.list_presets()
        if available:
            self._preset_combo.addItems(available)
        add_btn = QPushButton("Add preset")
        remove_btn = QPushButton("Remove selected")
        add_btn.clicked.connect(self._on_add)
        remove_btn.clicked.connect(self._on_remove)
        list_btns.addWidget(self._preset_combo, 1)
        list_btns.addWidget(add_btn)
        list_btns.addWidget(remove_btn)
        layout.addLayout(list_btns)

        # --- Button assignments ---
        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("Next button index:"))
        self._next_spin = QSpinBox()
        self._next_spin.setRange(-1, 31)
        self._next_spin.setSpecialValueText("(unset)")
        self._next_spin.setValue(sl.next_button)
        btn_row.addWidget(self._next_spin)
        btn_row.addSpacing(16)
        btn_row.addWidget(QLabel("Prev button index:"))
        self._prev_spin = QSpinBox()
        self._prev_spin.setRange(-1, 31)
        self._prev_spin.setSpecialValueText("(unset)")
        self._prev_spin.setValue(sl.prev_button)
        btn_row.addWidget(self._prev_spin)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # --- Wrap checkbox ---
        self._wrap_cb = QCheckBox("Wrap around at ends")
        self._wrap_cb.setChecked(sl.wrap)
        layout.addWidget(self._wrap_cb)

        # --- OK / Cancel ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ actions

    def _on_add(self) -> None:
        slug = self._preset_combo.currentText()
        if slug:
            self._list.addItem(QListWidgetItem(slug))

    def _on_remove(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _on_ok(self) -> None:
        presets = [
            self._list.item(i).text()
            for i in range(self._list.count())
        ]
        self._mapping.setlist = SetlistConfig(
            enabled=self._enabled_cb.isChecked(),
            name=self._name_edit.text().strip() or "Setlist",
            presets=presets,
            next_button=self._next_spin.value(),
            prev_button=self._prev_spin.value(),
            wrap=self._wrap_cb.isChecked(),
        )
        self.mapping_changed.emit(self._mapping)
        self.accept()
