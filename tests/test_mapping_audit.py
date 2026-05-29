"""Test suite for mapping_audit module."""

import pytest
from gamepad_midi_bridge.mapping import (
    Mapping,
    StickConfig,
    TriggerConfig,
    ShiftLayerConfig,
    SetlistConfig,
    Macro,
    MacroEvent,
)
from gamepad_midi_bridge.mapping_audit import MappingAuditReport, audit_mapping, summary_text


class TestMappingAuditReportDataclass:
    """Test MappingAuditReport dataclass initialization and serialization."""

    def test_report_initialization_defaults(self):
        """Test that MappingAuditReport initializes with sensible defaults."""
        report = MappingAuditReport()
        assert report.total_buttons == 0
        assert report.mapped_buttons == 0
        assert report.unmapped_buttons == []
        assert report.total_axes == 0
        assert report.mapped_axes == 0
        assert report.unmapped_axes == []
        assert report.triggers_configured == []
        assert report.triggers_with_crossfade == []
        assert report.triggers_with_bow == []
        assert report.sticks_with_chord == []
        assert report.total_channels_used == 0
        assert report.unique_notes_count == 0
        assert report.has_shift_layer is False
        assert report.has_ab_compare is False
        assert report.has_macros is False
        assert report.setlist_size == 0

    def test_report_to_dict_round_trip(self):
        """Test to_dict and from_dict round-trip."""
        report = MappingAuditReport(
            total_buttons=11,
            mapped_buttons=8,
            unmapped_buttons=[2, 5],
            total_axes=6,
            mapped_axes=4,
            unmapped_axes=[3],
            triggers_configured=["L2"],
            unique_notes_count=7,
            has_shift_layer=True,
            total_channels_used=2,
        )
        data = report.to_dict()
        restored = MappingAuditReport.from_dict(data)

        assert restored.total_buttons == 11
        assert restored.mapped_buttons == 8
        assert restored.unmapped_buttons == [2, 5]
        assert restored.total_axes == 6
        assert restored.mapped_axes == 4
        assert restored.unmapped_axes == [3]
        assert restored.triggers_configured == ["L2"]
        assert restored.unique_notes_count == 7
        assert restored.has_shift_layer is True
        assert restored.total_channels_used == 2


class TestAuditMappingButtons:
    """Test button audit logic."""

    def test_empty_mapping_has_default_buttons(self):
        """Empty Mapping() has default buttons from factory."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        # Default mapping has 11 buttons
        assert report.total_buttons == 11
        # All have non-zero notes (defaults: 60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77)
        assert report.mapped_buttons == 11
        assert report.unmapped_buttons == []

    def test_mapping_with_zero_note_unmapped(self):
        """Button with note=0 is unmapped."""
        mapping = Mapping()
        mapping.buttons[0] = 0  # Unmapped
        mapping.buttons[1] = 62  # Keep mapped
        report = audit_mapping(mapping)

        assert report.total_buttons == 11
        assert report.mapped_buttons == 10
        assert 0 in report.unmapped_buttons
        assert 1 not in report.unmapped_buttons

    def test_unique_notes_count(self):
        """unique_notes_count reflects unique MIDI notes."""
        mapping = Mapping()
        mapping.buttons = {0: 60, 1: 60, 2: 62}  # 60 twice, 62 once
        report = audit_mapping(mapping)

        assert report.unique_notes_count == 2


class TestAuditMappingAxes:
    """Test axis audit logic."""

    def test_default_axes_all_mapped(self):
        """Default Mapping has 6 axes, all mapped."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        assert report.total_axes == 6
        assert report.mapped_axes == 6
        assert report.unmapped_axes == []

    def test_axis_with_zero_cc_unmapped(self):
        """Axis with CC=0 is unmapped."""
        mapping = Mapping()
        mapping.axes[0] = 0  # Unmapped
        mapping.axes[1] = 4  # Keep mapped
        report = audit_mapping(mapping)

        assert report.total_axes == 6
        assert report.mapped_axes == 5
        assert 0 in report.unmapped_axes
        assert 1 not in report.unmapped_axes


class TestAuditMappingTriggers:
    """Test trigger audit logic."""

    def test_default_triggers_not_configured(self):
        """Default TriggerConfig (linear, ceiling 127, etc.) not in configured list."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        assert "L2" not in report.triggers_configured
        assert "R2" not in report.triggers_configured

    def test_trigger_with_latch_mode_configured(self):
        """Trigger with mode != 'linear' is configured."""
        mapping = Mapping()
        mapping.l2_trigger.mode = "latch"
        report = audit_mapping(mapping)

        assert "L2" in report.triggers_configured

    def test_trigger_with_gate_button_configured(self):
        """Trigger with gate_button set is configured."""
        mapping = Mapping()
        mapping.r2_trigger.gate_button = 5
        report = audit_mapping(mapping)

        assert "R2" in report.triggers_configured

    def test_trigger_with_crossfade_enabled(self):
        """Trigger with crossfade_enabled is in triggers_with_crossfade."""
        mapping = Mapping()
        mapping.l2_trigger.crossfade_enabled = True
        report = audit_mapping(mapping)

        assert "L2" in report.triggers_with_crossfade
        assert "L2" in report.triggers_configured

    def test_trigger_with_bow_mode_enabled(self):
        """Trigger with bow_mode is in triggers_with_bow."""
        mapping = Mapping()
        mapping.r2_trigger.bow_mode = True
        report = audit_mapping(mapping)

        assert "R2" in report.triggers_with_bow
        assert "R2" in report.triggers_configured


class TestAuditMappingSticks:
    """Test stick audit logic."""

    def test_sticks_chord_disabled_by_default(self):
        """Default sticks have chord_enabled=False."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        assert report.sticks_with_chord == []

    def test_left_stick_with_chord_enabled(self):
        """Stick with chord_enabled=True appears in sticks_with_chord."""
        mapping = Mapping()
        mapping.left_stick.chord_enabled = True
        report = audit_mapping(mapping)

        assert "left_stick" in report.sticks_with_chord
        assert "right_stick" not in report.sticks_with_chord

    def test_right_stick_with_chord_enabled(self):
        """Right stick chord appears separately."""
        mapping = Mapping()
        mapping.right_stick.chord_enabled = True
        report = audit_mapping(mapping)

        assert "right_stick" in report.sticks_with_chord
        assert "left_stick" not in report.sticks_with_chord

    def test_both_sticks_with_chord(self):
        """Both sticks with chord."""
        mapping = Mapping()
        mapping.left_stick.chord_enabled = True
        mapping.right_stick.chord_enabled = True
        report = audit_mapping(mapping)

        assert "left_stick" in report.sticks_with_chord
        assert "right_stick" in report.sticks_with_chord


class TestAuditMappingFeatures:
    """Test feature flag audit logic."""

    def test_shift_layer_disabled_by_default(self):
        """Default mapping has shift_layer disabled."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        assert report.has_shift_layer is False

    def test_shift_layer_enabled_with_button(self):
        """Shift layer is enabled when enabled=True and shift_button >= 0."""
        mapping = Mapping()
        mapping.shift_layer.enabled = True
        mapping.shift_layer.shift_button = 8
        report = audit_mapping(mapping)

        assert report.has_shift_layer is True

    def test_shift_layer_enabled_but_no_button(self):
        """Shift layer with no button set is not active."""
        mapping = Mapping()
        mapping.shift_layer.enabled = True
        mapping.shift_layer.shift_button = -1
        report = audit_mapping(mapping)

        assert report.has_shift_layer is False

    def test_ab_compare_disabled_by_default(self):
        """Default mapping has ab_compare disabled."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        assert report.has_ab_compare is False

    def test_ab_compare_enabled_with_slug(self):
        """A/B Compare is enabled when ab_compare_enabled=True and slug is set."""
        mapping = Mapping()
        mapping.ab_compare_enabled = True
        mapping.ab_b_preset_slug = "preset_b"
        report = audit_mapping(mapping)

        assert report.has_ab_compare is True

    def test_ab_compare_enabled_but_no_slug(self):
        """A/B Compare with no slug is not active."""
        mapping = Mapping()
        mapping.ab_compare_enabled = True
        mapping.ab_b_preset_slug = None
        report = audit_mapping(mapping)

        assert report.has_ab_compare is False

    def test_macros_empty_by_default(self):
        """Default mapping has no macros."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        assert report.has_macros is False

    def test_macros_non_empty(self):
        """Mapping with macros has has_macros=True."""
        mapping = Mapping()
        mapping.macros = [Macro(name="Test", events=[])]
        report = audit_mapping(mapping)

        assert report.has_macros is True

    def test_setlist_disabled_by_default(self):
        """Default mapping has setlist_size=0."""
        mapping = Mapping()
        report = audit_mapping(mapping)

        assert report.setlist_size == 0

    def test_setlist_enabled_with_presets(self):
        """Enabled setlist with presets reports correct size."""
        mapping = Mapping()
        mapping.setlist.enabled = True
        mapping.setlist.presets = ["preset_1", "preset_2", "preset_3"]
        report = audit_mapping(mapping)

        assert report.setlist_size == 3

    def test_setlist_enabled_empty(self):
        """Enabled setlist with no presets."""
        mapping = Mapping()
        mapping.setlist.enabled = True
        mapping.setlist.presets = []
        report = audit_mapping(mapping)

        assert report.setlist_size == 0


class TestAuditMappingChannels:
    """Test MIDI channel audit logic."""

    def test_default_mapping_single_channel(self):
        """Default mapping uses only the global midi_channel."""
        mapping = Mapping()
        mapping.midi_channel = 0
        report = audit_mapping(mapping)

        assert report.total_channels_used == 1

    def test_button_channel_override_counted(self):
        """Button channel override adds to total."""
        mapping = Mapping()
        mapping.midi_channel = 0
        mapping.button_channels = {0: 5}
        report = audit_mapping(mapping)

        assert report.total_channels_used == 2
        assert 0 in [mapping.midi_channel, list(mapping.button_channels.values())[0]]

    def test_axis_channel_override_counted(self):
        """Axis channel override adds to total."""
        mapping = Mapping()
        mapping.midi_channel = 0
        mapping.axis_channels = {0: 3}
        report = audit_mapping(mapping)

        assert report.total_channels_used == 2

    def test_trigger_crossfade_channel_counted(self):
        """Trigger crossfade channel override adds to total."""
        mapping = Mapping()
        mapping.midi_channel = 0
        mapping.l2_trigger.crossfade_enabled = True
        mapping.l2_trigger.crossfade_channel_b = 7
        report = audit_mapping(mapping)

        assert 7 in [mapping.midi_channel, mapping.l2_trigger.crossfade_channel_b]
        assert report.total_channels_used >= 2

    def test_stick_chord_channel_counted(self):
        """Stick chord channel override adds to total."""
        mapping = Mapping()
        mapping.midi_channel = 0
        mapping.left_stick.chord_enabled = True
        mapping.left_stick.chord_channel = 10
        report = audit_mapping(mapping)

        assert 10 in [mapping.midi_channel, mapping.left_stick.chord_channel]
        assert report.total_channels_used >= 2

    def test_duplicate_channels_counted_once(self):
        """Duplicate channels across different controls counted once."""
        mapping = Mapping()
        mapping.midi_channel = 0
        mapping.button_channels = {0: 5}
        mapping.axis_channels = {0: 5}  # Same channel as button override
        report = audit_mapping(mapping)

        # Should be: 0 (global), 5 (shared by button and axis)
        assert report.total_channels_used == 2


class TestAuditMappingMutation:
    """Test that audit does not mutate the mapping."""

    def test_audit_does_not_mutate_mapping(self):
        """Running audit_mapping should not modify the input mapping."""
        mapping = Mapping()
        original_buttons = dict(mapping.buttons)
        original_axes = dict(mapping.axes)

        audit_mapping(mapping)

        assert mapping.buttons == original_buttons
        assert mapping.axes == original_axes


class TestSummaryText:
    """Test summary_text output."""

    def test_summary_text_returns_string(self):
        """summary_text returns a non-empty string."""
        mapping = Mapping()
        report = audit_mapping(mapping)
        summary = summary_text(report)

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_text_contains_button_info(self):
        """Summary includes button coverage."""
        mapping = Mapping()
        mapping.buttons[0] = 0  # Unmapped
        report = audit_mapping(mapping)
        summary = summary_text(report)

        assert "buttons" in summary.lower()

    def test_summary_text_contains_axis_info(self):
        """Summary includes axis coverage."""
        mapping = Mapping()
        report = audit_mapping(mapping)
        summary = summary_text(report)

        assert "axes" in summary.lower()

    def test_summary_text_contains_trigger_info(self):
        """Summary includes trigger info."""
        mapping = Mapping()
        mapping.l2_trigger.mode = "latch"
        report = audit_mapping(mapping)
        summary = summary_text(report)

        assert "trigger" in summary.lower()

    def test_summary_text_contains_channel_info(self):
        """Summary includes channel count."""
        mapping = Mapping()
        report = audit_mapping(mapping)
        summary = summary_text(report)

        assert "channel" in summary.lower()

    def test_summary_text_with_all_features(self):
        """Summary includes all enabled features."""
        mapping = Mapping()
        mapping.shift_layer.enabled = True
        mapping.shift_layer.shift_button = 8
        mapping.ab_compare_enabled = True
        mapping.ab_b_preset_slug = "b"
        mapping.macros = [Macro(name="Test", events=[])]
        mapping.setlist.enabled = True
        mapping.setlist.presets = ["a", "b"]

        report = audit_mapping(mapping)
        summary = summary_text(report)

        assert "shift" in summary.lower() or "feature" in summary.lower()
        assert len(summary) > 0


class TestIntegration:
    """Integration tests combining multiple audit features."""

    def test_complex_mapping_audit(self):
        """Audit a complex mapping with many features enabled."""
        mapping = Mapping()
        # Configure some buttons and axes
        mapping.buttons[0] = 0  # Unmapped
        mapping.buttons[1] = 62
        mapping.axes[0] = 0  # Unmapped

        # Enable triggers
        mapping.l2_trigger.mode = "latch"
        mapping.r2_trigger.crossfade_enabled = True

        # Enable sticks
        mapping.left_stick.chord_enabled = True

        # Enable features
        mapping.shift_layer.enabled = True
        mapping.shift_layer.shift_button = 7
        mapping.ab_compare_enabled = True
        mapping.ab_b_preset_slug = "b_preset"
        mapping.macros = [Macro(name="M1", events=[])]

        # Overrides
        mapping.button_channels = {5: 3}
        mapping.l2_trigger.crossfade_channel_b = 5

        report = audit_mapping(mapping)

        assert report.total_buttons == 11
        assert report.mapped_buttons == 10
        assert 0 in report.unmapped_buttons

        assert report.total_axes == 6
        assert report.mapped_axes == 5
        assert 0 in report.unmapped_axes

        assert "L2" in report.triggers_configured
        assert "R2" in report.triggers_configured
        assert "R2" in report.triggers_with_crossfade

        assert "left_stick" in report.sticks_with_chord

        assert report.has_shift_layer is True
        assert report.has_ab_compare is True
        assert report.has_macros is True
        assert report.total_channels_used >= 2

        summary = summary_text(report)
        assert "10/11" in summary
