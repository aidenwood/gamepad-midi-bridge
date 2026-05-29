"""Mapping tour generator: produces ordered list of features for interactive walkthrough.

Scans a mapping dict and detects features (triggers, bow mode, stick chords, etc.)
to produce an ordered tour suitable for an interactive UI walkthrough. Each step
describes a feature and its location in the mapping hierarchy.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TourStep:
    """A single step in a mapping tour walkthrough."""

    feature: str
    """Feature name (e.g. "L2 Trigger", "Left Stick Chord", "Macro Bank")."""

    description: str
    """Human-readable explanation of what this feature does."""

    target_path: str
    """Dotted path to highlight in UI (e.g. "l2_trigger.crossfade_enabled")."""

    priority: int = 0
    """Higher priority = earlier in tour. Decreasing: 90, 85, 80, ..., 10."""

    def to_dict(self) -> dict:
        """Serialize to dict for JSON/storage."""
        return {
            "feature": self.feature,
            "description": self.description,
            "target_path": self.target_path,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TourStep:
        """Deserialize from dict."""
        return cls(
            feature=data.get("feature", ""),
            description=data.get("description", ""),
            target_path=data.get("target_path", ""),
            priority=data.get("priority", 0),
        )


def build_tour(mapping_dict: dict, limit: int = 10) -> list[TourStep]:
    """Scan mapping and produce ordered list of tour steps.

    Detects features in priority order:
      - Trigger crossfade (L2 or R2) — priority 90
      - Bow mode (L2 or R2) — priority 85
      - Stick chord enabled — priority 80
      - Shift layer — priority 75
      - A/B compare — priority 70
      - Macros (with count > 0) — priority 65
      - Note repeat / drumroll buttons — priority 60
      - Polar mode sticks — priority 55
      - Velocity humanize — priority 50
      - LFO bank — priority 45
      - MIDI learn bindings — priority 40
      - Default mappings (basic buttons + axes) — priority 10

    Args:
        mapping_dict: The mapping as a dict (e.g. from JSON deserialization).
        limit: Maximum steps to return (default 10).

    Returns:
        List of TourStep sorted by priority (descending), capped at limit.
    """
    steps = []

    # Priority 90: Trigger crossfade
    if _check_trigger_crossfade(mapping_dict):
        trigger = "L2" if _check_l2_crossfade(mapping_dict) else "R2"
        steps.append(
            TourStep(
                feature=f"{trigger} Trigger Crossfade",
                description=f"{trigger} drives two CCs in opposition (0..127 and 127..0).",
                target_path=f"{'l2_trigger' if trigger == 'L2' else 'r2_trigger'}.crossfade_enabled",
                priority=90,
            )
        )

    # Priority 85: Bow mode
    if _check_bow_mode(mapping_dict):
        trigger = "L2" if _check_l2_bow(mapping_dict) else "R2"
        steps.append(
            TourStep(
                feature=f"{trigger} Bow Mode",
                description=f"{trigger} movement velocity drives expression CC for smooth modulation.",
                target_path=f"{'l2_trigger' if trigger == 'L2' else 'r2_trigger'}.bow_mode",
                priority=85,
            )
        )

    # Priority 80: Stick chord enabled
    if _check_stick_chord(mapping_dict):
        stick = "Left" if _check_left_stick_chord(mapping_dict) else "Right"
        steps.append(
            TourStep(
                feature=f"{stick} Stick Chord",
                description=f"{stick} stick fires chords on diagonal pushes.",
                target_path=f"{'left_stick' if stick == 'Left' else 'right_stick'}.chord_mode",
                priority=80,
            )
        )

    # Priority 75: Shift layer
    if mapping_dict.get("shift_layer", {}).get("shift_button") is not None:
        steps.append(
            TourStep(
                feature="Shift Layer",
                description="Hold shift button to swap to alternate button/axis mappings.",
                target_path="shift_layer.shift_button",
                priority=75,
            )
        )

    # Priority 70: A/B compare
    if mapping_dict.get("ab_compare_enabled"):
        steps.append(
            TourStep(
                feature="A/B Compare",
                description="Hold AB button to hot-swap to a different preset, then snap back.",
                target_path="ab_compare_enabled",
                priority=70,
            )
        )

    # Priority 65: Macros
    macros = mapping_dict.get("macros", {})
    if macros and len(macros) > 0:
        steps.append(
            TourStep(
                feature="Macro Bank",
                description=f"Recorded sequences: {len(macros)} macro(s) available.",
                target_path="macros",
                priority=65,
            )
        )

    # Priority 60: Note repeat / drumroll buttons
    if _check_note_repeat_buttons(mapping_dict):
        steps.append(
            TourStep(
                feature="Note Repeat",
                description="Buttons configured to trigger note repeats or drumroll patterns.",
                target_path="button_configs",
                priority=60,
            )
        )

    # Priority 55: Polar mode sticks
    if _check_polar_sticks(mapping_dict):
        steps.append(
            TourStep(
                feature="Polar Mode Sticks",
                description="Stick axes use polar/circular mapping for radial control.",
                target_path="left_stick" if _check_left_polar(mapping_dict) else "right_stick",
                priority=55,
            )
        )

    # Priority 50: Velocity humanize
    if _check_velocity_humanize(mapping_dict):
        steps.append(
            TourStep(
                feature="Velocity Humanize",
                description="Note velocities humanized with slight randomization.",
                target_path="humanize_enabled",
                priority=50,
            )
        )

    # Priority 45: LFO bank
    if _check_lfo_bank(mapping_dict):
        steps.append(
            TourStep(
                feature="LFO Modulation Bank",
                description="Sticks can modulate CC values with LFO waveforms.",
                target_path="left_stick" if _check_left_lfo(mapping_dict) else "right_stick",
                priority=45,
            )
        )

    # Priority 40: MIDI learn bindings
    if _check_midi_learn(mapping_dict):
        steps.append(
            TourStep(
                feature="MIDI Learn Bindings",
                description="Controls set to learn incoming MIDI messages.",
                target_path="midi_learn",
                priority=40,
            )
        )

    # Priority 10: Default mappings
    buttons = mapping_dict.get("buttons", {})
    axes = mapping_dict.get("axes", {})
    if buttons or axes:
        button_count = len(buttons) if isinstance(buttons, dict) else 0
        axis_count = len(axes) if isinstance(axes, dict) else 0
        steps.append(
            TourStep(
                feature="Button & Axis Mappings",
                description=f"Basic mappings: {button_count} button(s), {axis_count} axis/CC stream(s).",
                target_path="buttons" if button_count > 0 else "axes",
                priority=10,
            )
        )

    # Sort by priority descending, then cap at limit
    steps.sort(key=lambda s: -s.priority)
    return steps[:limit]


def format_step(step: TourStep) -> str:
    """Format a single tour step as a 1-line summary string.

    Returns a human-readable description suitable for a UI tooltip or list item.
    """
    return f"{step.feature}: {step.description}"


def tour_text(steps: list[TourStep]) -> str:
    """Format tour steps as a numbered multi-line string.

    Returns a string like:
        1. L2 Trigger Crossfade: L2 drives two CCs in opposition...
        2. Bow Mode: L2 movement velocity drives expression...

    Args:
        steps: List of TourStep objects.

    Returns:
        Multi-line string with numbered list of steps.
    """
    if not steps:
        return ""

    lines = []
    for i, step in enumerate(steps, start=1):
        lines.append(f"{i}. {format_step(step)}")

    return "\n".join(lines)


def step_count_estimate(mapping_dict: dict) -> int:
    """Estimate total steps that build_tour would generate (without capping).

    Counts the number of features that would be detected by build_tour()
    if no limit were applied. Useful for showing "X steps available" UI.

    Args:
        mapping_dict: The mapping dict.

    Returns:
        Total count of detectable steps.
    """
    count = 0

    if _check_trigger_crossfade(mapping_dict):
        count += 1

    if _check_bow_mode(mapping_dict):
        count += 1

    if _check_stick_chord(mapping_dict):
        count += 1

    if mapping_dict.get("shift_layer", {}).get("shift_button") is not None:
        count += 1

    if mapping_dict.get("ab_compare_enabled"):
        count += 1

    macros = mapping_dict.get("macros", {})
    if macros and len(macros) > 0:
        count += 1

    if _check_note_repeat_buttons(mapping_dict):
        count += 1

    if _check_polar_sticks(mapping_dict):
        count += 1

    if _check_velocity_humanize(mapping_dict):
        count += 1

    if _check_lfo_bank(mapping_dict):
        count += 1

    if _check_midi_learn(mapping_dict):
        count += 1

    buttons = mapping_dict.get("buttons", {})
    axes = mapping_dict.get("axes", {})
    if (buttons and len(buttons) > 0) or (axes and len(axes) > 0):
        count += 1

    return count


# Detector functions — all handle None/missing keys defensively


def _check_trigger_crossfade(mapping_dict: dict) -> bool:
    """Check if L2 or R2 has crossfade enabled."""
    return _check_l2_crossfade(mapping_dict) or _check_r2_crossfade(mapping_dict)


def _check_l2_crossfade(mapping_dict: dict) -> bool:
    """Check if L2 specifically has crossfade enabled."""
    l2 = mapping_dict.get("l2_trigger")
    if not isinstance(l2, dict):
        return False
    return l2.get("crossfade_enabled", False)


def _check_r2_crossfade(mapping_dict: dict) -> bool:
    """Check if R2 specifically has crossfade enabled."""
    r2 = mapping_dict.get("r2_trigger")
    if not isinstance(r2, dict):
        return False
    return r2.get("crossfade_enabled", False)


def _check_bow_mode(mapping_dict: dict) -> bool:
    """Check if L2 or R2 has bow mode enabled."""
    return _check_l2_bow(mapping_dict) or _check_r2_bow(mapping_dict)


def _check_l2_bow(mapping_dict: dict) -> bool:
    """Check if L2 specifically has bow mode enabled."""
    l2 = mapping_dict.get("l2_trigger")
    if not isinstance(l2, dict):
        return False
    return l2.get("bow_mode", False)


def _check_r2_bow(mapping_dict: dict) -> bool:
    """Check if R2 specifically has bow mode enabled."""
    r2 = mapping_dict.get("r2_trigger")
    if not isinstance(r2, dict):
        return False
    return r2.get("bow_mode", False)


def _check_stick_chord(mapping_dict: dict) -> bool:
    """Check if left or right stick has chord mode enabled."""
    return _check_left_stick_chord(mapping_dict) or _check_right_stick_chord(mapping_dict)


def _check_left_stick_chord(mapping_dict: dict) -> bool:
    """Check if left stick specifically has chord mode enabled."""
    left = mapping_dict.get("left_stick")
    if not isinstance(left, dict):
        return False
    return left.get("chord_mode", False)


def _check_right_stick_chord(mapping_dict: dict) -> bool:
    """Check if right stick specifically has chord mode enabled."""
    right = mapping_dict.get("right_stick")
    if not isinstance(right, dict):
        return False
    return right.get("chord_mode", False)


def _check_note_repeat_buttons(mapping_dict: dict) -> bool:
    """Check if any button is configured for note repeat or drumroll."""
    button_configs = mapping_dict.get("button_configs", {})
    if not button_configs or not isinstance(button_configs, dict):
        return False

    for config in button_configs.values():
        if not isinstance(config, dict):
            continue
        # Check for note_repeat or drumroll fields
        if config.get("note_repeat_enabled") or config.get("drumroll_enabled"):
            return True

    return False


def _check_polar_sticks(mapping_dict: dict) -> bool:
    """Check if left or right stick uses polar mode."""
    return _check_left_polar(mapping_dict) or _check_right_polar(mapping_dict)


def _check_left_polar(mapping_dict: dict) -> bool:
    """Check if left stick specifically uses polar mode."""
    left = mapping_dict.get("left_stick")
    if not isinstance(left, dict):
        return False
    return left.get("mode") == "polar"


def _check_right_polar(mapping_dict: dict) -> bool:
    """Check if right stick specifically uses polar mode."""
    right = mapping_dict.get("right_stick")
    if not isinstance(right, dict):
        return False
    return right.get("mode") == "polar"


def _check_velocity_humanize(mapping_dict: dict) -> bool:
    """Check if velocity humanization is enabled."""
    return mapping_dict.get("humanize_enabled", False)


def _check_lfo_bank(mapping_dict: dict) -> bool:
    """Check if left or right stick has LFO modulation configured."""
    return _check_left_lfo(mapping_dict) or _check_right_lfo(mapping_dict)


def _check_left_lfo(mapping_dict: dict) -> bool:
    """Check if left stick specifically has LFO configured."""
    left_stick = mapping_dict.get("left_stick")
    if not isinstance(left_stick, dict):
        return False

    lfo = left_stick.get("lfo", {})
    if not isinstance(lfo, dict):
        return False

    return lfo.get("enabled", False)


def _check_right_lfo(mapping_dict: dict) -> bool:
    """Check if right stick specifically has LFO configured."""
    right_stick = mapping_dict.get("right_stick")
    if not isinstance(right_stick, dict):
        return False

    lfo = right_stick.get("lfo", {})
    if not isinstance(lfo, dict):
        return False

    return lfo.get("enabled", False)


def _check_midi_learn(mapping_dict: dict) -> bool:
    """Check if any MIDI learn bindings are configured."""
    midi_learn = mapping_dict.get("midi_learn", {})
    if not midi_learn or not isinstance(midi_learn, dict):
        return False

    bindings = midi_learn.get("bindings", {})
    return bool(bindings) and len(bindings) > 0
