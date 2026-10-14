"""Symbolic-sink → MIDI binding resolver.

Phase 1 ships the **raw-MIDI fallback** subset only: symbols of the form
``midi.cc:N@ch:C`` and ``midi.note:N@ch:C`` are parsed directly into a
:class:`RawMidiBinding`. Anything else (Resolume, Ableton, custom
connector symbols) returns ``None`` and the bridge loop logs it for now —
Phase 2 wires per-connector resolvers behind the same interface.

The grammar is intentionally narrow so it's unambiguous:

    midi.cc:<0..127>@ch:<1..16>
    midi.note:<0..127>@ch:<1..16>

Channel is **1-based** in the symbol (matches every DAW + Resolume) and
**0-based** in the MIDI status byte (matches python-rtmidi). Conversion
happens here so callers never have to think about it.

The resolver is the single source of truth for "what does this symbol
do?" — Phase 2 will extend it with a connector lookup table without
changing this API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional


_CC_PATTERN = re.compile(r"^midi\.cc:(\d+)@ch:(\d+)$")
_NOTE_PATTERN = re.compile(r"^midi\.note:(\d+)@ch:(\d+)$")


@dataclass(frozen=True)
class RawMidiBinding:
    """A resolved symbol — what to emit on the MIDI port for one Send.

    ``kind`` picks the status byte family:
        "cc"   → 0xB0 | channel
        "note" → 0x90 | channel for on, 0x80 | channel for off
    """
    kind: Literal["cc", "note"]
    channel: int   # 0..15, MIDI-status-byte form (already 0-indexed)
    number: int    # 0..127, CC number OR note number


def resolve(symbol: str) -> Optional[RawMidiBinding]:
    """Parse a symbol into a binding, or return None if not a raw form.

    None means "I don't know what to do with this" — callers should fall
    back to logging in Phase 1, or to a Phase-2 connector resolver later.
    """
    m = _CC_PATTERN.match(symbol)
    if m:
        number = int(m.group(1))
        ch_1based = int(m.group(2))
        if not (0 <= number <= 127) or not (1 <= ch_1based <= 16):
            return None
        return RawMidiBinding(kind="cc", channel=ch_1based - 1, number=number)
    m = _NOTE_PATTERN.match(symbol)
    if m:
        number = int(m.group(1))
        ch_1based = int(m.group(2))
        if not (0 <= number <= 127) or not (1 <= ch_1based <= 16):
            return None
        return RawMidiBinding(kind="note", channel=ch_1based - 1, number=number)
    return None


def value_to_midi(binding: RawMidiBinding, value: object) -> Optional[tuple]:
    """Turn a Send's value into a 3-byte MIDI message for `binding`.

    Returns None when the value can't be coerced (e.g. tuple feeding a
    raw scalar sink, or None) — caller should skip emission.

    Value semantics:
        * For CC:   scalar 0..1 → 0..127, scalar >1 assumed already 0..127,
                    bool → 127/0.
        * For note: bool decides on/off (velocity 100 / 0); scalar 0..1 →
                    velocity 0..127; scalar >1 assumed already 0..127.
                    Velocity 0 still emits a note-off byte (0x80).
    """
    if value is None or isinstance(value, tuple):
        return None
    if binding.kind == "cc":
        v = _scalar_to_127(value)
        return (0xB0 | binding.channel, binding.number & 0x7F, v)
    # note
    if isinstance(value, bool):
        velocity = 100 if value else 0
    else:
        velocity = _scalar_to_127(value)
    if velocity <= 0:
        return (0x80 | binding.channel, binding.number & 0x7F, 0)
    return (0x90 | binding.channel, binding.number & 0x7F, velocity)


def _scalar_to_127(value: object) -> int:
    """Coerce 0..1, 0..127, or bool to a clamped MIDI byte."""
    if isinstance(value, bool):
        return 127 if value else 0
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    if 0.0 <= v <= 1.0:
        v *= 127.0
    return max(0, min(127, int(round(v))))
