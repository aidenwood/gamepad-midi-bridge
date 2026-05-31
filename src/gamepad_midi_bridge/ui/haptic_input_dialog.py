"""Dialog for editing the haptic-input binding table.

Why a dialog vs an inline editor in SettingsPanel: bindings are an N-row
table with five columns; embedding that table in the Settings tab would
crowd the existing groups (channel, deadzone, OSC host, etc). A dialog
also lets the user dump the entire list and rebuild from scratch without
fear of partially-saved state — they hit Cancel to abort.

Columns (left to right):
    Trigger      L2 / R2        ComboBox
    Source       note / cc      ComboBox
    MIDI ID      0..127         SpinBox  (note number OR CC number)
    Effect       feedback/vibration/weapon/...  ComboBox
    Intensity    0.00..4.00     DoubleSpinBox  (gain multiplier)

The "Listen channel" SpinBox at the top tunes the channel filter without
having to memorise that -1 means "all channels" - the spin shows
"All channels" at zero and otherwise channels 1..16 mapped to 0..15.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox, QTableWidget,
    QVBoxLayout, QWidget,
)

from ..dualsense import TRIGGER_EFFECTS
from ..mapping import HapticInputBinding, HapticInputConfig


# Column indices - keep in sync with `_HEADERS`. Declared as constants so the
# row-building code reads as `_COL_TRIGGER` rather than magic `0`.
_COL_TRIGGER = 0
_COL_SOURCE = 1
_COL_MIDI_ID = 2
_COL_EFFECT = 3
_COL_INTENSITY = 4

_HEADERS = ["Trigger", "Source", "MIDI ID", "Effect", "Intensity"]

_TRIGGER_CHOICES = ["L2", "R2"]
_SOURCE_CHOICES = [("Note", "note"), ("CC", "cc")]
# Skip "off" - binding a trigger pulse to "do nothing" makes no sense.
_EFFECT_CHOICES = [e for e in TRIGGER_EFFECTS.keys() if e != "off"]


class HapticInputDialog(QDialog):
    """Editor for HapticInputConfig bindings + listen channel.

    Lifecycle: caller passes the live config object; dialog snapshots it
    into local widgets and only writes back when the parent reads
    `bindings()` / `listen_channel()` after the dialog is accepted.
    """

    def __init__(self, config: HapticInputConfig,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Haptic-in bindings")
        self.resize(640, 440)
        self._config = config

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        intro = QLabel(
            "Each binding fires an adaptive-trigger effect when a matching "
            "incoming MIDI message arrives. Velocity (notes) or value (CCs) "
            "scales how hard you feel it."
        )
        intro.setObjectName("HapticInputDialogIntro")
        intro.setWordWrap(True)
        root.addWidget(intro)

        # Listen channel filter sits above the table so it's visible without
        # scrolling, even on tiny laptop displays.
        chan_form = QFormLayout()
        self._channel = QSpinBox()
        self._channel.setRange(0, 16)
        # Display: 0 = "All channels", 1..16 = MIDI channels 1..16. Internally
        # we store -1 for "all" so the bridge can `cfg.listen_channel >= 0`.
        self._channel.setSpecialValueText("All channels")
        self._channel.setValue(0 if config.listen_channel < 0
                               else config.listen_channel + 1)
        chan_form.addRow("Listen channel", self._channel)
        root.addLayout(chan_form)

        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        for i in range(len(_HEADERS)):
            mode = (QHeaderView.Stretch if i == _COL_EFFECT
                    else QHeaderView.ResizeToContents)
            header.setSectionResizeMode(i, mode)
        for binding in config.bindings:
            self._append_row(binding)
        root.addWidget(self._table, 1)

        # Action row - add/remove flanking the OK/Cancel pair so users see
        # row controls grouped together rather than scattered.
        row = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._on_add)
        remove_btn = QPushButton("- Remove")
        remove_btn.clicked.connect(self._on_remove)
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addStretch(1)
        root.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------ rows

    def _append_row(self, binding: HapticInputBinding) -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)

        trigger_combo = QComboBox()
        trigger_combo.addItems(_TRIGGER_CHOICES)
        normalised = binding.trigger.upper()
        idx = (_TRIGGER_CHOICES.index(normalised)
               if normalised in _TRIGGER_CHOICES else 0)
        trigger_combo.setCurrentIndex(idx)
        self._table.setCellWidget(r, _COL_TRIGGER, trigger_combo)

        source_combo = QComboBox()
        for label, value in _SOURCE_CHOICES:
            source_combo.addItem(label, value)
        source_values = [v for _, v in _SOURCE_CHOICES]
        sidx = (source_values.index(binding.source)
                if binding.source in source_values else 0)
        source_combo.setCurrentIndex(sidx)
        self._table.setCellWidget(r, _COL_SOURCE, source_combo)

        midi_spin = QSpinBox()
        midi_spin.setRange(0, 127)
        midi_spin.setValue(int(binding.midi_id))
        self._table.setCellWidget(r, _COL_MIDI_ID, midi_spin)

        effect_combo = QComboBox()
        effect_combo.addItems(_EFFECT_CHOICES)
        if binding.effect in _EFFECT_CHOICES:
            effect_combo.setCurrentIndex(_EFFECT_CHOICES.index(binding.effect))
        self._table.setCellWidget(r, _COL_EFFECT, effect_combo)

        intensity_spin = QDoubleSpinBox()
        intensity_spin.setRange(0.0, 4.0)
        intensity_spin.setSingleStep(0.1)
        intensity_spin.setDecimals(2)
        intensity_spin.setValue(float(binding.intensity_scale))
        self._table.setCellWidget(r, _COL_INTENSITY, intensity_spin)

    def _on_add(self) -> None:
        # Default: kick->L2 vibration so a freshly-added row already "does
        # something" without the user having to configure every field.
        self._append_row(HapticInputBinding())

    def _on_remove(self) -> None:
        rows = sorted({i.row() for i in self._table.selectedIndexes()},
                      reverse=True)
        if not rows:
            # If nothing selected, drop the last row - matches the
            # "trailing remove" convention from spreadsheet apps.
            if self._table.rowCount() > 0:
                self._table.removeRow(self._table.rowCount() - 1)
            return
        for r in rows:
            self._table.removeRow(r)

    # ------------------------------------------------------------- accessors

    def bindings(self) -> List[HapticInputBinding]:
        """Read every row back into HapticInputBinding instances.

        Only called after the dialog is accepted, so we don't worry about
        partial state. Rows with invalid widgets are skipped silently rather
        than refusing to close the dialog.
        """
        out: List[HapticInputBinding] = []
        for r in range(self._table.rowCount()):
            try:
                trigger = self._table.cellWidget(r, _COL_TRIGGER).currentText()
                source = self._table.cellWidget(r, _COL_SOURCE).currentData()
                midi_id = self._table.cellWidget(r, _COL_MIDI_ID).value()
                effect = self._table.cellWidget(r, _COL_EFFECT).currentText()
                intensity = self._table.cellWidget(r, _COL_INTENSITY).value()
                out.append(HapticInputBinding(
                    trigger=trigger,
                    source=source,
                    midi_id=int(midi_id),
                    effect=effect,
                    intensity_scale=float(intensity),
                ))
            except (AttributeError, ValueError):
                continue
        return out

    def listen_channel(self) -> int:
        """Translate the spin's 0..16 value back to the bridge's -1..15.

        Spin 0 = "All channels" -> -1. Spin 1..16 -> 0..15.
        """
        raw = self._channel.value()
        return -1 if raw == 0 else raw - 1
