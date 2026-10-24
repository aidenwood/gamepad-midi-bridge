"""FlowLayout — a horizontal row that wraps onto more rows when it has to.

WHY THIS EXISTS
A ``QHBoxLayout`` of buttons reports a minimum width equal to the sum of
every button, so one row of three actions can set the floor for an entire
page: the Bluetooth tab's "Open system Bluetooth settings" + "Re-scan" +
"Connection guide" row demanded 509 px, which made 549 px the narrowest the
whole page could ever be. The page then grew a horizontal scrollbar on a
phone-width window and the user had to scroll sideways to read a paragraph.

Wrapping is the honest fix. Nothing is hidden, nothing moves behind a menu —
the same controls occupy however many rows they need, exactly like the shell
header does at its narrow tiers.

``heightForWidth`` is how a layout tells its parent "give me a width and
I'll tell you how tall I need to be", which is what makes the wrap actually
reserve vertical space instead of clipping the second row.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidgetItem


class FlowLayout(QLayout):
    """Left-to-right layout that wraps to a new line when it runs out of room.

    Args:
        parent:  Optional parent widget.
        margin:  Contents margin applied on all four sides.
        h_space: Horizontal gap between items.
        v_space: Vertical gap between wrapped rows.
    """

    def __init__(self, parent=None, margin: int = 0,
                 h_space: int = 8, v_space: int = 8) -> None:
        super().__init__(parent)
        self._items: list = []
        self._h_space = h_space
        self._v_space = v_space
        self.setContentsMargins(margin, margin, margin, margin)

    # ----------------------------------------------------------- QLayout API

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """The WIDEST SINGLE ITEM, not the sum of them.

        This is the whole point: the row can always fall back to one item
        per line, so it never forces its page wider than its biggest button.
        """
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(),
                            margins.top() + margins.bottom())

    # ----------------------------------------------------------- internals

    def _layout(self, rect: QRect, apply: bool) -> int:
        """Place items left to right, wrapping. Returns the total height."""
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(),
                                  -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            space_x, space_y = self._h_space, self._v_space
            if isinstance(item, QWidgetItem):
                widget = item.widget()
                if widget is not None:
                    style = widget.style()
                    space_x = max(space_x, style.layoutSpacing(
                        QSizePolicy.PushButton, QSizePolicy.PushButton,
                        Qt.Horizontal))
                    space_y = max(space_y, style.layoutSpacing(
                        QSizePolicy.PushButton, QSizePolicy.PushButton,
                        Qt.Vertical))
            next_x = x + hint.width() + space_x
            if next_x - space_x > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + hint.width() + space_x
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()
