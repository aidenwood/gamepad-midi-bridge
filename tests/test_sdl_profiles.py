"""Per-device index remapping.

`pygame.joystick` returns raw HID indices, not SDL GameController ones, so
SDL's mapping database never gets applied and the numbers differ per pad.

Confirmed on hardware 2026-10-22: an Xbox Wireless Controller (045e:0b12)
over USB puts its LEFT TRIGGER on axis 2 — the axis this app draws as
right-stick X. Reported as "L2 seems to be moving the right stick".
"""
from __future__ import annotations

from gamepad_midi_bridge import sdl_profiles as sp

# Real GUIDs. Bytes are little-endian 16-bit fields: bus, _, vid, _, pid.
XBOX_0B12_USB = "030000005e040000120b000000000000"
XBOX_0B20_BT = "030000005e040000200b000011050000"
XBOX_WIRED_D102 = "030000005e040000d102000000000000"
DUALSENSE_USB = "030000004c050000e60c000000006800"
UNKNOWN_PAD = "03000000de080000e002000000000000"


class TestXboxRemap:

    def test_left_trigger_is_axis_2_on_the_confirmed_pad(self):
        """The reported symptom, as a test."""
        axes, _buttons, _dpad = sp.profile_for(XBOX_0B12_USB, 1, 15)
        assert axes[4] == 2, "canonical L2 must read device axis 2"

    def test_right_stick_moves_off_axis_2(self):
        axes, _b, _d = sp.profile_for(XBOX_0B12_USB, 1, 15)
        assert axes[2] == 3   # RX
        assert axes[3] == 4   # RY
        assert axes[2] != 2, "right-stick X must no longer collide with L2"

    def test_sticks_and_right_trigger_are_unchanged(self):
        axes, _b, _d = sp.profile_for(XBOX_0B12_USB, 1, 15)
        assert axes[0] == 0 and axes[1] == 1
        assert axes[5] == 5

    def test_every_canonical_axis_maps_somewhere_unique(self):
        """A duplicate target would make two controls move as one."""
        for guid in (XBOX_0B12_USB, XBOX_0B20_BT, XBOX_WIRED_D102):
            axes, _b, _d = sp.profile_for(guid, 1, 15)
            assert sorted(axes) == [0, 1, 2, 3, 4, 5]
            assert len(set(axes.values())) == 6, guid

    def test_the_0b20_bluetooth_variant_has_swapped_triggers(self):
        """SDL's own entry for this one is lefttrigger:a5, righttrigger:a4."""
        axes, _b, _d = sp.profile_for(XBOX_0B20_BT, 1, 15)
        assert axes[4] == 5
        assert axes[5] == 4

    def test_the_0b20_variant_shifts_the_face_buttons(self):
        _a, buttons, _d = sp.profile_for(XBOX_0B20_BT, 1, 15)
        assert buttons[2] == 3   # X
        assert buttons[3] == 4   # Y

    def test_hatless_xbox_pads_get_dpad_buttons(self):
        """Otherwise the d-pad is silently dead on those devices."""
        _a, _b, dpad = sp.profile_for(XBOX_WIRED_D102, 0, 15)
        assert dpad == (11, 12, 13, 14)

    def test_unlisted_microsoft_pad_still_gets_the_axis_shuffle(self):
        unlisted = "030000005e040000ff0f000000000000"
        axes, _b, _d = sp.profile_for(unlisted, 1, 15)
        assert axes[4] == 2


class TestNonXboxIsLeftAlone:

    def test_dualsense_is_identity(self):
        """The defaults were written against the DualSense. Changing it
        without hardware confirmation is the mistake this module exists to
        stop repeating."""
        axes, buttons, dpad = sp.profile_for(DUALSENSE_USB, 1, 13)
        assert axes == sp.IDENTITY_AXES
        assert buttons == sp.IDENTITY_BUTTONS
        assert dpad is None

    def test_unknown_vendor_is_identity(self):
        axes, buttons, dpad = sp.profile_for(UNKNOWN_PAD, 1, 12)
        assert axes == sp.IDENTITY_AXES
        assert buttons == sp.IDENTITY_BUTTONS
        assert dpad is None

    def test_missing_guid_is_identity_not_a_crash(self):
        for guid in (None, "", "garbage"):
            axes, buttons, dpad = sp.profile_for(guid, 0, 0)
            assert axes == sp.IDENTITY_AXES
            assert buttons == sp.IDENTITY_BUTTONS
            assert dpad is None
