"""MIDI message rate limiting — cap messages/sec by type to prevent downstream flooding."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class RateLimitConfig:
    """Configuration for MIDI rate limiting."""

    enabled: bool = False
    max_total_per_sec: int = 1000
    max_cc_per_sec: int = 500
    max_note_per_sec: int = 100
    max_sysex_per_sec: int = 10
    coalesce_same_cc: bool = True
    coalesce_window_ms: int = 8

    def __post_init__(self) -> None:
        """Validate and clamp all numeric ranges."""
        self.max_total_per_sec = max(1, min(10000, self.max_total_per_sec))
        self.max_cc_per_sec = max(0, min(10000, self.max_cc_per_sec))
        self.max_note_per_sec = max(0, min(10000, self.max_note_per_sec))
        self.max_sysex_per_sec = max(0, min(1000, self.max_sysex_per_sec))
        self.coalesce_window_ms = max(1, min(1000, self.coalesce_window_ms))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RateLimitConfig:
        """Deserialize from dict."""
        # Only keep known fields to be forward-compatible
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class RateLimiter:
    """Enforce per-second rate limits on MIDI messages by category."""

    def __init__(self, cfg: RateLimitConfig) -> None:
        """Initialize with config. Sets up sliding-window queues."""
        self.cfg = cfg
        self._total: list[float] = []
        self._cc: list[float] = []
        self._note: list[float] = []
        self._sysex: list[float] = []
        # (channel, cc_num) -> (last_time_s, last_value)
        self._last_cc: dict[tuple[int, int], tuple[float, int]] = {}

    def allow(self, msg_bytes: list[int], now_s: float) -> bool:
        """
        Check if a MIDI message should be allowed through.

        Returns False if rate-limited, True if allowed.
        On allow, updates internal queues and coalesce state.
        """
        if not self.cfg.enabled:
            return True

        if not msg_bytes:
            return True

        # Classify message by status byte
        status = msg_bytes[0]
        category = self._classify(status)

        # Prune old entries from all queues
        self._prune(now_s)

        # Check coalesce for CC messages
        if category == "cc" and self.cfg.coalesce_same_cc:
            if len(msg_bytes) >= 3:
                channel = status & 0x0F
                cc_num = msg_bytes[1]
                cc_val = msg_bytes[2]
                key = (channel, cc_num)

                if key in self._last_cc:
                    last_time, last_val = self._last_cc[key]
                    time_delta_ms = (now_s - last_time) * 1000
                    if time_delta_ms < self.cfg.coalesce_window_ms and last_val == cc_val:
                        return False

        # Check quotas
        if len(self._total) >= self.cfg.max_total_per_sec:
            return False

        if category == "cc" and self.cfg.max_cc_per_sec > 0:
            if len(self._cc) >= self.cfg.max_cc_per_sec:
                return False
        elif category == "note" and self.cfg.max_note_per_sec > 0:
            if len(self._note) >= self.cfg.max_note_per_sec:
                return False
        elif category == "sysex" and self.cfg.max_sysex_per_sec > 0:
            if len(self._sysex) >= self.cfg.max_sysex_per_sec:
                return False

        # Accept: record in appropriate queues
        self._total.append(now_s)
        if category == "cc":
            self._cc.append(now_s)
            if len(msg_bytes) >= 3:
                channel = status & 0x0F
                cc_num = msg_bytes[1]
                cc_val = msg_bytes[2]
                self._last_cc[(channel, cc_num)] = (now_s, cc_val)
        elif category == "note":
            self._note.append(now_s)
        elif category == "sysex":
            self._sysex.append(now_s)
        # "other" messages count toward total but not a separate category

        return True

    def current_rate(self, now_s: float) -> dict[str, int]:
        """
        Return message counts within the trailing 1-second window.

        Returns dict with "total", "cc", "note", "sysex" keys.
        """
        self._prune(now_s)
        return {
            "total": len(self._total),
            "cc": len(self._cc),
            "note": len(self._note),
            "sysex": len(self._sysex),
        }

    def reset(self) -> None:
        """Clear all queues and coalesce state."""
        self._total.clear()
        self._cc.clear()
        self._note.clear()
        self._sysex.clear()
        self._last_cc.clear()

    def _classify(self, status: int) -> str:
        """
        Classify MIDI message by status byte.

        Returns "cc", "note", "sysex", or "other".
        """
        if 0xB0 <= status <= 0xBF:
            return "cc"
        elif 0x80 <= status <= 0x9F:
            return "note"
        elif status == 0xF0:
            return "sysex"
        else:
            return "other"

    def _prune(self, now_s: float) -> None:
        """Remove all entries older than 1 second from now."""
        cutoff = now_s - 1.0
        self._total = [t for t in self._total if t > cutoff]
        self._cc = [t for t in self._cc if t > cutoff]
        self._note = [t for t in self._note if t > cutoff]
        self._sysex = [t for t in self._sysex if t > cutoff]
