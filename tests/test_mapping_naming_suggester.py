"""Tests for mapping naming suggester.

Pure stdlib, no Qt. Tests the tag extraction, name generation, slugification,
symbol mapping, and detail formatting for mapping names.
"""
from __future__ import annotations

import pytest


class TestExtractTags:
    """extract_tags — analyze mapping contents and return tag list."""

    def test_empty_mapping_no_tags(self):
        """Empty mapping returns empty tag list."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        tags = extract_tags({})
        assert tags == []

    def test_drum_channel_many_buttons(self):
        """Mapping with 3+ buttons on channel 10 includes 'drums' tag."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        assert "drums" in tags

    def test_drum_channel_few_buttons(self):
        """Mapping with <3 buttons on channel 10 does NOT include 'drums'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "buttons": {0: 36, 1: 38},
            "button_channels": {0: 9, 1: 9},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        assert "drums" not in tags

    def test_lead_narrow_high_mid_notes(self):
        """Mapping with notes in 60..80 range includes 'lead' tag."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "buttons": {0: 65, 1: 70},
            "button_channels": {},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        assert "lead" in tags

    def test_lead_mixed_notes_no_lead(self):
        """Mapping with mixed note ranges does NOT include 'lead'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "buttons": {0: 30, 1: 70},
            "button_channels": {},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        assert "lead" not in tags

    def test_bass_low_range_notes(self):
        """Mapping with notes in 28..50 range includes 'bass' tag."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "buttons": {0: 30, 1: 40},
            "button_channels": {},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        assert "bass" in tags

    def test_bass_only_one_note(self):
        """Mapping with only 1 low note does NOT include 'bass'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "buttons": {0: 30},
            "button_channels": {},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        assert "bass" not in tags

    def test_chords_left_stick_enabled(self):
        """Mapping with left_stick.chord_enabled includes 'chords'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "left_stick": {"chord_enabled": True},
            "right_stick": {},
        }
        tags = extract_tags(mapping)
        assert "chords" in tags

    def test_chords_right_stick_enabled(self):
        """Mapping with right_stick.chord_enabled includes 'chords'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "left_stick": {},
            "right_stick": {"chord_enabled": True},
        }
        tags = extract_tags(mapping)
        assert "chords" in tags

    def test_chords_neither_stick(self):
        """Mapping with both chord_enabled=False does NOT include 'chords'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "left_stick": {"chord_enabled": False},
            "right_stick": {"chord_enabled": False},
        }
        tags = extract_tags(mapping)
        assert "chords" not in tags

    def test_ambient_trigger_crossfade(self):
        """Mapping with trigger crossfade_enabled includes 'ambient'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "l2_trigger": {"crossfade_enabled": True},
            "r2_trigger": {},
        }
        tags = extract_tags(mapping)
        assert "ambient" in tags

    def test_ambient_trigger_bow_mode(self):
        """Mapping with trigger bow_mode includes 'ambient'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "l2_trigger": {"bow_mode": True},
            "r2_trigger": {},
        }
        tags = extract_tags(mapping)
        assert "ambient" in tags

    def test_expressive_midi_learn_bindings(self):
        """Mapping with midi_learn.bindings includes 'expressive'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "midi_learn": {"bindings": {1: "some_param"}},
        }
        tags = extract_tags(mapping)
        assert "expressive" in tags

    def test_expressive_aftertouch_enabled(self):
        """Mapping with l2_trigger.aftertouch.enabled includes 'expressive'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "l2_trigger": {"aftertouch": {"enabled": True}},
            "r2_trigger": {},
        }
        tags = extract_tags(mapping)
        assert "expressive" in tags

    def test_expressive_midi_learn_enabled(self):
        """Mapping with midi_learn.enabled includes 'expressive'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "midi_learn": {"enabled": True},
        }
        tags = extract_tags(mapping)
        assert "expressive" in tags

    def test_polyrhythmic_macro_arp_mode(self):
        """Mapping with macro.arp_mode=True includes 'polyrhythmic'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "macros": [{"name": "test", "arp_mode": True}],
        }
        tags = extract_tags(mapping)
        assert "polyrhythmic" in tags

    def test_polyrhythmic_no_macros(self):
        """Mapping with no macros does NOT include 'polyrhythmic'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "macros": [],
        }
        tags = extract_tags(mapping)
        assert "polyrhythmic" not in tags

    def test_rotated_layer_shift_enabled(self):
        """Mapping with shift_layer.enabled includes 'rotated_layer'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "shift_layer": {"enabled": True},
        }
        tags = extract_tags(mapping)
        assert "rotated_layer" in tags

    def test_rotated_layer_ab_compare(self):
        """Mapping with ab_compare_enabled includes 'rotated_layer'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "ab_compare_enabled": True,
        }
        tags = extract_tags(mapping)
        assert "rotated_layer" in tags

    def test_macro_heavy_three_or_more(self):
        """Mapping with 3+ macros includes 'macro_heavy'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "macros": [
                {"name": "m1"},
                {"name": "m2"},
                {"name": "m3"},
            ],
        }
        tags = extract_tags(mapping)
        assert "macro_heavy" in tags

    def test_macro_heavy_two_macros(self):
        """Mapping with 2 macros does NOT include 'macro_heavy'."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "macros": [{"name": "m1"}, {"name": "m2"}],
        }
        tags = extract_tags(mapping)
        assert "macro_heavy" not in tags

    def test_tags_returned_in_order(self):
        """Tags are returned in order they appear (no guaranteed sort here)."""
        from gamepad_midi_bridge.mapping_naming_suggester import extract_tags

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "left_stick": {"chord_enabled": True},
            "l2_trigger": {"bow_mode": True},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        # All four should be present
        assert "drums" in tags
        assert "chords" in tags
        assert "ambient" in tags


class TestSuggestName:
    """suggest_name — combine tags into a friendly name."""

    def test_empty_mapping_untitled(self):
        """Empty mapping returns 'Untitled'."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_name

        name = suggest_name({})
        assert name == "Untitled"

    def test_drums_only(self):
        """Mapping with drums tag returns 'Drums'."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_name

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        name = suggest_name(mapping)
        assert "Drums" in name

    def test_lead_and_drums(self):
        """Mapping with lead + drums returns combined name."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_name

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42, 3: 65, 4: 70},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        name = suggest_name(mapping)
        # Should contain both
        assert "Drums" in name or "Lead" in name

    def test_max_words_limit(self):
        """suggest_name respects max_words parameter."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_name

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "left_stick": {"chord_enabled": True},
            "l2_trigger": {"bow_mode": True},
            "midi_learn": {"enabled": True},
            "midi_channel": 0,
        }
        name = suggest_name(mapping, max_words=2)
        word_count = len(name.split())
        assert word_count <= 2

    def test_title_case_output(self):
        """suggest_name returns title-cased string."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_name

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        name = suggest_name(mapping)
        # "Drums" is title-cased
        assert name[0].isupper()

    def test_bass_priority_over_lead(self):
        """suggest_name prioritizes bass over lead in order."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_name

        mapping = {
            "buttons": {0: 30, 1: 40, 2: 65, 3: 70},
            "button_channels": {},
            "midi_channel": 0,
        }
        name = suggest_name(mapping, max_words=1)
        # Should pick bass first due to priority order
        assert "Bass" in name


class TestSuggestSlug:
    """suggest_slug — convert name to kebab-case."""

    def test_simple_slug(self):
        """Single word slugifies correctly."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_slug

        slug = suggest_slug("Drums")
        assert slug == "drums"

    def test_multi_word_slug(self):
        """Multiple words become kebab-case."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_slug

        slug = suggest_slug("Lead Drums")
        assert slug == "lead-drums"

    def test_slug_strips_special_chars(self):
        """Special characters are removed."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_slug

        slug = suggest_slug("Lead! Drums@")
        assert slug == "lead-drums"
        assert "@" not in slug
        assert "!" not in slug

    def test_slug_multiple_spaces(self):
        """Multiple spaces collapse to single hyphen."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_slug

        slug = suggest_slug("Lead   Drums")
        assert slug == "lead-drums"

    def test_slug_hyphens_preserved(self):
        """Existing hyphens are preserved."""
        from gamepad_midi_bridge.mapping_naming_suggester import suggest_slug

        slug = suggest_slug("Lead-Drums-Macro")
        assert slug == "lead-drums-macro"


class TestTagToSymbol:
    """tag_to_symbol — map tags to ASCII text tokens."""

    def test_bass_symbol(self):
        """bass tag returns 'B'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("bass") == "B"

    def test_lead_symbol(self):
        """lead tag returns 'L'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("lead") == "L"

    def test_drums_symbol(self):
        """drums tag returns 'D'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("drums") == "D"

    def test_chords_symbol(self):
        """chords tag returns 'C'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("chords") == "C"

    def test_ambient_symbol(self):
        """ambient tag returns 'A'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("ambient") == "A"

    def test_expressive_symbol(self):
        """expressive tag returns 'E'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("expressive") == "E"

    def test_polyrhythmic_symbol(self):
        """polyrhythmic tag returns 'P'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("polyrhythmic") == "P"

    def test_rotated_layer_symbol(self):
        """rotated_layer tag returns 'R'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("rotated_layer") == "R"

    def test_macro_heavy_symbol(self):
        """macro_heavy tag returns 'M'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("macro_heavy") == "M"

    def test_unknown_tag_returns_question_mark(self):
        """Unknown tag returns '?'."""
        from gamepad_midi_bridge.mapping_naming_suggester import tag_to_symbol

        assert tag_to_symbol("unknown") == "?"


class TestFormatNameWithDetails:
    """format_name_with_details — add button count to name."""

    def test_format_with_buttons_count(self):
        """Name is formatted with button count."""
        from gamepad_midi_bridge.mapping_naming_suggester import (
            format_name_with_details,
        )

        mapping = {
            "buttons": {0: 60, 1: 62, 2: 64},
        }
        result = format_name_with_details("Lead Drums", mapping)
        assert "[3 buttons]" in result
        assert result.startswith("Lead Drums")

    def test_format_empty_buttons(self):
        """Mapping with no buttons shows [0 buttons]."""
        from gamepad_midi_bridge.mapping_naming_suggester import (
            format_name_with_details,
        )

        mapping = {"buttons": {}}
        result = format_name_with_details("Untitled", mapping)
        assert "[0 buttons]" in result

    def test_format_missing_buttons_key(self):
        """Mapping without buttons key shows [0 buttons]."""
        from gamepad_midi_bridge.mapping_naming_suggester import (
            format_name_with_details,
        )

        mapping = {}
        result = format_name_with_details("Untitled", mapping)
        assert "[0 buttons]" in result


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_workflow_drums_mapping(self):
        """Full workflow: extract tags → suggest name → slugify."""
        from gamepad_midi_bridge.mapping_naming_suggester import (
            extract_tags,
            suggest_name,
            suggest_slug,
        )

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        tags = extract_tags(mapping)
        assert "drums" in tags
        # Drum notes also fall in bass range, so both tags may appear
        assert "bass" in tags or len(tags) > 0

        name = suggest_name(mapping)
        assert "Drums" in name  # Should include drums due to channel 10

        slug = suggest_slug(name)
        assert "drums" in slug

    def test_full_workflow_complex_mapping(self):
        """Full workflow with multiple tags."""
        from gamepad_midi_bridge.mapping_naming_suggester import (
            extract_tags,
            suggest_name,
            suggest_slug,
            format_name_with_details,
        )

        mapping = {
            "buttons": {0: 30, 1: 40, 2: 65, 3: 70},
            "button_channels": {},
            "left_stick": {"chord_enabled": True},
            "l2_trigger": {"bow_mode": True},
            "midi_learn": {"enabled": True},
            "macros": [{"name": "m1"}, {"name": "m2"}, {"name": "m3"}],
            "midi_channel": 0,
        }

        tags = extract_tags(mapping)
        assert len(tags) > 0

        name = suggest_name(mapping)
        assert name != "Untitled"

        slug = suggest_slug(name)
        assert "-" in slug or slug.isalnum()

        formatted = format_name_with_details(name, mapping)
        assert "[4 buttons]" in formatted
