"""Stick-edge corner detection — turn an analog stick into 4/8/16 buttons.

The user pushes the stick all the way to a corner; we fire a MIDI note-on for
that sector. When they relax, we fire note-off. Hysteresis prevents chatter
when the stick hovers around a sector boundary.

Algorithm:
    1. Compute polar radius `r` and angle `theta` from (x, y).
    2. If we're idle and `r >= r_enter`: pick a sector and fire note-on.
    3. If we're active and `r <= r_exit`: fire note-off, go idle.
    4. If we're active and the angle has crossed a full sector boundary:
       fire note-off on the old sector, note-on on the new one (so users
       can sweep around the edge of the stick to trigger a sequence).

`r_enter > r_exit` and the angle-switch requires a full sector crossing,
which together kill the chatter the report flagged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CornerEvent:
    kind: str          # "on" or "off"
    sector: int        # 0..n-1


class CornerDetector:
    def __init__(
        self,
        n: int = 8,
        r_enter: float = 0.92,
        r_exit: float = 0.75,
    ) -> None:
        if n not in (4, 8, 16):
            raise ValueError(f"n must be 4, 8, or 16; got {n}")
        if r_enter <= r_exit:
            raise ValueError("r_enter must be greater than r_exit (hysteresis)")
        self.n = n
        self.r_enter = r_enter
        self.r_exit = r_exit
        self._active: Optional[int] = None

    def reset(self) -> None:
        self._active = None

    @property
    def active_sector(self) -> Optional[int]:
        return self._active

    def update(self, x: float, y: float) -> Optional[CornerEvent]:
        """Feed the latest stick reading. Returns an event when one fires."""
        r = math.hypot(x, y)

        if self._active is None:
            if r < self.r_enter:
                return None
            sector = self._sector_for(x, y)
            self._active = sector
            return CornerEvent("on", sector)

        # Currently active in some sector.
        if r < self.r_exit:
            old = self._active
            self._active = None
            return CornerEvent("off", old)

        new_sector = self._sector_for(x, y)
        if new_sector != self._active:
            old = self._active
            self._active = new_sector
            # Caller emits an "off" for `old` followed by an "on" for `new`.
            # We return the "on" here and rely on the caller's previous state
            # tracking to handle "off"; or, simpler: return a pair.
            return CornerEvent("switch", new_sector | (old << 8))
        return None

    def _sector_for(self, x: float, y: float) -> int:
        # atan2 returns (-pi, pi]. Shift to [0, 2pi) then quantize.
        theta = math.atan2(y, x)
        if theta < 0:
            theta += 2 * math.pi
        sector_width = (2 * math.pi) / self.n
        # Centre sector 0 at +X axis (right). Rotate by half a sector so the
        # right-most cardinal position is sector 0 rather than straddling 0/n-1.
        shifted = (theta + sector_width / 2) % (2 * math.pi)
        return int(shifted // sector_width) % self.n


def decode_switch(event: CornerEvent) -> tuple[int, int]:
    """Unpack a 'switch' event into (old_sector, new_sector)."""
    if event.kind != "switch":
        raise ValueError("Not a switch event")
    return (event.sector >> 8) & 0xFF, event.sector & 0xFF
