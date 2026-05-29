"""Tests for haptic effect presets library.

HapticEffect descriptors for DualSense controllers: kick, snap, click, buzz,
heartbeat, tick, flash, drum_roll. Pure data, no Qt, no hardware writes.
"""
from __future__ import annotations

import pytest


class TestListEffects:
    """list_effects() — retrieve all builtin effects."""

    def test_list_effects_returns_8_effects(self):
        """list_effects() returns exactly 8 builtin effects."""
        from gamepad_midi_bridge.haptic_presets import list_effects

        effects = list_effects()
        assert len(effects) == 8

    def test_list_effects_all_slugs_unique(self):
        """All effect slugs are unique."""
        from gamepad_midi_bridge.haptic_presets import list_effects

        effects = list_effects()
        slugs = [e.slug for e in effects]
        assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {slugs}"

    def test_list_effects_contains_expected_slugs(self):
        """list_effects() includes kick, snap, click, buzz, heartbeat, tick, flash, drum_roll."""
        from gamepad_midi_bridge.haptic_presets import list_effects

        effects = list_effects()
        slugs = {e.slug for e in effects}
        expected = {"kick", "snap", "click", "buzz", "heartbeat", "tick", "flash", "drum_roll"}
        assert slugs == expected


class TestGetEffect:
    """get_effect(slug) — lookup single effect by slug."""

    def test_get_effect_kick(self):
        """get_effect("kick") returns the kick effect."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        kick = get_effect("kick")
        assert kick is not None
        assert kick.slug == "kick"
        assert kick.display_name == "Kick"

    def test_get_effect_heartbeat(self):
        """get_effect("heartbeat") returns the heartbeat effect."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        hb = get_effect("heartbeat")
        assert hb is not None
        assert hb.slug == "heartbeat"
        assert hb.display_name == "Heartbeat"

    def test_get_effect_nonexistent(self):
        """get_effect() returns None for unknown slug."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        result = get_effect("nonexistent")
        assert result is None

    def test_get_effect_case_sensitive(self):
        """get_effect() is case-sensitive."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        assert get_effect("KICK") is None
        assert get_effect("Kick") is None
        assert get_effect("kick") is not None


class TestEffectTypes:
    """Effect type validation and filtering."""

    def test_kick_effect_type_is_rumble(self):
        """kick.effect_type == "rumble"."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        kick = get_effect("kick")
        assert kick.effect_type == "rumble"

    def test_snap_effect_type_is_trigger_click(self):
        """snap.effect_type == "trigger_click"."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        snap = get_effect("snap")
        assert snap.effect_type == "trigger_click"

    def test_buzz_effect_type_is_trigger_buzz(self):
        """buzz.effect_type == "trigger_buzz"."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        buzz = get_effect("buzz")
        assert buzz.effect_type == "trigger_buzz"

    def test_heartbeat_effect_type_is_trigger_pulse(self):
        """heartbeat.effect_type == "trigger_pulse"."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        hb = get_effect("heartbeat")
        assert hb.effect_type == "trigger_pulse"

    def test_flash_effect_type_is_lightbar_flash(self):
        """flash.effect_type == "lightbar_flash"."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        flash = get_effect("flash")
        assert flash.effect_type == "lightbar_flash"


class TestEffectsByType:
    """effects_by_type(effect_type) — filter effects by type."""

    def test_effects_by_type_rumble(self):
        """effects_by_type("rumble") includes kick."""
        from gamepad_midi_bridge.haptic_presets import effects_by_type

        rumble_effects = effects_by_type("rumble")
        assert len(rumble_effects) >= 1
        assert any(e.slug == "kick" for e in rumble_effects)

    def test_effects_by_type_trigger_click(self):
        """effects_by_type("trigger_click") includes snap, click, tick."""
        from gamepad_midi_bridge.haptic_presets import effects_by_type

        click_effects = effects_by_type("trigger_click")
        slugs = {e.slug for e in click_effects}
        assert {"snap", "click", "tick"}.issubset(slugs)

    def test_effects_by_type_nonexistent(self):
        """effects_by_type("nonexistent") returns empty list."""
        from gamepad_midi_bridge.haptic_presets import effects_by_type

        result = effects_by_type("nonexistent")
        assert result == []

    def test_effects_by_type_trigger_pulse(self):
        """effects_by_type("trigger_pulse") includes heartbeat and drum_roll."""
        from gamepad_midi_bridge.haptic_presets import effects_by_type

        pulse_effects = effects_by_type("trigger_pulse")
        slugs = {e.slug for e in pulse_effects}
        assert {"heartbeat", "drum_roll"}.issubset(slugs)


class TestPulseParameters:
    """Pulse count and gap validation."""

    def test_heartbeat_pulse_count_is_2(self):
        """heartbeat.pulse_count == 2."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        hb = get_effect("heartbeat")
        assert hb.pulse_count == 2

    def test_heartbeat_pulse_gap_ms_is_100(self):
        """heartbeat.pulse_gap_ms == 100."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        hb = get_effect("heartbeat")
        assert hb.pulse_gap_ms == 100

    def test_drum_roll_pulse_count_is_8(self):
        """drum_roll.pulse_count == 8."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        dr = get_effect("drum_roll")
        assert dr.pulse_count == 8

    def test_drum_roll_pulse_gap_ms_is_60(self):
        """drum_roll.pulse_gap_ms == 60."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        dr = get_effect("drum_roll")
        assert dr.pulse_gap_ms == 60


class TestIntensityClamping:
    """Intensity values are clamped to 0..1."""

    def test_haptic_effect_intensity_below_zero_clamped(self):
        """Negative intensity clamped to 0.0."""
        from gamepad_midi_bridge.haptic_presets import HapticEffect

        effect = HapticEffect(
            slug="test",
            display_name="Test",
            effect_type="rumble",
            intensity=-0.5,
        )
        assert effect.intensity == 0.0

    def test_haptic_effect_intensity_above_one_clamped(self):
        """Intensity > 1.0 clamped to 1.0."""
        from gamepad_midi_bridge.haptic_presets import HapticEffect

        effect = HapticEffect(
            slug="test",
            display_name="Test",
            effect_type="rumble",
            intensity=1.5,
        )
        assert effect.intensity == 1.0


class TestDurationClamping:
    """Duration values are clamped to 1..5000 ms."""

    def test_haptic_effect_duration_below_1_clamped(self):
        """duration_ms < 1 clamped to 1."""
        from gamepad_midi_bridge.haptic_presets import HapticEffect

        effect = HapticEffect(
            slug="test",
            display_name="Test",
            effect_type="rumble",
            duration_ms=0,
        )
        assert effect.duration_ms == 1

    def test_haptic_effect_duration_above_5000_clamped(self):
        """duration_ms > 5000 clamped to 5000."""
        from gamepad_midi_bridge.haptic_presets import HapticEffect

        effect = HapticEffect(
            slug="test",
            display_name="Test",
            effect_type="rumble",
            duration_ms=6000,
        )
        assert effect.duration_ms == 5000


class TestScaleEffect:
    """scale_effect(effect, factor) — scale intensity non-mutating."""

    def test_scale_effect_factor_2_doubles_intensity(self):
        """scale_effect(..., 2.0) doubles intensity (clamped at 1.0)."""
        from gamepad_midi_bridge.haptic_presets import get_effect, scale_effect

        kick = get_effect("kick")
        # kick.intensity == 0.9, scaled by 2.0 → 1.8, clamped to 1.0
        scaled = scale_effect(kick, 2.0)
        assert scaled.intensity == 1.0

    def test_scale_effect_factor_0_5_halves_intensity(self):
        """scale_effect(..., 0.5) halves intensity."""
        from gamepad_midi_bridge.haptic_presets import get_effect, scale_effect

        kick = get_effect("kick")
        # kick.intensity == 0.9, scaled by 0.5 → 0.45
        scaled = scale_effect(kick, 0.5)
        assert abs(scaled.intensity - 0.45) < 0.0001

    def test_scale_effect_returns_new_instance(self):
        """scale_effect() returns a new instance (non-mutating)."""
        from gamepad_midi_bridge.haptic_presets import get_effect, scale_effect

        kick = get_effect("kick")
        original_intensity = kick.intensity
        scaled = scale_effect(kick, 0.5)

        assert scaled is not kick
        assert kick.intensity == original_intensity
        assert scaled.intensity != original_intensity

    def test_scale_effect_factor_0_zero_intensity(self):
        """scale_effect(..., 0.0) zeroes intensity."""
        from gamepad_midi_bridge.haptic_presets import get_effect, scale_effect

        kick = get_effect("kick")
        scaled = scale_effect(kick, 0.0)
        assert scaled.intensity == 0.0

    def test_scale_effect_preserves_other_fields(self):
        """scale_effect() preserves slug, effect_type, duration_ms, etc."""
        from gamepad_midi_bridge.haptic_presets import get_effect, scale_effect

        kick = get_effect("kick")
        scaled = scale_effect(kick, 0.5)

        assert scaled.slug == kick.slug
        assert scaled.display_name == kick.display_name
        assert scaled.effect_type == kick.effect_type
        assert scaled.duration_ms == kick.duration_ms
        assert scaled.frequency_hz == kick.frequency_hz


class TestSerialization:
    """to_dict() / from_dict() round-trip serialization."""

    def test_haptic_effect_to_dict(self):
        """HapticEffect.to_dict() returns all fields."""
        from gamepad_midi_bridge.haptic_presets import HapticEffect

        effect = HapticEffect(
            slug="test",
            display_name="Test Effect",
            effect_type="rumble",
            intensity=0.7,
            duration_ms=150,
            pulse_count=3,
            pulse_gap_ms=75,
            frequency_hz=40.0,
            description="A test effect",
        )
        d = effect.to_dict()

        assert d["slug"] == "test"
        assert d["display_name"] == "Test Effect"
        assert d["effect_type"] == "rumble"
        assert d["intensity"] == 0.7
        assert d["duration_ms"] == 150
        assert d["pulse_count"] == 3
        assert d["pulse_gap_ms"] == 75
        assert d["frequency_hz"] == 40.0
        assert d["description"] == "A test effect"

    def test_haptic_effect_from_dict(self):
        """HapticEffect.from_dict() reconstructs effect from dict."""
        from gamepad_midi_bridge.haptic_presets import HapticEffect

        data = {
            "slug": "test",
            "display_name": "Test Effect",
            "effect_type": "trigger_click",
            "intensity": 0.6,
            "duration_ms": 50,
            "pulse_count": 1,
            "pulse_gap_ms": 50,
            "frequency_hz": 30.0,
            "description": "Reconstructed",
        }
        effect = HapticEffect.from_dict(data)

        assert effect.slug == "test"
        assert effect.display_name == "Test Effect"
        assert effect.effect_type == "trigger_click"
        assert effect.intensity == 0.6
        assert effect.duration_ms == 50
        assert effect.description == "Reconstructed"

    def test_haptic_effect_round_trip_serialization(self):
        """to_dict() -> from_dict() round-trip preserves all fields."""
        from gamepad_midi_bridge.haptic_presets import get_effect

        original = get_effect("heartbeat")
        d = original.to_dict()
        reconstructed = type(original).from_dict(d)

        assert reconstructed.slug == original.slug
        assert reconstructed.display_name == original.display_name
        assert reconstructed.effect_type == original.effect_type
        assert reconstructed.intensity == original.intensity
        assert reconstructed.duration_ms == original.duration_ms
        assert reconstructed.pulse_count == original.pulse_count
        assert reconstructed.pulse_gap_ms == original.pulse_gap_ms
        assert reconstructed.frequency_hz == original.frequency_hz
        assert reconstructed.description == original.description

    def test_haptic_effect_from_dict_missing_keys_use_defaults(self):
        """from_dict() with missing keys uses dataclass defaults."""
        from gamepad_midi_bridge.haptic_presets import HapticEffect

        data = {"slug": "minimal", "display_name": "Minimal"}
        effect = HapticEffect.from_dict(data)

        assert effect.slug == "minimal"
        assert effect.display_name == "Minimal"
        assert effect.effect_type == "rumble"  # default
        assert effect.intensity == 0.5  # default
        assert effect.duration_ms == 100  # default
