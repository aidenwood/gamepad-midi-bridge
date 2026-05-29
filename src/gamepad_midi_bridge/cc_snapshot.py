"""CC Snapshot helper — capture and recall MIDI CC states across all channels.

CcSnapshotStore manages named snapshots of MIDI CC values (channel + CC number → value).
Each snapshot captures the current state of every observed CC, and can be restored
by generating the necessary MIDI CC messages.

Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class CcSnapshot:
    """A named snapshot of CC values across all channels.

    Attributes:
        name: Human-readable identifier for this snapshot (e.g., "Vol+Exp").
        created_at_s: Unix timestamp (seconds) when snapshot was created.
        values: Dict mapping (channel 1..16, cc 0..127) tuples to values 0..127.
    """
    name: str = ""
    created_at_s: float = 0.0
    values: Dict[Tuple[int, int], int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict. Converts tuple keys to "channel_cc" strings."""
        return {
            "name": self.name,
            "created_at_s": self.created_at_s,
            "values": {
                f"{ch}_{cc}": val
                for (ch, cc), val in self.values.items()
            }
        }

    @classmethod
    def from_dict(cls, d: dict) -> CcSnapshot:
        """Deserialize from JSON-friendly dict. Converts "channel_cc" strings back to tuples."""
        values = {}
        for key_str, val in d.get("values", {}).items():
            parts = key_str.split("_")
            if len(parts) == 2:
                try:
                    ch, cc = int(parts[0]), int(parts[1])
                    values[(ch, cc)] = int(val)
                except (ValueError, IndexError):
                    pass
        return cls(
            name=str(d.get("name", "")),
            created_at_s=float(d.get("created_at_s", 0.0)),
            values=values
        )


@dataclass
class CcSnapshotConfig:
    """Configuration for CcSnapshotStore.

    Attributes:
        max_snapshots: Maximum number of snapshots to keep (clamped 1..256).
        auto_capture_on_preset_change: Whether to auto-capture when preset changes.
    """
    max_snapshots: int = 16
    auto_capture_on_preset_change: bool = False

    def __post_init__(self) -> None:
        """Clamp max_snapshots to valid range."""
        self.max_snapshots = max(1, min(256, self.max_snapshots))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "max_snapshots": self.max_snapshots,
            "auto_capture_on_preset_change": self.auto_capture_on_preset_change,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CcSnapshotConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            max_snapshots=int(d.get("max_snapshots", 16)),
            auto_capture_on_preset_change=bool(d.get("auto_capture_on_preset_change", False))
        )


class CcSnapshotStore:
    """Manages live CC observation and named snapshot capture/recall.

    Tracks current CC values across all 16 MIDI channels (0..127 CC numbers),
    and stores up to max_snapshots named snapshots for later restoration.
    """

    def __init__(self, cfg: CcSnapshotConfig) -> None:
        """Initialize with config.

        Args:
            cfg: CcSnapshotConfig instance.
        """
        self.cfg = cfg
        self._live: Dict[Tuple[int, int], int] = {}  # (channel 1..16, cc 0..127) → value 0..127
        self._snapshots: List[CcSnapshot] = []

    # ---------------------------------------------------------------- live observation

    def observe(self, channel: int, cc: int, value: int) -> None:
        """Record a CC value from a MIDI message.

        Args:
            channel: MIDI channel 1..16 (clamped).
            cc: CC number 0..127 (clamped).
            value: CC value 0..127 (clamped).
        """
        ch = max(1, min(16, channel))
        c = max(0, min(127, cc))
        v = max(0, min(127, value))
        self._live[(ch, c)] = v

    # ---------------------------------------------------------------- capture

    def capture(self, name: str, now_s: float = 0.0) -> CcSnapshot:
        """Capture current live CC state as a named snapshot.

        If the store already contains max_snapshots, the oldest is deleted.
        If now_s is 0.0, time.time() is used.

        Args:
            name: Human-readable snapshot name.
            now_s: Unix timestamp (optional; defaults to current time).

        Returns:
            The newly created and stored CcSnapshot.
        """
        if now_s <= 0.0:
            now_s = time.time()

        # Deep copy of live values
        snapshot_values = dict(self._live)

        snapshot = CcSnapshot(
            name=str(name),
            created_at_s=now_s,
            values=snapshot_values
        )

        self._snapshots.append(snapshot)

        # Truncate oldest if we exceeded max
        if len(self._snapshots) > self.cfg.max_snapshots:
            self._snapshots.pop(0)

        return snapshot

    # ---------------------------------------------------------------- list & find

    def list_snapshots(self) -> List[CcSnapshot]:
        """Return a copy of all stored snapshots."""
        return list(self._snapshots)

    def find(self, name: str) -> Optional[CcSnapshot]:
        """Find first snapshot by name.

        Args:
            name: Snapshot name to search for.

        Returns:
            The matching CcSnapshot, or None if not found.
        """
        for snap in self._snapshots:
            if snap.name == name:
                return snap
        return None

    def delete(self, name: str) -> bool:
        """Delete a snapshot by name.

        Args:
            name: Snapshot name to delete.

        Returns:
            True if a snapshot was removed, False if not found.
        """
        initial_len = len(self._snapshots)
        self._snapshots = [s for s in self._snapshots if s.name != name]
        return len(self._snapshots) < initial_len

    # ---------------------------------------------------------------- restore

    def restore_messages(self, name: str) -> List[List[int]]:
        """Generate MIDI CC messages to restore a snapshot.

        Args:
            name: Snapshot name to restore.

        Returns:
            List of [status_byte, data1, data2] for each CC in the snapshot.
            Returns [] if snapshot not found.
        """
        snapshot = self.find(name)
        if snapshot is None:
            return []

        messages = []
        for (channel, cc), value in sorted(snapshot.values.items()):
            # Status byte: 0xB0 (CC) | (channel - 1)
            status = 0xB0 | (channel - 1)
            messages.append([status, cc, value])

        return messages

    def diff(self, name: str) -> Dict[Tuple[int, int], Tuple[int, int]]:
        """Compute differences between live state and a snapshot.

        Args:
            name: Snapshot name to compare against.

        Returns:
            Dict of (channel, cc) → (current_value, snapshot_value) for entries
            that differ. Returns {} if snapshot not found or if live == snapshot.
        """
        snapshot = self.find(name)
        if snapshot is None:
            return {}

        differences = {}
        all_keys = set(self._live.keys()) | set(snapshot.values.keys())

        for key in all_keys:
            live_val = self._live.get(key)
            snap_val = snapshot.values.get(key)
            # Report difference if either is missing or values differ
            if live_val != snap_val:
                differences[key] = (live_val or 0, snap_val or 0)

        return differences

    # ---------------------------------------------------------------- clear

    def clear_snapshots(self) -> None:
        """Delete all stored snapshots."""
        self._snapshots.clear()

    def clear_live(self) -> None:
        """Clear all live CC observations."""
        self._live.clear()
