"""Tests for MIDI feedback-loop guard."""
import pytest
import time
from gamepad_midi_bridge.bridge import BridgeWorker
from gamepad_midi_bridge.mapping import Mapping


@pytest.fixture
def bridge_worker():
    """Create a BridgeWorker for testing (no actual threading)."""
    worker = BridgeWorker(demo=True)
    return worker


def test_recently_sent_within_window(bridge_worker):
    """_recently_sent returns True for recent CCs within the window."""
    worker = bridge_worker
    worker._record_outbound_cc(channel=0, cc_number=7, value=64)
    
    # Immediately check — should be within 50ms window
    assert worker._recently_sent(channel=0, cc_number=7, value=64) is True
    
    # Different value should not match
    assert worker._recently_sent(channel=0, cc_number=7, value=63) is False
    
    # Different CC should not match
    assert worker._recently_sent(channel=0, cc_number=8, value=64) is False
    
    # Different channel should not match
    assert worker._recently_sent(channel=1, cc_number=7, value=64) is False


def test_recently_sent_outside_window(bridge_worker):
    """_recently_sent returns False for CCs outside the window."""
    worker = bridge_worker
    worker._record_outbound_cc(channel=0, cc_number=7, value=64)
    
    # Wait beyond the default window (50ms)
    time.sleep(0.06)
    
    # Should no longer be found
    assert worker._recently_sent(channel=0, cc_number=7, value=64) is False


def test_recently_sent_custom_window(bridge_worker):
    """_recently_sent respects custom window parameter."""
    worker = bridge_worker
    worker._record_outbound_cc(channel=0, cc_number=7, value=64)
    
    # Wait 30ms, then check with 50ms window (should find) and 20ms window (should not)
    time.sleep(0.03)
    assert worker._recently_sent(channel=0, cc_number=7, value=64, window_ms=50) is True
    assert worker._recently_sent(channel=0, cc_number=7, value=64, window_ms=20) is False


def test_feedback_loop_deque_max_size(bridge_worker):
    """Deque respects max size of 50 entries."""
    worker = bridge_worker
    
    # Record 60 CCs — deque should keep only last 50
    for i in range(60):
        worker._record_outbound_cc(channel=0, cc_number=7, value=i % 128)
    
    # Deque size should be capped at 50
    assert len(worker._recent_outbound_cc) == 50
    
    # First recorded value (0) should be gone
    assert worker._recently_sent(channel=0, cc_number=7, value=0, window_ms=100000) is False
    
    # Last recorded value (59) should still be there
    assert worker._recently_sent(channel=0, cc_number=7, value=59 % 128, window_ms=100000) is True
