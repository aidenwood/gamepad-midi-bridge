"""Export a Mapping as human-readable Markdown documentation.

Pure stdlib — no Qt, no third-party dependencies.

Usage::

    from gamepad_midi_bridge.mapping_docs import render_mapping_docs
    md = render_mapping_docs(mapping)
    Path("my_preset.md").write_text(md, encoding="utf-8")
"""
from __future__ import annotations

from datetime import date
from typing import List

from . import __version__
from .mapping import Mapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _table(headers: List[str], rows: List[List[str]]) -> str:
    """Render a GitHub-Flavoured Markdown table."""
    widths = [max(len(h), *(len(r[i]) for r in rows), 3) for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    header_row = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    body = "\n".join(
        "| " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)) + " |"
        for row in rows
    )
    if body:
        return "\n".join([header_row, sep, body])
    return "\n".join([header_row, sep])


def _yn(val: bool) -> str:
    return "Yes" if val else "No"


def _channel(ch: int, default: int) -> str:
    """Return 1-based channel string."""
    return str((ch if ch >= 0 else default) + 1)


def _note_name(n: int) -> str:
    """Return MIDI note name + octave, e.g. C4 for note 60."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[n % 12]}{(n // 12) - 1}"


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_buttons(m: Mapping) -> str:
    if not m.buttons:
        return "_No button mappings._\n"
    headers = ["Button #", "MIDI Note", "Channel", "Velocity", "Gate btn", "Latch", "Repeat"]
    rows = []
    for btn_idx in sorted(m.buttons):
        note = m.buttons[btn_idx]
        ch = m.button_channels.get(btn_idx, m.midi_channel)
        cfg = m.button_configs.get(btn_idx)
        velocity = str(cfg.velocity) if cfg else "100"
        gate = str(cfg.gate_button) if cfg and cfg.gate_button is not None else "—"
        latch = _yn(False)  # buttons don't have a latch field at the mapping level
        repeat = _yn(cfg.repeat_enabled) if cfg else "No"
        rows.append([
            str(btn_idx),
            f"{note} ({_note_name(note)})",
            _channel(ch, m.midi_channel),
            velocity,
            gate,
            latch,
            repeat,
        ])
    return _table(headers, rows) + "\n"


def _render_axes(m: Mapping) -> str:
    if not m.axes:
        return "_No axis mappings._\n"
    headers = ["Axis #", "MIDI CC", "Channel", "Mode", "Curve"]
    rows = []
    for ax_idx in sorted(m.axes):
        cc = m.axes[ax_idx]
        ch = m.axis_channels.get(ax_idx, m.midi_channel)
        if ax_idx == 0:
            mode, curve = "Left stick X", m.left_stick.curve
        elif ax_idx == 1:
            mode, curve = "Left stick Y", m.left_stick.curve
        elif ax_idx == 2:
            mode, curve = "Right stick X", m.right_stick.curve
        elif ax_idx == 3:
            mode, curve = "Right stick Y", m.right_stick.curve
        elif ax_idx == 4:
            mode, curve = f"L2 ({m.l2_trigger.mode})", "—"
        elif ax_idx == 5:
            mode, curve = f"R2 ({m.r2_trigger.mode})", "—"
        else:
            mode, curve = "Analog", "—"
        rows.append([str(ax_idx), str(cc), _channel(ch, m.midi_channel), mode, curve])
    return _table(headers, rows) + "\n"


def _render_hats(m: Mapping) -> str:
    if not m.hats:
        return "_No D-pad mappings._\n"
    headers = ["Direction", "MIDI Note", "Channel"]
    rows = []
    for direction in ["up", "right", "down", "left"]:
        if direction not in m.hats:
            continue
        note = m.hats[direction]
        ch = m.hat_channels.get(direction, m.midi_channel)
        rows.append([direction.capitalize(), f"{note} ({_note_name(note)})", _channel(ch, m.midi_channel)])
    return _table(headers, rows) + "\n"


def _render_triggers(m: Mapping) -> str:
    lines = []
    for label, cfg in [("L2", m.l2_trigger), ("R2", m.r2_trigger)]:
        haptic = getattr(m, f"{'l2' if label == 'L2' else 'r2'}_haptic_effect") or "—"
        lines.append(f"**{label}**")
        lines.append(f"- Mode: `{cfg.mode}`")
        lines.append(f"- Ceiling CC value: {cfg.ceiling}")
        lines.append(f"- Latch threshold: {cfg.latch_threshold:.2f}")
        gate = str(cfg.gate_button) if cfg.gate_button is not None else "none"
        lines.append(f"- Gate button: {gate}")
        lines.append(f"- Gate release value: {cfg.gate_release_value}")
        lines.append(f"- Tactile click on latch: {_yn(cfg.tactile_click)}")
        at = cfg.aftertouch
        lines.append(f"- Aftertouch: {'enabled' if at.enabled else 'disabled'}"
                     + (f" (threshold {at.threshold:.2f})" if at.enabled else ""))
        lines.append(f"- Haptic effect: {haptic}")
        lines.append("")
    return "\n".join(lines)


def _render_sticks(m: Mapping) -> str:
    lines = []
    for label, sc in [("Left stick", m.left_stick), ("Right stick", m.right_stick)]:
        lines.append(f"**{label}**")
        lines.append(f"- Inner deadzone: {sc.inner_deadzone:.3f}")
        lines.append(f"- Outer clamp: {sc.outer_clamp:.3f}")
        lines.append(f"- Curve: {sc.curve} (amount {sc.curve_amount:.2f})")
        if sc.polar_mode:
            lines.append(f"- Polar mode: Yes — angle CC {sc.polar_angle_cc}, magnitude CC {sc.polar_mag_cc}")
        else:
            lines.append("- Polar mode: No")
        if sc.cc_smoothing_ms:
            lines.append(f"- CC smoothing: {sc.cc_smoothing_ms} ms")
        if sc.flick.enabled:
            lines.append(
                f"- Flick notes: +X={sc.flick.note_pos_x} −X={sc.flick.note_neg_x} "
                f"+Y={sc.flick.note_pos_y} −Y={sc.flick.note_neg_y} "
                f"(vel {sc.flick.velocity_min}–{sc.flick.velocity_max})"
            )
        if sc.lfo.enabled:
            lines.append(
                f"- LFO: {sc.lfo.waveform} @ {sc.lfo.rate_hz} Hz, "
                f"depth {sc.lfo.depth:.2f}, blend={sc.lfo.blend_mode}"
            )
        if sc.pitch_bend_enabled:
            lines.append(f"- Pitch bend: axis={sc.pitch_bend_axis}, range ±{sc.pitch_bend_range_semis} semitones")
        lines.append("")
    return "\n".join(lines)


def _render_touchpad(m: Mapping) -> str:
    tp = m.touchpad
    if not tp.enabled:
        return "_Touchpad disabled._\n"
    lines = [
        f"- Mode: {tp.mode}",
        f"- X CC: {tp.x_cc}  |  Y CC: {tp.y_cc}",
        f"- Two-finger: {_yn(tp.two_finger)}" + (f" (B X CC {tp.b_x_cc}, B Y CC {tp.b_y_cc})" if tp.two_finger else ""),
        f"- Click to arm: {_yn(tp.click_to_arm)}",
        f"- Inner deadzone: {tp.inner_deadzone:.3f}",
        f"- X curve: {tp.x_curve} ({tp.x_curve_amount:.2f})  |  Y curve: {tp.y_curve} ({tp.y_curve_amount:.2f})",
    ]
    if tp.zone_mode:
        notes_str = ", ".join(str(n) for n in tp.zone_notes)
        lines.append(f"- Zone mode: {tp.zone_grid}×{tp.zone_grid} grid, notes [{notes_str}], vel {tp.zone_velocity}")
    if tp.gesture_enabled:
        lines.append(
            f"- Gestures: swipe↑={tp.swipe_up_note} ↓={tp.swipe_down_note} "
            f"←={tp.swipe_left_note} →={tp.swipe_right_note} "
            f"pinch-in={tp.pinch_in_note} pinch-out={tp.pinch_out_note} "
            f"(min dist {tp.swipe_min_distance:.2f})"
        )
    return "\n".join(lines) + "\n"


def _render_shift_layer(m: Mapping) -> str:
    sl = m.shift_layer
    if not sl.enabled:
        return "_Shift layer disabled._\n"
    lines = [f"- Shift button: {sl.shift_button}"]
    if sl.buttons:
        lines.append("- Button overrides: " + ", ".join(f"{k}→{v}" for k, v in sorted(sl.buttons.items())))
    if sl.axes:
        lines.append("- Axis overrides: " + ", ".join(f"{k}→{v}" for k, v in sorted(sl.axes.items())))
    if sl.hats:
        lines.append("- Hat overrides: " + ", ".join(f"{k}→{v}" for k, v in sorted(sl.hats.items())))
    return "\n".join(lines) + "\n"


def _render_ab_compare(m: Mapping) -> str:
    if not m.ab_compare_enabled:
        return "_A/B compare disabled._\n"
    lines = [
        f"- Trigger button: {m.ab_compare_button}",
        f"- B preset: {m.ab_b_preset_slug or '(not set)'}",
    ]
    return "\n".join(lines) + "\n"


def _render_setlist(m: Mapping) -> str:
    sl = m.setlist
    if not sl.enabled:
        return "_Setlist disabled._\n"
    lines = [
        f"- Name: {sl.name}",
        f"- Presets: {', '.join(sl.presets) if sl.presets else '(empty)'}",
        f"- Next button: {sl.next_button if sl.next_button >= 0 else '(unset)'}",
        f"- Prev button: {sl.prev_button if sl.prev_button >= 0 else '(unset)'}",
        f"- Wrap: {_yn(sl.wrap)}",
    ]
    return "\n".join(lines) + "\n"


def _render_program_change(m: Mapping) -> str:
    pc = m.program_change
    if not pc.enabled:
        return "_Program change listener disabled._\n"
    ch_label = "any" if pc.listen_channel < 0 else str(pc.listen_channel + 1)
    lines = [f"- Listen channel: {ch_label}"]
    if pc.bindings:
        lines.append("- Bindings:")
        for pc_num in sorted(pc.bindings):
            lines.append(f"  - PC {pc_num} → `{pc.bindings[pc_num]}`")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_mapping_docs(mapping: Mapping) -> str:
    """Return a Markdown string documenting *mapping* in full.

    Pure stdlib — no Qt, no third-party imports.  Always produces valid
    UTF-8 text.
    """
    today = date.today().isoformat()

    sections: List[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    sections.append(f"# {mapping.name}\n")

    # ── Description ─────────────────────────────────────────────────────────
    sections.append("## Description\n")
    sections.append(
        f"| Property | Value |\n"
        f"| --- | --- |\n"
        f"| Schema version | {mapping.schema_version} |\n"
        f"| Global MIDI channel | {mapping.midi_channel + 1} |\n"
        f"| Deadzone | {mapping.deadzone:.3f} |\n"
        f"| Poll rate | {mapping.poll_hz} Hz |\n"
        f"| Color tag | {mapping.color_tag} |\n"
        f"| Favourite | {_yn(mapping.favourite)} |\n"
    )

    # ── Buttons → Notes ──────────────────────────────────────────────────────
    sections.append("## Buttons → Notes\n")
    sections.append(_render_buttons(mapping))

    # ── Axes → CC ────────────────────────────────────────────────────────────
    sections.append("## Axes → CC\n")
    sections.append(_render_axes(mapping))

    # ── D-pad → Notes ────────────────────────────────────────────────────────
    sections.append("## D-pad → Notes\n")
    sections.append(_render_hats(mapping))

    # ── Triggers ─────────────────────────────────────────────────────────────
    sections.append("## Triggers\n")
    sections.append(_render_triggers(mapping))

    # ── Sticks ───────────────────────────────────────────────────────────────
    sections.append("## Sticks\n")
    sections.append(_render_sticks(mapping))

    # ── Touchpad ─────────────────────────────────────────────────────────────
    sections.append("## Touchpad\n")
    sections.append(_render_touchpad(mapping))

    # ── Shift layer ──────────────────────────────────────────────────────────
    sections.append("## Shift Layer\n")
    sections.append(_render_shift_layer(mapping))

    # ── A/B compare ──────────────────────────────────────────────────────────
    sections.append("## A/B Compare\n")
    sections.append(_render_ab_compare(mapping))

    # ── Setlist ──────────────────────────────────────────────────────────────
    sections.append("## Setlist\n")
    sections.append(_render_setlist(mapping))

    # ── Program change ───────────────────────────────────────────────────────
    sections.append("## Program Change\n")
    sections.append(_render_program_change(mapping))

    # ── Footer ───────────────────────────────────────────────────────────────
    sections.append(
        f"---\n"
        f"_Generated {today} by Universal Controller MIDI Bridge v{__version__}_\n"
    )

    return "\n".join(sections)
