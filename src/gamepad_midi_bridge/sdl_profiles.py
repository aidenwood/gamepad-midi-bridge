"""Per-device SDL index profiles.

WHY THIS EXISTS
`pygame.joystick` reports RAW, device-and-driver-specific indices. It is not
SDL's GameController API, so SDL's mapping database is never applied — the
numbers that come back are whatever the HID descriptor happens to use. SDL's
own macOS table lists at least five incompatible layouts for Microsoft pads
alone, so a single hardcoded `L2_AXIS = 4` cannot be right for all of them.

Confirmed on real hardware 2026-10-22: an Xbox Wireless Controller
(`045e:0b12`) over USB reports the left trigger on **axis 2**, which the app
was drawing as right-stick X — "L2 seems to be moving the right stick".

This module maps a device's real indices onto the canonical layout the rest
of the app assumes:

    axes    0=LX 1=LY 2=RX 3=RY 4=L2 5=R2
    buttons 0=A/Cross 1=B/Circle 2=X/Square 3=Y/Triangle 4=LB/L1 5=RB/R1
            6=View/Share 7=Menu/Options 8=LS/L3 9=RS/R3 10=Guide/PS
    hat 0   d-pad

A profile is (axis_map, button_map, dpad_buttons):
  axis_map[canonical]   -> device axis index
  button_map[canonical] -> device button index, or None when absent
  dpad_buttons          -> (up, down, left, right) device button indices for
                           pads with no hat, else None
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from .control_labels import vid_pid_from_guid

Profile = Tuple[Dict[int, int], Dict[int, Optional[int]], Optional[Tuple[int, int, int, int]]]

# Used when a device already matches our assumptions.
IDENTITY_AXES: Dict[int, int] = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
IDENTITY_BUTTONS: Dict[int, Optional[int]] = {i: i for i in range(11)}

# The classic Microsoft / MFi ordering, and the one SDL's macOS table uses for
# every Xbox entry that is not the 0x0B20 Bluetooth variant:
#   lefttrigger:a2  rightx:a3  righty:a4  righttrigger:a5
#   a:b0 b:b1 x:b2 y:b3 leftshoulder:b4 rightshoulder:b5
#   back:b6 start:b7 leftstick:b8 rightstick:b9 guide:b10
# Buttons already line up with canonical; only the axes are shuffled.
XBOX_CLASSIC: Profile = (
    {0: 0, 1: 1, 2: 3, 3: 4, 4: 2, 5: 5},
    IDENTITY_BUTTONS,
    None,
)

# Xbox Wireless Controller 0x0B20 over Bluetooth, per SDL's own entry
# `030000005e040000200b000011050000`: the triggers are SWAPPED relative to
# everything else (lefttrigger:a5, righttrigger:a4) and the face/meta buttons
# are shifted (x:b3, y:b4, leftshoulder:b6, rightshoulder:b7, back:b10,
# start:b11, guide:b12, leftstick:b13, rightstick:b14).
XBOX_BT_0B20: Profile = (
    {0: 0, 1: 1, 2: 2, 3: 3, 4: 5, 5: 4},
    {0: 0, 1: 1, 2: 3, 3: 4, 4: 6, 5: 7, 6: 10, 7: 11, 8: 13, 9: 14, 10: 12},
    None,
)

# Xbox One wired (0x02D1/0x02DD/0x02E3/0x02EA) and X360 (0x028E): same axis
# shuffle as XBOX_CLASSIC, but the d-pad is buttons b11-b14 with NO hat, and
# the meta buttons sit at back:b9 start:b8 leftstick:b6 rightstick:b7.
XBOX_WIRED_NO_HAT: Profile = (
    {0: 0, 1: 1, 2: 3, 3: 4, 4: 2, 5: 5},
    {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 9, 7: 8, 8: 6, 9: 7, 10: 10},
    (11, 12, 13, 14),
)

_BY_PID: Dict[int, Profile] = {
    0x0B20: XBOX_BT_0B20,
    0x0B12: XBOX_CLASSIC,   # confirmed on hardware, 2026-10-22
    0x0B13: XBOX_CLASSIC,
    0x0B05: XBOX_CLASSIC,
    0x0B00: XBOX_CLASSIC,
    0x0B22: XBOX_CLASSIC,
    0x02E0: XBOX_CLASSIC,
    0x02FD: XBOX_CLASSIC,
    0x02D1: XBOX_WIRED_NO_HAT,
    0x02DD: XBOX_WIRED_NO_HAT,
    0x02E3: XBOX_WIRED_NO_HAT,
    0x02EA: XBOX_WIRED_NO_HAT,
    0x028E: XBOX_WIRED_NO_HAT,
}

VENDOR_MICROSOFT = 0x045E
VENDOR_SONY = 0x054C


def profile_for(guid: Optional[str], num_hats: int, num_buttons: int) -> Profile:
    """Resolve a profile, falling back to identity for unknown hardware.

    Identity is the right fallback rather than a guess: it reproduces the
    behaviour every existing preset was built against, so an unrecognised pad
    behaves exactly as it did before this module existed.

    Sony pads are deliberately left on identity — the DualSense is the
    primary target and its raw-HID layout is what the defaults were written
    for. Do not add a Sony entry without confirming on hardware first; that
    is the mistake this module exists to stop repeating.
    """
    vid, pid = vid_pid_from_guid(guid)
    if vid == VENDOR_MICROSOFT:
        profile = _BY_PID.get(pid)
        if profile is not None:
            return profile
        # Unlisted Microsoft pad: the axis shuffle is near-universal across
        # SDL's Xbox entries, so it is a better bet than identity. Pick the
        # hat-less variant when the device reports no hat.
        return XBOX_CLASSIC if num_hats > 0 else XBOX_WIRED_NO_HAT
    return (IDENTITY_AXES, IDENTITY_BUTTONS, None)
