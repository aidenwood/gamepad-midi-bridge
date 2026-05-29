"""Session activity log — append-only ring buffer of significant bridge events.

ActivityLog is a module-level singleton accessed via ``log()``.  Callers record
events with ``log().record(kind, message, severity="info")``.

A small Qt signaller is included so the UI can refresh whenever new events land
without polling.  Import ``activity_log_updated`` (a ``Signal()`` carried by the
``_Signaller`` instance at ``log().signaller``) to connect your widget.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

RING_BUFFER_SIZE = 200

_VALID_SEVERITIES = {"info", "warning", "error"}


@dataclass
class ActivityEvent:
    """One recorded event in the session timeline."""
    timestamp: float          # time.time() epoch seconds
    kind: str                 # e.g. "bridge_started", "preset_load", "error"
    message: str              # human-readable description
    severity: str = "info"    # one of: info | warning | error

    def __post_init__(self) -> None:
        if self.severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"severity must be one of {_VALID_SEVERITIES!r}, got {self.severity!r}"
            )


class _Signaller(QObject):
    """Tiny QObject that carries the ``activity_log_updated`` signal.

    Lives on the thread that constructs it (normally the GUI thread).
    """
    activity_log_updated = Signal()


class ActivityLog:
    """Singleton append-only ring buffer of the last ``RING_BUFFER_SIZE`` events.

    Obtain the instance via the module-level ``log()`` function.
    """

    def __init__(self) -> None:
        self._buf: deque[ActivityEvent] = deque(maxlen=RING_BUFFER_SIZE)
        self.signaller = _Signaller()

    # ---------------------------------------------------------------- public API

    def record(self, kind: str, message: str, severity: str = "info") -> None:
        """Append a new event and emit ``activity_log_updated``."""
        event = ActivityEvent(
            timestamp=time.time(),
            kind=str(kind),
            message=str(message),
            severity=str(severity),
        )
        self._buf.append(event)
        self.signaller.activity_log_updated.emit()

    def snapshot(self) -> List[ActivityEvent]:
        """Return a shallow copy of all buffered events (oldest-first)."""
        return list(self._buf)

    def snapshot_by_severity(self, severity: str) -> List[ActivityEvent]:
        """Return events filtered to a specific severity level."""
        return [e for e in self._buf if e.severity == severity]

    def clear(self) -> None:
        """Empty the buffer and emit ``activity_log_updated``."""
        self._buf.clear()
        self.signaller.activity_log_updated.emit()

    def __len__(self) -> int:
        return len(self._buf)


# ---------------------------------------------------------------------------
# Module-level singleton

_instance: Optional[ActivityLog] = None


def log() -> ActivityLog:
    """Return the global ``ActivityLog`` singleton, creating it on first call."""
    global _instance
    if _instance is None:
        _instance = ActivityLog()
    return _instance
