"""Tests for trigger_haptic_profiles module."""
import pytest
from gamepad_midi_bridge import trigger_haptic_profiles as thp


class TestListProfiles:
    """Test profile listing and lookup."""

    def test_list_profiles_returns_eight(self):
        """list_profiles() should return exactly 8 builtin profiles."""
        profiles = thp.list_profiles()
        assert len(profiles) == 8

    def test_all_slugs_unique(self):
        """All profile slugs should be unique."""
        profiles = thp.list_profiles()
        slugs = [p.slug for p in profiles]
        assert len(slugs) == len(set(slugs))

    def test_expected_slugs_present(self):
        """All expected profile slugs should be present."""
        profiles = thp.list_profiles()
        slugs = {p.slug for p in profiles}
        expected = {"off", "light_resistance", "heavy_resistance", "two_stage",
                    "gradual", "weapon", "springy", "mountain"}
        assert slugs == expected


class TestGetProfile:
    """Test profile lookup by slug."""

    def test_get_profile_off(self):
        """get_profile('off') should return the off profile."""
        profile = thp.get_profile("off")
        assert profile is not None
        assert profile.slug == "off"
        assert profile.display_name == "Off"
        assert profile.force_levels == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def test_get_profile_gradual(self):
        """get_profile('gradual') should return the gradual profile."""
        profile = thp.get_profile("gradual")
        assert profile is not None
        assert profile.slug == "gradual"
        assert profile.display_name == "Gradual"

    def test_get_profile_nonexistent(self):
        """get_profile('nonexistent') should return None."""
        profile = thp.get_profile("nonexistent")
        assert profile is None


class TestProfileStructure:
    """Test profile structure and constraints."""

    def test_each_profile_has_exactly_ten_force_levels(self):
        """Each profile must have exactly 10 force_levels."""
        profiles = thp.list_profiles()
        for profile in profiles:
            assert len(profile.force_levels) == 10

    def test_all_force_levels_in_range(self):
        """All force_levels values must be in 0..255."""
        profiles = thp.list_profiles()
        for profile in profiles:
            for force in profile.force_levels:
                assert 0 <= force <= 255


class TestInterpolation:
    """Test force interpolation at different positions."""

    def test_interpolate_at_position_zero(self):
        """interpolate_profile at position 0 should return first force level."""
        profile = thp.get_profile("gradual")
        assert profile is not None
        force = thp.interpolate_profile(profile, 0.0)
        assert force == profile.force_levels[0]  # 20

    def test_interpolate_at_position_one(self):
        """interpolate_profile at position 1 should return last force level."""
        profile = thp.get_profile("gradual")
        assert profile is not None
        force = thp.interpolate_profile(profile, 1.0)
        assert force == profile.force_levels[9]  # 250

    def test_interpolate_at_position_halfway(self):
        """interpolate_profile at position 0.5 should return mid-array interpolation."""
        profile = thp.get_profile("gradual")
        assert profile is not None
        force = thp.interpolate_profile(profile, 0.5)
        # At position 0.5, we're mapping to index 4.5, which is between indices 4 and 5.
        # Index 4 = 130, Index 5 = 160. Midpoint = 145.
        assert 140 <= force <= 160

    def test_interpolate_clamps_negative_position(self):
        """interpolate_profile should clamp negative positions to 0."""
        profile = thp.get_profile("gradual")
        assert profile is not None
        force_neg = thp.interpolate_profile(profile, -0.5)
        force_zero = thp.interpolate_profile(profile, 0.0)
        assert force_neg == force_zero

    def test_interpolate_clamps_over_one_position(self):
        """interpolate_profile should clamp positions > 1 to 1."""
        profile = thp.get_profile("gradual")
        assert profile is not None
        force_over = thp.interpolate_profile(profile, 1.5)
        force_one = thp.interpolate_profile(profile, 1.0)
        assert force_over == force_one


class TestBuildCustom:
    """Test custom profile builder."""

    def test_build_custom_short_list_pads_with_zeros(self):
        """build_custom should pad short lists to 10 with zeros."""
        profile = thp.build_custom("test", "Test", [100, 100])
        assert len(profile.force_levels) == 10
        assert profile.force_levels[0] == 100
        assert profile.force_levels[1] == 100
        assert profile.force_levels[2:] == [0] * 8

    def test_build_custom_long_list_truncates_to_ten(self):
        """build_custom should truncate long lists to 10."""
        long_list = list(range(20))
        profile = thp.build_custom("test", "Test", long_list)
        assert len(profile.force_levels) == 10
        assert profile.force_levels == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    def test_build_custom_clamps_force_values(self):
        """build_custom should clamp force values to 0..255."""
        profile = thp.build_custom("test", "Test", [-50, 300, 200] + [100] * 7)
        assert profile.force_levels[0] == 0  # -50 clamped to 0
        assert profile.force_levels[1] == 255  # 300 clamped to 255
        assert profile.force_levels[2] == 200

    def test_build_custom_with_mode_hint(self):
        """build_custom should accept mode_hint."""
        profile = thp.build_custom(
            "test", "Test", [100] * 10, mode_hint="vibration"
        )
        assert profile.mode_hint == "vibration"


class TestInvertProfile:
    """Test profile inversion."""

    def test_invert_profile_reverses_force_levels(self):
        """invert_profile should reverse force_levels."""
        original = thp.get_profile("gradual")
        assert original is not None
        inverted = thp.invert_profile(original)
        assert inverted.force_levels == list(reversed(original.force_levels))

    def test_invert_profile_updates_slug(self):
        """invert_profile should append '_inverted' to slug."""
        original = thp.get_profile("gradual")
        assert original is not None
        inverted = thp.invert_profile(original)
        assert inverted.slug == "gradual_inverted"

    def test_invert_profile_updates_display_name(self):
        """invert_profile should append '(Inverted)' to display_name."""
        original = thp.get_profile("gradual")
        assert original is not None
        inverted = thp.invert_profile(original)
        assert "(Inverted)" in inverted.display_name

    def test_invert_twice_recovers_original_force_levels(self):
        """Inverting twice should recover original force levels."""
        original = thp.get_profile("weapon")
        assert original is not None
        inverted_once = thp.invert_profile(original)
        inverted_twice = thp.invert_profile(inverted_once)
        assert inverted_twice.force_levels == original.force_levels


class TestProfilesByMode:
    """Test filtering profiles by mode hint."""

    def test_profiles_by_mode_constant(self):
        """profiles_by_mode('constant') should return at least off, light_resistance, heavy_resistance."""
        profiles = thp.profiles_by_mode("constant")
        slugs = {p.slug for p in profiles}
        assert "off" in slugs
        assert "light_resistance" in slugs
        assert "heavy_resistance" in slugs

    def test_profiles_by_mode_two_stage(self):
        """profiles_by_mode('two_stage') should return at least one profile."""
        profiles = thp.profiles_by_mode("two_stage")
        assert len(profiles) >= 1
        assert profiles[0].slug == "two_stage"

    def test_profiles_by_mode_unknown(self):
        """profiles_by_mode('unknown') should return empty list."""
        profiles = thp.profiles_by_mode("unknown")
        assert profiles == []

    def test_profiles_by_mode_gradual(self):
        """profiles_by_mode('gradual') should return the gradual profile."""
        profiles = thp.profiles_by_mode("gradual")
        assert len(profiles) >= 1
        assert any(p.slug == "gradual" for p in profiles)


class TestSerialization:
    """Test to_dict() and from_dict() round-trip."""

    def test_serialization_round_trip(self):
        """TriggerHapticProfile should round-trip through to_dict() and from_dict()."""
        original = thp.get_profile("springy")
        assert original is not None
        data = original.to_dict()
        restored = thp.TriggerHapticProfile.from_dict(data)
        assert restored.slug == original.slug
        assert restored.display_name == original.display_name
        assert restored.force_levels == original.force_levels
        assert restored.mode_hint == original.mode_hint
        assert restored.description == original.description

    def test_serialization_of_custom_profile(self):
        """Custom profiles should serialize and deserialize correctly."""
        custom = thp.build_custom("custom", "Custom Profile", [50, 100, 150, 200, 200, 150, 100, 50, 25, 10])
        data = custom.to_dict()
        restored = thp.TriggerHapticProfile.from_dict(data)
        assert restored.slug == custom.slug
        assert restored.force_levels == custom.force_levels

    def test_serialization_with_missing_keys(self):
        """from_dict() should handle missing keys with defaults."""
        partial_data = {"slug": "test", "display_name": "Test"}
        profile = thp.TriggerHapticProfile.from_dict(partial_data)
        assert profile.slug == "test"
        assert profile.display_name == "Test"
        assert profile.force_levels == [0] * 10
        assert profile.mode_hint == "constant"
        assert profile.description == ""
