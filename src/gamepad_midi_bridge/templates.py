"""Starter mapping templates for the visual template builder.

Each Template entry has a factory function that builds a fresh Mapping so
callers always receive an independent copy — no shared-state surprises.

Button / axis indices follow the pygame DualSense ordering used throughout
mapping.py and template_builder_tab.py:
  buttons:  0=Cross 1=Circle 2=Square 3=Triangle 4=L1 5=R1
            6=Share 7=Options 8=PS 9=L3 10=R3
  axes:     0=LX 1=LY 2=RX 3=RY 4=L2 5=R2
  hats:     "up"/"down"/"left"/"right"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from .mapping import Mapping, TouchpadConfig


@dataclass(frozen=True)
class Template:
    """One starter mapping template."""
    slug: str
    name: str
    description: str
    tag: str                          # "Drums" | "DJ" | "VJ" | "Synth" | "Modular" | "Streaming"
    build_mapping: Callable[[], Mapping]


# ---------------------------------------------------------------------------
# Factory functions — one per template
# ---------------------------------------------------------------------------

def _build_drum_pad() -> Mapping:
    """Face buttons → GM drum kit notes; L2 = pitch bend proxy via CC 1."""
    m = Mapping(name="Drum Pad")
    m.buttons = {
        0: 36,   # Cross    → Kick (C1)
        1: 38,   # Circle   → Snare (D1)
        2: 42,   # Square   → Closed Hi-Hat (F#1)
        3: 49,   # Triangle → Crash Cymbal (C#3)
        4: 46,   # L1       → Open Hi-Hat (A#1)
        5: 51,   # R1       → Ride Cymbal (D#3)
        6: 41,   # Share    → Low Floor Tom (F1)
        7: 45,   # Options  → Low Tom (A1)
        8: 48,   # PS       → Hi Mid Tom (C2)
        9: 43,   # L3       → High Floor Tom (G1)
        10: 50,  # R3       → High Tom (D2)
    }
    # L2 → Pitch Bend proxy (CC 1), R2 → Modulation (CC 2)
    m.axes = {
        0: 3, 1: 4, 2: 5, 3: 6,
        4: 1,   # L2 → CC 1 (pitch-bend proxy / expression)
        5: 2,   # R2 → CC 2 (modulation)
    }
    m.hats = {"up": 44, "down": 39, "left": 75, "right": 56}
    return m


def _build_dj() -> Mapping:
    """DJ-style: cue buttons, jog-wheel sticks, crossfader + filter on triggers."""
    m = Mapping(name="DJ")
    m.buttons = {
        0: 60,   # Cross    → Hot Cue 1
        1: 61,   # Circle   → Hot Cue 2
        2: 62,   # Square   → Hot Cue 3
        3: 63,   # Triangle → Hot Cue 4
        4: 64,   # L1       → Previous Cue
        5: 65,   # R1       → Next Cue
        6: 66,   # Share    → Play / Pause A
        7: 67,   # Options  → Play / Pause B
        8: 68,   # PS       → Sync
        9: 69,   # L3       → Loop in
        10: 70,  # R3       → Loop out
    }
    # LX/RX = jog wheel X (CC 20 / CC 22), LY/RY = pitch fader (CC 21 / CC 23)
    # L2 = crossfader (CC 8), R2 = filter cutoff (CC 74)
    m.axes = {
        0: 20,  # LX → Jog deck A X
        1: 21,  # LY → Jog deck A Y
        2: 22,  # RX → Jog deck B X
        3: 23,  # RY → Jog deck B Y
        4: 8,   # L2 → Crossfader (CC 8)
        5: 74,  # R2 → Filter cutoff (CC 74)
    }
    m.hats = {"up": 71, "down": 72, "left": 73, "right": 74}
    return m


def _build_vj() -> Mapping:
    """VJ: face buttons launch clips on scene 1 (C-1 = 0 … D#-1 = 3);
    touchpad XY = effect intensity X/Y.
    """
    m = Mapping(name="VJ")
    # Scene 1 clip-launch notes: C-1 (0), C#-1 (1), D-1 (2), D#-1 (3)
    m.buttons = {
        0: 0,    # Cross    → Clip 1 (C-1)
        1: 1,    # Circle   → Clip 2 (C#-1)
        2: 2,    # Square   → Clip 3 (D-1)
        3: 3,    # Triangle → Clip 4 (D#-1)
        4: 4,    # L1       → Clip 5
        5: 5,    # R1       → Clip 6
        6: 6,    # Share    → Clip 7
        7: 7,    # Options  → Clip 8
        8: 8,    # PS       → Blackout / master flash
        9: 9,    # L3       → Clip 9
        10: 10,  # R3       → Clip 10
    }
    m.axes = {
        0: 3, 1: 4, 2: 5, 3: 6,
        4: 1,   # L2 → Effect intensity
        5: 2,   # R2 → Mix / opacity
    }
    m.hats = {"up": 11, "down": 12, "left": 13, "right": 14}
    # Touchpad XY → effect X (CC 16) and effect Y (CC 17)
    m.touchpad = TouchpadConfig(
        enabled=True,
        x_cc=16,
        y_cc=17,
        require_contact=True,
    )
    return m


def _build_synth_lead() -> Mapping:
    """Synth lead: D-pad = scale degrees (notes), sticks = filter + resonance,
    L2/R2 = velocity-curve shaping via CC.
    """
    m = Mapping(name="Synth Lead")
    # Face buttons = chord tones (C major triad + extensions)
    m.buttons = {
        0: 60,   # Cross    → C4 root
        1: 64,   # Circle   → E4 major 3rd
        2: 67,   # Square   → G4 5th
        3: 72,   # Triangle → C5 octave
        4: 62,   # L1       → D4 (2nd)
        5: 69,   # R1       → A4 (6th)
        6: 65,   # Share    → F4 (4th)
        7: 71,   # Options  → B4 (7th)
        8: 74,   # PS       → D5
        9: 59,   # L3       → B3 (leading tone)
        10: 76,  # R3       → E5
    }
    # D-pad = scale degrees C4 (C D E G)
    m.hats = {
        "up":    60,   # D-Up    → C4
        "right": 62,   # D-Right → D4
        "down":  64,   # D-Down  → E4
        "left":  67,   # D-Left  → G4
    }
    # Sticks: LX = filter cutoff (CC 74), LY = resonance (CC 71),
    #         RX = chorus depth (CC 93), RY = reverb send (CC 91)
    # L2 = expression (CC 11), R2 = modulation (CC 1)
    m.axes = {
        0: 74,  # LX → Filter cutoff
        1: 71,  # LY → Resonance
        2: 93,  # RX → Chorus depth
        3: 91,  # RY → Reverb send
        4: 11,  # L2 → Expression (velocity-curve proxy)
        5: 1,   # R2 → Modulation wheel
    }
    return m


def _build_modular() -> Mapping:
    """Eurorack-friendly: every axis → CC 1-8, every button → note 36-50."""
    m = Mapping(name="Modular Control")
    # All axes → CC 1-8 (sequential)
    m.axes = {
        0: 1,   # LX  → CC 1
        1: 2,   # LY  → CC 2
        2: 3,   # RX  → CC 3
        3: 4,   # RY  → CC 4
        4: 5,   # L2  → CC 5
        5: 6,   # R2  → CC 6
    }
    # Touchpad X/Y → CC 7/8 (fills the 8-CC Eurorack block)
    m.touchpad = TouchpadConfig(
        enabled=True,
        x_cc=7,
        y_cc=8,
        require_contact=True,
    )
    # All 11 buttons → notes 36-46 (C2 upward, GM drum range)
    m.buttons = {i: 36 + i for i in range(11)}
    # D-pad → notes 47-50
    m.hats = {"up": 47, "down": 48, "left": 49, "right": 50}
    return m


def _build_obs_streamer() -> Mapping:
    """OBS Streamer: face buttons trigger OBS scenes/sources via CCs;
    sticks control audio faders; triggers = mic/desk mute.
    """
    m = Mapping(name="OBS Streamer")
    # Face buttons → OBS scene/source CCs (map to OBS MIDI plugin bindings)
    m.buttons = {
        0: 60,   # Cross    → Scene 1
        1: 61,   # Circle   → Scene 2
        2: 62,   # Square   → Scene 3
        3: 63,   # Triangle → Scene 4
        4: 64,   # L1       → Scene 5 / source toggle
        5: 65,   # R1       → Scene 6 / source toggle
        6: 66,   # Share    → Start/Stop Recording
        7: 67,   # Options  → Start/Stop Streaming
        8: 68,   # PS       → Studio Mode toggle
        9: 69,   # L3       → Mute mic
        10: 70,  # R3       → Mute desktop audio
    }
    # D-pad = source visibility toggles
    m.hats = {"up": 71, "down": 72, "left": 73, "right": 74}
    # Sticks: LX = mic volume (CC 7), LY = desktop audio (CC 8),
    #         RX = music/source volume (CC 9), RY = monitor mix (CC 10)
    # L2 = transition speed (CC 11), R2 = master audio (CC 12)
    m.axes = {
        0: 7,   # LX → Mic volume
        1: 8,   # LY → Desktop audio
        2: 9,   # RX → Music/source volume
        3: 10,  # RY → Monitor mix
        4: 11,  # L2 → Transition speed
        5: 12,  # R2 → Master audio
    }
    return m


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TEMPLATES: List[Template] = [
    Template(
        slug="drum-pad",
        name="Drum Pad",
        description=(
            "Face buttons fire GM drum-kit notes (kick, snare, hi-hat, crash). "
            "L2 = expression CC, R2 = modulation CC."
        ),
        tag="Drums",
        build_mapping=_build_drum_pad,
    ),
    Template(
        slug="dj",
        name="DJ",
        description=(
            "L1/R1 = prev/next cue. Left/right stick X axes = jog wheel. "
            "L2 = crossfader (CC 8), R2 = filter cutoff (CC 74)."
        ),
        tag="DJ",
        build_mapping=_build_dj,
    ),
    Template(
        slug="vj",
        name="VJ",
        description=(
            "Face buttons launch clips on scene 1 (C-1 … D#-1). "
            "Touchpad XY = effect intensity X/Y (CC 16/17)."
        ),
        tag="VJ",
        build_mapping=_build_vj,
    ),
    Template(
        slug="synth-lead",
        name="Synth Lead",
        description=(
            "D-pad = C major scale degrees. Sticks = filter cutoff + resonance. "
            "L2 = expression, R2 = mod wheel."
        ),
        tag="Synth",
        build_mapping=_build_synth_lead,
    ),
    Template(
        slug="modular-control",
        name="Modular Control",
        description=(
            "Every axis → CC 1-8, touchpad X/Y → CC 7/8, "
            "every button → note 36-46, D-pad → 47-50. Eurorack-friendly."
        ),
        tag="Modular",
        build_mapping=_build_modular,
    ),
    Template(
        slug="obs-streamer",
        name="OBS Streamer",
        description=(
            "Face buttons trigger OBS scenes/sources via CCs. "
            "Sticks = audio fader mix. L3/R3 = mic/desktop mute."
        ),
        tag="Streaming",
        build_mapping=_build_obs_streamer,
    ),
]

# Convenience lookup: slug → Template
TEMPLATES_BY_SLUG = {t.slug: t for t in TEMPLATES}
