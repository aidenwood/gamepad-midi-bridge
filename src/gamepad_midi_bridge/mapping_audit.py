"""Mapping audit helper — coverage report for which controls are mapped/configured."""

from dataclasses import dataclass, asdict
from typing import List

from .mapping import Mapping


@dataclass
class MappingAuditReport:
    """Coverage summary for a Mapping — which controls are mapped, which are defaults.

    Fields:
      - total_buttons: number of buttons in the mapping's buttons dict
      - mapped_buttons: count of buttons with non-zero note or CC
      - unmapped_buttons: list of button indices with default (0) note
      - total_axes: number of axes in the mapping's axes dict
      - mapped_axes: count of axes with non-zero CC number
      - unmapped_axes: list of axis indices with default (0) CC
      - triggers_configured: list of trigger names (e.g. ["L2", "R2"]) with non-default config
      - triggers_with_crossfade: list of trigger names with crossfade enabled
      - triggers_with_bow: list of trigger names with bow_mode enabled
      - sticks_with_chord: list of stick names (e.g. ["left_stick", "right_stick"]) with chord enabled
      - total_channels_used: count of unique MIDI channels (mapping.midi_channel + overrides)
      - unique_notes_count: count of unique MIDI notes across mapped buttons
      - has_shift_layer: bool, True if shift_layer is enabled and shift_button is set
      - has_ab_compare: bool, True if ab_compare_enabled and ab_b_preset_slug is set
      - has_macros: bool, True if macros list is non-empty
      - setlist_size: int, length of setlist.presets (0 if disabled)
    """

    total_buttons: int = 0
    mapped_buttons: int = 0
    unmapped_buttons: List[int] = None
    total_axes: int = 0
    mapped_axes: int = 0
    unmapped_axes: List[int] = None
    triggers_configured: List[str] = None
    triggers_with_crossfade: List[str] = None
    triggers_with_bow: List[str] = None
    sticks_with_chord: List[str] = None
    total_channels_used: int = 0
    unique_notes_count: int = 0
    has_shift_layer: bool = False
    has_ab_compare: bool = False
    has_macros: bool = False
    setlist_size: int = 0

    def __post_init__(self) -> None:
        """Initialize list fields to empty lists if None."""
        if self.unmapped_buttons is None:
            self.unmapped_buttons = []
        if self.unmapped_axes is None:
            self.unmapped_axes = []
        if self.triggers_configured is None:
            self.triggers_configured = []
        if self.triggers_with_crossfade is None:
            self.triggers_with_crossfade = []
        if self.triggers_with_bow is None:
            self.triggers_with_bow = []
        if self.sticks_with_chord is None:
            self.sticks_with_chord = []

    def to_dict(self) -> dict:
        """Round-trip to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MappingAuditReport":
        """Reconstruct from dict."""
        return cls(**data)


def audit_mapping(mapping: Mapping) -> MappingAuditReport:
    """Build a coverage report for a Mapping.

    Inspects buttons, axes, triggers, sticks, and feature toggles to count
    mapped controls and identify unconfigured ones.
    """
    report = MappingAuditReport()

    # ===== Buttons
    total_buttons = len(mapping.buttons)
    report.total_buttons = total_buttons
    mapped = []
    unmapped = []
    unique_notes = set()

    for btn_idx, note in mapping.buttons.items():
        if note != 0:
            mapped.append(btn_idx)
            unique_notes.add(note)
        else:
            unmapped.append(btn_idx)

    report.mapped_buttons = len(mapped)
    report.unmapped_buttons = sorted(unmapped)
    report.unique_notes_count = len(unique_notes)

    # ===== Axes
    total_axes = len(mapping.axes)
    report.total_axes = total_axes
    mapped_axes = []
    unmapped_axes = []

    for axis_idx, cc in mapping.axes.items():
        if cc != 0:
            mapped_axes.append(axis_idx)
        else:
            unmapped_axes.append(axis_idx)

    report.mapped_axes = len(mapped_axes)
    report.unmapped_axes = sorted(unmapped_axes)

    # ===== Triggers (L2 / R2)
    triggers_configured = []
    triggers_with_crossfade = []
    triggers_with_bow = []

    # Check L2 trigger
    l2_config = getattr(mapping, "l2_trigger", None)
    if l2_config:
        is_configured = (
            l2_config.mode != "linear"
            or l2_config.ceiling != 127
            or l2_config.latch_threshold != 0.5
            or l2_config.gate_button is not None
            or l2_config.bow_mode
            or l2_config.crossfade_enabled
            or l2_config.aftertouch.enabled
        )
        if is_configured:
            triggers_configured.append("L2")
        if l2_config.crossfade_enabled:
            triggers_with_crossfade.append("L2")
        if l2_config.bow_mode:
            triggers_with_bow.append("L2")

    # Check R2 trigger
    r2_config = getattr(mapping, "r2_trigger", None)
    if r2_config:
        is_configured = (
            r2_config.mode != "linear"
            or r2_config.ceiling != 127
            or r2_config.latch_threshold != 0.5
            or r2_config.gate_button is not None
            or r2_config.bow_mode
            or r2_config.crossfade_enabled
            or r2_config.aftertouch.enabled
        )
        if is_configured:
            triggers_configured.append("R2")
        if r2_config.crossfade_enabled:
            triggers_with_crossfade.append("R2")
        if r2_config.bow_mode:
            triggers_with_bow.append("R2")

    report.triggers_configured = triggers_configured
    report.triggers_with_crossfade = triggers_with_crossfade
    report.triggers_with_bow = triggers_with_bow

    # ===== Sticks (left / right)
    sticks_with_chord = []

    left_stick = getattr(mapping, "left_stick", None)
    if left_stick and getattr(left_stick, "chord_enabled", False):
        sticks_with_chord.append("left_stick")

    right_stick = getattr(mapping, "right_stick", None)
    if right_stick and getattr(right_stick, "chord_enabled", False):
        sticks_with_chord.append("right_stick")

    report.sticks_with_chord = sticks_with_chord

    # ===== Feature toggles
    # Shift layer: enabled and shift_button set
    shift_layer = getattr(mapping, "shift_layer", None)
    if shift_layer:
        report.has_shift_layer = (
            getattr(shift_layer, "enabled", False)
            and getattr(shift_layer, "shift_button", -1) >= 0
        )

    # A/B Compare: enabled and b_preset_slug set
    ab_enabled = getattr(mapping, "ab_compare_enabled", False)
    ab_slug = getattr(mapping, "ab_b_preset_slug", None)
    report.has_ab_compare = ab_enabled and bool(ab_slug)

    # Macros: non-empty list
    macros = getattr(mapping, "macros", [])
    report.has_macros = len(macros) > 0

    # Setlist: length of presets if enabled
    setlist = getattr(mapping, "setlist", None)
    if setlist and getattr(setlist, "enabled", False):
        presets = getattr(setlist, "presets", [])
        report.setlist_size = len(presets)
    else:
        report.setlist_size = 0

    # ===== Total channels used
    channels = {mapping.midi_channel}  # global channel

    # Button channel overrides
    button_channels = getattr(mapping, "button_channels", {})
    for ch in button_channels.values():
        channels.add(ch)

    # Axis channel overrides
    axis_channels = getattr(mapping, "axis_channels", {})
    for ch in axis_channels.values():
        channels.add(ch)

    # Hat channel overrides
    hat_channels = getattr(mapping, "hat_channels", {})
    for ch in hat_channels.values():
        channels.add(ch)

    # Trigger crossfade channel overrides
    if l2_config and l2_config.crossfade_channel_b is not None:
        channels.add(l2_config.crossfade_channel_b)
    if r2_config and r2_config.crossfade_channel_b is not None:
        channels.add(r2_config.crossfade_channel_b)

    # Stick chord channel overrides
    if left_stick and getattr(left_stick, "chord_channel", None) is not None:
        channels.add(left_stick.chord_channel)
    if right_stick and getattr(right_stick, "chord_channel", None) is not None:
        channels.add(right_stick.chord_channel)

    report.total_channels_used = len(channels)

    return report


def summary_text(report: MappingAuditReport) -> str:
    """Return a human-readable summary string (5-7 lines) for UI display.

    Shows mapped counts, active features, and coverage percentage.
    """
    lines = []

    # Button/axis coverage
    btn_coverage = (
        f"{report.mapped_buttons}/{report.total_buttons} buttons"
        if report.total_buttons > 0
        else "0 buttons"
    )
    ax_coverage = (
        f"{report.mapped_axes}/{report.total_axes} axes"
        if report.total_axes > 0
        else "0 axes"
    )
    lines.append(f"Controls: {btn_coverage}, {ax_coverage}")

    # Triggers and sticks
    trigger_info = ", ".join(report.triggers_configured) if report.triggers_configured else "—"
    lines.append(f"Triggers configured: {trigger_info}")

    stick_info = ", ".join(report.sticks_with_chord) if report.sticks_with_chord else "—"
    lines.append(f"Sticks with chord: {stick_info}")

    # Feature flags
    features = []
    if report.has_shift_layer:
        features.append("shift layer")
    if report.has_ab_compare:
        features.append("A/B compare")
    if report.has_macros:
        features.append(f"{len([]) if not report.has_macros else 'macros'}")  # simplified
    if report.setlist_size > 0:
        features.append(f"setlist ({report.setlist_size} presets)")

    if features:
        lines.append(f"Features: {', '.join(features)}")
    else:
        lines.append("Features: none enabled")

    # Channels
    lines.append(f"MIDI channels in use: {report.total_channels_used}")

    return "\n".join(lines)
