"""Gamepad MIDI Bridge — Ableton Live Remote Script (ControlSurface).

WHAT THIS DOES
==============
Binds the default gamepad MIDI map produced by Gamepad MIDI Bridge to native
Live controls so the user gets clip launch, transport, mixer, and scene
navigation without manually MIDI-learning every button:

    Face buttons (notes 60-65 ch 1)  -> Clip launch tracks 1-6, scene 1
    D-pad notes 78-81                -> Scene up/down + fire prev/next
    Sticks (CC 3-6)                  -> Volume tracks 1-4
    Triggers (CC 1-2)                -> Master Volume + Crossfader
    Buttons 6-7 (notes 71-72)        -> Transport: Play / Stop
    Buttons 8-10 (notes 74-77)       -> Loop, Metronome, Record

Mappings mirror `gamepad_midi_bridge.mapping.Mapping` defaults. Channel: 1
(matches the bridge's `midi_channel = 0`, which is 1-indexed in Live).

LIVE VERSION
============
Live 11+ only. Live 11 ships Python 3.7; Live 12 ships Python 3.11. We do not
ship Python-2 syntax. The `_Framework` modules we import are part of Ableton's
private Remote Script API — we DO NOT redistribute their source; we import at
runtime from the host's bundled Python environment, same as every official
Ableton-distributed control surface (APC, Push, Launchkey).

LICENSE NOTE
============
Bundling user-installable Remote Scripts that talk to `_Framework` is industry
standard practice — every hardware vendor partnered with Ableton (Akai, Novation,
Native Instruments, M-Audio) ships scripts under the same import pattern. We
distribute only OUR script and rely on `_Framework` being available on the host.
The user is the one running Live, and Live imports the script into its own
process, so no Ableton IP is redistributed.

INSTALL
=======
Use Gamepad MIDI Bridge's "Connectors" tab and click Install for Ableton Live.
The connector copies this folder into:

    macOS  : ~/Music/Ableton/User Library/Remote Scripts/Gamepad MIDI Bridge/
    Windows: ~/Documents/Ableton/User Library/Remote Scripts/Gamepad MIDI Bridge/

Then in Live: Preferences -> Link, Tempo & MIDI -> Control Surface dropdown ->
pick "Gamepad MIDI Bridge". Set Input to the bridge's virtual MIDI port.
"""
from __future__ import absolute_import

import logging

from _Framework.ControlSurface import ControlSurface
from _Framework.ButtonElement import ButtonElement
from _Framework.SliderElement import SliderElement
from _Framework.SessionComponent import SessionComponent
from _Framework.MixerComponent import MixerComponent
from _Framework.TransportComponent import TransportComponent
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE


logger = logging.getLogger(__name__)


# MIDI channel — Live's _Framework uses 0-indexed channels (0 == MIDI ch 1).
# Bridge default `midi_channel = 0` is also 0-indexed, so they match.
MIDI_CHANNEL = 0

# Session view dimensions: 6 tracks across, 1 scene tall (face buttons row).
NUM_TRACKS = 6
NUM_SCENES = 1

# --- Notes (from mapping.py defaults) -----------------------------------------
# Face buttons -> clip launch tracks 1-6, scene 1
FACE_BUTTON_NOTES = [60, 62, 64, 65, 67, 69]  # button index 0..5

# Transport
PLAY_NOTE = 71      # button 6
STOP_NOTE = 72      # button 7
LOOP_NOTE = 74      # button 8
METRO_NOTE = 76     # button 9
RECORD_NOTE = 77    # button 10

# D-pad / hats — scene navigation + fire
HAT_UP_NOTE = 78
HAT_DOWN_NOTE = 79
HAT_LEFT_NOTE = 80    # fire previous scene
HAT_RIGHT_NOTE = 81   # fire next scene

# --- CCs (from mapping.py defaults) -------------------------------------------
# Sticks -> volume tracks 1-4
STICK_CCS = [3, 4, 5, 6]   # track index 0..3

# Triggers
L2_CC = 1   # master volume
R2_CC = 2   # crossfader


class GamepadMidiBridge(ControlSurface):
    """ControlSurface wiring the bridge's default map to native Live controls."""

    def __init__(self, c_instance):
        super(GamepadMidiBridge, self).__init__(c_instance)
        with self.component_guard():
            self._suggested_input_port = "Gamepad MIDI Bridge"
            self._suggested_output_port = "Gamepad MIDI Bridge"
            self._build_session()
            self._build_mixer()
            self._build_transport()
            self._build_scene_navigation()
        self.log_message("Gamepad MIDI Bridge: loaded.")

    # ------------------------------------------------------------------ session
    def _build_session(self):
        """Face buttons -> clip launch on the first scene of tracks 1..6."""
        session = SessionComponent(num_tracks=NUM_TRACKS, num_scenes=NUM_SCENES)
        session.set_offsets(track_offset=0, scene_offset=0)

        for track_idx, note in enumerate(FACE_BUTTON_NOTES):
            button = ButtonElement(
                is_momentary=True,
                msg_type=MIDI_NOTE_TYPE,
                channel=MIDI_CHANNEL,
                identifier=note,
            )
            clip_slot = session.scene(0).clip_slot(track_idx)
            clip_slot.set_launch_button(button)

        self._session = session

    # ------------------------------------------------------------------ mixer
    def _build_mixer(self):
        """Sticks -> track volumes; triggers -> master + crossfader."""
        mixer = MixerComponent(NUM_TRACKS)
        mixer.set_track_offset(0)

        # Sticks (CC 3-6) -> volume tracks 1-4
        for track_idx, cc in enumerate(STICK_CCS):
            slider = SliderElement(
                msg_type=MIDI_CC_TYPE,
                channel=MIDI_CHANNEL,
                identifier=cc,
            )
            mixer.channel_strip(track_idx).set_volume_control(slider)

        # L2 -> master volume
        master_slider = SliderElement(
            msg_type=MIDI_CC_TYPE,
            channel=MIDI_CHANNEL,
            identifier=L2_CC,
        )
        mixer.master_strip().set_volume_control(master_slider)

        # R2 -> crossfader
        crossfader = SliderElement(
            msg_type=MIDI_CC_TYPE,
            channel=MIDI_CHANNEL,
            identifier=R2_CC,
        )
        mixer.set_crossfader_control(crossfader)

        self._mixer = mixer
        # Wire session + mixer together so highlight follows track offset.
        self._session.set_mixer(mixer)

    # ------------------------------------------------------------------ transport
    def _build_transport(self):
        """Buttons 6-10 -> Play / Stop / Loop / Metronome / Record."""
        transport = TransportComponent()

        transport.set_play_button(self._note_button(PLAY_NOTE))
        transport.set_stop_button(self._note_button(STOP_NOTE))
        transport.set_loop_button(self._note_button(LOOP_NOTE))
        transport.set_metronome_button(self._note_button(METRO_NOTE))
        transport.set_record_button(self._note_button(RECORD_NOTE))

        self._transport = transport

    # ------------------------------------------------------------------ scene nav
    def _build_scene_navigation(self):
        """D-pad -> scene up/down + fire previous/next scene."""
        up = self._note_button(HAT_UP_NOTE)
        down = self._note_button(HAT_DOWN_NOTE)
        self._session.set_scene_bank_buttons(down, up)

        # Left/Right hats — fire prev / next scene. _Framework doesn't expose a
        # one-shot "fire selected" pair on SessionComponent older than Live 11,
        # so we register listeners directly.
        left = self._note_button(HAT_LEFT_NOTE)
        right = self._note_button(HAT_RIGHT_NOTE)
        left.add_value_listener(self._on_fire_prev)
        right.add_value_listener(self._on_fire_next)
        self._hat_left_button = left
        self._hat_right_button = right

    # ------------------------------------------------------------------ helpers
    def _note_button(self, note):
        return ButtonElement(
            is_momentary=True,
            msg_type=MIDI_NOTE_TYPE,
            channel=MIDI_CHANNEL,
            identifier=note,
        )

    def _on_fire_prev(self, value):
        if value <= 0:
            return
        song = self.song()
        idx = list(song.scenes).index(song.view.selected_scene)
        new_idx = max(0, idx - 1)
        song.view.selected_scene = song.scenes[new_idx]
        song.view.selected_scene.fire_as_selected()

    def _on_fire_next(self, value):
        if value <= 0:
            return
        song = self.song()
        scenes = list(song.scenes)
        idx = scenes.index(song.view.selected_scene)
        new_idx = min(len(scenes) - 1, idx + 1)
        song.view.selected_scene = song.scenes[new_idx]
        song.view.selected_scene.fire_as_selected()

    # ------------------------------------------------------------------ teardown
    def disconnect(self):
        try:
            if hasattr(self, "_hat_left_button"):
                self._hat_left_button.remove_value_listener(self._on_fire_prev)
            if hasattr(self, "_hat_right_button"):
                self._hat_right_button.remove_value_listener(self._on_fire_next)
        except Exception:
            pass
        super(GamepadMidiBridge, self).disconnect()
