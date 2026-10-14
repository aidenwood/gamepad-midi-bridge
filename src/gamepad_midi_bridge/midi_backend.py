"""Cross-platform virtual MIDI port.

macOS and Linux: rtmidi can create a virtual port directly (CoreMIDI / ALSA).
Windows: no kernel virtual-port support, so there is a tiered fallback so the
app ALWAYS sends MIDI somewhere instead of dead-ending:

  1. An existing loopMIDI port (proper app-to-app routing into a DAW).
  2. The built-in Microsoft GS Wavetable Synth — ships on every Windows box,
     so the user hears their controller play notes instantly with zero install.
  3. Any other available output port (e.g. a hardware synth).

Only when Windows reports zero output ports do we raise MidiPortError.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional

import rtmidi


DEFAULT_PORT_NAME = "Universal Controller MIDI"
# Legacy port names we'll auto-match on Windows so users upgrading from
# beta/loopMIDI configurations don't have to rebuild their routing.
WINDOWS_FALLBACK_NAMES = ("ps5-bridge", "Universal Controller MIDI")
# Any loopMIDI port counts as a real routing target, even when the user never
# renamed it — loopMIDI names its default port "loopMIDI Port", so match the
# tool's own name so auto-detect works out of the box after a fresh install.
WINDOWS_LOOPMIDI_HINTS = ("loopmidi",)
# Built-in software synth present on every Windows install. Last-resort target
# so notes are audible immediately — not routable to a DAW, but it proves the
# bridge works and lets the user play without installing loopMIDI first.
WINDOWS_BUILTIN_SYNTH_HINTS = ("wavetable", "microsoft gs", "gs wavetable")


@dataclass
class OpenedPort:
    port: rtmidi.MidiOut
    name: str
    virtual: bool
    # True when we landed on a real downstream port (Windows fallback) rather
    # than a loopMIDI/virtual port. Audible, but not routable into a DAW — the
    # GUI uses this to nudge the user toward loopMIDI for production routing.
    fallback: bool = False


class MidiPortError(Exception):
    """Raised when no virtual MIDI port can be created or opened."""


def list_output_ports() -> List[str]:
    out = rtmidi.MidiOut()
    try:
        return list(out.get_ports())
    finally:
        del out


def _find_port(ports: List[str], *, names: tuple = (), hints: tuple = ()) -> Optional[int]:
    """Return the first port index whose name contains any name/hint, else None."""
    for i, name in enumerate(ports):
        lowered = name.lower()
        if any(n.lower() in lowered for n in names) or any(h in lowered for h in hints):
            return i
    return None


def open_port(preferred_name: str = DEFAULT_PORT_NAME) -> OpenedPort:
    """Open (or create) a MIDI output port.

    On macOS/Linux this creates a fresh virtual port other apps can subscribe to.
    On Windows it walks the tiered fallback documented in the module docstring so
    the app is always sending MIDI somewhere audible; it only raises
    MidiPortError when Windows exposes no output ports at all.
    """
    out = rtmidi.MidiOut()

    if sys.platform == "win32":
        ports = out.get_ports()
        if not ports:
            del out
            raise MidiPortError(
                "Windows reports no MIDI output ports at all. Install loopMIDI "
                "to create one, then click Start again."
            )

        # 1. A loopMIDI / named routing port — real app-to-app routing into a
        #    DAW. Prefer a port carrying our own (or legacy) name, then fall back
        #    to ANY loopMIDI port so a freshly-installed default "loopMIDI Port"
        #    is auto-detected without the user renaming it.
        idx = _find_port(ports, names=(preferred_name, *WINDOWS_FALLBACK_NAMES))
        if idx is None:
            idx = _find_port(ports, hints=WINDOWS_LOOPMIDI_HINTS)
        if idx is not None:
            out.open_port(idx)
            return OpenedPort(port=out, name=ports[idx], virtual=False)

        # 2. Built-in Microsoft GS Wavetable Synth — instant audible fallback.
        idx = _find_port(ports, hints=WINDOWS_BUILTIN_SYNTH_HINTS)
        if idx is None:
            # 3. Anything else that's available (e.g. a hardware synth).
            idx = 0
        out.open_port(idx)
        return OpenedPort(port=out, name=ports[idx], virtual=False, fallback=True)

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
