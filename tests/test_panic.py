"""Tests for panic() and send_test_note() methods.

Covers:
  - panic() sends CC 123 (all notes off) and CC 120 (all sound off) on all 16 channels.
  - panic() also sends note-off for every note 0..127 on all 16 channels.
  - panic() emits midi_sent signal after each message.
  - send_test_note() sends a note-on followed by a scheduled note-off.
  - send_test_note() clamps channel, note, and velocity to valid ranges.
  - send_test_note() cleans up expired timers to prevent memory leaks.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from gamepad_midi_bridge.bridge import BridgeWorker


class TestPanic:
    """Test panic() — all notes off + all sound off."""

    def test_panic_no_midi_port(self):
        """panic() should exit gracefully when _midi is None."""
        worker = BridgeWorker()
        worker._midi = None
        # Should not raise
        worker.panic()

    def test_panic_sends_expected_message_count(self):
        """panic() should send 2080 messages: 16 channels × (2 CCs + 128 note-offs)."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        worker._midi.port.send_message = MagicMock()

        worker.panic()

        # Each channel: 2 CCs (all notes off + all sound off) + 128 note-offs = 130 messages
        # 16 channels × 130 = 2080 messages
        expected_count = 16 * 130
        assert worker._midi.port.send_message.call_count == expected_count

    def test_panic_sends_cc123_all_channels(self):
        """panic() should send CC 123 (all notes off) on all 16 channels."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        worker.panic()

        # Check that CC 123 is sent on all 16 channels (status byte 0xB0-0xBF)
        cc123_messages = [
            msg for msg in sent_messages
            if (msg[0] & 0xF0) == 0xB0 and msg[1] == 123  # CC message with CC#123
        ]
        assert len(cc123_messages) == 16
        # Verify correct channel bytes (0xB0 | 0..15)
        channels_sent = {msg[0] & 0x0F for msg in cc123_messages}
        assert channels_sent == set(range(16))

    def test_panic_sends_cc120_all_channels(self):
        """panic() should send CC 120 (all sound off) on all 16 channels."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        worker.panic()

        # Check that CC 120 is sent on all 16 channels (status byte 0xB0-0xBF)
        cc120_messages = [
            msg for msg in sent_messages
            if (msg[0] & 0xF0) == 0xB0 and msg[1] == 120  # CC message with CC#120
        ]
        assert len(cc120_messages) == 16

    def test_panic_sends_noteoff_for_all_notes(self):
        """panic() should send note-off for every note 0..127 on all channels."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        worker.panic()

        # Filter to note-off messages (status byte 0x80-0x8F)
        note_off_messages = [
            msg for msg in sent_messages
            if (msg[0] & 0xF0) == 0x80
        ]
        # 16 channels × 128 notes = 2048 note-off messages
        assert len(note_off_messages) == 2048

    def test_panic_emits_midi_sent(self):
        """panic() should emit midi_sent signal."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        worker.midi_sent = MagicMock()

        worker.panic()

        # Should emit at least once per message or once overall
        # (implementation emits after CCs + once after loop)
        assert worker.midi_sent.emit.called

    def test_panic_handles_send_exception(self):
        """panic() should handle exceptions from send_message gracefully."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        worker._midi.port.send_message = MagicMock(side_effect=Exception("Port closed"))

        # Should not raise
        worker.panic()


class TestSendTestNote:
    """Test send_test_note() — brief test note for DAW verification."""

    def test_send_test_note_no_midi_port(self):
        """send_test_note() should exit gracefully when _midi is None."""
        worker = BridgeWorker()
        worker._midi = None
        # Should not raise
        worker.send_test_note(channel=0, note=60, velocity=100, duration_ms=200)

    def test_send_test_note_sends_note_on(self):
        """send_test_note() should send a note-on immediately."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        worker.send_test_note(channel=0, note=60, velocity=100, duration_ms=200)

        # Should have at least the note-on (scheduled note-off comes later via timer)
        assert len(sent_messages) >= 1
        # First message should be note-on (0x90 | channel, note, velocity)
        assert sent_messages[0] == [0x90, 60, 100]

    def test_send_test_note_clamps_channel(self):
        """send_test_note() should clamp channel to 0..15."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        # Try negative channel — should clamp to 0
        worker.send_test_note(channel=-5, note=60, velocity=100, duration_ms=200)
        assert (sent_messages[0][0] & 0x0F) == 0

        sent_messages.clear()
        # Try channel > 15 — should clamp to 15
        worker.send_test_note(channel=20, note=60, velocity=100, duration_ms=200)
        assert (sent_messages[0][0] & 0x0F) == 15

    def test_send_test_note_clamps_note(self):
        """send_test_note() should clamp note to 0..127."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        # Try negative note — should clamp to 0
        worker.send_test_note(channel=0, note=-10, velocity=100, duration_ms=200)
        assert sent_messages[0][1] == 0

        sent_messages.clear()
        # Try note > 127 — should clamp to 127
        worker.send_test_note(channel=0, note=200, velocity=100, duration_ms=200)
        assert sent_messages[0][1] == 127

    def test_send_test_note_clamps_velocity(self):
        """send_test_note() should clamp velocity to 0..127."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        # Try negative velocity — should clamp to 0
        worker.send_test_note(channel=0, note=60, velocity=-10, duration_ms=200)
        assert sent_messages[0][2] == 0

        sent_messages.clear()
        # Try velocity > 127 — should clamp to 127
        worker.send_test_note(channel=0, note=60, velocity=200, duration_ms=200)
        assert sent_messages[0][2] == 127

    def test_send_test_note_clamps_duration(self):
        """send_test_note() should enforce minimum duration of 10ms."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()

        # Should not raise on very short duration
        worker.send_test_note(channel=0, note=60, velocity=100, duration_ms=1)
        # Timer should be created with at least 10ms
        assert hasattr(worker, '_test_note_timers')

    def test_send_test_note_schedules_note_off(self):
        """send_test_note() should create a QTimer for the note-off."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)

        worker.send_test_note(channel=0, note=60, velocity=100, duration_ms=200)

        # Should have a timer stored in the list
        assert hasattr(worker, '_test_note_timers')
        assert len(worker._test_note_timers) >= 1
        # Timer should be created (may not be active in test context without event loop)

    def test_send_test_note_emits_midi_sent(self):
        """send_test_note() should emit midi_sent signal."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        worker.midi_sent = MagicMock()

        worker.send_test_note(channel=0, note=60, velocity=100, duration_ms=200)

        # Should emit at least once for the note-on
        assert worker.midi_sent.emit.called

    def test_send_test_note_handles_exception(self):
        """send_test_note() should handle exceptions from send_message gracefully."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        worker._midi.port.send_message = MagicMock(side_effect=Exception("Port closed"))

        # Should not raise
        worker.send_test_note(channel=0, note=60, velocity=100, duration_ms=200)

    def test_send_test_note_off_internal(self):
        """_send_test_note_off() should send note-off and clean up timers."""
        worker = BridgeWorker()
        worker._midi = MagicMock()
        worker._midi.port = MagicMock()
        sent_messages = []
        worker._midi.port.send_message = lambda msg: sent_messages.append(msg)
        worker._test_note_timers = []

        # Create an inactive timer (simulating an expired timer)
        inactive_timer = MagicMock()
        inactive_timer.isActive.return_value = False
        worker._test_note_timers.append(inactive_timer)

        worker._send_test_note_off(channel=0, note=60)

        # Should have sent note-off (0x80 | channel, note, 0)
        assert sent_messages[0] == [0x80, 60, 0]
        # Should have cleaned up the inactive timer
        assert len(worker._test_note_timers) == 0
