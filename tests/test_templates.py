"""Tests for starter mapping templates in gamepad_midi_bridge.templates."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import Mapping
from gamepad_midi_bridge.templates import TEMPLATES, TEMPLATES_BY_SLUG, Template

EXPECTED_COUNT = 6
EXPECTED_SLUGS = {
    "drum-pad",
    "dj",
    "vj",
    "synth-lead",
    "modular-control",
    "obs-streamer",
}
VALID_TAGS = {"Drums", "DJ", "VJ", "Synth", "Modular", "Streaming"}


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------

def test_template_count():
    assert len(TEMPLATES) == EXPECTED_COUNT


def test_slugs_are_unique():
    slugs = [t.slug for t in TEMPLATES]
    assert len(slugs) == len(set(slugs)), "Duplicate slugs found"


def test_all_expected_slugs_present():
    slugs = {t.slug for t in TEMPLATES}
    assert slugs == EXPECTED_SLUGS


def test_by_slug_lookup_covers_all():
    assert set(TEMPLATES_BY_SLUG.keys()) == EXPECTED_SLUGS


def test_all_tags_valid():
    for tmpl in TEMPLATES:
        assert tmpl.tag in VALID_TAGS, f"{tmpl.slug} has unknown tag {tmpl.tag!r}"


def test_all_have_non_empty_name_and_description():
    for tmpl in TEMPLATES:
        assert tmpl.name.strip(), f"{tmpl.slug} has empty name"
        assert tmpl.description.strip(), f"{tmpl.slug} has empty description"


# ---------------------------------------------------------------------------
# build_mapping factory
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.slug)
def test_build_mapping_returns_mapping(tmpl: Template):
    result = tmpl.build_mapping()
    assert isinstance(result, Mapping)


@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.slug)
def test_build_mapping_has_at_least_4_controls(tmpl: Template):
    m = tmpl.build_mapping()
    total = len(m.buttons) + len(m.axes) + len(m.hats)
    assert total >= 4, (
        f"{tmpl.slug}: only {total} mapped controls (buttons={len(m.buttons)}, "
        f"axes={len(m.axes)}, hats={len(m.hats)})"
    )


@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.slug)
def test_build_mapping_name_set(tmpl: Template):
    m = tmpl.build_mapping()
    assert m.name.strip(), f"{tmpl.slug}: Mapping.name is blank"


@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.slug)
def test_build_mapping_is_independent(tmpl: Template):
    """Each call returns a fresh object — mutations don't bleed between calls."""
    m1 = tmpl.build_mapping()
    m2 = tmpl.build_mapping()
    assert m1 is not m2
    m1.buttons[999] = 99
    assert 999 not in m2.buttons


@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.slug)
def test_build_mapping_round_trips(tmpl: Template):
    """Mapping → to_dict → from_dict should survive without error."""
    m = tmpl.build_mapping()
    restored = Mapping.from_dict(m.to_dict())
    assert restored.name == m.name
    assert restored.midi_channel == m.midi_channel
    assert restored.buttons == m.buttons
    assert restored.axes == m.axes
    assert restored.hats == m.hats


# ---------------------------------------------------------------------------
# Per-template spot checks
# ---------------------------------------------------------------------------

def test_drum_pad_cross_is_kick():
    m = TEMPLATES_BY_SLUG["drum-pad"].build_mapping()
    assert m.buttons[0] == 36, "Cross should map to GM Kick (note 36)"


def test_dj_l2_is_crossfader():
    m = TEMPLATES_BY_SLUG["dj"].build_mapping()
    assert m.axes[4] == 8, "L2 should map to crossfader CC 8"


def test_vj_touchpad_enabled():
    m = TEMPLATES_BY_SLUG["vj"].build_mapping()
    assert m.touchpad.enabled, "VJ template should have touchpad enabled"
    assert m.touchpad.x_cc == 16
    assert m.touchpad.y_cc == 17


def test_synth_lead_dpad_are_notes():
    m = TEMPLATES_BY_SLUG["synth-lead"].build_mapping()
    for direction in ("up", "down", "left", "right"):
        assert direction in m.hats, f"D-pad {direction} should be mapped"


def test_modular_axes_cc_1_to_6():
    m = TEMPLATES_BY_SLUG["modular-control"].build_mapping()
    for axis_idx, expected_cc in enumerate(range(1, 7)):
        assert m.axes[axis_idx] == expected_cc, (
            f"Axis {axis_idx} should be CC {expected_cc}"
        )


def test_modular_buttons_note_36_upward():
    m = TEMPLATES_BY_SLUG["modular-control"].build_mapping()
    for btn_idx in range(11):
        assert m.buttons[btn_idx] == 36 + btn_idx


def test_obs_streamer_cross_is_scene1():
    m = TEMPLATES_BY_SLUG["obs-streamer"].build_mapping()
    assert m.buttons[0] == 60, "Cross should trigger Scene 1 (note 60)"
