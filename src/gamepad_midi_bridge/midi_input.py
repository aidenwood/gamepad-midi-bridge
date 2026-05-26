"""Cross-platform virtual MIDI INPUT port (haptic-in feature).

Mirror image of `midi_backend.py` — same shape, same OS quirks.

macOS / Linux: rtmidi's CoreMIDI / ALSA backends create a true virtual input
port other apps publish into. Windows has no kernel virtual-port primitive,
so we attach to an existing loopMIDI port by name (users wanting haptic-in
on Windows create a port like "Universal Controller MIDI (in)" in loopMIDI
the same way they do for output).

The rtmidi callback fires on librtmidi's own C thread. The bridge layer
(`BridgeWorker._on_midi_in`) is responsible for marshalling the work back
onto a Qt-safe thread — this module just hands raw `(message, data)` pairs
through.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, List, Optional

import rtmidi


# Distinct name from the output port so DAWs don't get confused routing both
# directions to the same endpoint. Marketing name: "haptic-in".
INPUT_PORT_NAME = "Universal Controller MIDI (in)"
WINDOWS_FALLBACK_INPUT_NAMES = (
    "Universal Controller MIDI (in)",
    "Universal Controller MIDI in",
    "ps5-bridge-in",
)


@dataclass
class OpenedInputPort:
    """Thin wrapper so the worker can keep the handle + diagnostic info."""
    port: rtmidi.MidiIn
    name: str
    virtual: bool


class MidiInputError(Exception):
    """Raised when no virtual MIDI input port can be created or opened."""


def list_input_ports() -> List[str]:
    inp = rtmidi.MidiIn()
    try:
        return list(inp.get_ports())
    finally:
        del inp


def open_input_port(preferred_name: str = INPUT_PORT_NAME) -> OpenedInputPort:
    """Open (or create) a MIDI input port.

    Mac/Linux: creates a fresh virtual port so DAWs can route into us.
    Windows: looks for an existing loopMIDI port matching `preferred_name`
    (or one of the legacy fallbacks). Raises MidiInputError when nothing
    matches so the GUI can prompt for loopMIDI setup.
    """
    inp = rtmidi.MidiIn()

    if sys.platform == "win32":
        ports = inp.get_ports()
        for i, name in enumerate(ports):
            lowered = name.lower()
            if preferred_name.lower() in lowered or any(
                fb.lower() in lowered for fb in WINDOWS_FALLBACK_INPUT_NAMES
            ):
                inp.open_port(i)
                # Ignore SysEx/MTC/active-sense — we only care about Notes/CCs
                # and the firehose of timing messages just wastes callback time.
                inp.ignore_types(sysex=True, timing=True, active_sense=True)
                return OpenedInputPort(port=inp, name=name, virtual=False)
        del inp
        raise MidiInputError(
            "No loopMIDI input port found. Create a port named "
            f"'{preferred_name}' in loopMIDI, then try again."
        )

    # macOS / Linux — make a real virtual input port
    try:
        inp.open_virtual_port(preferred_name)
        inp.ignore_types(sysex=True, timing=True, active_sense=True)
        return OpenedInputPort(port=inp, name=preferred_name, virtual=True)
    except Exception as e:
        del inp
        raise MidiInputError(f"Could not create virtual MIDI input port: {e}") from e


def set_callback(opened: OpenedInputPort,
                 callback: Callable[[tuple, object], None]) -> None:
    """Attach a callback that fires on every incoming message.

    rtmidi invokes the callback on its own C thread (NOT the Qt main loop
    and NOT the BridgeWorker's QThread). The callback signature is
    `(message_tuple, data)` where `message_tuple` is `([bytes...], deltatime)`.
    Caller must keep the work non-blocking — block here and you stall every
    other MIDI source feeding the same port.
    """
    opened.port.set_callback(callback)


def close_input_port(opened: Optional[OpenedInputPort]) -> None:
    """Symmetric cleanup. Cancels the callback first so we don't get a stray
    callback fired while the underlying handle is mid-tear-down."""
    if opened is None:
        return
    try:
        opened.port.cancel_callback()
    except Exception:
        pass
    try:
        opened.port.close_port()
    except Exception:
        pass
    try:
        del opened.port
    except Exception:
        pass
