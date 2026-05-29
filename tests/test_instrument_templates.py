"""Tests for instrument-style preset templates."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.instrument_templates import (
    InstrumentTemplate,
    get_template,
    list_templates,
    templates_by_type,
)
from gamepad_midi_bridge.mapping import Mapping


def test_list_templates_returns_five():
    """list_templates() returns exactly 5 templates."""
    templates = list_templates()
    assert len(templates) == 5
    assert all(isinstance(t, InstrumentTemplate) for t in templates)


def test_all_template_slugs_unique():
    """Each template has a unique slug."""
    templates = list_templates()
    slugs = [t.slug for t in templates]
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs found: {slugs}"


def test_expected_template_slugs():
    """The 5 templates have the expected slugs."""
    templates = list_templates()
    slugs = {t.slug for t in templates}
    expected = {"synth_lead", "synth_pad", "bass_synth", "guitar_amp", "finger_drumming"}
    assert slugs == expected, f"Expected {expected}, got {slugs}"


def test_get_template_synth_lead():
    """get_template('synth_lead') returns the synth lead template."""
    template = get_template("synth_lead")
    assert template is not None
    assert template.slug == "synth_lead"
    assert template.instrument_type == "lead"
    assert "Lead" in template.display_name


def test_get_template_synth_pad():
    """get_template('synth_pad') returns the synth pad template."""
    template = get_template("synth_pad")
    assert template is not None
    assert template.slug == "synth_pad"
    assert template.instrument_type == "pad"


def test_get_template_bass_synth():
    """get_template('bass_synth') returns the bass synth template."""
    template = get_template("bass_synth")
    assert template is not None
    assert template.slug == "bass_synth"
    assert template.instrument_type == "bass"


def test_get_template_guitar_amp():
    """get_template('guitar_amp') returns the guitar amp template."""
    template = get_template("guitar_amp")
    assert template is not None
    assert template.slug == "guitar_amp"
    assert template.instrument_type == "guitar"


def test_get_template_finger_drumming():
    """get_template('finger_drumming') returns the finger drumming template."""
    template = get_template("finger_drumming")
    assert template is not None
    assert template.slug == "finger_drumming"
    assert template.instrument_type == "drums"


def test_get_template_nonexistent():
    """get_template() returns None for unknown slug."""
    result = get_template("nonexistent")
    assert result is None


def test_synth_lead_builds_valid_mapping():
    """Synth lead template builds a valid Mapping with no schema errors."""
    template = get_template("synth_lead")
    assert template is not None
    mapping = template.build_mapping()
    assert isinstance(mapping, Mapping)
    assert mapping.name == "Synth Lead"
    assert mapping.midi_channel == 0
    # Should round-trip without errors
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_synth_pad_builds_valid_mapping():
    """Synth pad template builds a valid Mapping with no schema errors."""
    template = get_template("synth_pad")
    assert template is not None
    mapping = template.build_mapping()
    assert isinstance(mapping, Mapping)
    assert mapping.name == "Synth Pad"
    # Should round-trip without errors
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_bass_synth_builds_valid_mapping():
    """Bass synth template builds a valid Mapping with no schema errors."""
    template = get_template("bass_synth")
    assert template is not None
    mapping = template.build_mapping()
    assert isinstance(mapping, Mapping)
    assert mapping.name == "Bass Synth"
    # Should round-trip without errors
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_guitar_amp_builds_valid_mapping():
    """Guitar amp template builds a valid Mapping with no schema errors."""
    template = get_template("guitar_amp")
    assert template is not None
    mapping = template.build_mapping()
    assert isinstance(mapping, Mapping)
    assert mapping.name == "Guitar Amp"
    # Should round-trip without errors
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_finger_drumming_builds_valid_mapping():
    """Finger drumming template builds a valid Mapping (uses classic drum kit)."""
    template = get_template("finger_drumming")
    assert template is not None
    # Build with channel 10 (GM drums default)
    mapping = template.build_mapping(channel=10)
    assert isinstance(mapping, Mapping)
    assert mapping.name == "Finger Drumming"
    assert mapping.midi_channel == 9  # Channel 10 (0-indexed as 9) for GM drums
    # Should round-trip without errors
    d = mapping.to_dict()
    restored = Mapping.from_dict(d)
    assert restored.name == mapping.name


def test_synth_lead_trigger_l2_maps_to_cc74():
    """Synth lead has L2 axis mapped to CC74 (filter cutoff)."""
    template = get_template("synth_lead")
    assert template is not None
    mapping = template.build_mapping()
    # Axis 4 is L2
    assert mapping.axes.get(4) == 74


def test_bass_synth_face_buttons_are_bass_notes():
    """Bass synth has face buttons mapped to bass notes C-D-E-F-G."""
    template = get_template("bass_synth")
    assert template is not None
    mapping = template.build_mapping()
    # Expected bass notes: C2=36, D2=38, E2=40, F2=41
    expected_bass_notes = {36, 38, 40, 41}
    # First 4 buttons should contain bass notes
    button_notes = {mapping.buttons[i] for i in range(4)}
    assert expected_bass_notes.issubset(button_notes)


def test_finger_drumming_uses_channel_10():
    """Finger drumming template uses MIDI channel 10 (0-indexed as 9)."""
    template = get_template("finger_drumming")
    assert template is not None
    mapping = template.build_mapping(channel=10)
    assert mapping.midi_channel == 9


def test_templates_by_type_lead():
    """templates_by_type('lead') returns at least synth_lead."""
    results = templates_by_type("lead")
    slugs = [t.slug for t in results]
    assert "synth_lead" in slugs


def test_templates_by_type_pad():
    """templates_by_type('pad') returns synth_pad."""
    results = templates_by_type("pad")
    slugs = [t.slug for t in results]
    assert "synth_pad" in slugs


def test_templates_by_type_bass():
    """templates_by_type('bass') returns bass_synth."""
    results = templates_by_type("bass")
    slugs = [t.slug for t in results]
    assert "bass_synth" in slugs


def test_templates_by_type_guitar():
    """templates_by_type('guitar') returns guitar_amp."""
    results = templates_by_type("guitar")
    slugs = [t.slug for t in results]
    assert "guitar_amp" in slugs


def test_templates_by_type_drums():
    """templates_by_type('drums') returns finger_drumming."""
    results = templates_by_type("drums")
    slugs = [t.slug for t in results]
    assert "finger_drumming" in slugs


def test_templates_by_type_unknown_returns_empty():
    """templates_by_type('unknown') returns empty list."""
    results = templates_by_type("unknown")
    assert results == []


def test_all_templates_have_non_empty_tags():
    """Each template has at least one tag."""
    templates = list_templates()
    for template in templates:
        assert len(template.tags) > 0, f"Template {template.slug} has no tags"


def test_all_templates_have_non_empty_display_name():
    """Each template has a non-empty display_name."""
    templates = list_templates()
    for template in templates:
        assert len(template.display_name) > 0, f"Template {template.slug} has no display_name"


def test_all_templates_have_non_empty_description():
    """Each template has a non-empty description."""
    templates = list_templates()
    for template in templates:
        assert len(template.description) > 0, f"Template {template.slug} has no description"


def test_synth_lead_has_pitch_bend_enabled():
    """Synth lead has pitch bend enabled on left stick X."""
    template = get_template("synth_lead")
    assert template is not None
    mapping = template.build_mapping()
    assert mapping.left_stick.pitch_bend_enabled is True
    assert mapping.left_stick.pitch_bend_axis == "x"


def test_synth_pad_has_bow_mode_enabled():
    """Synth pad has bow mode enabled on L2 trigger."""
    template = get_template("synth_pad")
    assert template is not None
    mapping = template.build_mapping()
    assert mapping.l2_trigger.bow_mode is True


def test_bass_synth_has_pitch_bend_enabled():
    """Bass synth has pitch bend enabled on left stick X."""
    template = get_template("bass_synth")
    assert template is not None
    mapping = template.build_mapping()
    assert mapping.left_stick.pitch_bend_enabled is True


def test_guitar_amp_has_lfo_on_left_stick():
    """Guitar amp has LFO enabled on left stick for tremolo."""
    template = get_template("guitar_amp")
    assert template is not None
    mapping = template.build_mapping()
    assert mapping.left_stick.lfo.enabled is True
    assert mapping.left_stick.lfo.waveform == "triangle"


def test_finger_drumming_builds_from_classic_kit():
    """Finger drumming template builds using classic drum kit."""
    template = get_template("finger_drumming")
    assert template is not None
    mapping = template.build_mapping()
    # Should have classic drum kit buttons
    assert 36 in mapping.buttons.values()  # Kick
    assert 38 in mapping.buttons.values()  # Snare


def test_synth_lead_channel_parameter():
    """Synth lead template respects channel parameter."""
    template = get_template("synth_lead")
    assert template is not None
    m1 = template.build_mapping(channel=1)
    m5 = template.build_mapping(channel=5)
    assert m1.midi_channel == 0
    assert m5.midi_channel == 4


def test_bass_synth_channel_parameter():
    """Bass synth template respects channel parameter."""
    template = get_template("bass_synth")
    assert template is not None
    m1 = template.build_mapping(channel=1)
    m16 = template.build_mapping(channel=16)
    assert m1.midi_channel == 0
    assert m16.midi_channel == 15


def test_all_templates_channel_clamping():
    """All templates clamp channel to 0-15 range."""
    templates = list_templates()
    for template in templates:
        m_negative = template.build_mapping(channel=-5)
        m_too_high = template.build_mapping(channel=100)
        assert 0 <= m_negative.midi_channel <= 15
        assert 0 <= m_too_high.midi_channel <= 15
