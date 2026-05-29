"""Per-control activity heatmap — tracks how many times each button/axis/trigger fires.

Records hit counts per control with timestamps of last activity. Exposes heatmap-ready
data structures for UI rendering. Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ControlHit:
    """A single control's activity record.

    Attributes:
        control_type: Type of control ("button", "axis", "trigger", "hat", "touchpad").
        control_id: Unique identifier (e.g. "button.0", "L2", "left_stick_x").
        count: Number of times this control has fired.
        last_at: Unix timestamp (seconds) of most recent activity, or None.
    """
    control_type: str
    control_id: str
    count: int = 0
    last_at: Optional[float] = None

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "control_type": self.control_type,
            "control_id": self.control_id,
            "count": self.count,
            "last_at": self.last_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ControlHit:
        """Deserialize from JSON-friendly dict."""
        return cls(
            control_type=str(d.get("control_type", "")),
            control_id=str(d.get("control_id", "")),
            count=int(d.get("count", 0)),
            last_at=float(d["last_at"]) if d.get("last_at") is not None else None,
        )


@dataclass
class ControlHeatmapConfig:
    """Configuration for ControlHeatmap.

    Attributes:
        max_controls: Maximum number of distinct controls to track (clamped 10..10000).
    """
    max_controls: int = 100

    def __post_init__(self) -> None:
        """Clamp parameters to valid ranges."""
        self.max_controls = max(10, min(10000, self.max_controls))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "max_controls": self.max_controls,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ControlHeatmapConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            max_controls=int(d.get("max_controls", 100)),
        )


class ControlHeatmap:
    """Tracks per-control activity: hit counts and last-activity timestamps.

    Records every control fire event, maintains hit counts, and provides query
    methods for analytics and heatmap visualization.
    """

    def __init__(self, cfg: ControlHeatmapConfig) -> None:
        """Initialize with config.

        Args:
            cfg: ControlHeatmapConfig instance.
        """
        self.cfg = cfg
        self._hits: Dict[str, ControlHit] = {}

    # ---------------------------------------------------------------- record

    def record(self, control_type: str, control_id: str, now_s: float) -> None:
        """Record a control activity event.

        If control_id exists, increment count and update last_at.
        Otherwise, create a new ControlHit. If count would exceed max_controls,
        evict the control with the oldest (smallest) last_at before adding.

        Args:
            control_type: Type of control ("button", "axis", "trigger", "hat", "touchpad").
            control_id: Unique identifier for this control.
            now_s: Unix timestamp in seconds of this activity.
        """
        if control_id in self._hits:
            # Existing control: increment and update timestamp
            hit = self._hits[control_id]
            hit.count += 1
            hit.last_at = now_s
        else:
            # New control: check if we need to evict
            if len(self._hits) >= self.cfg.max_controls:
                # Evict the control with oldest last_at (or None if it exists)
                # Prefer evicting controls with None last_at, then by oldest timestamp
                oldest_id = None
                oldest_time = None
                for cid, hit in self._hits.items():
                    if hit.last_at is None:
                        oldest_id = cid
                        break
                    if oldest_time is None or hit.last_at < oldest_time:
                        oldest_id = cid
                        oldest_time = hit.last_at
                if oldest_id is not None:
                    del self._hits[oldest_id]

            # Create new control
            self._hits[control_id] = ControlHit(
                control_type=control_type,
                control_id=control_id,
                count=1,
                last_at=now_s,
            )

    # ---------------------------------------------------------------- query

    def get_hit(self, control_id: str) -> Optional[ControlHit]:
        """Return the ControlHit for a given control_id, or None.

        Args:
            control_id: The control identifier to look up.

        Returns:
            The ControlHit, or None if not found.
        """
        return self._hits.get(control_id)

    def all_hits(self) -> Dict[str, ControlHit]:
        """Return a shallow copy of all ControlHit records.

        Returns:
            Dict mapping control_id -> ControlHit.
        """
        return dict(self._hits)

    def top_n(self, n: int = 5) -> List[ControlHit]:
        """Return the top N controls by hit count, descending.

        Args:
            n: Number of results to return.

        Returns:
            List of ControlHit, sorted by count descending. Empty if no hits.
        """
        if not self._hits:
            return []
        sorted_hits = sorted(
            self._hits.values(),
            key=lambda hit: hit.count,
            reverse=True,
        )
        return sorted_hits[:n]

    def bottom_n(self, n: int = 5) -> List[ControlHit]:
        """Return the lowest N controls by hit count, ascending (excluding count=0).

        Args:
            n: Number of results to return.

        Returns:
            List of ControlHit with count > 0, sorted by count ascending.
        """
        non_zero = [hit for hit in self._hits.values() if hit.count > 0]
        if not non_zero:
            return []
        sorted_hits = sorted(non_zero, key=lambda hit: hit.count)
        return sorted_hits[:n]

    def by_type(self, control_type: str) -> List[ControlHit]:
        """Return all ControlHits of a specific type.

        Args:
            control_type: Filter by this control type.

        Returns:
            List of matching ControlHits, unsorted.
        """
        return [hit for hit in self._hits.values() if hit.control_type == control_type]

    def to_heatmap(self) -> Dict[str, int]:
        """Export hit counts as a flat dict for UI heatmap rendering.

        Returns:
            Dict mapping control_id -> count.
        """
        return {cid: hit.count for cid, hit in self._hits.items()}

    def total_hits(self) -> int:
        """Return the sum of all hit counts.

        Returns:
            Total number of control fire events recorded.
        """
        return sum(hit.count for hit in self._hits.values())

    def unique_controls(self) -> int:
        """Return the number of distinct controls recorded.

        Returns:
            Number of unique control_ids currently tracked.
        """
        return len(self._hits)

    # ---------------------------------------------------------------- clear

    def clear(self) -> None:
        """Delete all recorded hits."""
        self._hits.clear()
