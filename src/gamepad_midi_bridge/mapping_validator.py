"""Mapping validator — validates untrusted JSON mapping dicts without raising.

Pure stdlib only. Returns a list of ValidationIssue objects describing any
schema, type, or range violations without throwing exceptions.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional


@dataclass
class ValidationIssue:
    """A single validation problem found during mapping inspection.

    Attributes:
        severity: "error", "warning", or "info"
        path: dotted path like "buttons.5.note" or top-level key
        message: human-readable description of the issue
    """
    severity: str  # "error" | "warning" | "info"
    path: str      # e.g. "buttons.5.note"
    message: str

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ValidationIssue:
        """Deserialize from a plain dict."""
        return cls(
            severity=data.get("severity", "info"),
            path=data.get("path", ""),
            message=data.get("message", ""),
        )


def validate_mapping(mapping_dict: dict) -> List[ValidationIssue]:
    """Validate an untrusted mapping dict and return all issues found.

    Args:
        mapping_dict: The raw dict, possibly from a marketplace download or file.

    Returns:
        A list of ValidationIssue objects. Empty list = valid mapping.
        Does not raise exceptions under any circumstance.
    """
    issues: List[ValidationIssue] = []

    if not isinstance(mapping_dict, dict):
        issues.append(ValidationIssue(
            severity="error",
            path="<root>",
            message="Mapping must be a dict, got " + type(mapping_dict).__name__,
        ))
        return issues

    # Schema version checks
    schema_version = mapping_dict.get("schema_version")
    if schema_version is None:
        issues.append(ValidationIssue(
            severity="warning",
            path="schema_version",
            message="schema_version is missing; will use defaults for new fields",
        ))
    elif not isinstance(schema_version, int):
        issues.append(ValidationIssue(
            severity="error",
            path="schema_version",
            message=f"schema_version must be int, got {type(schema_version).__name__}",
        ))

    # Buttons validation
    buttons = mapping_dict.get("buttons")
    if buttons is not None:
        if not isinstance(buttons, dict):
            issues.append(ValidationIssue(
                severity="error",
                path="buttons",
                message=f"buttons must be a dict, got {type(buttons).__name__}",
            ))
        else:
            for btn_idx, btn_cfg in buttons.items():
                if not isinstance(btn_cfg, dict):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"buttons.{btn_idx}",
                        message=f"button config must be a dict, got {type(btn_cfg).__name__}",
                    ))
                    continue

                # Check note field
                note = btn_cfg.get("note")
                if note is not None:
                    if not isinstance(note, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"buttons.{btn_idx}.note",
                            message=f"note must be int, got {type(note).__name__}",
                        ))
                    elif not (0 <= note <= 127):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"buttons.{btn_idx}.note",
                            message=f"note out of range (0..127): {note}",
                        ))

                # Check channel field
                channel = btn_cfg.get("channel")
                if channel is not None:
                    if not isinstance(channel, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"buttons.{btn_idx}.channel",
                            message=f"channel must be int, got {type(channel).__name__}",
                        ))
                    elif not (1 <= channel <= 16):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"buttons.{btn_idx}.channel",
                            message=f"channel out of range (1..16): {channel}",
                        ))

                # Check velocity field
                velocity = btn_cfg.get("velocity")
                if velocity is not None:
                    if not isinstance(velocity, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"buttons.{btn_idx}.velocity",
                            message=f"velocity must be int, got {type(velocity).__name__}",
                        ))
                    elif not (1 <= velocity <= 127):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"buttons.{btn_idx}.velocity",
                            message=f"velocity out of range (1..127): {velocity}",
                        ))

    # Axes validation
    axes = mapping_dict.get("axes")
    if axes is not None:
        if not isinstance(axes, dict):
            issues.append(ValidationIssue(
                severity="error",
                path="axes",
                message=f"axes must be a dict, got {type(axes).__name__}",
            ))
        else:
            for axis_idx, axis_cfg in axes.items():
                if not isinstance(axis_cfg, dict):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"axes.{axis_idx}",
                        message=f"axis config must be a dict, got {type(axis_cfg).__name__}",
                    ))
                    continue

                # Check cc field
                cc = axis_cfg.get("cc")
                if cc is not None:
                    if not isinstance(cc, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"axes.{axis_idx}.cc",
                            message=f"cc must be int, got {type(cc).__name__}",
                        ))
                    elif not (0 <= cc <= 127):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"axes.{axis_idx}.cc",
                            message=f"cc out of range (0..127): {cc}",
                        ))

                # Check channel field
                channel = axis_cfg.get("channel")
                if channel is not None:
                    if not isinstance(channel, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"axes.{axis_idx}.channel",
                            message=f"channel must be int, got {type(channel).__name__}",
                        ))
                    elif not (1 <= channel <= 16):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"axes.{axis_idx}.channel",
                            message=f"channel out of range (1..16): {channel}",
                        ))

    # Triggers validation
    triggers = mapping_dict.get("triggers")
    if triggers is not None:
        if not isinstance(triggers, dict):
            issues.append(ValidationIssue(
                severity="error",
                path="triggers",
                message=f"triggers must be a dict, got {type(triggers).__name__}",
            ))
        else:
            for trigger_name, trigger_cfg in triggers.items():
                if not isinstance(trigger_cfg, dict):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"triggers.{trigger_name}",
                        message=f"trigger config must be a dict, got {type(trigger_cfg).__name__}",
                    ))
                    continue

                # Check cc field
                cc = trigger_cfg.get("cc")
                if cc is not None:
                    if not isinstance(cc, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"triggers.{trigger_name}.cc",
                            message=f"cc must be int, got {type(cc).__name__}",
                        ))
                    elif not (0 <= cc <= 127):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"triggers.{trigger_name}.cc",
                            message=f"cc out of range (0..127): {cc}",
                        ))

                # Check channel field
                channel = trigger_cfg.get("channel")
                if channel is not None:
                    if not isinstance(channel, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"triggers.{trigger_name}.channel",
                            message=f"channel must be int, got {type(channel).__name__}",
                        ))
                    elif not (1 <= channel <= 16):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"triggers.{trigger_name}.channel",
                            message=f"channel out of range (1..16): {channel}",
                        ))

                # Check crossfade_cc_b field
                crossfade_cc_b = trigger_cfg.get("crossfade_cc_b")
                if crossfade_cc_b is not None:
                    if not isinstance(crossfade_cc_b, int):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"triggers.{trigger_name}.crossfade_cc_b",
                            message=f"crossfade_cc_b must be int, got {type(crossfade_cc_b).__name__}",
                        ))
                    elif not (0 <= crossfade_cc_b <= 127):
                        issues.append(ValidationIssue(
                            severity="error",
                            path=f"triggers.{trigger_name}.crossfade_cc_b",
                            message=f"crossfade_cc_b out of range (0..127): {crossfade_cc_b}",
                        ))

    # Sticks validation (left_stick, right_stick)
    for stick_name in ("left_stick", "right_stick"):
        stick_cfg = mapping_dict.get(stick_name)
        if stick_cfg is not None:
            if not isinstance(stick_cfg, dict):
                issues.append(ValidationIssue(
                    severity="error",
                    path=stick_name,
                    message=f"{stick_name} must be a dict, got {type(stick_cfg).__name__}",
                ))
                continue

            # Check chord_threshold field
            chord_threshold = stick_cfg.get("chord_threshold")
            if chord_threshold is not None:
                if not isinstance(chord_threshold, (int, float)):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"{stick_name}.chord_threshold",
                        message=f"chord_threshold must be numeric, got {type(chord_threshold).__name__}",
                    ))
                elif not (0 <= chord_threshold <= 1):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"{stick_name}.chord_threshold",
                        message=f"chord_threshold out of range (0..1): {chord_threshold}",
                    ))

            # Check chord_velocity field
            chord_velocity = stick_cfg.get("chord_velocity")
            if chord_velocity is not None:
                if not isinstance(chord_velocity, int):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"{stick_name}.chord_velocity",
                        message=f"chord_velocity must be int, got {type(chord_velocity).__name__}",
                    ))
                elif not (1 <= chord_velocity <= 127):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"{stick_name}.chord_velocity",
                        message=f"chord_velocity out of range (1..127): {chord_velocity}",
                    ))

    # Macros validation (if list)
    macros = mapping_dict.get("macros")
    if macros is not None:
        if not isinstance(macros, list):
            issues.append(ValidationIssue(
                severity="error",
                path="macros",
                message=f"macros must be a list, got {type(macros).__name__}",
            ))
        else:
            for idx, macro in enumerate(macros):
                if not isinstance(macro, dict):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"macros.{idx}",
                        message=f"macro must be a dict, got {type(macro).__name__}",
                    ))
                    continue

                # Check name field
                name = macro.get("name")
                if name is None:
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"macros.{idx}.name",
                        message="macro must have a 'name' field",
                    ))

                # Check events field
                events = macro.get("events")
                if events is None:
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"macros.{idx}.events",
                        message="macro must have an 'events' field",
                    ))
                elif not isinstance(events, list):
                    issues.append(ValidationIssue(
                        severity="error",
                        path=f"macros.{idx}.events",
                        message=f"macro events must be a list, got {type(events).__name__}",
                    ))

    return issues


def is_valid(mapping_dict: dict) -> bool:
    """Return True if the mapping has no 'error' severity issues.

    Args:
        mapping_dict: The raw dict to validate.

    Returns:
        True if no errors found (warnings/info allowed), False otherwise.
    """
    issues = validate_mapping(mapping_dict)
    return not any(issue.severity == "error" for issue in issues)


def count_by_severity(issues: List[ValidationIssue]) -> Dict[str, int]:
    """Count issues grouped by severity.

    Args:
        issues: List of ValidationIssue objects.

    Returns:
        Dict with keys "error", "warning", "info" and their counts.
    """
    counts: Dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        if issue.severity in counts:
            counts[issue.severity] += 1
    return counts


def format_issues(issues: List[ValidationIssue]) -> str:
    """Format a list of issues into human-readable multi-line string.

    Args:
        issues: List of ValidationIssue objects.

    Returns:
        Multi-line string with one issue per line, formatted as:
        "[SEVERITY] path: message"
        Returns empty string if no issues.
    """
    if not issues:
        return ""

    lines = []
    for issue in issues:
        line = f"[{issue.severity.upper()}] {issue.path}: {issue.message}"
        lines.append(line)
    return "\n".join(lines)
