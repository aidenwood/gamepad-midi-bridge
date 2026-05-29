"""Tests for the macro recorder feature.

Covers:
  - MacroEvent and Macro round-trip serialisation.
  - Empty macro list default on a fresh Mapping.
  - Mapping with macros serialises and deserialises correctly.
  - _macro_from_dict handles missing / partial fields gracefully.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import (
    MacroEvent,
    Macro,
    Mapping,
    _macro_event_from_dict,
    _macro_from_dict,
    _macros_from_dict,
)


# ------------------------------------------------------------------ unit tests


class TestMacroEvent:
    def test_round_trip_via_dataclass(self):
        ev = MacroEvent(delay_ms=100, status=0x90, data1=60, data2=127)
        assert ev.delay_ms == 100
        assert ev.status == 0x90
        assert ev.data1 == 60
        assert ev.data2 == 127

    def test_from_dict_full(self):
        d = {"delay_ms": 50, "status": 0xB0, "data1": 7, "data2": 64}
        ev = _macro_event_from_dict(d)
        assert ev.delay_ms == 50
        assert ev.status == 0xB0
        assert ev.data1 == 7
        assert ev.data2 == 64

    def test_from_dict_missing_fields_default_to_zero(self):
        ev = _macro_event_from_dict({})
        assert ev.delay_ms == 0
        assert ev.status == 0
        assert ev.data1 == 0
        assert ev.data2 == 0

    def test_from_dict_clamps_data_bytes(self):
        ev = _macro_event_from_dict({"delay_ms": 0, "status": 300, "data1": 200, "data2": -5})
        # status is not clamped (can be any status byte 0..255)
        assert ev.status == 255  # clamped to 255
        assert ev.data1 == 127  # clamped to 127
        assert ev.data2 == 0    # clamped to 0 (negative → 0)

    def test_from_dict_negative_delay_clamps_to_zero(self):
        ev = _macro_event_from_dict({"delay_ms": -100})
        assert ev.delay_ms == 0


class TestMacro:
    def test_empty_macro(self):
        m = Macro(name="Test")
        assert m.name == "Test"
        assert m.events == []
        assert m.duration_ms == 0

    def test_macro_with_events(self):
        events = [
            MacroEvent(delay_ms=0, status=0x90, data1=60, data2=100),
            MacroEvent(delay_ms=200, status=0x80, data1=60, data2=0),
        ]
        m = Macro(name="Kick", events=events, duration_ms=200)
        assert len(m.events) == 2
        assert m.duration_ms == 200

    def test_from_dict_full(self):
        d = {
            "name": "arp",
            "duration_ms": 300,
            "events": [
                {"delay_ms": 0, "status": 0x90, "data1": 60, "data2": 127},
                {"delay_ms": 150, "status": 0x90, "data1": 64, "data2": 127},
                {"delay_ms": 300, "status": 0x80, "data1": 60, "data2": 0},
            ],
        }
        m = _macro_from_dict(d)
        assert m.name == "arp"
        assert len(m.events) == 3
        assert m.duration_ms == 300
        assert m.events[1].delay_ms == 150

    def test_from_dict_missing_events_key(self):
        m = _macro_from_dict({"name": "empty"})
        assert m.name == "empty"
        assert m.events == []
        assert m.duration_ms == 0

    def test_from_dict_bad_event_entries_skipped(self):
        d = {
            "name": "partial",
            "events": [
                "not_a_dict",
                None,
                {"delay_ms": 10, "status": 0x90, "data1": 64, "data2": 80},
            ],
        }
        m = _macro_from_dict(d)
        assert len(m.events) == 1
        assert m.events[0].delay_ms == 10

    def test_from_dict_missing_name_defaults(self):
        m = _macro_from_dict({})
        assert m.name == "Unnamed"


class TestMacrosList:
    def test_macros_from_dict_none_returns_empty(self):
        assert _macros_from_dict(None) == []

    def test_macros_from_dict_empty_list(self):
        assert _macros_from_dict([]) == []

    def test_macros_from_dict_non_list_returns_empty(self):
        assert _macros_from_dict("bad") == []
        assert _macros_from_dict(42) == []

    def test_macros_from_dict_valid(self):
        raw = [
            {"name": "one", "events": [{"delay_ms": 0, "status": 0x90, "data1": 60, "data2": 127}]},
            {"name": "two", "events": []},
        ]
        result = _macros_from_dict(raw)
        assert len(result) == 2
        assert result[0].name == "one"
        assert result[1].name == "two"

    def test_macros_from_dict_skips_non_dicts(self):
        raw = ["not_a_dict", None, {"name": "ok", "events": []}]
        result = _macros_from_dict(raw)
        assert len(result) == 1
        assert result[0].name == "ok"


class TestMappingMacroFields:
    def test_fresh_mapping_has_empty_macros(self):
        m = Mapping()
        assert m.macros == []
        assert m.macro_bindings == {}

    def test_mapping_round_trip_with_macros(self):
        events = [MacroEvent(delay_ms=0, status=0x90, data1=60, data2=127)]
        macro = Macro(name="hit", events=events, duration_ms=0)
        m = Mapping(macros=[macro], macro_bindings={5: "hit"})

        d = m.to_dict()
        assert "macros" in d
        assert "macro_bindings" in d
        # Macro bindings keys are serialised as strings by asdict
        # but from_dict converts them back to ints.
        m2 = Mapping.from_dict(d)
        assert len(m2.macros) == 1
        assert m2.macros[0].name == "hit"
        assert len(m2.macros[0].events) == 1
        assert m2.macros[0].events[0].status == 0x90
        assert m2.macro_bindings == {5: "hit"}

    def test_mapping_from_dict_without_macros_defaults(self):
        """Old presets lacking macro keys load cleanly with defaults."""
        m = Mapping.from_dict({"name": "legacy"})
        assert m.macros == []
        assert m.macro_bindings == {}

    def test_mapping_from_dict_macro_bindings_keys_are_ints(self):
        d = Mapping().to_dict()
        d["macro_bindings"] = {"3": "my_macro", "7": "other"}
        m = Mapping.from_dict(d)
        assert 3 in m.macro_bindings
        assert m.macro_bindings[3] == "my_macro"
        assert 7 in m.macro_bindings
