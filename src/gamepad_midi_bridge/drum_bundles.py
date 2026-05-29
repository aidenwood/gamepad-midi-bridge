"""Drum-kit preset bundles for finger drumming.

Provides 5 ready-made drum-kit presets that map PS5 DualSense controller
buttons to General MIDI drum notes (channel 10) with humanizing jitter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Callable

from gamepad_midi_bridge.mapping import (
    Mapping,
    ButtonConfig,
)


@dataclass
class DrumBundle:
    """One drum-kit preset bundle with hardcoded sensible defaults.

    Fields:
      - `slug`         : unique identifier (e.g. "classic_kit")
      - `display_name` : user-facing label (e.g. "Classic Drum Kit")
      - `style`        : drum style tag (e.g. "Hip-hop", "Rock", "EDM")
      - `description`  : brief description of the bundle's layout
      - `tags`         : searchable tags (e.g. ["finger-drumming", "hip-hop"])
    """

    slug: str
    display_name: str
    style: str
    description: str
    tags: List[str]
    _builder: Callable[[int], Mapping] = None

    def build_mapping(self, channel: int = 10) -> Mapping:
        """Return a fully-configured Mapping for this drum kit.

        Args:
            channel: MIDI channel (1-16, converted to 0-15 internally).
                    Defaults to 10 (channel 9 in MIDI, the General MIDI drum channel).
        """
        if self._builder is None:
            raise NotImplementedError(f"build_mapping not implemented for {self.slug}")
        return self._builder(channel)


def _build_classic_kit_mapping(channel: int = 10) -> Mapping:
    """Classic drum kit: Cross→Kick, Square→Snare, Circle→Closed HH,
    Triangle→Open HH, L1→Crash, R1→Ride, D-pad→Toms & Clap.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Classic Drum Kit",
        midi_channel=midi_channel,
        buttons={
            0: 36,   # Cross → Kick
            1: 38,   # Circle → Snare
            2: 42,   # Triangle → Closed HH
            3: 46,   # Square → Open HH
            4: 49,   # L1 → Crash
            5: 51,   # R1 → Ride
        },
        hats={
            "up": 39,    # D-pad up → Hand Clap
            "down": 43,  # D-pad down → Low Tom
            "left": 45,  # D-pad left → Mid Tom
            "right": 47, # D-pad right → High Tom
        },
    )
    # Add velocity jitter (humanizing) to each button
    for button_idx in m.buttons.keys():
        m.button_configs[button_idx] = ButtonConfig(velocity_jitter=6)
    for hat_dir, note in m.hats.items():
        if hat_dir in ["up", "down", "left", "right"]:
            # Note: Hat directions don't have direct ButtonConfig support in the
            # mapping model, so jitter is applied at the button level only.
            pass
    return m


def _build_trap_mapping(channel: int = 10) -> Mapping:
    """Trap kit: modern snare, pedal HH, claps, and splash cymbal.
    Cross→Kick, Square→Electric Snare, Circle→Pedal HH, Triangle→Clap,
    L1→Splash, R1→Ride 2, D-pad→HH variations & toms.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Trap Drum Kit",
        midi_channel=midi_channel,
        buttons={
            0: 36,   # Cross → Kick
            1: 40,   # Circle → Electric Snare
            2: 44,   # Triangle → Pedal HH
            3: 39,   # Square → Clap
            4: 55,   # L1 → Splash
            5: 59,   # R1 → Ride 2
        },
        hats={
            "up": 42,    # D-pad up → Closed HH
            "down": 45,  # D-pad down → Mid Tom
            "left": 47,  # D-pad left → High Tom
            "right": 48, # D-pad right → High Tom (alt)
        },
    )
    for button_idx in m.buttons.keys():
        m.button_configs[button_idx] = ButtonConfig(velocity_jitter=6)
    return m


def _build_acoustic_mapping(channel: int = 10) -> Mapping:
    """Acoustic kit: natural drum sounds with emphasis on tom variations.
    Cross→Acoustic Bass Drum, Square→Snare, Circle→HH, Triangle→Crash,
    L1→High Tom, R1→Mid Tom, D-pad→Low/Floor toms & ride variations.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Acoustic Drum Kit",
        midi_channel=midi_channel,
        buttons={
            0: 35,   # Cross → Acoustic Bass Drum
            1: 38,   # Circle → Snare
            2: 42,   # Triangle → Closed HH
            3: 49,   # Square → Crash
            4: 50,   # L1 → High Tom
            5: 48,   # R1 → Mid Tom
        },
        hats={
            "up": 43,    # D-pad up → Low Tom
            "down": 45,  # D-pad down → Floor Tom
            "left": 51,  # D-pad left → Ride
            "right": 53, # D-pad right → Ride Bell
        },
    )
    for button_idx in m.buttons.keys():
        m.button_configs[button_idx] = ButtonConfig(velocity_jitter=6)
    return m


def _build_edm_mapping(channel: int = 10) -> Mapping:
    """EDM kit: electronic/synth drums with cymbals and exotic percussion.
    Cross→Kick, Square→Electric Snare, Circle→Pedal HH, Triangle→Open HH,
    L1→Splash, R1→Clap, D-pad→Vibraslap & high congas.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="EDM Drum Kit",
        midi_channel=midi_channel,
        buttons={
            0: 36,   # Cross → Kick
            1: 40,   # Circle → Electric Snare
            2: 44,   # Triangle → Pedal HH
            3: 46,   # Square → Open HH
            4: 55,   # L1 → Splash
            5: 39,   # R1 → Clap
        },
        hats={
            "up": 58,    # D-pad up → Vibraslap
            "down": 62,  # D-pad down → Mute Hi Conga
            "left": 61,  # D-pad left → Low Conga
            "right": 63, # D-pad right → Open Hi Conga
        },
    )
    for button_idx in m.buttons.keys():
        m.button_configs[button_idx] = ButtonConfig(velocity_jitter=6)
    return m


def _build_latin_mapping(channel: int = 10) -> Mapping:
    """Latin kit: congas, bongos, claves, maracas, woodblocks.
    Cross→Low Conga, Square→Open High Conga, Circle→Mute High Conga,
    Triangle→High Bongo, L1→Cabasa, R1→Maracas, D-pad→Claves & woodblocks.
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="Latin Drum Kit",
        midi_channel=midi_channel,
        buttons={
            0: 61,   # Cross → Low Conga
            1: 62,   # Circle → Open High Conga
            2: 63,   # Triangle → Mute High Conga
            3: 60,   # Square → High Bongo
            4: 69,   # L1 → Cabasa
            5: 70,   # R1 → Maracas
        },
        hats={
            "up": 73,    # D-pad up → Short Whistle
            "down": 74,  # D-pad down → Long Whistle
            "left": 76,  # D-pad left → Wood Block
            "right": 77, # D-pad right → Open Cuica
        },
    )
    for button_idx in m.buttons.keys():
        m.button_configs[button_idx] = ButtonConfig(velocity_jitter=6)
    return m


# Define the 5 bundles
BUNDLES: List[DrumBundle] = [
    DrumBundle(
        slug="classic_kit",
        display_name="Classic Drum Kit",
        style="Classic",
        description="Bread-and-butter kicks, snares, hats, toms, and cymbals. Perfect for learning.",
        tags=["finger-drumming", "acoustic", "classic"],
        _builder=_build_classic_kit_mapping,
    ),
    DrumBundle(
        slug="trap",
        display_name="Trap Kit",
        style="Trap",
        description="Modern trap drums: electric snare, pedal hats, splash, and ride cymbal.",
        tags=["finger-drumming", "trap", "hip-hop", "modern"],
        _builder=_build_trap_mapping,
    ),
    DrumBundle(
        slug="acoustic",
        display_name="Acoustic Drum Kit",
        style="Acoustic",
        description="Natural acoustic sounds with emphasis on tom variations and ride bells.",
        tags=["finger-drumming", "acoustic", "natural"],
        _builder=_build_acoustic_mapping,
    ),
    DrumBundle(
        slug="edm",
        display_name="EDM Drum Kit",
        style="EDM",
        description="Electronic & synth drums with exotic percussion: vibraslap and congas.",
        tags=["finger-drumming", "edm", "electronic", "synth"],
        _builder=_build_edm_mapping,
    ),
    DrumBundle(
        slug="latin",
        display_name="Latin Drum Kit",
        style="Latin",
        description="World percussion: congas, bongos, claves, maracas, cabasa, woodblocks.",
        tags=["finger-drumming", "latin", "world", "percussion"],
        _builder=_build_latin_mapping,
    ),
]


def get_bundle(slug: str) -> Optional[DrumBundle]:
    """Get a DrumBundle by slug.

    Args:
        slug: Bundle slug (e.g. "classic_kit", "trap", "acoustic", "edm", "latin")

    Returns:
        DrumBundle if found, None otherwise.
    """
    for bundle in BUNDLES:
        if bundle.slug == slug:
            return bundle
    return None


def list_bundles() -> List[DrumBundle]:
    """Return all available drum-kit bundles."""
    return list(BUNDLES)
