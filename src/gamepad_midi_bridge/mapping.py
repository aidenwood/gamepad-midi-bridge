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
class OscConfig:
    """Optional OSC output alongside (or instead of) MIDI.

    OSC addresses are per-control via lookup tables keyed by the same
    button/axis indices the MIDI side uses. Empty maps = no OSC sent for
    those controls. Pro feature.
    """
    enabled: bool = False
    mode: str = "alongside"          # "alongside" (MIDI + OSC) or "only" (OSC only)
    host: str = "127.0.0.1"
    port: int = 7000                 # Resolume default
    button_addresses: Dict[int, str] = field(default_factory=dict)
    axis_addresses: Dict[int, str] = field(default_factory=dict)


@dataclass
class HapticInputBinding:
    """One incoming-MIDI → trigger-effect rule.

    `trigger`     — which adaptive trigger fires: "L2" or "R2".
    `source`      — incoming MIDI message family: "note" or "cc".
    `midi_id`     — note number (0..127) for "note", CC number for "cc".
    `effect`      — one of `dualsense.TRIGGER_EFFECTS` keys (feedback,
                    vibration, weapon, bow, galloping, machine).
    `intensity_scale` — multiplier applied to the normalised velocity/CC
                    value (0..1) before passing to the trigger writer. >1
                    pushes weaker MIDI sources up; <1 dampens hot ones.

    WHY a dataclass per binding rather than a flat dict: lets users add
    many rules without colliding on the same source (e.g. note 36 → L2
    vibration AND note 36 → R2 feedback at the same time). The bridge
    iterates and applies every matching binding.
    """
    trigger: str = "L2"
    source: str = "note"
    midi_id: int = 36
    effect: str = "vibration"
    intensity_scale: float = 1.0


# Default bindings the user gets when they flip `enabled` on for the first
# time. Note 36 / 38 are the GM drum-kit standard for kick / snare so most
# DAWs route drum tracks here without any extra config. CC 71 / 74 are the
# canonical "resonance" / "filter cutoff" CCs from the MMA recommended
# practice list — synths point those at the obvious knobs.
_DEFAULT_HAPTIC_BINDINGS = [
    HapticInputBinding(trigger="L2", source="note", midi_id=36,
                       effect="vibration", intensity_scale=1.0),
    HapticInputBinding(trigger="R2", source="note", midi_id=38,
                       effect="vibration", intensity_scale=1.0),
    HapticInputBinding(trigger="L2", source="cc", midi_id=71,
                       effect="feedback", intensity_scale=1.0),
    HapticInputBinding(trigger="R2", source="cc", midi_id=74,
                       effect="feedback", intensity_scale=1.0),
]


@dataclass
class HapticInputConfig:
    """Incoming-MIDI → adaptive-trigger haptics config.

    `enabled=False` by default so existing users don't suddenly start
    grabbing a virtual MIDI input port without asking. Once enabled the
    bridge opens `INPUT_PORT_NAME` and any bound message fires the matching
    trigger effect, intensity scaled by velocity (notes) or value (CCs).

    `listen_channel = -1` means "every channel" — set to 0..15 to filter.
    """
    enabled: bool = False
    listen_channel: int = -1
    bindings: List[HapticInputBinding] = field(
        default_factory=lambda: list(_DEFAULT_HAPTIC_BINDINGS)
    )


@dataclass
class TouchpadConfig:
    """DualSense touchpad as a 2D MIDI modulator. Pro feature.

    The DualSense reports up to two simultaneous touch contacts. The first
    finger drives x_cc/y_cc; the second finger (when present) drives
    b_x_cc/b_y_cc. Producers can use this as a Kaoss Pad with a "macro"
    second control surface in the same physical space.
    """
    enabled: bool = False
    x_cc: int = 16                 # primary finger X
    y_cc: int = 17                 # primary finger Y
    b_x_cc: int = 18               # secondary finger X (two-finger mode)
    b_y_cc: int = 19               # secondary finger Y
    two_finger: bool = False       # also send b_x_cc/b_y_cc when a 2nd finger lands
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
    osc: OscConfig = field(default_factory=OscConfig)

    # Reserved for V1.1b adaptive triggers. Effect names come from dualsense
    # protocol: "off", "feedback", "weapon", "vibration", "bow", "galloping",
    # "machine". Left/right configured independently.
    l2_haptic_effect: Optional[str] = None
    r2_haptic_effect: Optional[str] = None

    # Incoming-MIDI → adaptive-trigger feedback. Stays disabled by default
    # so V1.1 users don't get their behaviour changed under them.
    haptic_input: HapticInputConfig = field(default_factory=HapticInputConfig)

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
            osc=_osc_from_dict(data.get("osc")),
            l2_haptic_effect=data.get("l2_haptic_effect"),
            r2_haptic_effect=data.get("r2_haptic_effect"),
            haptic_input=_haptic_input_from_dict(data.get("haptic_input")),
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


def _osc_from_dict(d: Optional[dict]) -> OscConfig:
    if not d:
        return OscConfig()
    return OscConfig(
        enabled=bool(d.get("enabled", False)),
        mode=str(d.get("mode", "alongside")),
        host=str(d.get("host", "127.0.0.1")),
        port=int(d.get("port", 7000)),
        button_addresses={int(k): str(v) for k, v in d.get("button_addresses", {}).items()},
        axis_addresses={int(k): str(v) for k, v in d.get("axis_addresses", {}).items()},
    )


def _haptic_input_from_dict(d: Optional[dict]) -> HapticInputConfig:
    """Hydrate HapticInputConfig from JSON. If the key is absent (V1/V1.1
    presets), we return the default config with the stock kick/snare/CC
    bindings BUT `enabled=False` — so loading an old preset never silently
    starts grabbing a virtual MIDI input port."""
    if not d:
        return HapticInputConfig()
    raw_bindings = d.get("bindings") or []
    bindings: List[HapticInputBinding] = []
    for entry in raw_bindings:
        if not isinstance(entry, dict):
            continue
        try:
            bindings.append(HapticInputBinding(
                trigger=str(entry.get("trigger", "L2")).upper(),
                source=str(entry.get("source", "note")).lower(),
                midi_id=int(entry.get("midi_id", 0)),
                effect=str(entry.get("effect", "vibration")).lower(),
                intensity_scale=float(entry.get("intensity_scale", 1.0)),
            ))
        except (TypeError, ValueError):
            # Skip malformed entries rather than failing the whole load —
            # a partially-corrupt preset shouldn't lock the user out.
            continue
    return HapticInputConfig(
        enabled=bool(d.get("enabled", False)),
        listen_channel=int(d.get("listen_channel", -1)),
        bindings=bindings if bindings else list(_DEFAULT_HAPTIC_BINDINGS),
    )


def _touchpad_from_dict(d: Optional[dict]) -> TouchpadConfig:
    if not d:
        return TouchpadConfig()
    return TouchpadConfig(
        enabled=bool(d.get("enabled", False)),
        x_cc=int(d.get("x_cc", 16)),
        y_cc=int(d.get("y_cc", 17)),
        b_x_cc=int(d.get("b_x_cc", 18)),
        b_y_cc=int(d.get("b_y_cc", 19)),
        two_finger=bool(d.get("two_finger", False)),
        require_contact=bool(d.get("require_contact", True)),
    )
