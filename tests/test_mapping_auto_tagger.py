"""Tests for mapping auto-tagger.

Pure stdlib, no Qt. Tests auto_tag with confidence scores, tag_set filtering,
confidence_for lookup, and available_tags.
"""
from __future__ import annotations

import pytest


class TestAutoTag:
    """auto_tag — generate tags with confidence scores."""

    def test_empty_mapping_returns_empty(self):
        """Empty mapping returns empty list."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        result = auto_tag({})
        assert result == []

    def test_none_input_returns_empty(self):
        """None input returns empty list."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        result = auto_tag(None)
        assert result == []

    def test_drums_channel_10_high_confidence(self):
        """Mapping with channel 10 drum kit → 'drums' tag with high confidence."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        tags = auto_tag(mapping)
        tag_names = [tc.tag for tc in tags]
        assert "drums" in tag_names
        # Find drums tag and check confidence
        drums_tag = [tc for tc in tags if tc.tag == "drums"][0]
        assert drums_tag.confidence >= 0.90

    def test_extensive_16_plus_buttons(self):
        """Mapping with 20 buttons → 'extensive' tag."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {i: (36 + i) for i in range(20)},
            "button_channels": {},
            "midi_channel": 0,
        }
        tags = auto_tag(mapping)
        tag_names = [tc.tag for tc in tags]
        assert "extensive" in tag_names

    def test_minimal_2_buttons(self):
        """Mapping with 2 buttons → 'minimal' tag."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {0: 60, 1: 62},
            "button_channels": {},
            "midi_channel": 0,
        }
        tags = auto_tag(mapping)
        tag_names = [tc.tag for tc in tags]
        assert "minimal" in tag_names

    def test_setlist_live_performance(self):
        """Mapping with setlist → 'live_performance' tag."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {0: 60, 1: 62},
            "button_channels": {},
            "midi_channel": 0,
            "setlist": [{"slug": "song_a"}, {"slug": "song_b"}],
        }
        tags = auto_tag(mapping)
        tag_names = [tc.tag for tc in tags]
        assert "live_performance" in tag_names

    def test_midi_clock_studio(self):
        """Mapping with midi_clock → 'studio' tag."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {0: 60},
            "button_channels": {},
            "midi_channel": 0,
            "midi_clock": True,
        }
        tags = auto_tag(mapping)
        tag_names = [tc.tag for tc in tags]
        assert "studio" in tag_names

    def test_experimental_bow_crossfade_lfo(self):
        """Mapping with bow + crossfade + LFO bank → 'experimental' tag."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {0: 60},
            "button_channels": {},
            "midi_channel": 0,
            "l2_trigger": {
                "bow_mode": True,
                "crossfade_enabled": True,
                "lfo_bank": {"lfo1": {}},
            },
        }
        tags = auto_tag(mapping)
        tag_names = [tc.tag for tc in tags]
        assert "experimental" in tag_names

    def test_tag_set_filters_by_confidence(self):
        """tag_set filters tags by min_confidence."""
        from gamepad_midi_bridge.mapping_auto_tagger import tag_set

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        # Get tags above 0.8 confidence
        tags_high = tag_set(mapping, min_confidence=0.8)
        # Should include drums at 0.95
        assert "drums" in tags_high

        # Get tags above 0.99 confidence
        tags_very_high = tag_set(mapping, min_confidence=0.99)
        # Should exclude everything
        assert len(tags_very_high) == 0

    def test_confidence_for_returns_float(self):
        """confidence_for returns 0..1 for a tag."""
        from gamepad_midi_bridge.mapping_auto_tagger import confidence_for

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        conf = confidence_for("drums", mapping)
        assert isinstance(conf, float)
        assert 0 <= conf <= 1
        assert conf >= 0.90

    def test_confidence_for_unknown_tag_returns_zero(self):
        """confidence_for unknown tag → 0."""
        from gamepad_midi_bridge.mapping_auto_tagger import confidence_for

        mapping = {
            "buttons": {0: 36, 1: 38, 2: 42},
            "button_channels": {0: 9, 1: 9, 2: 9},
            "midi_channel": 0,
        }
        conf = confidence_for("nonexistent_tag", mapping)
        assert conf == 0.0

    def test_available_tags_returns_sorted_list(self):
        """available_tags returns sorted list of all tags."""
        from gamepad_midi_bridge.mapping_auto_tagger import available_tags

        tags = available_tags()
        assert isinstance(tags, list)
        assert len(tags) >= 17  # 9 base + 8 new
        # Check it's sorted
        assert tags == sorted(tags)
        # Spot-check some tags
        assert "drums" in tags
        assert "extensive" in tags
        assert "minimal" in tags
        assert "live_performance" in tags

    def test_tags_sorted_by_confidence_desc(self):
        """auto_tag returns tags sorted by confidence descending."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {i: (36 + i) for i in range(20)},
            "button_channels": {i: 9 for i in range(3)},
            "midi_channel": 0,
            "setlist": [{"slug": "a"}],
        }
        tags = auto_tag(mapping)
        # Check sorted by confidence desc
        if len(tags) > 1:
            for i in range(len(tags) - 1):
                assert tags[i].confidence >= tags[i + 1].confidence

    def test_tagged_confidence_round_trip(self):
        """TaggedConfidence to_dict / from_dict round-trip."""
        from gamepad_midi_bridge.mapping_auto_tagger import TaggedConfidence

        original = TaggedConfidence(tag="drums", confidence=0.95)
        d = original.to_dict()
        assert d == {"tag": "drums", "confidence": 0.95}

        restored = TaggedConfidence.from_dict(d)
        assert restored.tag == original.tag
        assert restored.confidence == original.confidence

    def test_extensive_minimal_mutually_exclusive(self):
        """'extensive' and 'minimal' are mutually exclusive."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        # Extensive (20 buttons)
        extensive_mapping = {
            "buttons": {i: (36 + i) for i in range(20)},
        }
        extensive_tags = [tc.tag for tc in auto_tag(extensive_mapping)]
        assert "extensive" in extensive_tags
        assert "minimal" not in extensive_tags

        # Minimal (2 buttons)
        minimal_mapping = {
            "buttons": {0: 60, 1: 62},
        }
        minimal_tags = [tc.tag for tc in auto_tag(minimal_mapping)]
        assert "minimal" in minimal_tags
        assert "extensive" not in minimal_tags

    def test_polyphonic_monophonic_mutually_exclusive(self):
        """'polyphonic' and 'monophonic' are mutually exclusive."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        # Monophonic (1 channel)
        monophonic_mapping = {
            "buttons": {0: 60, 1: 62, 2: 64},
            "button_channels": {0: 0, 1: 0, 2: 0},
            "midi_channel": 0,
        }
        mono_tags = [tc.tag for tc in auto_tag(monophonic_mapping)]
        assert "monophonic" in mono_tags
        assert "polyphonic" not in mono_tags

        # Polyphonic (2+ channels)
        polyphonic_mapping = {
            "buttons": {0: 60, 1: 62, 2: 64},
            "button_channels": {0: 0, 1: 1, 2: 2},
            "midi_channel": 0,
        }
        poly_tags = [tc.tag for tc in auto_tag(polyphonic_mapping)]
        assert "polyphonic" in poly_tags
        assert "monophonic" not in poly_tags


class TestIntegration:
    """Integration tests combining auto_tag, tag_set, and confidence_for."""

    def test_full_workflow_complex_mapping(self):
        """Full workflow: auto_tag → tag_set → confidence_for."""
        from gamepad_midi_bridge.mapping_auto_tagger import (
            auto_tag,
            tag_set,
            confidence_for,
        )

        mapping = {
            "buttons": {i: (36 + i) for i in range(16)},
            "button_channels": {i: 9 for i in range(3)},
            "midi_channel": 0,
            "setlist": [{"slug": "song_a"}],
            "midi_clock": True,
        }

        # auto_tag returns scored list
        tags_conf = auto_tag(mapping)
        assert len(tags_conf) > 0

        # tag_set filters
        tags_above_75 = tag_set(mapping, min_confidence=0.75)
        assert len(tags_above_75) > 0

        # confidence_for individual lookup
        drums_conf = confidence_for("drums", mapping)
        assert drums_conf > 0

        live_conf = confidence_for("live_performance", mapping)
        assert live_conf > 0

    def test_edge_case_buttons_dict_not_dict(self):
        """Handles non-dict buttons gracefully."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": "not a dict",  # Invalid
        }
        tags = auto_tag(mapping)
        assert tags == []  # Should not crash, returns empty

    def test_edge_case_malformed_trigger(self):
        """Handles malformed l2_trigger/r2_trigger gracefully."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        mapping = {
            "buttons": {0: 60},
            "l2_trigger": "not a dict",  # Invalid
            "r2_trigger": None,  # Invalid
        }
        tags = auto_tag(mapping)
        # Should not crash
        assert isinstance(tags, list)

    def test_max_8_tags_limit(self):
        """auto_tag returns max 8 tags."""
        from gamepad_midi_bridge.mapping_auto_tagger import auto_tag

        # Build a mapping that triggers many tags
        mapping = {
            "buttons": {i: (36 + i) for i in range(20)},
            "button_channels": {i: 9 for i in range(3)},
            "midi_channel": 0,
            "setlist": [{"slug": "a"}],
            "midi_clock": True,
            "left_stick": {"chord_enabled": True},
            "l2_trigger": {
                "bow_mode": True,
                "crossfade_enabled": True,
                "lfo_bank": {"lfo1": {}},
            },
            "macros": [{"name": "m1", "arp_mode": True}, {"name": "m2"}, {"name": "m3"}],
        }
        tags = auto_tag(mapping)
        assert len(tags) <= 8
