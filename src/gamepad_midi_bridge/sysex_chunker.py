"""Pure stdlib MIDI System Exclusive (SysEx) message chunker.

Splits long SysEx messages into smaller chunks for safe transmission.
Some MIDI receivers choke on very large messages (>256 bytes), so this module
provides utilities to chunk and reassemble messages with configurable size limits
and inter-chunk delays.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional
import time


# MIDI constants
SYSEX_START = 0xF0  # 240: Start of exclusive
SYSEX_END = 0xF7    # 247: End of exclusive


@dataclass
class SysexChunkConfig:
    """Configuration for SysEx message chunking.

    Attributes:
        max_chunk_size: Maximum bytes per chunk (16..65536, default 256).
                       Clamped to valid range.
        delay_between_chunks_ms: Milliseconds to wait between sending chunks
                                (0..1000, default 5). Clamped to valid range.
    """

    max_chunk_size: int = 256
    delay_between_chunks_ms: int = 5

    def __post_init__(self) -> None:
        """Clamp values to valid ranges."""
        self.max_chunk_size = max(16, min(65536, self.max_chunk_size))
        self.delay_between_chunks_ms = max(0, min(1000, self.delay_between_chunks_ms))

    def to_dict(self) -> dict:
        """Convert to a dict for serialization.

        Returns:
            Dictionary representation of the SysexChunkConfig.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SysexChunkConfig:
        """Construct from a dict (reverse of to_dict).

        Args:
            data: Dictionary with keys matching SysexChunkConfig fields.

        Returns:
            A new SysexChunkConfig instance.
        """
        return cls(**data)


def chunk_sysex(msg_bytes: List[int], max_chunk_size: int = 256) -> List[List[int]]:
    """Split a SysEx message into safe-sized chunks.

    Strategy:
    - If message is shorter than max_chunk_size, return [msg_bytes] unchanged.
    - Otherwise: strip F0 from start and F7 from end, split the data into chunks
      of (max_chunk_size - 2) bytes (so each chunk + F0/F7 wrap fits inside
      max_chunk_size). Wrap each chunk with F0 ... F7. Return list of chunks.

    Args:
        msg_bytes: Full SysEx message including F0 start and F7 end.
        max_chunk_size: Maximum bytes per chunk (default 256).

    Returns:
        List of SysEx chunks, each with F0 start and F7 end.

    Raises:
        ValueError: If msg_bytes is empty, too short, or doesn't start with F0
                   or end with F7.
    """
    if not msg_bytes:
        raise ValueError("msg_bytes cannot be empty")

    if len(msg_bytes) < 2:
        raise ValueError("msg_bytes must be at least [F0, F7]")

    if msg_bytes[0] != SYSEX_START:
        raise ValueError(f"msg_bytes must start with F0 (0x{SYSEX_START:02X}), "
                        f"got 0x{msg_bytes[0]:02X}")

    if msg_bytes[-1] != SYSEX_END:
        raise ValueError(f"msg_bytes must end with F7 (0x{SYSEX_END:02X}), "
                        f"got 0x{msg_bytes[-1]:02X}")

    # If message fits within max_chunk_size, return as single chunk
    if len(msg_bytes) <= max_chunk_size:
        return [msg_bytes]

    # Strip F0 from start and F7 from end to get payload
    payload = msg_bytes[1:-1]

    # Calculate chunk data size (reserve 2 bytes for F0/F7 wrap)
    chunk_data_size = max_chunk_size - 2

    # Split payload into chunks
    chunks: List[List[int]] = []
    for i in range(0, len(payload), chunk_data_size):
        chunk_data = payload[i:i + chunk_data_size]
        # Wrap each chunk with F0 ... F7
        chunk = [SYSEX_START] + chunk_data + [SYSEX_END]
        chunks.append(chunk)

    return chunks


def unchunk(chunks: List[List[int]]) -> List[int]:
    """Recombine SysEx chunks into a single message.

    Strips F0/F7 from each chunk, concatenates the payloads, and wraps
    the result with a single F0 ... F7.

    Args:
        chunks: List of SysEx chunks, each with F0 start and F7 end.

    Returns:
        Full reassembled SysEx message with single F0 start and F7 end.

    Raises:
        ValueError: If chunks is empty or any chunk is malformed.
    """
    if not chunks:
        raise ValueError("chunks cannot be empty")

    # Extract payload from each chunk and concatenate
    combined_payload: List[int] = []
    for i, chunk in enumerate(chunks):
        if len(chunk) < 2:
            raise ValueError(f"Chunk {i} is too short (len={len(chunk)}); "
                            "must be at least [F0, F7]")
        if chunk[0] != SYSEX_START:
            raise ValueError(f"Chunk {i} does not start with F0 (0x{SYSEX_START:02X}), "
                            f"got 0x{chunk[0]:02X}")
        if chunk[-1] != SYSEX_END:
            raise ValueError(f"Chunk {i} does not end with F7 (0x{SYSEX_END:02X}), "
                            f"got 0x{chunk[-1]:02X}")
        # Extract data (between F0 and F7)
        combined_payload.extend(chunk[1:-1])

    # Wrap combined payload with single F0 ... F7
    return [SYSEX_START] + combined_payload + [SYSEX_END]


def estimate_send_duration_ms(
    msg_bytes: List[int],
    baud_rate_hz: int = 31250,
    max_chunk_size: int = 256,
    delay_between_chunks_ms: int = 5,
) -> float:
    """Estimate total transmission time for a SysEx message with chunking.

    Calculates the time to send a message when split into chunks, accounting for:
    - Transmission time of all bytes (10 bits per byte at given baud rate)
    - Inter-chunk delays

    Args:
        msg_bytes: Full SysEx message.
        baud_rate_hz: MIDI baud rate (default 31250 for standard MIDI).
        max_chunk_size: Maximum bytes per chunk (default 256).
        delay_between_chunks_ms: Milliseconds delay between chunks (default 5).

    Returns:
        Estimated duration in milliseconds as a float.
    """
    num_bytes = len(msg_bytes)
    # MIDI: 10 bits per byte (1 start, 8 data, 1 stop)
    # time_per_byte_ms = (10 bits / baud_rate_hz) * 1000
    time_per_byte_ms = (10 / baud_rate_hz) * 1000

    # Total transmission time for all bytes
    transmission_time_ms = num_bytes * time_per_byte_ms

    # Calculate number of chunks
    chunks = chunk_sysex(msg_bytes, max_chunk_size)
    num_chunks = len(chunks)

    # Inter-chunk delays (only between chunks, so num_chunks - 1 delays)
    delay_time_ms = (num_chunks - 1) * delay_between_chunks_ms

    return transmission_time_ms + delay_time_ms


class ChunkedSysexSender:
    """Manages queued SysEx chunks and respects inter-chunk delays.

    Enqueues a message (which gets chunked), then dispenses chunks one at a time
    while respecting a minimum delay between sends.

    Attributes:
        _config: SysexChunkConfig instance.
        _pending_chunks: Queue of chunks waiting to be sent.
        _last_sent_at: Timestamp (seconds) of the last pop_ready() call,
                      or None if nothing sent yet.
    """

    def __init__(self, cfg: SysexChunkConfig) -> None:
        """Initialize the sender.

        Args:
            cfg: SysexChunkConfig instance (or will be created with defaults
                if not provided).
        """
        self._config = cfg if cfg else SysexChunkConfig()
        self._pending_chunks: List[List[int]] = []
        self._last_sent_at: Optional[float] = None

    def enqueue(self, msg_bytes: List[int]) -> int:
        """Chunk a message and add to the queue.

        Args:
            msg_bytes: Full SysEx message to queue.

        Returns:
            Number of chunks created.

        Raises:
            ValueError: If msg_bytes is invalid.
        """
        chunks = chunk_sysex(msg_bytes, self._config.max_chunk_size)
        self._pending_chunks.extend(chunks)
        return len(chunks)

    def pop_ready(self, now_s: float) -> List[List[int]]:
        """Return and remove chunks that are ready to send.

        Returns at most one chunk per call (respecting delay_between_chunks_ms).
        If not enough time has passed since the last send, returns [].

        Args:
            now_s: Current time in seconds (e.g. from time.time()).

        Returns:
            List containing zero or one chunk ready to send.
        """
        if not self._pending_chunks:
            return []

        # If this is the first send, allow it immediately
        if self._last_sent_at is None:
            chunk = self._pending_chunks.pop(0)
            self._last_sent_at = now_s
            return [chunk]

        # Check if enough time has elapsed since last send
        elapsed_ms = (now_s - self._last_sent_at) * 1000
        if elapsed_ms >= self._config.delay_between_chunks_ms:
            chunk = self._pending_chunks.pop(0)
            self._last_sent_at = now_s
            return [chunk]

        # Not ready yet
        return []

    def pending_count(self) -> int:
        """Return number of chunks still pending.

        Returns:
            Number of chunks in the queue.
        """
        return len(self._pending_chunks)

    def clear(self) -> None:
        """Clear all pending chunks and reset send timestamp.

        Useful for flushing the queue or starting fresh.
        """
        self._pending_chunks.clear()
        self._last_sent_at = None
