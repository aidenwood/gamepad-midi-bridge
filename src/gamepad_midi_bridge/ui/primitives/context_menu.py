"""attach_context_menu — Radix-style right-click menu binding.

Lets any QWidget show a UIDropdownMenu on right-click without each call site
re-implementing the boilerplate of ``setContextMenuPolicy(Qt.CustomContextMenu)``
+ ``customContextMenuRequested.connect(...)``.

Two flavours:

    # Static menu — same items every right-click. Builder runs ONCE at attach.
    menu = UIDropdownMenu()
    menu.add_item("Delete", on_click=del_handler)
    attach_context_menu(my_widget, menu)

    # Dynamic menu — builder runs EVERY right-click. Use when items depend on
    # what was clicked (e.g. node graph wire context menu offers different
    # transforms depending on the wire's current inline_transform).
    def build_menu():
        m = UIDropdownMenu()
        m.add_item(f"Delete {selection.name}", on_click=...)
        if selection.has_transform:
            m.add_item("Change transform…", on_click=...)
        return m
    attach_context_menu(my_widget, build_menu)
"""
from __future__ import annotations

from typing import Callable, Union

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QWidget

from .dropdown import UIDropdownMenu


MenuOrBuilder = Union[UIDropdownMenu, Callable[[], UIDropdownMenu]]


def attach_context_menu(widget: QWidget, menu_or_builder: MenuOrBuilder) -> None:
    """Bind a right-click context menu to ``widget``.

    Args:
        widget: target widget. Existing context-menu policy is overwritten.
        menu_or_builder: either a UIDropdownMenu (reused on every right-
            click — fast, items must be static) OR a callable returning a
            fresh UIDropdownMenu (rebuilt per click — slower, items can
            reflect current selection / state).

    Multiple ``attach_context_menu`` calls on the same widget will REPLACE
    the previous handler — the most recent one wins. Disconnect manually
    via ``widget.customContextMenuRequested.disconnect()`` if you need to
    remove without replacing.
    """
    widget.setContextMenuPolicy(Qt.CustomContextMenu)

    if callable(menu_or_builder):
        builder = menu_or_builder

        def _on_request(pos: QPoint) -> None:
            menu = builder()
            menu.popup_at_global(widget.mapToGlobal(pos))
            # Builder-allocated menus must stay alive long enough to be
            # interacted with. Pin to widget as an attribute — replaced on
            # next click, freed when the widget is destroyed.
            widget._last_context_menu = menu  # type: ignore[attr-defined]
    else:
        menu = menu_or_builder

        def _on_request(pos: QPoint) -> None:
            menu.popup_at_global(widget.mapToGlobal(pos))

    # Replace any prior connection (idempotency: re-attaching a menu shouldn't
    # leave the old one wired up too). PySide6 emits a RuntimeWarning when
    # disconnect() finds no receivers — silence it so a fresh attach is clean.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            widget.customContextMenuRequested.disconnect()
        except (RuntimeError, TypeError):
            pass
    widget.customContextMenuRequested.connect(_on_request)
