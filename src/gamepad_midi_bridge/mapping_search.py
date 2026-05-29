"""Mapping content search helper — find where a specific note / CC / channel is used.

Pure stdlib only. Provides utilities to search through a mapping dict for:
  - Specific MIDI notes (buttons, macros, chord progressions)
  - Specific MIDI CCs (axes, triggers, modulation, crossfade)
  - Specific MIDI channels (global + per-control overrides)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterator, List, Optional, Tuple


@dataclass
class SearchHit:
    """Single match for a search query within a mapping dict.

    Attributes:
      - path: dotted path to the matched value (e.g. "buttons.5.note")
      - value: the actual value at that path
      - context: human-readable description (e.g. "button index 5", "axis 2 / L-stick X")
    """
    path: str
    value: Any
    context: str

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SearchHit:
        """Deserialize from dict."""
        return cls(**data)


def walk_paths(
    mapping_dict: dict,
    key_filter: Optional[str] = None,
) -> Iterator[Tuple[str, Any]]:
    """Walk a dict recursively, yielding (dotted_path, value) tuples.

    If key_filter is provided, only yields leaves whose final key component
    matches key_filter. Traverses all nested dicts and lists safely.

    Args:
      mapping_dict: the dict to walk (typically a Mapping.to_dict() result)
      key_filter: optional filter; only yield leaves where the key matches

    Yields:
      (dotted_path, value) tuples for each leaf (non-dict, non-list) node
    """
    if not isinstance(mapping_dict, dict):
        return

    def _walk(obj: Any, path: str) -> Iterator[Tuple[str, Any]]:
        if isinstance(obj, dict):
            for key, val in obj.items():
                new_path = f"{path}.{key}" if path else str(key)
                yield from _walk(val, new_path)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                new_path = f"{path}[{idx}]"
                yield from _walk(item, new_path)
        else:
            # Leaf node — check filter
            if key_filter is None:
                yield (path, obj)
            else:
                # Extract the final key component (after the last . or [)
                final_key = path.split(".")[-1].split("[")[0]
                if final_key == key_filter:
                    yield (path, obj)

    yield from _walk(mapping_dict, "")


def find_note(mapping_dict: dict, note: int) -> List[SearchHit]:
    """Find all occurrences of a MIDI note in the mapping.

    Searches:
      - buttons.* (button index -> note mappings)
      - hats.* (hat direction -> note mappings)
      - left_stick_corners.notes[*]
      - right_stick_corners.notes[*]
      - left_stick.chord_north, chord_east, chord_south, chord_west lists
      - right_stick.chord_north, chord_east, chord_south, chord_west lists
      - left_stick.flick.note_pos_x, note_neg_x, note_pos_y, note_neg_y
      - right_stick.flick.note_pos_x, note_neg_x, note_pos_y, note_neg_y
      - swipe_up_note, swipe_down_note, swipe_left_note, swipe_right_note
      - pinch_in_note, pinch_out_note
      - battery_alert.note
      - midi_learn.bindings[*].note (if midi_learn exists)

    Args:
      mapping_dict: the mapping dict (or Mapping.to_dict() result)
      note: the MIDI note number to search for (0..127)

    Returns:
      list of SearchHit objects with path, value, and context
    """
    if not isinstance(mapping_dict, dict):
        return []

    hits: List[SearchHit] = []

    # Search buttons dict (direct mapping: button index -> note)
    buttons = mapping_dict.get("buttons", {})
    if isinstance(buttons, dict):
        for button_idx, button_note in buttons.items():
            if isinstance(button_note, int) and button_note == note:
                path = f"buttons.{button_idx}"
                context = f"button index {button_idx}"
                hits.append(SearchHit(path=path, value=button_note, context=context))

    # Search hats dict (direct mapping: hat direction -> note)
    hats = mapping_dict.get("hats", {})
    if isinstance(hats, dict):
        for hat_dir, hat_note in hats.items():
            if isinstance(hat_note, int) and hat_note == note:
                path = f"hats.{hat_dir}"
                context = f"hat {hat_dir}"
                hits.append(SearchHit(path=path, value=hat_note, context=context))

    # Search corner configs
    for corner_name in ["left_stick_corners", "right_stick_corners"]:
        corner = mapping_dict.get(corner_name, {})
        if isinstance(corner, dict):
            notes_list = corner.get("notes", [])
            if isinstance(notes_list, list):
                for idx, corner_note in enumerate(notes_list):
                    if isinstance(corner_note, int) and corner_note == note:
                        path = f"{corner_name}.notes[{idx}]"
                        context = f"{corner_name.replace('_', ' ')} / notes[{idx}]"
                        hits.append(SearchHit(path=path, value=corner_note, context=context))

    # Search chord lists in sticks
    for stick_name in ["left_stick", "right_stick"]:
        stick = mapping_dict.get(stick_name, {})
        if isinstance(stick, dict):
            for chord_key in ["chord_north", "chord_east", "chord_south", "chord_west"]:
                chord_list = stick.get(chord_key, [])
                if isinstance(chord_list, list):
                    for idx, chord_note in enumerate(chord_list):
                        if isinstance(chord_note, int) and chord_note == note:
                            path = f"{stick_name}.{chord_key}[{idx}]"
                            context = f"{stick_name.replace('_', ' ')} / {chord_key}"
                            hits.append(SearchHit(path=path, value=chord_note, context=context))

    # Search stick flick configs
    for stick_name in ["left_stick", "right_stick"]:
        stick = mapping_dict.get(stick_name, {})
        if isinstance(stick, dict):
            flick = stick.get("flick", {})
            if isinstance(flick, dict):
                for flick_key in ["note_pos_x", "note_neg_x", "note_pos_y", "note_neg_y"]:
                    flick_note = flick.get(flick_key)
                    if isinstance(flick_note, int) and flick_note == note:
                        path = f"{stick_name}.flick.{flick_key}"
                        context = f"{stick_name.replace('_', ' ')} / flick / {flick_key}"
                        hits.append(SearchHit(path=path, value=flick_note, context=context))

    # Search gesture notes
    gesture_keys = [
        "swipe_up_note", "swipe_down_note", "swipe_left_note", "swipe_right_note",
        "pinch_in_note", "pinch_out_note"
    ]
    for gkey in gesture_keys:
        if gkey in mapping_dict and mapping_dict[gkey] == note:
            hits.append(SearchHit(
                path=gkey,
                value=note,
                context=f"gesture: {gkey}"
            ))

    # Search battery alert note
    battery_alert = mapping_dict.get("battery_alert", {})
    if isinstance(battery_alert, dict):
        bat_note = battery_alert.get("note")
        if isinstance(bat_note, int) and bat_note == note:
            hits.append(SearchHit(
                path="battery_alert.note",
                value=bat_note,
                context="battery alert"
            ))

    # Search MIDI learn bindings
    midi_learn = mapping_dict.get("midi_learn", {})
    if isinstance(midi_learn, dict):
        bindings = midi_learn.get("bindings", [])
        if isinstance(bindings, list):
            for idx, binding in enumerate(bindings):
                if isinstance(binding, dict):
                    binding_note = binding.get("note")
                    if isinstance(binding_note, int) and binding_note == note:
                        hits.append(SearchHit(
                            path=f"midi_learn.bindings[{idx}].note",
                            value=binding_note,
                            context=f"MIDI learn binding {idx}"
                        ))

    return hits


def find_cc(mapping_dict: dict, cc: int) -> List[SearchHit]:
    """Find all occurrences of a MIDI CC number in the mapping.

    Searches:
      - axes.* (axis index -> CC mappings)
      - triggers.L2.cc / triggers.R2.cc
      - triggers.L2.crossfade_cc_b / triggers.R2.crossfade_cc_b
      - triggers.*.bow_cc
      - left_stick.polar_angle_cc / polar_mag_cc
      - left_stick.random_mod_cc
      - right_stick.polar_angle_cc / polar_mag_cc
      - right_stick.random_mod_cc
      - touchpad.x_cc / y_cc
      - midi_learn.bindings[*].cc

    Args:
      mapping_dict: the mapping dict
      cc: the MIDI CC number to search for (0..119)

    Returns:
      list of SearchHit objects
    """
    if not isinstance(mapping_dict, dict):
        return []

    hits: List[SearchHit] = []

    # Search axes dict (direct mapping: axis index -> CC)
    axes = mapping_dict.get("axes", {})
    if isinstance(axes, dict):
        for axis_idx, axis_cc in axes.items():
            if isinstance(axis_cc, int) and axis_cc == cc:
                path = f"axes.{axis_idx}"
                axis_names = {
                    "0": "L-stick X",
                    "1": "L-stick Y",
                    "2": "R-stick X",
                    "3": "R-stick Y",
                    "4": "L-trigger (L2)",
                    "5": "R-trigger (R2)",
                }
                axis_name = axis_names.get(str(axis_idx), f"axis {axis_idx}")
                context = f"axis {axis_idx} / {axis_name}"
                hits.append(SearchHit(path=path, value=axis_cc, context=context))

    # Search triggers
    triggers = mapping_dict.get("triggers", {})
    if isinstance(triggers, dict):
        for trigger_name, trigger_config in triggers.items():
            if isinstance(trigger_config, dict):
                # Direct CC
                trigger_cc = trigger_config.get("cc")
                if isinstance(trigger_cc, int) and trigger_cc == cc:
                    path = f"triggers.{trigger_name}.cc"
                    context = f"trigger {trigger_name} / CC"
                    hits.append(SearchHit(path=path, value=trigger_cc, context=context))

                # Crossfade CC
                crossfade_cc = trigger_config.get("crossfade_cc_b")
                if isinstance(crossfade_cc, int) and crossfade_cc == cc:
                    path = f"triggers.{trigger_name}.crossfade_cc_b"
                    context = f"trigger {trigger_name} / crossfade CC"
                    hits.append(SearchHit(path=path, value=crossfade_cc, context=context))

                # Bow CC
                bow_cc = trigger_config.get("bow_cc")
                if isinstance(bow_cc, int) and bow_cc == cc:
                    path = f"triggers.{trigger_name}.bow_cc"
                    context = f"trigger {trigger_name} / bow CC"
                    hits.append(SearchHit(path=path, value=bow_cc, context=context))

    # Search sticks
    for stick_name in ["left_stick", "right_stick"]:
        stick = mapping_dict.get(stick_name, {})
        if isinstance(stick, dict):
            # Polar CCs
            for polar_key in ["polar_angle_cc", "polar_mag_cc"]:
                polar_cc = stick.get(polar_key)
                if isinstance(polar_cc, int) and polar_cc == cc:
                    path = f"{stick_name}.{polar_key}"
                    context = f"{stick_name.replace('_', ' ')} / {polar_key}"
                    hits.append(SearchHit(path=path, value=polar_cc, context=context))

            # Random mod CC
            random_cc = stick.get("random_mod_cc")
            if isinstance(random_cc, int) and random_cc == cc:
                path = f"{stick_name}.random_mod_cc"
                context = f"{stick_name.replace('_', ' ')} / random modulation CC"
                hits.append(SearchHit(path=path, value=random_cc, context=context))

    # Search touchpad
    touchpad = mapping_dict.get("touchpad", {})
    if isinstance(touchpad, dict):
        for tp_key in ["x_cc", "y_cc"]:
            tp_cc = touchpad.get(tp_key)
            if isinstance(tp_cc, int) and tp_cc == cc:
                path = f"touchpad.{tp_key}"
                context = f"touchpad / {tp_key}"
                hits.append(SearchHit(path=path, value=tp_cc, context=context))

    # Search MIDI learn bindings
    midi_learn = mapping_dict.get("midi_learn", {})
    if isinstance(midi_learn, dict):
        bindings = midi_learn.get("bindings", [])
        if isinstance(bindings, list):
            for idx, binding in enumerate(bindings):
                if isinstance(binding, dict):
                    binding_cc = binding.get("cc")
                    if isinstance(binding_cc, int) and binding_cc == cc:
                        hits.append(SearchHit(
                            path=f"midi_learn.bindings[{idx}].cc",
                            value=binding_cc,
                            context=f"MIDI learn binding {idx}"
                        ))

    return hits


def find_channel(mapping_dict: dict, channel: int) -> List[SearchHit]:
    """Find all occurrences of a MIDI channel in the mapping.

    Searches:
      - midi_channel (global channel, typically 0..15)
      - button_channels.* (per-button overrides)
      - axis_channels.* (per-axis overrides)
      - hat_channels.* (per-hat overrides)
      - left_stick.chord_channel
      - right_stick.chord_channel
      - triggers.L2.channel_override / triggers.R2.channel_override
      - triggers.L2.aftertouch.channel_override / triggers.R2.aftertouch.channel_override
      - battery_alert.channel_override
      - touchpad.channel_override (if it exists)

    Args:
      mapping_dict: the mapping dict
      channel: the MIDI channel number to search for (0..15)

    Returns:
      list of SearchHit objects
    """
    if not isinstance(mapping_dict, dict):
        return []

    hits: List[SearchHit] = []

    # Global channel
    if "midi_channel" in mapping_dict and mapping_dict["midi_channel"] == channel:
        hits.append(SearchHit(
            path="midi_channel",
            value=channel,
            context="global MIDI channel"
        ))

    # Search button_channels dict
    button_channels = mapping_dict.get("button_channels", {})
    if isinstance(button_channels, dict):
        for button_idx, button_ch in button_channels.items():
            if isinstance(button_ch, int) and button_ch == channel and button_ch != -1:
                path = f"button_channels.{button_idx}"
                context = f"button {button_idx} channel override"
                hits.append(SearchHit(path=path, value=button_ch, context=context))

    # Search axis_channels dict
    axis_channels = mapping_dict.get("axis_channels", {})
    if isinstance(axis_channels, dict):
        for axis_idx, axis_ch in axis_channels.items():
            if isinstance(axis_ch, int) and axis_ch == channel and axis_ch != -1:
                path = f"axis_channels.{axis_idx}"
                context = f"axis {axis_idx} channel override"
                hits.append(SearchHit(path=path, value=axis_ch, context=context))

    # Search hat_channels dict
    hat_channels = mapping_dict.get("hat_channels", {})
    if isinstance(hat_channels, dict):
        for hat_dir, hat_ch in hat_channels.items():
            if isinstance(hat_ch, int) and hat_ch == channel and hat_ch != -1:
                path = f"hat_channels.{hat_dir}"
                context = f"hat {hat_dir} channel override"
                hits.append(SearchHit(path=path, value=hat_ch, context=context))

    # Search sticks for chord_channel
    for stick_name in ["left_stick", "right_stick"]:
        stick = mapping_dict.get(stick_name, {})
        if isinstance(stick, dict):
            chord_ch = stick.get("chord_channel")
            if isinstance(chord_ch, int) and chord_ch == channel and chord_ch != -1:
                path = f"{stick_name}.chord_channel"
                context = f"{stick_name.replace('_', ' ')} chord channel override"
                hits.append(SearchHit(path=path, value=chord_ch, context=context))

    # Search triggers
    triggers = mapping_dict.get("triggers", {})
    if isinstance(triggers, dict):
        for trigger_name, trigger_config in triggers.items():
            if isinstance(trigger_config, dict):
                # Direct channel_override
                trig_ch = trigger_config.get("channel_override")
                if isinstance(trig_ch, int) and trig_ch == channel and trig_ch != -1:
                    path = f"triggers.{trigger_name}.channel_override"
                    context = f"trigger {trigger_name} channel override"
                    hits.append(SearchHit(path=path, value=trig_ch, context=context))

                # Aftertouch channel_override
                aftertouch = trigger_config.get("aftertouch", {})
                if isinstance(aftertouch, dict):
                    at_ch = aftertouch.get("channel_override")
                    if isinstance(at_ch, int) and at_ch == channel and at_ch != -1:
                        path = f"triggers.{trigger_name}.aftertouch.channel_override"
                        context = f"trigger {trigger_name} aftertouch channel override"
                        hits.append(SearchHit(path=path, value=at_ch, context=context))

    # Search battery alert
    battery_alert = mapping_dict.get("battery_alert", {})
    if isinstance(battery_alert, dict):
        bat_ch = battery_alert.get("channel_override")
        if isinstance(bat_ch, int) and bat_ch == channel and bat_ch != -1:
            hits.append(SearchHit(
                path="battery_alert.channel_override",
                value=bat_ch,
                context="battery alert channel override"
            ))

    # Search touchpad
    touchpad = mapping_dict.get("touchpad", {})
    if isinstance(touchpad, dict):
        tp_ch = touchpad.get("channel_override")
        if isinstance(tp_ch, int) and tp_ch == channel and tp_ch != -1:
            hits.append(SearchHit(
                path="touchpad.channel_override",
                value=tp_ch,
                context="touchpad channel override"
            ))

    return hits


def summary(mapping_dict: dict) -> Dict[str, int]:
    """Generate a summary of the mapping's MIDI usage.

    Returns a dict with counts:
      - unique_notes: count of distinct note values in the mapping
      - unique_ccs: count of distinct CC values
      - channels_in_use: count of distinct channel numbers (0..15)
      - total_controls: count of buttons + axes + hats that are mapped (non-zero)

    Args:
      mapping_dict: the mapping dict

    Returns:
      dict with summary counts
    """
    if not isinstance(mapping_dict, dict):
        return {
            "unique_notes": 0,
            "unique_ccs": 0,
            "channels_in_use": 0,
            "total_controls": 0,
        }

    notes: set = set()
    ccs: set = set()
    channels: set = set()
    total_controls = 0

    # Collect notes from buttons
    buttons = mapping_dict.get("buttons", {})
    if isinstance(buttons, dict):
        for button_note in buttons.values():
            if isinstance(button_note, int) and 0 <= button_note <= 127:
                notes.add(button_note)

    # Collect notes from hats
    hats = mapping_dict.get("hats", {})
    if isinstance(hats, dict):
        for hat_note in hats.values():
            if isinstance(hat_note, int) and 0 <= hat_note <= 127:
                notes.add(hat_note)

    # Collect notes from gesture keys
    for gkey in ["swipe_up_note", "swipe_down_note", "swipe_left_note", "swipe_right_note",
                 "pinch_in_note", "pinch_out_note"]:
        gesture_note = mapping_dict.get(gkey)
        if isinstance(gesture_note, int) and 0 <= gesture_note <= 127:
            notes.add(gesture_note)

    # Collect notes from corner configs
    for corner_name in ["left_stick_corners", "right_stick_corners"]:
        corner = mapping_dict.get(corner_name, {})
        if isinstance(corner, dict):
            notes_list = corner.get("notes", [])
            if isinstance(notes_list, list):
                for n in notes_list:
                    if isinstance(n, int) and 0 <= n <= 127:
                        notes.add(n)

    # Collect notes from chord lists
    for stick_name in ["left_stick", "right_stick"]:
        stick = mapping_dict.get(stick_name, {})
        if isinstance(stick, dict):
            for chord_key in ["chord_north", "chord_east", "chord_south", "chord_west"]:
                chord_list = stick.get(chord_key, [])
                if isinstance(chord_list, list):
                    for n in chord_list:
                        if isinstance(n, int) and 0 <= n <= 127:
                            notes.add(n)

            # Flick notes
            flick = stick.get("flick", {})
            if isinstance(flick, dict):
                for flick_key in ["note_pos_x", "note_neg_x", "note_pos_y", "note_neg_y"]:
                    flick_note = flick.get(flick_key)
                    if isinstance(flick_note, int) and 0 <= flick_note <= 127:
                        notes.add(flick_note)

    # Collect battery alert note
    battery_alert = mapping_dict.get("battery_alert", {})
    if isinstance(battery_alert, dict):
        bat_note = battery_alert.get("note")
        if isinstance(bat_note, int) and 0 <= bat_note <= 127:
            notes.add(bat_note)

    # Collect CCs from axes
    axes = mapping_dict.get("axes", {})
    if isinstance(axes, dict):
        for axis_cc in axes.values():
            if isinstance(axis_cc, int) and 0 <= axis_cc <= 119:
                ccs.add(axis_cc)

    # Collect CCs from triggers
    triggers = mapping_dict.get("triggers", {})
    if isinstance(triggers, dict):
        for trigger_config in triggers.values():
            if isinstance(trigger_config, dict):
                for cc_key in ["cc", "crossfade_cc_b", "bow_cc"]:
                    tc = trigger_config.get(cc_key)
                    if isinstance(tc, int) and 0 <= tc <= 119:
                        ccs.add(tc)

    # Collect CCs from sticks
    for stick_name in ["left_stick", "right_stick"]:
        stick = mapping_dict.get(stick_name, {})
        if isinstance(stick, dict):
            for cc_key in ["polar_angle_cc", "polar_mag_cc", "random_mod_cc"]:
                sc = stick.get(cc_key)
                if isinstance(sc, int) and 0 <= sc <= 119:
                    ccs.add(sc)

    # Collect CCs from touchpad
    touchpad = mapping_dict.get("touchpad", {})
    if isinstance(touchpad, dict):
        for tp_key in ["x_cc", "y_cc"]:
            tc = touchpad.get(tp_key)
            if isinstance(tc, int) and 0 <= tc <= 119:
                ccs.add(tc)

    # Collect channels
    if "midi_channel" in mapping_dict and isinstance(mapping_dict["midi_channel"], int):
        ch = mapping_dict["midi_channel"]
        if 0 <= ch <= 15:
            channels.add(ch)

    # Collect from all channel override dicts
    for ch_dict_name in ["button_channels", "axis_channels", "hat_channels"]:
        ch_dict = mapping_dict.get(ch_dict_name, {})
        if isinstance(ch_dict, dict):
            for ch in ch_dict.values():
                if isinstance(ch, int) and 0 <= ch <= 15:
                    channels.add(ch)

    # Collect from stick chord channels
    for stick_name in ["left_stick", "right_stick"]:
        stick = mapping_dict.get(stick_name, {})
        if isinstance(stick, dict):
            stick_ch = stick.get("chord_channel")
            if isinstance(stick_ch, int) and 0 <= stick_ch <= 15:
                channels.add(stick_ch)

    # Collect from triggers
    if isinstance(triggers, dict):
        for trigger_config in triggers.values():
            if isinstance(trigger_config, dict):
                tch = trigger_config.get("channel_override")
                if isinstance(tch, int) and 0 <= tch <= 15:
                    channels.add(tch)

                # Aftertouch
                aftertouch = trigger_config.get("aftertouch", {})
                if isinstance(aftertouch, dict):
                    atch = aftertouch.get("channel_override")
                    if isinstance(atch, int) and 0 <= atch <= 15:
                        channels.add(atch)

    # Collect from battery alert
    if isinstance(battery_alert, dict):
        bch = battery_alert.get("channel_override")
        if isinstance(bch, int) and 0 <= bch <= 15:
            channels.add(bch)

    # Collect from touchpad
    if isinstance(touchpad, dict):
        tpch = touchpad.get("channel_override")
        if isinstance(tpch, int) and 0 <= tpch <= 15:
            channels.add(tpch)

    # Count mapped controls (non-zero)
    if isinstance(buttons, dict):
        total_controls += len([v for v in buttons.values() if isinstance(v, int) and v != 0])

    if isinstance(axes, dict):
        total_controls += len([v for v in axes.values() if isinstance(v, int) and v != 0])

    if isinstance(hats, dict):
        total_controls += len([v for v in hats.values() if isinstance(v, int) and v != 0])

    return {
        "unique_notes": len(notes),
        "unique_ccs": len(ccs),
        "channels_in_use": len(channels),
        "total_controls": total_controls,
    }


def _context_for_path(path: str, mapping_dict: dict) -> str:
    """Generate a human-readable context string for a path.

    Examples:
      "buttons.5" -> "button index 5"
      "left_stick.chord_north" -> "left stick / chord north"
      "triggers.L2.cc" -> "trigger L2 / CC"

    Args:
      path: dotted path (e.g. "buttons.5.note")
      mapping_dict: the mapping dict (for hints about what things are)

    Returns:
      human-readable context string
    """
    parts = path.replace("[", ".").replace("]", "").split(".")

    if not parts:
        return "unknown"

    # Try to build sensible context from the path
    if parts[0] == "buttons":
        if len(parts) > 1:
            return f"button index {parts[1]}"
        return "buttons"

    if parts[0] == "axes":
        if len(parts) > 1:
            axis_idx = parts[1]
            axis_names = {
                "0": "L-stick X",
                "1": "L-stick Y",
                "2": "R-stick X",
                "3": "R-stick Y",
                "4": "L-trigger (L2)",
                "5": "R-trigger (R2)",
            }
            axis_name = axis_names.get(axis_idx, f"axis {axis_idx}")
            return f"axis {axis_idx} / {axis_name}"
        return "axes"

    if parts[0] == "hats":
        if len(parts) > 1:
            return f"hat {parts[1]}"
        return "hats"

    if "stick" in parts[0]:
        stick_name = parts[0].replace("_", " ")
        if len(parts) > 1:
            sub = parts[1]
            return f"{stick_name} / {sub}"
        return stick_name

    if parts[0] == "triggers":
        if len(parts) > 1:
            return f"trigger {parts[1]}"
        return "triggers"

    if "gesture" in path or "swipe" in path or "pinch" in path:
        return f"gesture: {parts[-1]}"

    if "battery" in parts[0]:
        return "battery alert"

    if "midi_learn" in parts[0]:
        if len(parts) > 2 and parts[1] == "bindings":
            return f"MIDI learn binding {parts[2]}"
        return "MIDI learn"

    if "touchpad" in parts[0]:
        if len(parts) > 1:
            return f"touchpad / {parts[1]}"
        return "touchpad"

    # Fallback: use path as-is
    return path
