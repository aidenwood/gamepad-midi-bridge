"""Mapping similarity scoring for preset deduplication and clone detection.

Computes 0..1 similarity scores between two mapping dicts, useful for:
- Marketplace "similar presets" recommendations
- Clone detection ("is this a copy of something in the library?")
- Deduplication on import

Pure stdlib only (no Qt dependencies).
"""

from typing import Dict, List, Optional, Set, Tuple


def jaccard(set_a: Set, set_b: Set) -> float:
    """Compute Jaccard similarity between two sets.

    Jaccard = |A ∩ B| / |A ∪ B|

    Edge cases:
    - Both empty → 1.0 (identical)
    - One or both have elements → standard formula

    Args:
        set_a: First set
        set_b: Second set

    Returns:
        Similarity score 0..1
    """
    if not set_a and not set_b:
        return 1.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    if union == 0:
        return 1.0

    return intersection / union


def note_set(mapping_dict: dict) -> Set[Tuple[int, int, int]]:
    """Extract button → note mappings as (button_index, note, channel) tuples.

    Scans the 'buttons' section and any per-button note bindings.
    Returns empty set if no buttons section or no notes found.

    Args:
        mapping_dict: The mapping dictionary

    Returns:
        Set of (button_index, note, channel) tuples
    """
    result = set()
    buttons = mapping_dict.get("buttons", {})

    for button_idx, button_data in buttons.items():
        if not isinstance(button_data, dict):
            continue

        # Direct note field
        note = button_data.get("note")
        if note is not None:
            channel = button_data.get("channel", 0)
            # Normalize button_idx to int if it's a string key
            try:
                btn_idx = int(button_idx) if isinstance(button_idx, str) else button_idx
            except (ValueError, TypeError):
                continue
            result.add((btn_idx, note, channel))

    return result


def cc_set(mapping_dict: dict) -> Set[Tuple]:
    """Extract axis/trigger → CC mappings as tuples.

    Returns (axis_index_or_trigger_name, cc, channel) tuples.
    Scans 'axes' and 'triggers' sections.
    Returns empty set if no axes/triggers found.

    Args:
        mapping_dict: The mapping dictionary

    Returns:
        Set of (axis_identifier, cc, channel) tuples
    """
    result = set()

    # Axes: {"0": {"cc": 7, "channel": 0}, ...}
    axes = mapping_dict.get("axes", {})
    for axis_idx, axis_data in axes.items():
        if not isinstance(axis_data, dict):
            continue

        cc = axis_data.get("cc")
        if cc is not None:
            channel = axis_data.get("channel", 0)
            # Normalize axis_idx to int if possible
            try:
                ax_idx = int(axis_idx) if isinstance(axis_idx, str) else axis_idx
            except (ValueError, TypeError):
                ax_idx = axis_idx
            result.add((ax_idx, cc, channel))

    # Triggers: {"L2": {"cc": 11, "channel": 0}, ...}
    triggers = mapping_dict.get("triggers", {})
    for trigger_name, trigger_data in triggers.items():
        if not isinstance(trigger_data, dict):
            continue

        cc = trigger_data.get("cc")
        if cc is not None:
            channel = trigger_data.get("channel", 0)
            result.add((trigger_name, cc, channel))

    return result


def feature_flags(mapping_dict: dict) -> Set[str]:
    """Extract enabled feature flags as string labels.

    Scans for enabled subsystems and returns their names.
    Each feature is a string like "shift_layer", "osc", "stick_chord_left", etc.

    Features checked:
    - shift_layer: shift_layer.enabled
    - left_stick_corners: left_stick_corners.enabled
    - right_stick_corners: right_stick_corners.enabled
    - touchpad: touchpad.enabled
    - osc: osc.enabled (includes listen_enabled)
    - ab_compare: ab_compare.enabled
    - stick_chord_left: left_stick.chord_enabled
    - stick_chord_right: right_stick.chord_enabled
    - stick_lfo_left: left_stick.lfo.enabled
    - stick_lfo_right: right_stick.lfo.enabled
    - trigger_crossfade_L2: triggers.L2.crossfade_enabled
    - trigger_crossfade_R2: triggers.R2.crossfade_enabled
    - macros: macros section non-empty
    - haptic_input: haptic_input section non-empty
    - midi_learn: midi_learn.enabled
    - setlist: setlist.enabled
    - program_change: program_change.enabled
    - passthrough: passthrough.enabled
    - battery_alert: battery_alert.enabled

    Args:
        mapping_dict: The mapping dictionary

    Returns:
        Set of enabled feature names
    """
    result = set()

    # Shift layer
    shift = mapping_dict.get("shift_layer", {})
    if isinstance(shift, dict) and shift.get("enabled"):
        result.add("shift_layer")

    # Corner configs
    left_corners = mapping_dict.get("left_stick_corners", {})
    if isinstance(left_corners, dict) and left_corners.get("enabled"):
        result.add("left_stick_corners")

    right_corners = mapping_dict.get("right_stick_corners", {})
    if isinstance(right_corners, dict) and right_corners.get("enabled"):
        result.add("right_stick_corners")

    # Touchpad
    touchpad = mapping_dict.get("touchpad", {})
    if isinstance(touchpad, dict) and touchpad.get("enabled"):
        result.add("touchpad")

    # OSC
    osc = mapping_dict.get("osc", {})
    if isinstance(osc, dict):
        if osc.get("enabled") or osc.get("listen_enabled"):
            result.add("osc")

    # A/B compare
    ab_compare = mapping_dict.get("ab_compare", {})
    if isinstance(ab_compare, dict) and ab_compare.get("enabled"):
        result.add("ab_compare")

    # Stick chord modes
    left_stick = mapping_dict.get("left_stick", {})
    if isinstance(left_stick, dict) and left_stick.get("chord_enabled"):
        result.add("stick_chord_left")

    right_stick = mapping_dict.get("right_stick", {})
    if isinstance(right_stick, dict) and right_stick.get("chord_enabled"):
        result.add("stick_chord_right")

    # Stick LFO
    if isinstance(left_stick, dict):
        lfo = left_stick.get("lfo", {})
        if isinstance(lfo, dict) and lfo.get("enabled"):
            result.add("stick_lfo_left")

    if isinstance(right_stick, dict):
        lfo = right_stick.get("lfo", {})
        if isinstance(lfo, dict) and lfo.get("enabled"):
            result.add("stick_lfo_right")

    # Trigger crossfade
    triggers = mapping_dict.get("triggers", {})
    if isinstance(triggers, dict):
        l2 = triggers.get("L2", {})
        if isinstance(l2, dict) and l2.get("crossfade_enabled"):
            result.add("trigger_crossfade_L2")

        r2 = triggers.get("R2", {})
        if isinstance(r2, dict) and r2.get("crossfade_enabled"):
            result.add("trigger_crossfade_R2")

    # Macros
    macros = mapping_dict.get("macros", {})
    if isinstance(macros, dict) and len(macros) > 0:
        result.add("macros")

    # Haptic input
    haptic_input = mapping_dict.get("haptic_input", [])
    if isinstance(haptic_input, (list, dict)) and len(haptic_input) > 0:
        result.add("haptic_input")

    # MIDI learn
    midi_learn = mapping_dict.get("midi_learn", {})
    if isinstance(midi_learn, dict) and midi_learn.get("enabled"):
        result.add("midi_learn")

    # Setlist
    setlist = mapping_dict.get("setlist", {})
    if isinstance(setlist, dict) and setlist.get("enabled"):
        result.add("setlist")

    # Program change
    program_change = mapping_dict.get("program_change", {})
    if isinstance(program_change, dict) and program_change.get("enabled"):
        result.add("program_change")

    # Passthrough
    passthrough = mapping_dict.get("passthrough", {})
    if isinstance(passthrough, dict) and passthrough.get("enabled"):
        result.add("passthrough")

    # Battery alert
    battery_alert = mapping_dict.get("battery_alert", {})
    if isinstance(battery_alert, dict) and battery_alert.get("enabled"):
        result.add("battery_alert")

    return result


def compute_similarity(
    mapping_a: dict,
    mapping_b: dict,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute weighted similarity score between two mappings.

    Computes Jaccard similarity across three components:
    - Notes (button → note mappings)
    - CCs (axis/trigger → CC mappings)
    - Features (enabled features)

    Then returns weighted average normalized to sum to 1.0.

    Args:
        mapping_a: First mapping dict
        mapping_b: Second mapping dict
        weights: Optional custom weights dict with keys "notes", "ccs", "features".
                 If provided, weights are normalized to sum to 1.0.
                 Defaults: {"notes": 0.4, "ccs": 0.3, "features": 0.3}

    Returns:
        Weighted similarity score 0..1
    """
    if weights is None:
        weights = {"notes": 0.4, "ccs": 0.3, "features": 0.3}

    # Normalize weights to sum to 1.0
    total_weight = sum(weights.values())
    if total_weight > 0:
        normalized_weights = {k: v / total_weight for k, v in weights.items()}
    else:
        normalized_weights = {"notes": 0.4, "ccs": 0.3, "features": 0.3}

    # Compute component scores
    notes_a = note_set(mapping_a)
    notes_b = note_set(mapping_b)
    notes_score = jaccard(notes_a, notes_b)

    ccs_a = cc_set(mapping_a)
    ccs_b = cc_set(mapping_b)
    ccs_score = jaccard(ccs_a, ccs_b)

    features_a = feature_flags(mapping_a)
    features_b = feature_flags(mapping_b)
    features_score = jaccard(features_a, features_b)

    # Weighted average
    overall = (
        normalized_weights.get("notes", 0.4) * notes_score
        + normalized_weights.get("ccs", 0.3) * ccs_score
        + normalized_weights.get("features", 0.3) * features_score
    )

    return overall


def similarity_breakdown(mapping_a: dict, mapping_b: dict) -> Dict[str, float]:
    """Return per-component similarity scores plus overall.

    Args:
        mapping_a: First mapping dict
        mapping_b: Second mapping dict

    Returns:
        Dict with keys "notes", "ccs", "features", "overall"
        Each value is 0..1 Jaccard score
    """
    notes_a = note_set(mapping_a)
    notes_b = note_set(mapping_b)
    notes_score = jaccard(notes_a, notes_b)

    ccs_a = cc_set(mapping_a)
    ccs_b = cc_set(mapping_b)
    ccs_score = jaccard(ccs_a, ccs_b)

    features_a = feature_flags(mapping_a)
    features_b = feature_flags(mapping_b)
    features_score = jaccard(features_a, features_b)

    # Default weighted average for overall
    overall = compute_similarity(mapping_a, mapping_b)

    return {
        "notes": notes_score,
        "ccs": ccs_score,
        "features": features_score,
        "overall": overall,
    }


def most_similar(
    target: dict, candidates: List[Tuple[str, dict]], top_n: int = 5
) -> List[Tuple[str, float]]:
    """Return top N most similar mappings from candidate list.

    Args:
        target: Target mapping dict
        candidates: List of (slug, mapping_dict) tuples
        top_n: How many results to return (default 5)

    Returns:
        List of (slug, similarity_score) tuples sorted by score descending
    """
    scores = []
    for slug, candidate_mapping in candidates:
        score = compute_similarity(target, candidate_mapping)
        scores.append((slug, score))

    # Sort by score descending
    scores.sort(key=lambda x: x[1], reverse=True)

    # Return top N
    return scores[:top_n]


def is_clone(
    mapping_a: dict, mapping_b: dict, threshold: float = 0.85
) -> bool:
    """Check if two mappings are clones (above similarity threshold).

    Args:
        mapping_a: First mapping dict
        mapping_b: Second mapping dict
        threshold: Similarity threshold (default 0.85). 0..1

    Returns:
        True if compute_similarity >= threshold
    """
    score = compute_similarity(mapping_a, mapping_b)
    return score >= threshold
