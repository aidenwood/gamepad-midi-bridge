"""Ableton Live Remote Script entry point for Gamepad MIDI Bridge.

Live discovers Remote Scripts by importing the folder as a package and calling
`create_instance(c_instance)`. The returned object must be a ControlSurface
subclass. `get_capabilities()` is optional but recommended on Live 11+ so the
Surface dropdown can show metadata.

Live 11+ / Python 3 only. Do not redistribute Ableton's `_Framework` source —
this script imports it at runtime from the host's bundled Python environment.
"""
from __future__ import absolute_import

from .GamepadMidiBridge import GamepadMidiBridge


def create_instance(c_instance):
    """Live calls this once when the user picks the Surface from Preferences."""
    return GamepadMidiBridge(c_instance)


def get_capabilities():
    """Optional metadata for Live 11+'s Control Surface picker."""
    # Constants live in _Framework.Capabilities in Live 11/12. Import lazily so
    # the module still loads on older builds even if the dropdown can't display
    # extras — `create_instance` will still work.
    try:
        from _Framework.Capabilities import (
            CONTROLLER_ID_KEY,
            PORTS_KEY,
            NOTES_CC,
            SCRIPT,
            REMOTE,
            controller_id,
            inport,
            outport,
        )
    except Exception:
        return {}

    return {
        CONTROLLER_ID_KEY: controller_id(
            vendor_id=0x0000,
            product_ids=[0x0000],
            model_name=["Gamepad MIDI Bridge"],
        ),
        PORTS_KEY: [
            inport(props=[NOTES_CC, SCRIPT, REMOTE]),
            outport(props=[SCRIPT, REMOTE]),
        ],
    }
