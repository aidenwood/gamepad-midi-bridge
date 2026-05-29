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

# Color tag options for visual show planning
COLOR_TAGS = ("none", "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink")

# Axes that come from analog sticks (vs triggers). Sticks need drift compensation.
STICK_AXES = frozenset({0, 1, 2, 3})

# Trigger axis indices — used by both the per-tick polling loop and the
# preset migration so we know where to attach a TriggerConfig.
L2_AXIS = 4
R2_AXIS = 5



@dataclass
class TriggerAftertouchConfig:
    """Second-stage aftertouch for the PS5 adaptive trigger.

    Once pressure exceeds ``threshold`` the bridge emits channel aftertouch
    (0xD0) proportional to how far past the threshold the trigger is pressed.
    ``channel_override=-1`` means use the mapping's global midi_channel.
    """

    enabled: bool = False
    threshold: float = 0.85   # 0..1 pressure where AT engages
    channel_override: int = -1


@dataclass
class StickFlickConfig:
    """Velocity-sensitive note-on from rapid stick movement.

    When the stick axis crosses ``speed_threshold`` (axis units/sec) and the
    axis magnitude passes 0.7 in that direction (rising edge), a note fires.
    Different directional notes let sticks act like 4-way drum pads.
    """

    enabled: bool = False
    note_pos_x: int = 64       # note fired on right-flick (+X)
    note_neg_x: int = 65       # left-flick (-X)
    note_pos_y: int = 66       # up-flick
    note_neg_y: int = 67       # down-flick
    velocity_min: int = 30
    velocity_max: int = 127
    speed_threshold: float = 4.0   # axis units / second minimum speed

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
      - `tactile_click`      : if True (default), fire 30ms haptic feedback
                               on the same trigger when latch mode crosses
                               the threshold (toggle point). Gives tactile
                               confirmation of when the latch flips.
    """
    mode: str = "linear"
    ceiling: int = 127
    latch_threshold: float = 0.5
    gate_button: Optional[int] = None
    gate_release_value: int = 0
    tactile_click: bool = True
    aftertouch: TriggerAftertouchConfig = field(default_factory=TriggerAftertouchConfig)


@dataclass
class PolyAftertouchConfig:
    """Polyphonic Aftertouch (PolyAT) emission for held buttons.

    When a button is held and poly_aftertouch is enabled, the bridge sends
    MIDI Polyphonic Aftertouch messages (0xA0) scaled from the configured
    pressure source. Each held note gets its own pressure stream.

    Fields:
      - `enabled`            : master switch (default False).
      - `pressure_source`    : where to read pressure: "left_stick_mag",
                               "right_stick_mag", "l2", or "r2".
                               Defaults to "left_stick_mag".
    """
    enabled: bool = False
    pressure_source: str = "left_stick_mag"


@dataclass
class ButtonConfig:
    """Per-button gating config for any face button.

    Optional modifier gate: the button is silent unless `gate_button` is held.
    On release edge we send `gate_release_value` exactly once.

    Fields:
      - `gate_button`        : optional button INDEX that must be held for
                               this button to send MIDI. `None` = no gate
                               (default).
      - `gate_release_value` : velocity to send on release edge (0 = note-off).
                               Default 0 = standard note-off.
      - `velocity`           : static velocity (1..127) sent for note-on when
                               > 0; else 100 (default). DualSense face buttons
                               are binary (no pressure), so this is a fixed
                               override per button, not a curve.
      - `poly_aftertouch`    : optional PolyAftertouchConfig for expressive
                               pressure control on held notes. Disabled by
                               default.
      - `velocity_jitter`    : optional ±N jitter on velocity (0..20). Adds
                               random ±N to the velocity before clamping to
                               0..127. Makes drum patterns feel less mechanical.
      - `timing_jitter_ms`   : optional delay jitter in milliseconds (0..15).
                               Defers the note-on by a random amount 0..N ms
                               using QTimer.singleShot. Humanizes timing.
    """
    gate_button: Optional[int] = None
    gate_release_value: int = 0
    velocity: int = 100
    poly_aftertouch: PolyAftertouchConfig = field(default_factory=PolyAftertouchConfig)
    velocity_jitter: int = 0       # 0..20
    timing_jitter_ms: int = 0      # 0..15


@dataclass
class StickLfoConfig:
    """Per-axis free-running LFO modulator.

    When enabled the LFO drives the CC autonomously at rest. When the user
    moves the stick the user value is combined with the LFO according to
    blend_mode.

    Fields:
      - `enabled`           : master switch (default False — no LFO).
      - `waveform`          : "sine" | "triangle" | "square" | "saw" | "random".
                              Unknown values fall back to "sine".
      - `rate_hz`           : LFO frequency in Hz (0.01..20).
      - `depth`             : blend factor 0..1. Scales the LFO contribution.
      - `phase_lock_to_bpm` : if True, rate = mapping.midi_clock.bpm / 60 * subdivision.
                              subdivision is expressed as a beat fraction (e.g. 1.0 = quarter).
      - `blend_mode`        : how user input and LFO combine.
                              "add"      — lfo*depth + user (clips to ±1).
                              "replace"  — lfo*depth when user is near 0, user otherwise.
                              "multiply" — user * (1 + lfo*depth - 0.5).
                              Unknown values fall back to "add".
    """
    enabled: bool = False
    waveform: str = "sine"       # "sine" | "triangle" | "square" | "saw" | "random"
    rate_hz: float = 0.5         # 0.01..20
    depth: float = 0.5           # 0..1
    phase_lock_to_bpm: bool = False
    blend_mode: str = "add"      # "add" | "replace" | "multiply"


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
      - `cc_smoothing_ms` : CC interpolation time in ms (0..1000). 0 = off;
                            otherwise CC changes interpolate over N ms instead
                            of jumping in steps. Useful for sticks producing
                            stepped 7-bit MIDI for filter sweeps.
    """
    inner_deadzone: float = 0.05
    outer_clamp: float = 0.0
    curve: str = "linear"
    curve_amount: float = 0.5
    polar_mode: bool = False
    polar_angle_cc: int = 7   # volume CC by default — meaningless but visible
    polar_mag_cc: int = 8     # balance CC
    cc_smoothing_ms: int = 0
    flick: StickFlickConfig = field(default_factory=StickFlickConfig)
    # Random/chance modulator (feature #A) — when enabled, samples a random CC
    # value at random_mod_rate_hz and sends it to random_mod_cc, optionally
    # smoothed over random_mod_smoothing_ms.
    random_mod_enabled: bool = False
    random_mod_cc: int = 16
    random_mod_rate_hz: float = 2.0
    random_mod_smoothing_ms: int = 200
    # LFO modulator — free-running waveform added to / replacing user input.
    lfo: StickLfoConfig = field(default_factory=StickLfoConfig)
    # Pitch bend — 14-bit MIDI pitch bend from stick axis
    pitch_bend_enabled: bool = False
    pitch_bend_axis: str = "x"       # "x" or "y"
    pitch_bend_range_semis: int = 2  # informational; full 14-bit range always used


@dataclass
class CornerConfig:
    """Edge-quantization config for one analog stick. Pro feature.

    `notes` should have exactly `n` entries — the MIDI note fired for each
    sector. Sector 0 is the +X cardinal (rightward); sectors advance clockwise.

    When `scale_quantize_enabled` is True the `notes` list is ignored and
    sectors are mapped to consecutive scale degrees instead — the N sectors
    walk up the chosen scale starting from `scale_root`, wrapping into the
    next octave when the scale runs out of degrees.
    """
    enabled: bool = False
    n: int = 8                                  # 4, 8, or 16
    notes: List[int] = field(default_factory=list)
    r_enter: float = 0.92
    r_exit: float = 0.75
    corner_haptic_feedback: bool = True        # fire short trigger pulse on corner fire

    # Scale-quantize (optional) — added in feature #24
    scale_quantize_enabled: bool = False
    scale_root: int = 60       # MIDI note (60 = C4)
    scale_name: str = "major"  # one of scales.SCALES

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
class OscHapticBinding:
    """One incoming OSC message → trigger haptic effect.

    Matches the OSC `address` exactly (e.g. /resolume/composition/layer/1/clip/3/connect).
    On match, fires the configured effect on the named trigger, scaled by
    the first OSC argument if it's a float 0..1.
    """
    address: str = "/midi/note/36"
    trigger: str = "L2"                  # "L2" or "R2"
    effect: str = "vibration"            # any dualsense.TRIGGER_EFFECTS key
    intensity_scale: float = 1.0


@dataclass
class OscConfig:
    """Optional OSC output alongside (or instead of) MIDI.

    OSC addresses are per-control via lookup tables keyed by the same
    button/axis indices the MIDI side uses. Empty maps = no OSC sent for
    those controls. Pro feature.

    listen_enabled / listen_port / listen_bindings: receive incoming OSC
    messages and route them to adaptive-trigger haptic effects (feature #16).
    """
    enabled: bool = False
    mode: str = "alongside"          # "alongside" (MIDI + OSC) or "only" (OSC only)
    host: str = "127.0.0.1"
    port: int = 7000                 # Resolume default
    button_addresses: Dict[int, str] = field(default_factory=dict)
    axis_addresses: Dict[int, str] = field(default_factory=dict)
    listen_enabled: bool = False
    listen_port: int = 7001          # different from output port to avoid loopback
    listen_bindings: List["OscHapticBinding"] = field(default_factory=list)


@dataclass
class MidiClockConfig:
    """MIDI clock send + tap-tempo config.

    When `enabled=True` the bridge emits MIDI clock pulses (0xF8) at 24 PPQN
    calculated from `bpm`. The controller can also drive tempo via tap-tempo
    and optionally send MIDI Start (0xFA) / Stop (0xFC) messages.

    Fields:
      - `enabled`         : master switch (default False so existing presets
                            are completely unaffected).
      - `bpm`             : current clock tempo in beats per minute (60..240).
      - `send_start_stop` : if True, designated buttons send 0xFA / 0xFC.
      - `tap_button`      : button index that records tap timestamps. -1 = off.
      - `start_button`    : button index that sends MIDI Start. -1 = off.
      - `stop_button`     : button index that sends MIDI Stop. -1 = off.
    """
    enabled: bool = False
    bpm: float = 120.0
    send_start_stop: bool = True
    tap_button: int = -1       # -1 = no tap-tempo
    start_button: int = -1
    stop_button: int = -1


@dataclass
class ProgramChangeConfig:
    """Bind incoming MIDI Program Change messages to preset loads.

    When `enabled=True` and a PC message arrives on `listen_channel` (or
    any channel if listen_channel=-1), the matching preset slug is loaded
    and made active. Off by default.

    bindings maps a PC number (0..127) to a preset slug.
    """
    enabled: bool = False
    listen_channel: int = -1   # -1 = any channel
    bindings: Dict[int, str] = field(default_factory=dict)  # PC# -> preset slug


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



QUANTIZE_GRIDS = ("1/4", "1/8", "1/8t", "1/16", "1/16t", "1/32")


@dataclass
class QuantizeConfig:
    """Beat-grid quantization for button note-on events.

    When enabled, note-on events are delayed to the nearest grid boundary
    so a sloppy player still lands on the beat.

    Fields:
      - `enabled`           : master switch (default False — no delay).
      - `grid`              : grid division — one of QUANTIZE_GRIDS.
                              Unknown values fall back to "1/16".
      - `swing_pct`         : swing percentage (0..50). Adds swing_pct% of
                              the grid duration to off-beat boundaries so
                              alternating 16ths get a shuffled feel.
      - `quantize_buttons`  : route button note-ons through the grid (True).
      - `quantize_cc`       : route CC changes through the grid (False by
                              default — sticks/triggers usually feel laggy).
    """
    enabled: bool = False
    grid: str = "1/16"
    swing_pct: int = 0
    quantize_buttons: bool = True
    quantize_cc: bool = False


def _quantize_from_dict(d: Optional[dict]) -> "QuantizeConfig":
    """Hydrate a QuantizeConfig from raw dict, defaulting to disabled."""
    if not d:
        return QuantizeConfig()
    raw_grid = str(d.get("grid", "1/16"))
    grid = raw_grid if raw_grid in QUANTIZE_GRIDS else "1/16"
    swing = max(0, min(50, int(d.get("swing_pct", 0))))
    return QuantizeConfig(
        enabled=bool(d.get("enabled", False)),
        grid=grid,
        swing_pct=swing,
        quantize_buttons=bool(d.get("quantize_buttons", True)),
        quantize_cc=bool(d.get("quantize_cc", False)),
    )


@dataclass
class RtpMidiConfig:
    """Optional RTP-MIDI (AppleMIDI / Network MIDI) output.

    When enabled, every MIDI message sent to the local virtual port is ALSO
    forwarded as a UDP RTP-MIDI packet to peer_host:peer_port.  No
    session negotiation -- the receiver must already be in listening mode
    (e.g. iOS GarageBand "Network Session", macOS Audio MIDI Setup,
    or any DAW with an RTP-MIDI input).

    Fields:
      - enabled      : master switch (default False -- no UDP traffic).
      - peer_host    : IPv4 address of the receiver (default 127.0.0.1).
      - peer_port    : UDP port, typically 5004 (RTP-MIDI default).
      - session_name : human-readable label shown in session logs.
    """
    enabled: bool = False
    peer_host: str = "127.0.0.1"
    peer_port: int = 5004
    session_name: str = "UCM Bridge"

@dataclass
class PassthroughConfig:
    """Optional MIDI passthrough/thru mode.

    When enabled, opens `input_port_name` as a second MIDI input and forwards
    every incoming message to the bridge's existing output port.  A MIDI
    keyboard can therefore layer with the DualSense: both arrive at the same
    DAW track without extra routing.

    Fields:
      - `enabled`            : master switch (default False — no extra port opened).
      - `input_port_name`    : rtmidi input port to listen on (empty = disabled).
      - `transpose_semitones`: semitones to add to every Note-On/Off data1 byte
                               before forwarding (-24..+24, 0 = unchanged).
      - `channel_remap`      : -1 = preserve original channel; 0..15 = force
                               this channel on every forwarded message.
      - `pass_cc`            : forward Control Change messages (0xB0).
      - `pass_notes`         : forward Note-On (0x90) and Note-Off (0x80).
      - `pass_other`         : forward everything else (PC, PB, aftertouch, …).
    """
    enabled: bool = False
    input_port_name: str = ""
    transpose_semitones: int = 0        # clamped -24..+24
    channel_remap: int = -1             # -1 = preserve; 0..15 = force
    pass_cc: bool = True
    pass_notes: bool = True
    pass_other: bool = False


@dataclass
class SetlistConfig:
    """Ordered list of preset slugs for live performance step-through.

    Two designated buttons advance (next_button) or retreat (prev_button)
    through the list. On each step the bridge emits `setlist_step` so the
    main window can load the preset and apply it immediately.

    Fields:
      - `enabled`      : master switch (default False).
      - `name`         : human-readable label for this setlist.
      - `presets`      : ordered list of preset slugs.
      - `next_button`  : button index that steps forward. -1 = unset.
      - `prev_button`  : button index that steps backward. -1 = unset.
      - `wrap`         : if True, wrap around at both ends.
    """
    enabled: bool = False
    name: str = "Setlist"
    presets: List[str] = field(default_factory=list)
    next_button: int = -1
    prev_button: int = -1
    wrap: bool = True


@dataclass
class MacroEvent:
    """One recorded MIDI message with a relative timestamp."""
    delay_ms: int           # ms since macro start (0 on first event)
    status: int             # MIDI status byte (message type | channel)
    data1: int              # note / CC number
    data2: int              # velocity / CC value


@dataclass
class Macro:
    """A recorded sequence of MIDI messages that can be replayed on a button press.

    events are ordered by delay_ms — playback schedules each send at its
    absolute offset from the start of replay so the original inter-event
    timing is preserved exactly.
    duration_ms mirrors the delay_ms of the last event so callers can easily
    check the total replay length without iterating.
    """
    name: str
    events: List[MacroEvent] = field(default_factory=list)
    duration_ms: int = 0
    # Arpeggiator mode (feature #B) — when enabled, the macro replays
    # continuously at arp_rate_hz while the bound button is held; releases
    # stop playback and send note-off for any held notes.
    arp_mode: bool = False
    arp_rate_hz: float = 8.0
    arp_loop: bool = True


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
    
    `guard_feedback_loop=True` detects when the DAW echoes our outbound CCs
    back and drops them to prevent feedback loops.
    """
    enabled: bool = False
    listen_channel: int = -1
    guard_feedback_loop: bool = True
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

    Zone mode (drum pad grid):
      - `zone_mode`      : if True, divide touchpad into NxN grid; each zone
                           fires a different MIDI note (like an MPC drum pad).
      - `zone_grid`      : grid size N (1..4); so 2 = 2x2 grid (4 zones),
                           3 = 3x3 (9 zones), 4 = 4x4 (16 zones).
      - `zone_notes`     : list of MIDI notes corresponding to zones (left-to-
                           right, top-to-bottom linear order). If shorter than
                           zone_grid², padded with the last value.
      - `zone_velocity`  : velocity (0..127) when firing zone notes.
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
    zone_mode: bool = False        # if True, use NxN grid for note-on/off
    zone_grid: int = 2            # grid size N (1..4)
    zone_notes: List[int] = field(default_factory=lambda: [36, 38, 40, 42])  # default 2x2 grid notes
    zone_velocity: int = 100       # velocity for zone notes
    gesture_enabled: bool = False  # detect swipes/pinches
    swipe_up_note: int = 60        # note fired on swipe up
    swipe_down_note: int = 61      # note fired on swipe down
    swipe_left_note: int = 62      # note fired on swipe left
    swipe_right_note: int = 63     # note fired on swipe right
    pinch_in_note: int = 64        # note fired on pinch inward
    pinch_out_note: int = 65       # note fired on pinch outward
    gesture_velocity: int = 100    # velocity for gesture notes
    swipe_min_distance: float = 0.3  # 0..1 normalised, min distance to register


@dataclass
class PatternRecorderConfig:
    """Configuration for the pattern/loop recorder.

    Different from the Macro recorder: patterns play continuously at a fixed
    length while held, and the user can overdub new events on top while the
    loop runs.

    Fields:
      - ``enabled``           : master switch (default False).
      - ``record_button``     : hold to record. -1 = unset.
      - ``overdub_button``    : hold while loop is playing to layer new events.
      - ``cancel_button``     : press to stop the running loop. -1 = unset.
      - ``loop_length_bars``  : loop length in bars (default 1).
      - ``quantize_to_grid``  : snap recorded events to the 1/16 grid.
    """
    enabled: bool = False
    record_button: int = -1
    overdub_button: int = -1
    cancel_button: int = -1
    loop_length_bars: int = 1
    quantize_to_grid: bool = True


@dataclass
class Midi2Config:
    """MIDI 2.0 / Universal MIDI Packet (UMP) emission config.

    When ``enabled=True`` the bridge attempts to emit 32-bit UMP-formatted
    packets instead of MIDI 1.0 3-byte messages.  rtmidi does not natively
    understand UMP framing; the bridge probes the port on startup and falls
    back to MIDI 1.0 transparently if the port rejects UMP (logged once).

    Fields:
      - ``enabled``          : master switch (default False — pure MIDI 1.0).
      - ``group``            : UMP group number 0..15 (default 0).
      - ``fallback_to_midi1``: if True (default), silently revert to MIDI 1.0
                               when the port does not accept UMP packets.
    """
    enabled: bool = False
    group: int = 0          # 0..15 UMP group
    fallback_to_midi1: bool = True


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

    gesture_enabled: bool = False  # detect swipes/pinches
    swipe_up_note: int = 60        # note fired on swipe up
    swipe_down_note: int = 61      # note fired on swipe down
    swipe_left_note: int = 62      # note fired on swipe left
    swipe_right_note: int = 63     # note fired on swipe right
    pinch_in_note: int = 64        # note fired on pinch inward
    pinch_out_note: int = 65       # note fired on pinch outward
    gesture_velocity: int = 100    # velocity for gesture notes
    swipe_min_distance: float = 0.3  # 0..1 normalised, min distance to register

    # Hat direction -> MIDI note number
    hats: Dict[str, int] = field(default_factory=lambda: {
        "up": 78, "down": 79, "left": 80, "right": 81,
    })

    # Per-control channel overrides (sparse maps, defaults to midi_channel)
    button_channels: Dict[int, int] = field(default_factory=dict)
    axis_channels: Dict[int, int] = field(default_factory=dict)
    hat_channels: Dict[str, int] = field(default_factory=dict)

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

    # Per-button gating config (sparse map indexed by button index).
    # Missing entry = no gate. Additive to v4 — old presets load unchanged.
    button_configs: Dict[int, ButtonConfig] = field(default_factory=dict)

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

    # A/B Compare — hold ab_compare_button (or keyboard Tab) to hot-swap to
    # a completely different preset for the held duration, then snap back.
    # Unlike shift-layer (partial overlay), this swaps the WHOLE mapping.
    # Disabled by default; ab_compare_button=-1 means unset.
    ab_compare_enabled: bool = False
    ab_compare_button: int = -1          # -1 = unset, otherwise button index
    ab_b_preset_slug: Optional[str] = None  # slug of the B preset to load

    # Headless/background mode config (feature #12)
    always_background_on_launch: bool = False  # if True, start with --background

    # Per-preset MIDI port name override (feature #23)
    # If set, BridgeWorker uses this instead of the default "Universal Controller MIDI"
    port_name_override: Optional[str] = None

    # Program Change → preset hot-swap (feature #15). Disabled by default so
    # existing users don't get DAW PC messages hijacking their controller config.
    program_change: ProgramChangeConfig = field(default_factory=ProgramChangeConfig)

    # MIDI clock send + tap-tempo. Off by default so existing presets are
    # completely unaffected. When enabled, the bridge emits 0xF8 at 24 PPQN.
    midi_clock: MidiClockConfig = field(default_factory=MidiClockConfig)

    # Theme preference — "dark", "light", or "system" (detect OS preference).
    # Defaults to "system" for automatic OS-aware theming.
    theme: str = "system"

    # V1.4 — macro recorder. macros is the library of recorded sequences;
    # macro_bindings maps button index → macro name for one-press replay.
    macros: List[Macro] = field(default_factory=list)
    macro_bindings: Dict[int, str] = field(default_factory=dict)

    # Setlist — ordered preset step-through for live performance. Disabled by
    # default so existing presets are completely unaffected. Schema v5 compatible
    # (additive-only; old loaders ignore the key).
    setlist: SetlistConfig = field(default_factory=SetlistConfig)

    # MIDI passthrough — forward a second MIDI input source to the bridge's
    # output port. Disabled by default; users enable via JSON for now (UI TBD).
    passthrough: "PassthroughConfig" = field(default_factory=lambda: PassthroughConfig())

    # RTP-MIDI (Network MIDI / AppleMIDI) output — stream over LAN to remote
    # receivers. Disabled by default; no UDP traffic unless explicitly enabled.
    rtp_midi: RtpMidiConfig = field(default_factory=RtpMidiConfig)

    # Beat-grid quantization — defer button note-ons to the nearest grid
    # boundary so sloppy playing lands on the beat. Disabled by default.
    quantize: QuantizeConfig = field(default_factory=QuantizeConfig)

    # Color tag for visual show planning (one of COLOR_TAGS)
    color_tag: str = "none"

    # Favourite flag for quick access in setlist / preset manager
    favourite: bool = False

    # MIDI 2.0 / UMP emission — disabled by default so all existing presets
    # continue to emit standard MIDI 1.0 without any change.
    midi2: Midi2Config = field(default_factory=Midi2Config)

    # Pattern recorder — loop-based recording with overdub. Disabled by default
    # so existing presets are completely unaffected. Additive-only schema field.
    pattern_recorder: PatternRecorderConfig = field(default_factory=PatternRecorderConfig)

    # ----------------------------------------------------- serialisation

    def to_dict(self) -> dict:
        d = asdict(self)
        # JSON keys must be strings — pygame indices are ints
        d["buttons"] = {str(k): v for k, v in self.buttons.items()}
        d["axes"] = {str(k): v for k, v in self.axes.items()}
        d["button_channels"] = {str(k): v for k, v in self.button_channels.items()}
        d["axis_channels"] = {str(k): v for k, v in self.axis_channels.items()}
        # Serialize sparse button_configs dict
        d["button_configs"] = {
            str(k): asdict(v) for k, v in self.button_configs.items()
        }
        # Ensure port_name_override is included
        if self.port_name_override:
            d["port_name_override"] = self.port_name_override
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Mapping":
        # Validate color_tag
        raw_color = str(data.get("color_tag", "none"))
        color_tag = raw_color if raw_color in COLOR_TAGS else "none"

        return cls(
            name=data.get("name", "Default"),
            schema_version=int(data.get("schema_version", 1)),
            midi_channel=int(data.get("midi_channel", 0)),
            deadzone=float(data.get("deadzone", 0.05)),
            poll_hz=int(data.get("poll_hz", 100)),
            buttons={int(k): int(v) for k, v in data.get("buttons", {}).items()},
            axes={int(k): int(v) for k, v in data.get("axes", {}).items()},
            hats={k: int(v) for k, v in data.get("hats", {}).items()},
            button_channels={int(k): max(0, min(15, int(v))) for k, v in data.get("button_channels", {}).items()},
            axis_channels={int(k): max(0, min(15, int(v))) for k, v in data.get("axis_channels", {}).items()},
            hat_channels={k: max(0, min(15, int(v))) for k, v in data.get("hat_channels", {}).items()},
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
            button_configs=_button_configs_from_dict(data.get("button_configs")),
            battery_alert=_battery_alert_from_dict(data.get("battery_alert")),
            shift_layer=_shift_layer_from_dict(data.get("shift_layer")),
            auto_reconnect_enabled=bool(data.get("auto_reconnect_enabled", True)),
            ab_compare_enabled=bool(data.get("ab_compare_enabled", False)),
            ab_compare_button=int(data.get("ab_compare_button", -1)),
            ab_b_preset_slug=data.get("ab_b_preset_slug") or None,
            always_background_on_launch=bool(data.get("always_background_on_launch", False)),
            port_name_override=data.get("port_name_override") or None,
            program_change=_program_change_from_dict(data.get("program_change")),
            midi_clock=_midi_clock_from_dict(data.get("midi_clock")),
            theme=str(data.get("theme", "system")),
            macros=_macros_from_dict(data.get("macros")),
            macro_bindings={int(k): str(v) for k, v in data.get("macro_bindings", {}).items()},
            setlist=_setlist_config_from_dict(data.get("setlist")),
            passthrough=_passthrough_from_dict(data.get("passthrough")),
            rtp_midi=_rtp_midi_from_dict(data.get("rtp_midi")),
            quantize=_quantize_from_dict(data.get("quantize")),
            color_tag=color_tag,
            favourite=bool(data.get("favourite", False)),
            midi2=_midi2_from_dict(data.get("midi2")),
            pattern_recorder=_pattern_recorder_from_dict(data.get("pattern_recorder")),
        )


def _trigger_aftertouch_from_dict(d: Optional[dict]) -> TriggerAftertouchConfig:
    """Hydrate a TriggerAftertouchConfig, defaulting to disabled."""
    if not d:
        return TriggerAftertouchConfig()
    return TriggerAftertouchConfig(
        enabled=bool(d.get("enabled", False)),
        threshold=max(0.0, min(1.0, float(d.get("threshold", 0.85)))),
        channel_override=int(d.get("channel_override", -1)),
    )


def _stick_flick_from_dict(d: Optional[dict]) -> StickFlickConfig:
    """Hydrate a StickFlickConfig, defaulting to disabled."""
    if not d:
        return StickFlickConfig()
    return StickFlickConfig(
        enabled=bool(d.get("enabled", False)),
        note_pos_x=max(0, min(127, int(d.get("note_pos_x", 64)))),
        note_neg_x=max(0, min(127, int(d.get("note_neg_x", 65)))),
        note_pos_y=max(0, min(127, int(d.get("note_pos_y", 66)))),
        note_neg_y=max(0, min(127, int(d.get("note_neg_y", 67)))),
        velocity_min=max(0, min(127, int(d.get("velocity_min", 30)))),
        velocity_max=max(0, min(127, int(d.get("velocity_max", 127)))),
        speed_threshold=max(0.0, float(d.get("speed_threshold", 4.0))),
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
        tactile_click=bool(d.get("tactile_click", True)),
        aftertouch=_trigger_aftertouch_from_dict(d.get("aftertouch")),
    )


def _poly_aftertouch_from_dict(d: Optional[dict]) -> PolyAftertouchConfig:
    """Hydrate a PolyAftertouchConfig from raw dict, defaulting to disabled."""
    if not d:
        return PolyAftertouchConfig()
    # Validate pressure_source is one of the allowed values
    valid_sources = {"left_stick_mag", "right_stick_mag", "l2", "r2"}
    pressure_source = str(d.get("pressure_source", "left_stick_mag"))
    if pressure_source not in valid_sources:
        pressure_source = "left_stick_mag"
    return PolyAftertouchConfig(
        enabled=bool(d.get("enabled", False)),
        pressure_source=pressure_source,
    )


def _button_config_from_dict(d: Optional[dict]) -> ButtonConfig:
    """Hydrate a ButtonConfig from raw dict."""
    if not d:
        return ButtonConfig()
    raw_gate = d.get("gate_button")
    gate_button: Optional[int] = None
    if raw_gate is not None:
        try:
            gate_button = int(raw_gate)
            if gate_button < 0:
                gate_button = None
        except (TypeError, ValueError):
            gate_button = None
    return ButtonConfig(
        gate_button=gate_button,
        gate_release_value=max(0, min(127, int(d.get("gate_release_value", 0)))),
        velocity=max(0, min(127, int(d.get("velocity", 100)))),
        poly_aftertouch=_poly_aftertouch_from_dict(d.get("poly_aftertouch")),
        velocity_jitter=max(0, min(20, int(d.get("velocity_jitter", 0)))),
        timing_jitter_ms=max(0, min(15, int(d.get("timing_jitter_ms", 0)))),
    )


def _button_configs_from_dict(d: Optional[dict]) -> Dict[int, ButtonConfig]:
    """Hydrate the sparse button_configs dict from raw JSON.

    d should be a dict with string keys (button indices) mapping to
    ButtonConfig dicts. Returns a dict with int keys.
    """
    if not d:
        return {}
    result: Dict[int, ButtonConfig] = {}
    for str_idx, cfg_dict in d.items():
        try:
            idx = int(str_idx)
            if isinstance(cfg_dict, dict):
                result[idx] = _button_config_from_dict(cfg_dict)
        except (TypeError, ValueError):
            # Skip malformed entries
            continue
    return result


def _corner_from_dict(d: Optional[dict]) -> CornerConfig:
    if not d:
        return CornerConfig()
    scale_root = max(0, min(127, int(d.get("scale_root", 60))))
    scale_name = str(d.get("scale_name", "major"))
    cfg = CornerConfig(
        enabled=bool(d.get("enabled", False)),
        n=int(d.get("n", 8)),
        notes=[int(v) for v in d.get("notes", [])],
        r_enter=float(d.get("r_enter", 0.92)),
        r_exit=float(d.get("r_exit", 0.75)),
        corner_haptic_feedback=bool(d.get("corner_haptic_feedback", True)),
        scale_quantize_enabled=bool(d.get("scale_quantize_enabled", False)),
        scale_root=scale_root,
        scale_name=scale_name,
    )
    cfg.ensure_notes()
    return cfg


def _osc_haptic_binding_from_dict(d: dict) -> OscHapticBinding:
    """Hydrate one OscHapticBinding from a raw dict."""
    return OscHapticBinding(
        address=str(d.get("address", "/midi/note/36")),
        trigger=str(d.get("trigger", "L2")).upper(),
        effect=str(d.get("effect", "vibration")).lower(),
        intensity_scale=float(d.get("intensity_scale", 1.0)),
    )


def _osc_from_dict(d: Optional[dict]) -> OscConfig:
    if not d:
        return OscConfig()
    raw_bindings = d.get("listen_bindings") or []
    listen_bindings: List[OscHapticBinding] = []
    for entry in raw_bindings:
        if not isinstance(entry, dict):
            continue
        try:
            listen_bindings.append(_osc_haptic_binding_from_dict(entry))
        except (TypeError, ValueError):
            continue
    return OscConfig(
        enabled=bool(d.get("enabled", False)),
        mode=str(d.get("mode", "alongside")),
        host=str(d.get("host", "127.0.0.1")),
        port=int(d.get("port", 7000)),
        button_addresses={int(k): str(v) for k, v in d.get("button_addresses", {}).items()},
        axis_addresses={int(k): str(v) for k, v in d.get("axis_addresses", {}).items()},
        listen_enabled=bool(d.get("listen_enabled", False)),
        listen_port=int(d.get("listen_port", 7001)),
        listen_bindings=listen_bindings,
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

    # Parse zone_notes list with safe int conversion
    zone_notes_raw = d.get("zone_notes", [36, 38, 40, 42])
    zone_notes: List[int] = []
    if isinstance(zone_notes_raw, list):
        for note in zone_notes_raw:
            try:
                zone_notes.append(max(0, min(127, int(note))))
            except (TypeError, ValueError):
                pass
    if not zone_notes:
        zone_notes = [36, 38, 40, 42]

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
        zone_mode=bool(d.get("zone_mode", False)),
        zone_grid=max(1, min(4, int(d.get("zone_grid", 2)))),
        zone_notes=zone_notes,
        zone_velocity=max(0, min(127, int(d.get("zone_velocity", 100)))),
        gesture_enabled=bool(d.get("gesture_enabled", False)),
        swipe_up_note=max(0, min(127, int(d.get("swipe_up_note", 60)))),
        swipe_down_note=max(0, min(127, int(d.get("swipe_down_note", 61)))),
        swipe_left_note=max(0, min(127, int(d.get("swipe_left_note", 62)))),
        swipe_right_note=max(0, min(127, int(d.get("swipe_right_note", 63)))),
        pinch_in_note=max(0, min(127, int(d.get("pinch_in_note", 64)))),
        pinch_out_note=max(0, min(127, int(d.get("pinch_out_note", 65)))),
        gesture_velocity=max(0, min(127, int(d.get("gesture_velocity", 100)))),
        swipe_min_distance=max(0.0, min(1.0, float(d.get("swipe_min_distance", 0.3)))),
    )


def _stick_lfo_from_dict(d: Optional[dict]) -> "StickLfoConfig":
    """Hydrate a StickLfoConfig from raw dict, defaulting to disabled."""
    if not d:
        return StickLfoConfig()
    allowed_waveforms = {"sine", "triangle", "square", "saw", "random"}
    waveform = str(d.get("waveform", "sine"))
    if waveform not in allowed_waveforms:
        waveform = "sine"
    allowed_blend = {"add", "replace", "multiply"}
    blend_mode = str(d.get("blend_mode", "add"))
    if blend_mode not in allowed_blend:
        blend_mode = "add"
    return StickLfoConfig(
        enabled=bool(d.get("enabled", False)),
        waveform=waveform,
        rate_hz=max(0.01, min(20.0, float(d.get("rate_hz", 0.5)))),
        depth=max(0.0, min(1.0, float(d.get("depth", 0.5)))),
        phase_lock_to_bpm=bool(d.get("phase_lock_to_bpm", False)),
        blend_mode=blend_mode,
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
        cc_smoothing_ms=max(0, min(1000, int(d.get("cc_smoothing_ms", 0)))),
        flick=_stick_flick_from_dict(d.get("flick")),
        random_mod_enabled=bool(d.get("random_mod_enabled", False)),
        random_mod_cc=max(0, min(127, int(d.get("random_mod_cc", 16)))),
        random_mod_rate_hz=max(0.01, float(d.get("random_mod_rate_hz", 2.0))),
        random_mod_smoothing_ms=max(0, int(d.get("random_mod_smoothing_ms", 200))),
        lfo=_stick_lfo_from_dict(d.get("lfo")),
        pitch_bend_enabled=bool(d.get("pitch_bend_enabled", False)),
        pitch_bend_axis=str(d.get("pitch_bend_axis", "x")) if str(d.get("pitch_bend_axis", "x")) in {"x", "y"} else "x",
        pitch_bend_range_semis=max(1, min(24, int(d.get("pitch_bend_range_semis", 2)))),
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


def _midi_clock_from_dict(d: Optional[dict]) -> MidiClockConfig:
    """Hydrate a MidiClockConfig from raw dict, defaulting to disabled."""
    if not d:
        return MidiClockConfig()
    return MidiClockConfig(
        enabled=bool(d.get("enabled", False)),
        bpm=max(60.0, min(240.0, float(d.get("bpm", 120.0)))),
        send_start_stop=bool(d.get("send_start_stop", True)),
        tap_button=int(d.get("tap_button", -1)),
        start_button=int(d.get("start_button", -1)),
        stop_button=int(d.get("stop_button", -1)),
    )


def _program_change_from_dict(d: Optional[dict]) -> ProgramChangeConfig:
    """Hydrate a ProgramChangeConfig from raw dict, defaulting to disabled.

    JSON keys are strings (PC numbers) — convert to ints internally.
    Missing/empty dict returns a disabled config so old presets are unaffected.
    """
    if not d:
        return ProgramChangeConfig()
    raw_bindings = d.get("bindings") or {}
    bindings: Dict[int, str] = {}
    for str_pc, slug in raw_bindings.items():
        try:
            pc = int(str_pc)
            if 0 <= pc <= 127 and isinstance(slug, str) and slug:
                bindings[pc] = slug
        except (TypeError, ValueError):
            continue
    return ProgramChangeConfig(
        enabled=bool(d.get("enabled", False)),
        listen_channel=int(d.get("listen_channel", -1)),
        bindings=bindings,
    )


def _macro_event_from_dict(d: dict) -> MacroEvent:
    """Hydrate one MacroEvent from a raw dict. Missing fields default to 0."""
    return MacroEvent(
        delay_ms=max(0, int(d.get("delay_ms", 0))),
        status=max(0, min(255, int(d.get("status", 0)))),
        data1=max(0, min(127, int(d.get("data1", 0)))),
        data2=max(0, min(127, int(d.get("data2", 0)))),
    )


def _macro_from_dict(d: dict) -> Macro:
    """Hydrate a Macro from a raw dict. Missing events list → empty macro."""
    name = str(d.get("name", "Unnamed"))
    raw_events = d.get("events") or []
    events: List[MacroEvent] = []
    for entry in raw_events:
        if not isinstance(entry, dict):
            continue
        try:
            events.append(_macro_event_from_dict(entry))
        except (TypeError, ValueError):
            continue
    duration_ms = max(0, int(d.get("duration_ms", events[-1].delay_ms if events else 0)))
    return Macro(
        name=name,
        events=events,
        duration_ms=duration_ms,
        arp_mode=bool(d.get("arp_mode", False)),
        arp_rate_hz=max(0.01, float(d.get("arp_rate_hz", 8.0))),
        arp_loop=bool(d.get("arp_loop", True)),
    )


def _macros_from_dict(raw: object) -> List[Macro]:
    """Hydrate the macros list from raw JSON. Returns empty list on missing/bad data."""
    if not isinstance(raw, list):
        return []
    result: List[Macro] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            result.append(_macro_from_dict(entry))
        except (TypeError, ValueError):
            continue
    return result


def _setlist_config_from_dict(d: Optional[dict]) -> SetlistConfig:
    """Hydrate a SetlistConfig from raw dict, defaulting to disabled.

    Missing fields fall back to defaults so old presets without a `setlist`
    key load cleanly (setlist stays disabled, schema version unchanged).
    """
    if not d:
        return SetlistConfig()
    raw_presets = d.get("presets") or []
    presets: List[str] = []
    for entry in raw_presets:
        if isinstance(entry, str) and entry.strip():
            presets.append(entry.strip())
    return SetlistConfig(
        enabled=bool(d.get("enabled", False)),
        name=str(d.get("name", "Setlist")),
        presets=presets,
        next_button=int(d.get("next_button", -1)),
        prev_button=int(d.get("prev_button", -1)),
        wrap=bool(d.get("wrap", True)),
    )


def _passthrough_from_dict(d: Optional[dict]) -> "PassthroughConfig":
    """Hydrate a PassthroughConfig from raw dict, defaulting to disabled.

    Missing/None dict returns a default disabled config so old presets load
    cleanly without opening any extra port.
    """
    if not d:
        return PassthroughConfig()
    raw_ch = d.get("channel_remap", -1)
    try:
        channel_remap = int(raw_ch)
        channel_remap = max(-1, min(15, channel_remap))
    except (TypeError, ValueError):
        channel_remap = -1
    raw_tr = d.get("transpose_semitones", 0)
    try:
        transpose = int(raw_tr)
        transpose = max(-24, min(24, transpose))
    except (TypeError, ValueError):
        transpose = 0
    return PassthroughConfig(
        enabled=bool(d.get("enabled", False)),
        input_port_name=str(d.get("input_port_name", "")),
        transpose_semitones=transpose,
        channel_remap=channel_remap,
        pass_cc=bool(d.get("pass_cc", True)),
        pass_notes=bool(d.get("pass_notes", True)),
        pass_other=bool(d.get("pass_other", False)),
    )

def _rtp_midi_from_dict(d: Optional[dict]) -> RtpMidiConfig:
    """Hydrate a RtpMidiConfig from raw dict, defaulting to disabled.

    Missing/None returns a default disabled config so old presets load
    cleanly without any UDP traffic.
    """
    if not d:
        return RtpMidiConfig()
    port_raw = d.get("peer_port", 5004)
    try:
        port = max(1, min(65535, int(port_raw)))
    except (TypeError, ValueError):
        port = 5004
    return RtpMidiConfig(
        enabled=bool(d.get("enabled", False)),
        peer_host=str(d.get("peer_host", "127.0.0.1")),
        peer_port=port,
        session_name=str(d.get("session_name", "UCM Bridge")),
    )


def _midi2_from_dict(d: Optional[dict]) -> Midi2Config:
    """Hydrate a Midi2Config from raw dict, defaulting to disabled.

    Missing/None returns a default disabled config so old presets load
    cleanly with no UMP traffic.
    """
    if not d:
        return Midi2Config()
    return Midi2Config(
        enabled=bool(d.get("enabled", False)),
        group=max(0, min(15, int(d.get("group", 0)))),
        fallback_to_midi1=bool(d.get("fallback_to_midi1", True)),
    )


def _pattern_recorder_from_dict(d: Optional[dict]) -> "PatternRecorderConfig":
    """Hydrate a PatternRecorderConfig from raw dict, defaulting to disabled.

    Missing/None returns a default disabled config so old presets load cleanly.
    """
    if not d:
        return PatternRecorderConfig()
    return PatternRecorderConfig(
        enabled=bool(d.get("enabled", False)),
        record_button=int(d.get("record_button", -1)),
        overdub_button=int(d.get("overdub_button", -1)),
        cancel_button=int(d.get("cancel_button", -1)),
        loop_length_bars=max(1, int(d.get("loop_length_bars", 1))),
        quantize_to_grid=bool(d.get("quantize_to_grid", True)),
    )
