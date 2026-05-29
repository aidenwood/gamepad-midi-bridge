"""Default control mapping + serialisation.

Schema version 4 (V1.3): touchpad shaping options (mode, curves, deadzone,
click_to_arm). V3 added per-trigger shaping + haptic input. V2 (V1.1) added
corner-quantized stick buttons, touchpad XY CCs, and adaptive-trigger haptic
effect names. Old presets without new fields load with sensible defaults
thanks to dict.get.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


SCHEMA_VERSION = 4

# Axes that come from analog sticks (vs triggers). Sticks need drift compensation.
STICK_AXES = frozenset({0, 1, 2, 3})

# Trigger axis indices — used by both the per-tick polling loop and the
# preset migration so we know where to attach a TriggerConfig.
L2_AXIS = 4
R2_AXIS = 5


@dataclass
class TriggerConfig:
    """Per-trigger shaping + gating config for L2 / R2.

    Default is a linear 0 → 127 ramp with no gate — exactly what v2 presets
    do — so a preset loaded without a TriggerConfig behaves identically to
    before the schema bumped.

    Fields:
      - `mode`               : one of `shaping.TRIGGER_MODES`
                               (linear / ceiling / inverted / latch)
      - `ceiling`            : max CC value for "ceiling" mode (0..127)
      - `latch_threshold`    : pressure level (0..1) where latch flips on/off
      - `gate_button`        : optional button INDEX that must be held for
                               this trigger to send MIDI. `None` = no gate
                               (default). e.g. DualSense D-pad down is
                               typically button 12 on pygame/SDL, so set
                               `gate_button=12` to require dpad-down hold
                               before the trigger fires.
      - `gate_release_value` : CC value sent ONCE when the gate releases.
                               Default 0 = silence the receiver. Set to a
                               middle value (e.g. 64) if your downstream
                               expects a "rest at centre" idle state.
    """
    mode: str = "linear"
    ceiling: int = 127
    latch_threshold: float = 0.5
    gate_button: Optional[int] = None
    gate_release_value: int = 0


@dataclass
class StickConfig:
    """Per-stick shaping config (left or right).

    Default values reproduce the legacy stick behaviour exactly (linear, no
    outer clamp, no polar) so old presets load unchanged.

    Fields:
      - `inner_deadzone`  : magnitudes below this snap to 0 (centre)
      - `outer_clamp`     : top fraction of travel that pegs to ±1
      - `curve`           : "linear" | "exponential" | "logarithmic" | "s-curve"
      - `curve_amount`    : 0..1, strength of the curve
      - `polar_mode`      : if True, emit (angle, magnitude) as 2 CCs instead of (X, Y)
      - `polar_angle_cc`  : CC number for the angle when polar_mode is on
      - `polar_mag_cc`    : CC number for the magnitude when polar_mode is on
    """
    inner_deadzone: float = 0.05
    outer_clamp: float = 0.0
    curve: str = "linear"
    curve_amount: float = 0.5
    polar_mode: bool = False
    polar_angle_cc: int = 7   # volume CC by default — meaningless but visible
    polar_mag_cc: int = 8     # balance CC


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
    corner_haptic_feedback: bool = True        # fire short trigger pulse on corner fire

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
class ShiftLayerConfig:
    """Optional shift-layer mapping. When `enabled=True` and the user holds
    `shift_button`, the bridge swaps its active mapping for this overlay.

    Behaviour is purely additive — the overlay only OVERRIDES the keys it
    explicitly defines. Buttons/axes/hats not present in the overlay fall
    through to the base mapping. This lets users say things like 'hold L1
    to remap face buttons to scene 2 cues, but keep the sticks doing the
    same thing'.
    """
    enabled: bool = False
    shift_button: int = -1                # -1 = unset; otherwise a button index
    buttons: Dict[int, int] = field(default_factory=dict)
    axes: Dict[int, int] = field(default_factory=dict)
    hats: Dict[str, int] = field(default_factory=dict)


@dataclass
class BatteryAlertConfig:
    """Emit a MIDI note when DualSense battery drops below a threshold.

    Fires once on threshold breach, resets when battery rises back above
    threshold (so plugging in for a charge re-arms the alert).
    """
    enabled: bool = False
    threshold_percent: int = 15
    note: int = 60
    velocity: int = 100
    channel_override: Optional[int] = None     # uses mapping.midi_channel if None


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

    V4 extensions — shaping options:
      - `mode`           : "absolute" (default, finger position IS CC) or
                           "relative" (finger movement adjusts CC smoothly).
      - `click_to_arm`   : only emit CCs while touchpad button is physically
                           clicked. Useful for avoiding accidental modulation.
      - `inner_deadzone` : centre deadzone in absolute mode (0..0.49). Within
                           this band around centre (0.5), snap to centre.
      - `x_curve`        : response curve for X axis (linear / exponential /
                           logarithmic / s-curve). See shaping.apply_curve.
      - `y_curve`        : response curve for Y axis.
      - `x_curve_amount` : curve aggressiveness for X (0..1).
      - `y_curve_amount` : curve aggressiveness for Y (0..1).
    """
    enabled: bool = False
    x_cc: int = 16                 # primary finger X
    y_cc: int = 17                 # primary finger Y
    b_x_cc: int = 18               # secondary finger X (two-finger mode)
    b_y_cc: int = 19               # secondary finger Y
    two_finger: bool = False       # also send b_x_cc/b_y_cc when a 2nd finger lands
    require_contact: bool = True   # only send CCs while finger is on the pad
    mode: str = "absolute"         # "absolute" | "relative"
    click_to_arm: bool = False     # only emit while touchpad button is clicked
    inner_deadzone: float = 0.0    # 0..0.49 centre deadzone
    x_curve: str = "linear"        # response curve for X (see shaping.apply_curve)
    y_curve: str = "linear"        # response curve for Y
    x_curve_amount: float = 0.5    # curve aggressiveness (0..1)
    y_curve_amount: float = 0.5


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

    # V1.2 — per-trigger shaping (linear / ceiling / inverted / latch). Stays
    # at "linear" defaults so v2 presets behave identically when loaded.
    l2_trigger: TriggerConfig = field(default_factory=TriggerConfig)
    r2_trigger: TriggerConfig = field(default_factory=TriggerConfig)

    # V1.3 — per-stick shaping (deadzone, curves, polar). Defaults preserve
    # legacy stick behaviour exactly so old presets load unchanged.
    left_stick: StickConfig = field(default_factory=StickConfig)
    right_stick: StickConfig = field(default_factory=StickConfig)

    # Incoming-MIDI → adaptive-trigger feedback. Stays disabled by default
    # so V1.1 users don't get their behaviour changed under them.
    haptic_input: HapticInputConfig = field(default_factory=HapticInputConfig)

    # Battery-low alert — fires a MIDI note when battery drops below threshold
    battery_alert: BatteryAlertConfig = field(default_factory=BatteryAlertConfig)

    # Auto-reconnect — show countdown overlay and retry when a controller drops.
    # Default ON so stage performers get the safety net automatically.
    auto_reconnect_enabled: bool = True

    # Shift-layer overlay — hold shift_button to swap the active mapping.
    # Disabled by default so existing presets are completely unaffected.
    shift_layer: ShiftLayerConfig = field(default_factory=ShiftLayerConfig)

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
            l2_trigger=_trigger_from_dict(data.get("l2_trigger")),
            r2_trigger=_trigger_from_dict(data.get("r2_trigger")),
            left_stick=_stick_from_dict(data.get("left_stick")),
            right_stick=_stick_from_dict(data.get("right_stick")),
            battery_alert=_battery_alert_from_dict(data.get("battery_alert")),
            shift_layer=_shift_layer_from_dict(data.get("shift_layer")),
            auto_reconnect_enabled=bool(data.get("auto_reconnect_enabled", True)),
        )


def _trigger_from_dict(d: Optional[dict]) -> TriggerConfig:
    """Hydrate a TriggerConfig from raw dict, defaulting to linear ramp."""
    if not d:
        return TriggerConfig()
    raw_gate = d.get("gate_button")
    gate_button: Optional[int] = None
    if raw_gate is not None:
        try:
            gate_button = int(raw_gate)
            if gate_button < 0:
                gate_button = None
        except (TypeError, ValueError):
            gate_button = None
    return TriggerConfig(
        mode=str(d.get("mode", "linear")),
        ceiling=max(0, min(127, int(d.get("ceiling", 127)))),
        latch_threshold=max(0.0, min(1.0, float(d.get("latch_threshold", 0.5)))),
        gate_button=gate_button,
        gate_release_value=max(0, min(127, int(d.get("gate_release_value", 0)))),
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
        corner_haptic_feedback=bool(d.get("corner_haptic_feedback", True)),
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
        mode=str(d.get("mode", "absolute")),
        click_to_arm=bool(d.get("click_to_arm", False)),
        inner_deadzone=max(0.0, min(0.49, float(d.get("inner_deadzone", 0.0)))),
        x_curve=str(d.get("x_curve", "linear")),
        y_curve=str(d.get("y_curve", "linear")),
        x_curve_amount=max(0.0, min(1.0, float(d.get("x_curve_amount", 0.5)))),
        y_curve_amount=max(0.0, min(1.0, float(d.get("y_curve_amount", 0.5)))),
    )


def _stick_from_dict(d: Optional[dict]) -> StickConfig:
    """Hydrate a StickConfig from raw dict, defaulting to legacy behaviour."""
    if not d:
        return StickConfig()
    # Validate curve against allowed values
    allowed_curves = {"linear", "exponential", "logarithmic", "s-curve"}
    curve = str(d.get("curve", "linear"))
    if curve not in allowed_curves:
        curve = "linear"
    return StickConfig(
        inner_deadzone=max(0.0, min(0.99, float(d.get("inner_deadzone", 0.05)))),
        outer_clamp=max(0.0, min(0.99, float(d.get("outer_clamp", 0.0)))),
        curve=curve,
        curve_amount=max(0.0, min(1.0, float(d.get("curve_amount", 0.5)))),
        polar_mode=bool(d.get("polar_mode", False)),
        polar_angle_cc=int(d.get("polar_angle_cc", 7)),
        polar_mag_cc=int(d.get("polar_mag_cc", 8)),
    )


def _battery_alert_from_dict(d: Optional[dict]) -> BatteryAlertConfig:
    """Hydrate a BatteryAlertConfig from raw dict with sensible defaults."""
    if not d:
        return BatteryAlertConfig()
    raw_override = d.get("channel_override")
    channel_override: Optional[int] = None
    if raw_override is not None:
        try:
            channel_override = int(raw_override)
            if channel_override < 0 or channel_override > 15:
                channel_override = None
        except (TypeError, ValueError):
            channel_override = None
    return BatteryAlertConfig(
        enabled=bool(d.get("enabled", False)),
        threshold_percent=max(0, min(100, int(d.get("threshold_percent", 15)))),
        note=max(0, min(127, int(d.get("note", 60)))),
        velocity=max(0, min(127, int(d.get("velocity", 100)))),
        channel_override=channel_override,
    )


def _shift_layer_from_dict(d: Optional[dict]) -> ShiftLayerConfig:
    """Hydrate a ShiftLayerConfig from raw dict, defaulting to disabled.

    Missing fields fall back to defaults so presets without a `shift_layer`
    key load cleanly (shift layer stays disabled, schema version unchanged).
    """
    if not d:
        return ShiftLayerConfig()
    shift_button = int(d.get("shift_button", -1))
    return ShiftLayerConfig(
        enabled=bool(d.get("enabled", False)),
        shift_button=shift_button,
        buttons={int(k): int(v) for k, v in d.get("buttons", {}).items()},
        axes={int(k): int(v) for k, v in d.get("axes", {}).items()},
        hats={k: int(v) for k, v in d.get("hats", {}).items()},
    )
