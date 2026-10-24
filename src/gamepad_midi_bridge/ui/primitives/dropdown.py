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

#: The objectName the global QSS targets. One definition — call sites use
#: ``style_as_dropdown()`` rather than repeating the string.
DROPDOWN_OBJECT_NAME = "UIDropdownMenu"


def style_as_dropdown(menu: QMenu) -> QMenu:
    """Opt an existing ``QMenu`` into the app's dropdown styling.

    For menus built with raw ``QMenu(...)`` and ``addAction`` rather than this
    module's fluent API. Returns the menu so it can be used inline.

    WHY THIS EXISTS — menu styling consistency, 2026-10-24.
    ``styles.qss`` styles ``QMenu#UIDropdownMenu``, deliberately scoped by
    objectName so the app's dark surface does not leak into native menus we
    do not own (the macOS application menu, the tray right-click menu). Five
    in-app menus were built as bare ``QMenu(self)`` and never set that name,
    so none of that rule applied to them: they fell back to the global
    ``QWidget`` rule and rendered as a plain #0e0f12 box instead of the
    intended #1d2028 elevated card with its border, radius, item padding and
    hover states. Two visual languages for the same control.

    This is COSMETIC — measured, not assumed. Rendering both offscreen against
    the real stylesheet gives styled #1d2028 and bare #0e0f12, both at full
    alpha, so an unstyled menu was never transparent or unreadable.

    Specifically NOT the cause of the see-through menu in the v3 screen
    recording: that frame is a crossfade between the menu closing and the
    Connectors tab opening, and the frames 0.4s either side of it show the menu
    painting solidly. ``WA_TranslucentBackground`` on the 3D chrome does not
    propagate to a QMenu either — checked, the popup reports the attribute
    unset with a translucent parent. Do not "fix" that frame.

    Deliberately NOT applied to the system-tray menu — that one should stay
    native. See the QMenu block in ``styles.qss``.
    """
    menu.setObjectName(DROPDOWN_OBJECT_NAME)
    # Matches UIDropdownMenu: keep explicitly-placed separators where they
    # were put, instead of letting Qt collapse them during macOS menu merging.
    menu.setSeparatorsCollapsible(False)
    return menu


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
        # into native Qt menus we don't own. Shared with every raw-QMenu call
        # site via the same helper, so the two cannot drift — and separators
        # stay where they were put rather than being collapsed by macOS menu
        # merging.
        style_as_dropdown(self.menu)

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
