"""DAW-specific preset bundles with tuned MIDI mappings.

Provides out-of-the-box sensible defaults for popular DAWs (Ableton Live,
Logic Pro, FL Studio, Cubase, Reaper) by bundling a fully-configured Mapping
for each.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Callable

from gamepad_midi_bridge.mapping import (
    Mapping,
    TriggerConfig,
    StickConfig,
)


@dataclass
class DawBundle:
    """One DAW-specific preset bundle with hardcoded sensible defaults.

    Fields:
      - `slug`         : unique identifier (e.g. "ableton")
      - `display_name` : user-facing label (e.g. "DualSense for Ableton Live")
      - `daw_name`     : DAW full name (e.g. "Ableton Live")
      - `description`  : brief description of the bundle's tuning
      - `tags`         : searchable tags (e.g. ["production", "clip-launch"])
    """

    slug: str
    display_name: str
    daw_name: str
    description: str
    tags: List[str]
    _builder: Callable[[int], Mapping] = None

    def build_mapping(self, channel: int = 1) -> Mapping:
        """Return a fully-configured Mapping for this DAW.

        Args:
            channel: MIDI channel (1-16, converted to 0-15 internally).
                    Defaults to 1 (channel 0 in MIDI).
        """
        if self._builder is None:
            raise NotImplementedError(f"build_mapping not implemented for {self.slug}")
        return self._builder(channel)


def _build_ableton_mapping(channel: int = 1) -> Mapping:
    """Ableton Live: mod wheel (L2), expression (R2), device macros (sticks),
    clip launch (cross), scene up/down (dpad).
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="DualSense for Ableton Live",
        midi_channel=midi_channel,
        buttons={
            0: 60,   # Cross → C3 (clip launch)
            1: 62,   # Circle → D3
            2: 64,   # Triangle → E3
            3: 65,   # Square → F3
        },
        axes={
            0: 21,   # Left stick X → CC21 (device macro 1)
            1: 22,   # Left stick Y → CC22 (device macro 2)
            2: 23,   # Right stick X → CC23 (device macro 3)
            3: 24,   # Right stick Y → CC24 (device macro 4)
            4: 1,    # L2 → CC1 (mod wheel)
            5: 11,   # R2 → CC11 (expression)
        },
        hats={
            "up": 127,    # Scene up (CC127 as note for now)
            "down": 126,  # Scene down (CC126 as note)
            "left": 80,
            "right": 81,
        },
    )
    # L2 and R2 as mod wheel and expression
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    return m


def _build_logic_mapping(channel: int = 1) -> Mapping:
    """Logic Pro: mod wheel (L2), filter cutoff (R2), smart controls (sticks),
    drum kit notes (face buttons).
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="DualSense for Logic Pro",
        midi_channel=midi_channel,
        buttons={
            0: 60,   # Cross → C3 (drum kit)
            1: 61,   # Circle → C#3
            2: 64,   # Triangle → E3
            3: 65,   # Square → F3
        },
        axes={
            0: 70,   # Left stick X → CC70 (smart control 1)
            1: 71,   # Left stick Y → CC71 (smart control 2)
            2: 72,   # Right stick X → CC72 (smart control 3)
            3: 73,   # Right stick Y → CC73 (smart control 4)
            4: 1,    # L2 → CC1 (mod wheel)
            5: 2,    # R2 → CC2 (breath)
        },
        hats={
            "up": 78,
            "down": 79,
            "left": 80,
            "right": 81,
        },
    )
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    return m


def _build_fl_mapping(channel: int = 1) -> Mapping:
    """FL Studio: mod wheel (L2), filter cutoff (R2), 4 macros (sticks),
    step sequencer notes (face buttons).
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="DualSense for FL Studio",
        midi_channel=midi_channel,
        buttons={
            0: 69,   # Cross → A4 (step seq)
            1: 71,   # Circle → B4
            2: 72,   # Triangle → C5
            3: 74,   # Square → D5
        },
        axes={
            0: 20,   # Left stick X → CC20 (macro 1)
            1: 21,   # Left stick Y → CC21 (macro 2)
            2: 22,   # Right stick X → CC22 (macro 3)
            3: 23,   # Right stick Y → CC23 (macro 4)
            4: 1,    # L2 → CC1 (mod wheel)
            5: 74,   # R2 → CC74 (cutoff)
        },
        hats={
            "up": 78,
            "down": 79,
            "left": 80,
            "right": 81,
        },
    )
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    return m


def _build_cubase_mapping(channel: int = 1) -> Mapping:
    """Cubase: mod wheel (L2), expression (R2), quick controls (sticks),
    drum notes (face buttons).
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="DualSense for Cubase",
        midi_channel=midi_channel,
        buttons={
            0: 60,   # Cross → C3
            1: 61,   # Circle → C#3
            2: 64,   # Triangle → E3
            3: 65,   # Square → F3
        },
        axes={
            0: 74,   # Left stick X → CC74 (quick control 1)
            1: 71,   # Left stick Y → CC71 (quick control 2)
            2: 7,    # Right stick X → CC7 (volume / quick control 3)
            3: 10,   # Right stick Y → CC10 (pan / quick control 4)
            4: 1,    # L2 → CC1 (mod wheel)
            5: 11,   # R2 → CC11 (expression)
        },
        hats={
            "up": 78,
            "down": 79,
            "left": 80,
            "right": 81,
        },
    )
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    return m


def _build_reaper_mapping(channel: int = 1) -> Mapping:
    """Reaper: mod wheel (L2), filter cutoff (R2), FX parameters (sticks),
    drum notes (face buttons).
    """
    midi_channel = max(0, min(15, channel - 1))
    m = Mapping(
        name="DualSense for Reaper",
        midi_channel=midi_channel,
        buttons={
            0: 60,   # Cross → C3
            1: 61,   # Circle → C#3
            2: 64,   # Triangle → E3
            3: 65,   # Square → F3
        },
        axes={
            0: 80,   # Left stick X → CC80 (FX param 1)
            1: 81,   # Left stick Y → CC81 (FX param 2)
            2: 82,   # Right stick X → CC82 (FX param 3)
            3: 83,   # Right stick Y → CC83 (FX param 4)
            4: 1,    # L2 → CC1 (mod wheel)
            5: 2,    # R2 → CC2 (breath / expression)
        },
        hats={
            "up": 78,
            "down": 79,
            "left": 80,
            "right": 81,
        },
    )
    m.l2_trigger = TriggerConfig(mode="linear")
    m.r2_trigger = TriggerConfig(mode="linear")
    return m


# Define the 5 bundles
BUNDLES: List[DawBundle] = [
    DawBundle(
        slug="ableton",
        display_name="DualSense for Ableton Live",
        daw_name="Ableton Live",
        description="Mod wheel on L2, expression on R2, device macros on sticks, clip launch on Cross, scene up/down on D-pad.",
        tags=["production", "clip-launch", "device-macros"],
        _builder=_build_ableton_mapping,
    ),
    DawBundle(
        slug="logic",
        display_name="DualSense for Logic Pro",
        daw_name="Logic Pro",
        description="Mod wheel on L2, breath control on R2, smart controls on sticks, drum kit notes on face buttons.",
        tags=["production", "smart-controls", "drum-kit"],
        _builder=_build_logic_mapping,
    ),
    DawBundle(
        slug="fl",
        display_name="DualSense for FL Studio",
        daw_name="FL Studio",
        description="Mod wheel on L2, filter cutoff on R2, 4 macros on sticks, step sequencer notes on face buttons.",
        tags=["production", "macros", "step-sequencer"],
        _builder=_build_fl_mapping,
    ),
    DawBundle(
        slug="cubase",
        display_name="DualSense for Cubase",
        daw_name="Cubase",
        description="Mod wheel on L2, expression on R2, quick controls on sticks, drum notes on face buttons.",
        tags=["production", "quick-controls", "drum-notes"],
        _builder=_build_cubase_mapping,
    ),
    DawBundle(
        slug="reaper",
        display_name="DualSense for Reaper",
        daw_name="Reaper",
        description="Mod wheel on L2, expression on R2, FX parameters on sticks, drum notes on face buttons.",
        tags=["production", "fx-parameters", "drum-notes"],
        _builder=_build_reaper_mapping,
    ),
]


def get_bundle(slug: str) -> Optional[DawBundle]:
    """Get a DawBundle by slug.

    Args:
        slug: Bundle slug (e.g. "ableton", "logic", "fl", "cubase", "reaper")

    Returns:
        DawBundle if found, None otherwise.
    """
    for bundle in BUNDLES:
        if bundle.slug == slug:
            return bundle
    return None


def list_bundles() -> List[DawBundle]:
    """Return all available DAW bundles."""
    return list(BUNDLES)
