"""ScaleQuantize — snap a MIDI note value to the nearest in-scale pitch.

Input is a MIDI note (0..127). Output is the closest pitch that belongs
to ``scale`` rooted at ``key``. Stops a stick-driven note source from
playing wrong notes against a backing track.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


# Scale intervals from the root (semitones). Each is a tuple covering one
# octave; the quantizer extends them across the full MIDI range.
SCALES: Dict[str, tuple] = {
    "chromatic":      (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    "major":          (0, 2, 4, 5, 7, 9, 11),
    "minor":          (0, 2, 3, 5, 7, 8, 10),     # natural minor
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "dorian":         (0, 2, 3, 5, 7, 9, 10),
    "mixolydian":     (0, 2, 4, 5, 7, 9, 10),
    "pentatonic_maj": (0, 2, 4, 7, 9),
    "pentatonic_min": (0, 3, 5, 7, 10),
    "blues":          (0, 3, 5, 6, 7, 10),
    "whole_tone":     (0, 2, 4, 6, 8, 10),
}


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    scale = SCALES.get(str(params.get("scale", "major")), SCALES["major"])
    key = int(params.get("key", 0)) % 12      # 0 = C, 1 = C#, ...
    # Walk every in-scale pitch across the MIDI range, pick the closest.
    best = 0
    best_dist = 999
    for octave in range(-1, 11):
        for step in scale:
            pitch = octave * 12 + step + key
            if 0 <= pitch <= 127:
                d = abs(pitch - v)
                if d < best_dist:
                    best_dist = d
                    best = pitch
    return {"out": float(best)}


SPEC = NodeSpec(
    kind="scale_quantize",
    label="Scale Quantize",
    category="music",
    description=(
        "Snap a continuous note value to the nearest pitch in a chosen "
        "scale + key. Wire after a stick-driven note generator so every "
        "note plays in key against your backing track. Ten built-in "
        "scales covering most performance use cases."
    ),
    short_description="Snap to nearest in-scale pitch.",
    params=(
        ParamSpec("scale", "choice", "major",
                  "Scale family. major/minor/dorian/mixolydian for tonal contexts; pentatonic/blues for jam-friendly safety; whole_tone/chromatic for outside-the-key colour.",
                  choices=tuple(SCALES.keys())),
        ParamSpec("key", "int", 0,
                  "Root note as semitones from C. 0=C, 2=D, 4=E, 5=F, 7=G, 9=A, 11=B; sharps in between.",
                  minimum=0, maximum=11),
    ),
    inputs=(PinSpec("in", "in", "MIDI note (0..127).", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Nearest in-scale pitch.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
