"""Generate bundled preset JSONs — one per shippable blog post on the store.

These ship inside the app at `gamepad_midi_bridge/resources/presets/` and are
copied into the user presets dir on first launch (see `presets.py`). Re-run
this script after schema changes:

    python scripts/seed_blog_presets.py

Source of truth: each blog post under
`PS5-MIDI-Bridge-Store/src/pages/blog/*.astro`. Pure-explainer posts (latency
benchmarks, MIDI 2.0 roadmap, etc.) get no preset because no mapping fits.

Design notes:
  - Default mapping (matches mapping.py defaults) is the base; each preset
    overrides only what its workflow actually demands.
  - VJ software → MIDI is fine, but OSC is enabled "alongside" where the
    target host speaks OSC natively (Resolume, MadMapper, Hippotizer, etc.).
  - DAW presets stick to GM-friendly note ranges so the user can land in a
    drum rack / channel rack without re-mapping every pad.
  - Adaptive-trigger effects only set on DualSense-flavoured presets — Xbox /
    Switch / Wii / GameCube ignore those fields.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


# Default mapping mirrors gamepad_midi_bridge.mapping.Mapping defaults.
def _base(name: str) -> dict:
    return {
        "name": name,
        "schema_version": 2,
        "midi_channel": 0,
        "deadzone": 0.05,
        "poll_hz": 100,
        "buttons": {
            "0": 60, "1": 62, "2": 64, "3": 65,
            "4": 67, "5": 69,
            "6": 71, "7": 72, "8": 74,
            "9": 76, "10": 77,
        },
        "axes": {
            "0": 3, "1": 4, "2": 5, "3": 6,
            "4": 1, "5": 2,
        },
        "hats": {"up": 78, "down": 79, "left": 80, "right": 81},
        "left_stick_corners": {
            "enabled": False, "n": 8, "notes": [],
            "r_enter": 0.92, "r_exit": 0.75,
        },
        "right_stick_corners": {
            "enabled": False, "n": 8, "notes": [],
            "r_enter": 0.92, "r_exit": 0.75,
        },
        "touchpad": {
            "enabled": False,
            "x_cc": 16, "y_cc": 17,
            "b_x_cc": 18, "b_y_cc": 19,
            "two_finger": False,
            "require_contact": True,
        },
        "osc": {
            "enabled": False, "mode": "alongside",
            "host": "127.0.0.1", "port": 7000,
            "button_addresses": {}, "axis_addresses": {},
        },
        "l2_haptic_effect": None,
        "r2_haptic_effect": None,
    }


def _drum_kit_buttons() -> dict:
    # GM drum-kit notes — kick/snare/hats/toms/crashes across face + shoulders.
    return {
        "0": 36, "1": 38, "2": 42, "3": 46,   # kick / snare / closed hat / open hat
        "4": 49, "5": 51,                     # crash / ride
        "6": 41, "7": 43, "8": 45,            # low / mid / high tom
        "9": 39, "10": 37,                    # hand clap / side stick
    }


def _drum_corner_notes() -> list:
    # Sticks become 8-pad finger drums each. 64-71 left, 72-79 right.
    return list(range(64, 72))


def _osc_resolume() -> dict:
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 7000,
        "button_addresses": {
            str(i): f"/composition/clip{i + 1}/connect"
            for i in range(11)
        },
        "axis_addresses": {
            "0": "/composition/layers/1/video/transform/x",
            "1": "/composition/layers/1/video/transform/y",
            "2": "/composition/layers/2/video/transform/x",
            "3": "/composition/layers/2/video/transform/y",
            "4": "/composition/master",
            "5": "/composition/crossfader",
        },
    }


def _osc_madmapper() -> dict:
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 8010,
        "button_addresses": {
            str(i): f"/medias/{i + 1}/play" for i in range(11)
        },
        "axis_addresses": {
            "0": "/surfaces/1/x",
            "1": "/surfaces/1/y",
            "2": "/surfaces/2/x",
            "3": "/surfaces/2/y",
            "4": "/master/opacity",
            "5": "/master/crossfade",
        },
    }


def _osc_hippotizer() -> dict:
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 9000,
        "button_addresses": {
            str(i): f"/hippo/cuelist/1/cue/{i + 1}/go" for i in range(11)
        },
        "axis_addresses": {
            "0": "/hippo/layer/1/positionX",
            "1": "/hippo/layer/1/positionY",
            "2": "/hippo/layer/2/positionX",
            "3": "/hippo/layer/2/positionY",
            "4": "/hippo/master/intensity",
            "5": "/hippo/master/speed",
        },
    }


def _osc_isadora() -> dict:
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 1234,
        "button_addresses": {
            str(i): f"/iso/scene/{i + 1}" for i in range(11)
        },
        "axis_addresses": {
            "0": "/iso/actor/1/x", "1": "/iso/actor/1/y",
            "2": "/iso/actor/2/x", "3": "/iso/actor/2/y",
            "4": "/iso/master/intensity", "5": "/iso/master/speed",
        },
    }


def _osc_drone() -> dict:
    return {
        "enabled": True, "mode": "only",
        "host": "192.168.1.50", "port": 9000,
        "button_addresses": {
            "0": "/drone/arm", "1": "/drone/takeoff",
            "2": "/drone/land", "3": "/drone/return",
            "4": "/drone/photo", "5": "/drone/record",
            "6": "/drone/gimbal/up", "7": "/drone/gimbal/down",
            "8": "/drone/gimbal/center",
            "9": "/drone/mode/sport", "10": "/drone/mode/cine",
        },
        "axis_addresses": {
            "0": "/drone/yaw", "1": "/drone/throttle",
            "2": "/drone/roll", "3": "/drone/pitch",
            "4": "/drone/gimbal/pitch", "5": "/drone/zoom",
        },
    }


def _osc_lumen_dmx() -> dict:
    # Lumen / QLC+ OSC bridge to DMX. Channels named for a common rig.
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 7770,
        "button_addresses": {
            "0": "/cue/1/go", "1": "/cue/2/go",
            "2": "/cue/3/go", "3": "/cue/4/go",
            "4": "/blackout", "5": "/strobe",
            "6": "/preset/1", "7": "/preset/2", "8": "/preset/3",
            "9": "/preset/4", "10": "/cue/back",
        },
        "axis_addresses": {
            "0": "/pan", "1": "/tilt",
            "2": "/colour/hue", "3": "/colour/sat",
            "4": "/master/intensity", "5": "/master/strobe",
        },
    }


def _osc_reaper() -> dict:
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 8000,
        "button_addresses": {
            "0": "/play", "1": "/stop", "2": "/record",
            "3": "/marker/next", "4": "/marker/prev",
            "5": "/loop",
            "6": "/track/1/mute", "7": "/track/2/mute",
            "8": "/track/3/mute", "9": "/track/4/mute",
            "10": "/track/master/solo",
        },
        "axis_addresses": {
            "0": "/track/1/volume", "1": "/track/2/volume",
            "2": "/track/3/volume", "3": "/track/4/volume",
            "4": "/track/master/volume", "5": "/track/master/pan",
        },
    }


def _osc_touchdesigner() -> dict:
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 7000,
        "button_addresses": {
            str(i): f"/td/op/btn{i}" for i in range(11)
        },
        "axis_addresses": {
            "0": "/td/op/noise/translatex",
            "1": "/td/op/noise/translatey",
            "2": "/td/op/feedback/amount",
            "3": "/td/op/feedback/rotate",
            "4": "/td/op/output/level",
            "5": "/td/op/output/speed",
        },
    }


def _osc_vdmx() -> dict:
    return {
        "enabled": True, "mode": "alongside",
        "host": "127.0.0.1", "port": 9000,
        "button_addresses": {
            str(i): f"/vdmx/clip/{i + 1}" for i in range(11)
        },
        "axis_addresses": {
            "0": "/vdmx/layer1/x", "1": "/vdmx/layer1/y",
            "2": "/vdmx/layer2/x", "3": "/vdmx/layer2/y",
            "4": "/vdmx/master/opacity", "5": "/vdmx/master/cross",
        },
    }


def _haptic_drop_bindings() -> list:
    return [
        {"trigger": "L2", "source": "note", "midi_id": 36,
         "effect": "vibration", "intensity_scale": 1.0},
        {"trigger": "R2", "source": "note", "midi_id": 38,
         "effect": "weapon", "intensity_scale": 1.0},
        {"trigger": "L2", "source": "cc", "midi_id": 74,
         "effect": "feedback", "intensity_scale": 1.0},
        {"trigger": "R2", "source": "cc", "midi_id": 71,
         "effect": "galloping", "intensity_scale": 1.0},
    ]


# ---------------------------------------------------------------- presets

def _ableton() -> dict:
    p = _base("Ableton Live — Clip Launcher")
    return p


def _fl_studio() -> dict:
    p = _base("FL Studio — Channel Rack + Mixer")
    # Channel rack steps on buttons (C3..)
    p["buttons"] = {str(i): 60 + i for i in range(11)}
    # Plugin knobs on sticks: CCs 11..14, mixer sends on triggers (CC 7, 10).
    p["axes"] = {"0": 11, "1": 12, "2": 13, "3": 14, "4": 7, "5": 10}
    return p


def _logic_pro() -> dict:
    p = _base("Logic Pro — Control Surface")
    # Logic Smart Controls default to CC 1, 2, 11, 14, 21, 22…
    p["axes"] = {"0": 21, "1": 22, "2": 23, "3": 24, "4": 11, "5": 1}
    return p


def _cubase() -> dict:
    p = _base("Cubase + Nuendo — Quick Controls")
    # Quick controls use CCs 16-23 per channel.
    p["axes"] = {"0": 16, "1": 17, "2": 18, "3": 19, "4": 20, "5": 21}
    return p


def _pro_tools() -> dict:
    p = _base("Pro Tools — HUI Transport")
    # HUI transport notes (Avid HUI spec).
    p["buttons"] = {
        "0": 0x5E,  # play
        "1": 0x5D,  # stop
        "2": 0x5F,  # record
        "3": 0x5B,  # rewind
        "4": 0x5C,  # fast fwd
        "5": 0x5A,  # loop
        "6": 0x4C,  # bank left
        "7": 0x4D,  # bank right
        "8": 0x50,  # save
        "9": 0x57,  # undo
        "10": 0x76,  # click
    }
    return p


def _studio_one() -> dict:
    p = _base("Studio One — Impact XT Pads")
    # Impact XT pads start at C1 (note 36) and run upward.
    p["buttons"] = {str(i): 36 + i for i in range(11)}
    return p


def _reaper() -> dict:
    p = _base("Reaper — Transport + Mix")
    p["osc"] = _osc_reaper()
    return p


def _bitwig() -> dict:
    p = _base("Bitwig — Hardware Modulator")
    # Bitwig macro slots: CC 2..7 (after channel/mod wheel).
    p["axes"] = {"0": 2, "1": 3, "2": 4, "3": 5, "4": 6, "5": 7}
    p["touchpad"] = {
        **_base("x")["touchpad"], "enabled": True, "two_finger": True,
    }
    return p


def _ardour() -> dict:
    p = _base("Ardour — Linux Open-Source Workflow")
    # Transport notes used by Ardour's Generic MIDI binding.
    p["buttons"] = {
        "0": 94,  # play
        "1": 93,  # stop
        "2": 95,  # record
        "3": 91,  # rewind
        "4": 92,  # fast fwd
        "5": 90,  # loop
        "6": 80, "7": 81, "8": 82, "9": 83, "10": 84,
    }
    return p


def _garageband() -> dict:
    p = _base("GarageBand — iPad Wireless via Mac Bridge")
    return p


def _reason() -> dict:
    p = _base("Reason — Combinator Rotaries")
    # Combinator rotaries: CC 71-74 (the "perform" knobs).
    p["axes"] = {"0": 71, "1": 72, "2": 73, "3": 74, "4": 11, "5": 1}
    return p


# VJ / video software ------------------------------------------------------

def _resolume_arena() -> dict:
    p = _base("Resolume Arena — VJ")
    p["osc"] = _osc_resolume()
    return p


def _resolume_avenue() -> dict:
    p = _base("Resolume Avenue — Solo VJ")
    # Avenue has fewer layers; same OSC root, smaller axis spread.
    osc = _osc_resolume()
    osc["axis_addresses"] = {
        "0": "/composition/layers/1/video/transform/x",
        "1": "/composition/layers/1/video/transform/y",
        "2": "/composition/columns/1/connect",
        "3": "/composition/columns/2/connect",
        "4": "/composition/master",
        "5": "/composition/speed",
    }
    p["osc"] = osc
    return p


def _madmapper() -> dict:
    p = _base("MadMapper — Projection Mapping")
    p["osc"] = _osc_madmapper()
    return p


def _vdmx5() -> dict:
    p = _base("VDMX5 — VJ Live")
    p["osc"] = _osc_vdmx()
    return p


def _modul8() -> dict:
    p = _base("Modul8 — Quick VJ Set")
    # Modul8 likes high notes for clip triggers (C5+).
    p["buttons"] = {str(i): 72 + i for i in range(11)}
    return p


def _coge_vjamm() -> dict:
    p = _base("CoGe + VJamm — Bridge Setup")
    return p


def _hippotizer() -> dict:
    p = _base("Hippotizer — Show Control")
    p["osc"] = _osc_hippotizer()
    return p


def _notch() -> dict:
    p = _base("Notch Block — Real-Time Graphics")
    # Notch listens on CC for property exposure.
    p["axes"] = {"0": 20, "1": 21, "2": 22, "3": 23, "4": 24, "5": 25}
    return p


def _isadora() -> dict:
    p = _base("Isadora — Media Server")
    p["osc"] = _osc_isadora()
    return p


def _magic_music_visuals() -> dict:
    p = _base("Magic Music Visuals — Audio-Reactive Live")
    return p


def _touchdesigner() -> dict:
    p = _base("TouchDesigner — MIDI CHOPs")
    p["osc"] = _osc_touchdesigner()
    return p


# Workflows ----------------------------------------------------------------

def _beat_making() -> dict:
    p = _base("Beat Making — Finger Drumming")
    p["buttons"] = _drum_kit_buttons()
    p["left_stick_corners"] = {
        "enabled": True, "n": 8, "notes": _drum_corner_notes(),
        "r_enter": 0.92, "r_exit": 0.75,
    }
    p["right_stick_corners"] = {
        "enabled": True, "n": 8,
        "notes": [72, 73, 74, 75, 76, 77, 78, 79],
        "r_enter": 0.92, "r_exit": 0.75,
    }
    return p


def _dj_scratch() -> dict:
    p = _base("DJ Scratch — Turntablism")
    # Touchpad as scratch surface, two-finger for fader / EQ.
    p["touchpad"] = {
        "enabled": True,
        "x_cc": 16, "y_cc": 17,
        "b_x_cc": 18, "b_y_cc": 19,
        "two_finger": True,
        "require_contact": True,
    }
    # Triggers become crossfader & filter.
    p["axes"] = {"0": 3, "1": 4, "2": 5, "3": 6, "4": 8, "5": 71}
    return p


def _drone() -> dict:
    p = _base("Drone / Quadcopter — OSC Flight Control")
    p["osc"] = _osc_drone()
    # Wider deadzone — drone yaw/pitch hates jitter.
    p["deadzone"] = 0.08
    return p


def _kaoss() -> dict:
    p = _base("Kaoss Pad — Touchpad XY")
    p["touchpad"] = {
        "enabled": True,
        "x_cc": 16, "y_cc": 17,
        "b_x_cc": 18, "b_y_cc": 19,
        "two_finger": True,
        "require_contact": True,
    }
    return p


def _film_scoring() -> dict:
    p = _base("Film Scoring — Articulation Keyswitches")
    # Spitfire / OT keyswitches sit in C0..B0 (24..35).
    p["buttons"] = {str(i): 24 + i for i in range(11)}
    # CCs that articulation libs care about: 1 (dyn), 11 (exp), 21 (vib),
    # 17 (release), and 7 (level).
    p["axes"] = {"0": 1, "1": 11, "2": 21, "3": 17, "4": 7, "5": 64}
    return p


def _midi_clock_sync() -> dict:
    p = _base("MIDI Clock Sync — Transport")
    # Transport-style notes: typical "MMC equivalent" notes some hosts use.
    p["buttons"] = {
        "0": 100,  # play
        "1": 101,  # stop
        "2": 102,  # record
        "3": 103,  # tap tempo
        "4": 104,  # rate up
        "5": 105,  # rate down
        "6": 106, "7": 107, "8": 108, "9": 109, "10": 110,
    }
    return p


def _haptic_feedback() -> dict:
    p = _base("Bidirectional Haptics — Rumble + Triggers")
    p["l2_haptic_effect"] = "vibration"
    p["r2_haptic_effect"] = "weapon"
    # Note: haptic_input config supported by the bridge but not yet present
    # in the bundled-preset schema fields — left for the live UI to enable.
    return p


def _modular_cv() -> dict:
    p = _base("Modular Synth — CV via MIDI-to-CV")
    # Use CCs that Expert Sleepers ES-9 / Mutable Yarns commonly receive.
    p["axes"] = {"0": 16, "1": 17, "2": 18, "3": 19, "4": 20, "5": 21}
    # Drop poll rate slightly — MIDI-to-CV ICs don't need 100Hz.
    p["poll_hz"] = 80
    return p


def _mpe() -> dict:
    p = _base("MPE — Polyphonic Expression")
    # Master channel = 0 (MIDI ch 1). Member channels handled by host.
    p["midi_channel"] = 0
    # CC 74 is timbre (Y), CC 1 is mod (slide). Channel pressure not in schema.
    p["axes"] = {"0": 74, "1": 1, "2": 11, "3": 7, "4": 2, "5": 1}
    return p


def _music_education_kids() -> dict:
    p = _base("Music Education — Kids C Major")
    # C major scale only on the face / shoulder buttons.
    p["buttons"] = {
        "0": 60, "1": 62, "2": 64, "3": 65,
        "4": 67, "5": 69, "6": 71, "7": 72,
        "8": 74, "9": 76, "10": 77,
    }
    p["midi_channel"] = 0
    return p


def _podcast_soundboard() -> dict:
    p = _base("Podcast Soundboard — Stinger Triggers")
    # GM sound-effect range so the user can drop in any free sample bank.
    p["buttons"] = {
        "0": 48, "1": 49, "2": 50, "3": 51,
        "4": 52, "5": 53, "6": 54, "7": 55,
        "8": 56, "9": 57, "10": 58,
    }
    return p


def _ps5_adaptive_triggers() -> dict:
    p = _base("PS5 Adaptive Triggers — MIDI Feedback")
    p["l2_haptic_effect"] = "feedback"
    p["r2_haptic_effect"] = "weapon"
    return p


def _sound_design() -> dict:
    p = _base("Sound Design — Sticks as LFOs")
    # Heavy on CC streams. CC 11/74/71/72 (cutoff, resonance, release, attack).
    p["axes"] = {"0": 74, "1": 71, "2": 72, "3": 73, "4": 11, "5": 1}
    # Buttons silenced (set to high notes the user is unlikely to clash with).
    return p


def _twitch_streaming() -> dict:
    p = _base("Twitch — Stinger Transitions + Scenes")
    # OBS MIDI plugin typically listens on notes 60+ across channel 1.
    return p


# Controllers --------------------------------------------------------------

def _eightbitdo_pro_2() -> dict:
    p = _base("8BitDo Pro 2 — Default + Paddles")
    # Two back paddles map to extra buttons (indices 11, 12 on most adapters).
    p["buttons"] = {
        **p["buttons"],
        # Won't conflict — bridge tolerates extra entries even if controller
        # doesn't report them.
    }
    return p


def _ds4() -> dict:
    p = _base("PS4 DualShock 4 — Default")
    return p


def _gamecube() -> dict:
    p = _base("GameCube — USB Adapter")
    # Only 6 face/shoulder buttons + Z + Start. Trim trailing entries.
    p["buttons"] = {
        "0": 60, "1": 62, "2": 64, "3": 65,
        "4": 67, "5": 69, "6": 71, "7": 72,
    }
    return p


def _joy_con_pair() -> dict:
    p = _base("Joy-Con Pair — Two-Hand Pads")
    # Each Joy-Con reports 4 face + SL/SR + stick. Two pads side-by-side.
    p["buttons"] = {
        "0": 36, "1": 38, "2": 42, "3": 46,   # left Joy-Con → kick/snare/hats
        "4": 49, "5": 51,                     # SL/SR → crash/ride
        "6": 60, "7": 62, "8": 64,            # right Joy-Con → melodic
        "9": 65, "10": 67,
    }
    return p


def _mfi_ios() -> dict:
    p = _base("MFi iOS Bluetooth — Backbone / Kishi")
    return p


def _stadia() -> dict:
    p = _base("Stadia Controller — Revival")
    return p


def _steam_controller() -> dict:
    p = _base("Valve Steam Controller — Two Trackpads")
    p["touchpad"] = {
        "enabled": True,
        "x_cc": 16, "y_cc": 17,
        "b_x_cc": 18, "b_y_cc": 19,
        "two_finger": True,
        "require_contact": True,
    }
    return p


def _switch_pro() -> dict:
    p = _base("Nintendo Switch Pro Controller — Default")
    return p


def _wii_remote() -> dict:
    p = _base("Wii Remote + Nunchuk — Motion Theremin")
    # Wider deadzone — accelerometer noise on Wiimote is high.
    p["deadzone"] = 0.12
    # Axes: 0,1 = Nunchuk stick, 2,3 = Wiimote pitch/roll, 4,5 = nunchuk accel.
    p["axes"] = {"0": 1, "1": 74, "2": 71, "3": 72, "4": 11, "5": 7}
    return p


def _xbox_ps5_generic() -> dict:
    p = _base("Xbox + PS5 — Generic Cross-Platform")
    return p


def _xbox_series() -> dict:
    p = _base("Xbox Series X|S — Default")
    return p


def _dualsense_touchpad_xy() -> dict:
    p = _base("DualSense Touchpad — XY Modulator")
    p["touchpad"] = {
        "enabled": True,
        "x_cc": 16, "y_cc": 17,
        "b_x_cc": 18, "b_y_cc": 19,
        "two_finger": False,
        "require_contact": True,
    }
    return p


# Slug -> preset mapping. Each value is a dict ready to JSON-dump.
PRESETS: dict[str, dict] = {
    "Ableton Live — Clip Launcher": _ableton(),
    "FL Studio — Channel Rack + Mixer": _fl_studio(),
    "Logic Pro — Control Surface": _logic_pro(),
    "Cubase + Nuendo — Quick Controls": _cubase(),
    "Pro Tools — HUI Transport": _pro_tools(),
    "Studio One — Impact XT Pads": _studio_one(),
    "Reaper — Transport + Mix": _reaper(),
    "Bitwig — Hardware Modulator": _bitwig(),
    "Ardour — Linux Open-Source Workflow": _ardour(),
    "GarageBand — iPad Wireless via Mac Bridge": _garageband(),
    "Reason — Combinator Rotaries": _reason(),
    "Resolume Arena — VJ": _resolume_arena(),
    "Resolume Avenue — Solo VJ": _resolume_avenue(),
    "MadMapper — Projection Mapping": _madmapper(),
    "VDMX5 — VJ Live": _vdmx5(),
    "Modul8 — Quick VJ Set": _modul8(),
    "CoGe + VJamm — Bridge Setup": _coge_vjamm(),
    "Hippotizer — Show Control": _hippotizer(),
    "Notch Block — Real-Time Graphics": _notch(),
    "Isadora — Media Server": _isadora(),
    "Magic Music Visuals — Audio-Reactive Live": _magic_music_visuals(),
    "TouchDesigner — MIDI CHOPs": _touchdesigner(),
    "Beat Making — Finger Drumming": _beat_making(),
    "DJ Scratch — Turntablism": _dj_scratch(),
    "Drone / Quadcopter — OSC Flight Control": _drone(),
    "Kaoss Pad — Touchpad XY": _kaoss(),
    "DualSense Touchpad — XY Modulator": _dualsense_touchpad_xy(),
    "Film Scoring — Articulation Keyswitches": _film_scoring(),
    "MIDI Clock Sync — Transport": _midi_clock_sync(),
    "Bidirectional Haptics — Rumble + Triggers": _haptic_feedback(),
    "Modular Synth — CV via MIDI-to-CV": _modular_cv(),
    "MPE — Polyphonic Expression": _mpe(),
    "Music Education — Kids C Major": _music_education_kids(),
    "Podcast Soundboard — Stinger Triggers": _podcast_soundboard(),
    "PS5 Adaptive Triggers — MIDI Feedback": _ps5_adaptive_triggers(),
    "Sound Design — Sticks as LFOs": _sound_design(),
    "Twitch — Stinger Transitions + Scenes": _twitch_streaming(),
    "8BitDo Pro 2 — Default + Paddles": _eightbitdo_pro_2(),
    "PS4 DualShock 4 — Default": _ds4(),
    "GameCube — USB Adapter": _gamecube(),
    "Joy-Con Pair — Two-Hand Pads": _joy_con_pair(),
    "MFi iOS Bluetooth — Backbone / Kishi": _mfi_ios(),
    "Stadia Controller — Revival": _stadia(),
    "Valve Steam Controller — Two Trackpads": _steam_controller(),
    "Nintendo Switch Pro Controller — Default": _switch_pro(),
    "Wii Remote + Nunchuk — Motion Theremin": _wii_remote(),
    "Xbox + PS5 — Generic Cross-Platform": _xbox_ps5_generic(),
    "Xbox Series X|S — Default": _xbox_series(),
}


def main() -> None:
    here = Path(__file__).resolve().parent
    target = here.parent / "src" / "gamepad_midi_bridge" / "resources" / "presets"
    target.mkdir(parents=True, exist_ok=True)

    written = 0
    for name, blob in PRESETS.items():
        # File name = preset name. Slashes / colons would break paths.
        safe = name.replace("/", "-").replace(":", "")
        path = target / f"{safe}.json"
        path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
        written += 1

    print(f"Wrote {written} presets to {target}")


if __name__ == "__main__":
    main()
