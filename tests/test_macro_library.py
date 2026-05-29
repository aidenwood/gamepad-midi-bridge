"""Macro effects library tests — flam, drumroll, glissando, portamento, chord_strum, tremolo."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.macro_library import (
    MACRO_RECIPES,
    MacroEvent,
    available_macros,
    chord_strum,
    drumroll,
    flam,
    glissando,
    portamento_cc,
    tremolo,
)


class TestMacroEventSerialization:
    """MacroEvent to_dict and from_dict."""

    def test_macro_event_to_dict_defaults(self):
        """to_dict serializes default event."""
        evt = MacroEvent(offset_ms=10.0, kind="note_on")
        data = evt.to_dict()
        assert data == {
            "offset_ms": 10.0,
            "kind": "note_on",
            "note": 0,
            "velocity": 100,
            "channel": 1,
            "cc": 0,
            "value": 0,
        }

    def test_macro_event_to_dict_full(self):
        """to_dict with all fields."""
        evt = MacroEvent(
            offset_ms=100.0,
            kind="cc",
            note=60,
            velocity=80,
            channel=2,
            cc=7,
            value=100,
        )
        data = evt.to_dict()
        assert data == {
            "offset_ms": 100.0,
            "kind": "cc",
            "note": 60,
            "velocity": 80,
            "channel": 2,
            "cc": 7,
            "value": 100,
        }

    def test_macro_event_from_dict(self):
        """from_dict deserializes correctly."""
        data = {
            "offset_ms": 50.0,
            "kind": "note_off",
            "note": 61,
            "velocity": 64,
            "channel": 3,
            "cc": 1,
            "value": 50,
        }
        evt = MacroEvent.from_dict(data)
        assert evt.offset_ms == 50.0
        assert evt.kind == "note_off"
        assert evt.note == 61
        assert evt.velocity == 64
        assert evt.channel == 3
        assert evt.cc == 1
        assert evt.value == 50

    def test_macro_event_from_dict_missing_fields(self):
        """from_dict uses defaults for missing fields."""
        evt = MacroEvent.from_dict({"offset_ms": 25.0, "kind": "note_on"})
        assert evt.offset_ms == 25.0
        assert evt.kind == "note_on"
        assert evt.note == 0
        assert evt.velocity == 100
        assert evt.channel == 1

    def test_macro_event_round_trip(self):
        """to_dict and from_dict preserve event."""
        evt = MacroEvent(
            offset_ms=75.5,
            kind="cc",
            note=72,
            velocity=90,
            channel=5,
            cc=64,
            value=127,
        )
        data = evt.to_dict()
        evt2 = MacroEvent.from_dict(data)
        assert evt == evt2


class TestFlam:
    """flam function — grace note + main note."""

    def test_flam_returns_four_events(self):
        """flam returns exactly 4 events."""
        events = flam(60)
        assert len(events) == 4

    def test_flam_event_kinds(self):
        """flam events are note_on, note_off, note_on, note_off."""
        events = flam(60)
        assert events[0].kind == "note_on"
        assert events[1].kind == "note_off"
        assert events[2].kind == "note_on"
        assert events[3].kind == "note_off"

    def test_flam_grace_note_is_two_semitones_below(self):
        """Grace note = root - 2 semitones."""
        events = flam(60)  # C4
        grace_note = events[0].note
        root_note = events[2].note
        assert root_note == 60
        assert grace_note == 58  # C4 - 2 = A#3

    def test_flam_grace_note_clamped_at_zero(self):
        """Grace note clamped to 0 when root < 2."""
        events = flam(1)
        grace_note = events[0].note
        assert grace_note == 0  # 1 - 2 = -1, clamped to 0

    def test_flam_grace_velocity_less_than_main(self):
        """Grace velocity < main velocity."""
        events = flam(60, grace_velocity=60, main_velocity=110)
        assert events[0].velocity == 60
        assert events[2].velocity == 110

    def test_flam_grace_offset(self):
        """Grace offset_ms is parameterizable."""
        events = flam(60, grace_offset_ms=25.0)
        assert events[2].offset_ms == 25.0  # root note_on
        assert events[3].offset_ms == 225.0  # root note_off

    def test_flam_channel(self):
        """flam respects channel parameter."""
        events = flam(60, channel=5)
        for evt in events:
            assert evt.channel == 5

    def test_flam_all_offsets_nonnegative(self):
        """All offsets are >= 0."""
        events = flam(60)
        for evt in events:
            assert evt.offset_ms >= 0

    def test_flam_clamped_channel_to_16(self):
        """channel > 16 clamped to 16."""
        events = flam(60, channel=20)
        assert all(evt.channel == 16 for evt in events)

    def test_flam_clamped_velocity_to_127(self):
        """velocity > 127 clamped to 127."""
        events = flam(60, grace_velocity=150, main_velocity=200)
        assert events[0].velocity == 127  # grace
        assert events[2].velocity == 127  # main


class TestDrumroll:
    """drumroll function — repeated note with velocity ramp."""

    def test_drumroll_returns_hits_times_two_events(self):
        """drumroll returns hits * 2 events."""
        events = drumroll(60, hits=6)
        assert len(events) == 12  # 6 hits * 2

    def test_drumroll_event_kinds_alternating(self):
        """Events alternate note_on, note_off."""
        events = drumroll(60, hits=3)
        for i in range(3):
            assert events[i * 2].kind == "note_on"
            assert events[i * 2 + 1].kind == "note_off"

    def test_drumroll_velocity_decreases(self):
        """Velocity decreases from start to end."""
        events = drumroll(60, hits=6, velocity_start=100, velocity_end=60)
        velocities = [events[i].velocity for i in range(0, 12, 2)]
        # Should be: 100, ~93, ~87, ~80, ~73, ~67 (roughly decreasing)
        assert velocities[0] == 100
        assert velocities[-1] <= 60  # Last should be <= end
        assert all(velocities[i] >= velocities[i + 1] for i in range(len(velocities) - 1))

    def test_drumroll_single_hit(self):
        """drumroll with hits=1 returns 2 events."""
        events = drumroll(60, hits=1)
        assert len(events) == 2

    def test_drumroll_zero_hits(self):
        """drumroll with hits=0 returns empty list."""
        events = drumroll(60, hits=0)
        assert len(events) == 0

    def test_drumroll_events_evenly_spaced(self):
        """Events spaced evenly over total_duration_ms."""
        events = drumroll(60, hits=4, total_duration_ms=400)
        # 4 hits over 400ms = 100ms per hit
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        offsets = [evt.offset_ms for evt in note_ons]
        assert offsets == [0.0, 100.0, 200.0, 300.0]

    def test_drumroll_all_same_note(self):
        """All events use the same root note."""
        events = drumroll(72, hits=5)
        for evt in events:
            assert evt.note == 72

    def test_drumroll_channel(self):
        """drumroll respects channel parameter."""
        events = drumroll(60, hits=2, channel=7)
        assert all(evt.channel == 7 for evt in events)


class TestGlissando:
    """glissando function — chromatic run."""

    def test_glissando_ascending(self):
        """Glissando from 60 to 65 has 6 notes (inclusive)."""
        events = glissando(60, 65, step_ms=50)
        # Notes: 60, 61, 62, 63, 64, 65 = 6 notes
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        notes = sorted(set(evt.note for evt in note_ons))
        assert notes == [60, 61, 62, 63, 64, 65]

    def test_glissando_descending(self):
        """Glissando from 65 to 60 descends."""
        events = glissando(65, 60, step_ms=50)
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        notes = [evt.note for evt in note_ons]
        # Should go 65, 64, 63, 62, 61, 60
        assert notes == [65, 64, 63, 62, 61, 60]

    def test_glissando_same_note(self):
        """Glissando from note to itself returns single note_on + note_off."""
        events = glissando(60, 60, duration_ms=100)
        assert len(events) == 2
        assert events[0].kind == "note_on"
        assert events[0].note == 60
        assert events[1].kind == "note_off"
        assert events[1].note == 60

    def test_glissando_velocity_consistent(self):
        """All notes have the same velocity."""
        events = glissando(60, 65, velocity=85)
        for evt in events:
            assert evt.velocity == 85

    def test_glissando_channel(self):
        """glissando respects channel parameter."""
        events = glissando(60, 65, channel=3)
        assert all(evt.channel == 3 for evt in events)

    def test_glissando_duration_final_note_off(self):
        """Final note_off is at duration_ms."""
        events = glissando(60, 62, duration_ms=200, step_ms=50)
        final_note_off = [evt for evt in events if evt.kind == "note_off"][-1]
        assert final_note_off.offset_ms == 200.0


class TestPortamentoCC:
    """portamento_cc function — smooth CC ramp."""

    def test_portamento_cc_returns_steps_events(self):
        """portamento_cc returns exactly steps CC events."""
        events = portamento_cc(0, 127, steps=16)
        assert len(events) == 16

    def test_portamento_cc_all_kind_cc(self):
        """All events are CC messages."""
        events = portamento_cc(0, 127, steps=8)
        assert all(evt.kind == "cc" for evt in events)

    def test_portamento_cc_values_linear(self):
        """CC values interpolate linearly from start to end."""
        events = portamento_cc(0, 100, steps=5)
        values = [evt.value for evt in events]
        # Should be approximately: 0, 25, 50, 75, 100
        assert values[0] == 0
        assert values[-1] == 100
        # Check monotonic increase
        assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))

    def test_portamento_cc_descending(self):
        """CC values can descend."""
        events = portamento_cc(127, 0, steps=5)
        values = [evt.value for evt in events]
        assert values[0] == 127
        assert values[-1] == 0
        assert all(values[i] >= values[i + 1] for i in range(len(values) - 1))

    def test_portamento_cc_single_step(self):
        """Single step returns start value."""
        events = portamento_cc(50, 100, steps=1)
        assert len(events) == 1
        assert events[0].value == 50  # First value is start_value

    def test_portamento_cc_zero_steps(self):
        """Zero steps returns empty list."""
        events = portamento_cc(0, 127, steps=0)
        assert len(events) == 0

    def test_portamento_cc_cc_number(self):
        """portamento_cc uses specified CC number."""
        events = portamento_cc(0, 127, cc=64, steps=4)
        assert all(evt.cc == 64 for evt in events)

    def test_portamento_cc_channel(self):
        """portamento_cc respects channel parameter."""
        events = portamento_cc(0, 127, channel=10, steps=4)
        assert all(evt.channel == 10 for evt in events)

    def test_portamento_cc_evenly_spaced_time(self):
        """CC events evenly spaced over duration."""
        events = portamento_cc(0, 127, duration_ms=1000, steps=5)
        offsets = [evt.offset_ms for evt in events]
        # 1000ms / 5 steps = 200ms per step
        assert offsets == [0.0, 200.0, 400.0, 600.0, 800.0]


class TestChordStrum:
    """chord_strum function — strum pattern."""

    def test_chord_strum_empty_chord(self):
        """Empty chord returns empty list."""
        events = chord_strum([])
        assert len(events) == 0

    def test_chord_strum_single_note(self):
        """Single-note chord returns note_on + note_off."""
        events = chord_strum([60])
        assert len(events) == 2
        assert events[0].kind == "note_on"
        assert events[1].kind == "note_off"

    def test_chord_strum_strums_in_order(self):
        """Notes are strummed in the order given."""
        events = chord_strum([60, 64, 67], strum_gap_ms=15)
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        notes = [evt.note for evt in note_ons]
        assert notes == [60, 64, 67]

    def test_chord_strum_strum_gap(self):
        """Note ons are spaced by strum_gap_ms."""
        events = chord_strum([60, 64, 67], strum_gap_ms=20)
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        offsets = [evt.offset_ms for evt in note_ons]
        assert offsets == [0.0, 20.0, 40.0]

    def test_chord_strum_all_release_together(self):
        """All notes release at hold_ms."""
        events = chord_strum([60, 64, 67], hold_ms=500)
        note_offs = [evt for evt in events if evt.kind == "note_off"]
        offsets = [evt.offset_ms for evt in note_offs]
        assert all(offset == 500.0 for offset in offsets)

    def test_chord_strum_velocity_consistent(self):
        """All notes have the same velocity."""
        events = chord_strum([60, 64, 67], velocity=85)
        for evt in events:
            assert evt.velocity == 85

    def test_chord_strum_channel(self):
        """chord_strum respects channel parameter."""
        events = chord_strum([60, 64, 67], channel=2)
        assert all(evt.channel == 2 for evt in events)

    def test_chord_strum_note_count(self):
        """Returns 2 * len(notes) events (one on + one off per note)."""
        notes = [60, 64, 67, 72]
        events = chord_strum(notes)
        assert len(events) == 8  # 4 notes * 2


class TestTremolo:
    """tremolo function — repeated same note."""

    def test_tremolo_returns_hits_times_two(self):
        """tremolo returns hits * 2 events."""
        events = tremolo(60, hits=8)
        assert len(events) == 16

    def test_tremolo_all_same_note(self):
        """All events use the same root note."""
        events = tremolo(72, hits=5)
        notes = set(evt.note for evt in events)
        assert notes == {72}

    def test_tremolo_event_kinds_alternating(self):
        """Events alternate note_on, note_off."""
        events = tremolo(60, hits=4)
        for i in range(4):
            assert events[i * 2].kind == "note_on"
            assert events[i * 2 + 1].kind == "note_off"

    def test_tremolo_gap_spacing(self):
        """Note ons spaced by gap_ms."""
        events = tremolo(60, hits=4, gap_ms=50)
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        offsets = [evt.offset_ms for evt in note_ons]
        assert offsets == [0.0, 50.0, 100.0, 150.0]

    def test_tremolo_velocity_consistent(self):
        """All notes have the same velocity."""
        events = tremolo(60, hits=5, velocity=90)
        for evt in events:
            assert evt.velocity == 90

    def test_tremolo_channel(self):
        """tremolo respects channel parameter."""
        events = tremolo(60, hits=3, channel=8)
        assert all(evt.channel == 8 for evt in events)

    def test_tremolo_zero_hits(self):
        """tremolo with hits=0 returns empty list."""
        events = tremolo(60, hits=0)
        assert len(events) == 0


class TestMacroRecipesAndAvailable:
    """MACRO_RECIPES and available_macros."""

    def test_macro_recipes_dict_has_all_macros(self):
        """MACRO_RECIPES contains all macro names."""
        assert "flam" in MACRO_RECIPES
        assert "drumroll" in MACRO_RECIPES
        assert "glissando" in MACRO_RECIPES
        assert "portamento_cc" in MACRO_RECIPES
        assert "chord_strum" in MACRO_RECIPES
        assert "tremolo" in MACRO_RECIPES

    def test_available_macros_returns_sorted_list(self):
        """available_macros returns sorted list of names."""
        names = available_macros()
        assert isinstance(names, list)
        assert names == sorted(names)
        assert "flam" in names
        assert "drumroll" in names
        assert "glissando" in names

    def test_macro_recipes_all_have_descriptions(self):
        """All recipes have non-empty descriptions."""
        for name, desc in MACRO_RECIPES.items():
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_available_macros_count_matches_recipes(self):
        """available_macros returns all recipes."""
        assert len(available_macros()) == len(MACRO_RECIPES)


class TestMIDIRangeClamping:
    """All values clamped to MIDI ranges (0..127 for notes/values, 1..16 for channels)."""

    def test_note_clamped_below_zero(self):
        """Notes < 0 clamped to 0."""
        events = flam(-10)
        assert all(0 <= evt.note <= 127 for evt in events)

    def test_note_clamped_above_127(self):
        """Notes > 127 clamped to 127."""
        events = glissando(200, 210)
        assert all(0 <= evt.note <= 127 for evt in events)

    def test_velocity_clamped_below_zero(self):
        """Velocities < 0 clamped to 0."""
        events = flam(60, grace_velocity=-50)
        assert all(0 <= evt.velocity <= 127 for evt in events)

    def test_velocity_clamped_above_127(self):
        """Velocities > 127 clamped to 127."""
        events = drumroll(60, hits=2, velocity_start=200)
        assert all(0 <= evt.velocity <= 127 for evt in events)

    def test_cc_value_clamped(self):
        """CC values clamped to 0..127."""
        events = portamento_cc(-50, 200, steps=4)
        assert all(0 <= evt.value <= 127 for evt in events)

    def test_cc_number_clamped(self):
        """CC number clamped to 0..127."""
        events = portamento_cc(0, 127, cc=200, steps=2)
        assert all(0 <= evt.cc <= 127 for evt in events)

    def test_channel_clamped_below_one(self):
        """Channel < 1 clamped to 1."""
        events = flam(60, channel=0)
        assert all(1 <= evt.channel <= 16 for evt in events)

    def test_channel_clamped_above_16(self):
        """Channel > 16 clamped to 16."""
        events = tremolo(60, hits=2, channel=100)
        assert all(1 <= evt.channel <= 16 for evt in events)


class TestOffsetProperties:
    """All MacroEvent offsets are non-negative and reasonable."""

    def test_flam_offsets_nonnegative(self):
        """All flam offsets >= 0."""
        events = flam(60)
        assert all(evt.offset_ms >= 0 for evt in events)

    def test_drumroll_offsets_nonnegative(self):
        """All drumroll offsets >= 0."""
        events = drumroll(60, hits=5)
        assert all(evt.offset_ms >= 0 for evt in events)

    def test_glissando_offsets_nonnegative(self):
        """All glissando offsets >= 0."""
        events = glissando(60, 65)
        assert all(evt.offset_ms >= 0 for evt in events)

    def test_portamento_cc_offsets_nonnegative(self):
        """All portamento_cc offsets >= 0."""
        events = portamento_cc(0, 127, steps=8)
        assert all(evt.offset_ms >= 0 for evt in events)

    def test_chord_strum_offsets_nonnegative(self):
        """All chord_strum offsets >= 0."""
        events = chord_strum([60, 64, 67])
        assert all(evt.offset_ms >= 0 for evt in events)

    def test_tremolo_offsets_nonnegative(self):
        """All tremolo offsets >= 0."""
        events = tremolo(60, hits=6)
        assert all(evt.offset_ms >= 0 for evt in events)


class TestIntegration:
    """Integration and real-world use cases."""

    def test_flam_produces_articulate_accent(self):
        """flam grace note is softer and earlier than main."""
        events = flam(72, grace_velocity=50, main_velocity=100, grace_offset_ms=15)
        grace_on = next(evt for evt in events if evt.kind == "note_on" and evt.offset_ms == 0.0)
        main_on = next(evt for evt in events if evt.kind == "note_on" and evt.offset_ms == 15.0)
        assert grace_on.velocity < main_on.velocity

    def test_drumroll_creates_smooth_effect(self):
        """drumroll with many hits creates smooth decay."""
        events = drumroll(60, hits=12, total_duration_ms=600, velocity_start=120, velocity_end=30)
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        velocities = [evt.velocity for evt in note_ons]
        # Check roughly monotonic decrease
        decreasing = sum(1 for i in range(len(velocities) - 1) if velocities[i] >= velocities[i + 1])
        assert decreasing >= len(velocities) - 2  # Allow up to 2 non-decreases

    def test_glissando_chromatic_completeness(self):
        """glissando covers all semitones between root and target."""
        events = glissando(60, 65, step_ms=50)
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        notes = sorted(set(evt.note for evt in note_ons))
        assert notes == list(range(60, 66))

    def test_portamento_cc_smooth_transition(self):
        """portamento_cc CC value smoothly transitions."""
        events = portamento_cc(0, 127, steps=10)
        values = [evt.value for evt in events]
        # Check no jumps > ~15 units
        for i in range(len(values) - 1):
            assert values[i + 1] - values[i] <= 15

    def test_chord_strum_playback_order(self):
        """chord_strum events can be played in offset order."""
        chord = [60, 64, 67, 72]
        events = chord_strum(chord, strum_gap_ms=10, hold_ms=200)
        sorted_events = sorted(events, key=lambda e: e.offset_ms)
        # All note ons before all note offs
        note_ons = [e for e in sorted_events if e.kind == "note_on"]
        note_offs = [e for e in sorted_events if e.kind == "note_off"]
        if note_ons and note_offs:
            last_on = max(e.offset_ms for e in note_ons)
            first_off = min(e.offset_ms for e in note_offs)
            assert last_on <= first_off

    def test_tremolo_percussive_rhythm(self):
        """tremolo creates even percussive pattern."""
        events = tremolo(60, hits=8, gap_ms=50)
        note_ons = [evt for evt in events if evt.kind == "note_on"]
        offsets = [evt.offset_ms for evt in note_ons]
        expected = [i * 50.0 for i in range(8)]
        assert offsets == expected

    def test_macro_event_serialization_roundtrip(self):
        """MacroEvent survives serialization cycle."""
        original = MacroEvent(
            offset_ms=123.45,
            kind="cc",
            note=61,
            velocity=99,
            channel=2,
            cc=7,
            value=64,
        )
        data = original.to_dict()
        restored = MacroEvent.from_dict(data)
        assert restored == original
