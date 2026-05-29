"""Tests for DAW-specific preset bundles."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.daw_bundles import (
    DawBundle,
    get_bundle,
    list_bundles,
    BUNDLES,
)
from gamepad_midi_bridge.mapping import Mapping


def test_list_bundles_returns_five():
    """list_bundles() returns exactly 5 bundles."""
    bundles = list_bundles()
    assert len(bundles) == 5
    assert all(isinstance(b, DawBundle) for b in bundles)


def test_all_bundle_slugs_unique():
    """Each bundle has a unique slug."""
    bundles = list_bundles()
    slugs = [b.slug for b in bundles]
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs found: {slugs}"


def test_expected_bundle_slugs():
    """The 5 bundles have the expected slugs."""
    bundles = list_bundles()
    slugs = {b.slug for b in bundles}
    expected = {"ableton", "logic", "fl", "cubase", "reaper"}
    assert slugs == expected, f"Expected {expected}, got {slugs}"


def test_get_bundle_ableton():
    """get_bundle('ableton') returns the Ableton bundle."""
    bundle = get_bundle("ableton")
    assert bundle is not None
    assert bundle.slug == "ableton"
    assert bundle.daw_name == "Ableton Live"
    assert "Ableton" in bundle.display_name


def test_get_bundle_logic():
    """get_bundle('logic') returns the Logic bundle."""
    bundle = get_bundle("logic")
    assert bundle is not None
    assert bundle.slug == "logic"
    assert bundle.daw_name == "Logic Pro"


def test_get_bundle_fl():
    """get_bundle('fl') returns the FL Studio bundle."""
    bundle = get_bundle("fl")
    assert bundle is not None
    assert bundle.slug == "fl"
    assert bundle.daw_name == "FL Studio"


def test_get_bundle_cubase():
    """get_bundle('cubase') returns the Cubase bundle."""
    bundle = get_bundle("cubase")
    assert bundle is not None
    assert bundle.slug == "cubase"
    assert bundle.daw_name == "Cubase"


def test_get_bundle_reaper():
    """get_bundle('reaper') returns the Reaper bundle."""
    bundle = get_bundle("reaper")
    assert bundle is not None
    assert bundle.slug == "reaper"
    assert bundle.daw_name == "Reaper"


def test_get_bundle_nonexistent():
    """get_bundle() returns None for unknown slug."""
    result = get_bundle("nonexistent")
    assert result is None


def test_ableton_builds_valid_mapping():
    """Ableton bundle builds a valid Mapping with no schema errors."""
    bundle = get_bundle("ableton")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    assert mapping.name == "DualSense for Ableton Live"
    assert mapping.midi_channel == 0
    # Should round-trip without errors
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_logic_builds_valid_mapping():
    """Logic bundle builds a valid Mapping with no schema errors."""
    bundle = get_bundle("logic")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_fl_builds_valid_mapping():
    """FL Studio bundle builds a valid Mapping."""
    bundle = get_bundle("fl")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_cubase_builds_valid_mapping():
    """Cubase bundle builds a valid Mapping."""
    bundle = get_bundle("cubase")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_reaper_builds_valid_mapping():
    """Reaper bundle builds a valid Mapping."""
    bundle = get_bundle("reaper")
    assert bundle is not None
    mapping = bundle.build_mapping()
    assert isinstance(mapping, Mapping)
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_ableton_l2_cc_is_1():
    """Ableton: L2 trigger sends CC1 (mod wheel)."""
    bundle = get_bundle("ableton")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(4) == 1  # axis 4 = L2 trigger


def test_ableton_r2_cc_is_11():
    """Ableton: R2 trigger sends CC11 (expression)."""
    bundle = get_bundle("ableton")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(5) == 11  # axis 5 = R2 trigger


def test_ableton_sticks_are_device_macros():
    """Ableton: sticks control CC21-24 (device macros 1-4)."""
    bundle = get_bundle("ableton")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(0) == 21  # left stick X
    assert mapping.axes.get(1) == 22  # left stick Y
    assert mapping.axes.get(2) == 23  # right stick X
    assert mapping.axes.get(3) == 24  # right stick Y


def test_logic_l2_cc_is_1():
    """Logic: L2 sends CC1 (mod wheel)."""
    bundle = get_bundle("logic")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(4) == 1


def test_logic_r2_cc_is_2():
    """Logic: R2 sends CC2 (breath)."""
    bundle = get_bundle("logic")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(5) == 2


def test_logic_sticks_are_smart_controls():
    """Logic: sticks control CC70-73 (smart controls 1-4)."""
    bundle = get_bundle("logic")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(0) == 70
    assert mapping.axes.get(1) == 71
    assert mapping.axes.get(2) == 72
    assert mapping.axes.get(3) == 73


def test_fl_l2_cc_is_1():
    """FL Studio: L2 sends CC1 (mod wheel)."""
    bundle = get_bundle("fl")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(4) == 1


def test_fl_r2_cc_is_74():
    """FL Studio: R2 sends CC74 (cutoff)."""
    bundle = get_bundle("fl")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(5) == 74


def test_fl_sticks_are_macros():
    """FL Studio: sticks control CC20-23 (macros 1-4)."""
    bundle = get_bundle("fl")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(0) == 20
    assert mapping.axes.get(1) == 21
    assert mapping.axes.get(2) == 22
    assert mapping.axes.get(3) == 23


def test_cubase_l2_cc_is_1():
    """Cubase: L2 sends CC1 (mod wheel)."""
    bundle = get_bundle("cubase")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(4) == 1


def test_cubase_r2_cc_is_11():
    """Cubase: R2 sends CC11 (expression)."""
    bundle = get_bundle("cubase")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(5) == 11


def test_cubase_sticks_are_quick_controls():
    """Cubase: sticks control quick controls (74, 71, 7, 10)."""
    bundle = get_bundle("cubase")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(0) == 74
    assert mapping.axes.get(1) == 71
    assert mapping.axes.get(2) == 7
    assert mapping.axes.get(3) == 10


def test_reaper_l2_cc_is_1():
    """Reaper: L2 sends CC1 (mod wheel)."""
    bundle = get_bundle("reaper")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(4) == 1


def test_reaper_r2_cc_is_2():
    """Reaper: R2 sends CC2 (breath/expression)."""
    bundle = get_bundle("reaper")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(5) == 2


def test_reaper_sticks_are_fx_params():
    """Reaper: sticks control CC80-83 (FX parameters 1-4)."""
    bundle = get_bundle("reaper")
    mapping = bundle.build_mapping()
    assert mapping.axes.get(0) == 80
    assert mapping.axes.get(1) == 81
    assert mapping.axes.get(2) == 82
    assert mapping.axes.get(3) == 83


def test_channel_override_works():
    """build_mapping(channel=5) sets MIDI channel to 4."""
    bundle = get_bundle("ableton")
    mapping = bundle.build_mapping(channel=5)
    assert mapping.midi_channel == 4  # 5 - 1


def test_channel_clamps_low():
    """build_mapping(channel=0) clamps to 0."""
    bundle = get_bundle("ableton")
    mapping = bundle.build_mapping(channel=0)
    assert mapping.midi_channel == 0


def test_channel_clamps_high():
    """build_mapping(channel=20) clamps to 15."""
    bundle = get_bundle("ableton")
    mapping = bundle.build_mapping(channel=20)
    assert mapping.midi_channel == 15


def test_bundle_tags_present():
    """All bundles have non-empty tags."""
    bundles = list_bundles()
    for bundle in bundles:
        assert isinstance(bundle.tags, list)
        assert len(bundle.tags) > 0


def test_bundle_descriptions_present():
    """All bundles have non-empty descriptions."""
    bundles = list_bundles()
    for bundle in bundles:
        assert isinstance(bundle.description, str)
        assert len(bundle.description) > 0


def test_all_bundles_have_buttons():
    """All built mappings have buttons configured."""
    bundles = list_bundles()
    for bundle in bundles:
        mapping = bundle.build_mapping()
        assert len(mapping.buttons) > 0


def test_all_bundles_have_axes():
    """All built mappings have axes (sticks + triggers) configured."""
    bundles = list_bundles()
    for bundle in bundles:
        mapping = bundle.build_mapping()
        assert len(mapping.axes) == 6  # 4 stick axes + 2 triggers


def test_bundle_constants_match_list():
    """The BUNDLES constant matches list_bundles()."""
    constant_bundles = BUNDLES
    listed_bundles = list_bundles()
    assert len(constant_bundles) == len(listed_bundles)
    for c, l in zip(constant_bundles, listed_bundles):
        assert c.slug == l.slug
