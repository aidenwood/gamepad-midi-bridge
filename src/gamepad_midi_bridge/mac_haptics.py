"""macOS adaptive-trigger output via Apple's GameController framework.

Why this module exists
----------------------
macOS post-Catalina (and aggressively from Big Sur on) sandboxes raw HID
*output* reports to Sony's DualSense. The kernel accepts our hidapi input
reads but silently drops trigger-feedback writes (hid_write returns -1, or
returns >0 but the controller ignores the packet). That is intentional —
Apple owns the DualSense pipeline on mac and routes it through their
`GameController` framework. There is no entitlement we can ship in an
open-source binary that unlocks raw HID-out.

So instead of fighting it, we use the supported path: Apple's
`GCDualSenseAdaptiveTrigger`, available since **macOS 11.3 (April 2021)**.

This module is import-safe on every platform: if pyobjc or the
GameController framework can't load, `HAPTICS_AVAILABLE` stays False and
callers fall back to the hidapi path (Win/Linux) or simply no-op.

Effect coverage
---------------
Apple's GCController exposes four trigger modes:
    off, feedback, weapon, vibration
plus (macOS 12+) `slopeFeedback`. That's it. The richer DualShock effects
Sony ships in their PS5 SDK — **bow, galloping, machine** — are not exposed
through GCController and require raw HID writes that macOS blocks. We
keep them in the public `EFFECTS` tuple so the bridge's MIDI mapping stays
platform-agnostic, but on mac they degrade to `setModeOff()` and
`set_trigger_effect` returns False so the caller can log the gap.

Reference: Apple GameController headers (Xcode SDK) →
    GCDualSenseAdaptiveTrigger.h, introduced macOS 11.3 / iOS 14.5.
"""
from __future__ import annotations

import sys
from typing import Optional


EFFECTS = ("off", "feedback", "weapon", "vibration", "bow", "galloping", "machine")

# Effects Apple actually exposes through GCController. The rest fall back to off.
_NATIVE_EFFECTS = frozenset({"off", "feedback", "weapon", "vibration"})


# --- guarded import -----------------------------------------------------------
# Both pyobjc-core and pyobjc-framework-GameController must be present, and we
# must be on Darwin >= 11.3. Any failure here flips HAPTICS_AVAILABLE off; we
# never raise at import time so the bridge stays portable.

HAPTICS_AVAILABLE: bool = False
_GCController = None  # type: ignore[assignment]
_import_error: Optional[str] = None

if sys.platform == "darwin":
    try:
        # pyobjc-framework-GameController exposes the whole framework under
        # this top-level name. Importing it lazily means non-mac builds never
        # try to resolve the dylib.
        from GameController import GCController  # type: ignore
        _GCController = GCController
        HAPTICS_AVAILABLE = True
    except Exception as exc:  # pragma: no cover — env-dependent
        _import_error = f"{type(exc).__name__}: {exc}"
        HAPTICS_AVAILABLE = False


def import_error() -> Optional[str]:
    """Diagnostic helper — why did HAPTICS_AVAILABLE come back False?"""
    return _import_error


# --- handle -------------------------------------------------------------------


class MacHapticsHandle:
    """Bound to the first DualSense GCController sees.

    GCController auto-discovers paired controllers. We don't start the
    discovery service ourselves because the host app (or SDL via pygame)
    will have done that already, and starting it twice triggers Apple's
    duplicate-observer warning. If no controller is visible yet, `open()`
    returns None — caller should retry after the user presses the PS button.
    """

    def __init__(self, controller, left, right) -> None:
        # Stash the native ObjC objects. They're retained automatically by
        # pyobjc's bridge; releasing happens in close().
        self._controller = controller
        self._left = left
        self._right = right
        self._closed = False

    # ---- discovery ---------------------------------------------------------

    @classmethod
    def open(cls) -> Optional["MacHapticsHandle"]:
        """Return a handle bound to the first DualSense, or None.

        None means: not on mac, pyobjc missing, or GCController hasn't
        enumerated a DualSense yet. The bridge should fall back to hidapi
        (or no-op on mac since hidapi-out is blocked anyway).
        """
        if not HAPTICS_AVAILABLE or _GCController is None:
            return None

        controllers = _GCController.controllers()
        if not controllers:
            return None

        # GCController doesn't give us a clean `isKindOfClass:` check from
        # python without importing the subclass symbol, so we probe by
        # selector. Only DualSense gamepads respond to
        # `dualsenseAdaptiveTriggers` (returns a GCDualSenseGamepad).
        for c in controllers:
            gamepad = None
            if c.respondsToSelector_("extendedGamepad"):
                gamepad = c.extendedGamepad()
            if gamepad is None:
                continue
            # GCDualSenseGamepad inherits from GCExtendedGamepad and adds
            # leftTrigger/rightTrigger overrides that ARE
            # GCDualSenseAdaptiveTrigger instances.
            left = gamepad.leftTrigger() if gamepad.respondsToSelector_("leftTrigger") else None
            right = gamepad.rightTrigger() if gamepad.respondsToSelector_("rightTrigger") else None
            if left is None or right is None:
                continue
            # Adaptive triggers respond to setModeOff; the plain
            # GCControllerButtonInput does not.
            if not left.respondsToSelector_("setModeOff"):
                continue
            return cls(c, left, right)

        return None

    # ---- output ------------------------------------------------------------

    def set_trigger_effect(self, side: str, effect: str) -> bool:
        """Apply `effect` to L or R adaptive trigger.

        Returns True if Apple's GCController accepted the call. Returns
        False if the effect isn't natively supported on mac (bow,
        galloping, machine) — in that case we fall back to setModeOff so
        the trigger isn't left in a stale state, and the caller can log
        the limitation.
        """
        if self._closed:
            return False
        trigger = self._trigger_for(side)
        if trigger is None:
            return False
        if effect not in EFFECTS:
            return False

        # Native four. Default parameters are tuned for "you can feel it
        # without losing fine control" — pull request a tuning pass once
        # we have real MIDI input to drive them.
        if effect == "off":
            trigger.setModeOff()
            return True
        if effect == "feedback":
            if trigger.respondsToSelector_("setModeFeedbackWithStartPosition:resistiveStrength:"):
                trigger.setModeFeedbackWithStartPosition_resistiveStrength_(0.0, 0.8)
                return True
        elif effect == "weapon":
            if trigger.respondsToSelector_(
                "setModeWeaponWithStartPosition:endPosition:resistiveStrength:"
            ):
                trigger.setModeWeaponWithStartPosition_endPosition_resistiveStrength_(
                    0.4, 0.8, 0.8
                )
                return True
        elif effect == "vibration":
            if trigger.respondsToSelector_(
                "setModeVibrationWithStartPosition:amplitude:frequency:"
            ):
                trigger.setModeVibrationWithStartPosition_amplitude_frequency_(
                    0.0, 0.8, 20.0
                )
                return True

        # Sony-only effects. Apple's GameController framework does NOT
        # expose bow / galloping / machine — those are part of Sony's
        # DualShock SDK (libpad on PS5, libScePad on the dev kits) and
        # would require a raw HID-out report that macOS blocks. We fall
        # back to off so the trigger doesn't stay stuck in whatever mode
        # it was in before, and return False so the bridge can surface
        # the gap.
        trigger.setModeOff()
        return False

    def _trigger_for(self, side: str):
        s = (side or "").strip().upper()
        if s == "L":
            return self._left
        if s == "R":
            return self._right
        return None

    # ---- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Drop references. GCController itself owns the controller object;
        we just release our retains so pyobjc can let go."""
        if self._closed:
            return
        self._closed = True
        # Reset triggers on the way out — leaving a controller with an
        # active resistance profile after the app dies is a bad surprise
        # next time the user opens any other game.
        for t in (self._left, self._right):
            try:
                if t is not None and t.respondsToSelector_("setModeOff"):
                    t.setModeOff()
            except Exception:
                pass
        self._left = None
        self._right = None
        self._controller = None
