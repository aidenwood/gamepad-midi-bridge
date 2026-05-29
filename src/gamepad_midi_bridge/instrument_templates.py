"""Instrument-style starter mapping templates organized by playing style.

Provides 5 ready-made preset templates that focus on specific instrument/playing
styles (synth_lead, synth_pad, bass_synth, guitar_amp, finger_drumming). Each is
a complete Mapping with sensible defaults for that style, independent of DAW or
drum kit choice.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Callable

from gamepad_midi_bridge.mapping import (
    Mapping,
    TriggerConfig,
    StickConfig,
    StickLfoConfig,
    ButtonConfig,
)
from gamepad_midi_bridge import drum_bundles


@dataclass
class InstrumentTemplate:
    """One instrument-style preset template with hardcoded sensible defaults.

    Fields:
      - `slug`             : unique identifier (e.g. "synth_lead")
      - `display_name`     : user-facing label (e.g. "Synth Lead")
      - `instrument_type`  : category (e.g. "lead", "pad", "bass", "guitar", "drums")
      - `description`      : brief description of the template's tuning
      - `tags`             : searchable tags (e.g. ["synth", "expressive"])
    """

    slug: str
    display_name: str
    instrument_type: str
    description: str
    tags: List[str]
    _builder: Callable[[int], Mapping] = None

    def build_mapping(self, channel: int = 1) -> Mapping:
        """Return a fully-configured Mapping for this instrument template.

        Args:
            channel: MIDI channel (1-16, converted to 0-15 internally).
                    Defaults to 1 (channel 0 in MIDI).
        """
        if self._builder is None:
            raise NotImplementedError(f"build_mapping not implemented for {self.slug}")
        return self._builder(channel)


def _build_synth_lead_mapping(channel: int = 1) -> Mapping:
    """Synth lead: L2 controls filter cutoff (CC74), R2 controls resonance (CC71).
    Sticks drive pitch bend (X) and mod wheel (Y). Face buttons map to 4-note arp seed.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Synth Lead",
        midi_channel=midi_channel,
        buttons={
            0: 60,   # Cross → C4 (arp note 1)
            1: 62,   # Circle → D4 (arp note 2)
            2: 64,   # Triangle → E4 (arp note 3)
            3: 65,   # Square → F4 (arp note 4)
        },
        axes={
            0: 74,   # Left stick X → CC74 (filter cutoff)
            1: 1,    # Left stick Y → CC1 (mod wheel)
            2: 71,   # Right stick X → CC71 (resonance)
            3: 73,   # Right stick Y → CC73 (attack)
            4: 74,   # L2 → CC74 (filter cutoff)
            5: 71,   # R2 → CC71 (resonance)
        },
        hats={
            "up": 78,
            "down": 79,
            "left": 80,
            "right": 81,
        },
    )
    # L2 and R2 both control filter parameters
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    # Left stick: pitch bend on X, mod on Y
    m.left_stick = StickConfig(
        pitch_bend_enabled=True,
        pitch_bend_axis="x",
        pitch_bend_range_semis=12,
    )
    return m


def _build_synth_pad_mapping(channel: int = 1) -> Mapping:
    """Synth pad: L2 controls filter cutoff (CC74), R2 controls reverb send (CC91).
    Sticks drive slow LFO-modulated parameters. Face buttons map to 4-chord progression.
    Bow mode enabled on triggers for swelling expressions.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Synth Pad",
        midi_channel=midi_channel,
        buttons={
            0: 60,   # Cross → C4 (chord 1)
            1: 62,   # Circle → D4 (chord 2)
            2: 64,   # Triangle → E4 (chord 3)
            3: 67,   # Square → G4 (chord 4)
        },
        axes={
            0: 74,   # Left stick X → CC74 (filter cutoff)
            1: 91,   # Left stick Y → CC91 (reverb send)
            2: 93,   # Right stick X → CC93 (chorus)
            3: 75,   # Right stick Y → CC75 (decay)
            4: 74,   # L2 → CC74 (filter cutoff)
            5: 91,   # R2 → CC91 (reverb send)
        },
        hats={
            "up": 78,
            "down": 79,
            "left": 80,
            "right": 81,
        },
    )
    # L2 and R2 with bow mode for smooth swell expressions
    m.l2_trigger = TriggerConfig(
        mode="linear",
        bow_mode=True,
        bow_cc=74,
        bow_velocity_scale=1.5,
        bow_min_velocity=0.3,
    )
    m.r2_trigger = TriggerConfig(
        mode="linear",
        bow_mode=True,
        bow_cc=91,
        bow_velocity_scale=1.2,
        bow_min_velocity=0.3,
    )
    # Left stick with slow LFO for ambient texture
    m.left_stick = StickConfig(
        lfo=StickLfoConfig(
            enabled=True,
            waveform="sine",
            rate_hz=0.3,
            depth=0.4,
            blend_mode="replace",
        ),
    )
    return m


def _build_bass_synth_mapping(channel: int = 1) -> Mapping:
    """Bass synth: L2 controls filter cutoff (CC74), R2 controls accent/drive (CC1).
    Sticks drive pitch bend. Face buttons map to C-D-E-F-G bass notes.
    Touchpad gestures for octave shifts.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Bass Synth",
        midi_channel=midi_channel,
        buttons={
            0: 36,   # Cross → C2 (low bass)
            1: 38,   # Circle → D2
            2: 40,   # Triangle → E2
            3: 41,   # Square → F2
            4: 43,   # L1 → G2 (octave up root)
            5: 48,   # R1 → C3 (octave up bass)
        },
        axes={
            0: 1,    # Left stick X → CC1 (mod/drive)
            1: 74,   # Left stick Y → CC74 (filter cutoff)
            2: 2,    # Right stick X → CC2 (breath)
            3: 5,    # Right stick Y → CC5 (portamento)
            4: 74,   # L2 → CC74 (filter cutoff)
            5: 1,    # R2 → CC1 (mod/drive/accent)
        },
        hats={
            "up": 78,
            "down": 79,
            "left": 80,
            "right": 81,
        },
    )
    # L2 and R2 for filter and accent
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    # Left stick: pitch bend on X for dynamic bass motion
    m.left_stick = StickConfig(
        pitch_bend_enabled=True,
        pitch_bend_axis="x",
        pitch_bend_range_semis=24,
    )
    return m


def _build_guitar_amp_mapping(channel: int = 1) -> Mapping:
    """Guitar amp: L2 controls wah (CC4), R2 controls volume (CC7).
    Face buttons map to chord triggers (strum on each fire). Sticks control
    tremolo (LFO bipolar on CC1) and tone. D-pad for capo up/down notes.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Guitar Amp",
        midi_channel=midi_channel,
        buttons={
            0: 60,   # Cross → C4 (chord 1)
            1: 62,   # Circle → D4 (chord 2)
            2: 64,   # Triangle → E4 (chord 3)
            3: 65,   # Square → F4 (chord 4)
        },
        axes={
            0: 1,    # Left stick X → CC1 (tremolo LFO)
            1: 75,   # Left stick Y → CC75 (tone/brightness)
            2: 80,   # Right stick X → CC80 (sustain)
            3: 81,   # Right stick Y → CC81 (reverb)
            4: 4,    # L2 → CC4 (wah pedal)
            5: 7,    # R2 → CC7 (volume)
        },
        hats={
            "up": 78,    # Capo up
            "down": 79,  # Capo down
            "left": 80,
            "right": 81,
        },
    )
    # L2 and R2 for wah and volume expression
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    # Left stick: tremolo (LFO on X) and tone control
    m.left_stick = StickConfig(
        lfo=StickLfoConfig(
            enabled=True,
            waveform="triangle",
            rate_hz=6.0,
            depth=0.8,
            blend_mode="multiply",
        ),
    )
    return m


def _build_finger_drumming_mapping(channel: int = 10) -> Mapping:
    """Finger drumming: bridges to classic drum kit on channel 10 (GM drums).
    Uses the classic_kit preset layout optimized for real-time drum performance.
    Touchpad gesture = panic (all notes off).
    """
    # Build the classic drum kit from drum_bundles and ensure we're on channel 10
    classic_kit = drum_bundles.get_bundle("classic_kit")
    if classic_kit is None:
        raise RuntimeError("Classic drum kit bundle not found")
    m = classic_kit.build_mapping(channel=channel)
    m.name = "Finger Drumming"
    return m


# Registry of all builtin instrument templates
TEMPLATES: List[InstrumentTemplate] = [
    InstrumentTemplate(
        slug="synth_lead",
        display_name="Synth Lead",
        instrument_type="lead",
        description="Filter cutoff & resonance on triggers, pitch bend & mod on sticks, 4-note arp seed on face buttons.",
        tags=["synth", "expressive", "lead", "melodic"],
        _builder=_build_synth_lead_mapping,
    ),
    InstrumentTemplate(
        slug="synth_pad",
        display_name="Synth Pad",
        instrument_type="pad",
        description="Filter & reverb on triggers with bow mode for swells, slow LFO on sticks, 4-chord progression on buttons.",
        tags=["synth", "ambient", "pad", "atmospheric"],
        _builder=_build_synth_pad_mapping,
    ),
    InstrumentTemplate(
        slug="bass_synth",
        display_name="Bass Synth",
        instrument_type="bass",
        description="Filter cutoff & accent on triggers, pitch bend on sticks, bass notes C-D-E-F-G on buttons with octave shifts.",
        tags=["synth", "bass", "sub", "low-end"],
        _builder=_build_bass_synth_mapping,
    ),
    InstrumentTemplate(
        slug="guitar_amp",
        display_name="Guitar Amp",
        instrument_type="guitar",
        description="Wah pedal (L2) and volume (R2), tremolo LFO on sticks, chord triggers on buttons, capo up/down on D-pad.",
        tags=["guitar", "amp", "wah", "strumming"],
        _builder=_build_guitar_amp_mapping,
    ),
    InstrumentTemplate(
        slug="finger_drumming",
        display_name="Finger Drumming",
        instrument_type="drums",
        description="Real-time drum kit optimized for finger drumming on channel 10 (General MIDI drums) with humanizing jitter.",
        tags=["drums", "percussion", "finger-drumming", "real-time"],
        _builder=_build_finger_drumming_mapping,
    ),
]


def get_template(slug: str) -> Optional[InstrumentTemplate]:
    """Get an InstrumentTemplate by slug.

    Args:
        slug: Template slug (e.g. "synth_lead", "synth_pad", "bass_synth",
              "guitar_amp", "finger_drumming")

    Returns:
        InstrumentTemplate if found, None otherwise.
    """
    for template in TEMPLATES:
        if template.slug == slug:
            return template
    return None


def list_templates() -> List[InstrumentTemplate]:
    """Return all available instrument templates."""
    return list(TEMPLATES)


def templates_by_type(instrument_type: str) -> List[InstrumentTemplate]:
    """Filter templates by instrument type.

    Args:
        instrument_type: Type filter (e.g. "lead", "pad", "bass", "guitar", "drums")

    Returns:
        List of matching templates. Empty list if no matches.
    """
    return [t for t in TEMPLATES if t.instrument_type == instrument_type]
