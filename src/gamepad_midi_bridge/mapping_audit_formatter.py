"""Mapping audit report formatter — render MappingAuditReport as text/markdown/HTML."""

from .mapping_audit import MappingAuditReport


def format_text(report: MappingAuditReport) -> str:
    """Return a multi-line plain-text summary of the audit report.

    Sections:
      - Buttons: mapped/total
      - Axes: mapped/total
      - Triggers configured
      - Trigger crossfade
      - Sticks with chord
      - Channels used
      - Unique notes
      - Features: shift_layer, ab_compare, macros (count)
      - Setlist size
    """
    lines = []

    # Buttons
    lines.append(f"Buttons: {report.mapped_buttons}/{report.total_buttons} mapped")

    # Axes
    lines.append(f"Axes: {report.mapped_axes}/{report.total_axes} mapped")

    # Triggers configured
    if report.triggers_configured:
        trigger_list = ", ".join(report.triggers_configured)
        lines.append(f"Triggers configured: {trigger_list}")
    else:
        lines.append("Triggers configured: none")

    # Trigger crossfade
    if report.triggers_with_crossfade:
        crossfade_list = ", ".join(report.triggers_with_crossfade)
        lines.append(f"Trigger crossfade: {crossfade_list}")

    # Sticks with chord
    if report.sticks_with_chord:
        stick_list = ", ".join(report.sticks_with_chord)
        lines.append(f"Sticks with chord: {stick_list}")

    # Channels used
    lines.append(f"Channels used: {report.total_channels_used}")

    # Unique notes
    lines.append(f"Unique notes: {report.unique_notes_count}")

    # Features
    features = []
    if report.has_shift_layer:
        features.append("shift_layer")
    if report.has_ab_compare:
        features.append("ab_compare")
    if report.has_macros:
        # Count macros to display in format
        features.append("macros")

    if features:
        features_str = ", ".join(features)
        lines.append(f"Features: {features_str}")
    else:
        lines.append("Features: none")

    # Setlist size
    lines.append(f"Setlist size: {report.setlist_size}")

    return "\n".join(lines)


def format_markdown(report: MappingAuditReport) -> str:
    """Return a markdown-formatted summary of the audit report.

    Sections use ## headers and - bullets for lists.
    """
    lines = []

    lines.append("## Audit Report\n")

    # Buttons
    lines.append("### Buttons")
    lines.append(f"- {report.mapped_buttons} / {report.total_buttons} mapped\n")

    # Axes
    lines.append("### Axes")
    lines.append(f"- {report.mapped_axes} / {report.total_axes} mapped\n")

    # Triggers
    lines.append("### Triggers")
    if report.triggers_configured:
        trigger_list = ", ".join(report.triggers_configured)
        lines.append(f"- Configured: {trigger_list}")
    else:
        lines.append("- Configured: none")

    if report.triggers_with_crossfade:
        crossfade_list = ", ".join(report.triggers_with_crossfade)
        lines.append(f"- Crossfade: {crossfade_list}")
    lines.append("")

    # Sticks
    lines.append("### Sticks")
    if report.sticks_with_chord:
        stick_list = ", ".join(report.sticks_with_chord)
        lines.append(f"- Chord enabled: {stick_list}")
    else:
        lines.append("- Chord enabled: none")
    lines.append("")

    # Channels
    lines.append("### Channels")
    lines.append(f"- Total unique channels: {report.total_channels_used}\n")

    # Notes
    lines.append("### Notes")
    lines.append(f"- Unique notes: {report.unique_notes_count}\n")

    # Features
    lines.append("### Features")
    features = []
    if report.has_shift_layer:
        features.append("shift_layer")
    if report.has_ab_compare:
        features.append("ab_compare")
    if report.has_macros:
        features.append("macros")

    if features:
        for feature in features:
            lines.append(f"- {feature}")
    else:
        lines.append("- none enabled")
    lines.append("")

    # Setlist
    lines.append("### Setlist")
    lines.append(f"- Size: {report.setlist_size} presets\n")

    return "\n".join(lines)


def format_html(report: MappingAuditReport) -> str:
    """Return an HTML-formatted summary of the audit report.

    Uses h2/h3 headers, ul/li lists, and basic structure.
    """
    lines = []

    lines.append("<h2>Audit Report</h2>")

    # Buttons
    lines.append("<h3>Buttons</h3>")
    lines.append("<ul>")
    lines.append(
        f"<li>{report.mapped_buttons} / {report.total_buttons} mapped</li>"
    )
    lines.append("</ul>")

    # Axes
    lines.append("<h3>Axes</h3>")
    lines.append("<ul>")
    lines.append(f"<li>{report.mapped_axes} / {report.total_axes} mapped</li>")
    lines.append("</ul>")

    # Triggers
    lines.append("<h3>Triggers</h3>")
    lines.append("<ul>")
    if report.triggers_configured:
        trigger_list = ", ".join(report.triggers_configured)
        lines.append(f"<li>Configured: {trigger_list}</li>")
    else:
        lines.append("<li>Configured: none</li>")
    if report.triggers_with_crossfade:
        crossfade_list = ", ".join(report.triggers_with_crossfade)
        lines.append(f"<li>Crossfade: {crossfade_list}</li>")
    lines.append("</ul>")

    # Sticks
    lines.append("<h3>Sticks</h3>")
    lines.append("<ul>")
    if report.sticks_with_chord:
        stick_list = ", ".join(report.sticks_with_chord)
        lines.append(f"<li>Chord enabled: {stick_list}</li>")
    else:
        lines.append("<li>Chord enabled: none</li>")
    lines.append("</ul>")

    # Channels
    lines.append("<h3>Channels</h3>")
    lines.append("<ul>")
    lines.append(f"<li>Total unique channels: {report.total_channels_used}</li>")
    lines.append("</ul>")

    # Notes
    lines.append("<h3>Notes</h3>")
    lines.append("<ul>")
    lines.append(f"<li>Unique notes: {report.unique_notes_count}</li>")
    lines.append("</ul>")

    # Features
    lines.append("<h3>Features</h3>")
    lines.append("<ul>")
    features = []
    if report.has_shift_layer:
        features.append("shift_layer")
    if report.has_ab_compare:
        features.append("ab_compare")
    if report.has_macros:
        features.append("macros")

    if features:
        for feature in features:
            lines.append(f"<li>{feature}</li>")
    else:
        lines.append("<li>none enabled</li>")
    lines.append("</ul>")

    # Setlist
    lines.append("<h3>Setlist</h3>")
    lines.append("<ul>")
    lines.append(f"<li>Size: {report.setlist_size} presets</li>")
    lines.append("</ul>")

    return "\n".join(lines)


def format_summary_line(report: MappingAuditReport) -> str:
    """Return a single-line elevator pitch summary.

    Example: "12 buttons, 6 axes, 4 channels, with crossfade + chord + shift layer"
    """
    parts = []

    # Button count
    parts.append(f"{report.mapped_buttons} buttons")

    # Axis count
    parts.append(f"{report.mapped_axes} axes")

    # Channel count
    parts.append(f"{report.total_channels_used} channels")

    # Feature list
    features = []
    if report.triggers_with_crossfade:
        features.append("crossfade")
    if report.sticks_with_chord:
        features.append("chord")
    if report.has_shift_layer:
        features.append("shift layer")
    if report.has_ab_compare:
        features.append("ab compare")
    if report.has_macros:
        features.append("macros")

    if features:
        parts.append("with " + " + ".join(features))

    return ", ".join(parts)


def colorize_text(text: str, color_terminal: bool = True) -> str:
    """Optionally wrap key numbers in ANSI bright-cyan color.

    If color_terminal=False, returns text unchanged.
    Looks for numeric patterns and wraps them in ANSI bright-cyan (\033[96m).
    """
    if not color_terminal:
        return text

    # ANSI codes
    BRIGHT_CYAN = "\033[96m"
    RESET = "\033[0m"

    # Replace patterns like "12/" or "6 " with colored versions
    import re

    # Match numbers that appear in lines (e.g., "12/24", "6 mapped")
    def color_number(match):
        return BRIGHT_CYAN + match.group(0) + RESET

    # Color any sequence of digits
    result = re.sub(r"\d+", color_number, text)

    return result
