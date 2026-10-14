"""Deferred tab content — build the real widget the first time it's shown.

Every tab used to be constructed during ``MainWindow.__init__``, so startup
paid for tabs the user might never open. ``LazyTab`` stands in for one of
them: it's an empty placeholder until Qt shows it, at which point it builds
the real widget, swaps it in, and emits ``loaded`` so MainWindow can wire
signals at that point.

Only worth it for tabs that cost real time to build AND aren't needed for
the first thing a user does. Deferring a cheap tab just moves work from
startup (where it's invisible) to a click (where it isn't).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LazyTab(QWidget):
    """Placeholder that builds its real content on first show."""

    # Emitted once, with the constructed widget, so the owner can wire it up.
    loaded = Signal(object)

    def __init__(self, factory: Callable[[], QWidget],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._factory = factory
        self._inner: Optional[QWidget] = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        # Shown only for the instant between the click and the build. Without
        # it the tab flashes as a blank panel with no indication anything is
        # happening.
        self._placeholder = QLabel("Loading…")
        self._placeholder.setObjectName("LazyTabPlaceholder")
        self._layout.addWidget(self._placeholder)

    # ------------------------------------------------------------------ API

    def inner(self) -> QWidget:
        """The real widget, building it now if it doesn't exist yet.

        Lets callers reach the content without waiting for a user click.
        """
        self._ensure_built()
        return self._inner  # type: ignore[return-value]

    def is_built(self) -> bool:
        return self._inner is not None

    # ------------------------------------------------------------ internals

    def showEvent(self, event) -> None:  # noqa: N802 — Qt override
        super().showEvent(event)
        self._ensure_built()

    def _ensure_built(self) -> None:
        if self._inner is not None:
            return
        widget = self._factory()
        self._inner = widget
        self._layout.removeWidget(self._placeholder)
        self._placeholder.setParent(None)
        self._placeholder.deleteLater()
        self._layout.addWidget(widget)
        self.loaded.emit(widget)
