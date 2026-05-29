"""Tests for MIDI Learn parameter binding."""
import pytest
from gamepad_midi_bridge.midi_learn import (
    MidiLearnBinding,
    MidiLearnConfig,
    apply_learn_to_mapping,
    _scale_value,
)


class TestMidiLearnBinding:
    """Test MidiLearnBinding dataclass."""

    def test_binding_creation(self) -> None:
        """Create a valid binding."""
        binding = MidiLearnBinding(
            cc=71,
            channel=1,
            target_path="triggers.L2.cc_value_max",
            min_value=0.0,
            max_value=127.0,
        )
        assert binding.cc == 71
        assert binding.channel == 1
        assert binding.target_path == "triggers.L2.cc_value_max"
        assert binding.enabled is True

    def test_binding_clamps_cc(self) -> None:
        """CC is clamped to 0..127."""
        binding = MidiLearnBinding(
            cc=200, channel=1, target_path="test", min_value=0, max_value=1
        )
        assert binding.cc == 127

        binding2 = MidiLearnBinding(
            cc=-10, channel=1, target_path="test", min_value=0, max_value=1
        )
        assert binding2.cc == 0

    def test_binding_clamps_channel(self) -> None:
        """Channel is clamped to 1..16."""
        binding = MidiLearnBinding(
            cc=71, channel=20, target_path="test", min_value=0, max_value=1
        )
        assert binding.channel == 16

        binding2 = MidiLearnBinding(
            cc=71, channel=0, target_path="test", min_value=0, max_value=1
        )
        assert binding2.channel == 1


class TestMidiLearnConfig:
    """Test MidiLearnConfig round-trip."""

    def test_empty_config(self) -> None:
        """Empty config round-trips correctly."""
        cfg = MidiLearnConfig()
        assert cfg.bindings == []

        d = cfg.to_dict()
        assert d == {"bindings": []}

        cfg2 = MidiLearnConfig.from_dict(d)
        assert cfg2.bindings == []

    def test_config_with_bindings(self) -> None:
        """Config with bindings round-trips correctly."""
        cfg = MidiLearnConfig(
            bindings=[
                MidiLearnBinding(
                    cc=71,
                    channel=1,
                    target_path="triggers.L2.ceiling",
                    min_value=0.0,
                    max_value=127.0,
                ),
                MidiLearnBinding(
                    cc=74,
                    channel=2,
                    target_path="left_stick.curve_amount",
                    min_value=0.0,
                    max_value=1.0,
                    enabled=False,
                ),
            ]
        )

        d = cfg.to_dict()
        assert len(d["bindings"]) == 2
        assert d["bindings"][0]["cc"] == 71
        assert d["bindings"][0]["enabled"] is True
        assert d["bindings"][1]["enabled"] is False

        cfg2 = MidiLearnConfig.from_dict(d)
        assert len(cfg2.bindings) == 2
        assert cfg2.bindings[0].cc == 71
        assert cfg2.bindings[1].enabled is False

    def test_from_dict_missing(self) -> None:
        """from_dict(None) returns empty config."""
        cfg = MidiLearnConfig.from_dict(None)
        assert cfg.bindings == []

        cfg2 = MidiLearnConfig.from_dict({})
        assert cfg2.bindings == []

    def test_from_dict_malformed_entries(self) -> None:
        """Malformed binding entries are skipped."""
        data = {
            "bindings": [
                {
                    "cc": 71,
                    "channel": 1,
                    "target_path": "test",
                    "min_value": 0,
                    "max_value": 1,
                },
                "not a dict",  # Skip this
                None,  # Skip this too
                {
                    "cc": 74,
                    "channel": 1,
                    "target_path": "test2",
                    "min_value": 0,
                    "max_value": 1,
                },
            ]
        }
        cfg = MidiLearnConfig.from_dict(data)
        assert len(cfg.bindings) == 2
        assert cfg.bindings[0].cc == 71
        assert cfg.bindings[1].cc == 74

    def test_from_dict_clamps_values(self) -> None:
        """from_dict clamps CC and channel to valid ranges."""
        data = {
            "bindings": [
                {
                    "cc": 200,
                    "channel": -5,
                    "target_path": "test",
                    "min_value": 0,
                    "max_value": 1,
                }
            ]
        }
        cfg = MidiLearnConfig.from_dict(data)
        assert cfg.bindings[0].cc == 127
        assert cfg.bindings[0].channel == 1


class TestScaleValue:
    """Test CC value scaling."""

    def test_scale_min(self) -> None:
        """CC value 0 scales to min_value."""
        result = _scale_value(0, 10.0, 20.0)
        assert result == pytest.approx(10.0)

    def test_scale_max(self) -> None:
        """CC value 127 scales to max_value."""
        result = _scale_value(127, 10.0, 20.0)
        assert result == pytest.approx(20.0)

    def test_scale_mid(self) -> None:
        """CC value 64 scales to approximately mid-range."""
        result = _scale_value(64, 0.0, 1.0)
        assert result == pytest.approx(0.5, abs=0.01)

    def test_scale_inverted_range(self) -> None:
        """Works with inverted ranges (min > max)."""
        result = _scale_value(0, 1.0, 0.0)
        assert result == pytest.approx(1.0)

        result = _scale_value(127, 1.0, 0.0)
        assert result == pytest.approx(0.0)


class TestApplyLearnToMapping:
    """Test MIDI Learn application to mapping dicts."""

    def test_simple_dict_update(self) -> None:
        """Update a simple nested dict value."""
        mapping = {"triggers": {"L2": {"ceiling": 100}}}
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="triggers.L2.ceiling",
                min_value=0.0,
                max_value=127.0,
            )
        ]

        result = apply_learn_to_mapping(mapping, 71, 1, 64, bindings)

        # Original should be unchanged
        assert mapping["triggers"]["L2"]["ceiling"] == 100

        # Result should be updated
        assert result["triggers"]["L2"]["ceiling"] == pytest.approx(64.0, abs=0.1)

    def test_disabled_binding_skipped(self) -> None:
        """Disabled bindings are not applied."""
        mapping = {"triggers": {"L2": {"ceiling": 100}}}
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="triggers.L2.ceiling",
                min_value=0.0,
                max_value=127.0,
                enabled=False,
            )
        ]

        result = apply_learn_to_mapping(mapping, 71, 1, 64, bindings)

        # Value should be unchanged
        assert result["triggers"]["L2"]["ceiling"] == 100

    def test_cc_mismatch_skipped(self) -> None:
        """Bindings with non-matching CC are skipped."""
        mapping = {"triggers": {"L2": {"ceiling": 100}}}
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="triggers.L2.ceiling",
                min_value=0.0,
                max_value=127.0,
            )
        ]

        result = apply_learn_to_mapping(mapping, 72, 1, 64, bindings)

        # Value should be unchanged
        assert result["triggers"]["L2"]["ceiling"] == 100

    def test_channel_mismatch_skipped(self) -> None:
        """Bindings with non-matching channel are skipped."""
        mapping = {"triggers": {"L2": {"ceiling": 100}}}
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="triggers.L2.ceiling",
                min_value=0.0,
                max_value=127.0,
            )
        ]

        result = apply_learn_to_mapping(mapping, 71, 2, 64, bindings)

        # Value should be unchanged
        assert result["triggers"]["L2"]["ceiling"] == 100

    def test_missing_path_silent_noop(self) -> None:
        """Missing target path is a silent no-op."""
        mapping = {"triggers": {"L2": {"ceiling": 100}}}
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="triggers.R2.ceiling",  # Doesn't exist
                min_value=0.0,
                max_value=127.0,
            )
        ]

        result = apply_learn_to_mapping(mapping, 71, 1, 64, bindings)

        # No crash, original structure preserved
        assert "triggers" in result
        assert "L2" in result["triggers"]

    def test_multiple_bindings_applied_in_order(self) -> None:
        """Multiple bindings are applied in sequence."""
        mapping = {
            "triggers": {"L2": {"ceiling": 100}},
            "left_stick": {"curve_amount": 0.5},
        }
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="triggers.L2.ceiling",
                min_value=0.0,
                max_value=127.0,
            ),
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="left_stick.curve_amount",
                min_value=0.0,
                max_value=1.0,
            ),
        ]

        result = apply_learn_to_mapping(mapping, 71, 1, 64, bindings)

        # Both should be updated
        assert result["triggers"]["L2"]["ceiling"] == pytest.approx(64.0, abs=0.1)
        assert result["left_stick"]["curve_amount"] == pytest.approx(0.5, abs=0.01)

    def test_deeply_nested_path(self) -> None:
        """Walk deeply nested paths."""
        mapping = {"a": {"b": {"c": {"d": 10}}}}
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="a.b.c.d",
                min_value=0.0,
                max_value=100.0,
            )
        ]

        result = apply_learn_to_mapping(mapping, 71, 1, 127, bindings)

        assert result["a"]["b"]["c"]["d"] == pytest.approx(100.0)

    def test_original_dict_not_mutated(self) -> None:
        """Original mapping dict is not mutated."""
        original = {"triggers": {"L2": {"ceiling": 100}}}
        mapping = original.copy()
        bindings = [
            MidiLearnBinding(
                cc=71,
                channel=1,
                target_path="triggers.L2.ceiling",
                min_value=0.0,
                max_value=127.0,
            )
        ]

        result = apply_learn_to_mapping(mapping, 71, 1, 64, bindings)

        # Original should be completely unchanged
        assert mapping == original
        # Result should be different
        assert result != mapping

    def test_empty_bindings_list(self) -> None:
        """Empty bindings list returns unchanged dict."""
        mapping = {"triggers": {"L2": {"ceiling": 100}}}
        result = apply_learn_to_mapping(mapping, 71, 1, 64, [])
        assert result == mapping
        # But a different object
        assert result is not mapping

    def test_value_range_scaling(self) -> None:
        """CC values scale correctly across various ranges."""
        mapping = {"param": 0.5}

        # Test 0..1 range
        bindings = [
            MidiLearnBinding(
                cc=1, channel=1, target_path="param", min_value=0.0, max_value=1.0
            )
        ]
        result = apply_learn_to_mapping(mapping, 1, 1, 0, bindings)
        assert result["param"] == pytest.approx(0.0)

        # Test 0..127 range
        bindings = [
            MidiLearnBinding(
                cc=1, channel=1, target_path="param", min_value=0.0, max_value=127.0
            )
        ]
        result = apply_learn_to_mapping(mapping, 1, 1, 127, bindings)
        assert result["param"] == pytest.approx(127.0)

        # Test negative range
        bindings = [
            MidiLearnBinding(
                cc=1, channel=1, target_path="param", min_value=-1.0, max_value=1.0
            )
        ]
        result = apply_learn_to_mapping(mapping, 1, 1, 0, bindings)
        assert result["param"] == pytest.approx(-1.0)

        result = apply_learn_to_mapping(mapping, 1, 1, 127, bindings)
        assert result["param"] == pytest.approx(1.0)
