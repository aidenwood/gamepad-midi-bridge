"""UIDropdownMenu — Radix-style menu primitive over QMenu.

A fluent wrapper that gives QMenu a richer surface API matching Radix's
``DropdownMenu`` patterns:

    menu = UIDropdownMenu()
    menu.add_label("View")
    menu.add_item("Reset zoom", on_click=app.reset_zoom, shortcut="⌘0")
    menu.add_item("Fit to viewport", on_click=app.fit)
    menu.add_separator()
    menu.add_checkable("Snap to grid", checked=True, on_toggle=app.set_snap)
    submenu = menu.add_submenu("Export…")
    submenu.add_item("XML…", on_click=app.export_xml)
    submenu.add_item("JSON…", on_click=app.export_json)

    menu.attach_to_button(my_button)        # click-to-open
    menu.popup_at_global(QCursor.pos())     # ad-hoc popup (e.g. right-click)

Styling is owned by the global QSS so the menu picks up theme changes
automatically. The class only deals with structure and wiring.

Why a wrapper rather than subclass QMenu directly: the fluent ``return self``
pattern in TypeScript translates poorly to inheriting from QMenu (signature
conflicts with QMenu.addAction). The wrapper holds the QMenu, exposes it
via ``.menu`` for advanced cases, and keeps the surface clean.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QAction, QCursor, QIcon, QKeySequence
from PySide6.QtWidgets import QMenu, QPushButton, QWidget


class UIDropdownMenu(QObject):
    """Fluent wrapper around QMenu — Radix-style API.

    Every ``add_*`` method returns ``self`` so multiple items can be chained
    inline if that reads better at the call site.
    """

    def __init__(
        self,
        *,
        title: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.menu = QMenu(title or "", parent)
        # Stable object name lets the global QSS target this menu (and any
        # submenus, which inherit) without leaking generic QMenu styling
        # into native Qt menus we don't own.
        self.menu.setObjectName("UIDropdownMenu")
        # Don't let macOS-native menu-merging hijack items we explicitly
        # name "Settings" / "Preferences" / "Quit" etc. inside an in-app
        # dropdown — those should stay where the user dropped them.
        self.menu.setSeparatorsCollapsible(False)

    # ============================================================ build API

    def add_label(self, text: str) -> "UIDropdownMenu":
        """Add a non-interactive group label (small, muted, uppercase).

        QMenu's ``addSection`` is the closest native equivalent — renders as
        a header with a divider above. Good for grouping items: ``"View"`` /
        ``"Account"`` / ``"Help"`` style headings inside one menu.
        """
        self.menu.addSection(text)
        return self

    def add_item(
        self,
        text: str,
        *,
        on_click: Optional[Callable[[], None]] = None,
        shortcut: Optional[str] = None,
        icon: Optional[QIcon] = None,
        disabled: bool = False,
    ) -> QAction:
        """Add a regular menu item. Returns the underlying QAction so callers
        can keep a reference (e.g. to flip ``disabled`` later)."""
        action = QAction(text, self.menu)
        if icon is not None:
            action.setIcon(icon)
        if shortcut:
            # Try to parse as a QKeySequence — falls back to plain text in
            # the right-aligned shortcut column if that fails (e.g. for
            # display-only hints like "⌘0" that aren't real keybindings).
            ks = QKeySequence(shortcut)
            if not ks.isEmpty():
                action.setShortcut(ks)
            else:
                action.setText(f"{text}\t{shortcut}")
        if disabled:
            action.setEnabled(False)
        if on_click is not None:
            action.triggered.connect(lambda checked=False: on_click())
        self.menu.addAction(action)
        return action

    def add_checkable(
        self,
        text: str,
        *,
        checked: bool = False,
        on_toggle: Optional[Callable[[bool], None]] = None,
        shortcut: Optional[str] = None,
    ) -> QAction:
        """Add a checkable item (Radix DropdownMenu.CheckboxItem equivalent).
        The checkmark appears on the left when checked."""
        action = QAction(text, self.menu)
        action.setCheckable(True)
        action.setChecked(checked)
        if shortcut:
            ks = QKeySequence(shortcut)
            if not ks.isEmpty():
                action.setShortcut(ks)
        if on_toggle is not None:
            action.toggled.connect(lambda state: on_toggle(state))
        self.menu.addAction(action)
        return action

    def add_separator(self) -> "UIDropdownMenu":
        """Thin horizontal divider — visually groups adjacent items."""
        self.menu.addSeparator()
        return self

    def add_submenu(self, text: str) -> "UIDropdownMenu":
        """Nest another UIDropdownMenu under this one. Returns the new
        UIDropdownMenu so the caller can keep building items on it."""
        sub = UIDropdownMenu(title=text, parent=self.menu)
        self.menu.addMenu(sub.menu)
        return sub

    # ============================================================ trigger API

    def attach_to_button(self, button: QPushButton) -> "UIDropdownMenu":
        """Wire the menu to a button's click. Click pops the menu below the
        button (Radix DropdownMenu.Root + Trigger + Content shape)."""
        button.clicked.connect(self._popup_below_button(button))
        return self

    def popup_at_global(self, point: QPoint) -> None:
        """Show the menu anchored at a global screen point. Used by
        ``attach_context_menu`` for right-click activation."""
        self.menu.popup(point)

    def popup_at_cursor(self) -> None:
        """Convenience — show the menu where the cursor currently is."""
        self.menu.popup(QCursor.pos())

    # ============================================================ internals

    def _popup_below_button(self, button: QPushButton) -> Callable[[], None]:
        """Return a click handler that pops the menu directly below the button.

        Captured by value so multiple buttons can reuse the same menu safely.
        """
        def _on_click() -> None:
            pos = button.mapToGlobal(button.rect().bottomLeft())
            self.menu.popup(pos)
        return _on_click
