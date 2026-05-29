"""Per-channel MIDI mute and solo matrix tests."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.channel_mute import ChannelMute


class TestChannelMuteDefaults:
    """Test default state and initialization."""

    def test_default_all_unmuted(self):
        """Default: all channels unmuted."""
        cm = ChannelMute()
        assert all(not m for m in cm.muted_channels)
        assert len(cm.muted_channels) == 16

    def test_default_all_unsoloed(self):
        """Default: all channels unsoloed."""
        cm = ChannelMute()
        assert all(not s for s in cm.solo_channels)
        assert len(cm.solo_channels) == 16

    def test_default_is_muted_all_false(self):
        """Default: is_muted returns False for all valid channels."""
        cm = ChannelMute()
        for ch in range(1, 17):
            assert cm.is_muted(ch) is False

    def test_default_any_soloed_false(self):
        """Default: any_soloed returns False."""
        cm = ChannelMute()
        assert cm.any_soloed() is False


class TestMuteBasics:
    """Test mute setting and querying."""

    def test_set_mute_single_channel(self):
        """set_mute(1, True) mutes channel 1."""
        cm = ChannelMute()
        cm.set_mute(1, True)
        assert cm.is_muted(1) is True

    def test_is_muted_returns_false_for_unmuted_channels(self):
        """Only the muted channel returns True; others False."""
        cm = ChannelMute()
        cm.set_mute(1, True)
        assert cm.is_muted(1) is True
        assert cm.is_muted(2) is False
        assert cm.is_muted(3) is False

    def test_set_mute_multiple_channels(self):
        """Multiple channels can be muted independently."""
        cm = ChannelMute()
        cm.set_mute(1, True)
        cm.set_mute(8, True)
        cm.set_mute(16, True)
        assert cm.is_muted(1) is True
        assert cm.is_muted(2) is False
        assert cm.is_muted(8) is True
        assert cm.is_muted(9) is False
        assert cm.is_muted(16) is True

    def test_set_mute_false_unmutes(self):
        """set_mute(ch, False) unmutes a channel."""
        cm = ChannelMute()
        cm.set_mute(5, True)
        assert cm.is_muted(5) is True
        cm.set_mute(5, False)
        assert cm.is_muted(5) is False


class TestSoloBasics:
    """Test solo setting and querying."""

    def test_set_solo_single_channel(self):
        """set_solo(3, True) solos channel 3."""
        cm = ChannelMute()
        cm.set_solo(3, True)
        assert cm.any_soloed() is True

    def test_solo_mutes_non_soloed_channels(self):
        """When solo is active, non-soloed channels return is_muted=True."""
        cm = ChannelMute()
        cm.set_solo(3, True)
        assert cm.is_muted(1) is True
        assert cm.is_muted(2) is True
        assert cm.is_muted(3) is False  # soloed channel is audible
        assert cm.is_muted(4) is True

    def test_multiple_solos(self):
        """Multiple channels can be soloed; all others muted."""
        cm = ChannelMute()
        cm.set_solo(2, True)
        cm.set_solo(5, True)
        cm.set_solo(12, True)
        assert cm.is_muted(1) is True
        assert cm.is_muted(2) is False
        assert cm.is_muted(3) is True
        assert cm.is_muted(5) is False
        assert cm.is_muted(12) is False
        assert cm.is_muted(16) is True

    def test_set_solo_false_removes_solo(self):
        """set_solo(ch, False) removes solo from a channel."""
        cm = ChannelMute()
        cm.set_solo(7, True)
        assert cm.any_soloed() is True
        cm.set_solo(7, False)
        assert cm.any_soloed() is False
        assert cm.is_muted(7) is False  # back to unmuted since no solos remain


class TestMuteAndSolo:
    """Test interaction between mute and solo."""

    def test_mute_overrides_solo(self):
        """A channel that is both muted and soloed is silenced (mute wins)."""
        cm = ChannelMute()
        cm.set_solo(3, True)
        cm.set_mute(3, True)
        # Channel 3 is soloed, but also muted
        assert cm.is_muted(3) is True

    def test_mute_and_solo_other_channel(self):
        """Muting one channel while soloing another works as expected."""
        cm = ChannelMute()
        cm.set_solo(5, True)
        cm.set_mute(2, True)
        assert cm.is_muted(2) is True
        assert cm.is_muted(5) is False
        assert cm.is_muted(1) is True  # not soloed, so muted

    def test_unmute_overridden_by_solo(self):
        """An unmuted channel is still muted if other channels are soloed."""
        cm = ChannelMute()
        cm.set_solo(5, True)
        assert cm.is_muted(1) is True  # unmuted, but soloed status mutes it


class TestToggle:
    """Test toggle_mute and toggle_solo."""

    def test_toggle_mute_on(self):
        """toggle_mute returns new state and updates it."""
        cm = ChannelMute()
        result = cm.toggle_mute(4)
        assert result is True
        assert cm.is_muted(4) is True

    def test_toggle_mute_off(self):
        """toggle_mute(ch) when ch is muted returns False and unmutes."""
        cm = ChannelMute()
        cm.set_mute(4, True)
        result = cm.toggle_mute(4)
        assert result is False
        assert cm.is_muted(4) is False

    def test_toggle_mute_multiple_times(self):
        """Multiple toggles flip the state each time."""
        cm = ChannelMute()
        r1 = cm.toggle_mute(6)
        assert r1 is True
        r2 = cm.toggle_mute(6)
        assert r2 is False
        r3 = cm.toggle_mute(6)
        assert r3 is True

    def test_toggle_solo_on(self):
        """toggle_solo returns new state and updates it."""
        cm = ChannelMute()
        result = cm.toggle_solo(8)
        assert result is True
        assert cm.any_soloed() is True

    def test_toggle_solo_off(self):
        """toggle_solo(ch) when ch is soloed returns False and removes solo."""
        cm = ChannelMute()
        cm.set_solo(8, True)
        result = cm.toggle_solo(8)
        assert result is False
        assert cm.any_soloed() is False

    def test_toggle_solo_multiple_times(self):
        """Multiple toggles flip the solo state each time."""
        cm = ChannelMute()
        r1 = cm.toggle_solo(9)
        assert r1 is True
        r2 = cm.toggle_solo(9)
        assert r2 is False
        r3 = cm.toggle_solo(9)
        assert r3 is True


class TestClear:
    """Test clear_all_mutes and clear_all_solos."""

    def test_clear_all_mutes(self):
        """clear_all_mutes unmutes all channels."""
        cm = ChannelMute()
        cm.set_mute(1, True)
        cm.set_mute(5, True)
        cm.set_mute(16, True)
        cm.clear_all_mutes()
        for ch in range(1, 17):
            assert cm.is_muted(ch) is False

    def test_clear_all_solos(self):
        """clear_all_solos removes all solos."""
        cm = ChannelMute()
        cm.set_solo(2, True)
        cm.set_solo(8, True)
        cm.set_solo(15, True)
        cm.clear_all_solos()
        assert cm.any_soloed() is False
        for ch in range(1, 17):
            assert cm.is_muted(ch) is False

    def test_clear_mutes_with_solo_active(self):
        """Clearing mutes with solo active doesn't affect solo behavior."""
        cm = ChannelMute()
        cm.set_solo(5, True)
        cm.set_mute(3, True)
        cm.clear_all_mutes()
        # Channel 5 is soloed, so others are still muted by solo logic
        assert cm.is_muted(1) is True
        assert cm.is_muted(5) is False


class TestAnySoloed:
    """Test any_soloed detection."""

    def test_any_soloed_false_by_default(self):
        """any_soloed is False when no solos are set."""
        cm = ChannelMute()
        assert cm.any_soloed() is False

    def test_any_soloed_true_with_one_solo(self):
        """any_soloed is True when one channel is soloed."""
        cm = ChannelMute()
        cm.set_solo(7, True)
        assert cm.any_soloed() is True

    def test_any_soloed_true_with_multiple_solos(self):
        """any_soloed is True with multiple solos."""
        cm = ChannelMute()
        cm.set_solo(2, True)
        cm.set_solo(10, True)
        assert cm.any_soloed() is True

    def test_any_soloed_false_after_clearing(self):
        """any_soloed becomes False after clear_all_solos."""
        cm = ChannelMute()
        cm.set_solo(11, True)
        assert cm.any_soloed() is True
        cm.clear_all_solos()
        assert cm.any_soloed() is False


class TestChannelClamping:
    """Test out-of-range channel handling."""

    def test_set_mute_channel_zero_clamps_to_one(self):
        """set_mute(0, True) clamps to channel 1."""
        cm = ChannelMute()
        cm.set_mute(0, True)
        assert cm.is_muted(1) is True

    def test_set_mute_channel_17_clamps_to_16(self):
        """set_mute(17, True) clamps to channel 16."""
        cm = ChannelMute()
        cm.set_mute(17, True)
        assert cm.is_muted(16) is True

    def test_set_mute_large_channel_clamps(self):
        """set_mute with very large channel number clamps to 16."""
        cm = ChannelMute()
        cm.set_mute(1000, True)
        assert cm.is_muted(16) is True

    def test_set_mute_negative_channel_clamps(self):
        """set_mute with negative channel clamps to 1."""
        cm = ChannelMute()
        cm.set_mute(-5, True)
        assert cm.is_muted(1) is True

    def test_is_muted_channel_zero_returns_true(self):
        """is_muted(0) returns True (safety: invalid channel)."""
        cm = ChannelMute()
        assert cm.is_muted(0) is True

    def test_is_muted_channel_17_returns_true(self):
        """is_muted(17) returns True (safety: invalid channel)."""
        cm = ChannelMute()
        assert cm.is_muted(17) is True

    def test_is_muted_negative_channel_returns_true(self):
        """is_muted with negative channel returns True (safety)."""
        cm = ChannelMute()
        assert cm.is_muted(-1) is True

    def test_set_solo_out_of_range_clamps(self):
        """set_solo also clamps out-of-range channels."""
        cm = ChannelMute()
        cm.set_solo(25, True)
        assert cm.any_soloed() is True
        assert cm.is_muted(16) is False  # clamped to ch 16, which is soloed


class TestPostInitPadding:
    """Test __post_init__ padding and trimming."""

    def test_post_init_pads_short_muted_list(self):
        """Creating ChannelMute with short muted_channels pads to 16."""
        cm = ChannelMute(muted_channels=[True, False])
        assert len(cm.muted_channels) == 16
        assert cm.muted_channels[0] is True
        assert cm.muted_channels[1] is False
        assert all(not m for m in cm.muted_channels[2:])

    def test_post_init_pads_short_solo_list(self):
        """Creating ChannelMute with short solo_channels pads to 16."""
        cm = ChannelMute(solo_channels=[True, True, True])
        assert len(cm.solo_channels) == 16
        assert cm.solo_channels[0] is True
        assert all(not s for s in cm.solo_channels[3:])

    def test_post_init_trims_long_muted_list(self):
        """Creating ChannelMute with long muted_channels trims to 16."""
        long_list = [True] * 20
        cm = ChannelMute(muted_channels=long_list)
        assert len(cm.muted_channels) == 16

    def test_post_init_trims_long_solo_list(self):
        """Creating ChannelMute with long solo_channels trims to 16."""
        long_list = [False] * 30
        cm = ChannelMute(solo_channels=long_list)
        assert len(cm.solo_channels) == 16

    def test_post_init_empty_lists_padded(self):
        """Empty lists are padded to 16 all-False."""
        cm = ChannelMute(muted_channels=[], solo_channels=[])
        assert len(cm.muted_channels) == 16
        assert len(cm.solo_channels) == 16
        assert all(not m for m in cm.muted_channels)
        assert all(not s for s in cm.solo_channels)


class TestSerialization:
    """Test to_dict and from_dict round-tripping."""

    def test_to_dict_format(self):
        """to_dict returns a dict with muted_channels and solo_channels."""
        cm = ChannelMute()
        cm.set_mute(1, True)
        cm.set_solo(5, True)
        data = cm.to_dict()
        assert isinstance(data, dict)
        assert "muted_channels" in data
        assert "solo_channels" in data
        assert len(data["muted_channels"]) == 16
        assert len(data["solo_channels"]) == 16

    def test_from_dict_basic(self):
        """from_dict creates a new ChannelMute from dict."""
        data = {
            "muted_channels": [True, False] + [False] * 14,
            "solo_channels": [False] * 16,
        }
        cm = ChannelMute.from_dict(data)
        assert cm.is_muted(1) is True
        assert cm.is_muted(2) is False

    def test_round_trip(self):
        """to_dict -> from_dict preserves state."""
        cm1 = ChannelMute()
        cm1.set_mute(2, True)
        cm1.set_mute(7, True)
        cm1.set_solo(10, True)

        data = cm1.to_dict()
        cm2 = ChannelMute.from_dict(data)

        # Channel 10 is soloed, so all others (including 1) are muted by solo logic
        assert cm2.is_muted(1) is True
        assert cm2.is_muted(2) is True  # also muted explicitly, but solo logic also mutes it
        assert cm2.is_muted(7) is True  # also muted explicitly, but solo logic also mutes it
        assert cm2.is_muted(10) is False  # soloed channel is audible
        assert cm2.any_soloed() is True

    def test_from_dict_missing_keys_defaults_false(self):
        """from_dict with missing keys defaults to all-False."""
        data = {}
        cm = ChannelMute.from_dict(data)
        assert all(not m for m in cm.muted_channels)
        assert all(not s for s in cm.solo_channels)

    def test_from_dict_pads_short_lists(self):
        """from_dict pads short lists to 16."""
        data = {
            "muted_channels": [True, False, True],
            "solo_channels": [False],
        }
        cm = ChannelMute.from_dict(data)
        assert len(cm.muted_channels) == 16
        assert len(cm.solo_channels) == 16
        assert cm.muted_channels[0] is True
        assert cm.solo_channels[0] is False

    def test_from_dict_trims_long_lists(self):
        """from_dict trims long lists to 16."""
        data = {
            "muted_channels": [False] * 25,
            "solo_channels": [True] * 30,
        }
        cm = ChannelMute.from_dict(data)
        assert len(cm.muted_channels) == 16
        assert len(cm.solo_channels) == 16

    def test_from_dict_non_list_values_default(self):
        """from_dict handles non-list values gracefully."""
        data = {
            "muted_channels": "not a list",
            "solo_channels": 42,
        }
        cm = ChannelMute.from_dict(data)
        assert len(cm.muted_channels) == 16
        assert len(cm.solo_channels) == 16
        assert all(not m for m in cm.muted_channels)
