"""Note hold stack — build chords one note at a time. Pure stdlib, no Qt."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_hold_stack import NoteHoldStackConfig, NoteHoldStack


class TestNoteHoldStackConfig:
    """NoteHoldStackConfig dataclass — serialization and clamping."""

    def test_defaults(self):
        """Default config is disabled with sensible defaults."""
        cfg = NoteHoldStackConfig()
        assert cfg.enabled is False
        assert cfg.mode == "add"
        assert cfg.max_notes == 16
        assert cfg.auto_release_on_overflow is True

    def test_to_dict_round_trip(self):
        """to_dict and from_dict preserve config."""
        cfg = NoteHoldStackConfig(
            enabled=True,
            mode="additive",
            max_notes=8,
            auto_release_on_overflow=False,
        )
        data = cfg.to_dict()
        cfg2 = NoteHoldStackConfig.from_dict(data)
        assert cfg2 == cfg

    def test_max_notes_clamped_1_to_32(self):
        """max_notes is clamped to 1..32."""
        cfg1 = NoteHoldStackConfig.from_dict({"max_notes": -5})
        assert cfg1.max_notes == 1

        cfg2 = NoteHoldStackConfig.from_dict({"max_notes": 50})
        assert cfg2.max_notes == 32

        cfg3 = NoteHoldStackConfig.from_dict({"max_notes": 16})
        assert cfg3.max_notes == 16

    def test_unknown_mode_defaults_to_add(self):
        """Unknown mode defaults to 'add'."""
        cfg = NoteHoldStackConfig.from_dict({"mode": "unknown"})
        assert cfg.mode == "add"

    def test_valid_modes_preserved(self):
        """Valid modes are preserved."""
        for mode in ["add", "toggle", "additive"]:
            cfg = NoteHoldStackConfig.from_dict({"mode": mode})
            assert cfg.mode == mode

    def test_auto_release_on_overflow_default_true(self):
        """auto_release_on_overflow defaults to True."""
        cfg = NoteHoldStackConfig.from_dict({})
        assert cfg.auto_release_on_overflow is True


class TestNoteHoldStackBasicAdding:
    """Basic adding and holding notes."""

    def test_press_adds_single_note(self):
        """Pressing a note adds it to held set."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        pressed, released = stack.press(60)
        assert pressed == [(60, 1)]
        assert released == []
        assert stack.held() == [(60, 1)]

    def test_press_adds_multiple_notes_in_order(self):
        """Pressing multiple notes adds them in order."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60)
        pressed, released = stack.press(64)
        assert pressed == [(64, 1)]
        assert released == []
        assert stack.held() == [(60, 1), (64, 1)]

    def test_press_third_note(self):
        """Pressing a third note maintains order."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60)
        stack.press(64)
        pressed, released = stack.press(67)
        assert pressed == [(67, 1)]
        assert released == []
        assert stack.held() == [(60, 1), (64, 1), (67, 1)]

    def test_count_tracks_held_notes(self):
        """count() returns the number of held notes."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        assert stack.count() == 0
        stack.press(60)
        assert stack.count() == 1
        stack.press(64)
        assert stack.count() == 2
        stack.press(67)
        assert stack.count() == 3

    def test_is_held_returns_true_for_held_notes(self):
        """is_held() returns True for notes in stack."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60)
        assert stack.is_held(60)
        assert not stack.is_held(64)
        stack.press(64)
        assert stack.is_held(60)
        assert stack.is_held(64)


class TestNoteHoldStackAddToggleMode:
    """Add/toggle mode: pressing held note removes it."""

    def test_add_mode_press_held_removes_it(self):
        """In add mode, pressing a held note removes it."""
        cfg = NoteHoldStackConfig(enabled=True, mode="add")
        stack = NoteHoldStack(cfg)
        stack.press(60)
        assert stack.held() == [(60, 1)]
        pressed, released = stack.press(60)
        assert pressed == []
        assert released == [(60, 1)]
        assert stack.held() == []

    def test_add_mode_build_chord_then_deconstruct(self):
        """Build a chord, then remove notes one at a time."""
        cfg = NoteHoldStackConfig(enabled=True, mode="add")
        stack = NoteHoldStack(cfg)
        # Build chord: C E G
        stack.press(60)  # C
        stack.press(64)  # E
        stack.press(67)  # G
        assert stack.held() == [(60, 1), (64, 1), (67, 1)]

        # Remove E
        _, released = stack.press(64)
        assert released == [(64, 1)]
        assert stack.held() == [(60, 1), (67, 1)]

        # Remove C
        _, released = stack.press(60)
        assert released == [(60, 1)]
        assert stack.held() == [(67, 1)]

        # Remove G
        _, released = stack.press(67)
        assert released == [(67, 1)]
        assert stack.held() == []

    def test_toggle_mode_same_behavior_as_add(self):
        """Toggle mode should behave identically to add mode."""
        cfg_add = NoteHoldStackConfig(enabled=True, mode="add")
        cfg_toggle = NoteHoldStackConfig(enabled=True, mode="toggle")

        stack_add = NoteHoldStack(cfg_add)
        stack_toggle = NoteHoldStack(cfg_toggle)

        # Both should press same notes
        p1, r1 = stack_add.press(60)
        p2, r2 = stack_toggle.press(60)
        assert p1 == p2 and r1 == r2

        p1, r1 = stack_add.press(64)
        p2, r2 = stack_toggle.press(64)
        assert p1 == p2 and r1 == r2

        # Both should remove same notes
        p1, r1 = stack_add.press(60)
        p2, r2 = stack_toggle.press(60)
        assert p1 == p2 and r1 == r2


class TestNoteHoldStackAdditiveMode:
    """Additive mode: pressing always adds, never removes via press."""

    def test_additive_mode_never_removes_via_press(self):
        """In additive mode, pressing a held note has no effect."""
        cfg = NoteHoldStackConfig(enabled=True, mode="additive")
        stack = NoteHoldStack(cfg)
        stack.press(60)
        assert stack.held() == [(60, 1)]

        # Press same note again — should be no-op
        pressed, released = stack.press(60)
        assert pressed == []
        assert released == []
        assert stack.held() == [(60, 1)]  # Still only one copy

    def test_additive_mode_can_accumulate_many_notes(self):
        """Additive mode allows accumulating notes without deduplication."""
        cfg = NoteHoldStackConfig(enabled=True, mode="additive", max_notes=10)
        stack = NoteHoldStack(cfg)

        # Press same note multiple times — should only hold it once
        for _ in range(5):
            pressed, released = stack.press(60)
            if _ == 0:
                assert pressed == [(60, 1)]
            else:
                assert pressed == []  # No-op after first press
        assert stack.held() == [(60, 1)]
        assert stack.count() == 1


class TestNoteHoldStackChannels:
    """Channel handling — same note on different channels are separate."""

    def test_different_channels_are_distinct(self):
        """Same note on different channels are held separately."""
        cfg = NoteHoldStackConfig(enabled=True, mode="add")
        stack = NoteHoldStack(cfg)

        # Press C on channel 1
        stack.press(60, channel=1)
        # Press C on channel 2
        stack.press(60, channel=2)

        assert stack.held() == [(60, 1), (60, 2)]
        assert stack.count() == 2

        # Remove C on channel 1 only
        _, released = stack.press(60, channel=1)
        assert released == [(60, 1)]
        assert stack.held() == [(60, 2)]

    def test_is_held_respects_channel(self):
        """is_held() respects channel parameter."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60, channel=1)
        stack.press(60, channel=3)

        assert stack.is_held(60, channel=1)
        assert not stack.is_held(60, channel=2)
        assert stack.is_held(60, channel=3)

    def test_clear_releases_all_channels(self):
        """clear() releases all notes on all channels."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60, channel=1)
        stack.press(64, channel=2)
        stack.press(67, channel=3)

        released = stack.clear()
        assert set(released) == {(60, 1), (64, 2), (67, 3)}
        assert stack.held() == []


class TestNoteHoldStackMaxNotesAndOverflow:
    """Max notes cap and overflow behavior."""

    def test_max_notes_enforced(self):
        """Stack respects max_notes limit."""
        cfg = NoteHoldStackConfig(enabled=True, max_notes=2)
        stack = NoteHoldStack(cfg)

        p, r = stack.press(60)
        assert p == [(60, 1)] and r == []

        p, r = stack.press(64)
        assert p == [(64, 1)] and r == []
        assert stack.count() == 2

        # Try to add third note with auto_release_on_overflow=True (default)
        p, r = stack.press(67)
        assert p == [(67, 1)]
        assert r == [(60, 1)]  # Oldest was released
        assert stack.held() == [(64, 1), (67, 1)]

    def test_overflow_auto_release_oldest_first(self):
        """When overflow, oldest note is released first."""
        cfg = NoteHoldStackConfig(enabled=True, max_notes=2, auto_release_on_overflow=True)
        stack = NoteHoldStack(cfg)

        stack.press(60)  # oldest
        stack.press(64)
        # stack.held() = [(60, 1), (64, 1)]

        # Add 67, should eject 60
        p, r = stack.press(67)
        assert r == [(60, 1)]
        assert stack.held() == [(64, 1), (67, 1)]

        # Add 72, should eject 64
        p, r = stack.press(72)
        assert r == [(64, 1)]
        assert stack.held() == [(67, 1), (72, 1)]

    def test_overflow_reject_when_auto_release_disabled(self):
        """When auto_release_on_overflow=False and max hit, new note is rejected."""
        cfg = NoteHoldStackConfig(enabled=True, max_notes=2, auto_release_on_overflow=False)
        stack = NoteHoldStack(cfg)

        stack.press(60)
        stack.press(64)
        assert stack.count() == 2

        # Try to add 67 with overflow protection disabled
        p, r = stack.press(67)
        assert p == []  # No-op: note was not added
        assert r == []  # Nothing was released
        assert stack.held() == [(60, 1), (64, 1)]  # Unchanged

    def test_max_notes_1_allows_single_note(self):
        """max_notes=1 allows only one note at a time."""
        cfg = NoteHoldStackConfig(enabled=True, max_notes=1)
        stack = NoteHoldStack(cfg)

        p, r = stack.press(60)
        assert p == [(60, 1)] and r == []

        p, r = stack.press(64)
        assert p == [(64, 1)]
        assert r == [(60, 1)]  # Auto-released
        assert stack.count() == 1


class TestNoteHoldStackClear:
    """Clear / panic function."""

    def test_clear_empties_stack(self):
        """clear() releases all notes and empties stack."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60)
        stack.press(64)
        stack.press(67)
        assert stack.count() == 3

        released = stack.clear()
        assert set(released) == {(60, 1), (64, 1), (67, 1)}
        assert stack.held() == []
        assert stack.count() == 0

    def test_clear_empty_stack_returns_empty(self):
        """clear() on empty stack returns empty list."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        released = stack.clear()
        assert released == []

    def test_clear_then_press_again(self):
        """After clear(), stack can be reused."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60)
        stack.clear()

        p, r = stack.press(72)
        assert p == [(72, 1)] and r == []
        assert stack.held() == [(72, 1)]


class TestNoteHoldStackHeldReturnsACopy:
    """held() returns a copy, not the actual stack."""

    def test_held_returns_copy_not_reference(self):
        """held() returns a copy that doesn't affect the stack if mutated."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60)
        stack.press(64)

        held_copy = stack.held()
        assert held_copy == [(60, 1), (64, 1)]

        # Mutate the copy
        held_copy.append((99, 1))

        # Stack should be unchanged
        assert stack.held() == [(60, 1), (64, 1)]


class TestNoteHoldStackRemoveNonexistent:
    """Edge case: removing a note that doesn't exist."""

    def test_press_nonexistent_note_in_add_mode_adds_it(self):
        """Pressing a note that isn't held should add it."""
        cfg = NoteHoldStackConfig(enabled=True, mode="add")
        stack = NoteHoldStack(cfg)
        stack.press(60)

        # Press 64 (doesn't exist)
        p, r = stack.press(64)
        assert p == [(64, 1)]
        assert r == []
        assert stack.held() == [(60, 1), (64, 1)]


class TestNoteHoldStackPressWithTimestamp:
    """Timestamp parameter (for future use, currently unused)."""

    def test_press_with_now_s_parameter(self):
        """press() accepts now_s parameter (unused)."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        p, r = stack.press(60, channel=1, now_s=1234.5)
        assert p == [(60, 1)]
        assert r == []


class TestNoteHoldStackRoundTrip:
    """Serialization and deserialization."""

    def test_config_round_trip_all_modes(self):
        """Config round-trip preserves all modes."""
        for mode in ["add", "toggle", "additive"]:
            cfg = NoteHoldStackConfig(
                enabled=True,
                mode=mode,
                max_notes=12,
                auto_release_on_overflow=False,
            )
            data = cfg.to_dict()
            cfg2 = NoteHoldStackConfig.from_dict(data)
            assert cfg == cfg2

    def test_config_round_trip_all_max_notes_values(self):
        """Config round-trip preserves max_notes across valid range."""
        for max_notes in [1, 8, 16, 32]:
            cfg = NoteHoldStackConfig(max_notes=max_notes)
            data = cfg.to_dict()
            cfg2 = NoteHoldStackConfig.from_dict(data)
            assert cfg2.max_notes == max_notes


class TestNoteHoldStackUnknownMode:
    """Unknown modes handled gracefully."""

    def test_unknown_mode_falls_back_to_add_behavior(self):
        """Unknown mode is treated as 'add'."""
        cfg = NoteHoldStackConfig.from_dict({"mode": "nonexistent_mode"})
        assert cfg.mode == "add"

        stack = NoteHoldStack(cfg)
        stack.press(60)
        assert stack.is_held(60)

        # Press same note — should remove it (add behavior)
        p, r = stack.press(60)
        assert r == [(60, 1)]
        assert stack.held() == []


class TestNoteHoldStackMidiReturns:
    """Return values suitable for MIDI sender."""

    def test_press_returns_pressed_and_released_tuples(self):
        """press() returns correct tuples for MIDI note on/off."""
        cfg = NoteHoldStackConfig(enabled=True, mode="add")
        stack = NoteHoldStack(cfg)

        # Press C
        pressed, released = stack.press(60, channel=1)
        assert pressed == [(60, 1)]
        assert released == []

        # Press E
        pressed, released = stack.press(64, channel=1)
        assert pressed == [(64, 1)]
        assert released == []

        # Press C again (remove)
        pressed, released = stack.press(60, channel=1)
        assert pressed == []
        assert released == [(60, 1)]

    def test_clear_returns_released_notes_for_midi(self):
        """clear() returns notes in format ready for MIDI note-off."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        stack.press(60, channel=1)
        stack.press(64, channel=2)

        released = stack.clear()
        assert len(released) == 2
        # Each tuple can be unpacked as (note, channel)
        for note, channel in released:
            assert isinstance(note, int)
            assert isinstance(channel, int)


class TestNoteHoldStackIntegration:
    """Integration scenarios."""

    def test_build_c_major_triad_then_release(self):
        """Full scenario: build C major chord, then release it."""
        cfg = NoteHoldStackConfig(enabled=True, mode="add")
        stack = NoteHoldStack(cfg)

        # C major: C E G = 60 64 67
        p, r = stack.press(60)
        assert p == [(60, 1)] and r == []

        p, r = stack.press(64)
        assert p == [(64, 1)] and r == []

        p, r = stack.press(67)
        assert p == [(67, 1)] and r == []

        assert stack.held() == [(60, 1), (64, 1), (67, 1)]

        # Release E
        p, r = stack.press(64)
        assert r == [(64, 1)]
        assert stack.held() == [(60, 1), (67, 1)]

        # Panic (clear all)
        released = stack.clear()
        assert set(released) == {(60, 1), (67, 1)}
        assert stack.count() == 0

    def test_polyphonic_chord_on_multiple_channels(self):
        """Build a polyphonic chord across multiple MIDI channels."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)

        # Add notes on different channels
        stack.press(60, channel=1)  # Bass C
        stack.press(64, channel=2)  # Mid E
        stack.press(67, channel=3)  # High G

        assert stack.count() == 3
        assert stack.is_held(60, channel=1)
        assert stack.is_held(64, channel=2)
        assert stack.is_held(67, channel=3)

        # Release all
        released = stack.clear()
        assert len(released) == 3

    def test_max_notes_with_additive_mode(self):
        """Additive mode respects max_notes even though it never removes."""
        cfg = NoteHoldStackConfig(
            enabled=True, mode="additive", max_notes=3, auto_release_on_overflow=True
        )
        stack = NoteHoldStack(cfg)

        # Add 3 different notes
        stack.press(60)
        stack.press(64)
        stack.press(67)
        assert stack.count() == 3

        # Try to add a 4th (should eject the oldest: 60)
        p, r = stack.press(72)
        assert p == [(72, 1)]
        assert r == [(60, 1)]
        assert stack.held() == [(64, 1), (67, 1), (72, 1)]


class TestNoteHoldStackEmptyStack:
    """Edge cases with empty stack."""

    def test_empty_stack_count_is_zero(self):
        """Empty stack has count 0."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        assert stack.count() == 0

    def test_empty_stack_held_is_empty_list(self):
        """Empty stack held() returns empty list."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        assert stack.held() == []

    def test_empty_stack_is_held_returns_false(self):
        """Empty stack is_held() returns False for any note."""
        cfg = NoteHoldStackConfig(enabled=True)
        stack = NoteHoldStack(cfg)
        assert not stack.is_held(60)
        assert not stack.is_held(127)
