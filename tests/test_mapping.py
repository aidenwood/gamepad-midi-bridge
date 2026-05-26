"""Mapping dataclass defaults + JSON round-trip + V1 backwards compat."""
from __future__ import annotations

from gamepad_midi_bridge.mapping import (
    CornerConfig,
    Mapping,
    OscConfig,
    SCHEMA_VERSION,
    TouchpadConfig,
)


def test_default_mapping_counts():
    m = Mapping()
    assert len(m.buttons) == 11
    assert len(m.axes) == 6
    assert len(m.hats) == 4
    assert m.midi_channel == 0
    assert m.schema_version == SCHEMA_VERSION


def test_round_trip_preserves_fields():
    m = Mapping(name="RoundTrip", midi_channel=7, deadzone=0.1, poll_hz=200)
    m.left_stick_corners = CornerConfig(enabled=True, n=8, notes=list(range(60, 68)))
    m.touchpad = TouchpadConfig(enabled=True, x_cc=20, y_cc=21, require_contact=False)
    m.osc = OscConfig(enabled=True, mode="only", host="10.0.0.1", port=9000,
                      button_addresses={0: "/a"}, axis_addresses={1: "/b"})
    m.l2_haptic_effect = "weapon"
    m.r2_haptic_effect = "vibration"

    restored = Mapping.from_dict(m.to_dict())
    assert restored.name == m.name
    assert restored.midi_channel == m.midi_channel
    assert restored.deadzone == m.deadzone
    assert restored.poll_hz == m.poll_hz
    assert restored.buttons == m.buttons
    assert restored.axes == m.axes
    assert restored.hats == m.hats
    assert restored.left_stick_corners.enabled is True
    assert restored.left_stick_corners.notes == list(range(60, 68))
    assert restored.touchpad.x_cc == 20
    assert restored.osc.host == "10.0.0.1"
    assert restored.osc.button_addresses == {0: "/a"}
    assert restored.osc.axis_addresses == {1: "/b"}
    assert restored.l2_haptic_effect == "weapon"
    assert restored.r2_haptic_effect == "vibration"


def test_v1_dict_loads_with_v11_defaults():
    """Old V1 preset (no schema_version, no V1.1 fields) loads cleanly."""
    v1_dict = {
        "name": "Legacy",
        "midi_channel": 3,
        "deadzone": 0.07,
        "poll_hz": 120,
        "buttons": {"0": 40, "1": 41},
        "axes": {"0": 1, "1": 2},
        "hats": {"up": 90, "down": 91, "left": 92, "right": 93},
    }
    m = Mapping.from_dict(v1_dict)
    assert m.name == "Legacy"
    assert m.midi_channel == 3
    assert m.schema_version == 1
    # V1.1 fields default sensibly
    assert isinstance(m.left_stick_corners, CornerConfig)
    assert m.left_stick_corners.enabled is False
    assert isinstance(m.osc, OscConfig)
    assert m.osc.enabled is False
    assert m.osc.port == 7000
    assert m.osc.mode == "alongside"
    assert m.touchpad.enabled is False
    assert m.l2_haptic_effect is None
    assert m.r2_haptic_effect is None


def test_corner_config_ensure_notes_pads():
    cfg = CornerConfig(n=8, notes=[60, 61])
    cfg.ensure_notes()
    assert len(cfg.notes) == 8
    assert cfg.notes[:2] == [60, 61]


def test_corner_config_ensure_notes_trims():
    cfg = CornerConfig(n=4, notes=[60, 61, 62, 63, 64, 65])
    cfg.ensure_notes()
    assert cfg.notes == [60, 61, 62, 63]


def test_corner_config_ensure_notes_empty():
    cfg = CornerConfig(n=4, notes=[])
    cfg.ensure_notes()
    assert len(cfg.notes) == 4
    # Defaults to a chromatic sweep starting at C6 (note 96).
    assert cfg.notes == [96, 97, 98, 99]


def test_osc_config_defaults():
    cfg = OscConfig()
    assert cfg.enabled is False
    assert cfg.port == 7000
    assert cfg.mode == "alongside"
    assert cfg.host == "127.0.0.1"
    assert cfg.button_addresses == {}
    assert cfg.axis_addresses == {}


def test_touchpad_config_defaults():
    cfg = TouchpadConfig()
    assert cfg.enabled is False
    assert cfg.x_cc == 16
    assert cfg.y_cc == 17
    assert cfg.require_contact is True
