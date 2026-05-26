"""Cross-platform virtual MIDI port.

macOS and Linux: rtmidi can create a virtual port directly (CoreMIDI / ALSA).
Windows: no kernel virtual-port support. We connect to an existing loopMIDI
port if present, otherwise return a clear error the GUI can act on.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional

import rtmidi


DEFAULT_PORT_NAME = "Gamepad MIDI Bridge"
WINDOWS_FALLBACK_NAME = "ps5-bridge"   # matches the original script for upgraders


@dataclass
class OpenedPort:
    port: rtmidi.MidiOut
    name: str
    virtual: bool


class MidiPortError(Exception):
    """Raised when no virtual MIDI port can be created or opened."""


def list_output_ports() -> List[str]:
    out = rtmidi.MidiOut()
    try:
        return list(out.get_ports())
    finally:
        del out


def open_port(preferred_name: str = DEFAULT_PORT_NAME) -> OpenedPort:
    """Open (or create) a MIDI output port.

    On macOS/Linux this creates a fresh virtual port other apps can subscribe to.
    On Windows it looks for an existing loopMIDI port matching `preferred_name`
    or the legacy `ps5-bridge` name; if none found, raises MidiPortError so the
    GUI can prompt for loopMIDI setup.
    """
    out = rtmidi.MidiOut()

    if sys.platform == "win32":
        ports = out.get_ports()
        for i, name in enumerate(ports):
            lowered = name.lower()
            if preferred_name.lower() in lowered or WINDOWS_FALLBACK_NAME in lowered:
                out.open_port(i)
                return OpenedPort(port=out, name=name, virtual=False)
        del out
        raise MidiPortError(
            "No loopMIDI port found. Create a port named "
            f"'{preferred_name}' in loopMIDI, then try again."
        )

    # macOS / Linux — create a true virtual port
    try:
        out.open_virtual_port(preferred_name)
        return OpenedPort(port=out, name=preferred_name, virtual=True)
    except Exception as e:
        del out
        raise MidiPortError(f"Could not create virtual MIDI port: {e}") from e


def close_port(opened: Optional[OpenedPort]) -> None:
    if opened is None:
        return
    try:
        opened.port.close_port()
    except Exception:
        pass
    try:
        del opened.port
    except Exception:
        pass
