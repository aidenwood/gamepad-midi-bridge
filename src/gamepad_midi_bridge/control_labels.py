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

    Feed this a name from ``display_name`` below, not SDL's raw string.
    Microsoft's Xbox USB descriptor sets the product string to the literal
    word "Controller", so the raw name classifies as GENERIC and an Xbox
    pad loses the A/B/X/Y labels this module exists to give it.
    """
    lc = (controller_name or "").lower()
    if "xbox" in lc or "x-input" in lc or "xinput" in lc:
        return XBOX
    if ("dualsense" in lc or "dualshock" in lc or "playstation" in lc
            or "wireless controller" in lc):
        return PLAYSTATION
    if "switch" in lc or "joy-con" in lc or "joycon" in lc or "nintendo" in lc:
        return SWITCH
    return GENERIC


# ----------------------------------------------------------------- identity
# SDL packs the hardware IDs into the joystick GUID, which is where the real
# identity lives when the product string is useless. The 32-char hex string
# is a 16-byte struct of little-endian 16-bit fields:
#   [0:4] bus  [4:8] name-CRC  [8:12] vendor  [12:16] pad
#   [16:20] product  [20:24] pad  [24:28] version  [28:32] driver
# DualSense over USB: 030000004c050000e60c000000006800
#                     ^bus    ^vid    ^pid
BUS_USB = 0x03
BUS_BLUETOOTH = 0x05


def _le16(guid: str, start: int) -> int:
    chunk = guid[start:start + 4]
    if len(chunk) != 4:
        return 0
    try:
        return int(chunk[2:4] + chunk[0:2], 16)
    except ValueError:
        return 0


def vid_pid_from_guid(guid: Optional[str]) -> tuple:
    """(vendor_id, product_id) from an SDL GUID. (0, 0) when unknown."""
    g = (guid or "").strip().lower()
    if len(g) < 20:
        return (0, 0)
    return (_le16(g, 8), _le16(g, 16))


def bus_from_guid(guid: Optional[str]) -> int:
    """SDL bus type: BUS_USB, BUS_BLUETOOTH, or 0 when unknown."""
    g = (guid or "").strip().lower()
    if len(g) < 4:
        return 0
    return _le16(g, 0)


_PRODUCT_NAMES: Dict[tuple, str] = {
    (0x054C, 0x0CE6): "DualSense Wireless Controller",
    (0x054C, 0x0DF2): "DualSense Edge Wireless Controller",
    (0x054C, 0x09CC): "DualShock 4 Wireless Controller",
    (0x054C, 0x05C4): "DualShock 4 Wireless Controller",
    (0x054C, 0x0268): "DualShock 3 Controller",
    (0x045E, 0x02E0): "Xbox Wireless Controller",
    (0x045E, 0x02EA): "Xbox Wireless Controller",
    (0x045E, 0x02FD): "Xbox Wireless Controller",
    (0x045E, 0x0B12): "Xbox Wireless Controller",
    (0x045E, 0x0B13): "Xbox Wireless Controller",
    (0x045E, 0x0B20): "Xbox Wireless Controller",
    (0x045E, 0x0B00): "Xbox Elite Wireless Controller",
    (0x045E, 0x0B05): "Xbox Elite Wireless Controller Series 2",
    (0x045E, 0x0B22): "Xbox Elite Wireless Controller Series 2",
    (0x057E, 0x2009): "Nintendo Switch Pro Controller",
    (0x057E, 0x2006): "Joy-Con (L)",
    (0x057E, 0x2007): "Joy-Con (R)",
}

# VID-only fallback so a new PID from a known vendor still gets a brand.
_VENDOR_NAMES: Dict[int, str] = {
    0x054C: "PlayStation Controller",
    0x045E: "Xbox Controller",
    0x057E: "Nintendo Controller",
    0x28DE: "Steam Controller",
    0x18D1: "Stadia Controller",
}

# Strings SDL hands back that tell the user nothing. "Wireless Controller"
# is deliberately NOT here: it is the DualShock 4's real name and
# family_for() already resolves it to PLAYSTATION.
_USELESS_NAMES = {"", "controller", "gamepad", "game controller",
                  "unknown", "generic controller"}


def display_name(raw_name: Optional[str], guid: Optional[str] = None) -> str:
    """The name to put in front of a user.

    SDL reports whatever the device's USB descriptor says, and Microsoft
    sets that to the literal "Controller" — so an Xbox pad arrives with no
    brand on it at all, and every surface downstream inherits the blank.
    The GUID still carries the real VID:PID, so prefer a looked-up name and
    keep SDL's string only for hardware we don't have an entry for.
    """
    name = (raw_name or "").strip()
    vid, pid = vid_pid_from_guid(guid)
    known = _PRODUCT_NAMES.get((vid, pid))
    if known:
        return known
    if name.lower() not in _USELESS_NAMES:
        return name
    vendor = _VENDOR_NAMES.get(vid)
    if vendor:
        return vendor
    if vid or pid:
        return "Unknown Controller ({:04x}:{:04x})".format(vid, pid)
    return "Unknown Controller"


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
