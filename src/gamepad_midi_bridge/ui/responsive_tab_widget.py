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

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLayout,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Vertical floor the tab area reports to a parent splitter. A QTabWidget's
# minimumSizeHint is the MAX over ALL pages, so one tall page (e.g. About at
# ~1080 px) would otherwise force the whole window taller than the screen and
# squeeze a sibling bottom dock (Console / MIDI activity) to nothing. Cap the
# floor here; tall pages scroll within their own viewport instead.
_MIN_CONTENT_HEIGHT = 160

# Horizontal twin of the above. 320 is narrower than the window's own 380 px
# floor, so the tab area is never the thing blocking a resize.
_MIN_CONTENT_WIDTH = 320

_COMPACT_THRESHOLD = 1100  # pixels — switch below this width. 11 tabs at
# ~95 px each comfortably fit in ~1050 px; below this width we collapse to a
# QComboBox dropdown so labels never get truncated to "Li..."/"Vis..."

# Tabs that own their own panning / zooming viewport. Nesting those inside a
# QScrollArea gives two things fighting over the same wheel event, so they
# opt out and keep their natural (small) width floor instead.
_NO_SCROLL_TABS = frozenset({"Nodes"})


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
        self._chrome_hidden = False
        # index -> the REAL page widget. ``_tabs.widget(i)`` may be the
        # QScrollArea wrapper, and callers want the page.
        self._pages: list[QWidget] = []

        # --- inner QTabWidget ---
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setUsesScrollButtons(True)
        from PySide6.QtCore import Qt as _Qt
        # ElideNone — let tabs keep their natural width. With scroll buttons
        # on + non-expanding, overflow tabs are reachable via ← → arrows
        # instead of every label getting truncated to "Li..."
        self._tabs.tabBar().setElideMode(_Qt.ElideNone)
        self._tabs.tabBar().setExpanding(False)
        # Pad tabs to their label size — apply via objectName so the rule
        # lives in styles.qss.
        self._tabs.tabBar().setObjectName("ResponsiveTabBar")
        # Keep the tab widget's own currentChanged wired to the combo so they
        # stay in sync regardless of which control the user interacts with.
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # --- compact combo ---
        self._combo = QComboBox()
        self._combo.setObjectName("ResponsiveTabPickerCombo")
        self._combo.setMinimumHeight(28)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._combo.setVisible(False)  # hidden until compact mode activates

        # --- layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # Don't let the layout push our minimumSize up to the inner tabs'
        # aggregate minimum — minimumSizeHint() below controls our floor.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.addWidget(self._combo)
        layout.addWidget(self._tabs, 1)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Cap BOTH floors so one fat page can't dictate the whole window.

        Height: a tall page (About is ~1080 px) would otherwise force the
        window taller than the screen and squeeze the bottom dock to nothing.

        Width: same problem sideways, and worse — the Bluetooth page alone
        wanted 549 px, which meant the window physically could not be dragged
        to the 380 px floor it advertises. Pages are wrapped in a QScrollArea
        by ``addTab``, so a page that genuinely needs more room scrolls
        instead of pinning every other part of the app.
        """
        hint = self._tabs.minimumSizeHint()
        return QSize(min(hint.width(), _MIN_CONTENT_WIDTH),
                     min(hint.height(), _MIN_CONTENT_HEIGHT))

    # ------------------------------------------------------------------ public API

    def addTab(self, widget: QWidget, label: str) -> int:  # noqa: N802
        """Add a tab. Mirrors QTabWidget.addTab.

        The page is wrapped in a scroll area unless it is in
        ``_NO_SCROLL_TABS``. ``widgetResizable`` means the page still fills
        the viewport whenever there is room, so nothing changes on a wide
        window — scrollbars appear only when the page genuinely cannot fit.
        """
        self._combo.addItem(label)
        self._pages.append(widget)
        if label in _NO_SCROLL_TABS:
            return self._tabs.addTab(widget, label)
        scroller = QScrollArea()
        scroller.setObjectName("TabScrollArea")
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.NoFrame)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroller.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroller.setWidget(widget)
        return self._tabs.addTab(scroller, label)

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
        """Return the PAGE at *index*, not its scroll-area wrapper.

        Mirrors QTabWidget.widget from the caller's point of view — callers
        asked for the Mapping editor, not the viewport it happens to sit in.
        """
        if 0 <= index < len(self._pages):
            return self._pages[index]
        return self._tabs.widget(index)

    # ------------------------------------------------------------------ mode switching

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_mode(event.size().width())

    def set_chrome_visible(self, visible: bool) -> None:
        """Show or permanently hide this widget's OWN navigation chrome.

        The shell header owns navigation now, so the tab strip and its
        compact combo are redundant. They cannot simply be hidden from
        outside: `_apply_mode` re-asserts tab-bar visibility on every
        resize, so an external hide gets undone on the next resize event
        and the two fight each other. One owner, one switch.
        """
        self._chrome_hidden = not visible
        self._tabs.tabBar().setVisible(visible and not self._compact)
        self._combo.setVisible(visible and self._compact)

    def _apply_mode(self, width: int) -> None:
        compact = width < self._threshold
        if compact == self._compact:
            return
        self._compact = compact
        if getattr(self, "_chrome_hidden", False):
            # Still track compact state for anything else that reads it,
            # but leave the chrome alone — the header is doing this job.
            self._tabs.tabBar().setVisible(False)
            self._combo.setVisible(False)
            return
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
