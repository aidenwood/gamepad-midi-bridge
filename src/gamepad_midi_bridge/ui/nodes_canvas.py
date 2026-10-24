"""Node-graph canvas — read-only QGraphicsScene render of a NodeGraph.

Phase 2.0: visible. Phase 2.1+ adds interaction (drag, drag-to-connect,
context menus, node picker). The data model is fixed; everything here is
presentation. Don't add domain logic — keep transforms / evaluation in
``nodes/`` where the tests live.

Layout:
    ControllerSource cards on the left edge (no inputs, one out pin)
    Node cards in the middle (inputs left, outputs right, category-coloured)
    SymbolicSink cards on the right (one in pin, no outs)
    Cubic bezier WireItems join output → input pins, painted in the
    SOURCE node's category accent so a wire's colour reads "what kind of
    thing is flowing here".

Pan + zoom:
    - Cmd/Ctrl + wheel → zoom (0.25× to 4×, mouse-centred)
    - Trackpad pinch     → zoom (native gesture)
    - Drag empty space   → pan
    - `F` → fit graph to viewport
    - `1` → reset to 100% centred on graph
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from ..nodes import (
    CATEGORIES,
    ControllerSource,
    Node,
    NodeGraph,
    NodeRegistry,
    NodeSpec,
    SymbolicSink,
    category_meta,
)
from . import tokens as T


# ---------------------------------------------------------------------------
# Visual constants — kept in one place so they're easy to tune.
# ---------------------------------------------------------------------------

NODE_WIDTH = 200
NODE_TITLE_H = 30
NODE_PARAM_H = 20
NODE_PAD = 10
NODE_RADIUS = 8

PIN_SIZE = 10
PIN_GAP = 6     # vertical gap between adjacent pins
PIN_OFFSET = 5   # how far the pin centres extend outside the node body

WIRE_WIDTH = 2.0


def _qcolor(token_name: str) -> QColor:
    """Resolve a token name (e.g. 'ACCENT_TEAL') to a QColor via tokens.py.

    Falls back to ``TEXT_MUTED`` if the name is unknown — keeps a typo
    in CategoryMeta.color_token from crashing the render.
    """
    raw = getattr(T, token_name, None) or T.TEXT_MUTED
    return QColor(raw)


def _category_color(category: str) -> QColor:
    meta = category_meta(category)
    return _qcolor(meta.color_token) if meta else _qcolor("TEXT_MUTED")


# ---------------------------------------------------------------------------
# PinItem — small circle at the edge of a node, anchors wires.
# ---------------------------------------------------------------------------

class PinItem(QGraphicsObject):
    """One input or output pin. Position is relative to the parent NodeItem.

    Mouse-press on an OUTPUT pin starts a drag-to-connect interaction:
    the scene shows a rubber-band bezier following the cursor, and on
    release tries to drop on a compatible INPUT pin. Press on an input
    pin is a no-op (you always wire from output → input).
    """

    def __init__(
        self,
        *,
        parent_node: "NodeItem | BoundaryItem",
        pin_name: str,
        direction: str,
        accent: QColor,
    ) -> None:
        super().__init__(parent_node)
        self._pin_name = pin_name
        self._direction = direction   # "in" | "out"
        self._accent = accent
        self.setAcceptHoverEvents(True)
        self._hover = False
        # Eat clicks here so they don't propagate to the parent node's
        # drag-to-move handler. Without this, mousePress on a pin would
        # start dragging the whole node card around.
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    @property
    def pin_name(self) -> str:
        return self._pin_name

    @property
    def direction(self) -> str:
        return self._direction

    def boundingRect(self) -> QRectF:
        # A touch larger than the visible dot so hover hit-testing isn't pixel-perfect.
        return QRectF(-PIN_SIZE / 2 - 2, -PIN_SIZE / 2 - 2, PIN_SIZE + 4, PIN_SIZE + 4)

    def set_snap_target(self, on: bool) -> None:
        """Toggle the "drop-target glow" rendered while a wire drag is near.

        The scene calls this on every mouseMove during a drag — input pins
        within the snap radius receive ``True``, everyone else ``False``.
        Cheap repaint; only changes when the state actually flips.
        """
        if on != getattr(self, "_snap_target", False):
            self._snap_target = on
            self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        active = self._hover or getattr(self, "_snap_target", False)
        fill = self._accent if active else _qcolor("BG_ELEVATED")
        border = self._accent
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 1.5))
        # Snap-target state draws a soft outer ring so the user gets a
        # clear "drop here" affordance even before the cursor lands on
        # the pin itself.
        if getattr(self, "_snap_target", False):
            ring_pen = QPen(self._accent)
            ring_pen.setWidthF(1.2)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), PIN_SIZE / 2 + 4, PIN_SIZE / 2 + 4)
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(border, 1.5))
        painter.drawEllipse(QPointF(0, 0), PIN_SIZE / 2, PIN_SIZE / 2)

    # Hover feedback so drag-to-connect has a visible target.
    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """Click-to-click wiring (TouchDesigner style):

        - Left-click an OUTPUT pin → start a pending wire that follows the
          cursor without the mouse being held. Click on the SAME output
          again cancels.
        - Left-click an INPUT pin while pending → commit the connection.
        - Click an output pin while pending from a DIFFERENT output → re-
          anchor the pending wire to this new source.

        Always accepts the event so the parent node's drag-to-move doesn't
        steal it.
        """
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        scene = self.scene()
        if not isinstance(scene, NodeGraphScene):
            event.accept()
            return

        if self._direction == "out":
            # Output click — start, restart, or cancel pending.
            if scene._pending_source is self:
                scene._cancel_wire_drag()
            else:
                scene._begin_wire_drag(self, event.scenePos())
        else:
            # Input click — commit if there's a pending wire.
            if scene._pending_source is not None:
                scene._end_wire_drag(self.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        # Click-to-click flow: release does nothing — the pending wire stays
        # alive across press→release until a second click commits or cancels.
        event.accept()


# ---------------------------------------------------------------------------
# NodeItem — rectangular card representing a Node on the canvas.
# ---------------------------------------------------------------------------

class NodeItem(QGraphicsObject):
    """A single Node rendered as a card. Reads its NodeSpec from the registry.

    Layout (top → bottom):
        title bar  — category dot + label text, height NODE_TITLE_H
        param rows — one per ParamSpec, height NODE_PARAM_H each
        bottom pad — NODE_PAD
    """

    def __init__(self, *, node: Node, spec: NodeSpec) -> None:
        super().__init__()
        self._node = node
        self._spec = spec
        self._accent = _category_color(spec.category)
        self.setPos(QPointF(*node.position))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        # ItemSendsGeometryChanges fires itemChange on every move — needed so
        # we can write the position back into Node.position (for save-round-
        # trip) and tell the scene to redraw any wires touching this node.
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        # Position children deterministically — pins live in scene coords
        # relative to this item via their own setPos calls.
        self._pins_in: Dict[str, PinItem] = {}
        self._pins_out: Dict[str, PinItem] = {}
        self._build_pins()

    # ----- geometry

    def _content_height(self) -> float:
        return NODE_TITLE_H + max(0, len(self._spec.params)) * NODE_PARAM_H + NODE_PAD

    def boundingRect(self) -> QRectF:
        # Extend the rect outwards by PIN_OFFSET so pin halos aren't clipped.
        return QRectF(
            -PIN_OFFSET, 0,
            NODE_WIDTH + 2 * PIN_OFFSET, self._content_height(),
        )

    # ----- pins

    def _build_pins(self) -> None:
        # Inputs on the left edge, vertically distributed below the title.
        y_in = NODE_TITLE_H + NODE_PARAM_H / 2
        for spec_pin in self._spec.inputs:
            pin = PinItem(parent_node=self, pin_name=spec_pin.name,
                          direction="in", accent=self._accent)
            pin.setPos(0, y_in)
            self._pins_in[spec_pin.name] = pin
            y_in += NODE_PARAM_H + PIN_GAP
        # Outputs on the right edge, similarly distributed.
        y_out = NODE_TITLE_H + NODE_PARAM_H / 2
        for spec_pin in self._spec.outputs:
            pin = PinItem(parent_node=self, pin_name=spec_pin.name,
                          direction="out", accent=self._accent)
            pin.setPos(NODE_WIDTH, y_out)
            self._pins_out[spec_pin.name] = pin
            y_out += NODE_PARAM_H + PIN_GAP

    def input_pin(self, name: str) -> Optional[PinItem]:
        return self._pins_in.get(name)

    def output_pin(self, name: str) -> Optional[PinItem]:
        return self._pins_out.get(name)

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionHasChanged:
            # Write the new position back into the data model so it survives
            # a save → load round-trip. Tell the scene to refresh wires that
            # anchor on any of our pins.
            self._node.position = (float(value.x()), float(value.y()))
            scene = self.scene()
            if isinstance(scene, NodeGraphScene):
                scene._refresh_wires_for(self)
        return super().itemChange(change, value)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        scene = self.scene()
        if not isinstance(scene, NodeGraphScene):
            return
        menu = build_node_menu(self, scene)
        menu.popup_at_global(event.screenPos())
        scene._last_menu = menu

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        # Fast path to the param editor — matches the canvas conventions
        # of Figma / Blender where double-click "enters" the item.
        scene = self.scene()
        if isinstance(scene, NodeGraphScene):
            _open_param_editor(self, scene)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        # Position writeback happens in itemChange on every move; we only
        # tell the auto-save path ONCE per drag, on release. Avoids the
        # save-storm of firing on every pixel of cursor movement.
        scene = self.scene()
        if isinstance(scene, NodeGraphScene) and event.button() == Qt.LeftButton:
            scene.graph_changed.emit()
        super().mouseReleaseEvent(event)

    # ----- painting

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        body_rect = QRectF(0, 0, NODE_WIDTH, self._content_height())

        # Card surface + border
        painter.setBrush(QBrush(_qcolor("BG_ELEVATED")))
        painter.setPen(QPen(_qcolor("BORDER_SUBTLE"), 1))
        painter.drawRoundedRect(body_rect, NODE_RADIUS, NODE_RADIUS)

        # Left-edge category accent stripe — 3px coloured bar so the user
        # sees the node's category at a glance even when zoomed out.
        accent_rect = QRectF(0, 0, 3, self._content_height())
        painter.setBrush(QBrush(self._accent))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(accent_rect, 1.5, 1.5)

        # Title bar
        title_font = QFont()
        title_font.setPixelSize(T.FS_M)
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QPen(_qcolor("TEXT_PRIMARY")))
        painter.drawText(
            QRectF(NODE_PAD + 6, 0, NODE_WIDTH - NODE_PAD - 12, NODE_TITLE_H),
            Qt.AlignVCenter | Qt.AlignLeft,
            self._spec.label,
        )

        # Param rows — read-only key/value display for now.
        param_font = QFont()
        param_font.setPixelSize(T.FS_S)
        painter.setFont(param_font)
        for i, ps in enumerate(self._spec.params):
            row_y = NODE_TITLE_H + i * NODE_PARAM_H
            painter.setPen(QPen(_qcolor("TEXT_MUTED")))
            painter.drawText(
                QRectF(NODE_PAD, row_y, NODE_WIDTH / 2 - 6, NODE_PARAM_H),
                Qt.AlignVCenter | Qt.AlignLeft, ps.name,
            )
            value = self._node.params.get(ps.name, ps.default)
            painter.setPen(QPen(_qcolor("TEXT_SECONDARY")))
            painter.drawText(
                QRectF(NODE_WIDTH / 2, row_y, NODE_WIDTH / 2 - NODE_PAD, NODE_PARAM_H),
                Qt.AlignVCenter | Qt.AlignRight, str(value),
            )


# ---------------------------------------------------------------------------
# BoundaryItem — simpler card for ControllerSource (left) / SymbolicSink (right).
# ---------------------------------------------------------------------------

class BoundaryItem(QGraphicsObject):
    """Render a graph boundary (source or sink) as a smaller card.

    Sources have one ``out`` pin on the right; sinks have one ``in`` pin
    on the left. The visual is intentionally lighter than a NodeItem so
    the eye reads them as I/O, not processing.
    """

    BOUNDARY_HEIGHT = 50

    def __init__(self, *, boundary, role: str) -> None:
        super().__init__()
        self._b = boundary
        self._role = role          # "source" | "sink"
        self._accent = _qcolor(
            "ACCENT_TEAL" if role == "source" else "ACCENT_CORAL"
        )
        self.setPos(QPointF(*boundary.position))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # Single pin on the appropriate edge.
        self.pin = PinItem(
            parent_node=self,
            pin_name="out" if role == "source" else "in",
            direction="out" if role == "source" else "in",
            accent=self._accent,
        )
        if role == "source":
            self.pin.setPos(NODE_WIDTH, self.BOUNDARY_HEIGHT / 2)
        else:
            self.pin.setPos(0, self.BOUNDARY_HEIGHT / 2)

    def boundingRect(self) -> QRectF:
        return QRectF(-PIN_OFFSET, 0, NODE_WIDTH + 2 * PIN_OFFSET, self.BOUNDARY_HEIGHT)

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._b.position = (float(value.x()), float(value.y()))
            scene = self.scene()
            if isinstance(scene, NodeGraphScene):
                scene._refresh_wires_for(self)
        return super().itemChange(change, value)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        """Right-click menu — sinks get Edit target / Delete; sources get
        Rename / Delete (kind stays bound to hardware)."""
        scene = self.scene()
        if not isinstance(scene, NodeGraphScene):
            return
        if self._role == "sink":
            menu = build_sink_menu(self, scene)
        else:
            menu = build_source_menu(self, scene)
        menu.popup_at_global(event.screenPos())
        scene._last_menu = menu

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        # Mirror of NodeItem.mouseReleaseEvent — save layout on drag-end
        # without firing on every intermediate move.
        scene = self.scene()
        if isinstance(scene, NodeGraphScene) and event.button() == Qt.LeftButton:
            scene.graph_changed.emit()
        super().mouseReleaseEvent(event)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        body = QRectF(0, 0, NODE_WIDTH, self.BOUNDARY_HEIGHT)
        painter.setBrush(QBrush(_qcolor("BG_SURFACE")))
        painter.setPen(QPen(self._accent, 1.5))
        painter.drawRoundedRect(body, NODE_RADIUS, NODE_RADIUS)

        # Role chip in the corner
        role_font = QFont()
        role_font.setPixelSize(T.FS_XS)
        role_font.setWeight(QFont.Bold)
        painter.setFont(role_font)
        painter.setPen(QPen(self._accent))
        chip = QRectF(NODE_PAD, 6, 60, 14)
        painter.drawText(chip, Qt.AlignVCenter | Qt.AlignLeft, self._role.upper())

        # Label + symbol/kind underneath
        label = getattr(self._b, "label", "") or self._role
        title_font = QFont()
        title_font.setPixelSize(T.FS_M)
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QPen(_qcolor("TEXT_PRIMARY")))
        painter.drawText(
            QRectF(NODE_PAD, 20, NODE_WIDTH - 2 * NODE_PAD, 18),
            Qt.AlignLeft | Qt.AlignVCenter, label,
        )


# ---------------------------------------------------------------------------
# WireItem — bezier between two pins. Self-updates when endpoints move.
# ---------------------------------------------------------------------------

class WireChipItem(QGraphicsObject):
    """Tiny clickable circle pinned at the wire's bezier midpoint.

    Visible when:
        - the wire's underlying Connection has an inline_transform (so the
          user can see at a glance "this wire is doing something")
        - OR the wire is being hovered (transient affordance hint)

    Click opens the same wire menu the right-click route uses (delete +
    inline-transform picker). Lives at zValue +1 so it sits above the
    wire stroke but below node cards.
    """
    CHIP_RADIUS = 7

    def __init__(self, parent_wire: "WireItem") -> None:
        super().__init__(parent_wire)
        self._wire = parent_wire
        self._visible = False
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.setVisible(False)

    def boundingRect(self) -> QRectF:
        r = self.CHIP_RADIUS + 2
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        # Two-tone: filled with wire accent if a transform IS applied, else
        # outline-only so an empty chip reads as "click to add a transform".
        scene = self._wire.scene()
        has_transform = False
        if isinstance(scene, NodeGraphScene) and scene._graph is not None:
            f_id = scene._endpoint_id(self._wire._from)
            t_id = scene._endpoint_id(self._wire._to)
            for c in scene._graph.connections:
                if (c.from_node == f_id and c.from_pin == self._wire._from.pin_name
                        and c.to_node == t_id and c.to_pin == self._wire._to.pin_name):
                    has_transform = c.inline_transform is not None
                    break
        accent = self._wire._from._accent
        bg = _qcolor("BG_ELEVATED")
        if has_transform:
            painter.setBrush(QBrush(accent))
            painter.setPen(QPen(accent, 1.2))
        else:
            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(accent, 1.2))
        painter.drawEllipse(QPointF(0, 0), self.CHIP_RADIUS, self.CHIP_RADIUS)
        # Tiny gear glyph — three vertical dots so it reads as a menu
        # control without needing a real SVG icon shipped.
        painter.setPen(QPen(accent if not has_transform else _qcolor("BG_BASE"), 1.4))
        painter.drawPoint(QPointF(0, -2.5))
        painter.drawPoint(QPointF(0, 0))
        painter.drawPoint(QPointF(0, 2.5))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        scene = self._wire.scene()
        if not isinstance(scene, NodeGraphScene):
            event.accept()
            return
        menu = build_wire_menu(self._wire, scene)
        menu.popup_at_global(event.screenPos())
        scene._last_menu = menu
        event.accept()


class WireItem(QGraphicsPathItem):
    """Cubic bezier connecting one PinItem to another.

    Path is recomputed whenever ``update_path`` is called. The view
    invokes it after every node move so wires track positions. Wire
    colour comes from the SOURCE pin's accent so the colour tells the
    user "what kind of value is flowing along this wire".

    `_active` reflects whether a controller source upstream is currently
    emitting non-zero signal. The scene maintains this — set_active() to
    light a wire, decays via the NodesTab's poll timer.
    """

    def __init__(self, *, from_pin: PinItem, to_pin: PinItem) -> None:
        super().__init__()
        self._from = from_pin
        self._to = to_pin
        self._active = False
        self.setZValue(-1)        # always paint behind nodes
        # Accept hover + clicks so contextMenuEvent fires when the user
        # right-clicks the wire path (not just the empty canvas around it).
        self.setAcceptHoverEvents(True)
        self._idle_pen = QPen(from_pin._accent, WIRE_WIDTH)
        self._idle_pen.setCapStyle(Qt.RoundCap)
        # Brighter + thicker pen for the active state. We compute it once
        # at construction time so the paint hot path doesn't re-allocate.
        bright = QColor(from_pin._accent)
        bright = bright.lighter(150)   # 50% brighter
        self._active_pen = QPen(bright, WIRE_WIDTH + 1.5)
        self._active_pen.setCapStyle(Qt.RoundCap)
        self.setPen(self._idle_pen)
        # Midpoint chip — visibility driven by hover + presence of an
        # inline transform on the underlying Connection.
        self._chip = WireChipItem(self)
        self.update_path()
        self._refresh_chip_visibility()

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        self.setPen(self._active_pen if active else self._idle_pen)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        """Build + show the wire menu (Delete + inline-transform picker).

        Dispatch to a free function in this module so the menu shape is
        easy to test in isolation without instantiating a real Qt event.
        """
        scene = self.scene()
        if not isinstance(scene, NodeGraphScene):
            return
        from .primitives import UIDropdownMenu
        menu = build_wire_menu(self, scene)
        menu.popup_at_global(event.screenPos())
        # Pin the menu to the scene so it doesn't get GC'd before the
        # user clicks something.
        scene._last_menu = menu

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        # Hover composes on top of active state: clone the appropriate base
        # pen and bump its width by the hover delta. Both idle and active
        # paths keep their colour, just gain visual weight.
        base = self._active_pen if self._active else self._idle_pen
        pen = QPen(base)
        pen.setWidthF(pen.widthF() + 1.5)
        self.setPen(pen)
        # Show the chip while the user is hovering even if no transform
        # is applied — "click here to add one" affordance.
        self._chip.setVisible(True)
        self._chip.update()

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        # Restore whichever base pen is correct for our current activity.
        self.setPen(self._active_pen if self._active else self._idle_pen)
        # When the cursor leaves, hide the chip UNLESS the wire actually
        # has an inline transform — those stay visible as a permanent
        # "this wire is doing something" badge.
        self._refresh_chip_visibility()

    def _refresh_chip_visibility(self) -> None:
        """Idle visibility — show the chip iff the wire has an inline
        transform. Hover state overrides this when active."""
        scene = self.scene()
        if not isinstance(scene, NodeGraphScene) or scene._graph is None:
            self._chip.setVisible(False)
            return
        f_id = scene._endpoint_id(self._from)
        t_id = scene._endpoint_id(self._to)
        has_transform = False
        for c in scene._graph.connections:
            if (c.from_node == f_id and c.from_pin == self._from.pin_name
                    and c.to_node == t_id and c.to_pin == self._to.pin_name):
                has_transform = c.inline_transform is not None
                break
        self._chip.setVisible(has_transform)
        self._chip.update()

    def update_path(self) -> None:
        a = self._from.scenePos()
        b = self._to.scenePos()
        # Horizontal-tangent cubic. dx controls how "loose" the curve hangs;
        # half the horizontal distance feels natural and matches TouchDesigner.
        dx = max(40.0, abs(b.x() - a.x()) * 0.5)
        path = QPainterPath(a)
        path.cubicTo(a.x() + dx, a.y(), b.x() - dx, b.y(), b.x(), b.y())
        self.setPath(path)
        # Pin the midpoint chip — pointAtPercent walks the path's arc length,
        # which feels right (matches TD-style "label the wire halfway along").
        if hasattr(self, "_chip"):
            mid = path.pointAtPercent(0.5)
            self._chip.setPos(mid)


# ---------------------------------------------------------------------------
# Scene + View
# ---------------------------------------------------------------------------

class NodeGraphScene(QGraphicsScene):
    """Holds the items for one NodeGraph render. Reusable: call
    ``load_graph(...)`` with a different graph to swap contents.

    Keeps a live reference to the loaded ``NodeGraph`` and ``NodeRegistry``
    so right-click context menus on the canvas can mutate the model in
    place (add node, delete wire, change inline transform) without going
    back through MainWindow → Mapping → reload.

    Emits ``graph_changed`` after every mutation so a parent widget
    (NodesTab) can persist the underlying Mapping to disk. Loading a
    graph does NOT emit (so a fresh load doesn't re-save what we just
    read).
    """

    graph_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setBackgroundBrush(QBrush(_qcolor("BG_BASE")))
        self._node_items: Dict[str, NodeItem] = {}
        self._boundary_items: Dict[str, BoundaryItem] = {}
        self._wires: list = []
        self._graph: Optional[NodeGraph] = None
        self._registry: Optional[NodeRegistry] = None
        # Drag-to-connect transient state. _pending_source is the OUTPUT
        # PinItem the user is dragging from; _pending_wire is the temp
        # rubber-band QGraphicsPathItem on the scene.
        self._pending_source: Optional[PinItem] = None
        self._pending_wire: Optional[QGraphicsPathItem] = None

    def load_graph(self, graph: NodeGraph, registry: NodeRegistry) -> None:
        """Clear and rebuild the scene from `graph`.

        Items are positioned from each entity's ``position`` field. If the
        graph was loaded from an old-shape preset that didn't include
        positions, every item lands at (0, 0) and the user can rearrange.
        """
        self.clear()
        self._node_items.clear()
        self._boundary_items.clear()
        self._wires = []
        # Reverse index used by drag updates: which wires anchor on each
        # NodeItem / BoundaryItem? Rebuilt below as we wire endpoints.
        self._wires_by_endpoint: Dict[int, list] = {}
        # Live references for in-place mutation via right-click menus.
        self._graph = graph
        self._registry = registry

        for src_id, src in graph.sources.items():
            item = BoundaryItem(boundary=src, role="source")
            self.addItem(item)
            self._boundary_items[src_id] = item

        for sink_id, sink in graph.sinks.items():
            item = BoundaryItem(boundary=sink, role="sink")
            self.addItem(item)
            self._boundary_items[sink_id] = item

        for node_id, node in graph.nodes.items():
            spec = registry.get(node.kind)
            if spec is None:
                continue
            item = NodeItem(node=node, spec=spec)
            self.addItem(item)
            self._node_items[node_id] = item

        for conn in graph.connections:
            from_pin = self._resolve_out_pin(conn.from_node, conn.from_pin)
            to_pin = self._resolve_in_pin(conn.to_node, conn.to_pin)
            if from_pin is None or to_pin is None:
                continue
            wire = WireItem(from_pin=from_pin, to_pin=to_pin)
            self.addItem(wire)
            self._wires.append(wire)
            # The chip's initial visibility needs the wire to already be on
            # a scene — refresh once now that addItem has wired self.scene().
            wire._refresh_chip_visibility()
            # Index this wire under both endpoint items so a drag on either
            # one triggers a single repath. id() because graphics items don't
            # hash by value.
            for endpoint in (from_pin.parentItem(), to_pin.parentItem()):
                if endpoint is None:
                    continue
                self._wires_by_endpoint.setdefault(id(endpoint), []).append(wire)

    # ----- in-place mutation (called by context-menu actions)

    def delete_node(self, node_id: str) -> None:
        """Remove a Node from the graph + scene, and drop every Connection
        that referenced it. Idempotent: deleting a missing node is a no-op.

        Order matters: collect affected wires + drop connections WHILE the
        item is still in ``_node_items`` so ``_endpoint_id`` can resolve. If
        we popped the item first, ``_endpoint_id`` would return None for
        every wire touching this node and the connections would leak.
        """
        if self._graph is None or node_id not in self._node_items:
            return
        # 1. Find wires that anchor on this node (using the still-present item).
        affected_wires = [
            w for w in list(self._wires)
            if self._endpoint_id(w._from) == node_id
            or self._endpoint_id(w._to) == node_id
        ]
        # 2. Drop matching connections directly — by node_id, not via the
        # wire-based delete path which would need _endpoint_id to still resolve.
        self._graph.connections = [
            c for c in self._graph.connections
            if c.from_node != node_id and c.to_node != node_id
        ]
        # 3. Remove the wire visuals + reverse-index entries.
        for w in affected_wires:
            self.removeItem(w)
            if w in self._wires:
                self._wires.remove(w)
            for key, wires in list(self._wires_by_endpoint.items()):
                if w in wires:
                    wires.remove(w)
        # 4. Drop the node visual + data + bookkeeping.
        item = self._node_items.pop(node_id)
        self._graph.nodes.pop(node_id, None)
        self.removeItem(item)
        self.graph_changed.emit()

    def reset_node_params(self, node_id: str) -> None:
        """Reset every param on the named node to its NodeSpec default."""
        if self._graph is None or self._registry is None:
            return
        node = self._graph.nodes.get(node_id)
        if node is None:
            return
        spec = self._registry.get(node.kind)
        if spec is None:
            return
        node.params = spec.default_params()
        item = self._node_items.get(node_id)
        if item is not None:
            item.update()  # repaint the param-rows display
        self.graph_changed.emit()

    def edit_source(self, source_id: str, *, label: Optional[str] = None) -> None:
        """Rename a controller source (kind + index stay tied to hardware).

        Sources are read from controller surfaces — changing the kind would
        re-bind to different physical input. Only the display label is
        editable from the UI; if you want a different kind, delete this
        source and Add Input a new one.
        """
        if self._graph is None:
            return
        src = self._graph.sources.get(source_id)
        if src is None or label is None:
            return
        src.label = label
        item = self._boundary_items.get(source_id)
        if item is not None:
            item.update()
        self.graph_changed.emit()

    def delete_source(self, source_id: str) -> None:
        """Remove a controller source + every connection touching it.

        Idempotent. The seed function will only re-add the default set if
        the graph has ZERO sources, so a user who deletes selectively
        doesn't get their picks overwritten on next load.
        """
        if self._graph is None or source_id not in self._boundary_items:
            return
        affected_wires = [
            w for w in list(self._wires)
            if self._endpoint_id(w._from) == source_id
            or self._endpoint_id(w._to) == source_id
        ]
        self._graph.connections = [
            c for c in self._graph.connections
            if c.from_node != source_id and c.to_node != source_id
        ]
        for w in affected_wires:
            self.removeItem(w)
            if w in self._wires:
                self._wires.remove(w)
            for key, wires in list(self._wires_by_endpoint.items()):
                if w in wires:
                    wires.remove(w)
        item = self._boundary_items.pop(source_id)
        self._graph.sources.pop(source_id, None)
        self.removeItem(item)
        self.graph_changed.emit()

    def edit_sink(self, sink_id: str, *,
                  symbol: Optional[str] = None,
                  label: Optional[str] = None) -> None:
        """Mutate a sink's symbolic target and/or display label in place.

        Repaints just the touched BoundaryItem so the new label shows up
        without a full graph reload. Wires keep their endpoints — the
        sink's pin reference doesn't change.
        """
        if self._graph is None:
            return
        sink = self._graph.sinks.get(sink_id)
        if sink is None:
            return
        if symbol is not None:
            sink.symbol = symbol
        if label is not None:
            sink.label = label
        item = self._boundary_items.get(sink_id)
        if item is not None:
            item.update()
        self.graph_changed.emit()

    def delete_sink(self, sink_id: str) -> None:
        """Remove a sink + every connection touching it. Idempotent."""
        if self._graph is None or sink_id not in self._boundary_items:
            return
        affected_wires = [
            w for w in list(self._wires)
            if self._endpoint_id(w._from) == sink_id
            or self._endpoint_id(w._to) == sink_id
        ]
        self._graph.connections = [
            c for c in self._graph.connections
            if c.from_node != sink_id and c.to_node != sink_id
        ]
        for w in affected_wires:
            self.removeItem(w)
            if w in self._wires:
                self._wires.remove(w)
            for key, wires in list(self._wires_by_endpoint.items()):
                if w in wires:
                    wires.remove(w)
        item = self._boundary_items.pop(sink_id)
        self._graph.sinks.pop(sink_id, None)
        self.removeItem(item)
        self.graph_changed.emit()

    def add_source(self, kind: str, index: int, label: str,
                   scene_pos: QPointF) -> Optional["BoundaryItem"]:
        """Append a new ControllerSource and render it on the canvas.

        Used by the "Add Input" picker so the user can add extra sources
        on top of the default seeded set (e.g. another individual axis,
        a button that wasn't in the default 8). The seed function only
        runs when the graph has ZERO sources — new ones go through here.
        """
        if self._graph is None:
            return None
        import uuid
        src_id = f"src_{uuid.uuid4().hex[:10]}"
        source = ControllerSource(
            id=src_id, kind=kind, index=index, label=label,  # type: ignore[arg-type]
            position=(scene_pos.x(), scene_pos.y()),
        )
        self._graph.sources[src_id] = source
        item = BoundaryItem(boundary=source, role="source")
        self.addItem(item)
        self._boundary_items[src_id] = item
        self.graph_changed.emit()
        return item

    def add_sink(self, symbol: str, scene_pos: QPointF,
                 label: Optional[str] = None) -> Optional["BoundaryItem"]:
        """Append a new SymbolicSink with `symbol` at `scene_pos`.

        Used by the right-click "Add Output" picker. The symbol is the
        same format the bridge expects on emit (``midi.cc:7@ch:1``,
        ``midi.note:60@ch:1``, ``resolume.layer:1.opacity``). Sinks get a
        slug id so they round-trip cleanly.
        """
        if self._graph is None:
            return None
        import uuid
        sink_id = f"k_{uuid.uuid4().hex[:10]}"
        sink = SymbolicSink(
            id=sink_id,
            symbol=symbol,
            label=label or symbol,
            position=(scene_pos.x(), scene_pos.y()),
        )
        self._graph.sinks[sink_id] = sink
        item = BoundaryItem(boundary=sink, role="sink")
        self.addItem(item)
        self._boundary_items[sink_id] = item
        self.graph_changed.emit()
        return item

    def add_node(self, kind: str, scene_pos: QPointF) -> Optional["NodeItem"]:
        """Insert a new Node of `kind` at `scene_pos` and render it.

        Returns the NodeItem on success, None if `kind` isn't in the
        registry. Caller (the picker) is responsible for picking a stable
        node id — we use uuid hex so collisions are essentially impossible.
        """
        if self._graph is None or self._registry is None:
            return None
        spec = self._registry.get(kind)
        if spec is None:
            return None
        import uuid
        node_id = f"n_{uuid.uuid4().hex[:10]}"
        node = Node(
            id=node_id, kind=kind,
            params=spec.default_params(),
            position=(scene_pos.x(), scene_pos.y()),
        )
        self._graph.nodes[node_id] = node
        item = NodeItem(node=node, spec=spec)
        self.addItem(item)
        self._node_items[node_id] = item
        self.graph_changed.emit()
        return item

    def add_template(self, template_id: str, scene_pos: QPointF) -> bool:
        """Drop a starter sub-graph at `scene_pos`. True if anything landed.

        Rebuilds the whole scene afterwards rather than adding items one by
        one: a template brings sources, nodes, sinks and wires at once, and
        load_graph already knows how to render all four from positions. The
        merge itself is additive, so existing work on the canvas survives.
        """
        if self._graph is None or self._registry is None:
            return False
        from ..nodes import templates as node_templates
        template = node_templates.get(template_id)
        if template is None:
            return False
        node_templates.apply_to(
            self._graph, template, (scene_pos.x(), scene_pos.y()),
        )
        self.load_graph(self._graph, self._registry)
        self.graph_changed.emit()
        return True

    def delete_wire(self, wire: "WireItem") -> None:
        """Remove a wire from both the scene and the underlying NodeGraph.

        Looks up the matching Connection by (from_node_id, from_pin, to_node_id,
        to_pin) — fast enough at the connection counts we expect (graphs of
        50+ nodes are already unwieldy). Idempotent: removing a wire that's
        already gone is a no-op.
        """
        if self._graph is None:
            return
        if wire not in self._wires:
            return
        # Identify endpoints by traversing the pin → parent → node id chain.
        from_node_id = self._endpoint_id(wire._from)
        to_node_id = self._endpoint_id(wire._to)
        if from_node_id is None or to_node_id is None:
            return
        # Drop the matching Connection from the graph data.
        self._graph.connections = [
            c for c in self._graph.connections
            if not (
                c.from_node == from_node_id and c.from_pin == wire._from.pin_name
                and c.to_node == to_node_id and c.to_pin == wire._to.pin_name
            )
        ]
        # Drop the visual + reverse-index entries.
        self.removeItem(wire)
        self._wires.remove(wire)
        for key, wires in list(self._wires_by_endpoint.items()):
            if wire in wires:
                wires.remove(wire)
        self.graph_changed.emit()

    def _refresh_chip_for(self, wire: "WireItem") -> None:
        """After mutating a connection's inline_transform, ask the wire to
        update its midpoint chip's visibility + colour."""
        wire._refresh_chip_visibility()

    def set_wire_inline_transform(
        self,
        wire: "WireItem",
        transform_kind: Optional[str],
        transform_params: Optional[Dict] = None,
    ) -> None:
        """Set (or clear, by passing kind=None) the inline transform on a wire.

        Phase 1 inline transforms reuse wire-eligible NodeSpecs — see
        ``NodeRegistry.wire_eligible``. The transform is applied to the
        value as it travels from source pin to destination pin.
        """
        if self._graph is None:
            return
        from_node_id = self._endpoint_id(wire._from)
        to_node_id = self._endpoint_id(wire._to)
        if from_node_id is None or to_node_id is None:
            return
        for c in self._graph.connections:
            if (
                c.from_node == from_node_id and c.from_pin == wire._from.pin_name
                and c.to_node == to_node_id and c.to_pin == wire._to.pin_name
            ):
                if transform_kind is None:
                    c.inline_transform = None
                else:
                    from ..nodes import InlineTransform
                    c.inline_transform = InlineTransform(
                        kind=transform_kind,
                        params=dict(transform_params or {}),
                    )
                self._refresh_chip_for(wire)
                self.graph_changed.emit()
                return

    def _endpoint_id(self, pin: "PinItem") -> Optional[str]:
        """Resolve a pin → its parent's id string in the graph data."""
        parent = pin.parentItem()
        for nid, item in self._node_items.items():
            if item is parent:
                return nid
        for bid, item in self._boundary_items.items():
            if item is parent:
                return bid
        return None

    # ----- live signal flow

    def set_active_sources(self, active_source_ids) -> None:
        """Mark every wire downstream of an active source as active.

        Reachability walk: BFS from each source, marking wires we traverse.
        ``active_source_ids`` is the set of ControllerSource ids whose live
        controller value is currently non-zero. Wires not reachable from any
        active source go idle.

        Cheap enough to run every poll tick — typical graphs are <100 nodes
        and the visit set keeps work linear in #edges per source.
        """
        if self._graph is None:
            for w in self._wires:
                w.set_active(False)
            return
        active = set(active_source_ids) if active_source_ids else set()
        if not active:
            for w in self._wires:
                w.set_active(False)
            return
        # Adjacency: from each (source-OR-node) id, list of wires leaving it.
        outgoing: Dict[str, list] = {}
        for w in self._wires:
            f_id = self._endpoint_id(w._from)
            if f_id is None:
                continue
            outgoing.setdefault(f_id, []).append(w)
        # BFS forward from each active source.
        live_wires = set()
        frontier = list(active)
        visited = set(active)
        while frontier:
            node_id = frontier.pop()
            for w in outgoing.get(node_id, ()):
                if w in live_wires:
                    continue
                live_wires.add(w)
                # Continue the walk through node items (not boundaries) so
                # the chain propagates: source → node → node → sink.
                to_id = self._endpoint_id(w._to)
                if to_id is not None and to_id not in visited:
                    visited.add(to_id)
                    frontier.append(to_id)
        for w in self._wires:
            w.set_active(w in live_wires)

    # ----- drag updates

    def _refresh_wires_for(self, endpoint_item) -> None:
        """Recompute paths for every WireItem anchored on `endpoint_item`.

        Called by NodeItem / BoundaryItem.itemChange when they move. O(W)
        where W is the wire count touching this one item — typically 1-4
        per drag tick, well under any perceivable cost.
        """
        wires = self._wires_by_endpoint.get(id(endpoint_item), ())
        for wire in wires:
            wire.update_path()

    # ----- drag-to-connect

    def _cancel_wire_drag(self) -> None:
        """Drop the pending wire without committing. Called from clicks on
        empty canvas, Esc keystrokes, and same-source re-clicks."""
        if self._pending_wire is not None:
            self.removeItem(self._pending_wire)
        self._pending_source = None
        self._pending_wire = None
        for item in self.items():
            if isinstance(item, PinItem) and item._direction == "in":
                item.set_snap_target(False)

    def _begin_wire_drag(self, source: "PinItem", scene_pos: QPointF) -> None:
        """Click on an output pin — start (or re-anchor) the pending wire."""
        # Clean up any prior pending state so re-anchoring from a different
        # output doesn't leak the previous temp wire.
        if self._pending_wire is not None:
            self.removeItem(self._pending_wire)
            self._pending_wire = None
        self._pending_source = source
        path_item = QGraphicsPathItem()
        pen = QPen(source._accent, WIRE_WIDTH, Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        path_item.setPen(pen)
        path_item.setZValue(-1)
        self.addItem(path_item)
        self._pending_wire = path_item
        self._update_wire_drag(scene_pos)

    # Snap radius — input pins within this distance from the cursor glow
    # as valid drop targets. Generous enough that a fast drag still snaps.
    _WIRE_SNAP_RADIUS = 28.0

    def _update_wire_drag(self, scene_pos: QPointF) -> None:
        """Called on each mouseMove while a wire drag is in flight.

        Repaths the rubber-band bezier AND sweeps input pins to toggle the
        snap-target glow. The sweep is O(pins) which is fine — even a
        50-node graph has under 200 pins.
        """
        if self._pending_source is None or self._pending_wire is None:
            return
        a = self._pending_source.scenePos()
        b = scene_pos
        dx = max(40.0, abs(b.x() - a.x()) * 0.5)
        path = QPainterPath(a)
        path.cubicTo(a.x() + dx, a.y(), b.x() - dx, b.y(), b.x(), b.y())
        self._pending_wire.setPath(path)

        # Sweep input pins — toggle snap glow on/off.
        source_parent = self._pending_source.parentItem()
        r2 = self._WIRE_SNAP_RADIUS ** 2
        for item in self.items():
            if not isinstance(item, PinItem) or item._direction != "in":
                continue
            # Never light up an input on the SAME node as the drag source —
            # self-loops are refused at commit, so don't lie about them here.
            if item.parentItem() is source_parent:
                item.set_snap_target(False)
                continue
            pin_pos = item.scenePos()
            dx_p = pin_pos.x() - scene_pos.x()
            dy_p = pin_pos.y() - scene_pos.y()
            item.set_snap_target((dx_p * dx_p + dy_p * dy_p) <= r2)

    def _end_wire_drag(self, scene_pos: QPointF) -> None:
        """Called by the output PinItem on mouseRelease — commit or discard.

        Commits IFF the cursor is over a compatible input pin (direction
        ``in``, different node, no duplicate connection). Otherwise the
        temp wire just disappears. The drop tolerance is the pin's hit
        rect — same as the hover halo, so a near-miss won't surprise the
        user with a connection they didn't intend.
        """
        source = self._pending_source
        temp = self._pending_wire
        # Always clear transient state first, even on failure.
        self._pending_source = None
        self._pending_wire = None
        if temp is not None:
            self.removeItem(temp)
        # Clear every input pin's snap-target glow so we don't leave
        # stale highlights after the drag ends.
        for item in self.items():
            if isinstance(item, PinItem) and item._direction == "in":
                item.set_snap_target(False)
        if source is None or self._graph is None:
            return

        target = self._find_input_pin_at(scene_pos)
        if target is None:
            return
        # Disallow self-loops (same node) — graph evaluator refuses cycles,
        # this is the friendlier UX gate that prevents them at draw time.
        if target.parentItem() is source.parentItem():
            return

        src_id = self._endpoint_id(source)
        dst_id = self._endpoint_id(target)
        if src_id is None or dst_id is None:
            return

        # Idempotency: ignore if this exact connection already exists.
        for c in self._graph.connections:
            if (c.from_node == src_id and c.from_pin == source.pin_name
                and c.to_node == dst_id and c.to_pin == target.pin_name):
                return

        from ..nodes import Connection
        new_conn = Connection(
            from_node=src_id, from_pin=source.pin_name,
            to_node=dst_id, to_pin=target.pin_name,
        )
        self._graph.connections.append(new_conn)
        wire = WireItem(from_pin=source, to_pin=target)
        self.addItem(wire)
        self._wires.append(wire)
        wire._refresh_chip_visibility()
        for endpoint in (source.parentItem(), target.parentItem()):
            if endpoint is None:
                continue
            self._wires_by_endpoint.setdefault(id(endpoint), []).append(wire)
        self.graph_changed.emit()

    def _find_input_pin_at(self, scene_pos: QPointF) -> Optional["PinItem"]:
        """Return the first input PinItem under `scene_pos`, or None."""
        # itemAt returns the topmost item; we want any PinItem touching the
        # point — easier to iterate items() and look up by bounding rect.
        for item in self.items(scene_pos):
            if isinstance(item, PinItem) and item._direction == "in":
                return item
        return None

    # ----- helpers

    def _resolve_out_pin(self, node_id: str, pin_name: str) -> Optional[PinItem]:
        if node_id in self._node_items:
            return self._node_items[node_id].output_pin(pin_name)
        bi = self._boundary_items.get(node_id)
        if bi is not None and bi.pin.direction == "out":
            return bi.pin
        return None

    def _resolve_in_pin(self, node_id: str, pin_name: str) -> Optional[PinItem]:
        if node_id in self._node_items:
            return self._node_items[node_id].input_pin(pin_name)
        bi = self._boundary_items.get(node_id)
        if bi is not None and bi.pin.direction == "in":
            return bi.pin
        return None


# ---------------------------------------------------------------------------
# Context-menu builders. Factored out of the QGraphicsItem subclasses so the
# menu shape is easy to assert in tests without instantiating Qt events.
# ---------------------------------------------------------------------------

def build_wire_menu(wire: "WireItem", scene: "NodeGraphScene"):
    """Wire ⚙ context menu — Delete + inline-transform picker.

    Wire-eligible nodes are surfaced as a submenu so the user can see every
    1-in / 1-out transform available. "None" entry clears any existing
    inline transform. Current transform (if any) is shown as the menu
    title prefix for orientation.
    """
    from .primitives import UIDropdownMenu

    menu = UIDropdownMenu()
    # Read the current inline transform off the wire's underlying Connection
    # so the user can see what's already applied before changing it.
    current_kind: Optional[str] = None
    if scene._graph is not None:
        from_id = scene._endpoint_id(wire._from)
        to_id = scene._endpoint_id(wire._to)
        for c in scene._graph.connections:
            if (
                c.from_node == from_id and c.from_pin == wire._from.pin_name
                and c.to_node == to_id and c.to_pin == wire._to.pin_name
            ):
                if c.inline_transform is not None:
                    current_kind = c.inline_transform.kind
                break

    label = "Wire" if current_kind is None else f"Wire — {current_kind}"
    menu.add_label(label)
    menu.add_item("Delete connection", on_click=lambda: scene.delete_wire(wire))
    menu.add_separator()

    # Inline transform submenu — only wire-eligible nodes from the registry.
    if scene._registry is not None:
        sub = menu.add_submenu("Inline transform")
        sub.add_item(
            "(none)",
            on_click=lambda: scene.set_wire_inline_transform(wire, None),
        )
        for spec in scene._registry.wire_eligible():
            mark = "✓ " if spec.kind == current_kind else "  "
            sub.add_item(
                f"{mark}{spec.label}",
                on_click=lambda k=spec.kind: scene.set_wire_inline_transform(wire, k),
            )
    return menu


def build_source_menu(source_item: "BoundaryItem", scene: "NodeGraphScene"):
    """Right-click menu on a controller source — Rename + Delete.

    Kind (button vs stick vs trigger) isn't editable here — sources are
    tied to physical hardware surfaces. To change WHICH surface a source
    reads, delete this one and Add Input a new one.
    """
    from .primitives import UIDropdownMenu

    source_id = None
    for sid, item in scene._boundary_items.items():
        if item is source_item:
            source_id = sid
            break

    menu = UIDropdownMenu()
    menu.add_label(source_item._b.label or "Input")
    menu.add_item(
        "Rename…",
        on_click=lambda: _prompt_edit_source_label(scene, source_id) if source_id else None,
    )
    menu.add_separator()
    menu.add_item(
        "Delete source",
        on_click=lambda: scene.delete_source(source_id) if source_id else None,
        shortcut="Del",
    )
    return menu


def _prompt_edit_source_label(scene: "NodeGraphScene", source_id: str) -> None:
    if scene._graph is None or source_id not in scene._graph.sources:
        return
    from PySide6.QtWidgets import QInputDialog
    src = scene._graph.sources[source_id]
    text, ok = QInputDialog.getText(
        None, "Rename input", "Display label:", text=src.label or "",
    )
    if ok:
        scene.edit_source(source_id, label=text.strip())


def build_sink_menu(sink_item: "BoundaryItem", scene: "NodeGraphScene"):
    """Right-click menu on a sink — Edit target, Edit label, Delete."""
    from .primitives import UIDropdownMenu

    sink_id = None
    for sid, item in scene._boundary_items.items():
        if item is sink_item:
            sink_id = sid
            break

    menu = UIDropdownMenu()
    menu.add_label(sink_item._b.label or "Output")
    menu.add_item(
        "Edit target…",
        on_click=lambda: _prompt_edit_sink_target(scene, sink_id) if sink_id else None,
    )
    menu.add_item(
        "Rename…",
        on_click=lambda: _prompt_edit_sink_label(scene, sink_id) if sink_id else None,
    )
    menu.add_separator()
    menu.add_item(
        "Delete output",
        on_click=lambda: scene.delete_sink(sink_id) if sink_id else None,
        shortcut="Del",
    )
    return menu


def _prompt_edit_sink_target(scene: "NodeGraphScene", sink_id: str) -> None:
    if scene._graph is None or sink_id not in scene._graph.sinks:
        return
    from PySide6.QtWidgets import QInputDialog
    sink = scene._graph.sinks[sink_id]
    text, ok = QInputDialog.getText(
        None,
        "Edit output target",
        "Symbolic target string:",
        text=sink.symbol,
    )
    if ok and text.strip():
        scene.edit_sink(sink_id, symbol=text.strip())


def _prompt_edit_sink_label(scene: "NodeGraphScene", sink_id: str) -> None:
    if scene._graph is None or sink_id not in scene._graph.sinks:
        return
    from PySide6.QtWidgets import QInputDialog
    sink = scene._graph.sinks[sink_id]
    text, ok = QInputDialog.getText(
        None,
        "Rename output",
        "Display label:",
        text=sink.label or sink.symbol,
    )
    if ok:
        scene.edit_sink(sink_id, label=text.strip())


def build_node_menu(node_item: "NodeItem", scene: "NodeGraphScene"):
    """Right-click menu on a NodeItem — Edit + Reset + Delete."""
    from .primitives import UIDropdownMenu

    menu = UIDropdownMenu()
    menu.add_label(node_item._spec.label)
    menu.add_item(
        "Edit params…",
        on_click=lambda: _open_param_editor(node_item, scene),
    )
    menu.add_item(
        "Reset params to defaults",
        on_click=lambda: scene.reset_node_params(node_item._node.id),
    )
    menu.add_separator()
    menu.add_item(
        "Delete node",
        on_click=lambda: scene.delete_node(node_item._node.id),
        shortcut="Del",
    )
    return menu


def _open_param_editor(node_item: "NodeItem", scene: "NodeGraphScene") -> None:
    """Pop the NodeParamEditor (Qt modal dialog). Repaints the card on OK
    so the new param values show up in the right-aligned row display.
    Emits graph_changed so the auto-save path picks up the new params."""
    from .node_param_editor import NodeParamEditor
    dlg = NodeParamEditor(node=node_item._node, spec=node_item._spec)
    if dlg.exec_() == NodeParamEditor.Accepted:
        node_item.update()
        scene.graph_changed.emit()


def build_add_node_menu(scene: "NodeGraphScene", scene_pos: QPointF):
    """Empty-canvas right-click menu — categorised "Add Node" picker +
    "Add Output" submenu for new MIDI sinks at the click position.

    Categories are submenus, nodes inside each are items. Categories with
    no registered nodes are absent (NodeRegistry.by_category drops empties).
    """
    from .primitives import UIDropdownMenu

    menu = UIDropdownMenu()
    menu.add_label("Add Node")
    if scene._registry is None:
        menu.add_item("(no registry attached)", disabled=True)
        return menu
    for cat_kind, specs in scene._registry.by_category().items():
        meta = category_meta(cat_kind)
        label = meta.label if meta else cat_kind
        sub = menu.add_submenu(label)
        for spec in specs:
            sub.add_item(
                spec.label,
                on_click=lambda k=spec.kind: scene.add_node(k, scene_pos),
            )

    menu.add_separator()
    menu.add_label("Add Input")
    src_sub = menu.add_submenu("Controller Input…")
    # Common controller surfaces — quick-add for each. Users can rename
    # via right-click on the source if they want a custom label.
    _add_source_quick_options(src_sub, scene, scene_pos)

    menu.add_separator()
    menu.add_label("Add Output")
    sink_sub = menu.add_submenu("MIDI Output…")
    # Quick-add common MIDI destinations. User can right-click the sink
    # after to edit the exact CC/note number via the sink-target dialog.
    sink_sub.add_item(
        "MIDI CC 1  (Mod Wheel)",
        on_click=lambda: scene.add_sink("midi.cc:1@ch:1", scene_pos, "CC 1 Mod Wheel"),
    )
    sink_sub.add_item(
        "MIDI CC 7  (Volume)",
        on_click=lambda: scene.add_sink("midi.cc:7@ch:1", scene_pos, "CC 7 Volume"),
    )
    sink_sub.add_item(
        "MIDI CC 11 (Expression)",
        on_click=lambda: scene.add_sink("midi.cc:11@ch:1", scene_pos, "CC 11 Expression"),
    )
    sink_sub.add_item(
        "MIDI CC 64 (Sustain)",
        on_click=lambda: scene.add_sink("midi.cc:64@ch:1", scene_pos, "CC 64 Sustain"),
    )
    sink_sub.add_item(
        "MIDI CC 71 (Resonance)",
        on_click=lambda: scene.add_sink("midi.cc:71@ch:1", scene_pos, "CC 71 Resonance"),
    )
    sink_sub.add_item(
        "MIDI CC 74 (Filter Cutoff)",
        on_click=lambda: scene.add_sink("midi.cc:74@ch:1", scene_pos, "CC 74 Cutoff"),
    )
    sink_sub.add_separator()
    sink_sub.add_item(
        "MIDI Note 60 (C4)",
        on_click=lambda: scene.add_sink("midi.note:60@ch:1", scene_pos, "Note 60 (C4)"),
    )
    sink_sub.add_item(
        "MIDI Note 36 (Kick)",
        on_click=lambda: scene.add_sink("midi.note:36@ch:1", scene_pos, "Note 36 (Kick)"),
    )
    sink_sub.add_separator()
    sink_sub.add_item(
        "Custom symbolic target…",
        on_click=lambda: _prompt_custom_sink(scene, scene_pos),
    )
    return menu


def _add_source_quick_options(sub, scene: "NodeGraphScene", scene_pos: QPointF) -> None:
    """Populate the Add Input submenu with every standard controller surface.

    Mirrors ``seed.py`` plus extras that aren't in the default seed (left/
    right stick X+Y as separate axes, individual triggers as raw axes,
    extra buttons by index). Each entry adds a fresh source at the
    click position — duplicates are allowed because a user might want
    two views on the same button (e.g. one feeding a tap-vs-hold, one
    feeding a chord_detect).
    """
    entries = [
        ("Left Stick (XY)",        "stick_xy", 0, "Left Stick"),
        ("Right Stick (XY)",       "stick_xy", 1, "Right Stick"),
        ("L2 Trigger",             "trigger",  0, "L2 Trigger"),
        ("R2 Trigger",             "trigger",  1, "R2 Trigger"),
        ("D-Pad",                  "dpad",     0, "D-Pad"),
        ("Touchpad",               "touchpad", 0, "Touchpad"),
        ("Battery (0..1)",         "battery",  0, "Battery"),
    ]
    for label, kind, idx, default_label in entries:
        sub.add_item(
            label,
            on_click=lambda k=kind, i=idx, l=default_label:
                scene.add_source(k, i, l, scene_pos),
        )
    sub.add_separator()
    button_names = [
        (0, "Cross / A"), (1, "Circle / B"), (2, "Square / X"),
        (3, "Triangle / Y"), (4, "L1"), (5, "R1"),
        (6, "Share / View"), (7, "Options / Menu"),
        (8, "L3 Stick Click"), (9, "R3 Stick Click"),
        (10, "PS / Xbox Home"),
    ]
    btn_sub = sub.add_submenu("Button…")
    for idx, btn_label in button_names:
        btn_sub.add_item(
            btn_label,
            on_click=lambda i=idx, l=btn_label:
                scene.add_source("button", i, l, scene_pos),
        )
    sub.add_separator()
    sub.add_item(
        "Single Axis…",
        on_click=lambda: _prompt_single_axis_source(scene, scene_pos),
    )


def _prompt_single_axis_source(scene: "NodeGraphScene", scene_pos: QPointF) -> None:
    from PySide6.QtWidgets import QInputDialog
    idx, ok = QInputDialog.getInt(
        None, "Add Single Axis",
        "Axis index (0..5; 0-3 = stick axes, 4-5 = triggers):",
        0, 0, 32,
    )
    if ok:
        scene.add_source("axis", int(idx), f"Axis {idx}", scene_pos)


def _prompt_custom_sink(scene: "NodeGraphScene", scene_pos: QPointF) -> None:
    """Pop a small QInputDialog asking for a raw symbol string. Used by
    the "Custom symbolic target…" entry on the Add Output picker so the
    user can drop in any destination (e.g. ``resolume.layer:1.opacity``)
    without hand-editing JSON."""
    from PySide6.QtWidgets import QInputDialog
    text, ok = QInputDialog.getText(
        None,
        "Add Output",
        "Symbolic target (e.g. midi.cc:7@ch:1 or resolume.layer:1.opacity):",
        text="midi.cc:1@ch:1",
    )
    if ok and text.strip():
        scene.add_sink(text.strip(), scene_pos, text.strip())


class NodeGraphView(QGraphicsView):
    """Pan + zoom + fit. Single-purpose view for one NodeGraphScene."""

    MIN_ZOOM = 0.25
    MAX_ZOOM = 4.0

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = NodeGraphScene()
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        # Mouse-anchored zoom — feels right with trackpad pinch + Cmd-scroll.
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        # Empty-space drag pans the view. ScrollHandDrag puts a hand cursor.
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        # Avoid jagged transforms — smooth pixmaps at non-integer zooms.
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        # Larger scene rect than the content so panning past the edges
        # doesn't snap back to the bounding box of the items.
        self.setSceneRect(-2000, -1000, 4000, 3000)
        # Mouse tracking so the view receives mouseMove events without a
        # button held — needed for click-to-click wiring where the pending
        # wire follows the cursor between the first and second click.
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def scene_view(self) -> NodeGraphScene:
        return self._scene

    def load_graph(self, graph: NodeGraph, registry: NodeRegistry) -> None:
        self._scene.load_graph(graph, registry)
        self.fit_to_graph()

    # ----- zoom

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        # Cmd/Ctrl + scroll → zoom. Plain scroll falls through to default
        # (vertical scroll of the view) so trackpad two-finger pan still works.
        mod = event.modifiers()
        if mod & (Qt.ControlModifier | Qt.MetaModifier):
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1.0 / 1.15
            self._apply_zoom(factor)
            event.accept()
            return
        super().wheelEvent(event)

    def _apply_zoom(self, factor: float) -> None:
        new_scale = self.transform().m11() * factor
        if new_scale < self.MIN_ZOOM or new_scale > self.MAX_ZOOM:
            return
        self.scale(factor, factor)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_F:
            self.fit_to_graph()
            return
        if event.key() == Qt.Key_1:
            self.resetTransform()
            return
        if event.key() == Qt.Key_Escape:
            # Cancel any pending wire — TouchDesigner convention.
            if self._scene._pending_source is not None:
                self._scene._cancel_wire_drag()
                return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Delete every selected NodeItem. BoundaryItems are intentionally
            # NOT deletable from this shortcut — they're first-class graph
            # boundaries that the user creates / removes by other means
            # (controller hardware / sink right-click menu).
            for item in list(self._scene.selectedItems()):
                if isinstance(item, NodeItem):
                    self._scene.delete_node(item._node.id)
            return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        # Track the cursor for the pending wire's endpoint even when no
        # mouse button is held — this is what makes click-to-click feel
        # like TouchDesigner / Blender's node editors.
        if self._scene._pending_source is not None:
            self._scene._update_wire_drag(self.mapToScene(event.pos()))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        # If a wire is pending and the user clicks on empty canvas, cancel.
        # Item clicks (output / input pin) are handled by the items themselves
        # before this fires, so we only see clicks that missed everything.
        if (
            event.button() == Qt.LeftButton
            and self._scene._pending_source is not None
            and self.scene().itemAt(self.mapToScene(event.pos()), self.transform()) is None
        ):
            self._scene._cancel_wire_drag()
            event.accept()
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        """Right-click on empty canvas → "Add Node" picker.

        If the click lands ON an item (NodeItem, BoundaryItem, PinItem,
        WireItem), QGraphicsScene dispatches contextMenuEvent to that
        item instead and we never see it here.
        """
        scene_pos = self.mapToScene(event.pos())
        # Did this click hit any item? Pin items have very small bounding
        # rects so we generously widen the hit-test by 4px each side.
        hit = self.scene().itemAt(scene_pos, self.transform())
        if hit is not None:
            super().contextMenuEvent(event)
            return
        menu = build_add_node_menu(self._scene, scene_pos)
        menu.popup_at_global(event.globalPos())
        self._scene._last_menu = menu       # keep alive until selection

    def fit_to_graph(self) -> None:
        """Frame all items with a small margin. No-op if the scene is empty."""
        items_rect = self._scene.itemsBoundingRect()
        if items_rect.isNull() or items_rect.isEmpty():
            return
        margin = 60
        framed = items_rect.adjusted(-margin, -margin, margin, margin)
        self.fitInView(framed, Qt.KeepAspectRatio)
        # Clamp to MAX_ZOOM so tiny graphs don't blow up to 10× scale.
        scale = self.transform().m11()
        if scale > self.MAX_ZOOM:
            factor = self.MAX_ZOOM / scale
            self.scale(factor, factor)


def build_template_menu(scene: "NodeGraphScene", scene_pos: QPointF):
    """Starter-template picker, grouped by category like the node picker.

    Templates exist because 78 nodes behind one dropdown gives a newcomer no
    way in. Each entry drops a small working sub-graph — source, a node or
    two, a sink, already wired — so the canvas does something immediately and
    there is a concrete example to pull apart.

    Descriptions go on the item as a tooltip rather than in the label: the
    label has to stay scannable, and the description is a sentence.
    """
    from .primitives import UIDropdownMenu
    from ..nodes import templates as node_templates

    menu = UIDropdownMenu()
    menu.add_label("Start from a template")
    for cat_kind, items in node_templates.by_category().items():
        meta = category_meta(cat_kind)
        sub = menu.add_submenu(meta.label if meta else cat_kind)
        for t in items:
            node_count = t.node_count
            # add_item has no tooltip kwarg; it returns the QAction so the
            # description can be attached there.
            action = sub.add_item(
                f"{t.label}  ·  {node_count} node{'' if node_count == 1 else 's'}",
                on_click=(lambda tid=t.id: scene.add_template(tid, scene_pos)),
            )
            action.setToolTip(t.description)
    return menu
