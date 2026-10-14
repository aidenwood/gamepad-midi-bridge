"""NodeParamEditor — modal-ish dialog for editing a node's params.

Drives off `NodeSpec.params: Tuple[ParamSpec, ...]`. Each ParamSpec picks
the widget shape (float / int / bool / choice / string) and contributes
its `description` as a TouchDesigner-style hover tooltip on every row.

Live-applies on OK (writes into ``node.params`` and tells the scene to
repaint the card so the new values show up in the param-row display).
Cancel reverts nothing — there's no preview path yet; edits are only
committed on OK.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..nodes import Node, NodeSpec, ParamSpec


class NodeParamEditor(QDialog):
    """One-shot dialog for editing the params of a single Node.

    Args:
        node: live Node from the graph — mutated in place on OK.
        spec: the NodeSpec for the node's kind — drives the widget choices.
        parent: usually the MainWindow.
    """

    def __init__(
        self,
        *,
        node: Node,
        spec: NodeSpec,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._node = node
        self._spec = spec
        self._readers: Dict[str, Callable[[], Any]] = {}

        self.setWindowTitle(f"Edit — {spec.label}")
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        # Header — node name + short description so the user remembers
        # WHY they opened this dialog when scanning between graphs.
        if spec.short_description:
            outer.addWidget(QLabel(spec.short_description))

        # Empty form is allowed — e.g. polar has no params. Show a hint
        # instead of an empty grid so the user doesn't think it's broken.
        if not spec.params:
            outer.addWidget(QLabel(
                "<i>This node has no parameters.</i>"
            ))
        else:
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.setSpacing(10)
            for ps in spec.params:
                row_widget, reader = self._build_row(ps)
                row_widget.setToolTip(ps.description)
                form.addRow(self._label_for(ps), row_widget)
                self._readers[ps.name] = reader
            outer.addLayout(form)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # ----------------------------------------------------------- row builders

    @staticmethod
    def _label_for(ps: ParamSpec) -> QLabel:
        text = ps.name
        if ps.unit:
            text = f"{text} ({ps.unit})"
        lbl = QLabel(text)
        lbl.setToolTip(ps.description)
        return lbl

    def _build_row(self, ps: ParamSpec):
        """Pick a widget + return ``(widget, reader)`` where ``reader()``
        returns the current value as the right Python type."""
        current = self._node.params.get(ps.name, ps.default)
        if ps.kind == "bool":
            cb = QCheckBox()
            cb.setChecked(bool(current))
            return cb, lambda: cb.isChecked()
        if ps.kind == "int":
            sb = QSpinBox()
            sb.setMinimum(int(ps.minimum) if ps.minimum is not None else -10**6)
            sb.setMaximum(int(ps.maximum) if ps.maximum is not None else 10**6)
            sb.setValue(int(current))
            if ps.unit:
                sb.setSuffix(f" {ps.unit}")
            return sb, lambda: sb.value()
        if ps.kind == "float":
            dsb = QDoubleSpinBox()
            dsb.setDecimals(3)
            dsb.setMinimum(float(ps.minimum) if ps.minimum is not None else -1e6)
            dsb.setMaximum(float(ps.maximum) if ps.maximum is not None else 1e6)
            dsb.setSingleStep(0.01)
            dsb.setValue(float(current))
            if ps.unit:
                dsb.setSuffix(f" {ps.unit}")
            return dsb, lambda: dsb.value()
        if ps.kind == "choice":
            combo = QComboBox()
            for opt in ps.choices or ():
                combo.addItem(opt)
            if isinstance(current, str) and current in (ps.choices or ()):
                combo.setCurrentText(current)
            return combo, lambda: combo.currentText()
        # string fallback (also catches midi_target — Phase 2 uses a free-
        # text input; a richer picker can land later).
        edit = QLineEdit()
        edit.setText(str(current) if current is not None else "")
        return edit, lambda: edit.text()

    # ----------------------------------------------------------- accept

    def _on_accept(self) -> None:
        for name, reader in self._readers.items():
            self._node.params[name] = reader()
        self.accept()
