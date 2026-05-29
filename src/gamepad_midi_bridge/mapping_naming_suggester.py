"""Mapping name suggester — suggest friendly names based on mapping contents.

Pure stdlib functions that analyze a mapping dict and generate descriptive
names (e.g. "Lead Drums", "Expressive Bass Macro") and kebab-case slugs.

No Qt, no unicode emoji — uses ASCII text tokens instead.
"""
from __future__ import annotations

from typing import List


def extract_tags(mapping_dict: dict) -> List[str]:
    """Extract descriptive tags from a mapping's contents.

    Tags describe the mapping's primary characteristics:
    - "drums": channel 10 (GM drums) has many buttons mapped
    - "lead": buttons cover narrow high-mid note range (60..80)
    - "bass": notes cluster in low range (28..50)
    - "chords": any stick has chord_enabled=True
    - "ambient": trigger crossfade enabled OR bow mode enabled
    - "expressive": midi_learn has bindings OR aftertouch enabled
    - "polyrhythmic": polyrhythm or euclidean fields present
    - "rotated_layer": shift_layer or ab_compare enabled
    - "macro_heavy": 3+ macros configured

    Returns tags in priority order: bass, lead, drums, chords, ambient,
    expressive, polyrhythmic, rotated_layer, macro_heavy.
    """
    tags = []

    # Extract buttons and build note statistics
    buttons_dict = mapping_dict.get("buttons", {})
    button_channels = mapping_dict.get("button_channels", {})
    midi_channel = mapping_dict.get("midi_channel", 0)

    drum_notes = []
    all_notes = []

    for btn_idx, note in buttons_dict.items():
        ch = button_channels.get(btn_idx, midi_channel)
        all_notes.append(note)
        if ch == 9:  # MIDI channel 10 (0-indexed as 9)
            drum_notes.append(note)

    # "drums" — channel 10 with many buttons (3+)
    if len(drum_notes) >= 3:
        tags.append("drums")

    # "lead" — narrow high-mid note range (60..80)
    high_mid_notes = [n for n in all_notes if 60 <= n <= 80]
    if high_mid_notes and len(high_mid_notes) >= 2 and max(all_notes or [0]) <= 80:
        tags.append("lead")

    # "bass" — notes cluster in low range (28..50)
    bass_notes = [n for n in all_notes if 28 <= n <= 50]
    if bass_notes and len(bass_notes) >= 2:
        tags.append("bass")

    # "chords" — any stick has chord_enabled
    left_stick = mapping_dict.get("left_stick", {})
    right_stick = mapping_dict.get("right_stick", {})
    if isinstance(left_stick, dict) and left_stick.get("chord_enabled"):
        tags.append("chords")
    elif isinstance(right_stick, dict) and right_stick.get("chord_enabled"):
        tags.append("chords")

    # "ambient" — trigger crossfade enabled OR bow mode enabled
    l2_trigger = mapping_dict.get("l2_trigger", {})
    r2_trigger = mapping_dict.get("r2_trigger", {})
    if isinstance(l2_trigger, dict):
        if l2_trigger.get("crossfade_enabled") or l2_trigger.get("bow_mode"):
            tags.append("ambient")
    if isinstance(r2_trigger, dict):
        if r2_trigger.get("crossfade_enabled") or r2_trigger.get("bow_mode"):
            tags.append("ambient")

    # "expressive" — midi_learn has bindings OR aftertouch enabled
    midi_learn = mapping_dict.get("midi_learn", {})
    if isinstance(midi_learn, dict) and midi_learn.get("bindings"):
        tags.append("expressive")
    if isinstance(l2_trigger, dict) and l2_trigger.get("aftertouch", {}).get("enabled"):
        tags.append("expressive")
    if isinstance(r2_trigger, dict) and r2_trigger.get("aftertouch", {}).get("enabled"):
        tags.append("expressive")
    if isinstance(midi_learn, dict) and midi_learn.get("enabled"):
        tags.append("expressive")

    # "polyrhythmic" — polyrhythm or euclidean fields present
    # (These would be in stick configs or similar advanced fields)
    # For now, check if any macros with arp_mode suggest polyrhythmics
    macros = mapping_dict.get("macros", [])
    if isinstance(macros, list):
        for macro in macros:
            if isinstance(macro, dict) and macro.get("arp_mode"):
                tags.append("polyrhythmic")
                break

    # "rotated_layer" — shift_layer or ab_compare enabled
    shift_layer = mapping_dict.get("shift_layer", {})
    if isinstance(shift_layer, dict) and shift_layer.get("enabled"):
        tags.append("rotated_layer")
    if mapping_dict.get("ab_compare_enabled"):
        tags.append("rotated_layer")

    # "macro_heavy" — 3+ macros configured
    if isinstance(macros, list) and len(macros) >= 3:
        tags.append("macro_heavy")

    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)

    return unique_tags


def suggest_name(mapping_dict: dict, max_words: int = 4) -> str:
    """Combine highest-priority tags into a friendly name.

    Priority order: bass, lead, drums, chords, ambient, expressive,
    polyrhythmic, rotated_layer, macro_heavy.

    Args:
        mapping_dict: the mapping as a dict
        max_words: max number of tags to include in the name (default 4)

    Returns:
        Title-cased name like "Lead Drums" or "Expressive Bass Macro".
        If no tags, returns "Untitled".
    """
    priority_order = [
        "bass", "lead", "drums", "chords", "ambient",
        "expressive", "polyrhythmic", "rotated_layer", "macro_heavy",
    ]

    tags = extract_tags(mapping_dict)

    # Sort tags by priority, then take top N
    sorted_tags = sorted(
        tags,
        key=lambda t: priority_order.index(t) if t in priority_order else 999
    )
    selected = sorted_tags[:max_words]

    if not selected:
        return "Untitled"

    # Title case each tag and join
    return " ".join(tag.replace("_", " ").title() for tag in selected)


def suggest_slug(name: str) -> str:
    """Convert a name to kebab-case slug.

    Strips non-alphanumeric characters, replaces spaces with "-", converts
    to lowercase.

    Args:
        name: the name to slugify

    Returns:
        kebab-case slug like "lead-drums"
    """
    import re
    # Remove non-alphanumeric except spaces and hyphens
    cleaned = re.sub(r"[^a-zA-Z0-9\s\-]", "", name)
    # Replace spaces with hyphens
    slug = cleaned.replace(" ", "-")
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Lowercase and strip leading/trailing hyphens
    return slug.lower().strip("-")


def tag_to_symbol(tag: str) -> str:
    """Map a tag to a single ASCII text token.

    Returns a short ASCII symbol representing the tag for quick visual
    identification without unicode emoji.

    Args:
        tag: one of the valid tags

    Returns:
        Single ASCII letter or short text token
    """
    tag_symbols = {
        "bass": "B",
        "lead": "L",
        "drums": "D",
        "chords": "C",
        "ambient": "A",
        "expressive": "E",
        "polyrhythmic": "P",
        "rotated_layer": "R",
        "macro_heavy": "M",
    }
    return tag_symbols.get(tag, "?")


def format_name_with_details(name: str, mapping_dict: dict) -> str:
    """Return name with bracketed details like button count.

    Args:
        name: the suggested or user-provided name
        mapping_dict: the mapping dict

    Returns:
        String like "Lead Drums [10 buttons]"
    """
    buttons = mapping_dict.get("buttons", {})
    btn_count = len(buttons) if isinstance(buttons, dict) else 0
    return f"{name} [{btn_count} buttons]"
