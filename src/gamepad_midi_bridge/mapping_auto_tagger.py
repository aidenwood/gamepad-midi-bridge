"""Mapping Auto-Tagger — extended tag extraction with confidence scores.

Pure stdlib functions that analyze a mapping dict and generate rich tags
with confidence scores. Extends mapping_naming_suggester.extract_tags with
a richer tag set (18+ tags) and per-tag confidence metrics (0..1).

No Qt, stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict


@dataclass
class TaggedConfidence:
    """A tag with its confidence score.

    Attributes:
        tag: The tag name (str)
        confidence: Confidence 0..1 (float)
    """

    tag: str
    confidence: float

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> TaggedConfidence:
        """Deserialize from dict."""
        return TaggedConfidence(**data)


# Extended tag set: superset including all 9 base tags + 9 new ones
EXTENDED_TAGS: List[str] = [
    # Base 9 from mapping_naming_suggester
    "drums",
    "lead",
    "bass",
    "chords",
    "ambient",
    "expressive",
    "polyrhythmic",
    "rotated_layer",
    "macro_heavy",
    # New 9
    "live_performance",
    "studio",
    "experimental",
    "minimal",
    "extensive",
    "monophonic",
    "polyphonic",
    "tempo_sync",
]


def _get_buttons_dict(mapping_dict: dict) -> dict:
    """Extract buttons dict defensively."""
    buttons = mapping_dict.get("buttons", {})
    return buttons if isinstance(buttons, dict) else {}


def _get_button_channels(mapping_dict: dict) -> dict:
    """Extract button_channels dict defensively."""
    button_channels = mapping_dict.get("button_channels", {})
    return button_channels if isinstance(button_channels, dict) else {}


def _get_midi_channel(mapping_dict: dict) -> int:
    """Extract midi_channel int defensively."""
    ch = mapping_dict.get("midi_channel", 0)
    return int(ch) if isinstance(ch, int) else 0


def _count_buttons(mapping_dict: dict) -> int:
    """Count total buttons mapped."""
    buttons = _get_buttons_dict(mapping_dict)
    return len(buttons)


def _count_channels_used(mapping_dict: dict) -> int:
    """Count unique MIDI channels in button mappings."""
    buttons = _get_buttons_dict(mapping_dict)
    button_channels = _get_button_channels(mapping_dict)
    midi_channel = _get_midi_channel(mapping_dict)

    channels = set()
    for btn_idx in buttons.keys():
        ch = button_channels.get(btn_idx, midi_channel)
        channels.add(ch)
    return len(channels)


def _has_drums(mapping_dict: dict) -> bool:
    """Check if mapping has 3+ buttons on channel 10 (MIDI drum kit)."""
    buttons = _get_buttons_dict(mapping_dict)
    button_channels = _get_button_channels(mapping_dict)
    midi_channel = _get_midi_channel(mapping_dict)

    drum_count = 0
    for btn_idx in buttons.keys():
        ch = button_channels.get(btn_idx, midi_channel)
        if ch == 9:  # Channel 10 (0-indexed as 9)
            drum_count += 1
    return drum_count >= 3


def _has_setlist(mapping_dict: dict) -> bool:
    """Check if mapping has setlist field (live performance indicator)."""
    setlist = mapping_dict.get("setlist")
    return isinstance(setlist, list) and len(setlist) > 0


def _has_midi_clock(mapping_dict: dict) -> bool:
    """Check if mapping has midi_clock or quantize features (studio indicator)."""
    return bool(mapping_dict.get("midi_clock")) or bool(
        mapping_dict.get("quantize")
    )


def _has_experimental_features(mapping_dict: dict) -> bool:
    """Check for experimental features: bow + crossfade + LFO bank."""
    l2_trigger = mapping_dict.get("l2_trigger", {})
    r2_trigger = mapping_dict.get("r2_trigger", {})

    if not isinstance(l2_trigger, dict):
        l2_trigger = {}
    if not isinstance(r2_trigger, dict):
        r2_trigger = {}

    has_bow = l2_trigger.get("bow_mode") or r2_trigger.get("bow_mode")
    has_crossfade = (
        l2_trigger.get("crossfade_enabled") or r2_trigger.get("crossfade_enabled")
    )

    # LFO bank check (advanced feature in trigger or macro)
    has_lfo = False
    for trigger in [l2_trigger, r2_trigger]:
        if isinstance(trigger, dict) and trigger.get("lfo_bank"):
            has_lfo = True
            break
    macros = mapping_dict.get("macros", [])
    if isinstance(macros, list):
        for macro in macros:
            if isinstance(macro, dict) and macro.get("lfo_bank"):
                has_lfo = True
                break

    return all([has_bow, has_crossfade, has_lfo])


def _has_tempo_sync(mapping_dict: dict) -> bool:
    """Check for tempo sync: LFO BPM sync enabled or bpm field present."""
    # Check for bpm field at top level or in triggers/macros
    if mapping_dict.get("bpm"):
        return True

    l2_trigger = mapping_dict.get("l2_trigger", {})
    r2_trigger = mapping_dict.get("r2_trigger", {})
    if not isinstance(l2_trigger, dict):
        l2_trigger = {}
    if not isinstance(r2_trigger, dict):
        r2_trigger = {}

    # Check for LFO BPM sync in triggers
    for trigger in [l2_trigger, r2_trigger]:
        lfo = trigger.get("lfo", {})
        if isinstance(lfo, dict) and lfo.get("bpm_sync"):
            return True

    # Check in macros
    macros = mapping_dict.get("macros", [])
    if isinstance(macros, list):
        for macro in macros:
            if isinstance(macro, dict):
                lfo = macro.get("lfo", {})
                if isinstance(lfo, dict) and lfo.get("bpm_sync"):
                    return True

    return False


def auto_tag(mapping_dict: dict) -> List[TaggedConfidence]:
    """Generate tags with confidence scores for a mapping.

    Analyzes mapping contents and returns a list of (tag, confidence) tuples
    sorted by confidence descending. Up to 8 entries max.

    Args:
        mapping_dict: The mapping as a dict

    Returns:
        List of TaggedConfidence, sorted by confidence desc (max 8)
    """
    if not isinstance(mapping_dict, dict):
        return []

    scored_tags: Dict[str, float] = {}

    # Base 9 tags (from mapping_naming_suggester logic)

    # "drums" — channel 10 with 3+ buttons
    if _has_drums(mapping_dict):
        scored_tags["drums"] = 0.95

    # "bass" — notes cluster in low range (28..50), 2+
    buttons = _get_buttons_dict(mapping_dict)
    bass_notes = [n for n in buttons.values() if isinstance(n, int) and 28 <= n <= 50]
    if len(bass_notes) >= 2:
        scored_tags["bass"] = 0.90

    # "lead" — narrow high-mid note range (60..80), 2+, all notes <= 80
    high_mid_notes = [
        n for n in buttons.values() if isinstance(n, int) and 60 <= n <= 80
    ]
    all_notes = [n for n in buttons.values() if isinstance(n, int)]
    if (
        high_mid_notes
        and len(high_mid_notes) >= 2
        and (not all_notes or max(all_notes) <= 80)
    ):
        scored_tags["lead"] = 0.85

    # "chords" — stick has chord_enabled
    left_stick = mapping_dict.get("left_stick", {})
    right_stick = mapping_dict.get("right_stick", {})
    if (
        isinstance(left_stick, dict) and left_stick.get("chord_enabled")
    ) or (isinstance(right_stick, dict) and right_stick.get("chord_enabled")):
        scored_tags["chords"] = 0.80

    # "ambient" — trigger crossfade OR bow mode
    l2_trigger = mapping_dict.get("l2_trigger", {})
    r2_trigger = mapping_dict.get("r2_trigger", {})
    if not isinstance(l2_trigger, dict):
        l2_trigger = {}
    if not isinstance(r2_trigger, dict):
        r2_trigger = {}

    if (
        l2_trigger.get("crossfade_enabled")
        or r2_trigger.get("crossfade_enabled")
        or l2_trigger.get("bow_mode")
        or r2_trigger.get("bow_mode")
    ):
        scored_tags["ambient"] = 0.85

    # "expressive" — midi_learn bindings, aftertouch, or midi_learn enabled
    midi_learn = mapping_dict.get("midi_learn", {})
    if not isinstance(midi_learn, dict):
        midi_learn = {}

    has_bindings = bool(midi_learn.get("bindings"))
    has_aftertouch = (
        l2_trigger.get("aftertouch", {}).get("enabled")
        or r2_trigger.get("aftertouch", {}).get("enabled")
    )
    has_midi_learn = bool(midi_learn.get("enabled"))

    if has_bindings or has_aftertouch or has_midi_learn:
        scored_tags["expressive"] = 0.80

    # "polyrhythmic" — macro with arp_mode
    macros = mapping_dict.get("macros", [])
    if isinstance(macros, list):
        for macro in macros:
            if isinstance(macro, dict) and macro.get("arp_mode"):
                scored_tags["polyrhythmic"] = 0.75
                break

    # "rotated_layer" — shift_layer enabled or ab_compare enabled
    shift_layer = mapping_dict.get("shift_layer", {})
    if isinstance(shift_layer, dict) and shift_layer.get("enabled"):
        scored_tags["rotated_layer"] = 0.80
    elif mapping_dict.get("ab_compare_enabled"):
        scored_tags["rotated_layer"] = 0.80

    # "macro_heavy" — 3+ macros
    if isinstance(macros, list) and len(macros) >= 3:
        scored_tags["macro_heavy"] = 0.85

    # New 9 tags

    # "live_performance" — has setlist or A/B compare
    if _has_setlist(mapping_dict):
        scored_tags["live_performance"] = 0.90
    elif mapping_dict.get("ab_compare_enabled"):
        scored_tags["live_performance"] = 0.60

    # "studio" — has midi_clock or quantize
    if _has_midi_clock(mapping_dict):
        scored_tags["studio"] = 0.85

    # "experimental" — has bow + crossfade + LFO bank
    if _has_experimental_features(mapping_dict):
        scored_tags["experimental"] = 0.90

    # "minimal" — < 4 buttons mapped
    btn_count = _count_buttons(mapping_dict)
    if 0 < btn_count < 4:
        scored_tags["minimal"] = 0.85
        # Mutually exclusive: remove extensive if present
        scored_tags.pop("extensive", None)

    # "extensive" — >= 16 buttons mapped
    if btn_count >= 16:
        scored_tags["extensive"] = 0.90
        # Mutually exclusive: remove minimal if present
        scored_tags.pop("minimal", None)

    # "monophonic" — no polyphony in macros; single-channel only
    channel_count = _count_channels_used(mapping_dict)
    has_poly = False
    if isinstance(macros, list):
        for macro in macros:
            if isinstance(macro, dict) and macro.get("polyphony"):
                has_poly = True
                break

    if channel_count == 1 and not has_poly and btn_count > 0:
        scored_tags["monophonic"] = 0.80
        # Mutually exclusive: remove polyphonic if present
        scored_tags.pop("polyphonic", None)

    # "polyphonic" — multiple channels used
    if channel_count > 1:
        scored_tags["polyphonic"] = 0.85
        # Mutually exclusive: remove monophonic if present
        scored_tags.pop("monophonic", None)

    # "tempo_sync" — LFO BPM sync enabled or bpm field present
    if _has_tempo_sync(mapping_dict):
        scored_tags["tempo_sync"] = 0.85

    # Convert to TaggedConfidence, sort by confidence desc, limit to 8
    result = [
        TaggedConfidence(tag=tag, confidence=conf)
        for tag, conf in scored_tags.items()
    ]
    result.sort(key=lambda tc: tc.confidence, reverse=True)
    return result[:8]


def tag_set(mapping_dict: dict, min_confidence: float = 0.5) -> List[str]:
    """Return plain tag names above min_confidence threshold.

    Args:
        mapping_dict: The mapping as a dict
        min_confidence: Minimum confidence to include (0..1, default 0.5)

    Returns:
        Sorted list of tag names
    """
    tags_conf = auto_tag(mapping_dict)
    filtered = [tc.tag for tc in tags_conf if tc.confidence >= min_confidence]
    return sorted(filtered)


def confidence_for(tag: str, mapping_dict: dict) -> float:
    """Return confidence score for a specific tag (0..1).

    Returns 0 if tag not found or has no confidence.

    Args:
        tag: The tag name to lookup
        mapping_dict: The mapping as a dict

    Returns:
        Confidence 0..1
    """
    tags_conf = auto_tag(mapping_dict)
    for tc in tags_conf:
        if tc.tag == tag:
            return tc.confidence
    return 0.0


def available_tags() -> List[str]:
    """Return all available extended tags, sorted alphabetically.

    Returns:
        Sorted list of tag names
    """
    return sorted(EXTENDED_TAGS)
