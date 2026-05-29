"""Command Palette — Cmd-K / Ctrl-K global search dialog.

Linear / Spotlight style: type to filter, Up/Down to navigate, Enter to run,
Esc to close. Pure PySide6, no extra dependencies.
"""
from __future__ import annotations

from typing import Callable, List, NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class Command(NamedTuple):
    title: str
    subtitle: str
    callback: Callable[[], None]


def _score(query: str, title: str) -> int:
    """Return a match score. Higher = better match. 0 = no match.

    Priority:
        3 — exact prefix (title starts with query)
        2 — word prefix (any word in title starts with query)
        1 — substring anywhere
        0 — no match
    """
    lq = query.lower()
    lt = title.lower()
    if not lq:
        return 1  # empty query matches everything with equal weight
    if lt.startswith(lq):
        return 3
    words = lt.split()
    if any(w.startswith(lq) for w in words):
        return 2
    if lq in lt:
        return 1
    return 0


class CommandPalette(QDialog):
    """Floating command palette dialog. Create once per trigger, then exec()."""

    def __init__(self, commands: List[Command], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._commands = commands
        self._filtered: List[Command] = list(commands)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.resize(600, 400)

        self._build_ui()
        self._refresh_list("")

        # Auto-focus the search input.
        self._search.setFocus()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Container card
        card = QWidget()
        card.setObjectName("CommandPaletteCard")
        card.setStyleSheet(
            "QWidget#CommandPaletteCard {"
            "  background: #16181f;"
            "  border: 1px solid #2c313b;"
            "  border-radius: 10px;"
            "}"
        )
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Search input
        self._search = QLineEdit()
        self._search.setObjectName("CommandPaletteSearch")
        self._search.setPlaceholderText("Type a command...")
        self._search.setStyleSheet(
            "QLineEdit#CommandPaletteSearch {"
            "  background: transparent;"
            "  border: none;"
            "  border-bottom: 1px solid #2c313b;"
            "  border-radius: 0;"
            "  color: #f5f7fa;"
            "  font-size: 15px;"
            "  padding: 14px 18px;"
            "}"
        )
        self._search.textChanged.connect(self._on_text_changed)
        self._search.installEventFilter(self)
        v.addWidget(self._search)

        # Results list
        self._list = QListWidget()
        self._list.setObjectName("CommandPaletteList")
        self._list.setStyleSheet(
            "QListWidget#CommandPaletteList {"
            "  background: transparent;"
            "  border: none;"
            "  outline: none;"
            "  color: #f5f7fa;"
            "  font-size: 13px;"
            "  padding: 4px 0;"
            "}"
            "QListWidget#CommandPaletteList::item {"
            "  padding: 8px 18px;"
            "  border-radius: 6px;"
            "}"
            "QListWidget#CommandPaletteList::item:selected {"
            "  background: #2563eb;"
            "  color: #ffffff;"
            "}"
            "QListWidget#CommandPaletteList::item:hover:!selected {"
            "  background: #1e2230;"
            "}"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #2c313b; border-radius: 3px; }"
        )
        self._list.itemActivated.connect(self._execute_current)
        v.addWidget(self._list, 1)

        # Hint footer
        hint = QLabel("Up/Down navigate   Enter run   Esc close")
        hint.setStyleSheet(
            "color: #5a606b; font-size: 11px; padding: 8px 18px;"
            "border-top: 1px solid #1c1e25;"
        )
        v.addWidget(hint)

    # ------------------------------------------------------------------ filtering

    def _on_text_changed(self, text: str) -> None:
        self._refresh_list(text)

    def _refresh_list(self, query: str) -> None:
        scored = [(cmd, _score(query, cmd.title)) for cmd in self._commands]
        # Keep matches only (score > 0). Sort descending by score, then alpha.
        scored = [(c, s) for c, s in scored if s > 0]
        scored.sort(key=lambda x: (-x[1], x[0].title.lower()))
        self._filtered = [c for c, _ in scored]

        self._list.clear()
        for cmd in self._filtered:
            item = QListWidgetItem()
            item.setText(cmd.title)
            item.setToolTip(cmd.subtitle)
            item.setData(Qt.UserRole, cmd.subtitle)
            self._list.addItem(item)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    # ------------------------------------------------------------------ keyboard

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        if obj is self._search and isinstance(event, QKeyEvent):
            key = event.key()
            if key == Qt.Key_Down:
                self._move_selection(1)
                return True
            if key == Qt.Key_Up:
                self._move_selection(-1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._execute_current()
                return True
            if key == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    def _move_selection(self, delta: int) -> None:
        count = self._list.count()
        if count == 0:
            return
        row = self._list.currentRow()
        new_row = (row + delta) % count
        self._list.setCurrentRow(new_row)

    # ------------------------------------------------------------------ execution

    def _execute_current(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._filtered):
            return
        cmd = self._filtered[row]
        self.accept()
        cmd.callback()

    # ------------------------------------------------------------------ centering

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        # Centre over the parent (or screen if no parent).
        if self.parentWidget() is not None:
            parent_rect = self.parentWidget().geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 3
            self.move(x, y)
        else:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.geometry()
                self.move(
                    sg.x() + (sg.width() - self.width()) // 2,
                    sg.y() + (sg.height() - self.height()) // 3,
                )
