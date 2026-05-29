"""Tests for LFO bank manager."""

import pytest

from gamepad_midi_bridge.lfo_bank import (
    LfoBank,
    LfoBankConfig,
    LfoBankSlot,
)
from gamepad_midi_bridge.lfo_waveforms import LfoConfig


class TestLfoBankSlot:
    """Tests for LfoBankSlot dataclass."""

    def test_slot_defaults(self):
        """LfoBankSlot should have sensible defaults."""
        slot = LfoBankSlot()
        assert slot.name == ""
        assert slot.cc == 1
        assert slot.channel == 1
        assert slot.config_dict == {}

    def test_slot_cc_clamping(self):
        """CC value should be clamped to 0..127."""
        slot = LfoBankSlot(cc=200)
        assert slot.cc == 127

        slot = LfoBankSlot(cc=-5)
        assert slot.cc == 0

    def test_slot_channel_clamping(self):
        """Channel should be clamped to 1..16."""
        slot = LfoBankSlot(channel=20)
        assert slot.channel == 16

        slot = LfoBankSlot(channel=0)
        assert slot.channel == 1

    def test_slot_to_dict(self):
        """Slot should serialize to dict."""
        slot = LfoBankSlot(
            name="vibrato",
            cc=1,
            channel=1,
            config_dict={"enabled": True, "shape": "sine"},
        )
        d = slot.to_dict()
        assert d["name"] == "vibrato"
        assert d["cc"] == 1
        assert d["channel"] == 1
        assert d["config_dict"]["shape"] == "sine"

    def test_slot_from_dict(self):
        """Slot should deserialize from dict."""
        data = {
            "name": "filter",
            "cc": 74,
            "channel": 2,
            "config_dict": {"enabled": True, "shape": "triangle"},
        }
        slot = LfoBankSlot.from_dict(data)
        assert slot.name == "filter"
        assert slot.cc == 74
        assert slot.channel == 2
        assert slot.config_dict["shape"] == "triangle"

    def test_slot_from_dict_missing_keys(self):
        """LfoBankSlot.from_dict should use defaults for missing keys."""
        slot = LfoBankSlot.from_dict({})
        assert slot.name == ""
        assert slot.cc == 1
        assert slot.channel == 1


class TestLfoBankConfig:
    """Tests for LfoBankConfig dataclass."""

    def test_config_defaults(self):
        """LfoBankConfig should have sensible defaults."""
        cfg = LfoBankConfig()
        assert cfg.enabled is False
        assert cfg.slots == []
        assert cfg.shared_start is True
        assert cfg.max_slots == 8

    def test_config_max_slots_clamping(self):
        """max_slots should be clamped to 1..32."""
        cfg = LfoBankConfig(max_slots=50)
        assert cfg.max_slots == 32

        cfg = LfoBankConfig(max_slots=0)
        assert cfg.max_slots == 1

    def test_config_slots_truncation(self):
        """Slots list should be truncated to max_slots."""
        slots = [LfoBankSlot(name=f"slot_{i}") for i in range(10)]
        cfg = LfoBankConfig(slots=slots, max_slots=5)
        assert len(cfg.slots) == 5
        assert cfg.slots[0].name == "slot_0"
        assert cfg.slots[4].name == "slot_4"

    def test_config_to_dict(self):
        """Config should serialize to dict."""
        slot = LfoBankSlot(name="vibrato", cc=1)
        cfg = LfoBankConfig(enabled=True, slots=[slot], shared_start=False, max_slots=16)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert len(d["slots"]) == 1
        assert d["slots"][0]["name"] == "vibrato"
        assert d["shared_start"] is False
        assert d["max_slots"] == 16

    def test_config_from_dict(self):
        """Config should deserialize from dict."""
        data = {
            "enabled": True,
            "slots": [{"name": "vibrato", "cc": 1, "channel": 1, "config_dict": {}}],
            "shared_start": False,
            "max_slots": 16,
        }
        cfg = LfoBankConfig.from_dict(data)
        assert cfg.enabled is True
        assert len(cfg.slots) == 1
        assert cfg.slots[0].name == "vibrato"
        assert cfg.shared_start is False
        assert cfg.max_slots == 16

    def test_config_from_dict_missing_keys(self):
        """LfoBankConfig.from_dict should use defaults for missing keys."""
        cfg = LfoBankConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.slots == []
        assert cfg.shared_start is True


class TestLfoBank:
    """Tests for LfoBank class."""

    def test_bank_empty(self):
        """Empty bank should return no values."""
        cfg = LfoBankConfig(enabled=True)
        bank = LfoBank(cfg)
        values = bank.values(0.0)
        assert values == []

    def test_bank_single_lfo(self):
        """Bank with single sine LFO should produce output."""
        slot = LfoBankSlot(
            name="vibrato",
            cc=1,
            channel=1,
            config_dict={
                "enabled": True,
                "shape": "sine",
                "rate_hz": 2.0,
                "depth": 1.0,
            },
        )
        cfg = LfoBankConfig(enabled=True, slots=[slot])
        bank = LfoBank(cfg)
        bank.start(0.0)

        values = bank.values(0.25)
        assert len(values) == 1
        slot_idx, cc, channel, value = values[0]
        assert slot_idx == 0
        assert cc == 1
        assert channel == 1
        # At 2 Hz, after 0.25s, phase should be 0.5 (half cycle).
        # Sine at 0.5 should be 0.5.
        assert abs(value - 0.5) < 0.01

    def test_bank_two_lfo_different_rates(self):
        """Bank with two sine LFOs at different rates."""
        slots = [
            LfoBankSlot(
                name="vibrato",
                cc=1,
                channel=1,
                config_dict={
                    "enabled": True,
                    "shape": "sine",
                    "rate_hz": 2.0,
                    "depth": 1.0,
                },
            ),
            LfoBankSlot(
                name="filter",
                cc=74,
                channel=1,
                config_dict={
                    "enabled": True,
                    "shape": "sine",
                    "rate_hz": 0.5,
                    "depth": 1.0,
                },
            ),
        ]
        cfg = LfoBankConfig(enabled=True, slots=slots)
        bank = LfoBank(cfg)
        bank.start(0.0)

        values = bank.values(0.5)
        assert len(values) == 2

        # First slot: 2 Hz, 0.5s → phase=1.0 (full cycle) → sine(0)=0.5
        slot_idx, cc, channel, value = values[0]
        assert slot_idx == 0
        assert cc == 1
        assert abs(value - 0.5) < 0.01

        # Second slot: 0.5 Hz, 0.5s → phase=0.25 → sine(0.25)=1.0
        slot_idx, cc, channel, value = values[1]
        assert slot_idx == 1
        assert cc == 74
        assert abs(value - 1.0) < 0.01

    def test_bank_shared_start_true(self):
        """With shared_start=True, both LFOs should start at same time."""
        slots = [
            LfoBankSlot(
                name="lfo_1",
                cc=1,
                config_dict={
                    "enabled": True,
                    "shape": "sine",
                    "rate_hz": 1.0,
                    "depth": 1.0,
                },
            ),
            LfoBankSlot(
                name="lfo_2",
                cc=2,
                config_dict={
                    "enabled": True,
                    "shape": "sine",
                    "rate_hz": 1.0,
                    "depth": 1.0,
                },
            ),
        ]
        cfg = LfoBankConfig(enabled=True, slots=slots, shared_start=True)
        bank = LfoBank(cfg)
        bank.start(100.0)

        # After 0.5s from start, both should be in sync.
        values = bank.values(100.5)
        assert len(values) == 2
        _, _, _, value_1 = values[0]
        _, _, _, value_2 = values[1]
        # Both should be identical (same phase).
        assert abs(value_1 - value_2) < 0.001

    def test_bank_mixed_shapes(self):
        """Bank with different waveform shapes should produce distinct outputs."""
        slots = [
            LfoBankSlot(
                name="sine",
                cc=1,
                config_dict={
                    "enabled": True,
                    "shape": "sine",
                    "rate_hz": 1.0,
                    "depth": 1.0,
                },
            ),
            LfoBankSlot(
                name="square",
                cc=2,
                config_dict={
                    "enabled": True,
                    "shape": "square",
                    "rate_hz": 1.0,
                    "depth": 1.0,
                    "duty": 0.5,
                },
            ),
        ]
        cfg = LfoBankConfig(enabled=True, slots=slots)
        bank = LfoBank(cfg)
        bank.start(0.0)

        values = bank.values(0.1)  # phase = 0.1
        assert len(values) == 2

        _, _, _, sine_val = values[0]
        _, _, _, square_val = values[1]

        # At phase 0.1: sine should be different from square.
        # sine(0.1) ≈ 0.794
        # square(0.1, 0.5) = 1.0
        assert abs(sine_val - 0.794) < 0.01
        assert square_val == 1.0
        assert sine_val != square_val

    def test_bank_cc_messages(self):
        """cc_messages should generate valid MIDI CC messages."""
        slot = LfoBankSlot(
            name="vibrato",
            cc=1,
            channel=2,
            config_dict={
                "enabled": True,
                "shape": "sine",
                "rate_hz": 2.0,
                "depth": 1.0,
            },
        )
        cfg = LfoBankConfig(enabled=True, slots=[slot])
        bank = LfoBank(cfg)
        bank.start(0.0)

        messages = bank.cc_messages(0.25)
        assert len(messages) == 1

        status, cc, value_int = messages[0]
        # Status byte: 0xB0 (CC) + channel - 1 = 0xB0 + 1 = 0xB1
        assert status == 0xB1
        assert cc == 1
        # Value should be in 0..127.
        assert 0 <= value_int <= 127

    def test_bank_cc_messages_clamps_to_0_127(self):
        """cc_messages should clamp output to 0..127."""
        slot = LfoBankSlot(
            name="test",
            cc=1,
            channel=1,
            config_dict={
                "enabled": True,
                "shape": "sine",
                "rate_hz": 1.0,
                "depth": 2.0,  # Unusually high depth.
            },
        )
        cfg = LfoBankConfig(enabled=True, slots=[slot])
        bank = LfoBank(cfg)
        bank.start(0.0)

        # Test at several phases.
        for t in [0.0, 0.1, 0.25, 0.5]:
            messages = bank.cc_messages(t)
            assert len(messages) == 1
            status, cc, value_int = messages[0]
            assert 0 <= value_int <= 127, f"Value out of range at t={t}: {value_int}"

    def test_bank_reset(self):
        """reset should clear all LFO states."""
        slot = LfoBankSlot(
            name="test",
            cc=1,
            config_dict={
                "enabled": True,
                "shape": "sine",
                "rate_hz": 2.0,
                "depth": 1.0,
            },
        )
        cfg = LfoBankConfig(enabled=True, slots=[slot])
        bank = LfoBank(cfg)
        bank.start(0.0)

        # Get a value before reset.
        values_before = bank.values(0.1)
        assert len(values_before) == 1
        assert values_before[0][3] != 0.0

        # Reset and check again.
        bank.reset()
        values_after = bank.values(0.1)
        assert len(values_after) == 1
        assert values_after[0][3] == 0.0  # Should be 0 after reset.

    def test_bank_slot_count(self):
        """slot_count should return the number of active slots."""
        slots = [
            LfoBankSlot(name=f"slot_{i}", cc=i)
            for i in range(5)
        ]
        cfg = LfoBankConfig(enabled=True, slots=slots)
        bank = LfoBank(cfg)
        assert bank.slot_count() == 5

    def test_bank_max_slots_enforcement(self):
        """Bank should respect max_slots limit during construction."""
        slots = [
            LfoBankSlot(name=f"slot_{i}", cc=i)
            for i in range(50)
        ]
        cfg = LfoBankConfig(enabled=True, slots=slots, max_slots=32)
        bank = LfoBank(cfg)
        # Config truncates to max_slots during __post_init__.
        assert bank.slot_count() == 32

    def test_bank_sample_hold_deterministic(self):
        """sample_hold should be deterministic with seed."""
        slot1 = LfoBankSlot(
            name="sh_1",
            cc=1,
            config_dict={
                "enabled": True,
                "shape": "sample_hold",
                "rate_hz": 1.0,
                "depth": 1.0,
            },
        )
        cfg1 = LfoBankConfig(enabled=True, slots=[slot1])
        bank1 = LfoBank(cfg1)

        # Manually set seed on the state.
        bank1._states[0]._rng = __import__("random").Random(42)
        bank1.start(0.0)
        values1 = bank1.values(0.3)

        # Create second bank with same config and seed.
        slot2 = LfoBankSlot(
            name="sh_2",
            cc=1,
            config_dict={
                "enabled": True,
                "shape": "sample_hold",
                "rate_hz": 1.0,
                "depth": 1.0,
            },
        )
        cfg2 = LfoBankConfig(enabled=True, slots=[slot2])
        bank2 = LfoBank(cfg2)
        bank2._states[0]._rng = __import__("random").Random(42)
        bank2.start(0.0)
        values2 = bank2.values(0.3)

        # Both should produce same output.
        assert abs(values1[0][3] - values2[0][3]) < 0.001

    def test_bank_values_before_start(self):
        """values() before start should return near initial (0.0)."""
        slot = LfoBankSlot(
            name="test",
            cc=1,
            config_dict={
                "enabled": True,
                "shape": "sine",
                "rate_hz": 2.0,
                "depth": 1.0,
            },
        )
        cfg = LfoBankConfig(enabled=True, slots=[slot])
        bank = LfoBank(cfg)

        # Without calling start(), values should be 0.
        values = bank.values(0.0)
        assert len(values) == 1
        assert values[0][3] == 0.0

    def test_bank_disabled_slot(self):
        """Slot with disabled config should return 0."""
        slot = LfoBankSlot(
            name="disabled",
            cc=1,
            config_dict={
                "enabled": False,  # Disabled.
                "shape": "sine",
                "rate_hz": 2.0,
                "depth": 1.0,
            },
        )
        cfg = LfoBankConfig(enabled=True, slots=[slot])
        bank = LfoBank(cfg)
        bank.start(0.0)

        values = bank.values(0.5)
        assert len(values) == 1
        assert values[0][3] == 0.0

    def test_bank_channel_encoding_in_status_byte(self):
        """Status byte should correctly encode MIDI channel."""
        slots = [
            LfoBankSlot(name="ch1", cc=1, channel=1),
            LfoBankSlot(name="ch5", cc=2, channel=5),
            LfoBankSlot(name="ch16", cc=3, channel=16),
        ]
        for slot in slots:
            slot.config_dict = {
                "enabled": True,
                "shape": "sine",
                "rate_hz": 1.0,
                "depth": 1.0,
            }

        cfg = LfoBankConfig(enabled=True, slots=slots)
        bank = LfoBank(cfg)
        bank.start(0.0)

        messages = bank.cc_messages(0.1)
        assert len(messages) == 3

        # Channel 1: status = 0xB0 + 0 = 0xB0
        assert messages[0][0] == 0xB0
        # Channel 5: status = 0xB0 + 4 = 0xB4
        assert messages[1][0] == 0xB4
        # Channel 16: status = 0xB0 + 15 = 0xBF
        assert messages[2][0] == 0xBF

    def test_bank_round_trip_serialization(self):
        """Bank config should round-trip through dict."""
        slots = [
            LfoBankSlot(
                name="vibrato",
                cc=1,
                channel=1,
                config_dict={
                    "enabled": True,
                    "shape": "sine",
                    "rate_hz": 2.0,
                    "depth": 1.0,
                },
            ),
            LfoBankSlot(
                name="filter",
                cc=74,
                channel=2,
                config_dict={
                    "enabled": True,
                    "shape": "triangle",
                    "rate_hz": 0.5,
                    "depth": 0.8,
                },
            ),
        ]
        cfg1 = LfoBankConfig(enabled=True, slots=slots, shared_start=False, max_slots=16)

        # Serialize.
        d = cfg1.to_dict()

        # Deserialize.
        cfg2 = LfoBankConfig.from_dict(d)

        # Check equality.
        assert cfg2.enabled == cfg1.enabled
        assert cfg2.shared_start == cfg1.shared_start
        assert cfg2.max_slots == cfg1.max_slots
        assert len(cfg2.slots) == len(cfg1.slots)
        assert cfg2.slots[0].name == cfg1.slots[0].name
        assert cfg2.slots[1].name == cfg1.slots[1].name
        assert cfg2.slots[0].config_dict["shape"] == "sine"
        assert cfg2.slots[1].config_dict["shape"] == "triangle"
