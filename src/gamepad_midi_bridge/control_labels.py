"""Canonical control names per controller family.

SDL reports the same button indices for every pad, so index 0 is "the bottom
face button" regardless of hardware. What that button is CALLED differs:
Cross on a PlayStation pad, A on an Xbox pad. The UI used to hardcode the
PlayStation names everywhere, so a Windows user with an Xbox One Controller
saw Cross / Circle / Square / Triangle / Share / Options / PS — plus a
touchpad their controller doesn't have.

One module owns these names. Import from here rather than re-declaring a
button list in a widget; two lists WILL drift.

Index order matches ``mapping.py`` defaults and ``BridgeWorker.button_state``.
"""
from __future__ import annotations

from typing import Dict, Optional

# Families we render differently. "playstation" is the default because the
# DualSense is the primary target and the superset (it has a touchpad).
PLAYSTATION = "playstation"
XBOX = "xbox"
SWITCH = "switch"
GENERIC = "generic"


def family_for(controller_name: Optional[str]) -> str:
    """Classify a controller name into a label family.

    Matches the substrings SDL / the OS actually report, lower-cased.
    """
    lc = (controller_name or "").lower()
    if "xbox" in lc or "x-input" in lc or "xinput" in lc:
        return XBOX
    if "dualsense" in lc or "dualshock" in lc or "wireless controller" in lc:
        return PLAYSTATION
    if "switch" in lc or "joy-con" in lc or "joycon" in lc:
        return SWITCH
    return GENERIC


# Button index -> label, per family.
_BUTTONS: Dict[str, Dict[int, str]] = {
    PLAYSTATION: {
        0: "Cross", 1: "Circle", 2: "Square", 3: "Triangle",
        4: "L1", 5: "R1", 6: "Share", 7: "Options",
        8: "L3", 9: "R3", 10: "PS",
    },
    XBOX: {
        0: "A", 1: "B", 2: "X", 3: "Y",
        4: "LB", 5: "RB", 6: "View", 7: "Menu",
        8: "LS", 9: "RS", 10: "Guide",
    },
    SWITCH: {
        0: "B", 1: "A", 2: "Y", 3: "X",
        4: "L", 5: "R", 6: "Minus", 7: "Plus",
        8: "LS", 9: "RS", 10: "Home",
    },
    GENERIC: {
        0: "Btn 1", 1: "Btn 2", 2: "Btn 3", 3: "Btn 4",
        4: "L1", 5: "R1", 6: "Select", 7: "Start",
        8: "L3", 9: "R3", 10: "Home",
    },
}

# Short glyphs for the compact face-button cluster. Falls back to the full
# label when a family has no distinct glyph.
_GLYPHS: Dict[str, Dict[int, str]] = {
    PLAYSTATION: {0: "✕", 1: "○", 2: "□", 3: "△"},
    XBOX: {0: "A", 1: "B", 2: "X", 3: "Y"},
    SWITCH: {0: "B", 1: "A", 2: "Y", 3: "X"},
}

_TRIGGERS: Dict[str, Dict[str, str]] = {
    PLAYSTATION: {"L2": "L2", "R2": "R2"},
    XBOX: {"L2": "LT", "R2": "RT"},
    SWITCH: {"L2": "ZL", "R2": "ZR"},
    GENERIC: {"L2": "L2", "R2": "R2"},
}

DPAD_LABELS = {"up": "D-Up", "down": "D-Down",
               "left": "D-Left", "right": "D-Right"}
DPAD_ARROWS = {"up": "↑", "down": "↓", "left": "←", "right": "→"}


def button_label(index: int, family: str = PLAYSTATION) -> str:
    """Human name for a button index on the given family."""
    table = _BUTTONS.get(family, _BUTTONS[GENERIC])
    return table.get(index, f"Btn {index}")


def button_glyph(index: int, family: str = PLAYSTATION) -> str:
    """Compact glyph for a face button (indices 0-3), else the full label."""
    glyphs = _GLYPHS.get(family)
    if glyphs and index in glyphs:
        return glyphs[index]
    return button_label(index, family)


def trigger_label(side: str, family: str = PLAYSTATION) -> str:
    """``side`` is the canonical "L2"/"R2"; returns the family's name for it."""
    return _TRIGGERS.get(family, _TRIGGERS[GENERIC]).get(side, side)


def shoulder_label(side: str, family: str = PLAYSTATION) -> str:
    """``side`` is "L1"/"R1" — i.e. button index 4 / 5."""
    return button_label(4 if side == "L1" else 5, family)


def has_touchpad(family: str) -> bool:
    """Only PlayStation pads have one — don't draw dead UI for the rest."""
    return family == PLAYSTATION
