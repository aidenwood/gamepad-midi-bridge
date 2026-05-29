"""Multi-controller orchestration (Pro feature).

Owns 1..2 BridgeControllers and decides at start() time how many to spin up
based on:
    1. how many controllers pygame sees,
    2. the license tier (free tier caps at one slot),
    3. the user-selected mode ("off" / "auto" / "force_two").

Each slot gets its own MIDI virtual port + its own Mapping (deep-copied from
the user's base mapping then channel-bumped) so DAWs can route each controller
independently. Signals are NOT slot-tagged — the GUI wires each slot's worker
to its own meter directly, which keeps BridgeWorker untouched on the single
-controller path.
"""
from __future__ import annotations

import copy
import os
from typing import List, Optional

from PySide6.QtCore import QObject

from . import license as _license
from . import telemetry
from .bridge import BridgeController
from .controller import available_count
from .mapping import Mapping
from .midi_backend import DEFAULT_PORT_NAME


def _demo_env() -> bool:
    """`GMB_DEMO=1` env var swaps every controller for the synthetic one.
    Lets the GUI path opt into demo mode without re-plumbing every callsite.
    """
    return os.environ.get("GMB_DEMO", "").lower() in ("1", "true", "yes")


def _keyboard_env() -> bool:
    """`GMB_KEYBOARD=1` env var swaps every controller for keyboard input.
    Lets the GUI path opt into keyboard mode without re-plumbing every callsite.
    """
    return os.environ.get("GMB_KEYBOARD", "").lower() in ("1", "true", "yes")


# User-facing modes for the "Active controllers" combo in Settings.
MODE_OFF = "off"            # always single-slot (default)
MODE_AUTO = "auto"          # use both if Pro + 2 connected
MODE_FORCE_TWO = "force_two"  # Pro-only, error if <2 connected

MAX_SLOTS = 2


def port_name_for_slot(slot_index: int) -> str:
    """Suffix the virtual port so two bridges can coexist.

    Slot 0 keeps the original "Universal Controller MIDI" name so existing DAW
    routings continue to work after upgrade.
    """
    if slot_index == 0:
        return DEFAULT_PORT_NAME
    return f"{DEFAULT_PORT_NAME} {slot_index + 1}"


def mapping_for_slot(base: Mapping, slot_index: int) -> Mapping:
    """Deep-copy the base mapping and offset its MIDI channel.

    Each slot defaults to its own channel so a DAW receives controller 1 on
    channel 1 and controller 2 on channel 2 — the smallest-surprise default.
    The user can still edit each slot's mapping in the Pro editor.
    """
    cloned = copy.deepcopy(base)
    cloned.midi_channel = (base.midi_channel + slot_index) & 0x0F
    if slot_index > 0:
        cloned.name = f"{base.name} (slot {slot_index + 1})"
    return cloned


def desired_slot_count(mode: str, detected: Optional[int] = None) -> int:
    """How many slots SHOULD activate, given the mode + what's plugged in.

    Free tier always returns 1. `force_two` raises on insufficient hardware so
    the GUI can surface a friendly error instead of silently degrading.
    """
    count = available_count() if detected is None else detected
    multi_ok = (
        _license.is_pro()
        and _license.feature_enabled("multi_controller")
    )
    if not multi_ok:
        return 1
    if mode == MODE_FORCE_TWO:
        if count < 2:
            raise RuntimeError(
                "Force-two mode needs two controllers. Plug in a second one or "
                "switch Active controllers to Auto."
            )
        return 2
    if mode == MODE_AUTO and count >= 2:
        return 2
    return 1


class MultiBridgeController(QObject):
    """Owns one or two BridgeControllers. Behaves like a single one when the
    free tier or hardware can't support multi-controller.

    The GUI treats `bridges[0]` exactly like the V1.1 single bridge — every
    signal wiring path is preserved. The second bridge is only ever populated
    when Pro is active AND the mode says so.
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._parent = parent
        self._demo = _demo_env()
        self._keyboard = _keyboard_env()
        self.bridges: List[BridgeController] = [
            BridgeController(parent, demo=self._demo, keyboard=self._keyboard)
        ]

    # ------------------------------------------------------------------ slots

    def slot_count(self) -> int:
        return len(self.bridges)

    def primary(self) -> BridgeController:
        return self.bridges[0]

    def secondary(self) -> Optional[BridgeController]:
        return self.bridges[1] if len(self.bridges) > 1 else None

    # ------------------------------------------------------------------ configure

    def configure(self, base_mapping: Mapping, mode: str) -> int:
        """Decide how many slots to activate and (re)build BridgeControllers.

        Returns the active slot count. Must be called BEFORE start() — once a
        thread is running we don't hot-swap workers.
        """
        wanted = desired_slot_count(mode)
        # Tear down any prior secondary if we're dropping back to 1.
        if wanted == 1 and len(self.bridges) > 1:
            self.bridges[1].shutdown()
            self.bridges = self.bridges[:1]
        # Build the secondary on demand. Primary is rebuilt only if we're
        # adding a slot to make sure its mapping/port match the new config.
        if wanted >= 2 and len(self.bridges) < 2:
            self.bridges.append(BridgeController(
                self._parent,
                slot_index=1,
                demo=self._demo,
                keyboard=self._keyboard,
                midi_port_name=port_name_for_slot(1),
            ))
        # Push per-slot mappings — each worker gets a deep copy so edits on
        # slot 1 don't bleed into slot 0.
        for i, bridge in enumerate(self.bridges):
            bridge.worker.set_mapping(mapping_for_slot(base_mapping, i))
        return wanted

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        for bridge in self.bridges:
            bridge.start()
        if len(self.bridges) >= 2:
            telemetry.send_event("multi_controller_active",
                                 slot_count=len(self.bridges))

    def stop(self) -> None:
        for bridge in self.bridges:
            bridge.stop()

    def recalibrate(self) -> None:
        for bridge in self.bridges:
            bridge.recalibrate()

    def shutdown(self) -> None:
        for bridge in self.bridges:
            bridge.shutdown()

    # ------------------------------------------------------------------ helpers

    def apply_mapping(self, base_mapping: Mapping) -> None:
        """Live-apply a mapping change across all active slots."""
        for i, bridge in enumerate(self.bridges):
            bridge.worker.set_mapping(mapping_for_slot(base_mapping, i))
