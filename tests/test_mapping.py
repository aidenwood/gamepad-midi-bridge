"""Mapping dataclass defaults + JSON round-trip + V1 backwards compat."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import (
    BatteryAlertConfig,
    CornerConfig,
    Mapping,
    OscConfig,
    SCHEMA_VERSION,
    ShiftLayerConfig,
    StickConfig,
    TouchpadConfig,
    _shift_layer_from_dict,
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
    # V4 shaping defaults
    assert cfg.mode == "absolute"
    assert cfg.click_to_arm is False
    assert cfg.inner_deadzone == 0.0
    assert cfg.x_curve == "linear"
    assert cfg.y_curve == "linear"
    assert cfg.x_curve_amount == 0.5
    assert cfg.y_curve_amount == 0.5


def test_touchpad_shaping_round_trip():
    """V4 touchpad shaping fields preserve through serialisation."""
    m = Mapping(name="TouchpadShaping")
    m.touchpad = TouchpadConfig(
        enabled=True,
        x_cc=20,
        y_cc=21,
        mode="relative",
        click_to_arm=True,
        inner_deadzone=0.1,
        x_curve="exponential",
        y_curve="logarithmic",
        x_curve_amount=0.7,
        y_curve_amount=0.3,
    )

    restored = Mapping.from_dict(m.to_dict())
    assert restored.touchpad.enabled is True
    assert restored.touchpad.x_cc == 20
    assert restored.touchpad.y_cc == 21
    assert restored.touchpad.mode == "relative"
    assert restored.touchpad.click_to_arm is True
    assert restored.touchpad.inner_deadzone == pytest.approx(0.1, abs=1e-6)
    assert restored.touchpad.x_curve == "exponential"
    assert restored.touchpad.y_curve == "logarithmic"
    assert restored.touchpad.x_curve_amount == pytest.approx(0.7, abs=1e-6)
    assert restored.touchpad.y_curve_amount == pytest.approx(0.3, abs=1e-6)


def test_v3_preset_loads_with_v4_defaults():
    """V3 preset (no touchpad shaping) loads cleanly with V4 defaults."""
    v3_dict = {
        "name": "LegacyTouchpad",
        "schema_version": 3,
        "touchpad": {
            "enabled": True,
            "x_cc": 20,
            "y_cc": 21,
            "require_contact": False,
            # Missing: mode, click_to_arm, inner_deadzone, curves, amounts
        }
    }
    m = Mapping.from_dict(v3_dict)
    assert m.touchpad.enabled is True
    assert m.touchpad.x_cc == 20
    assert m.touchpad.require_contact is False
    # Shaping fields default to V4 defaults (absolute, not armed, linear)
    assert m.touchpad.mode == "absolute"
    assert m.touchpad.click_to_arm is False
    assert m.touchpad.inner_deadzone == 0.0
    assert m.touchpad.x_curve == "linear"
    assert m.touchpad.y_curve == "linear"


def test_touchpad_curve_amount_clamping():
    """Curve amounts outside 0..1 are clamped on load."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "x_curve_amount": 1.5,   # over-range
            "y_curve_amount": -0.5,  # under-range
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.x_curve_amount == 1.0
    assert m.touchpad.y_curve_amount == 0.0


def test_touchpad_inner_deadzone_clamping():
    """Inner deadzone is clamped to 0..0.49."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "inner_deadzone": 0.7,   # over-range
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.inner_deadzone == pytest.approx(0.49, abs=1e-6)


def test_touchpad_schema_version_bumped():
    """Confirm SCHEMA_VERSION is 4."""
    assert SCHEMA_VERSION == 4


def test_stick_config_defaults():
    """StickConfig defaults preserve legacy behaviour (linear, no clamp, no polar)."""
    cfg = StickConfig()
    assert cfg.inner_deadzone == 0.05
    assert cfg.outer_clamp == 0.0
    assert cfg.curve == "linear"
    assert cfg.curve_amount == 0.5
    assert cfg.polar_mode is False
    assert cfg.polar_angle_cc == 7
    assert cfg.polar_mag_cc == 8


def test_stick_config_round_trip():
    """StickConfig fields preserve through serialisation."""
    m = Mapping(name="StickShaping")
    m.left_stick = StickConfig(
        inner_deadzone=0.1,
        outer_clamp=0.15,
        curve="exponential",
        curve_amount=0.7,
        polar_mode=False,
    )
    m.right_stick = StickConfig(
        inner_deadzone=0.08,
        outer_clamp=0.0,
        curve="s-curve",
        curve_amount=0.6,
        polar_mode=True,
        polar_angle_cc=10,
        polar_mag_cc=11,
    )

    restored = Mapping.from_dict(m.to_dict())
    assert restored.left_stick.inner_deadzone == pytest.approx(0.1, abs=1e-6)
    assert restored.left_stick.outer_clamp == pytest.approx(0.15, abs=1e-6)
    assert restored.left_stick.curve == "exponential"
    assert restored.left_stick.curve_amount == pytest.approx(0.7, abs=1e-6)
    assert restored.left_stick.polar_mode is False

    assert restored.right_stick.inner_deadzone == pytest.approx(0.08, abs=1e-6)
    assert restored.right_stick.outer_clamp == 0.0
    assert restored.right_stick.curve == "s-curve"
    assert restored.right_stick.curve_amount == pytest.approx(0.6, abs=1e-6)
    assert restored.right_stick.polar_mode is True
    assert restored.right_stick.polar_angle_cc == 10
    assert restored.right_stick.polar_mag_cc == 11


def test_stick_config_invalid_curve_defaults_to_linear():
    """Invalid curve names default to 'linear' on load."""
    v_dict = {
        "left_stick": {
            "curve": "invalid_curve_name",
            "curve_amount": 0.5,
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.left_stick.curve == "linear"


def test_stick_config_clamping():
    """StickConfig numeric fields are clamped on load."""
    v_dict = {
        "left_stick": {
            "inner_deadzone": 1.5,    # over-range
            "outer_clamp": -0.1,      # under-range
            "curve_amount": 2.0,      # over-range
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.left_stick.inner_deadzone == pytest.approx(0.99, abs=1e-6)
    assert m.left_stick.outer_clamp == 0.0
    assert m.left_stick.curve_amount == 1.0


def test_stick_config_missing_fields_load_defaults():
    """StickConfig fields missing from dict load with sensible defaults."""
    v_dict = {
        "left_stick": {
            "inner_deadzone": 0.1,
            # Missing: outer_clamp, curve, curve_amount, polar_mode, polar_*_cc
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.left_stick.inner_deadzone == pytest.approx(0.1, abs=1e-6)
    assert m.left_stick.outer_clamp == 0.0
    assert m.left_stick.curve == "linear"
    assert m.left_stick.curve_amount == 0.5
    assert m.left_stick.polar_mode is False
    assert m.left_stick.polar_angle_cc == 7
    assert m.left_stick.polar_mag_cc == 8


def test_v3_preset_loads_with_v4_stick_defaults():
    """V3 preset (no stick config) loads cleanly with V4 defaults."""
    v3_dict = {
        "name": "LegacySticks",
        "schema_version": 3,
        "buttons": {"0": 60},
        "axes": {"0": 3},
        # Missing: left_stick, right_stick
    }
    m = Mapping.from_dict(v3_dict)
    # Legacy behaviour: linear stick ramp, no polar, default deadzone
    assert m.left_stick.curve == "linear"
    assert m.left_stick.polar_mode is False
    assert m.left_stick.inner_deadzone == pytest.approx(0.05, abs=1e-6)
    assert m.right_stick.curve == "linear"
    assert m.right_stick.polar_mode is False


def test_battery_alert_config_defaults():
    """BatteryAlertConfig has sensible defaults."""
    cfg = BatteryAlertConfig()
    assert cfg.enabled is False
    assert cfg.threshold_percent == 15
    assert cfg.note == 60
    assert cfg.velocity == 100
    assert cfg.channel_override is None


def test_battery_alert_config_round_trip():
    """BatteryAlertConfig serializes and deserializes correctly."""
    m = Mapping(name="BatteryAlert")
    m.battery_alert = BatteryAlertConfig(
        enabled=True,
        threshold_percent=20,
        note=64,
        velocity=80,
        channel_override=5,
    )
    restored = Mapping.from_dict(m.to_dict())
    assert restored.battery_alert.enabled is True
    assert restored.battery_alert.threshold_percent == 20
    assert restored.battery_alert.note == 64
    assert restored.battery_alert.velocity == 80
    assert restored.battery_alert.channel_override == 5


def test_corner_config_haptic_feedback_round_trip():
    """CornerConfig corner_haptic_feedback field round-trips correctly."""
    m = Mapping(name="CornerHaptic")
    m.left_stick_corners = CornerConfig(
        enabled=True,
        n=8,
        notes=list(range(60, 68)),
        corner_haptic_feedback=False,
    )
    restored = Mapping.from_dict(m.to_dict())
    assert restored.left_stick_corners.enabled is True
    assert restored.left_stick_corners.corner_haptic_feedback is False


def test_corner_config_haptic_feedback_default_is_true():
    """CornerConfig defaults corner_haptic_feedback to True."""
    cfg = CornerConfig()
    assert cfg.corner_haptic_feedback is True


def test_v4_preset_without_battery_alert_loads_with_defaults():
    """V4 preset (no battery_alert field) loads cleanly with defaults."""
    v4_dict = {
        "name": "LegacyV4",
        "schema_version": 4,
        "buttons": {"0": 60},
        "axes": {"0": 3},
        # Missing: battery_alert
    }
    m = Mapping.from_dict(v4_dict)
    assert m.battery_alert.enabled is False
    assert m.battery_alert.threshold_percent == 15
    assert m.battery_alert.note == 60
    assert m.battery_alert.velocity == 100
    assert m.battery_alert.channel_override is None


# ------------------------------------------------------------------ shift layer


def test_shift_layer_config_defaults():
    """ShiftLayerConfig defaults to disabled/unset."""
    sl = ShiftLayerConfig()
    assert sl.enabled is False
    assert sl.shift_button == -1
    assert sl.buttons == {}
    assert sl.axes == {}
    assert sl.hats == {}


def test_shift_layer_config_round_trip():
    """ShiftLayerConfig serialises and deserialises end-to-end via Mapping."""
    m = Mapping(name="ShiftTest")
    m.shift_layer = ShiftLayerConfig(
        enabled=True,
        shift_button=4,
        buttons={0: 72, 1: 74},
        axes={0: 10},
        hats={"up": 90},
    )
    restored = Mapping.from_dict(m.to_dict())
    sl = restored.shift_layer
    assert sl.enabled is True
    assert sl.shift_button == 4
    assert sl.buttons == {0: 72, 1: 74}
    assert sl.axes == {0: 10}
    assert sl.hats == {"up": 90}


def test_shift_layer_from_dict_handles_missing_fields():
    """_shift_layer_from_dict fills in defaults for any absent keys."""
    sl = _shift_layer_from_dict({"enabled": True})
    assert sl.enabled is True
    assert sl.shift_button == -1
    assert sl.buttons == {}
    assert sl.axes == {}
    assert sl.hats == {}


def test_shift_layer_from_dict_none_returns_disabled():
    """_shift_layer_from_dict(None) returns a disabled default."""
    sl = _shift_layer_from_dict(None)
    assert sl.enabled is False
    assert sl.shift_button == -1


def test_v4_preset_without_shift_layer_loads_cleanly():
    """V4 preset (no shift_layer field) loads cleanly; shift layer disabled."""
    v4_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "buttons": {"0": 60},
        "axes": {"0": 3},
        # Missing: shift_layer
    }
    m = Mapping.from_dict(v4_dict)
    assert m.shift_layer.enabled is False
    assert m.shift_layer.shift_button == -1
    assert m.shift_layer.buttons == {}


def test_schema_version_unchanged():
    """SCHEMA_VERSION is still 4 after adding shift layer."""
    assert SCHEMA_VERSION == 4


# ------------------------------------------------------------------ A/B compare


def test_ab_compare_defaults():
    """A/B compare fields default to disabled/unset/no slug."""
    m = Mapping()
    assert m.ab_compare_enabled is False
    assert m.ab_compare_button == -1
    assert m.ab_b_preset_slug is None


def test_ab_compare_round_trip():
    """A/B compare fields round-trip through serialisation."""
    m = Mapping(name="ABTest")
    m.ab_compare_enabled = True
    m.ab_compare_button = 6
    m.ab_b_preset_slug = "my-b-preset"

    restored = Mapping.from_dict(m.to_dict())
    assert restored.ab_compare_enabled is True
    assert restored.ab_compare_button == 6
    assert restored.ab_b_preset_slug == "my-b-preset"


def test_ab_compare_missing_fields_load_defaults():
    """Preset without ab_compare keys loads cleanly with safe defaults."""
    v_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "buttons": {"0": 60},
        # Missing: ab_compare_enabled, ab_compare_button, ab_b_preset_slug
    }
    m = Mapping.from_dict(v_dict)
    assert m.ab_compare_enabled is False
    assert m.ab_compare_button == -1
    assert m.ab_b_preset_slug is None


def test_ab_compare_none_slug_tolerates_cleanly():
    """Explicitly setting ab_b_preset_slug=None round-trips to None."""
    m = Mapping(name="ABNoSlug")
    m.ab_compare_enabled = True
    m.ab_compare_button = 3
    m.ab_b_preset_slug = None

    restored = Mapping.from_dict(m.to_dict())
    assert restored.ab_b_preset_slug is None
    assert restored.ab_compare_button == 3
