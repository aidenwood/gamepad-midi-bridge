"""Tests for groove_template module.

Tests cover:
  - Built-in groove templates (names, offsets, descriptions)
  - Template retrieval and fallback
  - Groove application with various intensities
  - Grid index wrapping
  - Intensity clamping
  - Custom template building (padding, truncation, clamping)
  - Serialization round-trips
"""

import pytest

from gamepad_midi_bridge import groove_template as gt


class TestListGrooveNames:
    """Tests for list_groove_names()."""

    def test_returns_six_names(self):
        """list_groove_names() returns exactly 6 builtin names."""
        names = gt.list_groove_names()
        assert len(names) == 6

    def test_names_are_sorted(self):
        """Names are returned in sorted order."""
        names = gt.list_groove_names()
        assert names == sorted(names)

    def test_contains_expected_names(self):
        """Expected groove names are present."""
        names = gt.list_groove_names()
        expected = {"straight", "swing_light", "swing_heavy", "shuffle", "drag", "push"}
        assert set(names) == expected


class TestGetTemplate:
    """Tests for get_template()."""

    def test_get_straight(self):
        """get_template('straight') returns straight with all zeros."""
        gt_straight = gt.get_template("straight")
        assert gt_straight.name == "straight"
        assert all(offset == 0 for offset in gt_straight.offsets_ms)
        assert len(gt_straight.offsets_ms) == 16

    def test_get_swing_light(self):
        """get_template('swing_light') returns swing_light with proper offsets."""
        gt_swing = gt.get_template("swing_light")
        assert gt_swing.name == "swing_light"
        # Odd indices (1, 3, 5, ...) should be 15, even should be 0
        for i in range(16):
            if i % 2 == 1:
                assert gt_swing.offsets_ms[i] == 15
            else:
                assert gt_swing.offsets_ms[i] == 0

    def test_get_swing_heavy(self):
        """get_template('swing_heavy') returns heavy swing with 40ms offsets."""
        gt_heavy = gt.get_template("swing_heavy")
        assert gt_heavy.name == "swing_heavy"
        for i in range(16):
            if i % 2 == 1:
                assert gt_heavy.offsets_ms[i] == 40
            else:
                assert gt_heavy.offsets_ms[i] == 0

    def test_get_nonexistent_returns_straight(self):
        """get_template() with unknown name returns straight."""
        gt_fallback = gt.get_template("nonexistent")
        assert gt_fallback.name == "straight"
        assert all(offset == 0 for offset in gt_fallback.offsets_ms)


class TestApplyGroove:
    """Tests for apply_groove()."""

    def test_straight_unchanged(self):
        """apply_groove with 'straight' returns input unchanged."""
        cfg = gt.GrooveConfig(enabled=True, template_name="straight", intensity=1.0)
        result = gt.apply_groove(1.0, 0, cfg)
        assert result == 1.0

    def test_swing_light_odd_index(self):
        """apply_groove with swing_light at odd index shifts forward 15ms."""
        cfg = gt.GrooveConfig(enabled=True, template_name="swing_light", intensity=1.0)
        result = gt.apply_groove(1.0, 1, cfg)
        assert result == pytest.approx(1.015)

    def test_swing_light_even_index(self):
        """apply_groove with swing_light at even index unchanged."""
        cfg = gt.GrooveConfig(enabled=True, template_name="swing_light", intensity=1.0)
        result = gt.apply_groove(1.0, 0, cfg)
        assert result == 1.0

    def test_drag_pulls_back(self):
        """apply_groove with drag pulls all times back 8ms."""
        cfg = gt.GrooveConfig(enabled=True, template_name="drag", intensity=1.0)
        result = gt.apply_groove(1.0, 0, cfg)
        assert result == pytest.approx(0.992)

    def test_push_nudges_forward(self):
        """apply_groove with push nudges all times forward 6ms."""
        cfg = gt.GrooveConfig(enabled=True, template_name="push", intensity=1.0)
        result = gt.apply_groove(1.0, 0, cfg)
        assert result == pytest.approx(1.006)

    def test_intensity_0_5_halves_offset(self):
        """apply_groove with intensity 0.5 halves the offset."""
        cfg = gt.GrooveConfig(enabled=True, template_name="swing_light", intensity=0.5)
        result = gt.apply_groove(1.0, 1, cfg)
        # 15ms * 0.5 = 7.5ms = 0.0075s
        assert result == pytest.approx(1.0075)

    def test_intensity_2_doubles_offset(self):
        """apply_groove with intensity 2.0 doubles the offset."""
        cfg = gt.GrooveConfig(enabled=True, template_name="swing_light", intensity=2.0)
        result = gt.apply_groove(1.0, 1, cfg)
        # 15ms * 2 = 30ms = 0.03s
        assert result == pytest.approx(1.03)

    def test_grid_index_wraps(self):
        """apply_groove wraps grid_index modulo template length."""
        cfg = gt.GrooveConfig(enabled=True, template_name="swing_light", intensity=1.0)
        # Index 17 wraps to 1 (odd, so 15ms shift)
        result = gt.apply_groove(1.0, 17, cfg)
        assert result == pytest.approx(1.015)
        # Index 16 wraps to 0 (even, so no shift)
        result = gt.apply_groove(1.0, 16, cfg)
        assert result == 1.0

    def test_disabled_returns_unchanged(self):
        """apply_groove with enabled=False returns input unchanged."""
        cfg = gt.GrooveConfig(enabled=False, template_name="swing_light", intensity=1.0)
        result = gt.apply_groove(1.0, 1, cfg)
        assert result == 1.0


class TestGrooveConfigClamping:
    """Tests for GrooveConfig intensity clamping."""

    def test_clamp_intensity_lower(self):
        """GrooveConfig clamps intensity < 0 to 0."""
        cfg = gt.GrooveConfig(intensity=-1.0)
        assert cfg.intensity == 0.0

    def test_clamp_intensity_upper(self):
        """GrooveConfig clamps intensity > 2 to 2."""
        cfg = gt.GrooveConfig(intensity=3.0)
        assert cfg.intensity == 2.0

    def test_clamp_unknown_template(self):
        """GrooveConfig defaults unknown template to 'straight'."""
        cfg = gt.GrooveConfig(template_name="nonexistent")
        assert cfg.template_name == "straight"


class TestBuildCustom:
    """Tests for build_custom()."""

    def test_pads_short_pattern(self):
        """build_custom pads short pattern to 16 entries with zeros."""
        gt_custom = gt.build_custom("short", [0, 20, 0, 20])
        assert len(gt_custom.offsets_ms) == 16
        assert gt_custom.offsets_ms[0:4] == [0, 20, 0, 20]
        assert all(offset == 0 for offset in gt_custom.offsets_ms[4:])

    def test_truncates_long_pattern(self):
        """build_custom truncates long pattern to 16 entries."""
        long_pattern = list(range(20))
        gt_custom = gt.build_custom("long", long_pattern)
        assert len(gt_custom.offsets_ms) == 16
        assert gt_custom.offsets_ms == list(range(16))

    def test_clamps_offsets_upper(self):
        """build_custom clamps positive offsets to +200ms."""
        gt_custom = gt.build_custom("big", [300, 250, 200, 100])
        assert gt_custom.offsets_ms[0] == 200
        assert gt_custom.offsets_ms[1] == 200
        assert gt_custom.offsets_ms[2] == 200
        assert gt_custom.offsets_ms[3] == 100

    def test_clamps_offsets_lower(self):
        """build_custom clamps negative offsets to -200ms."""
        gt_custom = gt.build_custom("negative", [-300, -250, -200, -100])
        assert gt_custom.offsets_ms[0] == -200
        assert gt_custom.offsets_ms[1] == -200
        assert gt_custom.offsets_ms[2] == -200
        assert gt_custom.offsets_ms[3] == -100

    def test_preserves_name_and_description(self):
        """build_custom preserves name and description."""
        gt_custom = gt.build_custom("my_groove", [0, 10], "My custom groove")
        assert gt_custom.name == "my_groove"
        assert gt_custom.description == "My custom groove"


class TestSerialization:
    """Tests for to_dict() and from_dict() round-trips."""

    def test_groove_template_roundtrip(self):
        """GrooveTemplate serialization round-trips correctly."""
        original = gt.GrooveTemplate(
            name="test",
            offsets_ms=[0, 15, 0, 15, 0, 15, 0, 15, 0, 15, 0, 15, 0, 15, 0, 15],
            description="Test groove",
        )
        data = original.to_dict()
        restored = gt.GrooveTemplate.from_dict(data)
        assert restored.name == original.name
        assert restored.offsets_ms == original.offsets_ms
        assert restored.description == original.description

    def test_groove_config_roundtrip(self):
        """GrooveConfig serialization round-trips correctly."""
        original = gt.GrooveConfig(
            enabled=True, template_name="swing_light", intensity=0.8
        )
        data = original.to_dict()
        restored = gt.GrooveConfig.from_dict(data)
        assert restored.enabled == original.enabled
        assert restored.template_name == original.template_name
        assert restored.intensity == pytest.approx(original.intensity)

    def test_groove_config_from_dict_invalid_template(self):
        """GrooveConfig.from_dict defaults invalid template to 'straight'."""
        data = {
            "enabled": True,
            "template_name": "nonexistent",
            "intensity": 1.0,
        }
        cfg = gt.GrooveConfig.from_dict(data)
        assert cfg.template_name == "straight"

    def test_groove_config_from_dict_clamps_intensity(self):
        """GrooveConfig.from_dict clamps intensity to valid range."""
        data = {"enabled": True, "template_name": "straight", "intensity": 5.0}
        cfg = gt.GrooveConfig.from_dict(data)
        assert cfg.intensity == 2.0


class TestBuiltinGrooves:
    """Tests for all built-in groove templates."""

    def test_straight_has_16_zeros(self):
        """straight groove has 16 zero offsets."""
        g = gt.BUILTIN_GROOVES["straight"]
        assert len(g.offsets_ms) == 16
        assert all(o == 0 for o in g.offsets_ms)

    def test_shuffle_has_alternating_pattern(self):
        """shuffle groove alternates 0 and 30."""
        g = gt.BUILTIN_GROOVES["shuffle"]
        assert len(g.offsets_ms) == 16
        for i in range(16):
            if i % 2 == 0:
                assert g.offsets_ms[i] == 0
            else:
                assert g.offsets_ms[i] == 30

    def test_drag_has_all_minus_8(self):
        """drag groove has all entries = -8ms."""
        g = gt.BUILTIN_GROOVES["drag"]
        assert len(g.offsets_ms) == 16
        assert all(o == -8 for o in g.offsets_ms)

    def test_push_has_all_plus_6(self):
        """push groove has all entries = +6ms."""
        g = gt.BUILTIN_GROOVES["push"]
        assert len(g.offsets_ms) == 16
        assert all(o == 6 for o in g.offsets_ms)

    def test_all_grooves_have_descriptions(self):
        """All built-in grooves have non-empty descriptions."""
        for name, groove in gt.BUILTIN_GROOVES.items():
            assert groove.description, f"Groove '{name}' missing description"

    def test_all_grooves_have_16_offsets(self):
        """All built-in grooves have exactly 16 offset entries."""
        for name, groove in gt.BUILTIN_GROOVES.items():
            assert len(groove.offsets_ms) == 16, f"Groove '{name}' has {len(groove.offsets_ms)} entries, expected 16"
