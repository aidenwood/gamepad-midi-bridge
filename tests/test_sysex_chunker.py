"""Tests for SysEx message chunking and transmission timing.

Tests the chunking logic, reassembly, delay management, and transmission
time estimation.
"""

import pytest
import time
from gamepad_midi_bridge.sysex_chunker import (
    SysexChunkConfig,
    chunk_sysex,
    unchunk,
    estimate_send_duration_ms,
    ChunkedSysexSender,
)


class TestSysexChunkConfig:
    """Tests for SysexChunkConfig dataclass."""

    def test_default_values(self) -> None:
        """Default config has sensible values."""
        cfg = SysexChunkConfig()
        assert cfg.max_chunk_size == 256
        assert cfg.delay_between_chunks_ms == 5

    def test_clamping_max_chunk_size_too_small(self) -> None:
        """max_chunk_size is clamped to minimum 16."""
        cfg = SysexChunkConfig(max_chunk_size=5)
        assert cfg.max_chunk_size == 16

    def test_clamping_max_chunk_size_too_large(self) -> None:
        """max_chunk_size is clamped to maximum 65536."""
        cfg = SysexChunkConfig(max_chunk_size=100000)
        assert cfg.max_chunk_size == 65536

    def test_clamping_delay_too_small(self) -> None:
        """delay_between_chunks_ms is clamped to minimum 0."""
        cfg = SysexChunkConfig(delay_between_chunks_ms=-5)
        assert cfg.delay_between_chunks_ms == 0

    def test_clamping_delay_too_large(self) -> None:
        """delay_between_chunks_ms is clamped to maximum 1000."""
        cfg = SysexChunkConfig(delay_between_chunks_ms=2000)
        assert cfg.delay_between_chunks_ms == 1000

    def test_to_dict(self) -> None:
        """to_dict() produces a dict representation."""
        cfg = SysexChunkConfig(max_chunk_size=128, delay_between_chunks_ms=10)
        d = cfg.to_dict()
        assert d == {"max_chunk_size": 128, "delay_between_chunks_ms": 10}

    def test_from_dict(self) -> None:
        """from_dict() reconstructs from a dict."""
        d = {"max_chunk_size": 512, "delay_between_chunks_ms": 20}
        cfg = SysexChunkConfig.from_dict(d)
        assert cfg.max_chunk_size == 512
        assert cfg.delay_between_chunks_ms == 20

    def test_round_trip_serialization(self) -> None:
        """to_dict -> from_dict is a round-trip."""
        original = SysexChunkConfig(max_chunk_size=100, delay_between_chunks_ms=50)
        d = original.to_dict()
        reconstructed = SysexChunkConfig.from_dict(d)
        assert reconstructed.max_chunk_size == original.max_chunk_size
        assert reconstructed.delay_between_chunks_ms == original.delay_between_chunks_ms


class TestChunkSysex:
    """Tests for chunk_sysex() function."""

    def test_chunk_sysex_small_message(self) -> None:
        """Small message that fits in one chunk returns a single chunk."""
        msg = [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7]  # GM reset
        chunks = chunk_sysex(msg, max_chunk_size=256)
        assert len(chunks) == 1
        assert chunks[0] == msg

    def test_chunk_sysex_long_message_returns_multiple_chunks(self) -> None:
        """Long message is split into multiple chunks."""
        # Create a 500-byte message
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        chunks = chunk_sysex(msg, max_chunk_size=128)
        assert len(chunks) > 1

    def test_chunk_sysex_each_chunk_starts_with_f0(self) -> None:
        """Each chunk starts with F0."""
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        chunks = chunk_sysex(msg, max_chunk_size=128)
        for chunk in chunks:
            assert chunk[0] == 0xF0

    def test_chunk_sysex_each_chunk_ends_with_f7(self) -> None:
        """Each chunk ends with F7."""
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        chunks = chunk_sysex(msg, max_chunk_size=128)
        for chunk in chunks:
            assert chunk[-1] == 0xF7

    def test_chunk_sysex_each_chunk_respects_max_size(self) -> None:
        """Each chunk is <= max_chunk_size."""
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        max_size = 128
        chunks = chunk_sysex(msg, max_chunk_size=max_size)
        for chunk in chunks:
            assert len(chunk) <= max_size

    def test_chunk_sysex_empty_raises(self) -> None:
        """Empty message raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            chunk_sysex([], max_chunk_size=256)

    def test_chunk_sysex_too_short_raises(self) -> None:
        """Message shorter than [F0, F7] raises ValueError."""
        with pytest.raises(ValueError, match="at least"):
            chunk_sysex([0xF0], max_chunk_size=256)

    def test_chunk_sysex_without_f0_raises(self) -> None:
        """Message without F0 prefix raises ValueError."""
        with pytest.raises(ValueError, match="F0"):
            chunk_sysex([0x7E, 0x7F, 0x09, 0x01, 0xF7], max_chunk_size=256)

    def test_chunk_sysex_without_f7_raises(self) -> None:
        """Message without F7 suffix raises ValueError."""
        with pytest.raises(ValueError, match="F7"):
            chunk_sysex([0xF0, 0x7E, 0x7F, 0x09, 0x01], max_chunk_size=256)

    def test_chunk_sysex_with_max_chunk_size_16(self) -> None:
        """Chunking with max_chunk_size=16 creates multiple chunks."""
        msg = [0xF0, 0x41, 0x42, 0x43, 0x44, 0x45, 0xF7]  # 7 bytes
        chunks = chunk_sysex(msg, max_chunk_size=16)
        assert len(chunks) == 1  # Still fits in 1 chunk

        # Larger message
        msg = [0xF0] + [0x41] * 50 + [0xF7]
        chunks = chunk_sysex(msg, max_chunk_size=16)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 16


class TestUnchunk:
    """Tests for unchunk() function."""

    def test_unchunk_single_chunk(self) -> None:
        """Single chunk is reassembled correctly."""
        original = [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7]
        chunks = [original]
        reassembled = unchunk(chunks)
        assert reassembled == original

    def test_unchunk_multiple_chunks(self) -> None:
        """Multiple chunks are reassembled correctly."""
        original = [0xF0] + [0x41] * 500 + [0xF7]
        chunks = chunk_sysex(original, max_chunk_size=128)
        reassembled = unchunk(chunks)
        assert reassembled == original

    def test_unchunk_empty_raises(self) -> None:
        """Empty chunks list raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            unchunk([])

    def test_unchunk_chunk_without_f0_raises(self) -> None:
        """Chunk without F0 raises ValueError."""
        chunks = [[0x41, 0xF7]]
        with pytest.raises(ValueError, match="F0"):
            unchunk(chunks)

    def test_unchunk_chunk_without_f7_raises(self) -> None:
        """Chunk without F7 raises ValueError."""
        chunks = [[0xF0, 0x41]]
        with pytest.raises(ValueError, match="F7"):
            unchunk(chunks)

    def test_round_trip_chunk_then_unchunk(self) -> None:
        """chunk -> unchunk is a round-trip for various message sizes."""
        test_messages = [
            [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7],  # Small
            [0xF0] + [0x41] * 100 + [0xF7],  # Medium
            [0xF0] + [0x42] * 500 + [0xF7],  # Large
        ]
        for original in test_messages:
            chunks = chunk_sysex(original, max_chunk_size=256)
            reassembled = unchunk(chunks)
            assert reassembled == original


class TestEstimateSendDuration:
    """Tests for estimate_send_duration_ms() function."""

    def test_estimate_send_duration_returns_float(self) -> None:
        """estimate_send_duration_ms returns a float."""
        msg = [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7]
        duration = estimate_send_duration_ms(msg)
        assert isinstance(duration, float)
        assert duration > 0

    def test_estimate_send_duration_scales_with_byte_count(self) -> None:
        """Longer messages have longer estimated duration."""
        msg_short = [0xF0] + [0x41] * 10 + [0xF7]
        msg_long = [0xF0] + [0x41] * 100 + [0xF7]
        duration_short = estimate_send_duration_ms(msg_short)
        duration_long = estimate_send_duration_ms(msg_long)
        assert duration_long > duration_short

    def test_estimate_send_duration_with_custom_baud_rate(self) -> None:
        """Custom baud rate affects estimate."""
        msg = [0xF0] + [0x41] * 50 + [0xF7]
        duration_fast = estimate_send_duration_ms(msg, baud_rate_hz=115200)
        duration_slow = estimate_send_duration_ms(msg, baud_rate_hz=9600)
        assert duration_slow > duration_fast

    def test_estimate_send_duration_includes_chunk_delays(self) -> None:
        """Estimated duration increases with chunk delays."""
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        duration_no_delay = estimate_send_duration_ms(
            msg, max_chunk_size=256, delay_between_chunks_ms=0
        )
        duration_with_delay = estimate_send_duration_ms(
            msg, max_chunk_size=256, delay_between_chunks_ms=5
        )
        assert duration_with_delay > duration_no_delay


class TestChunkedSysexSender:
    """Tests for ChunkedSysexSender class."""

    def test_init_with_config(self) -> None:
        """Sender initializes with a config."""
        cfg = SysexChunkConfig(max_chunk_size=128, delay_between_chunks_ms=10)
        sender = ChunkedSysexSender(cfg)
        assert sender.pending_count() == 0

    def test_enqueue_returns_chunk_count(self) -> None:
        """enqueue() returns number of chunks created."""
        cfg = SysexChunkConfig(max_chunk_size=128)
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        chunk_count = sender.enqueue(msg)
        assert chunk_count > 1
        assert sender.pending_count() == chunk_count

    def test_enqueue_small_message(self) -> None:
        """Enqueueing a small message creates 1 chunk."""
        cfg = SysexChunkConfig()
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7]
        chunk_count = sender.enqueue(msg)
        assert chunk_count == 1

    def test_pop_ready_empty_queue(self) -> None:
        """pop_ready on empty queue returns empty list."""
        cfg = SysexChunkConfig()
        sender = ChunkedSysexSender(cfg)
        result = sender.pop_ready(time.time())
        assert result == []

    def test_pop_ready_first_chunk_ready_immediately(self) -> None:
        """First call to pop_ready returns first chunk immediately."""
        cfg = SysexChunkConfig()
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        sender.enqueue(msg)
        now = time.time()
        chunk = sender.pop_ready(now)
        assert len(chunk) == 1
        assert chunk[0][0] == 0xF0
        assert chunk[0][-1] == 0xF7

    def test_pop_ready_respects_delay_between_chunks(self) -> None:
        """pop_ready respects delay_between_chunks_ms."""
        cfg = SysexChunkConfig(delay_between_chunks_ms=5)
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        sender.enqueue(msg)

        now = time.time()
        # Get first chunk
        chunk1 = sender.pop_ready(now)
        assert len(chunk1) == 1

        # Try to get second chunk immediately (not enough time)
        chunk2 = sender.pop_ready(now)
        assert chunk2 == []

        # Try after enough time has passed
        later = now + 0.01  # 10ms, > 5ms delay
        chunk2 = sender.pop_ready(later)
        assert len(chunk2) == 1

    def test_pending_count_decreases(self) -> None:
        """pending_count decreases as chunks are popped."""
        cfg = SysexChunkConfig()
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        sender.enqueue(msg)
        initial_count = sender.pending_count()

        now = time.time()
        sender.pop_ready(now)
        assert sender.pending_count() == initial_count - 1

    def test_clear_empties_queue(self) -> None:
        """clear() empties the pending queue."""
        cfg = SysexChunkConfig()
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        sender.enqueue(msg)
        assert sender.pending_count() > 0

        sender.clear()
        assert sender.pending_count() == 0

    def test_clear_resets_timestamp(self) -> None:
        """clear() resets the send timestamp."""
        cfg = SysexChunkConfig(delay_between_chunks_ms=100)
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        sender.enqueue(msg)

        now = time.time()
        # Get first chunk
        sender.pop_ready(now)

        # Clear and re-enqueue
        sender.clear()
        sender.enqueue(msg)

        # First chunk of new queue should be ready immediately (not blocked by delay)
        chunk = sender.pop_ready(now)
        assert len(chunk) == 1

    def test_many_small_messages_enqueued(self) -> None:
        """Multiple messages can be enqueued and popped in order."""
        cfg = SysexChunkConfig(delay_between_chunks_ms=0)
        sender = ChunkedSysexSender(cfg)

        msg1 = [0xF0, 0x41, 0x42, 0xF7]
        msg2 = [0xF0, 0x43, 0x44, 0xF7]
        msg3 = [0xF0, 0x45, 0x46, 0xF7]

        sender.enqueue(msg1)
        sender.enqueue(msg2)
        sender.enqueue(msg3)

        assert sender.pending_count() == 3

        now = time.time()
        chunk1 = sender.pop_ready(now)[0]
        chunk2 = sender.pop_ready(now)[0]
        chunk3 = sender.pop_ready(now)[0]

        assert chunk1 == msg1
        assert chunk2 == msg2
        assert chunk3 == msg3
        assert sender.pending_count() == 0

    def test_delay_enforcement_multiple_chunks(self) -> None:
        """Delay is enforced between every chunk pop."""
        cfg = SysexChunkConfig(max_chunk_size=64, delay_between_chunks_ms=5)
        sender = ChunkedSysexSender(cfg)
        msg = [0xF0] + [0x41] * 500 + [0xF7]
        num_chunks = sender.enqueue(msg)
        assert num_chunks > 1

        now = time.time()
        sent_chunks = []

        # Pop as many chunks as we can
        for i in range(num_chunks * 2):  # Try more than available
            chunk = sender.pop_ready(now)
            if chunk:
                sent_chunks.append(chunk)
                # Advance time by 6ms (more than the 5ms delay)
                now += 0.006

        # All chunks should have been sent (one per iteration with sufficient delay)
        assert len(sent_chunks) == num_chunks
