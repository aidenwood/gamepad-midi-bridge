"""Test suite for mapping_audit_formatter module."""

import pytest
from gamepad_midi_bridge.mapping_audit import MappingAuditReport
from gamepad_midi_bridge.mapping_audit_formatter import (
    format_text,
    format_markdown,
    format_html,
    format_summary_line,
    colorize_text,
)


class TestFormatText:
    """Test format_text function."""

    def test_format_text_returns_multiline_string(self):
        """Test that format_text returns a multi-line string."""
        report = MappingAuditReport(
            total_buttons=24,
            mapped_buttons=12,
            total_axes=6,
            mapped_axes=6,
            total_channels_used=4,
            unique_notes_count=18,
        )
        result = format_text(report)
        assert isinstance(result, str)
        assert "\n" in result
        lines = result.split("\n")
        assert len(lines) >= 7

    def test_format_text_mentions_buttons_section(self):
        """Test that format_text includes buttons mapping."""
        report = MappingAuditReport(
            total_buttons=24,
            mapped_buttons=12,
        )
        result = format_text(report)
        assert "Buttons: 12/24 mapped" in result

    def test_format_text_mentions_axes_section(self):
        """Test that format_text includes axes mapping."""
        report = MappingAuditReport(
            total_axes=6,
            mapped_axes=6,
        )
        result = format_text(report)
        assert "Axes: 6/6 mapped" in result

    def test_format_text_mentions_triggers_when_configured(self):
        """Test that format_text includes configured triggers."""
        report = MappingAuditReport(
            triggers_configured=["L2", "R2"],
        )
        result = format_text(report)
        assert "Triggers configured: L2, R2" in result

    def test_format_text_mentions_triggers_crossfade(self):
        """Test that format_text includes trigger crossfade."""
        report = MappingAuditReport(
            triggers_with_crossfade=["L2"],
        )
        result = format_text(report)
        assert "Trigger crossfade: L2" in result

    def test_format_text_mentions_sticks_chord(self):
        """Test that format_text includes sticks with chord."""
        report = MappingAuditReport(
            sticks_with_chord=["left_stick", "right_stick"],
        )
        result = format_text(report)
        assert "Sticks with chord: left_stick, right_stick" in result

    def test_format_text_mentions_channels(self):
        """Test that format_text includes channels used."""
        report = MappingAuditReport(total_channels_used=4)
        result = format_text(report)
        assert "Channels used: 4" in result

    def test_format_text_mentions_unique_notes(self):
        """Test that format_text includes unique notes count."""
        report = MappingAuditReport(unique_notes_count=18)
        result = format_text(report)
        assert "Unique notes: 18" in result

    def test_format_text_mentions_features(self):
        """Test that format_text includes feature flags."""
        report = MappingAuditReport(
            has_shift_layer=True,
            has_ab_compare=True,
            has_macros=True,
        )
        result = format_text(report)
        assert "Features:" in result
        assert "shift_layer" in result
        assert "ab_compare" in result
        assert "macros" in result

    def test_format_text_mentions_setlist_size(self):
        """Test that format_text includes setlist size."""
        report = MappingAuditReport(setlist_size=5)
        result = format_text(report)
        assert "Setlist size: 5" in result


class TestFormatMarkdown:
    """Test format_markdown function."""

    def test_format_markdown_contains_headers(self):
        """Test that format_markdown contains ## headers."""
        report = MappingAuditReport()
        result = format_markdown(report)
        assert "## Audit Report" in result
        assert "### Buttons" in result
        assert "### Axes" in result
        assert "### Triggers" in result

    def test_format_markdown_contains_bullets(self):
        """Test that format_markdown contains - bullets."""
        report = MappingAuditReport()
        result = format_markdown(report)
        assert "- " in result

    def test_format_markdown_formats_buttons(self):
        """Test markdown formatting of button section."""
        report = MappingAuditReport(
            total_buttons=24,
            mapped_buttons=12,
        )
        result = format_markdown(report)
        assert "### Buttons" in result
        assert "- 12 / 24 mapped" in result

    def test_format_markdown_formats_axes(self):
        """Test markdown formatting of axes section."""
        report = MappingAuditReport(
            total_axes=6,
            mapped_axes=4,
        )
        result = format_markdown(report)
        assert "### Axes" in result
        assert "- 4 / 6 mapped" in result

    def test_format_markdown_includes_setlist(self):
        """Test that markdown includes setlist section."""
        report = MappingAuditReport(setlist_size=5)
        result = format_markdown(report)
        assert "### Setlist" in result
        assert "- Size: 5 presets" in result


class TestFormatHtml:
    """Test format_html function."""

    def test_format_html_contains_h2_headers(self):
        """Test that format_html contains <h2> headers."""
        report = MappingAuditReport()
        result = format_html(report)
        assert "<h2>Audit Report</h2>" in result

    def test_format_html_contains_h3_headers(self):
        """Test that format_html contains <h3> headers."""
        report = MappingAuditReport()
        result = format_html(report)
        assert "<h3>Buttons</h3>" in result
        assert "<h3>Axes</h3>" in result

    def test_format_html_contains_ul_li(self):
        """Test that format_html contains <ul> and <li> elements."""
        report = MappingAuditReport()
        result = format_html(report)
        assert "<ul>" in result
        assert "<li>" in result
        assert "</li>" in result
        assert "</ul>" in result

    def test_format_html_formats_buttons(self):
        """Test HTML formatting of button section."""
        report = MappingAuditReport(
            total_buttons=24,
            mapped_buttons=12,
        )
        result = format_html(report)
        assert "<h3>Buttons</h3>" in result
        assert "<li>12 / 24 mapped</li>" in result

    def test_format_html_includes_features(self):
        """Test that HTML includes features section."""
        report = MappingAuditReport(
            has_shift_layer=True,
            has_ab_compare=False,
            has_macros=False,
        )
        result = format_html(report)
        assert "<h3>Features</h3>" in result
        assert "<li>shift_layer</li>" in result


class TestFormatSummaryLine:
    """Test format_summary_line function."""

    def test_format_summary_line_returns_single_line(self):
        """Test that format_summary_line returns a single line."""
        report = MappingAuditReport(
            mapped_buttons=12,
            mapped_axes=6,
            total_channels_used=4,
        )
        result = format_summary_line(report)
        assert isinstance(result, str)
        assert "\n" not in result

    def test_format_summary_line_includes_button_count(self):
        """Test that summary includes button count."""
        report = MappingAuditReport(mapped_buttons=12)
        result = format_summary_line(report)
        assert "12 buttons" in result

    def test_format_summary_line_includes_axis_count(self):
        """Test that summary includes axis count."""
        report = MappingAuditReport(mapped_axes=6)
        result = format_summary_line(report)
        assert "6 axes" in result

    def test_format_summary_line_includes_channel_count(self):
        """Test that summary includes channel count."""
        report = MappingAuditReport(total_channels_used=4)
        result = format_summary_line(report)
        assert "4 channels" in result

    def test_format_summary_line_includes_features(self):
        """Test that summary includes features list."""
        report = MappingAuditReport(
            mapped_buttons=12,
            mapped_axes=6,
            total_channels_used=4,
            triggers_with_crossfade=["L2"],
            sticks_with_chord=["left_stick"],
            has_shift_layer=True,
        )
        result = format_summary_line(report)
        assert "with " in result
        assert "crossfade" in result
        assert "chord" in result
        assert "shift layer" in result

    def test_format_summary_line_no_features_no_with(self):
        """Test summary without features doesn't include 'with'."""
        report = MappingAuditReport(
            mapped_buttons=12,
            mapped_axes=6,
            total_channels_used=4,
        )
        result = format_summary_line(report)
        assert "with" not in result


class TestColorizeText:
    """Test colorize_text function."""

    def test_colorize_text_with_color_true_wraps_numbers(self):
        """Test that colorize_text with color=True wraps numbers in ANSI."""
        text = "12 buttons, 6 axes"
        result = colorize_text(text, color_terminal=True)
        # Should contain ANSI escape codes
        assert "\033[96m" in result  # BRIGHT_CYAN
        assert "\033[0m" in result  # RESET
        # Original numbers should be present
        assert "12" in result
        assert "6" in result

    def test_colorize_text_with_color_false_unchanged(self):
        """Test that colorize_text with color=False returns unchanged."""
        text = "12 buttons, 6 axes"
        result = colorize_text(text, color_terminal=False)
        assert result == text

    def test_colorize_text_default_color_is_true(self):
        """Test that default color_terminal is True."""
        text = "24 buttons"
        result = colorize_text(text)
        # Default should apply colors
        assert "\033[96m" in result

    def test_colorize_text_preserves_text_content(self):
        """Test that colorize_text preserves text content."""
        text = "12 buttons, 6 axes, 4 channels"
        result = colorize_text(text, color_terminal=False)
        assert result == text


class TestEmptyReportHandling:
    """Test handling of empty/zero reports."""

    def test_empty_report_format_text(self):
        """Test that empty report formats gracefully."""
        report = MappingAuditReport()
        result = format_text(report)
        assert "Buttons: 0/0 mapped" in result
        assert "Axes: 0/0 mapped" in result
        assert "Channels used: 0" in result

    def test_empty_report_format_markdown(self):
        """Test that empty report renders valid markdown."""
        report = MappingAuditReport()
        result = format_markdown(report)
        assert "## Audit Report" in result
        assert "### Buttons" in result

    def test_empty_report_format_html(self):
        """Test that empty report renders valid HTML."""
        report = MappingAuditReport()
        result = format_html(report)
        assert "<h2>Audit Report</h2>" in result
        assert "<ul>" in result

    def test_empty_report_format_summary_line(self):
        """Test that empty report summary line is valid."""
        report = MappingAuditReport()
        result = format_summary_line(report)
        assert isinstance(result, str)
        assert "0 buttons" in result


class TestCompleteReportHandling:
    """Test handling of fully-featured reports."""

    def test_complete_report_all_sections_present(self):
        """Test that complete report includes every section."""
        report = MappingAuditReport(
            total_buttons=24,
            mapped_buttons=12,
            total_axes=6,
            mapped_axes=6,
            triggers_configured=["L2", "R2"],
            triggers_with_crossfade=["L2"],
            triggers_with_bow=["R2"],
            sticks_with_chord=["left_stick", "right_stick"],
            total_channels_used=4,
            unique_notes_count=18,
            has_shift_layer=True,
            has_ab_compare=True,
            has_macros=True,
            setlist_size=5,
        )
        result = format_text(report)
        assert "Buttons: 12/24 mapped" in result
        assert "Axes: 6/6 mapped" in result
        assert "Triggers configured:" in result
        assert "Trigger crossfade: L2" in result
        assert "Sticks with chord:" in result
        assert "Channels used: 4" in result
        assert "Unique notes: 18" in result
        assert "Features:" in result
        assert "Setlist size: 5" in result


class TestFunctionPurity:
    """Test that formatter functions don't mutate the report."""

    def test_format_text_does_not_mutate(self):
        """Test that format_text doesn't mutate the report."""
        report = MappingAuditReport(
            total_buttons=24,
            mapped_buttons=12,
            triggers_configured=["L2"],
        )
        original_buttons = report.total_buttons
        original_triggers = report.triggers_configured.copy()

        format_text(report)

        assert report.total_buttons == original_buttons
        assert report.triggers_configured == original_triggers

    def test_format_markdown_does_not_mutate(self):
        """Test that format_markdown doesn't mutate the report."""
        report = MappingAuditReport(
            total_buttons=24,
            mapped_buttons=12,
        )
        original_buttons = report.total_buttons

        format_markdown(report)

        assert report.total_buttons == original_buttons

    def test_format_html_does_not_mutate(self):
        """Test that format_html doesn't mutate the report."""
        report = MappingAuditReport(setlist_size=5)
        original_setlist = report.setlist_size

        format_html(report)

        assert report.setlist_size == original_setlist

    def test_format_summary_line_does_not_mutate(self):
        """Test that format_summary_line doesn't mutate the report."""
        report = MappingAuditReport(
            mapped_buttons=12,
            has_shift_layer=True,
        )
        original_buttons = report.mapped_buttons
        original_shift = report.has_shift_layer

        format_summary_line(report)

        assert report.mapped_buttons == original_buttons
        assert report.has_shift_layer == original_shift
