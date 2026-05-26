"""Default control mapping + serialisation.

Schema version 2 (V1.1): adds corner-quantized stick buttons, touchpad XY
CCs, and a placeholder for adaptive-trigger haptic effect names. Old v1
presets without these fields load with sensible defaults thanks to dict.get.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


SCHEMA_VERSION = 2

# Axes that come from analog sticks (vs triggers). Sticks need drift compensation.
STICK_AXES = frozenset({0, 1, 2, 3})


@dataclass
class CornerConfig:
    """Edge-quantization config for one analog stick. Pro feature.

    `notes` should have exactly `n` entries — the MIDI note fired for each
    sector. Sector 0 is the +X cardinal (rightward); sectors advance clockwise.
    """
    enabled: bool = False
    n: int = 8                                  # 4, 8, or 16
    notes: List[int] = field(default_factory=list)
    r_enter: float = 0.92
    r_exit: float = 0.75

    def ensure_notes(self) -> None:
        """Pad or trim `notes` to match `n` so the UI can edit safely."""
        if len(self.notes) < self.n:
            start = 96 if self.n <= len(self.notes) else 96
            # Default to a chromatic sweep starting at C6 (note 96).
            self.notes = self.notes + [
                start + i for i in range(len(self.notes), self.n)
            ]
        elif len(self.notes) > self.n:
            self.notes = self.notes[: self.n]


@dataclass
class TouchpadConfig:
    """DualSense touchpad as a 2D MIDI modulator. Pro feature."""
    enabled: bool = False
    x_cc: int = 16          # MIDI CC for X position
    y_cc: int = 17          # MIDI CC for Y position
    require_contact: bool = True   # only send CCs while finger is on the pad


@dataclass
class Mapping:
    """A complete set of controller -> MIDI assignments."""

    name: str = "Default"
    schema_version: int = SCHEMA_VERSION
    midi_channel: int = 0                    # 0-15
    deadzone: float = 0.05                   # post-calibration deadzone
    poll_hz: int = 100

    # Button index -> MIDI note number
    buttons: Dict[int, int] = field(default_factory=lambda: {
        0: 60, 1: 62, 2: 64, 3: 65,
        4: 67, 5: 69,
        6: 71, 7: 72, 8: 74,
        9: 76, 10: 77,
    })

    # Axis index -> MIDI CC number (for analog -> CC streams)
    axes: Dict[int, int] = field(default_factory=lambda: {
        0: 3, 1: 4, 2: 5, 3: 6,    # sticks
        4: 1, 5: 2,                # triggers
    })

    # Hat direction -> MIDI note number
    hats: Dict[str, int] = field(default_factory=lambda: {
        "up": 78, "down": 79, "left": 80, "right": 81,
    })

    # V1.1 — Pro features
    left_stick_corners: CornerConfig = field(default_factory=CornerConfig)
    right_stick_corners: CornerConfig = field(default_factory=CornerConfig)
    touchpad: TouchpadConfig = field(default_factory=TouchpadConfig)

    # Reserved for V1.1b adaptive triggers. Effect names come from dualsense
    # protocol: "off", "feedback", "weapon", "vibration", "bow", "galloping",
    # "machine". Left/right configured independently.
    l2_haptic_effect: Optional[str] = None
    r2_haptic_effect: Optional[str] = None

    # ----------------------------------------------------- serialisation

    def to_dict(self) -> dict:
        d = asdict(self)
        # JSON keys must be strings — pygame indices are ints
        d["buttons"] = {str(k): v for k, v in self.buttons.items()}
        d["axes"] = {str(k): v for k, v in self.axes.items()}
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Mapping":
        return cls(
            name=data.get("name", "Default"),
            schema_version=int(data.get("schema_version", 1)),
            midi_channel=int(data.get("midi_channel", 0)),
            deadzone=float(data.get("deadzone", 0.05)),
            poll_hz=int(data.get("poll_hz", 100)),
            buttons={int(k): int(v) for k, v in data.get("buttons", {}).items()},
            axes={int(k): int(v) for k, v in data.get("axes", {}).items()},
            hats={k: int(v) for k, v in data.get("hats", {}).items()},
            left_stick_corners=_corner_from_dict(data.get("left_stick_corners")),
            right_stick_corners=_corner_from_dict(data.get("right_stick_corners")),
            touchpad=_touchpad_from_dict(data.get("touchpad")),
            l2_haptic_effect=data.get("l2_haptic_effect"),
            r2_haptic_effect=data.get("r2_haptic_effect"),
        )


def _corner_from_dict(d: Optional[dict]) -> CornerConfig:
    if not d:
        return CornerConfig()
    cfg = CornerConfig(
        enabled=bool(d.get("enabled", False)),
        n=int(d.get("n", 8)),
        notes=[int(v) for v in d.get("notes", [])],
        r_enter=float(d.get("r_enter", 0.92)),
        r_exit=float(d.get("r_exit", 0.75)),
    )
    cfg.ensure_notes()
    return cfg


def _touchpad_from_dict(d: Optional[dict]) -> TouchpadConfig:
    if not d:
        return TouchpadConfig()
    return TouchpadConfig(
        enabled=bool(d.get("enabled", False)),
        x_cc=int(d.get("x_cc", 16)),
        y_cc=int(d.get("y_cc", 17)),
        require_contact=bool(d.get("require_contact", True)),
    )
