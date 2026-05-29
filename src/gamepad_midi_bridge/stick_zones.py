"""Stick zone mapper: divides stick xy area into named zones and maps to MIDI notes."""

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


ZONE_4 = ["N", "E", "S", "W"]
ZONE_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
ZONE_9 = ["NW", "N", "NE", "W", "C", "E", "SW", "S", "SE"]


@dataclass
class StickZoneConfig:
    """Configuration for stick zone mapping."""

    enabled: bool = False
    zone_count: int = 9
    center_deadzone: float = 0.15
    outer_threshold: float = 0.95
    zone_notes: Dict[str, int] = field(default_factory=dict)
    channel: int = 1
    velocity: int = 100

    def __post_init__(self) -> None:
        """Clamp numeric bounds."""
        self.zone_count = max(4, min(self.zone_count, 16))
        self.center_deadzone = max(0.0, min(self.center_deadzone, 0.5))
        self.outer_threshold = max(0.1, min(self.outer_threshold, 1.0))
        self.channel = max(1, min(self.channel, 16))
        self.velocity = max(1, min(self.velocity, 127))

    def to_dict(self) -> dict:
        """Serialize to dict for storage."""
        return {
            "enabled": self.enabled,
            "zone_count": self.zone_count,
            "center_deadzone": self.center_deadzone,
            "outer_threshold": self.outer_threshold,
            "zone_notes": self.zone_notes,
            "channel": self.channel,
            "velocity": self.velocity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StickZoneConfig":
        """Deserialize from dict."""
        return cls(
            enabled=data.get("enabled", False),
            zone_count=data.get("zone_count", 9),
            center_deadzone=data.get("center_deadzone", 0.15),
            outer_threshold=data.get("outer_threshold", 0.95),
            zone_notes=data.get("zone_notes", {}),
            channel=data.get("channel", 1),
            velocity=data.get("velocity", 100),
        )


def pick_zone_4(x: float, y: float) -> str:
    """Pick one of 4 cardinal zones (N/E/S/W) based on dominant axis.

    Args:
        x: horizontal position (-1 to 1, left to right)
        y: vertical position (-1 to 1, down to up in stick coords, but we interpret
           positive y as "up" in cardinal terms for intuition)

    Returns:
        One of "N", "E", "S", "W"
    """
    abs_x = abs(x)
    abs_y = abs(y)

    if abs_x > abs_y:
        return "E" if x > 0 else "W"
    else:
        return "N" if y > 0 else "S"


def pick_zone_8(x: float, y: float) -> str:
    """Pick one of 8 zones (cardinal + diagonal) based on angle.

    Args:
        x: horizontal position (-1 to 1)
        y: vertical position (-1 to 1)

    Returns:
        One of "N", "NE", "E", "SE", "S", "SW", "W", "NW"
    """
    angle = math.atan2(y, x)
    # Normalize angle to start at north (pi/2) and go clockwise
    adjusted = -(angle - math.pi / 2) / (2 * math.pi)
    if adjusted < 0:
        adjusted += 1.0
    zone_index = int(adjusted * 8) % 8

    # Map: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
    zones = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return zones[zone_index]


def pick_zone_9(x: float, y: float, center_deadzone: float = 0.15) -> str:
    """Pick one of 9 zones (8 directions + center) based on magnitude and angle.

    Args:
        x: horizontal position (-1 to 1)
        y: vertical position (-1 to 1)
        center_deadzone: magnitude threshold below which to return "C"

    Returns:
        One of "N", "NE", "E", "SE", "S", "SW", "W", "NW", "C"
    """
    magnitude = math.sqrt(x * x + y * y)

    if magnitude < center_deadzone:
        return "C"

    return pick_zone_8(x, y)


def zone_for(x: float, y: float, cfg: StickZoneConfig) -> Optional[str]:
    """Dispatch to appropriate zone picker based on config.

    Args:
        x: horizontal position (-1 to 1)
        y: vertical position (-1 to 1)
        cfg: zone configuration

    Returns:
        Zone name or None if below deadzone (for 4/8 modes) or if zone is None
    """
    magnitude = math.sqrt(x * x + y * y)

    # For 4 and 8 zone modes, return None below deadzone
    if magnitude < cfg.center_deadzone and cfg.zone_count != 9:
        return None

    if cfg.zone_count == 4:
        return pick_zone_4(x, y)
    elif cfg.zone_count == 8:
        return pick_zone_8(x, y)
    elif cfg.zone_count == 9:
        return pick_zone_9(x, y, cfg.center_deadzone)
    else:
        # For 16-zone: sub-divide each of the 8 zones radially
        # Use outer_threshold to determine if we're in an "edge" zone
        # For now, treat as 8-zone; could expand to radial sub-division later
        return pick_zone_8(x, y)


class StickZoneMapper:
    """Maps stick position to zones and triggers MIDI note on zone change."""

    def __init__(self, cfg: StickZoneConfig) -> None:
        """Initialize mapper with config.

        Args:
            cfg: zone configuration
        """
        self.cfg = cfg
        self._last_zone: Optional[str] = None

    def feed(self, x: float, y: float) -> Optional[Tuple[str, int]]:
        """Feed stick position and return (zone, note) if zone changed and is mapped.

        Args:
            x: horizontal position (-1 to 1)
            y: vertical position (-1 to 1)

        Returns:
            (zone_name, midi_note) tuple if zone changed and is in zone_notes, else None
        """
        zone = zone_for(x, y, self.cfg)

        # No change if same zone
        if zone == self._last_zone:
            return None

        self._last_zone = zone

        # Return (zone, note) only if zone is mapped
        if zone is not None and zone in self.cfg.zone_notes:
            return (zone, self.cfg.zone_notes[zone])

        return None

    def current_zone(self) -> Optional[str]:
        """Return the current zone without triggering a change event.

        Returns:
            Current zone name or None
        """
        return self._last_zone

    def reset(self) -> None:
        """Clear zone state to trigger a change on next feed."""
        self._last_zone = None
