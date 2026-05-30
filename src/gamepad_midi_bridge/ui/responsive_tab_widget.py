"""ResponsiveTabWidget — drop-in for QTabWidget that swaps the tab bar for a
QComboBox dropdown when the window is narrower than a configurable threshold.

At >= threshold width: normal QTabWidget tab bar is visible.
At <  threshold width: tab bar is hidden; a QComboBox floats above the content
                       area instead so tab labels never get truncated to "P..."

The public API mirrors the subset used in main_window.py:
    addTab(widget, label)
    tabText(index) -> str
    count() -> int
    currentIndex() -> int
    setCurrentIndex(index)
    widget(index) -> QWidget | None
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_COMPACT_THRESHOLD = 720  # pixels — switch below this width


class ResponsiveTabWidget(QWidget):
    """QWidget that owns a QTabWidget internally and switches between its
    native tab bar and a compact QComboBox header depending on window width."""

    def __init__(
        self,
        parent: QWidget | None = None,
        threshold: int = _COMPACT_THRESHOLD,
    ) -> None:
        super().__init__(parent)
        self._threshold = threshold
        self._compact = False  # current mode; set properly in first resizeEvent

        # --- inner QTabWidget ---
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setUsesScrollButtons(True)
        from PySide6.QtCore import Qt as _Qt
        self._tabs.tabBar().setElideMode(_Qt.ElideRight)
        self._tabs.tabBar().setExpanding(False)
        # Keep the tab widget's own currentChanged wired to the combo so they
        # stay in sync regardless of which control the user interacts with.
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # --- compact combo ---
        self._combo = QComboBox()
        self._combo.setMinimumHeight(28)
        self._combo.setStyleSheet(
            "QComboBox { background: #0e0f12; color: #f5f7fa; "
            "border: 1px solid #2c313b; border-radius: 4px; "
            "padding: 4px 8px; font-size: 12px; font-weight: 500; }"
            "QComboBox::drop-down { border: none; }"
        )
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._combo.setVisible(False)  # hidden until compact mode activates

        # --- layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._combo)
        layout.addWidget(self._tabs, 1)

    # ------------------------------------------------------------------ public API

    def addTab(self, widget: QWidget, label: str) -> int:  # noqa: N802
        """Add a tab. Mirrors QTabWidget.addTab."""
        self._combo.addItem(label)
        return self._tabs.addTab(widget, label)

    def tabText(self, index: int) -> str:  # noqa: N802
        """Return the tab label at *index*. Mirrors QTabWidget.tabText."""
        return self._tabs.tabText(index)

    def count(self) -> int:
        """Number of tabs. Mirrors QTabWidget.count."""
        return self._tabs.count()

    def currentIndex(self) -> int:  # noqa: N802
        """Currently selected tab index. Mirrors QTabWidget.currentIndex."""
        return self._tabs.currentIndex()

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        """Switch to tab *index*. Mirrors QTabWidget.setCurrentIndex."""
        self._tabs.setCurrentIndex(index)

    def widget(self, index: int) -> QWidget | None:
        """Return the widget at *index*. Mirrors QTabWidget.widget."""
        return self._tabs.widget(index)

    # ------------------------------------------------------------------ mode switching

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_mode(event.size().width())

    def _apply_mode(self, width: int) -> None:
        compact = width < self._threshold
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            # Hide the native tab bar; show the combo.
            self._tabs.tabBar().setVisible(False)
            self._combo.setVisible(True)
            # Sync combo to current tab index.
            self._combo.setCurrentIndex(self._tabs.currentIndex())
        else:
            # Restore the native tab bar; hide the combo.
            self._tabs.tabBar().setVisible(True)
            self._combo.setVisible(False)

    # ------------------------------------------------------------------ signal glue

    def _on_tab_changed(self, index: int) -> None:
        """Keep the combo in sync when the tab widget's index changes."""
        if self._combo.currentIndex() != index:
            # Block the combo's signal to avoid a re-entrant loop.
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(index)
            self._combo.blockSignals(False)

    def _on_combo_changed(self, index: int) -> None:
        """Drive the tab widget when the user picks from the dropdown."""
        if self._tabs.currentIndex() != index:
            self._tabs.setCurrentIndex(index)
