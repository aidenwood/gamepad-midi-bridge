"""Qt glue for touchpad-as-mouse.

Owns the Qt half of the feature: subscribes to the BridgeWorker's existing
`touchpad_xy` and `button_state` signals and moves the system cursor. The
delta maths lives in `touchpad_mouse.py`, which is pure stdlib and tested on
its own; nothing here does arithmetic beyond adding a delta to the current
cursor position.

Thread safety is the reason this is a separate object rather than code in the
worker. BridgeWorker runs on its own QThread and its poll loop is hot — the
house rule is that heavy work happens in slots on the GUI thread, never inside
`_loop`. Signals from the worker to an object living on the GUI thread are
queued, so `_on_touchpad` runs on the GUI thread, which is the only thread
allowed to touch `QCursor`.

Not wired into any tab yet — the Customise tab that will expose the toggle is
being built separately. Construct it with the worker and a callable that
returns the live Mapping, and it works headlessly of any UI.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor

from ..mapping import Mapping
from ..touchpad_mouse import TouchpadMouse


class MouseModeDriver(QObject):
    """Drives the OS cursor from the controller touchpad.

    Args:
        worker: the BridgeWorker emitting `touchpad_xy` / `button_state`.
        get_mapping: callable returning the current Mapping. Read on every
            event so a preset change or a settings tweak takes effect without
            reconstructing the driver.
        parent: owning QObject — must live on the GUI thread.
    """

    #: Emitted when mouse mode turns on or off, so UI can reflect the state.
    mode_changed = Signal(bool)

    def __init__(
        self,
        worker,
        get_mapping: Callable[[], Mapping],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_mapping = get_mapping
        self._engine = TouchpadMouse(self._config())
        worker.button_state.connect(self._on_button)
        worker.touchpad_xy.connect(self._on_touchpad)

    # ── state ───────────────────────────────────────────────────────────
    def _config(self):
        return self._get_mapping().mouse_mode

    @property
    def active(self) -> bool:
        return self._engine.active

    def set_active(self, active: bool) -> None:
        """Engage or disengage from UI."""
        if self._engine.active == bool(active):
            return
        self._engine.set_active(active)
        self.mode_changed.emit(self._engine.active)

    def suppresses_midi(self) -> bool:
        """True when the touchpad should stop emitting its XY CCs.

        The bridge asks this before sending touchpad CCs so a single finger is
        not scrubbing a filter and moving the pointer at the same time.
        """
        return self._engine.active and self._config().suppress_midi

    # ── slots (GUI thread) ──────────────────────────────────────────────
    def _on_button(self, index: int, pressed: bool) -> None:
        cfg = self._config()
        # Re-sync the engine with config that may have changed under us, but
        # keep whatever live on/off state the performer has toggled to.
        self._engine._config = cfg  # same feature, one owner
        if self._engine.handle_button(index, pressed):
            self.mode_changed.emit(self._engine.active)

    def _on_touchpad(self, contact: bool, x: float, y: float) -> None:
        self._engine._config = self._config()
        dx, dy = self._engine.update(contact, x, y)
        if dx == 0.0 and dy == 0.0:
            return
        pos = QCursor.pos()
        QCursor.setPos(round(pos.x() + dx), round(pos.y() + dy))
