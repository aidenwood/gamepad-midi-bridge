"""Stick-chord mode: direction-based note firing on threshold cross."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock

from gamepad_midi_bridge.bridge import BridgeWorker
from gamepad_midi_bridge.mapping import Mapping, StickConfig


class MockMidiPort:
    """Mock MIDI port for testing."""
    def __init__(self):
        self.messages_sent = []

    def send_message(self, msg):
        """Record MIDI messages."""
        self.messages_sent.append(msg)


class TestStickChordBasics:
    """Test stick-chord detection and note firing."""

    def test_chord_disabled_no_notes_sent(self):
        """When chord_enabled=False, no chord notes fire."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=False,
            chord_north=[60, 64, 67],
        )
        midi = Mock()
        midi.port = MockMidiPort()

        # Call chord polling with high magnitude (would trigger if enabled)
        worker._poll_stick_chords(0, 0.0, 0.9, mapping.left_stick, mapping, midi)

        assert len(midi.port.messages_sent) == 0


    def test_chord_north_fires_on_threshold_cross(self):
        """North direction fires chord notes when magnitude crosses threshold."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[60, 64, 67],
            chord_velocity=100,
            chord_channel=None,  # use mapping channel (0)
        )
        midi = Mock()
        midi.port = MockMidiPort()

        # Initial state: magnitude below threshold
        worker._stick_chord_state[0] = None
        worker._stick_chord_state["0_notes"] = []

        # Trigger north (0.0 X, 0.8 Y — dominant axis is Y, positive)
        worker._poll_stick_chords(0, 0.0, 0.8, mapping.left_stick, mapping, midi)

        # Should have sent 3 note-on messages
        note_ons = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x90]
        assert len(note_ons) == 3
        assert note_ons[0][1] == 60  # first note
        assert note_ons[0][2] == 100  # velocity
        assert note_ons[1][1] == 64  # second note
        assert note_ons[2][1] == 67  # third note

        # State should track direction and notes
        assert worker._stick_chord_state[0] == "north"
        assert worker._stick_chord_state["0_notes"] == [60, 64, 67]


    def test_chord_direction_change_fires_note_offs(self):
        """Changing direction sends note-off for old chord, note-on for new."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[60, 64, 67],
            chord_east=[62, 66, 71],
            chord_velocity=100,
        )
        midi = Mock()
        midi.port = MockMidiPort()

        # Pre-populate state: north chord is active
        worker._stick_chord_state[0] = "north"
        worker._stick_chord_state["0_notes"] = [60, 64, 67]

        # Change direction to east (0.8 X, 0.0 Y)
        worker._poll_stick_chords(0, 0.8, 0.0, mapping.left_stick, mapping, midi)

        # Should have note-off for north notes, then note-on for east
        messages = midi.port.messages_sent
        note_offs = [msg for msg in messages if (msg[0] & 0xF0) == 0x80]
        note_ons = [msg for msg in messages if (msg[0] & 0xF0) == 0x90]

        # 3 note-offs for old chord
        assert len(note_offs) == 3
        assert [msg[1] for msg in note_offs] == [60, 64, 67]

        # 3 note-ons for new chord
        assert len(note_ons) == 3
        assert [msg[1] for msg in note_ons] == [62, 66, 71]


    def test_chord_release_sends_note_offs(self):
        """Dropping below threshold releases all held notes."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[60, 64, 67],
            chord_velocity=100,
        )
        midi = Mock()
        midi.port = MockMidiPort()

        # Pre-populate: north chord is active
        worker._stick_chord_state[0] = "north"
        worker._stick_chord_state["0_notes"] = [60, 64, 67]

        # Drop below threshold (magnitude 0.3)
        worker._poll_stick_chords(0, 0.0, 0.2, mapping.left_stick, mapping, midi)

        # Should have 3 note-off messages
        note_offs = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x80]
        assert len(note_offs) == 3
        assert [msg[1] for msg in note_offs] == [60, 64, 67]

        # State should be None
        assert worker._stick_chord_state[0] is None


    def test_chord_all_four_directions(self):
        """Test north, east, south, west chord firing."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[60],
            chord_east=[62],
            chord_south=[64],
            chord_west=[65],
            chord_velocity=100,
        )
        midi = Mock()
        midi.port = MockMidiPort()

        # Test each direction
        directions = [
            ((0.0, 0.8), "north", 60),   # Y positive
            ((0.8, 0.0), "east", 62),    # X positive
            ((0.0, -0.8), "south", 64),  # Y negative
            ((-0.8, 0.0), "west", 65),   # X negative
        ]

        for (x, y), expected_dir, expected_note in directions:
            midi.port.messages_sent.clear()
            # Reset state
            worker._stick_chord_state[0] = None
            worker._stick_chord_state["0_notes"] = []

            worker._poll_stick_chords(0, x, y, mapping.left_stick, mapping, midi)

            assert worker._stick_chord_state[0] == expected_dir
            note_ons = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x90]
            assert len(note_ons) == 1
            assert note_ons[0][1] == expected_note


    def test_chord_empty_list_no_notes_sent(self):
        """Empty chord note list fires nothing."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[],  # empty!
            chord_velocity=100,
        )
        midi = Mock()
        midi.port = MockMidiPort()

        worker._poll_stick_chords(0, 0.0, 0.8, mapping.left_stick, mapping, midi)

        # No note-on messages (chord is empty)
        note_ons = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x90]
        assert len(note_ons) == 0


    def test_chord_respects_channel_override(self):
        """chord_channel override applies to fired notes."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping(midi_channel=0)
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[60],
            chord_velocity=100,
            chord_channel=5,  # override
        )
        midi = Mock()
        midi.port = MockMidiPort()

        worker._poll_stick_chords(0, 0.0, 0.8, mapping.left_stick, mapping, midi)

        note_ons = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x90]
        assert len(note_ons) == 1
        # Channel is in status byte: 0x90 | channel
        assert (note_ons[0][0] & 0x0F) == 5


    def test_chord_right_stick(self):
        """Chord works on right stick (stick_index=1)."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.right_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[72, 76, 79],
            chord_velocity=100,
        )
        midi = Mock()
        midi.port = MockMidiPort()

        worker._poll_stick_chords(1, 0.0, 0.8, mapping.right_stick, mapping, midi)

        note_ons = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x90]
        assert len(note_ons) == 3
        assert [msg[1] for msg in note_ons] == [72, 76, 79]


    def test_chord_threshold_boundary(self):
        """Exactly at threshold doesn't fire; just above does."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[60],
            chord_velocity=100,
        )
        midi = Mock()
        midi.port = MockMidiPort()

        # Exactly at threshold (0.5) — should NOT fire
        import math
        x, y = 0.0, 0.5
        magnitude = math.sqrt(x**2 + y**2)  # 0.5
        # Initialize state
        worker._stick_chord_state[0] = None
        worker._stick_chord_state["0_notes"] = []

        worker._poll_stick_chords(0, x, y, mapping.left_stick, mapping, midi)

        note_ons = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x90]
        assert len(note_ons) == 0  # not fired
        assert worker._stick_chord_state[0] is None

        # Just above threshold (0.51) — should fire
        midi.port.messages_sent.clear()
        worker._stick_chord_state[0] = None
        worker._stick_chord_state["0_notes"] = []
        y = 0.51
        worker._poll_stick_chords(0, x, y, mapping.left_stick, mapping, midi)

        note_ons = [msg for msg in midi.port.messages_sent if (msg[0] & 0xF0) == 0x90]
        assert len(note_ons) == 1  # fired


    def test_chord_no_retrigger_same_direction(self):
        """Staying in same direction doesn't retrigger notes."""
        worker = BridgeWorker(demo=True)
        mapping = Mapping()
        mapping.left_stick = StickConfig(
            chord_enabled=True,
            chord_threshold=0.5,
            chord_north=[60, 64, 67],
            chord_velocity=100,
        )
        midi = Mock()
        midi.port = MockMidiPort()

        # First call: trigger north
        worker._stick_chord_state[0] = None
        worker._stick_chord_state["0_notes"] = []
        worker._poll_stick_chords(0, 0.0, 0.8, mapping.left_stick, mapping, midi)
        first_send_count = len(midi.port.messages_sent)

        # Second call: still north (different Y value, but still dominant Y positive)
        midi.port.messages_sent.clear()
        worker._poll_stick_chords(0, 0.0, 0.9, mapping.left_stick, mapping, midi)
        second_send_count = len(midi.port.messages_sent)

        # Second call should send nothing (no direction change)
        assert second_send_count == 0
        assert worker._stick_chord_state[0] == "north"  # still north
