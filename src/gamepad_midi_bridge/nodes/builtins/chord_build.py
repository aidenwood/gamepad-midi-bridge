"""ChordBuild — from a root note, emit the 3 (or 4) chord-tone notes.

Three outputs: ``note1``, ``note2``, ``note3`` for the chord tones
above the root. Type picks the intervals: major/minor/diminished
triad, or add a 7th tone (out4 is omitted — keep this node 1-in 3-out
to stay simple; users can chain with a parallel Transpose for 4-note
voicings).
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


CHORD_INTERVALS: Dict[str, tuple] = {
    "major":      (4, 7),       # 0, +4, +7
    "minor":      (3, 7),
    "diminished": (3, 6),
    "augmented":  (4, 8),
    "sus2":       (2, 7),
    "sus4":       (5, 7),
    "major_7":    (4, 11),      # root + maj 3 + maj 7 (drop 5 to fit 3 outs)
    "minor_7":    (3, 10),
    "dom_7":      (4, 10),
}


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"note1": raw, "note2": raw, "note3": raw}
    try:
        root = float(raw)
    except (TypeError, ValueError):
        return {"note1": raw, "note2": raw, "note3": raw}
    chord_type = str(params.get("type", "major"))
    third, fifth = CHORD_INTERVALS.get(chord_type, CHORD_INTERVALS["major"])
    return {
        "note1": max(0.0, min(127.0, root)),
        "note2": max(0.0, min(127.0, root + third)),
        "note3": max(0.0, min(127.0, root + fifth)),
    }


SPEC = NodeSpec(
    kind="chord_build",
    label="Chord Build",
    category="music",
    description=(
        "Take a root note and emit a chord's 3 component notes on "
        "separate output pins. Major / minor / diminished / augmented / "
        "sus2 / sus4 triads plus dropped-5 voicings of maj7 / min7 / "
        "dom7. Wire each output to its own sink for instant chord "
        "voicings from a single root-note source."
    ),
    short_description="Root → 3 chord tones.",
    params=(
        ParamSpec("type", "choice", "major",
                  "Chord quality. Triads stay clean across all 3 outputs; 7th chords drop the 5 to keep 3-pin shape.",
                  choices=tuple(CHORD_INTERVALS.keys())),
    ),
    inputs=(PinSpec("in", "in", "Root MIDI note.", expected="scalar"),),
    outputs=(
        PinSpec("note1", "out", "Root note.", expected="scalar"),
        PinSpec("note2", "out", "Third.", expected="scalar"),
        PinSpec("note3", "out", "Fifth (or 7th in 7-chord modes).", expected="scalar"),
    ),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
