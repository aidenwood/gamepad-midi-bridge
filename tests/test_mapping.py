"""Mapping dataclass defaults + JSON round-trip + V1 backwards compat."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import (
    BatteryAlertConfig,
    ButtonConfig,
    CornerConfig,
    Mapping,
    OscConfig,
    PassthroughConfig,
    ProgramChangeConfig,
    SCHEMA_VERSION,
    SetlistConfig,
    ShiftLayerConfig,
    StickConfig,
    TouchpadConfig,
    TriggerConfig,
    _passthrough_from_dict,
    _program_change_from_dict,
    _setlist_config_from_dict,
    _shift_layer_from_dict,
    _stick_from_dict,
    _button_config_from_dict,
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


# ------------------------------------------------------------------ button config (feature #1)


def test_button_config_defaults():
    """ButtonConfig defaults to no gate."""
    cfg = ButtonConfig()
    assert cfg.gate_button is None
    assert cfg.gate_release_value == 0


def test_button_config_round_trip():
    """ButtonConfig serializes and deserializes correctly."""
    m = Mapping(name="ButtonGateTest")
    m.button_configs = {
        0: ButtonConfig(gate_button=4, gate_release_value=64),
        2: ButtonConfig(gate_button=5),
    }
    restored = Mapping.from_dict(m.to_dict())
    assert restored.button_configs[0].gate_button == 4
    assert restored.button_configs[0].gate_release_value == 64
    assert restored.button_configs[2].gate_button == 5
    assert restored.button_configs[2].gate_release_value == 0


def test_mapping_with_sparse_button_configs_round_trips():
    """Sparse button_configs dict (only some buttons gated) round-trips correctly."""
    m = Mapping(name="SparseButtonGates")
    m.button_configs = {
        1: ButtonConfig(gate_button=10),
        3: ButtonConfig(gate_button=11, gate_release_value=32),
    }
    restored = Mapping.from_dict(m.to_dict())
    assert len(restored.button_configs) == 2
    assert 0 not in restored.button_configs
    assert 1 in restored.button_configs
    assert 3 in restored.button_configs
    assert restored.button_configs[1].gate_button == 10
    assert restored.button_configs[3].gate_release_value == 32


# ------------------------------------------------------------------ trigger config tactile_click (feature #10)


def test_trigger_config_tactile_click_defaults_true():
    """TriggerConfig tactile_click defaults to True."""
    cfg = TriggerConfig()
    assert cfg.tactile_click is True


def test_trigger_config_tactile_click_round_trip():
    """TriggerConfig tactile_click field round-trips correctly."""
    m = Mapping(name="TactileClickTest")
    m.l2_trigger = TriggerConfig(mode="latch", tactile_click=False)
    m.r2_trigger = TriggerConfig(mode="latch", tactile_click=True)
    restored = Mapping.from_dict(m.to_dict())
    assert restored.l2_trigger.tactile_click is False
    assert restored.r2_trigger.tactile_click is True


def test_v4_preset_without_button_configs_tactile_click_loads_with_defaults():
    """V4 preset without button_configs and tactile_click loads cleanly with defaults."""
    v4_dict = {
        "name": "LegacyV4NoNewFields",
        "schema_version": 4,
        "buttons": {"0": 60},
        "axes": {"0": 3},
        # Missing: button_configs, l2_trigger/r2_trigger tactile_click
    }
    m = Mapping.from_dict(v4_dict)
    # button_configs should default to empty dict
    assert m.button_configs == {}
    # tactile_click should default to True for both triggers
    assert m.l2_trigger.tactile_click is True
    assert m.r2_trigger.tactile_click is True


def test_schema_version_still_4():
    """Confirm SCHEMA_VERSION is still 4 after adding features #1 and #10."""
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


def test_per_control_channel_maps_round_trip():
    """Per-control channel overrides serialize and deserialize correctly."""
    m = Mapping(name="ChannelOverrides")
    m.button_channels = {0: 3, 5: 7}
    m.axis_channels = {1: 2, 4: 8}
    m.hat_channels = {"up": 5, "left": 10}

    restored = Mapping.from_dict(m.to_dict())
    assert restored.button_channels == {0: 3, 5: 7}
    assert restored.axis_channels == {1: 2, 4: 8}
    assert restored.hat_channels == {"up": 5, "left": 10}


def test_per_control_channels_default_to_global():
    """When channel not in override map, should default to global."""
    # This test exercises the bridge helpers directly
    from gamepad_midi_bridge.bridge import BridgeWorker

    worker = BridgeWorker(demo=True)
    mapping = Mapping(midi_channel=2)
    mapping.button_channels = {0: 5}  # Only button 0 overridden
    
    # Button 0 uses override
    assert worker._channel_for_button(mapping, 0) == 5
    # Button 1 not in override map, falls back to global
    assert worker._channel_for_button(mapping, 1) == 2
    
    # Axes and hats behave similarly
    mapping.axis_channels = {2: 10}
    assert worker._channel_for_axis(mapping, 2) == 10
    assert worker._channel_for_axis(mapping, 3) == 2
    
    mapping.hat_channels = {"up": 15}
    assert worker._channel_for_hat(mapping, "up") == 15
    assert worker._channel_for_hat(mapping, "down") == 2


def test_per_control_channel_values_clamped_0_to_15():
    """Channel values outside 0..15 are clamped on deserialization."""
    v_dict = {
        "name": "BadChannels",
        "button_channels": {"0": -5, "1": 20},  # Should clamp to 0 and 15
        "axis_channels": {"2": 99},  # Should clamp to 15
        "hat_channels": {"up": -1},  # Should clamp to 0
    }
    m = Mapping.from_dict(v_dict)
    assert m.button_channels[0] == 0
    assert m.button_channels[1] == 15
    assert m.axis_channels[2] == 15
    assert m.hat_channels["up"] == 0


def test_background_launch_config_round_trip():
    """Background launch setting serializes and deserializes correctly."""
    m = Mapping(name="BackgroundMode")
    m.always_background_on_launch = True

    restored = Mapping.from_dict(m.to_dict())
    assert restored.always_background_on_launch is True

    # Default is False
    m2 = Mapping(name="Default")
    restored2 = Mapping.from_dict(m2.to_dict())
    assert restored2.always_background_on_launch is False


# ------------------------------------------------------------------ port_name_override (feature #23)


def test_port_name_override_defaults_to_none():
    """port_name_override defaults to None."""
    m = Mapping()
    assert m.port_name_override is None


def test_port_name_override_round_trip():
    """port_name_override serializes and deserializes correctly."""
    m = Mapping(name="PortNameTest")
    m.port_name_override = "Logic Pro MIDI Input"

    restored = Mapping.from_dict(m.to_dict())
    assert restored.port_name_override == "Logic Pro MIDI Input"


def test_port_name_override_empty_string_becomes_none():
    """Empty string port_name_override becomes None on deserialization."""
    v_dict = {
        "name": "EmptyPort",
        "port_name_override": "",
    }
    m = Mapping.from_dict(v_dict)
    assert m.port_name_override is None


# ------------------------------------------------------------------ program change (feature #15)


def test_program_change_config_defaults():
    """ProgramChangeConfig defaults to disabled with empty bindings."""
    cfg = ProgramChangeConfig()
    assert cfg.enabled is False
    assert cfg.listen_channel == -1
    assert cfg.bindings == {}


def test_program_change_config_round_trip():
    """ProgramChangeConfig serialises and deserialises end-to-end via Mapping."""
    m = Mapping(name="PCHotSwap")
    m.program_change = ProgramChangeConfig(
        enabled=True,
        listen_channel=0,
        bindings={0: "verse-groove", 5: "chorus-punch", 127: "outro-quiet"},
    )
    restored = Mapping.from_dict(m.to_dict())
    pc = restored.program_change
    assert pc.enabled is True
    assert pc.listen_channel == 0
    assert pc.bindings[0] == "verse-groove"
    assert pc.bindings[5] == "chorus-punch"
    assert pc.bindings[127] == "outro-quiet"


def test_program_change_config_missing_fields_load_defaults():
    """Preset without program_change key loads cleanly; feature disabled."""
    v_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "buttons": {"0": 60},
    }
    m = Mapping.from_dict(v_dict)
    assert m.program_change.enabled is False
    assert m.program_change.listen_channel == -1
    assert m.program_change.bindings == {}


def test_program_change_from_dict_handles_missing_fields():
    """_program_change_from_dict fills in defaults for absent keys."""
    pc = _program_change_from_dict({"enabled": True})
    assert pc.enabled is True
    assert pc.listen_channel == -1
    assert pc.bindings == {}


def test_program_change_from_dict_none_returns_disabled():
    """_program_change_from_dict(None) returns a disabled default."""
    pc = _program_change_from_dict(None)
    assert pc.enabled is False
    assert pc.bindings == {}


def test_program_change_from_dict_string_keys_parse_to_int():
    """JSON string keys in bindings are converted to int PC numbers."""
    raw = {
        "enabled": True,
        "listen_channel": -1,
        "bindings": {"0": "kick-map", "63": "snare-map", "127": "fill-map"},
    }
    pc = _program_change_from_dict(raw)
    assert 0 in pc.bindings
    assert 63 in pc.bindings
    assert 127 in pc.bindings
    assert pc.bindings[0] == "kick-map"
    assert pc.bindings[63] == "snare-map"
    assert pc.bindings[127] == "fill-map"


def test_program_change_from_dict_skips_malformed_entries():
    """Malformed bindings entries (bad PC key or empty slug) are skipped."""
    raw = {
        "enabled": True,
        "bindings": {
            "not_a_number": "valid-slug",  # bad key
            "5": "",                        # empty slug skipped
            "10": "good-slug",
        },
    }
    pc = _program_change_from_dict(raw)
    assert "not_a_number" not in str(pc.bindings)
    assert 5 not in pc.bindings   # empty slug excluded
    assert pc.bindings.get(10) == "good-slug"


def test_schema_version_unchanged_after_feature_15():
    """SCHEMA_VERSION is still 4 after adding program change."""
    assert SCHEMA_VERSION == 4


# ------------------------------------------------------------------ zone mode (feature #9)


def test_touchpad_zone_mode_defaults():
    """TouchpadConfig zone mode fields default correctly."""
    cfg = TouchpadConfig()
    assert cfg.zone_mode is False
    assert cfg.zone_grid == 2
    assert cfg.zone_notes == [36, 38, 40, 42]
    assert cfg.zone_velocity == 100


def test_touchpad_zone_mode_round_trip():
    """TouchpadConfig zone mode fields round-trip through serialisation."""
    m = Mapping(name="ZoneModeTest")
    m.touchpad = TouchpadConfig(
        enabled=True,
        zone_mode=True,
        zone_grid=3,
        zone_notes=[36, 38, 40, 42, 43, 45, 46, 47, 48],
        zone_velocity=80,
    )
    restored = Mapping.from_dict(m.to_dict())
    assert restored.touchpad.zone_mode is True
    assert restored.touchpad.zone_grid == 3
    assert restored.touchpad.zone_notes == [36, 38, 40, 42, 43, 45, 46, 47, 48]
    assert restored.touchpad.zone_velocity == 80


def test_touchpad_zone_grid_clamps_to_1_4():
    """zone_grid clamps to 1..4 on deserialization."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "zone_mode": True,
            "zone_grid": 0,      # under-range
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.zone_grid == 1

    v_dict["touchpad"]["zone_grid"] = 10   # over-range
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.zone_grid == 4


def test_touchpad_zone_notes_clamped_to_0_127():
    """zone_notes values are clamped to 0..127."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "zone_mode": True,
            "zone_notes": [-5, 36, 150, 64],  # -5 and 150 out of range
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.zone_notes == [0, 36, 127, 64]


def test_touchpad_zone_notes_skips_malformed():
    """Malformed zone_notes entries are skipped; defaults used if empty."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "zone_mode": True,
            "zone_notes": ["not_a_number", 36, None, 40],
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.zone_notes == [36, 40]


def test_touchpad_zone_notes_empty_uses_defaults():
    """Empty zone_notes list defaults to [36, 38, 40, 42]."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "zone_mode": True,
            "zone_notes": [],
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.zone_notes == [36, 38, 40, 42]


def test_touchpad_zone_velocity_clamped_0_127():
    """zone_velocity clamps to 0..127."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "zone_mode": True,
            "zone_velocity": 150,  # over-range
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.zone_velocity == 127

    v_dict["touchpad"]["zone_velocity"] = -10  # under-range
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.zone_velocity == 0


def test_touchpad_zone_mode_compatible_with_cc_mode():
    """Mapping can toggle between zone_mode and CC mode without data loss."""
    m = Mapping(name="ZoneToggle")
    m.touchpad = TouchpadConfig(
        enabled=True,
        x_cc=20,
        y_cc=21,
        zone_mode=False,
    )
    restored = Mapping.from_dict(m.to_dict())
    # CC fields preserved
    assert restored.touchpad.x_cc == 20
    assert restored.touchpad.y_cc == 21
    # Zone mode field is False
    assert restored.touchpad.zone_mode is False

    # Now switch to zone mode
    m.touchpad.zone_mode = True
    m.touchpad.zone_grid = 2
    m.touchpad.zone_notes = [36, 38, 40, 42]
    restored = Mapping.from_dict(m.to_dict())
    assert restored.touchpad.zone_mode is True
    assert restored.touchpad.zone_grid == 2
    # CC fields still there if we switch back
    assert restored.touchpad.x_cc == 20
    assert restored.touchpad.y_cc == 21


def test_v4_preset_without_zone_mode_loads_with_defaults():
    """V4 preset (no zone_mode fields) loads cleanly with zone defaults."""
    v4_dict = {
        "name": "LegacyTouchpadNoZone",
        "schema_version": 4,
        "touchpad": {
            "enabled": True,
            "x_cc": 20,
            "y_cc": 21,
            # Missing: zone_mode, zone_grid, zone_notes, zone_velocity
        }
    }
    m = Mapping.from_dict(v4_dict)
    assert m.touchpad.zone_mode is False
    assert m.touchpad.zone_grid == 2
    assert m.touchpad.zone_notes == [36, 38, 40, 42]
    assert m.touchpad.zone_velocity == 100


def test_touchpad_zone_grid_4x4_has_16_default_notes():
    """4x4 zone grid with short zone_notes list defaults sensibly."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "zone_mode": True,
            "zone_grid": 4,
            "zone_notes": [36, 38],  # only 2 notes for 16 zones
        }
    }
    m = Mapping.from_dict(v_dict)
    # Notes are preserved (not padded by loader)
    assert m.touchpad.zone_notes == [36, 38]
    assert m.touchpad.zone_grid == 4


def test_touchpad_gesture_config_defaults():
    """Gesture fields default to disabled with sensible note + velocity values."""
    cfg = TouchpadConfig()
    assert cfg.gesture_enabled is False
    assert cfg.swipe_up_note == 60
    assert cfg.swipe_down_note == 61
    assert cfg.swipe_left_note == 62
    assert cfg.swipe_right_note == 63
    assert cfg.pinch_in_note == 64
    assert cfg.pinch_out_note == 65
    assert cfg.gesture_velocity == 100
    assert cfg.swipe_min_distance == 0.3


def test_touchpad_gesture_round_trip():
    """Gesture config fields preserve through serialisation."""
    m = Mapping(name="GestureTest")
    m.touchpad = TouchpadConfig(
        enabled=True,
        gesture_enabled=True,
        swipe_up_note=72,
        swipe_down_note=73,
        swipe_left_note=74,
        swipe_right_note=75,
        pinch_in_note=76,
        pinch_out_note=77,
        gesture_velocity=110,
        swipe_min_distance=0.25,
    )
    
    restored = Mapping.from_dict(m.to_dict())
    assert restored.touchpad.gesture_enabled is True
    assert restored.touchpad.swipe_up_note == 72
    assert restored.touchpad.swipe_down_note == 73
    assert restored.touchpad.swipe_left_note == 74
    assert restored.touchpad.swipe_right_note == 75
    assert restored.touchpad.pinch_in_note == 76
    assert restored.touchpad.pinch_out_note == 77
    assert restored.touchpad.gesture_velocity == 110
    assert restored.touchpad.swipe_min_distance == pytest.approx(0.25, abs=1e-6)


def test_touchpad_gesture_clamping():
    """Gesture note values clamp to MIDI range 0..127."""
    v_dict = {
        "touchpad": {
            "enabled": True,
            "gesture_enabled": True,
            "swipe_up_note": 150,      # over-range
            "swipe_down_note": -10,    # under-range
            "gesture_velocity": 200,   # over-range
            "swipe_min_distance": 1.5, # over-range
        }
    }
    m = Mapping.from_dict(v_dict)
    assert m.touchpad.swipe_up_note == 127
    assert m.touchpad.swipe_down_note == 0
    assert m.touchpad.gesture_velocity == 127
    assert m.touchpad.swipe_min_distance == 1.0


def test_touchpad_gesture_independent_of_zone_mode():
    """Gesture and zone_mode are independent fields."""
    m = Mapping(name="BothModes")
    m.touchpad = TouchpadConfig(
        enabled=True,
        gesture_enabled=True,
        zone_mode=True,  # both can be True; gesture wins
        swipe_up_note=60,
        zone_grid=2,
        zone_notes=[36, 38, 40, 42],
    )

    restored = Mapping.from_dict(m.to_dict())
    assert restored.touchpad.gesture_enabled is True
    assert restored.touchpad.zone_mode is True
    assert restored.touchpad.swipe_up_note == 60
    assert restored.touchpad.zone_grid == 2


# ------------------------------------------------------------------ setlist (feature: Setlist mode)


def test_setlist_config_defaults():
    """SetlistConfig defaults to disabled with empty preset list."""
    sl = SetlistConfig()
    assert sl.enabled is False
    assert sl.name == "Setlist"
    assert sl.presets == []
    assert sl.next_button == -1
    assert sl.prev_button == -1
    assert sl.wrap is True


def test_setlist_config_round_trip():
    """SetlistConfig serialises and deserialises end-to-end via Mapping."""
    m = Mapping(name="SetlistTest")
    m.setlist = SetlistConfig(
        enabled=True,
        name="Show Night 1",
        presets=["intro", "verse", "drop", "outro"],
        next_button=5,
        prev_button=4,
        wrap=False,
    )
    restored = Mapping.from_dict(m.to_dict())
    sl = restored.setlist
    assert sl.enabled is True
    assert sl.name == "Show Night 1"
    assert sl.presets == ["intro", "verse", "drop", "outro"]
    assert sl.next_button == 5
    assert sl.prev_button == 4
    assert sl.wrap is False


def test_setlist_config_from_dict_handles_missing_fields():
    """_setlist_config_from_dict fills in defaults for absent keys."""
    sl = _setlist_config_from_dict({"enabled": True, "presets": ["verse"]})
    assert sl.enabled is True
    assert sl.name == "Setlist"
    assert sl.presets == ["verse"]
    assert sl.next_button == -1
    assert sl.prev_button == -1
    assert sl.wrap is True


def test_setlist_config_from_dict_none_returns_disabled():
    """_setlist_config_from_dict(None) returns a disabled default."""
    sl = _setlist_config_from_dict(None)
    assert sl.enabled is False
    assert sl.presets == []


def test_mapping_without_setlist_loads_with_default():
    """Old preset (no setlist key) loads cleanly; setlist stays disabled."""
    v_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "buttons": {"0": 60},
        # Missing: setlist
    }
    m = Mapping.from_dict(v_dict)
    assert m.setlist.enabled is False
    assert m.setlist.presets == []
    assert m.setlist.next_button == -1


def test_schema_version_unchanged_after_setlist():
    """SCHEMA_VERSION stays at 4 — setlist is additive."""
    assert SCHEMA_VERSION == 4


# Feature #A: CC smoothing per stick axis
def test_stick_config_cc_smoothing_ms_default():
    """StickConfig.cc_smoothing_ms defaults to 0 (off)."""
    cfg = StickConfig()
    assert cfg.cc_smoothing_ms == 0


def test_stick_config_cc_smoothing_ms_round_trip():
    """StickConfig with non-zero cc_smoothing_ms round-trips through JSON."""
    cfg = StickConfig(cc_smoothing_ms=100)
    assert cfg.cc_smoothing_ms == 100
    # Via Mapping round-trip
    m = Mapping(left_stick=cfg)
    restored = Mapping.from_dict(m.to_dict())
    assert restored.left_stick.cc_smoothing_ms == 100


def test_stick_config_cc_smoothing_ms_clamps_to_0_1000():
    """StickConfig.cc_smoothing_ms clamps to 0..1000."""
    # Below min: -5 → 0
    cfg = _stick_from_dict({"cc_smoothing_ms": -5})
    assert cfg.cc_smoothing_ms == 0
    
    # At min: 0 → 0
    cfg = _stick_from_dict({"cc_smoothing_ms": 0})
    assert cfg.cc_smoothing_ms == 0
    
    # In range: 500 → 500
    cfg = _stick_from_dict({"cc_smoothing_ms": 500})
    assert cfg.cc_smoothing_ms == 500
    
    # At max: 1000 → 1000
    cfg = _stick_from_dict({"cc_smoothing_ms": 1000})
    assert cfg.cc_smoothing_ms == 1000
    
    # Above max: 1500 → 1000
    cfg = _stick_from_dict({"cc_smoothing_ms": 1500})
    assert cfg.cc_smoothing_ms == 1000


# Feature #B: Velocity sensitivity per button
def test_button_config_velocity_default():
    """ButtonConfig.velocity defaults to 100."""
    cfg = ButtonConfig()
    assert cfg.velocity == 100


def test_button_config_velocity_round_trip():
    """ButtonConfig with custom velocity round-trips through JSON."""
    cfg = ButtonConfig(velocity=80)
    assert cfg.velocity == 80
    # Via Mapping round-trip
    m = Mapping(button_configs={0: cfg})
    restored = Mapping.from_dict(m.to_dict())
    assert restored.button_configs[0].velocity == 80


def test_button_config_velocity_clamps_to_0_127():
    """ButtonConfig.velocity clamps to 0..127."""
    # Below min: -1 → 0
    cfg = _button_config_from_dict({"velocity": -1})
    assert cfg.velocity == 0
    
    # At min: 0 → 0
    cfg = _button_config_from_dict({"velocity": 0})
    assert cfg.velocity == 0
    
    # In range: 64 → 64
    cfg = _button_config_from_dict({"velocity": 64})
    assert cfg.velocity == 64
    
    # At max: 127 → 127
    cfg = _button_config_from_dict({"velocity": 127})
    assert cfg.velocity == 127
    
    # Above max: 200 → 127
    cfg = _button_config_from_dict({"velocity": 200})
    assert cfg.velocity == 127


# ---------------------------------------------------------- PassthroughConfig

def test_passthrough_config_defaults():
    """PassthroughConfig defaults to disabled with safe field values."""
    cfg = PassthroughConfig()
    assert cfg.enabled is False
    assert cfg.input_port_name == ""
    assert cfg.transpose_semitones == 0
    assert cfg.channel_remap == -1
    assert cfg.pass_cc is True
    assert cfg.pass_notes is True
    assert cfg.pass_other is False


def test_passthrough_config_round_trip():
    """PassthroughConfig round-trips through Mapping.to_dict / from_dict."""
    m = Mapping()
    m.passthrough = PassthroughConfig(
        enabled=True,
        input_port_name="My MIDI Keyboard",
        transpose_semitones=7,
        channel_remap=3,
        pass_cc=False,
        pass_notes=True,
        pass_other=True,
    )
    restored = Mapping.from_dict(m.to_dict())
    pt = restored.passthrough
    assert pt.enabled is True
    assert pt.input_port_name == "My MIDI Keyboard"
    assert pt.transpose_semitones == 7
    assert pt.channel_remap == 3
    assert pt.pass_cc is False
    assert pt.pass_notes is True
    assert pt.pass_other is True


def test_passthrough_channel_remap_clamp():
    """channel_remap clamps to -1..15."""
    assert _passthrough_from_dict({"channel_remap": -1}).channel_remap == -1
    assert _passthrough_from_dict({"channel_remap": 0}).channel_remap == 0
    assert _passthrough_from_dict({"channel_remap": 15}).channel_remap == 15
    # Out-of-range values clamp to boundaries.
    assert _passthrough_from_dict({"channel_remap": -5}).channel_remap == -1
    assert _passthrough_from_dict({"channel_remap": 99}).channel_remap == 15


def test_passthrough_transpose_clamp():
    """transpose_semitones clamps to -24..+24."""
    assert _passthrough_from_dict({"transpose_semitones": 0}).transpose_semitones == 0
    assert _passthrough_from_dict({"transpose_semitones": 24}).transpose_semitones == 24
    assert _passthrough_from_dict({"transpose_semitones": -24}).transpose_semitones == -24
    assert _passthrough_from_dict({"transpose_semitones": 99}).transpose_semitones == 24
    assert _passthrough_from_dict({"transpose_semitones": -99}).transpose_semitones == -24


def test_passthrough_defaults_to_disabled():
    """_passthrough_from_dict(None) returns a disabled default config."""
    cfg = _passthrough_from_dict(None)
    assert cfg.enabled is False
    assert cfg.input_port_name == ""
    assert cfg.transpose_semitones == 0
    assert cfg.channel_remap == -1


def test_mapping_without_passthrough_loads_with_default():
    """Old preset (no passthrough key) loads cleanly; passthrough stays disabled."""
    v_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "buttons": {"0": 60},
        # Missing: passthrough
    }
    m = Mapping.from_dict(v_dict)
    assert m.passthrough.enabled is False
    assert m.passthrough.input_port_name == ""
    assert m.passthrough.channel_remap == -1


# ------------------------------------------------------------------ color tag + favourite


def test_color_tag_and_favourite_defaults():
    """color_tag defaults to 'none', favourite defaults to False."""
    m = Mapping()
    assert m.color_tag == "none"
    assert m.favourite is False


def test_color_tag_round_trip():
    """color_tag serializes and deserializes correctly."""
    from gamepad_midi_bridge.mapping import COLOR_TAGS

    for tag in COLOR_TAGS:
        m = Mapping(name=f"ColorTest_{tag}", color_tag=tag)
        restored = Mapping.from_dict(m.to_dict())
        assert restored.color_tag == tag


def test_favourite_round_trip():
    """favourite flag serializes and deserializes correctly."""
    m = Mapping(name="FavouriteTest", favourite=True)
    restored = Mapping.from_dict(m.to_dict())
    assert restored.favourite is True


def test_invalid_color_tag_falls_back_to_none():
    """Invalid color_tag defaults to 'none'."""
    v_dict = {
        "name": "BadColor",
        "color_tag": "invalid_color",
    }
    m = Mapping.from_dict(v_dict)
    assert m.color_tag == "none"


def test_color_tags_contains_expected_values():
    """COLOR_TAGS contains the 9 expected values."""
    from gamepad_midi_bridge.mapping import COLOR_TAGS

    expected = ("none", "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink")
    assert COLOR_TAGS == expected
    assert len(COLOR_TAGS) == 9


def test_color_tag_and_favourite_in_full_preset():
    """color_tag and favourite work in a full preset with other fields."""
    m = Mapping(
        name="FullPreset",
        midi_channel=5,
        color_tag="blue",
        favourite=True,
    )
    m.buttons[0] = 72
    m.axes[2] = 10

    restored = Mapping.from_dict(m.to_dict())
    assert restored.name == "FullPreset"
    assert restored.midi_channel == 5
    assert restored.color_tag == "blue"
    assert restored.favourite is True
    assert restored.buttons[0] == 72
    assert restored.axes[2] == 10


def test_old_preset_without_color_tag_loads_cleanly():
    """Old preset (no color_tag/favourite keys) loads with defaults."""
    v_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "buttons": {"0": 60},
        # Missing: color_tag and favourite
    }
    m = Mapping.from_dict(v_dict)
    assert m.color_tag == "none"
    assert m.favourite is False


# ------------------------------------------------------------------ StickFlickConfig (#A)


def test_stick_flick_config_defaults():
    """StickFlickConfig defaults to disabled with expected note/velocity values."""
    from gamepad_midi_bridge.mapping import StickFlickConfig

    cfg = StickFlickConfig()
    assert cfg.enabled is False
    assert cfg.note_pos_x == 64
    assert cfg.note_neg_x == 65
    assert cfg.note_pos_y == 66
    assert cfg.note_neg_y == 67
    assert cfg.velocity_min == 30
    assert cfg.velocity_max == 127
    assert cfg.speed_threshold == pytest.approx(4.0, abs=1e-6)


def test_stick_flick_config_round_trip():
    """StickFlickConfig preserves all fields through Mapping serialisation."""
    from gamepad_midi_bridge.mapping import StickFlickConfig

    m = Mapping(name="FlickTest")
    m.left_stick.flick = StickFlickConfig(
        enabled=True,
        note_pos_x=70,
        note_neg_x=71,
        note_pos_y=72,
        note_neg_y=73,
        velocity_min=40,
        velocity_max=120,
        speed_threshold=6.0,
    )
    restored = Mapping.from_dict(m.to_dict())
    flick = restored.left_stick.flick
    assert flick.enabled is True
    assert flick.note_pos_x == 70
    assert flick.note_neg_x == 71
    assert flick.note_pos_y == 72
    assert flick.note_neg_y == 73
    assert flick.velocity_min == 40
    assert flick.velocity_max == 120
    assert flick.speed_threshold == pytest.approx(6.0, abs=1e-6)


def test_stick_flick_config_nested_in_mapping_round_trip():
    """left_stick.flick and right_stick.flick both survive a full Mapping round-trip."""
    from gamepad_midi_bridge.mapping import StickFlickConfig

    m = Mapping(name="BothFlicks")
    m.left_stick.flick = StickFlickConfig(enabled=True, speed_threshold=3.0)
    m.right_stick.flick = StickFlickConfig(enabled=False, note_pos_x=80)

    restored = Mapping.from_dict(m.to_dict())
    assert restored.left_stick.flick.enabled is True
    assert restored.left_stick.flick.speed_threshold == pytest.approx(3.0, abs=1e-6)
    assert restored.right_stick.flick.enabled is False
    assert restored.right_stick.flick.note_pos_x == 80


def test_old_preset_without_flick_loads_with_defaults():
    """Old preset (no flick field) loads cleanly; flick stays disabled."""
    v_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "left_stick": {
            "inner_deadzone": 0.05,
            "curve": "linear",
        },
    }
    m = Mapping.from_dict(v_dict)
    assert m.left_stick.flick.enabled is False
    assert m.left_stick.flick.speed_threshold == pytest.approx(4.0, abs=1e-6)


# ------------------------------------------------------------------ TriggerAftertouchConfig (#B)


def test_trigger_aftertouch_config_defaults():
    """TriggerAftertouchConfig defaults to disabled."""
    from gamepad_midi_bridge.mapping import TriggerAftertouchConfig

    cfg = TriggerAftertouchConfig()
    assert cfg.enabled is False
    assert cfg.threshold == pytest.approx(0.85, abs=1e-6)
    assert cfg.channel_override == -1


def test_trigger_aftertouch_config_round_trip():
    """TriggerAftertouchConfig preserves all fields through Mapping serialisation."""
    from gamepad_midi_bridge.mapping import TriggerAftertouchConfig

    m = Mapping(name="ATTest")
    m.l2_trigger.aftertouch = TriggerAftertouchConfig(
        enabled=True, threshold=0.9, channel_override=2
    )
    restored = Mapping.from_dict(m.to_dict())
    at = restored.l2_trigger.aftertouch
    assert at.enabled is True
    assert at.threshold == pytest.approx(0.9, abs=1e-6)
    assert at.channel_override == 2


def test_trigger_aftertouch_nested_in_mapping_round_trip():
    """l2_trigger.aftertouch and r2_trigger.aftertouch both survive a full Mapping round-trip."""
    from gamepad_midi_bridge.mapping import TriggerAftertouchConfig

    m = Mapping(name="BothAT")
    m.l2_trigger.aftertouch = TriggerAftertouchConfig(enabled=True, threshold=0.8)
    m.r2_trigger.aftertouch = TriggerAftertouchConfig(enabled=False, channel_override=5)

    restored = Mapping.from_dict(m.to_dict())
    assert restored.l2_trigger.aftertouch.enabled is True
    assert restored.l2_trigger.aftertouch.threshold == pytest.approx(0.8, abs=1e-6)
    assert restored.r2_trigger.aftertouch.enabled is False
    assert restored.r2_trigger.aftertouch.channel_override == 5


def test_old_preset_without_aftertouch_loads_with_defaults():
    """Old preset (no aftertouch field on trigger) loads cleanly; AT stays disabled."""
    v_dict = {
        "name": "OldPreset",
        "schema_version": 4,
        "l2_trigger": {
            "mode": "linear",
        },
    }
    m = Mapping.from_dict(v_dict)
    assert m.l2_trigger.aftertouch.enabled is False
    assert m.l2_trigger.aftertouch.threshold == pytest.approx(0.85, abs=1e-6)
