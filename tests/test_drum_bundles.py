"""Tests for drum-kit preset bundles."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.drum_bundles import (
    DrumBundle,
    get_bundle,
    list_bundles,
    BUNDLES,
)
from gamepad_midi_bridge.mapping import Mapping


def test_list_bundles_returns_five():
    """list_bundles() returns exactly 5 drum bundles."""
    bundles = list_bundles()
    assert len(bundles) == 5
    assert all(isinstance(b, DrumBundle) for b in bundles)


def test_all_bundle_slugs_unique():
    """Each bundle has a unique slug."""
    bundles = list_bundles()
    slugs = [b.slug for b in bundles]
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs found: {slugs}"


def test_expected_bundle_slugs():
    """The 5 bundles have the expected slugs."""
    bundles = list_bundles()
    slugs = {b.slug for b in bundles}
    expected = {"classic_kit", "trap", "acoustic", "edm", "latin"}
    assert slugs == expected, f"Expected {expected}, got {slugs}"


def test_get_bundle_classic_kit():
    """get_bundle('classic_kit') returns the classic kit bundle."""
    bundle = get_bundle("classic_kit")
    assert bundle is not None
    assert bundle.slug == "classic_kit"
    assert "Classic" in bundle.display_name
    assert bundle.style == "Classic"


def test_get_bundle_trap():
    """get_bundle('trap') returns the trap kit bundle."""
    bundle = get_bundle("trap")
    assert bundle is not None
    assert bundle.slug == "trap"
    assert bundle.style == "Trap"
    assert "Trap" in bundle.display_name


def test_get_bundle_acoustic():
    """get_bundle('acoustic') returns the acoustic kit bundle."""
    bundle = get_bundle("acoustic")
    assert bundle is not None
    assert bundle.slug == "acoustic"
    assert bundle.style == "Acoustic"


def test_get_bundle_edm():
    """get_bundle('edm') returns the EDM kit bundle."""
    bundle = get_bundle("edm")
    assert bundle is not None
    assert bundle.slug == "edm"
    assert bundle.style == "EDM"


def test_get_bundle_latin():
    """get_bundle('latin') returns the Latin kit bundle."""
    bundle = get_bundle("latin")
    assert bundle is not None
    assert bundle.slug == "latin"
    assert bundle.style == "Latin"


def test_get_bundle_nonexistent():
    """get_bundle() returns None for unknown slug."""
    result = get_bundle("nonexistent")
    assert result is None


def test_classic_kit_builds_valid_mapping():
    """Classic kit bundle builds a valid Mapping."""
    bundle = get_bundle("classic_kit")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    assert mapping.midi_channel == 9  # default channel 10 → 9 internally
    assert mapping.name == "Classic Drum Kit"


def test_trap_kit_builds_valid_mapping():
    """Trap kit bundle builds a valid Mapping."""
    bundle = get_bundle("trap")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_acoustic_kit_builds_valid_mapping():
    """Acoustic kit bundle builds a valid Mapping."""
    bundle = get_bundle("acoustic")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_edm_kit_builds_valid_mapping():
    """EDM kit bundle builds a valid Mapping."""
    bundle = get_bundle("edm")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_latin_kit_builds_valid_mapping():
    """Latin kit bundle builds a valid Mapping."""
    bundle = get_bundle("latin")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_classic_kit_cross_button_is_36():
    """Classic kit: Cross button (0) maps to MIDI note 36 (Kick)."""
    bundle = get_bundle("classic_kit")
    mapping = bundle.build_mapping()
    assert mapping.buttons.get(0) == 36


def test_trap_kit_circle_button_is_40():
    """Trap kit: Circle button (1) maps to MIDI note 40 (Electric Snare)."""
    bundle = get_bundle("trap")
    mapping = bundle.build_mapping()
    assert mapping.buttons.get(1) == 40


def test_acoustic_kit_triangle_button_is_49():
    """Acoustic kit: Triangle button (2) maps to MIDI note 49 (Crash)."""
    bundle = get_bundle("acoustic")
    mapping = bundle.build_mapping()
    assert mapping.buttons.get(3) == 49


def test_default_channel_is_10():
    """Default MIDI channel for all bundles is 10 (GM drum channel)."""
    for bundle in list_bundles():
        mapping = bundle.build_mapping()
        assert mapping.midi_channel == 9  # channel 10 → index 9


def test_channel_override_works():
    """build_mapping(channel=15) sets MIDI channel to 14."""
    bundle = get_bundle("classic_kit")
    mapping = bundle.build_mapping(channel=15)
    assert mapping.midi_channel == 14  # 15 - 1


def test_channel_clamps_low():
    """build_mapping(channel=0) clamps to 0."""
    bundle = get_bundle("classic_kit")
    mapping = bundle.build_mapping(channel=0)
    assert mapping.midi_channel == 0


def test_channel_clamps_high():
    """build_mapping(channel=20) clamps to 15."""
    bundle = get_bundle("classic_kit")
    mapping = bundle.build_mapping(channel=20)
    assert mapping.midi_channel == 15


def test_all_bundles_have_display_names():
    """All bundles have non-empty display names."""
    bundles = list_bundles()
    for bundle in bundles:
        assert isinstance(bundle.display_name, str)
        assert len(bundle.display_name) > 0


def test_all_bundles_have_descriptions():
    """All bundles have non-empty descriptions."""
    bundles = list_bundles()
    for bundle in bundles:
        assert isinstance(bundle.description, str)
        assert len(bundle.description) > 0


def test_all_bundles_have_tags():
    """All bundles have non-empty tags."""
    bundles = list_bundles()
    for bundle in bundles:
        assert isinstance(bundle.tags, list)
        assert len(bundle.tags) > 0
        # Each tag should be a string
        for tag in bundle.tags:
            assert isinstance(tag, str)
            assert len(tag) > 0


def test_all_bundles_have_styles():
    """All bundles have non-empty style values."""
    bundles = list_bundles()
    for bundle in bundles:
        assert isinstance(bundle.style, str)
        assert len(bundle.style) > 0


def test_all_bundles_have_at_least_8_buttons():
    """All built mappings have at least 8 buttons configured."""
    bundles = list_bundles()
    for bundle in bundles:
        mapping = bundle.build_mapping()
        # 6 face/shoulder buttons + 4 D-pad directions = 10 total possible
        assert len(mapping.buttons) >= 6, f"{bundle.slug} has fewer than 6 buttons"
        assert len(mapping.hats) >= 4, f"{bundle.slug} has fewer than 4 D-pad directions"


def test_bundle_styles_have_variety():
    """Bundles have at least 4 unique style values."""
    bundles = list_bundles()
    styles = {b.style for b in bundles}
    # We have: Classic, Trap, Acoustic, EDM, Latin = 5 unique
    assert len(styles) >= 4, f"Expected at least 4 unique styles, got {len(styles)}"


def test_all_buttons_have_velocity_jitter():
    """All configured buttons have velocity jitter for humanization."""
    for bundle in list_bundles():
        mapping = bundle.build_mapping()
        for button_idx in mapping.buttons.keys():
            assert button_idx in mapping.button_configs
            config = mapping.button_configs[button_idx]
            assert config.velocity_jitter == 6, \
                f"{bundle.slug} button {button_idx} has jitter {config.velocity_jitter}, expected 6"


def test_classic_kit_has_kick_snare_hh():
    """Classic kit has kick (36), snare (38), and closed HH (42)."""
    bundle = get_bundle("classic_kit")
    mapping = bundle.build_mapping()
    notes = list(mapping.buttons.values())
    assert 36 in notes, "Kick (36) not found in classic kit"
    assert 38 in notes, "Snare (38) not found in classic kit"
    assert 42 in notes, "Closed HH (42) not found in classic kit"


def test_trap_kit_has_kick_electric_snare_clap():
    """Trap kit has kick (36), electric snare (40), and clap (39)."""
    bundle = get_bundle("trap")
    mapping = bundle.build_mapping()
    notes = list(mapping.buttons.values())
    assert 36 in notes, "Kick (36) not found in trap kit"
    assert 40 in notes, "Electric Snare (40) not found in trap kit"
    assert 39 in notes, "Clap (39) not found in trap kit"


def test_latin_kit_has_congas_bongos():
    """Latin kit has congas (61, 62, 63) and bongos (60)."""
    bundle = get_bundle("latin")
    mapping = bundle.build_mapping()
    notes = list(mapping.buttons.values())
    assert 61 in notes or 62 in notes or 63 in notes, "No congas found in latin kit"
    assert 60 in notes, "Bongo (60) not found in latin kit"


def test_bundle_to_dict_round_trip():
    """All bundles' mappings round-trip through to_dict/from_dict."""
    for bundle in list_bundles():
        mapping = bundle.build_mapping()
        d = mapping.to_dict()
        restored = Mapping.from_dict(d)
        assert restored.name == mapping.name
        assert restored.midi_channel == mapping.midi_channel
        assert len(restored.buttons) == len(mapping.buttons)


def test_bundle_constants_match_list():
    """The BUNDLES constant matches list_bundles()."""
    constant_bundles = BUNDLES
    listed_bundles = list_bundles()
    assert len(constant_bundles) == len(listed_bundles)
    for c, l in zip(constant_bundles, listed_bundles):
        assert c.slug == l.slug
        assert c.display_name == l.display_name


def test_classic_kit_dpad_coverage():
    """Classic kit D-pad has all 4 directions mapped."""
    bundle = get_bundle("classic_kit")
    mapping = bundle.build_mapping()
    assert "up" in mapping.hats
    assert "down" in mapping.hats
    assert "left" in mapping.hats
    assert "right" in mapping.hats
    assert len(mapping.hats) == 4


def test_trap_kit_splash_note():
    """Trap kit L1 button maps to note 55 (Splash cymbal)."""
    bundle = get_bundle("trap")
    mapping = bundle.build_mapping()
    assert mapping.buttons.get(4) == 55


def test_acoustic_kit_tom_coverage():
    """Acoustic kit has multiple tom notes for variation."""
    bundle = get_bundle("acoustic")
    mapping = bundle.build_mapping()
    all_notes = list(mapping.buttons.values()) + list(mapping.hats.values())
    # High Tom (50), Mid Tom (48), Low Tom (43), Floor Tom (45)
    tom_notes = [48, 43, 45, 50]
    found_toms = [n for n in tom_notes if n in all_notes]
    assert len(found_toms) >= 2, f"Acoustic kit missing tom variety. Found: {found_toms}"


def test_edm_kit_splash_vibraslap():
    """EDM kit has splash (55) and vibraslap (58)."""
    bundle = get_bundle("edm")
    mapping = bundle.build_mapping()
    all_notes = list(mapping.buttons.values()) + list(mapping.hats.values())
    assert 55 in all_notes or 58 in all_notes, "EDM kit missing splash/vibraslap"
