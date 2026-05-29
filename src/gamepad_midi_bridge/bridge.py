"""Bridge engine — runs the controller-poll/MIDI-send loop in its own QThread.

Signals stream controller and status updates back to the GUI without blocking
the main loop. Keep the inner loop hot — anything heavy belongs in slots on
the GUI side.

V1.1: optional parallel DualSense HID handle gives us battery, touchpad, and
edge-quantized stick corners on top of the SDL2-driven pygame input.
"""
from __future__ import annotations

import random
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QMetaObject, QObject, QThread, QTimer, Q_ARG, Qt, Signal, Slot,
)

from . import dualsense as ds
from .calibration import calibrate
from .controller import ControllerInfo, ControllerReader
from .demo_controller import SyntheticControllerReader
from .keyboard_controller import KeyboardControllerReader
from .mouse_controller import MouseControllerReader
from .corner_quantizer import CornerDetector, decode_switch
from .mapping import HapticInputBinding, L2_AXIS, Macro, MacroEvent, Mapping, Midi2Config, MidiClockConfig, PassthroughConfig, PatternRecorderConfig, QuantizeConfig, R2_AXIS, STICK_AXES, StickFlickConfig, StickLfoConfig, TriggerAftertouchConfig
from .pattern import PatternEngine, PatternState
from . import midi2 as _midi2
from .rtp_midi import RtpMidiSender
from . import shaping
from .midi_backend import DEFAULT_PORT_NAME, MidiPortError, OpenedPort, close_port, open_port
from . import presets as _presets
from .midi_input import (
    INPUT_PORT_NAME, MidiInputError, OpenedInputPort,
    close_input_port, open_input_port, set_callback as set_input_callback,
)
from .osc_backend import OscReceiver, OscSender
from . import usage_stats as _usage_stats
from . import latency_test as _latency_test


# Adaptive-trigger effects whose output report carries a meaningful amplitude/
# strength byte. The bridge scales those bytes by incoming velocity/CC. The
# rest are fire-or-skip (we threshold at 0.5).
_AMPLITUDE_AWARE_EFFECTS = frozenset({"feedback", "vibration"})

# How long an incoming MIDI event holds the trigger effect before the bridge
# reverts to the user's static l2/r2_haptic_effect. ~50 ms is long enough to
# feel as a real "thump" but short enough that fast notes don't smear.
_HAPTIC_PULSE_MS = 50

# macOS-only PyObjC fallback for adaptive triggers. Imported lazily so
# non-mac users don't even attempt to load the framework.
_mac_haptics = None
if sys.platform == "darwin":
    try:
        from . import mac_haptics as _mac_haptics  # type: ignore
    except Exception:
        _mac_haptics = None


@dataclass
class BridgeState:
    mapping: Mapping = field(default_factory=Mapping)
    stick_offsets: Dict[int, float] = field(default_factory=dict)


class BridgeWorker(QObject):
    """Lives on a QThread. Owns the controller, MIDI port, and calibration."""

    # --- Engine status
    status = Signal(str)                              # human-readable status
    started = Signal(str, str)                        # controller_name, midi_port_name
    stopped = Signal()
    error = Signal(str)
    controller_info = Signal(object)                  # ControllerInfo | None
    calibration_progress = Signal(float)              # 0.0..1.0
    # PySide6's dict ↔ QVariantMap conversion sometimes warns about
    # _pythonToCppCopy; declaring `object` keeps the Python dict intact
    # across the queued connection without the noise.
    calibration_done = Signal(object, list, list)     # offsets, severe, significant

    # --- Live telemetry (throttled to avoid spamming the GUI)
    axis_value = Signal(int, float)                   # axis_idx, -1..1 (post-offset)
    button_state = Signal(int, bool)
    hat_state = Signal(str, bool)

    # --- V1.1 DualSense extras
    battery_changed = Signal(int, bool, bool)         # percent, charging, fully_charged
    touchpad_xy = Signal(bool, float, float)          # contact, x_norm, y_norm
    transport_changed = Signal(bool)                  # wired (True) vs BT (False)
    corner_triggered = Signal(str, str, int)          # side ("L"/"R"), kind, sector

    # --- MIDI sent (for the "MIDI activity" indicator)
    midi_sent = Signal()

    # --- MIDI message detail (for the MIDI activity log panel)
    # direction: "sent" or "received", channel: 0-15, status: status byte,
    # data1: CC/note number, data2: velocity/value, label: human-readable string
    midi_message = Signal(str, int, int, int, int, str)

    # --- V1.1c haptic-input: emitted whenever an incoming MIDI message
    # fired a trigger effect. (side="L"/"R", effect name, intensity 0..1).
    haptic_event = Signal(str, str, float)

    # --- Feature #15: Program Change → preset hot-swap. Emitted on the
    # rtmidi callback thread; main window connects to _on_preset_change_requested
    # which runs on the GUI thread via a queued connection.
    preset_change_requested = Signal(str)  # preset slug

    # --- Setlist mode: emitted on each Next/Prev step so the main window can
    # load the preset without the bridge knowing about the file system.
    # slug: preset slug to load, index: new 0-based position, total: list len.
    setlist_step = Signal(str, int, int)

    def __init__(self, slot_index: int = 0,
                 midi_port_name: Optional[str] = None,
                 demo: bool = False,
                 keyboard: bool = False,
                 mouse: bool = False) -> None:
        """Multi-controller plumbing — slot_index picks which pygame joystick
        this worker binds to, and midi_port_name overrides the virtual port so
        two workers don't fight over a single "Universal Controller MIDI" port name.
        `demo` swaps the pygame reader for a synthetic one so the bridge can
        be exercised end-to-end without hardware (recording demo videos, CI).
        `keyboard` uses keyboard input instead (WASD + arrows + keys).
        Both default to the V1.1 single-controller behaviour.
        """
        super().__init__()
        self._slot_index = max(0, int(slot_index))
        self._midi_port_name = midi_port_name or DEFAULT_PORT_NAME
        self._demo = bool(demo)
        self._keyboard = bool(keyboard)
        self._mouse = bool(mouse)
        self._state = BridgeState()
        self._reader: Optional[ControllerReader] = None
        self._midi: Optional[OpenedPort] = None
        self._ds_handle: Optional[ds.DualSenseHandle] = None
        self._mac_haptic_handle = None     # set on darwin if mac_haptics opens
        self._osc: Optional[OscSender] = None
        self._osc_receiver: Optional[OscReceiver] = None
        self._prev_osc_axes: Dict[int, int] = {}   # last sent value as MIDI 0-127
        self._left_corner: Optional[CornerDetector] = None
        self._right_corner: Optional[CornerDetector] = None
        self._last_haptic_pair: tuple = (None, None)   # (l2, r2) last applied
        # Haptic-in plumbing. Lock serialises HID writes between the rtmidi
        # callback thread and the main poll loop's `_apply_haptics` calls so
        # we never interleave two output reports on the same handle.
        self._midi_in: Optional[OpenedInputPort] = None
        # Passthrough input port — separate from the haptic-in port.
        self._passthrough_input: Optional[OpenedInputPort] = None
        self._haptic_lock = threading.Lock()
        self._haptic_revert_timers: List["threading.Timer"] = []
        self._running = False
        self._prev_buttons: Dict[int, bool] = {}
        self._prev_cc: Dict[int, int] = {}
        # MIDI clock state
        self._clock_thread: Optional[threading.Thread] = None
        self._clock_running: bool = False
        self._tap_times: List[float] = []   # timestamps of last ≤4 taps
        # Per-trigger latch state, only consulted by `shaping.apply_trigger`
        # when the trigger config mode is "latch". Stateless modes ignore.
        self._trigger_states: Dict[int, shaping.TriggerState] = {
            L2_AXIS: shaping.TriggerState(),
            R2_AXIS: shaping.TriggerState(),
        }
        # Per-trigger "modifier gate" state — was the gate button held on the
        # previous tick? Used to detect the release edge so we can send the
        # configured rest value exactly once instead of leaving the receiver
        # stuck on the last trigger value.
        self._trigger_gate_was_held: Dict[int, bool] = {L2_AXIS: False, R2_AXIS: False}
        # Per-button "modifier gate" state — track gate-button hold per button.
        self._button_gate_was_held: Dict[int, bool] = {}
        # Per-trigger latch state for tactile feedback — track previous latch state
        # to detect threshold crossings and fire haptic clicks.
        self._prev_latch_state: Dict[int, bool] = {L2_AXIS: False, R2_AXIS: False}
        # Per-trigger bow mode state: (prev_pressure, prev_timestamp)
        self._bow_state: Dict[int, tuple] = {}  # axis_idx -> (prev_pressure, prev_ts)
        self._prev_hat = {"up": False, "down": False, "left": False, "right": False}
        self._prev_corner_notes: Dict[str, Optional[int]] = {"L": None, "R": None}
        self._prev_touch_cc: Dict[str, int] = {}
        self._prev_touch_value: Dict[str, float] = {}  # tracks relative-mode state per axis
        self._touch_armed: bool = False  # for click_to_arm mode
        self._prev_touchpad_zone: Optional[int] = None  # zone index for hysteresis
        self._touchpad_zone_bias: Dict[int, float] = {}  # hysteresis bias per zone
        self._prev_battery: Optional[tuple] = None
        # CC smoothing state: keyed by (axis_idx, cc_num), value = (current_val, target_val, start_ms)
        self._cc_smooth_state: Dict[tuple, tuple] = {}  # (current, target, started_at_ms)
        # Gesture tracking — per-finger touch start position + two-finger distance
        self._touch_start_xy: Optional[Tuple[float, float]] = None  # first contact XY
        self._touch_last_xy: Optional[Tuple[float, float]] = None  # last recorded touch position
        self._touch_start_two_finger_distance: Optional[float] = None  # initial 2-finger separation
        self._battery_alert_fired: bool = False  # track if alert has fired for current low state
        # Telemetry throttle — emit GUI updates at ~30Hz max even at 100Hz polling
        self._last_telemetry: float = 0.0
        self._telemetry_interval = 1.0 / 30.0
        # Battery + touchpad poll less often — they don't need 100Hz
        self._last_battery_poll: float = 0.0
        self._battery_interval = 5.0
        # A/B compare state — B preset loaded once per set_mapping call.
        self._b_mapping: Optional[Mapping] = None
        self._ab_b_active: bool = False
        # Pitch bend state — per-stick: last sent 14-bit value (0..16383)
        self._prev_pitch_bend: Dict[int, int] = {}  # axis_idx -> 14-bit value
        # Feedback-loop guard: track recent outbound CC messages to detect echoes
        # Deque of (channel, cc_number, value, timestamp) tuples, max 50 entries
        self._recent_outbound_cc: deque = deque(maxlen=50)
        self._feedback_guard_window_ms = 50  # Drop messages within 50ms of send
        # Macro recorder state — capture MIDI sends with relative timestamps.
        self._recording: bool = False
        self._recording_start_ms: float = 0.0
        self._recording_events: List[MacroEvent] = []
        # Pattern recorder — loop engine (None = feature disabled / not yet started)
        self._pattern_engine: Optional[PatternEngine] = None
        self._pattern_rec_was_held: bool = False   # edge-detect for record_button
        self._pattern_ovd_was_held: bool = False   # edge-detect for overdub_button
        self._pattern_cxl_was_held: bool = False   # edge-detect for cancel_button
        # Setlist mode — current position in the ordered preset list.
        self._setlist_index: int = 0
        # Stick-flick state — per axis: (prev_shaped_val, prev_timestamp)
        self._flick_state: Dict[int, tuple] = {}  # axis_idx -> (prev_val, prev_ts)
        # Stick-chord state — per stick index (0=left, 1=right): direction last fired
        # Tracks which direction chord is currently held to avoid re-triggering.
        self._stick_chord_state: Dict[int, Optional[str]] = {}  # stick_idx -> direction | None
        # Stick chord values — per-tick tracking of shaped X, Y for each stick pair
        self._stick_chord_values: Dict[int, Tuple[float, float]] = {}  # stick_idx -> (x, y)
        # Trigger aftertouch state — was AT active last tick?
        self._at_active: Dict[int, bool] = {L2_AXIS: False, R2_AXIS: False}
        # Polyphonic aftertouch state — per-(button, note): last sent pressure (0..127).
        # Used to deduplicate messages and rate-limit to 30Hz.
        self._poly_at_last_pressure: Dict[Tuple[int, int], int] = {}  # (btn_idx, note) -> last_pressure
        self._poly_at_last_send_ms: float = 0.0  # timestamp of last batch send
        # Test note timers — keeps QTimer objects alive across send_test_note() calls
        self._test_note_timers: List[QTimer] = []
        # Latency self-test — set True by LatencyDialog; bridge records
        # input/output timestamps only when this flag is active (zero overhead
        # in normal operation).
        self._latency_test_active: bool = False
        # RTP-MIDI network sender (None = disabled)
        self._rtp_sender: Optional[RtpMidiSender] = None
        # Random-mod state — keyed by axis_idx.
        # Values: (last_sample_ms, current_value) where current_value is 0..127.
        self._random_mod_state: Dict[int, tuple] = {}
        # LFO phase state — keyed by axis_idx, value is current phase in 0..2π.
        self._lfo_phase: Dict[int, float] = {}
        # Arp playback state — keyed by button_idx.
        # Values: (QTimer, event_index, macro_name) or None when idle.
        self._arp_state: Dict[int, Optional[object]] = {}
        # Button repeat/strum state — keyed by button_idx.
        # Values: (QTimer, current_velocity) or None when idle.
        # Tracks the repeat timer and decaying velocity per button.
        self._repeat_state: Dict[int, Optional[tuple]] = {}
        # Quantize: epoch (perf_counter) when the clock loop started its current beat.
        # Updated by _run_midi_clock_loop each quarter-note so the quantize helper
        # can compute the current beat phase without separate bookkeeping.
        self._clock_beat_epoch: float = 0.0   # perf_counter timestamp of last beat start
        self._clock_bpm_live: float = 120.0   # BPM currently running in the clock thread
        # MIDI 2.0 / UMP state — probed once per port open.
        # True = port accepted the UMP probe; False = fell back to MIDI 1.0.
        self._midi2_supported: bool = False
        self._midi2_warned: bool = False  # suppress repeated "no UMP" log spam

    # ---------------------------------------------------------------- public API

    def _emit_midi_message(
        self, direction: str, status: int, data1: int, data2: int, label: str
    ) -> None:
        """Emit a MIDI message detail signal for the activity log panel.

        direction: "sent" or "received"
        status: raw status byte (includes channel in lower 4 bits)
        data1: note/CC number or similar
        data2: velocity/value
        label: human-readable label like "NOTE-ON C4" or "CC#1"
        """
        channel = status & 0x0F
        self.midi_message.emit(direction, channel, status, data1, data2, label)

    def set_mapping(self, mapping: Mapping) -> None:
        self._state.mapping = mapping
        # Check if port_name_override changed; if running, restart with new name
        if self._running and self._midi:
            old_name = self._midi_port_name
            new_name = mapping.port_name_override or old_name
            if new_name != old_name:
                self._update_port_name(new_name)
        self._cache_b_mapping(mapping)
        self._sync_corner_detectors()
        self._apply_haptics()
        self._sync_osc_sender()
        self._sync_haptic_input()
        self._sync_passthrough()
        self._sync_midi_clock()
        self._sync_rtp_sender()

    @Slot()
    def start(self) -> None:
        """Entry point — invoked once when the worker's thread starts."""
        if self._keyboard:
            self._reader = KeyboardControllerReader(slot_index=self._slot_index)
        elif self._mouse:
            self._reader = MouseControllerReader(slot_index=self._slot_index)
        elif self._demo:
            self._reader = SyntheticControllerReader(slot_index=self._slot_index)
        else:
            self._reader = ControllerReader(slot_index=self._slot_index)
        info = self._reader.detect()
        self.controller_info.emit(info)
        if info is None:
            self.error.emit("No controller detected. Plug one in and click Start.")
            return

        try:
            self._midi = open_port(self._midi_port_name)
        except MidiPortError as e:
            self.error.emit(str(e))
            return

        self._probe_midi2_support()
        self._maybe_open_dualsense(info)
        self._sync_corner_detectors()
        self._apply_haptics()
        self._sync_osc_sender()
        self._sync_haptic_input()
        self._sync_passthrough()
        self._sync_rtp_sender()

        # Auto-calibrate on first start. UI may also trigger recalibration.
        self._run_calibration()

        self.started.emit(info.name, self._midi.name)
        self.status.emit(f"Bridging {info.name} → {self._midi.name}")
        self._running = True
        self._loop()

    @Slot()
    def stop(self) -> None:
        self._running = False

    def panic(self) -> None:
        """Send all notes off + all sound off on every channel as emergency stop.

        Sends CC 123 (all notes off) and CC 120 (all sound off) for each channel,
        plus note-off for every note 0..127 on every channel for DAW compatibility.
        Total: ~2080 messages per panic across 16 channels.
        """
        if self._midi is None:
            return
        try:
            for channel in range(16):
                cc_byte = 0xB0 | channel
                # CC 123 = all notes off
                self._midi.port.send_message([cc_byte, 123, 0])
                self._emit_midi_message("sent", cc_byte, 123, 0, "CC#123 (all notes off)")
                self.midi_sent.emit()

                # CC 120 = all sound off
                self._midi.port.send_message([cc_byte, 120, 0])
                self._emit_midi_message("sent", cc_byte, 120, 0, "CC#120 (all sound off)")
                self.midi_sent.emit()

                # Belt-and-braces: send note-off for every note on every channel
                note_off = 0x80 | channel
                for note in range(128):
                    self._midi.port.send_message([note_off, note, 0])
            self.midi_sent.emit()
        except Exception:
            pass

    def send_test_note(self, channel: int = 0, note: int = 60,
                       velocity: int = 100, duration_ms: int = 200) -> None:
        """Send a brief test note (note-on then note-off) to verify DAW connectivity.

        Sends note-on immediately, schedules note-off via QTimer after duration_ms.
        Useful for testing connector output before connecting the full bridge.
        """
        if self._midi is None:
            return

        channel = max(0, min(15, channel))  # Clamp to 0..15
        note = max(0, min(127, note))      # Clamp to 0..127
        velocity = max(0, min(127, velocity))
        duration_ms = max(10, duration_ms)

        try:
            note_on = 0x90 | channel
            self._midi.port.send_message([note_on, note, velocity])
            self._emit_midi_message("sent", note_on, note, velocity, f"TEST NOTE-ON #{note}")
            self.midi_sent.emit()

            # Schedule note-off via QTimer (thread-safe signal/slot mechanism)
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._send_test_note_off(channel, note))
            timer.start(duration_ms)
            # Keep timer alive by storing in a list
            self._test_note_timers.append(timer)
        except Exception:
            pass

    def _send_test_note_off(self, channel: int, note: int) -> None:
        """Internal: send note-off and clean up the timer."""
        if self._midi is None:
            return
        try:
            note_off = 0x80 | channel
            self._midi.port.send_message([note_off, note, 0])
            self._emit_midi_message("sent", note_off, note, 0, f"TEST NOTE-OFF #{note}")
            self.midi_sent.emit()
        except Exception:
            pass
        # Clean up expired timers to avoid memory leak
        self._test_note_timers = [t for t in self._test_note_timers if t.isActive()]

    @Slot()
    def recalibrate(self) -> None:
        if self._reader is None:
            return
        was_running = self._running
        self._running = False  # pause the inner loop
        self._run_calibration()
        if was_running:
            self._running = True
            self._loop()

    # ---------------------------------------------------------------- macro recorder

    def start_recording(self) -> None:
        """Begin capturing outbound MIDI messages as a macro.

        Any previous partial recording is discarded. Call stop_recording() to
        finalise and retrieve the Macro object.
        """
        self._recording_events = []
        self._recording_start_ms = time.time() * 1000.0
        self._recording = True

    def stop_recording(self) -> Macro:
        """Stop capturing and return the recorded Macro.

        Returns an unnamed Macro with all captured events. The caller should
        assign a name and append it to mapping.macros.
        """
        self._recording = False
        events = list(self._recording_events)
        self._recording_events = []
        duration = events[-1].delay_ms if events else 0
        return Macro(name="", events=events, duration_ms=duration)

    def cancel_recording(self) -> None:
        """Discard the current recording without returning a Macro."""
        self._recording = False
        self._recording_events = []

    def _record_midi_send(self, status: int, data1: int, data2: int) -> None:
        """Capture one outbound MIDI message if recording is active.

        Called from every send site. Cheap no-op when _recording is False.
        Also forwards to the PatternEngine when it is in RECORDING or OVERDUB.
        """
        if self._recording:
            delay_ms = int((time.time() * 1000.0) - self._recording_start_ms)
            self._recording_events.append(MacroEvent(
                delay_ms=max(0, delay_ms),
                status=status,
                data1=data1,
                data2=data2,
            ))
        if self._pattern_engine is not None:
            self._pattern_engine.record_event(status, data1, data2)

    def _play_macro(self, macro: "Macro", midi: "OpenedPort") -> None:
        """Replay a recorded macro sequence using QTimer for timing.

        Each event is scheduled at its absolute delay_ms offset from now.
        Multiple simultaneous playbacks are independent — each call creates
        its own timer chain so they don't interfere with each other.
        """
        from PySide6.QtCore import QTimer as _QTimer
        for event in macro.events:
            timer = _QTimer(self)
            timer.setSingleShot(True)
            # Capture event bytes in the closure
            status, d1, d2 = event.status, event.data1, event.data2
            timer.timeout.connect(
                lambda s=status, d1_=d1, d2_=d2: (
                    midi.port.send_message([s, d1_, d2_]),
                    self.midi_sent.emit(),
                    self._emit_midi_message("sent", s, d1_, d2_, f"Macro d1={d1_:3d} d2={d2_:3d}"),
                )
            )
            timer.start(event.delay_ms)

    # ---------------------------------------------------------------- internals

    # ---------------------------------------------------------- MIDI 2.0 / UMP

    def _probe_midi2_support(self) -> None:
        """Probe the current MIDI port for UMP support and cache the result.

        Called once after a port is successfully opened.  If the mapping has
        midi2.enabled=False the probe is skipped (no silent test notes sent).
        """
        if self._midi is None:
            return
        m2 = self._state.mapping.midi2
        if not m2.enabled:
            self._midi2_supported = False
            return
        _midi2.clear_probe_cache()
        self._midi2_supported = _midi2.is_supported(self._midi.port)
        if not self._midi2_supported and not self._midi2_warned:
            self._midi2_warned = True
            self.status.emit(
                "MIDI 2.0 UMP not accepted by this port — using MIDI 1.0 fallback"
            )

    def _use_midi2(self) -> bool:
        """Return True when UMP emission is active for the current mapping."""
        m2 = self._state.mapping.midi2
        if not m2.enabled:
            return False
        if self._midi2_supported:
            return True
        # Port doesn't support UMP — fall back if configured, else skip send entirely.
        return False

    def _send_note_on(self, midi, status_1: int, note: int, velocity: int) -> None:
        """Send a Note On using MIDI 2.0 UMP or MIDI 1.0 depending on config.

        ``status_1`` is the MIDI 1.0 status byte (0x90 | channel) used for the
        MIDI 1.0 path and to extract channel for the UMP path.
        """
        if self._use_midi2():
            m2 = self._state.mapping.midi2
            channel = status_1 & 0x0F
            vel_16 = _midi2.scale_7bit_to_16bit(velocity)
            ump = _midi2.pack_midi2_note_on(m2.group, channel, note, vel_16)
            midi.port.send_message(list(ump))
        else:
            midi.port.send_message([status_1, note, velocity])

    def _send_note_off(self, midi, status_1: int, note: int, velocity: int) -> None:
        """Send a Note Off (always MIDI 1.0 — UMP note-off is an optional upgrade)."""
        midi.port.send_message([status_1, note, velocity])

    def _send_jittered_note(self, midi, btn_note_on: int, note: int, velocity: int) -> None:
        """Send a note-on with associated telemetry after timing jitter delay."""
        self._send_note_on(midi, btn_note_on, note, velocity)
        self._rtp_send(btn_note_on, note, velocity)
        self._record_midi_send(btn_note_on, note, velocity)
        self.midi_sent.emit()
        self._emit_midi_message("sent", btn_note_on, note, velocity, f"NOTE-ON #{note}")

    def _send_cc(self, midi, status_1: int, cc_num: int, value: int) -> None:
        """Send a CC using MIDI 2.0 UMP or MIDI 1.0 depending on config."""
        if self._use_midi2():
            m2 = self._state.mapping.midi2
            channel = status_1 & 0x0F
            val_32 = _midi2.scale_7bit_to_32bit(value)
            ump = _midi2.pack_midi2_cc(m2.group, channel, cc_num, val_32)
            midi.port.send_message(list(ump))
        else:
            midi.port.send_message([status_1, cc_num, value])

    def _maybe_open_dualsense(self, info: ControllerInfo) -> None:
        """Open a parallel HID handle if the controller looks like a DualSense.

        SDL2's controller name on macOS is "DualSense Wireless Controller";
        on Windows via XInput-passthrough it can vary. Match generously.
        """
        name_lc = info.name.lower()
        if "dualsense" not in name_lc and "dual sense" not in name_lc:
            return
        dev = ds.find_first()
        if dev is None:
            return
        try:
            self._ds_handle = dev.open()
            self.transport_changed.emit(dev.wired)
        except Exception as e:
            # Non-fatal — the standard pygame path still works for buttons/sticks.
            self.status.emit(f"DualSense extras unavailable: {e}")

        # macOS-only: open a GCController-backed haptic handle for the same
        # device. hidapi can't write triggers on darwin so this is the only
        # path that works there.
        if _mac_haptics is not None and getattr(_mac_haptics, "HAPTICS_AVAILABLE", False):
            try:
                self._mac_haptic_handle = _mac_haptics.MacHapticsHandle.open()
            except Exception as e:
                self.status.emit(f"macOS haptics unavailable: {e}")

    # ---------------------------------------------------------- A/B compare

    def _cache_b_mapping(self, mapping: Mapping) -> None:
        """Load and cache the B preset whenever the base mapping changes.

        Called by set_mapping so the hot path (_active_mapping) never does I/O.
        If ab_b_preset_slug is unset or the file doesn't exist, _b_mapping stays
        None and A/B compare silently no-ops even if the button is pressed.
        """
        slug = mapping.ab_b_preset_slug
        if slug:
            self._b_mapping = _presets.load_preset_by_slug(slug)
        else:
            self._b_mapping = None

    def _active_mapping(self) -> Mapping:
        """Return the mapping currently active in the poll loop.

        Returns the B preset when A/B compare is enabled, the designated button
        is held, and the B preset was successfully loaded. Otherwise the base
        mapping is returned unchanged — zero overhead when the feature is off.
        """
        m = self._state.mapping
        if (m.ab_compare_enabled
                and m.ab_compare_button >= 0
                and self._ab_b_active
                and self._b_mapping is not None):
            return self._b_mapping
        return m

    def _sync_osc_sender(self) -> None:
        """Open or close the OSC UDP sender to match the mapping's OscConfig."""
        cfg = self._state.mapping.osc
        if not cfg.enabled:
            if self._osc is not None:
                self._osc.close()
                self._osc = None
        else:
            # Reopen on host/port change so we don't keep stale state.
            if self._osc is None or self._osc.host != cfg.host or self._osc.port != cfg.port:
                if self._osc is not None:
                    self._osc.close()
                self._osc = OscSender(host=cfg.host, port=cfg.port)
            self._prev_osc_axes.clear()
        self._sync_osc_receiver()

    def _sync_osc_receiver(self) -> None:
        """Spin up or tear down the OSC listener per the mapping's OscConfig."""
        cfg = self._state.mapping.osc
        if not cfg.listen_enabled:
            if self._osc_receiver is not None:
                self._osc_receiver.stop()
                self._osc_receiver = None
            return
        # Restart if port changed or not yet started.
        if (self._osc_receiver is not None
                and self._osc_receiver.port != cfg.listen_port):
            self._osc_receiver.stop()
            self._osc_receiver = None
        if self._osc_receiver is None:
            recv = OscReceiver(port=cfg.listen_port)
            recv.set_callback(self._on_osc_in)
            try:
                recv.start()
                self._osc_receiver = recv
                self.status.emit(f"OSC listen on UDP {cfg.listen_port}")
            except OSError as e:
                self.status.emit(f"OSC listen failed (port {cfg.listen_port}): {e}")

    def _on_osc_in(self, address: str, args: list) -> None:
        """OscReceiver callback — runs on the receiver daemon thread.

        Looks up every matching OscHapticBinding and fires the haptic effect,
        scaled by the first float argument (0..1) if present. Mirrors the
        MIDI-in haptic path from _dispatch_haptic / _fire_haptic.
        """
        from .mapping import OscHapticBinding
        cfg = self._state.mapping.osc
        if not cfg.listen_enabled or not cfg.listen_bindings:
            return
        for binding in cfg.listen_bindings:
            if binding.address != address:
                continue
            # Derive intensity from the first float arg, if any.
            intensity = 1.0
            for a in args:
                if isinstance(a, float):
                    intensity = max(0.0, min(1.0, a))
                    break
                if isinstance(a, int):
                    # Treat integer 0/1 as off/on
                    intensity = float(max(0, min(1, a)))
                    break
            intensity = max(0.0, min(1.0, intensity * binding.intensity_scale))
            # Build a synthetic HapticInputBinding so we can reuse _fire_haptic.
            haptic = HapticInputBinding(
                trigger=binding.trigger.upper(),
                source="note",   # source field unused by _fire_haptic pattern 1
                midi_id=0,
                effect=binding.effect,
                intensity_scale=1.0,
            )
            self._fire_haptic(haptic, intensity)

    def _send_osc_axis(self, axis_idx: int, value_0_to_1: float) -> None:
        if self._osc is None:
            return
        cfg = self._state.mapping.osc
        addr = cfg.axis_addresses.get(axis_idx)
        if addr:
            self._osc.send(addr, float(value_0_to_1))

    def _send_osc_button(self, btn_idx: int, pressed: bool) -> None:
        if self._osc is None:
            return
        cfg = self._state.mapping.osc
        addr = cfg.button_addresses.get(btn_idx)
        if addr:
            # OSC convention for triggers: send 1.0 on press, 0.0 on release.
            self._osc.send(addr, 1.0 if pressed else 0.0)

    def _osc_only(self) -> bool:
        return (self._state.mapping.osc.enabled
                and self._state.mapping.osc.mode == "only")

    def _update_port_name(self, new_name: str) -> None:
        """Close the current MIDI port and reopen with a new name.
        
        If reopening fails, attempts to reopen with the old name.
        """
        old_name = self._midi_port_name
        self._midi_port_name = new_name
        
        # Close current port if open
        if self._midi:
            try:
                self._midi.close()
            except Exception as e:
                self.error.emit(f"Error closing MIDI port: {e}")
                self._midi = None
        
        # Try to reopen with new name
        try:
            from .connectors import open_port
            self._midi = open_port(new_name)
            self.status.emit(f"MIDI port switched to: {new_name}")
        except Exception as e:
            # Attempt to revert to old name
            self.error.emit(f"Failed to open MIDI port '{new_name}': {e}. Reverting to '{old_name}'.")
            self._midi_port_name = old_name
            try:
                self._midi = open_port(old_name)
                self.status.emit(f"Reverted to MIDI port: {old_name}")
            except Exception as revert_err:
                self.error.emit(f"Also failed to revert: {revert_err}")
                self._midi = None

    def _sync_corner_detectors(self) -> None:
        m = self._state.mapping
        self._left_corner = self._build_detector(m.left_stick_corners)
        self._right_corner = self._build_detector(m.right_stick_corners)
        # Reset prev-note tracking when config changes so we don't leak hangs.
        self._prev_corner_notes = {"L": None, "R": None}

    def _apply_haptics(self) -> None:
        """Push current trigger-effect config to the controller.

        Idempotent — if nothing's changed since last apply, no-op. Safe to
        call before a handle exists (it just defers until one does). The
        lock serialises against haptic-input pulses so we never interleave
        two HID writes on the same handle.
        """
        m = self._state.mapping
        pair = (m.l2_haptic_effect, m.r2_haptic_effect)
        if pair == self._last_haptic_pair:
            return

        with self._haptic_lock:
            applied = self._write_trigger_pair(m.l2_haptic_effect, m.r2_haptic_effect)
        if applied:
            self._last_haptic_pair = pair

    def _write_trigger_pair(self, l2: Optional[str], r2: Optional[str]) -> bool:
        """Low-level HID write. Caller MUST hold `self._haptic_lock`."""
        # macOS goes through GCController; everything else uses hidapi.
        if self._mac_haptic_handle is not None:
            try:
                self._mac_haptic_handle.set_trigger_effect("L", l2 or "off")
                self._mac_haptic_handle.set_trigger_effect("R", r2 or "off")
                return True
            except Exception as e:
                self.status.emit(f"Haptic apply failed: {e}")
                return False
        if self._ds_handle is not None and self._ds_handle.wired:
            # BT haptics now use a CRC32-framed report — both paths supported.
            return ds.write_trigger_effects(self._ds_handle, l2, r2)
        if self._ds_handle is not None and not self._ds_handle.wired:
            return ds.write_trigger_effects(self._ds_handle, l2, r2)
        return False

    # ---------------------------------------------------------- haptic input

    def _sync_haptic_input(self) -> None:
        """Open / close the virtual MIDI input port.

        The port is needed when either haptic_input OR program_change is
        enabled — both features piggyback on the same rtmidi callback.
        Re-entrant: called on start() AND every set_mapping() so the user can
        toggle either feature live from the UI.
        """
        need_port = (self._state.mapping.haptic_input.enabled
                     or self._state.mapping.program_change.enabled)
        if not need_port:
            if self._midi_in is not None:
                close_input_port(self._midi_in)
                self._midi_in = None
            return
        if self._midi_in is not None:
            # Already open — bindings live on self._state so no re-open needed.
            return
        try:
            self._midi_in = open_input_port(INPUT_PORT_NAME)
            set_input_callback(self._midi_in, self._on_midi_in)
            self.status.emit(
                f"MIDI-in listening on '{self._midi_in.name}'"
            )
        except MidiInputError as e:
            self.status.emit(f"MIDI-in unavailable: {e}")
            self._midi_in = None

    def _on_midi_in(self, event, _data) -> None:
        """rtmidi callback — runs on librtmidi's C thread.

        Must stay non-blocking. We parse the message, find every matching
        binding, and fire the trigger effect under a small mutex. Heavy work
        (timer scheduling for the revert) is fine because `threading.Timer`
        just hands the callback to a daemon thread.

        Why we don't marshal back to the QThread via QMetaObject: the
        BridgeWorker's QThread is busy running the input poll loop and never
        spins a Qt event loop, so queued invocations would never execute.
        Direct HID writes from this thread are safe as long as we lock
        against the main loop's `_apply_haptics`.
        """
        try:
            message, _delta = event
        except (TypeError, ValueError):
            return
        if not message:
            return
        try:
            status_byte = message[0]
        except IndexError:
            return
        msg_type = status_byte & 0xF0
        channel = status_byte & 0x0F

        # --- Feature #15: Program Change → preset hot-swap. Runs regardless
        # of haptic_input.enabled so DAWs can drive preset loads even when the
        # user hasn't set up adaptive-trigger feedback.
        if msg_type == 0xC0 and len(message) >= 2:
            pc_num = int(message[1])
            pc_cfg = self._state.mapping.program_change
            if pc_cfg.enabled:
                ch_match = (pc_cfg.listen_channel < 0
                            or channel == (pc_cfg.listen_channel & 0x0F))
                if ch_match:
                    slug = pc_cfg.bindings.get(pc_num)
                    if slug:
                        self.preset_change_requested.emit(slug)
            return

        # --- Haptic input (NOTE_ON, CC → adaptive-trigger effects)
        cfg = self._state.mapping.haptic_input
        if not cfg.enabled or not cfg.bindings:
            return
        if cfg.listen_channel >= 0 and channel != (cfg.listen_channel & 0x0F):
            return

        # NOTE_ON with velocity 0 is conventionally a NOTE_OFF; ignore.
        if msg_type == 0x90 and len(message) >= 3 and message[2] > 0:
            self._dispatch_haptic("note", int(message[1]),
                                  int(message[2]) / 127.0)
        elif msg_type == 0xB0 and len(message) >= 3:
            cc_num = int(message[1])
            cc_val = int(message[2])
            # Check feedback loop guard if enabled
            if self._state.mapping.haptic_input.guard_feedback_loop:
                if self._recently_sent(channel, cc_num, cc_val):
                    # This CC was just sent by us — drop it to avoid feedback
                    import logging
                    logging.debug(f"Dropped feedback echo: ch={channel} cc={cc_num} val={cc_val}")
                    return
            self._dispatch_haptic("cc", cc_num, cc_val / 127.0)
        # NOTE_OFF, polyphonic aftertouch, channel pressure, etc. are no-ops —
        # haptics naturally decay (we revert after _HAPTIC_PULSE_MS).

    # ---------------------------------------------------------- passthrough

    def _sync_passthrough(self) -> None:
        """Open or close the passthrough input port to match the current config.

        Called from set_mapping() and start() so it tracks live mapping changes.
        If enabled + input_port_name is set, opens the port and registers
        _on_passthrough_in as the callback. Otherwise closes any existing port.
        """
        cfg: PassthroughConfig = self._state.mapping.passthrough
        want_port = cfg.enabled and bool(cfg.input_port_name.strip())

        if not want_port:
            if self._passthrough_input is not None:
                close_input_port(self._passthrough_input)
                self._passthrough_input = None
            return

        # Already open on the same port name — nothing to do.
        if (self._passthrough_input is not None
                and self._passthrough_input.name == cfg.input_port_name):
            return

        # Close any previously-open port (name changed or first open).
        if self._passthrough_input is not None:
            close_input_port(self._passthrough_input)
            self._passthrough_input = None

        try:
            port = open_input_port(cfg.input_port_name)
            set_input_callback(port, self._on_passthrough_in)
            self._passthrough_input = port
            self.status.emit(
                f"MIDI passthrough: listening on \'{port.name}\'"
            )
        except MidiInputError as e:
            self.status.emit(f"MIDI passthrough unavailable: {e}")
            self._passthrough_input = None

    def _on_passthrough_in(self, event, _data) -> None:
        """rtmidi callback for the passthrough input port.

        Runs on librtmidi's C thread — must stay non-blocking.

        Signal flow for an incoming note:
          1. Parse (message, delta) from rtmidi.
          2. Check pass_notes / pass_cc / pass_other against message type.
          3. If channel_remap >= 0, rewrite the channel nibble in the status byte.
          4. If note message and transpose_semitones != 0, clamp-add to data1.
          5. Forward via midi.port.send_message to the bridge's output port.
          6. Emit midi_message signal ("received") so the activity log shows it.
        """
        try:
            message, _delta = event
        except (TypeError, ValueError):
            return
        if not message or len(message) < 1:
            return

        cfg: PassthroughConfig = self._state.mapping.passthrough
        if not cfg.enabled:
            return

        midi = self._midi
        if midi is None:
            return

        try:
            status_byte = int(message[0])
        except (IndexError, ValueError):
            return

        msg_type = status_byte & 0xF0
        is_note = msg_type in (0x80, 0x90)
        is_cc = msg_type == 0xB0

        if is_note and not cfg.pass_notes:
            return
        if is_cc and not cfg.pass_cc:
            return
        if not is_note and not is_cc and not cfg.pass_other:
            return

        # Build a mutable copy of the raw message bytes.
        out = list(message)

        # Channel remap: replace the lower nibble of the status byte.
        if cfg.channel_remap >= 0:
            out[0] = msg_type | (cfg.channel_remap & 0x0F)

        # Transpose: shift note number on Note-On / Note-Off.
        if is_note and cfg.transpose_semitones != 0 and len(out) >= 2:
            note = int(out[1]) + cfg.transpose_semitones
            out[1] = max(0, min(127, note))

        try:
            midi.port.send_message(out)
            self.midi_sent.emit()
            # Emit to the activity log (direction "received" = came from passthrough).
            d1 = int(out[1]) if len(out) > 1 else 0
            d2 = int(out[2]) if len(out) > 2 else 0
            label = f"PT {'NOTE' if is_note else 'CC' if is_cc else 'MSG'} d1={d1}"
            self._emit_midi_message("received", int(out[0]), d1, d2, label)
        except Exception:
            pass

    def _sync_rtp_sender(self) -> None:
        """Start or stop the RTP-MIDI sender to match the current mapping config.

        Called from set_mapping() and start() so live changes are applied
        immediately without restarting the bridge.  When the peer host/port
        changes the old sender is torn down and a new one is opened.
        """
        cfg = self._state.mapping.rtp_midi
        if not cfg.enabled:
            if self._rtp_sender is not None:
                self._rtp_sender.stop()
                self._rtp_sender = None
            return
        # Reopen when any connection parameter changes.
        if (self._rtp_sender is not None
                and (self._rtp_sender.peer_host != cfg.peer_host
                     or self._rtp_sender.peer_port != cfg.peer_port)):
            self._rtp_sender.stop()
            self._rtp_sender = None
        if self._rtp_sender is None:
            sender = RtpMidiSender(cfg.peer_host, cfg.peer_port, cfg.session_name)
            try:
                sender.start()
                self._rtp_sender = sender
                self.status.emit(
                    f"RTP-MIDI sending to {cfg.peer_host}:{cfg.peer_port}"
                )
            except OSError as e:
                self.status.emit(f"RTP-MIDI unavailable: {e}")

    def _rtp_send(self, status: int, data1: int, data2: int) -> None:
        """Forward one MIDI message to the RTP-MIDI sender (no-op if disabled)."""
        if self._rtp_sender is not None:
            self._rtp_sender.send_midi(status, data1, data2)

    def _recently_sent(self, channel: int, cc_number: int, value: int, window_ms: Optional[int] = None) -> bool:
        """Check if this (channel, cc_number, value) was sent recently.

        Returns True if found within the window, False otherwise.
        Window defaults to _feedback_guard_window_ms (50ms).
        """
        if window_ms is None:
            window_ms = self._feedback_guard_window_ms
        now_ms = time.time() * 1000.0
        for ch, cc, val, ts_ms in self._recent_outbound_cc:
            if now_ms - ts_ms > window_ms:
                continue
            if ch == channel and cc == cc_number and val == value:
                return True
        return False

    def _channel_for_button(self, mapping: Mapping, idx: int) -> int:
        """Return the MIDI channel for a button: override or global default."""
        override = mapping.button_channels.get(idx)
        if override is not None:
            return override & 0x0F
        return mapping.midi_channel & 0x0F

    def _channel_for_axis(self, mapping: Mapping, idx: int) -> int:
        """Return the MIDI channel for an axis: override or global default."""
        override = mapping.axis_channels.get(idx)
        if override is not None:
            return override & 0x0F
        return mapping.midi_channel & 0x0F

    def _channel_for_hat(self, mapping: Mapping, direction: str) -> int:
        """Return the MIDI channel for a hat direction: override or global default."""
        override = mapping.hat_channels.get(direction)
        if override is not None:
            return override & 0x0F
        return mapping.midi_channel & 0x0F

    def _record_outbound_cc(self, channel: int, cc_number: int, value: int) -> None:
        """Record an outbound CC send for feedback-loop detection."""
        ts_ms = time.time() * 1000.0
        self._recent_outbound_cc.append((channel, cc_number, value, ts_ms))

    def _get_poly_at_pressure(self, reader, pressure_source: str) -> float:
        """Get normalized pressure (0..1) from the configured source.

        pressure_source: "left_stick_mag", "right_stick_mag", "l2", or "r2".
        Returns 0..1 normalized value.
        """
        if pressure_source == "left_stick_mag":
            x = reader.get_axis(0) or 0.0
            y = reader.get_axis(1) or 0.0
            return (x*x + y*y) ** 0.5  # magnitude
        elif pressure_source == "right_stick_mag":
            x = reader.get_axis(2) or 0.0
            y = reader.get_axis(3) or 0.0
            return (x*x + y*y) ** 0.5
        elif pressure_source == "l2":
            return max(0.0, min(1.0, float(reader.get_axis(4) or 0.0)))
        elif pressure_source == "r2":
            return max(0.0, min(1.0, float(reader.get_axis(5) or 0.0)))
        return 0.0

    def _dispatch_haptic(self, source: str, midi_id: int, normalized: float) -> None:
        """Match an incoming MIDI value against every binding and fire."""
        cfg = self._state.mapping.haptic_input
        for binding in cfg.bindings:
            if binding.source != source or binding.midi_id != midi_id:
                continue
            intensity = max(0.0, min(1.0, normalized * binding.intensity_scale))
            # For non-amplitude effects (weapon, bow, etc.) only fire above
            # the half-mark — otherwise a quiet note silently slams the
            # trigger into full resistance.
            if (binding.effect not in _AMPLITUDE_AWARE_EFFECTS
                    and intensity < 0.5):
                continue
            self._fire_haptic(binding, intensity)

    def _fire_haptic(self, binding_or_side, intensity_or_effect=None, duration_ms=None) -> None:
        """Write the trigger effect and schedule a revert to the static config.

        Supports two calling patterns:
        1. _fire_haptic(binding, intensity) — from haptic-input MIDI callback
        2. _fire_haptic(side, effect, duration_ms=30) — from latch tactile click

        binding_or_side: either a HapticInputBinding or a str ("L"/"R")
        intensity_or_effect: float (intensity 0..1) or str (effect name)
        duration_ms: optional override for pulse duration (default _HAPTIC_PULSE_MS)
        """
        if isinstance(binding_or_side, HapticInputBinding):
            # Pattern 1: haptic-input MIDI callback
            binding = binding_or_side
            intensity = intensity_or_effect or 0.0
            side = "L" if binding.trigger.upper() == "L2" else "R"
            effect = binding.effect
            pulse_ms = duration_ms if duration_ms is not None else _HAPTIC_PULSE_MS
            emit_signal = True
        else:
            # Pattern 2: latch tactile click
            side = str(binding_or_side).upper()
            effect = str(intensity_or_effect or "feedback").lower()
            intensity = 1.0  # Tactile click is full intensity
            pulse_ms = duration_ms if duration_ms is not None else 30
            emit_signal = False  # Don't emit haptic_event signal for internal clicks

        # Build the (l2, r2) tuple — only touch the bound side, leave the
        # other at its static config so the user's existing L2/R2 'feel'
        # selection survives the pulse on the opposite trigger.
        m = self._state.mapping
        if side == "L":
            new_pair = (effect, m.r2_haptic_effect)
        else:
            new_pair = (m.l2_haptic_effect, effect)
        with self._haptic_lock:
            self._write_trigger_pair(*new_pair)
            self._last_haptic_pair = new_pair

        if emit_signal:
            self.haptic_event.emit(side, effect, intensity)

        # Schedule a revert so the trigger relaxes back to the user's static
        # 'feel'. Each binding gets its own timer; if a flurry of notes lands
        # on the same trigger we just keep refreshing the latest revert.
        t = threading.Timer(pulse_ms / 1000.0, self._revert_to_static)
        t.daemon = True
        self._haptic_revert_timers.append(t)
        t.start()

    def _revert_to_static(self) -> None:
        """Restore the user's static L2/R2 trigger feel after a pulse."""
        m = self._state.mapping
        pair = (m.l2_haptic_effect, m.r2_haptic_effect)
        with self._haptic_lock:
            self._write_trigger_pair(*pair)
            self._last_haptic_pair = pair

    @staticmethod
    def _build_detector(cfg) -> Optional[CornerDetector]:
        if not cfg.enabled:
            return None
        try:
            return CornerDetector(n=cfg.n, r_enter=cfg.r_enter, r_exit=cfg.r_exit)
        except ValueError:
            return None

    def _run_calibration(self) -> None:
        assert self._reader is not None
        self.status.emit("Calibrating sticks — keep your hands off the controller...")
        result = calibrate(
            self._reader,
            on_progress=lambda f: self.calibration_progress.emit(f),
        )
        self._state.stick_offsets = result.offsets
        self.calibration_done.emit(
            result.offsets, result.severe_axes, result.significant_axes
        )

    def _loop(self) -> None:
        reader = self._reader
        midi = self._midi
        if reader is None or midi is None:
            return

        base_mapping = self._state.mapping
        offsets = self._state.stick_offsets

        # Derive loop constants from the base mapping (channel / hz never
        # change mid-performance; if user saves a different channel they'll
        # restart the bridge anyway).
        channel = base_mapping.midi_channel & 0x0F
        note_on = 0x90 | channel
        note_off = 0x80 | channel
        cc = 0xB0 | channel

        interval = 1.0 / max(base_mapping.poll_hz, 1)
        n_buttons = reader.num_buttons()
        n_axes = reader.num_axes()
        n_hats = reader.num_hats()

        try:
            while self._running:
                t0 = time.perf_counter()
                reader.pump()

                # Refresh base mapping reference in case set_mapping was called
                # between ticks (e.g. user saved edits while bridge was running).
                base_mapping = self._state.mapping

                # A/B compare — track button edge and update _ab_b_active.
                self._update_ab_state(reader, base_mapping, n_buttons)

                # Active mapping: B preset when A/B button held, else base.
                mapping = self._active_mapping()
                deadzone = mapping.deadzone

                self._poll_buttons(reader, mapping, midi, note_on, note_off, n_buttons)
                self._poll_axes(reader, mapping, offsets, deadzone, midi, cc, n_axes)
                self._poll_polar_sticks(reader, mapping, offsets, midi, cc, n_axes)
                self._poll_corners(reader, mapping, offsets, deadzone, midi, note_on, note_off, n_axes)
                if n_hats > 0:
                    self._poll_hat(reader, mapping, midi, note_on, note_off)
                if self._ds_handle is not None:
                    self._poll_dualsense(mapping, midi, cc, t0)

                # Sleep the remainder of the interval — keeps CPU usage low
                elapsed = time.perf_counter() - t0
                if elapsed < interval:
                    time.sleep(interval - elapsed)
        finally:
            self._silence_all(midi, mapping, channel)
            self._cleanup()
            self.stopped.emit()
            self.status.emit("Stopped")

    # ---------------------------------------------------------- inner-loop chunks

    def _update_ab_state(self, reader, base_mapping: Mapping, n_buttons: int) -> None:
        """Track A/B compare button edge and update _ab_b_active.

        Only runs when the feature is enabled and a valid button is configured.
        Logs once on each A→B and B→A transition so the operator can see it.
        """
        m = base_mapping
        if not m.ab_compare_enabled or m.ab_compare_button < 0 or self._b_mapping is None:
            if self._ab_b_active:
                self._ab_b_active = False
            return
        btn = m.ab_compare_button
        if btn >= n_buttons:
            return
        held = bool(reader.get_button(btn))
        if held and not self._ab_b_active:
            self._ab_b_active = True
            self.status.emit(f"A/B: swapped to B preset '{m.ab_b_preset_slug}'")
        elif not held and self._ab_b_active:
            self._ab_b_active = False
            self.status.emit("A/B: back to A preset")

    def _active_mappings_view(self, mapping):
        """Return (buttons, axes, hats) dicts with the shift overlay merged in.

        If the shift layer is enabled AND the designated shift button is
        currently held, each dict is formed as {**base, **overlay} so the
        overlay wins on any key it defines while unmentioned controls fall
        through unchanged. Otherwise the base mapping dicts are returned
        as-is (no copy, no allocation).
        """
        sl = mapping.shift_layer
        if (sl.enabled
                and sl.shift_button >= 0
                and self._prev_buttons.get(sl.shift_button, False)):
            buttons = {**mapping.buttons, **sl.buttons}
            axes = {**mapping.axes, **sl.axes}
            hats = {**mapping.hats, **sl.hats}
            return buttons, axes, hats
        return mapping.buttons, mapping.axes, mapping.hats

    def _poll_setlist_buttons(self, reader, mapping, n_buttons) -> None:
        """Detect press edges on the setlist next/prev buttons and emit setlist_step.

        Only runs when setlist is enabled and has at least one preset. Uses
        the same was/now edge detection as every other button path so rapid
        taps don't fire multiple steps per press.
        """
        sl = mapping.setlist
        if not sl.enabled or not sl.presets:
            return
        total = len(sl.presets)

        for delta, btn_idx in ((+1, sl.next_button), (-1, sl.prev_button)):
            if btn_idx < 0 or btn_idx >= n_buttons:
                continue
            pressed = bool(reader.get_button(btn_idx))
            was = self._prev_buttons.get(btn_idx, False)
            if pressed and not was:
                # Rising edge — advance the index
                new_index = self._setlist_index + delta
                if sl.wrap:
                    new_index = new_index % total
                else:
                    new_index = max(0, min(total - 1, new_index))
                self._setlist_index = new_index
                slug = sl.presets[new_index]
                self.setlist_step.emit(slug, new_index, total)
            # Always track state so we can detect the next edge.
            if pressed != was:
                self._prev_buttons[btn_idx] = pressed
                self.button_state.emit(btn_idx, pressed)

    def _poll_pattern_buttons(self, reader, mapping, midi, n_buttons: int) -> None:
        """Handle pattern-recorder button edges (record / overdub / cancel).

        Detects rising/falling edges on the three configured buttons and drives
        the PatternEngine state machine accordingly.  Also provides the
        MIDI-send callback to the engine so playback events go to the real port.
        """
        cfg: PatternRecorderConfig = mapping.pattern_recorder

        def _send(status: int, d1: int, d2: int) -> None:
            if midi is None:
                return
            try:
                midi.port.send_message([status, d1, d2])
                self.midi_sent.emit()
                self._emit_midi_message("sent", status, d1, d2, f"PAT d1={d1} d2={d2}")
            except Exception:
                pass

        def _read_btn(idx: int) -> bool:
            if idx < 0 or idx >= n_buttons:
                return False
            return bool(reader.get_button(idx))

        rec_held = _read_btn(cfg.record_button)
        ovd_held = _read_btn(cfg.overdub_button)
        cxl_held = _read_btn(cfg.cancel_button)

        # Lazily create the engine on first enable
        if self._pattern_engine is None or (
            self._pattern_engine.loop_ms
            != self._compute_pattern_loop_ms(mapping)
        ):
            self._pattern_engine = PatternEngine(
                send_fn=_send,
                bpm=mapping.midi_clock.bpm if mapping.midi_clock.enabled else 120.0,
                loop_length_bars=cfg.loop_length_bars,
                quantize_to_grid=cfg.quantize_to_grid,
            )
        else:
            # Always refresh the send_fn so it captures the current midi handle
            self._pattern_engine._send_fn = _send

        eng = self._pattern_engine

        # --- record button: hold = record, release = play
        rec_edge_down = rec_held and not self._pattern_rec_was_held
        rec_edge_up = not rec_held and self._pattern_rec_was_held

        if rec_edge_down and eng.state == PatternState.IDLE:
            eng.start_recording()
        if rec_edge_up and eng.state == PatternState.RECORDING:
            eng.stop_recording()

        # --- overdub button: hold = overdub (only while playing)
        if ovd_held and not self._pattern_ovd_was_held:
            if eng.state == PatternState.PLAYING:
                eng.start_overdub()
        if not ovd_held and self._pattern_ovd_was_held:
            if eng.state == PatternState.OVERDUB:
                eng.stop_overdub()

        # --- cancel button: press = stop loop (any playing/recording state)
        if cxl_held and not self._pattern_cxl_was_held:
            if eng.state in (PatternState.PLAYING, PatternState.OVERDUB, PatternState.RECORDING):
                eng.stop_loop()

        self._pattern_rec_was_held = rec_held
        self._pattern_ovd_was_held = ovd_held
        self._pattern_cxl_was_held = cxl_held

    def _compute_pattern_loop_ms(self, mapping: "Mapping") -> int:
        """Compute the expected loop duration in ms from the current mapping config."""
        bpm = mapping.midi_clock.bpm if mapping.midi_clock.enabled else 120.0
        bars = mapping.pattern_recorder.loop_length_bars
        beat_ms = (60.0 / max(1.0, bpm)) * 1000.0
        return max(1, int(round(beat_ms * 4.0 * bars)))

    def _poll_buttons(self, reader, mapping, midi, note_on, note_off, n_buttons) -> None:
        # --- MIDI clock button handling (tap-tempo, start, stop) ---
        clk = mapping.midi_clock
        if clk.enabled:
            self._poll_clock_buttons(reader, midi, clk, n_buttons)

        # --- Setlist step-through ---
        self._poll_setlist_buttons(reader, mapping, n_buttons)

        # --- Pattern recorder ---
        if mapping.pattern_recorder.enabled:
            self._poll_pattern_buttons(reader, mapping, midi, n_buttons)
            # Advance the loop playback tick each poll cycle
            if self._pattern_engine is not None:
                self._pattern_engine.tick()

        buttons, _axes, _hats = self._active_mappings_view(mapping)
        osc_only = self._osc_only()
        for btn_idx, note in buttons.items():
            if btn_idx >= n_buttons:
                continue
            pressed = reader.get_button(btn_idx)
            was = self._prev_buttons.get(btn_idx, False)

            # Get per-button channel, falling back to global
            btn_channel = self._channel_for_button(mapping, btn_idx)
            btn_note_on = 0x90 | btn_channel
            btn_note_off = 0x80 | btn_channel

            # Per-button modifier gate check (feature #1)
            btn_cfg = mapping.button_configs.get(btn_idx)
            if btn_cfg and btn_cfg.gate_button is not None:
                gate_held = bool(reader.get_button(btn_cfg.gate_button))
                was_gate_held = self._button_gate_was_held.get(btn_idx, False)
                self._button_gate_was_held[btn_idx] = gate_held
                # Use the same gate_decision logic as triggers
                should_emit, send_release = shaping.gate_decision(gate_held, was_gate_held)
                if not should_emit:
                    # Silently skip if gate is not held
                    if pressed != was:
                        self._prev_buttons[btn_idx] = pressed
                    continue
                if send_release:
                    # Gate just released — send the configured release value as velocity
                    if not osc_only:
                        midi.port.send_message([btn_note_on, note, btn_cfg.gate_release_value])
                        self._rtp_send(btn_note_on, note, btn_cfg.gate_release_value)
                        self.midi_sent.emit()
                        self._emit_midi_message("sent", btn_note_on, note, btn_cfg.gate_release_value, f"NOTE-ON #{note}")
                    self._send_osc_button(btn_idx, False)
                    self._prev_buttons[btn_idx] = False
                    self.button_state.emit(btn_idx, False)
                    continue

            if pressed and not was:
                # Latency self-test: capture button-event timestamp (input side).
                if self._latency_test_active:
                    _latency_test.tracker().record_input(time.perf_counter())
                # Macro playback: if this button is bound to a macro, play it
                # instead of (or in addition to) the normal note. Each playback
                # gets its own QTimer chain so simultaneous macros work fine.
                macro_name = mapping.macro_bindings.get(btn_idx)
                if macro_name:
                    macro = next((m for m in mapping.macros if m.name == macro_name), None)
                    if macro:
                        if macro.arp_mode:
                            # Arp mode: start continuous playback while held
                            if btn_idx not in self._arp_state:
                                self._start_arp(btn_idx, macro, midi)
                        else:
                            self._play_macro(macro, midi)
                # Use velocity from button config if available, else default to 100
                velocity = btn_cfg.velocity if btn_cfg else 100

                # Apply velocity jitter if configured
                if btn_cfg and btn_cfg.velocity_jitter > 0:
                    jitter = random.randint(-btn_cfg.velocity_jitter, btn_cfg.velocity_jitter)
                    velocity = max(0, min(127, velocity + jitter))

                if not osc_only:
                    # Latency self-test: capture MIDI-send timestamp (output side).
                    if self._latency_test_active:
                        _latency_test.tracker().record_output(time.perf_counter())
                    qcfg = mapping.quantize

                    # Apply timing jitter if configured
                    if btn_cfg and btn_cfg.timing_jitter_ms > 0:
                        delay_ms = random.randint(0, btn_cfg.timing_jitter_ms)
                        if qcfg.enabled and qcfg.quantize_buttons:
                            q_delay = self._quantize_delay_ms(qcfg)
                            # Combine quantize delay and timing jitter
                            total_delay = q_delay + delay_ms
                            self._schedule_quantized_note(btn_note_on, note, velocity, total_delay)
                        else:
                            # Schedule the note-on with timing jitter via QTimer
                            # Use default args to capture current values (not by reference)
                            QTimer.singleShot(delay_ms, lambda m=midi, s=btn_note_on, n=note, v=velocity: self._send_jittered_note(m, s, n, v))
                    elif qcfg.enabled and qcfg.quantize_buttons:
                        delay = self._quantize_delay_ms(qcfg)
                        self._schedule_quantized_note(btn_note_on, note, velocity, delay)
                    else:
                        self._send_note_on(midi, btn_note_on, note, velocity)
                        self._rtp_send(btn_note_on, note, velocity)
                        self._record_midi_send(btn_note_on, note, velocity)
                        self.midi_sent.emit()
                        self._emit_midi_message("sent", btn_note_on, note, velocity, f"NOTE-ON #{note}")
                        # Start repeat if enabled for this button
                        if btn_cfg and btn_cfg.repeat_enabled:
                            self._start_repeat(btn_idx, midi, btn_note_on, note, velocity, btn_cfg)
                self._send_osc_button(btn_idx, True)
                _usage_stats.tracker().record("button", btn_idx)
            elif not pressed and was:
                # Stop arp playback if active on this button
                if btn_idx in self._arp_state:
                    self._stop_arp(btn_idx, mapping, midi)
                # Stop repeat if active on this button
                if btn_idx in self._repeat_state:
                    self._stop_repeat(btn_idx, midi, btn_note_off, note)
                else:
                    if not osc_only:
                        self._send_note_off(midi, btn_note_off, note, 0)
                        self._record_midi_send(btn_note_off, note, 0)
                        self.midi_sent.emit()
                        self._emit_midi_message("sent", btn_note_off, note, 0, f"NOTE-OFF #{note}")
                self._send_osc_button(btn_idx, False)
            if pressed != was:
                self._prev_buttons[btn_idx] = pressed
                self.button_state.emit(btn_idx, pressed)

        # --- Polyphonic Aftertouch (PolyAT) for held buttons
        self._poll_poly_aftertouch(reader, mapping, midi, buttons, n_buttons)

    def _poll_poly_aftertouch(self, reader, mapping, midi, buttons, n_buttons) -> None:
        """Send PolyAT messages for held buttons with poly_aftertouch enabled.

        Rate-limited to 30Hz to avoid swamping MIDI. Tracks last-sent pressure
        per (button, note) to deduplicate.
        """
        now_ms = time.time() * 1000.0
        # Rate limit to 30Hz (~33ms between sends)
        if now_ms - self._poly_at_last_send_ms < 33.0:
            return

        if midi is None:
            return

        osc_only = self._osc_only()
        if osc_only:
            return

        any_sent = False
        for btn_idx, note in buttons.items():
            if btn_idx >= n_buttons:
                continue
            pressed = reader.get_button(btn_idx)
            if not pressed:
                # Clean up state when button is released
                self._poly_at_last_pressure.pop((btn_idx, note), None)
                continue

            # Get button config and check if PolyAT is enabled
            btn_cfg = mapping.button_configs.get(btn_idx)
            if not btn_cfg or not btn_cfg.poly_aftertouch.enabled:
                continue

            # Get pressure from configured source
            pressure_0_to_1 = self._get_poly_at_pressure(
                reader, btn_cfg.poly_aftertouch.pressure_source
            )
            pressure_7bit = round(pressure_0_to_1 * 127.0)
            pressure_7bit = max(0, min(127, pressure_7bit))

            # Deduplicate: only send if pressure changed
            last_pressure = self._poly_at_last_pressure.get((btn_idx, note), -1)
            if pressure_7bit == last_pressure:
                continue

            # Get per-button channel
            btn_channel = self._channel_for_button(mapping, btn_idx)
            poly_at = 0xA0 | btn_channel  # Polyphonic aftertouch status

            try:
                midi.port.send_message([poly_at, note, pressure_7bit])
                self._rtp_send(poly_at, note, pressure_7bit)
                self._record_midi_send(poly_at, note, pressure_7bit)
                self._emit_midi_message(
                    "sent", poly_at, note, pressure_7bit,
                    f"POLY-AT #{note} pressure={pressure_7bit}"
                )
                self._poly_at_last_pressure[(btn_idx, note)] = pressure_7bit
                any_sent = True
            except Exception:
                pass

        if any_sent:
            self.midi_sent.emit()
            self._poly_at_last_send_ms = now_ms

    def _poll_axes(self, reader, mapping, offsets, deadzone, midi, cc, n_axes) -> None:
        _buttons, axes, _hats = self._active_mappings_view(mapping)
        osc_only = self._osc_only()
        for axis_idx, cc_num in axes.items():
            if axis_idx >= n_axes:
                continue
            raw = reader.get_axis(axis_idx)
            if axis_idx in STICK_AXES:
                # Apply offset for drift compensation
                raw = max(-1.0, min(1.0, raw - offsets.get(axis_idx, 0.0)))
                # Select the appropriate stick config (left = 0,1; right = 2,3)
                stick_cfg = mapping.left_stick if axis_idx < 2 else mapping.right_stick
                # Apply shaping (deadzone, curves, etc.)
                raw = shaping.apply_stick_shape(
                    raw,
                    inner_deadzone=stick_cfg.inner_deadzone,
                    outer_clamp=stick_cfg.outer_clamp,
                    curve=stick_cfg.curve,
                    curve_amount=stick_cfg.curve_amount,
                )
                # Stick-flick velocity notes (feature #A)
                if stick_cfg.flick.enabled:
                    self._check_stick_flick(axis_idx, raw, stick_cfg.flick, mapping, midi)
                # Random-mod (feature #A2) — sample a random CC at configured rate
                if stick_cfg.random_mod_enabled:
                    self._tick_random_mod(axis_idx, stick_cfg, mapping, midi)
                # LFO modulator — blend free-running waveform with user input
                if stick_cfg.lfo.enabled:
                    raw = self._apply_lfo(axis_idx, raw, stick_cfg.lfo, mapping)
                # Pitch bend — 14-bit MIDI from configured axis
                if stick_cfg.pitch_bend_enabled:
                    # Read raw axis value; if pitch_bend_axis is "y" and we're on x-axis,
                    # we'll read the companion y-axis value from the reader instead.
                    if stick_cfg.pitch_bend_axis == "x" and axis_idx < 2:
                        # Left stick X or right stick X — already have raw
                        pb_raw = raw
                    elif stick_cfg.pitch_bend_axis == "y" and axis_idx < 2:
                        # Want Y axis, but currently processing X
                        pb_raw = reader.get_axis(axis_idx + 1)
                        # Apply same shaping to the Y axis
                        pb_raw = shaping.apply_stick_shape(
                            pb_raw,
                            inner_deadzone=stick_cfg.inner_deadzone,
                            outer_clamp=stick_cfg.outer_clamp,
                            curve=stick_cfg.curve,
                            curve_amount=stick_cfg.curve_amount,
                        )
                    else:
                        # Right stick Y (axis 3) wants X (axis 2), or other edge case
                        pb_axis_for_read = axis_idx - 1 if stick_cfg.pitch_bend_axis == "x" else axis_idx
                        pb_raw = reader.get_axis(pb_axis_for_read)
                        pb_raw = shaping.apply_stick_shape(
                            pb_raw,
                            inner_deadzone=stick_cfg.inner_deadzone,
                            outer_clamp=stick_cfg.outer_clamp,
                            curve=stick_cfg.curve,
                            curve_amount=stick_cfg.curve_amount,
                        )
                    # Convert -1..+1 to 14-bit 0..16383, centre at 8192
                    pb_14bit = int(round((pb_raw + 1.0) * 8191.5))
                    pb_14bit = max(0, min(16383, pb_14bit))
                    # Only send if changed (dedupe)
                    if self._prev_pitch_bend.get(axis_idx) != pb_14bit:
                        axis_channel = self._channel_for_axis(mapping, axis_idx)
                        # Send pitch bend: 0xE0 | channel, lsb, msb
                        lsb = pb_14bit & 0x7F
                        msb = (pb_14bit >> 7) & 0x7F
                        if not self._osc_only():
                            midi.port.send_message([0xE0 | axis_channel, lsb, msb])
                            self.midi_sent.emit()
                        self._rtp_send(0xE0 | axis_channel, lsb, msb)
                        self._record_midi_send(0xE0 | axis_channel, lsb, msb)
                        self._emit_midi_message("sent", 0xE0 | axis_channel, lsb, msb, f"PITCH_BEND:{pb_14bit}")
                        self._prev_pitch_bend[axis_idx] = pb_14bit
                # Convert to 0..127 range
                val = int(round((raw + 1.0) * 63.5))
                val = max(0, min(127, val))
            elif axis_idx == L2_AXIS or axis_idx == R2_AXIS:
                # Triggers run through the shaping pipeline — supports linear
                # (default), ceiling-cap, inverted, and latch modes. Latch
                # mode mutates the per-trigger TriggerState held on `self`.
                cfg = mapping.l2_trigger if axis_idx == L2_AXIS else mapping.r2_trigger
                pressure = shaping.normalise_trigger_pressure(raw)
                val = shaping.apply_trigger(
                    pressure,
                    mode=cfg.mode,
                    ceiling=cfg.ceiling,
                    latch_threshold=cfg.latch_threshold,
                    state=self._trigger_states.get(axis_idx),
                )

                # Feature #10: Adaptive trigger tactile click at threshold
                # In latch mode, detect threshold crossing and fire haptic feedback
                if cfg.mode == "latch" and cfg.tactile_click:
                    trigger_state = self._trigger_states.get(axis_idx)
                    if trigger_state is not None:
                        latch_now = trigger_state.latched_on
                        latch_before = self._prev_latch_state.get(axis_idx, False)
                        if latch_now != latch_before:
                            # Threshold crossed — fire 30ms haptic feedback on same trigger
                            trigger_side = "L" if axis_idx == L2_AXIS else "R"
                            self._fire_haptic(trigger_side, "feedback", duration_ms=30)
                        self._prev_latch_state[axis_idx] = latch_now

                # Modifier-gate check. If the trigger is configured with a
                # `gate_button`, the trigger is silent unless the user is
                # holding that button. On the release edge we send the
                # configured rest value exactly once so the receiver doesn't
                # keep hearing the last value forever.
                if cfg.gate_button is not None:
                    gate_held = bool(reader.get_button(cfg.gate_button))
                    was_held = self._trigger_gate_was_held.get(axis_idx, False)
                    self._trigger_gate_was_held[axis_idx] = gate_held
                    should_emit, send_release = shaping.gate_decision(gate_held, was_held)
                    if not should_emit:
                        continue
                    if send_release:
                        val = cfg.gate_release_value

                # Trigger aftertouch (feature #B): emit 0xD0 past threshold
                if cfg.aftertouch.enabled:
                    at_cfg = cfg.aftertouch
                    raw_pressure = shaping.normalise_trigger_pressure(
                        reader.get_axis(axis_idx)
                    )
                    if raw_pressure > at_cfg.threshold:
                        at_val = int(round(
                            (raw_pressure - at_cfg.threshold)
                            / (1.0 - at_cfg.threshold) * 127
                        ))
                        at_val = max(0, min(127, at_val))
                        at_ch = (
                            at_cfg.channel_override
                            if at_cfg.channel_override >= 0
                            else mapping.midi_channel
                        ) & 0x0F
                        if not self._osc_only():
                            midi.port.send_message([0xD0 | at_ch, at_val])
                            self.midi_sent.emit()
                            self._emit_midi_message(
                                "sent", 0xD0 | at_ch, at_val, 0,
                                f"AFTERTOUCH {at_val}",
                            )
                        self._at_active[axis_idx] = True
                    elif self._at_active.get(axis_idx):
                        # Dropped below threshold — send AT=0 to zero out
                        at_ch = (
                            at_cfg.channel_override
                            if at_cfg.channel_override >= 0
                            else mapping.midi_channel
                        ) & 0x0F
                        if not self._osc_only():
                            midi.port.send_message([0xD0 | at_ch, 0])
                            self.midi_sent.emit()
                        self._at_active[axis_idx] = False

                # Bow mode: velocity-driven expression CC (trigger movement)
                if cfg.bow_mode:
                    now_ts = time.perf_counter()
                    prev_pressure, prev_ts = self._bow_state.get(axis_idx, (pressure, now_ts))

                    # Compute pressure change rate (units/sec)
                    dt = now_ts - prev_ts
                    velocity = (pressure - prev_pressure) / dt if dt > 1e-6 else 0.0

                    # Clamp velocity to 0..1+ range for scaling
                    velocity = abs(velocity)

                    # Below minimum velocity = silence; otherwise scale by config
                    if velocity > cfg.bow_min_velocity:
                        bow_value = velocity * cfg.bow_velocity_scale
                        # Clamp final CC value to 0..127
                        bow_cc_val = int(round(max(0.0, min(1.0, bow_value)) * 127.0))
                    else:
                        bow_cc_val = 0

                    # Send the expression CC alongside the main trigger value
                    axis_channel = self._channel_for_axis(mapping, axis_idx)
                    bow_cc_status = 0xB0 | axis_channel
                    if not self._osc_only():
                        midi.port.send_message([bow_cc_status, cfg.bow_cc, bow_cc_val])
                        self._rtp_send(bow_cc_status, cfg.bow_cc, bow_cc_val)
                        self._record_outbound_cc(axis_channel, cfg.bow_cc, bow_cc_val)
                        self._record_midi_send(bow_cc_status, cfg.bow_cc, bow_cc_val)
                        self.midi_sent.emit()
                        self._emit_midi_message("sent", bow_cc_status, cfg.bow_cc, bow_cc_val,
                                              f"BOW-CC#{cfg.bow_cc}={bow_cc_val}")

                    # Update state for next tick
                    self._bow_state[axis_idx] = (pressure, now_ts)
            else:
                # Other axes (HID hats, generic analogs) use the legacy
                # -1..1 → 0..127 remap so unknown controllers keep working.
                val = int(round((raw + 1.0) * 63.5))
                val = max(0, min(127, val))
            # CC smoothing: if stick config has cc_smoothing_ms > 0, interpolate
            # the CC value over time instead of jumping in steps
            if (axis_idx in STICK_AXES and
                axis_idx < 2 and mapping.left_stick.cc_smoothing_ms > 0) or \
               (axis_idx in STICK_AXES and
                axis_idx >= 2 and mapping.right_stick.cc_smoothing_ms > 0):
                stick_cfg = mapping.left_stick if axis_idx < 2 else mapping.right_stick
                smoothing_ms = stick_cfg.cc_smoothing_ms
                key = (axis_idx, cc_num)
                now_ms = time.time() * 1000.0

                # Initialize or update smoothing state
                if key not in self._cc_smooth_state:
                    # First time seeing this axis at this cc — start smoothing
                    self._cc_smooth_state[key] = (val, val, now_ms)

                current_val, target_val, started_ms = self._cc_smooth_state[key]

                # If target changed, reset the smoothing start time
                if target_val != val:
                    self._cc_smooth_state[key] = (current_val, val, now_ms)
                    target_val = val
                    started_ms = now_ms

                # Compute interpolated value
                elapsed_ms = now_ms - started_ms
                if elapsed_ms >= smoothing_ms:
                    # Smoothing complete, snap to target
                    send_val = val
                    self._cc_smooth_state[key] = (val, val, now_ms)
                else:
                    # Lerp: current + (target - current) * (elapsed / duration)
                    progress = elapsed_ms / smoothing_ms
                    send_val = int(round(current_val + (target_val - current_val) * progress))
                    send_val = max(0, min(127, send_val))
                    self._cc_smooth_state[key] = (send_val, target_val, started_ms)
            else:
                send_val = val

            if self._prev_cc.get(axis_idx) != send_val:
                if not osc_only:
                    axis_channel = self._channel_for_axis(mapping, axis_idx)
                    axis_cc = 0xB0 | axis_channel
                    self._send_cc(midi, axis_cc, cc_num, send_val)
                    self._rtp_send(axis_cc, cc_num, send_val)
                    self._record_outbound_cc(axis_channel, cc_num, send_val)
                    self._record_midi_send(axis_cc, cc_num, send_val)
                    self.midi_sent.emit()
                    self._emit_midi_message("sent", axis_cc, cc_num, send_val, f"CC#{cc_num}")
                _usage_stats.tracker().record("axis", axis_idx)
                # OSC sends a 0..1 float, MIDI a 0..127 int — keep both
                # streams in lock-step but de-dup against last-sent 0..127.
                if self._osc is not None and self._prev_osc_axes.get(axis_idx) != send_val:
                    self._send_osc_axis(axis_idx, send_val / 127.0)
                    self._prev_osc_axes[axis_idx] = send_val
                self._prev_cc[axis_idx] = send_val
                self._emit_axis(axis_idx, raw)

            # Track stick chord values — collect X,Y pairs then poll
            if axis_idx in STICK_AXES:
                stick_idx = axis_idx // 2  # 0,1 -> stick 0; 2,3 -> stick 1
                is_x = (axis_idx % 2 == 0)
                # raw here is the shaped stick value from earlier in the loop
                if stick_idx not in self._stick_chord_values:
                    self._stick_chord_values[stick_idx] = (0.0, 0.0)
                x, y = self._stick_chord_values[stick_idx]
                if is_x:
                    x = raw
                else:
                    y = raw
                self._stick_chord_values[stick_idx] = (x, y)

                # When we've just processed the Y axis (axis 1 or 3), call chord polling
                if not is_x:
                    stick_cfg = mapping.left_stick if stick_idx == 0 else mapping.right_stick
                    self._poll_stick_chords(stick_idx, x, y, stick_cfg, mapping, midi)


    def _check_stick_flick(self, axis_idx: int, shaped_val: float,
                           flick_cfg, mapping: Mapping, midi) -> None:
        """Detect rapid stick movement and fire a velocity-proportional note.

        Called per-tick for each enabled stick axis. Computes axis velocity
        (units/sec), and on the first tick where:
          - |velocity| > speed_threshold, AND
          - shaped_val magnitude > 0.7 (stick clearly moved in that direction)
        fires the appropriate directional note with velocity scaled by speed.
        Uses a rising-edge guard so rapid-fire repeats don't happen while the
        stick stays at the destination.
        """
        now_ts = time.perf_counter()
        prev_val, prev_ts = self._flick_state.get(axis_idx, (0.0, now_ts))

        # Compute axis velocity in units/sec
        dt = now_ts - prev_ts
        velocity = (shaped_val - prev_val) / dt if dt > 1e-6 else 0.0

        # Update history
        self._flick_state[axis_idx] = (shaped_val, now_ts)

        if not flick_cfg.enabled:
            return

        speed = abs(velocity)
        if speed < flick_cfg.speed_threshold:
            return

        # Determine direction and magnitude threshold
        # axis_idx 0/2 = X axis, 1/3 = Y axis
        is_x_axis = (axis_idx % 2 == 0)
        pos_flick = velocity > 0

        if is_x_axis:
            note = flick_cfg.note_pos_x if pos_flick else flick_cfg.note_neg_x
        else:
            note = flick_cfg.note_pos_y if pos_flick else flick_cfg.note_neg_y

        # Rising-edge guard: only fire if stick just crossed 0.7 in the direction
        # i.e. shaped_val >= 0.7 (positive) or <= -0.7 (negative) and wasn't before
        threshold = 0.7
        crossed = (pos_flick and shaped_val >= threshold and prev_val < threshold) or                   (not pos_flick and shaped_val <= -threshold and prev_val > -threshold)
        if not crossed:
            return

        # Scale velocity: clamp to velocity_min..velocity_max
        excess = speed - flick_cfg.speed_threshold
        gain = (flick_cfg.velocity_max - flick_cfg.velocity_min) / max(1.0, flick_cfg.speed_threshold * 4)
        midi_vel = int(round(flick_cfg.velocity_min + excess * gain))
        midi_vel = max(flick_cfg.velocity_min, min(flick_cfg.velocity_max, midi_vel))

        channel = self._channel_for_axis(mapping, axis_idx)
        note_on = 0x90 | channel
        note_off = 0x80 | channel

        if not self._osc_only():
            midi.port.send_message([note_on, note, midi_vel])
            midi.port.send_message([note_off, note, 0])
            self.midi_sent.emit()
            self._emit_midi_message("sent", note_on, note, midi_vel, f"FLICK NOTE-ON #{note}")

    def _poll_stick_chords(self, stick_index: int, x: float, y: float,
                           chord_cfg, mapping: Mapping, midi) -> None:
        """Detect stick direction and fire/release chord notes based on threshold.

        stick_index: 0 = left stick, 1 = right stick
        x, y: shaped stick values (-1..+1)
        chord_cfg: StickConfig with chord settings
        mapping: current mapping (for channel resolution)
        midi: MIDI port writer

        When magnitude exceeds threshold, the dominant axis + sign pick a
        direction (north/east/south/west), and the corresponding chord notes
        fire (note-on). When magnitude drops below threshold or direction
        changes, previous chord notes send note-off and the new direction's
        notes fire.
        """
        if not chord_cfg.chord_enabled:
            return

        # Compute magnitude and clamp to 0..1
        magnitude = (x ** 2 + y ** 2) ** 0.5
        magnitude = min(1.0, magnitude)

        # Determine direction based on dominant axis
        # Defaults to None if below threshold
        direction: Optional[str] = None
        if magnitude > chord_cfg.chord_threshold:
            # Pick direction from dominant axis (X or Y) and sign
            abs_x = abs(x)
            abs_y = abs(y)
            if abs_x > abs_y:
                direction = "east" if x > 0 else "west"
            else:
                direction = "north" if y > 0 else "south"

        # Get previous direction and current notes
        prev_direction = self._stick_chord_state.get(stick_index)
        current_notes = self._stick_chord_state.get(f"{stick_index}_notes", [])

        # Direction changed or dropped below threshold
        if prev_direction != direction:
            # Send note-off for previously held notes
            if current_notes and not self._osc_only():
                channel = (
                    chord_cfg.chord_channel
                    if chord_cfg.chord_channel is not None
                    else mapping.midi_channel
                ) & 0x0F
                note_off = 0x80 | channel
                for note in current_notes:
                    try:
                        midi.port.send_message([note_off, note, 0])
                        self.midi_sent.emit()
                        self._emit_midi_message("sent", note_off, note, 0,
                                              f"CHORD NOTE-OFF #{note}")
                    except Exception:
                        pass

            # Fire note-on for new direction (if any)
            new_notes: List[int] = []
            if direction is not None:
                chord_map = {
                    "north": chord_cfg.chord_north,
                    "east": chord_cfg.chord_east,
                    "south": chord_cfg.chord_south,
                    "west": chord_cfg.chord_west,
                }
                new_notes = chord_map.get(direction, [])

                if new_notes and not self._osc_only():
                    channel = (
                        chord_cfg.chord_channel
                        if chord_cfg.chord_channel is not None
                        else mapping.midi_channel
                    ) & 0x0F
                    note_on = 0x90 | channel
                    for note in new_notes:
                        try:
                            midi.port.send_message([note_on, note, chord_cfg.chord_velocity])
                            self.midi_sent.emit()
                            self._emit_midi_message("sent", note_on, note,
                                                  chord_cfg.chord_velocity,
                                                  f"CHORD NOTE-ON #{note}")
                        except Exception:
                            pass

            # Update state
            self._stick_chord_state[stick_index] = direction
            self._stick_chord_state[f"{stick_index}_notes"] = new_notes

    # ---------------------------------------------------------- arp playback

    def _start_arp(self, btn_idx: int, macro, midi) -> None:
        """Begin continuous arp playback for btn_idx.

        Creates a QTimer that fires every (1000 / arp_rate_hz) ms. Each tick
        plays the next event in the macro; when all events have been played it
        loops (arp_loop=True) or stops. State is stored in _arp_state[btn_idx].
        """
        interval_ms = max(1, int(round(1000.0 / max(0.01, macro.arp_rate_hz))))
        state = {"event_index": 0, "timer": None}

        def _tick():
            if not macro.events:
                return
            idx = state["event_index"]
            event = macro.events[idx % len(macro.events)]
            if midi is not None:
                try:
                    midi.port.send_message([event.status, event.data1, event.data2])
                    self.midi_sent.emit()
                    self._emit_midi_message(
                        "sent", event.status, event.data1, event.data2,
                        f"ARP d1={event.data1:3d} d2={event.data2:3d}"
                    )
                except Exception:
                    pass
            state["event_index"] = idx + 1
            if not macro.arp_loop and state["event_index"] >= len(macro.events):
                self._stop_arp(btn_idx, mapping=None, midi=midi)

        timer = QTimer(self)
        timer.setInterval(interval_ms)
        timer.timeout.connect(_tick)
        state["timer"] = timer
        self._arp_state[btn_idx] = state
        timer.start()

    def _stop_arp(self, btn_idx: int, mapping, midi) -> None:
        """Stop arp playback for btn_idx and send note-off for all playing notes.

        Iterates the macro's events and sends a note-off for every NOTE-ON found
        so no notes are left hanging.
        """
        state = self._arp_state.pop(btn_idx, None)
        if state is None:
            return
        timer = state.get("timer")
        if timer is not None:
            timer.stop()
        # Send note-off for every NOTE-ON in the macro so nothing hangs.
        if midi is not None:
            macro_name = None
            if mapping is not None:
                macro_name = mapping.macro_bindings.get(btn_idx)
            # Retrieve macro from mapping if available, else nothing to silence.
            macro = None
            if mapping is not None and macro_name:
                macro = next((m for m in mapping.macros if m.name == macro_name), None)
            if macro is not None:
                try:
                    for event in macro.events:
                        if (event.status & 0xF0) == 0x90 and event.data2 > 0:
                            note_off = (0x80 | (event.status & 0x0F))
                            midi.port.send_message([note_off, event.data1, 0])
                            self.midi_sent.emit()
                except Exception:
                    pass

    def _start_repeat(self, btn_idx: int, midi, btn_note_on: int, note: int,
                      initial_velocity: int, btn_cfg) -> None:
        """Start the repeat timer for a held button with repeat enabled.

        Schedules note-on repeats at repeat_rate_hz with optional velocity decay.
        State is stored in _repeat_state[btn_idx] as (timer, current_velocity).
        """
        if btn_idx in self._repeat_state:
            # Already repeating — ignore
            return

        interval_ms = int(1000.0 / max(1.0, btn_cfg.repeat_rate_hz))

        def schedule_repeat():
            # Calculate next velocity with decay
            current_vel = self._repeat_state.get(btn_idx, (None, initial_velocity))[1]
            next_vel = int(current_vel * (1.0 - btn_cfg.repeat_velocity_decay))
            next_vel = max(1, min(127, next_vel))  # Clamp to 1..127

            # Send the repeat note
            try:
                self._send_note_on(midi, btn_note_on, note, next_vel)
                self._rtp_send(btn_note_on, note, next_vel)
                self._record_midi_send(btn_note_on, note, next_vel)
                self.midi_sent.emit()
                self._emit_midi_message("sent", btn_note_on, note, next_vel, f"REPEAT #{note}")
            except Exception:
                pass

            # Update state with new velocity
            timer = self._repeat_state.get(btn_idx, (None, 0))[0]
            self._repeat_state[btn_idx] = (timer, next_vel)

            # Schedule the next repeat
            if timer is not None and btn_idx in self._repeat_state:
                timer.start(interval_ms)

        # Create the repeating timer
        timer = QTimer()
        timer.setSingleShot(False)
        timer.timeout.connect(schedule_repeat)
        timer.start(interval_ms)

        # Store state
        self._repeat_state[btn_idx] = (timer, initial_velocity)

    def _stop_repeat(self, btn_idx: int, midi, btn_note_off: int, note: int) -> None:
        """Stop the repeat timer for btn_idx and send note-off."""
        state = self._repeat_state.pop(btn_idx, None)
        if state is None:
            return

        timer, _velocity = state
        if timer is not None:
            timer.stop()

        # Send note-off
        try:
            midi.port.send_message([btn_note_off, note, 0])
            self._record_midi_send(btn_note_off, note, 0)
            self.midi_sent.emit()
            self._emit_midi_message("sent", btn_note_off, note, 0, f"NOTE-OFF #{note}")
        except Exception:
            pass

    def _tick_random_mod(self, axis_idx: int, stick_cfg, mapping: Mapping, midi) -> None:
        """Sample a random CC value at random_mod_rate_hz and send to random_mod_cc.

        Uses exponential smoothing: on each new sample the running value
        moves toward the target over random_mod_smoothing_ms.  Called once
        per poll tick for every enabled stick axis; the rate gate prevents
        sampling more often than the configured rate.
        """
        import random
        cfg = stick_cfg
        now_ms = time.time() * 1000.0
        last_ms, current_val = self._random_mod_state.get(axis_idx, (0.0, 64))

        interval_ms = 1000.0 / max(0.01, cfg.random_mod_rate_hz)
        if now_ms - last_ms >= interval_ms:
            # New sample
            target_val = random.randint(0, 127)
            # Exponential-ish one-pole smooth: alpha = dt / smoothing_ms
            smooth_ms = max(1, cfg.random_mod_smoothing_ms)
            alpha = min(1.0, interval_ms / smooth_ms)
            new_val = int(round(current_val + alpha * (target_val - current_val)))
            new_val = max(0, min(127, new_val))
            self._random_mod_state[axis_idx] = (now_ms, new_val)

            if not self._osc_only() and midi is not None:
                ch = self._channel_for_axis(mapping, axis_idx)
                axis_cc = 0xB0 | ch
                midi.port.send_message([axis_cc, cfg.random_mod_cc, new_val])
                self._record_outbound_cc(ch, cfg.random_mod_cc, new_val)
                self._record_midi_send(axis_cc, cfg.random_mod_cc, new_val)
                self.midi_sent.emit()
                self._emit_midi_message(
                    "sent", axis_cc, cfg.random_mod_cc, new_val,
                    f"RAND CC#{cfg.random_mod_cc}"
                )
        else:
            # Keep current value in state (no resample yet)
            self._random_mod_state.setdefault(axis_idx, (last_ms, current_val))

    def _apply_lfo(self, axis_idx: int, user_val: float,
                   lfo_cfg: "StickLfoConfig", mapping: "Mapping") -> float:
        """Compute the LFO sample for this axis and combine with user input.

        Advances `_lfo_phase[axis_idx]` each call based on elapsed wall-clock
        time and the configured rate_hz (or BPM-locked rate when
        phase_lock_to_bpm is True).  The LFO waveform is evaluated in -1..+1
        and combined with user_val according to blend_mode:

          add      — lfo*depth + user  (hard-clipped to ±1)
          replace  — lfo*depth when |user| < 0.05 (stick at rest), else user
          multiply — user * (1 + lfo*depth - 0.5)

        Returns the blended value in -1..+1.
        """
        import math
        import random as _random

        # Determine effective rate (Hz)
        rate = max(0.01, min(20.0, lfo_cfg.rate_hz))
        if lfo_cfg.phase_lock_to_bpm:
            bpm = mapping.midi_clock.bpm if mapping.midi_clock.enabled else 120.0
            rate = bpm / 60.0  # 1 cycle per beat (quarter-note subdivision)

        # Advance phase
        now = time.perf_counter()
        _TWO_PI = 2.0 * math.pi
        if axis_idx not in self._lfo_phase:
            self._lfo_phase[axis_idx] = 0.0
        # We compute phase directly from time so phase is consistent even when
        # the rate changes mid-performance, avoiding clicks.
        phase = (now * rate * _TWO_PI) % _TWO_PI

        # Evaluate waveform → -1..+1
        wf = lfo_cfg.waveform
        if wf == "sine":
            lfo_val = math.sin(phase)
        elif wf == "triangle":
            t = (now * rate) % 1.0
            lfo_val = 2.0 * abs(2.0 * t - 1.0) - 1.0
        elif wf == "square":
            lfo_val = 1.0 if phase < math.pi else -1.0
        elif wf == "saw":
            t = (now * rate) % 1.0
            lfo_val = 2.0 * t - 1.0
        elif wf == "random":
            # Sample-and-hold: one new sample per cycle
            cycle = int(now * rate)
            prev_cycle, prev_lfo = self._lfo_phase.get(axis_idx, (None, 0.0)) \
                if isinstance(self._lfo_phase.get(axis_idx), tuple) else (None, 0.0)
            if prev_cycle != cycle:
                lfo_val = _random.uniform(-1.0, 1.0)
                self._lfo_phase[axis_idx] = (cycle, lfo_val)
            else:
                lfo_val = prev_lfo
        else:
            lfo_val = math.sin(phase)  # fallback to sine

        # For non-random waveforms, store phase (kept as float for simplicity)
        if wf != "random":
            self._lfo_phase[axis_idx] = phase

        depth = max(0.0, min(1.0, lfo_cfg.depth))
        mode = lfo_cfg.blend_mode

        if mode == "replace":
            # At rest (|user| < 0.05) the LFO drives; otherwise user wins
            if abs(user_val) < 0.05:
                result = lfo_val * depth
            else:
                result = user_val
        elif mode == "multiply":
            result = user_val * (1.0 + lfo_val * depth - 0.5)
        else:
            # "add" (default / fallback)
            result = user_val + lfo_val * depth

        return max(-1.0, min(1.0, result))

    def _poll_polar_sticks(self, reader, mapping, offsets, midi, cc, n_axes) -> None:
        """Emit polar (angle, magnitude) pairs for sticks in polar_mode.

        Only runs for sticks configured with polar_mode=True. Converts cartesian
        (X, Y) into (angle 0..1, magnitude 0..1) and sends as 2 separate CCs.
        Deduplicates on last-sent CC value to avoid spam.
        """
        osc_only = self._osc_only()
        for side, x_idx, y_idx, stick_cfg in (
            ("L", 0, 1, mapping.left_stick),
            ("R", 2, 3, mapping.right_stick),
        ):
            if not stick_cfg.polar_mode or x_idx >= n_axes or y_idx >= n_axes:
                continue
            # Read raw stick axes and apply offset
            x = max(-1.0, min(1.0, reader.get_axis(x_idx) - offsets.get(x_idx, 0.0)))
            y = max(-1.0, min(1.0, reader.get_axis(y_idx) - offsets.get(y_idx, 0.0)))
            # Convert to polar (angle 0..1, magnitude 0..1)
            angle, magnitude = shaping.apply_polar(
                x, y, deadzone=stick_cfg.inner_deadzone
            )
            # Clamp outer radius if configured
            if stick_cfg.outer_clamp > 0.0:
                magnitude = min(1.0, magnitude / (1.0 - stick_cfg.outer_clamp))
            # Convert to MIDI CC values (0..127)
            angle_cc_val = int(round(angle * 127.0))
            mag_cc_val = int(round(magnitude * 127.0))
            angle_cc_val = max(0, min(127, angle_cc_val))
            mag_cc_val = max(0, min(127, mag_cc_val))
            # Track by synthetic axis indices to avoid collision with normal axes
            angle_key = f"polar_{side}_angle"
            mag_key = f"polar_{side}_mag"
            # Only send if changed
            if self._prev_cc.get(angle_key) != angle_cc_val:
                if not osc_only:
                    midi.port.send_message([cc, stick_cfg.polar_angle_cc, angle_cc_val])
                    self._record_outbound_cc(mapping.midi_channel, stick_cfg.polar_angle_cc, angle_cc_val)
                    self.midi_sent.emit()
                self._prev_cc[angle_key] = angle_cc_val
            if self._prev_cc.get(mag_key) != mag_cc_val:
                if not osc_only:
                    midi.port.send_message([cc, stick_cfg.polar_mag_cc, mag_cc_val])
                    self._record_outbound_cc(mapping.midi_channel, stick_cfg.polar_mag_cc, mag_cc_val)
                    self.midi_sent.emit()
                self._prev_cc[mag_key] = mag_cc_val

    def _poll_corners(self, reader, mapping, offsets, deadzone,
                      midi, note_on, note_off, n_axes) -> None:
        for side, detector, cfg, x_axis, y_axis in (
            ("L", self._left_corner, mapping.left_stick_corners, 0, 1),
            ("R", self._right_corner, mapping.right_stick_corners, 2, 3),
        ):
            if detector is None or x_axis >= n_axes or y_axis >= n_axes:
                continue
            x = reader.get_axis(x_axis) - offsets.get(x_axis, 0.0)
            y = reader.get_axis(y_axis) - offsets.get(y_axis, 0.0)
            event = detector.update(x, y)
            if event is None:
                continue

            if event.kind == "on":
                note = self._note_for_sector(cfg, event.sector)
                if note is not None:
                    midi.port.send_message([note_on, note, 127])
                    self.midi_sent.emit()
                    self._prev_corner_notes[side] = note
                    self.corner_triggered.emit(side, "on", event.sector)
                    # Fire corner haptic feedback on the matching trigger
                    self._fire_corner_haptic(side, mapping)
                    _usage_stats.tracker().record("corner", side)
            elif event.kind == "off":
                note = self._prev_corner_notes[side]
                if note is not None:
                    midi.port.send_message([note_off, note, 0])
                    self.midi_sent.emit()
                self._prev_corner_notes[side] = None
                self.corner_triggered.emit(side, "off", event.sector)
            elif event.kind == "switch":
                old_sector, new_sector = decode_switch(event)
                prev_note = self._prev_corner_notes[side]
                if prev_note is not None:
                    midi.port.send_message([note_off, prev_note, 0])
                    self.midi_sent.emit()
                self.corner_triggered.emit(side, "off", old_sector)
                new_note = self._note_for_sector(cfg, new_sector)
                if new_note is not None:
                    midi.port.send_message([note_on, new_note, 127])
                    self.midi_sent.emit()
                    self._prev_corner_notes[side] = new_note
                    self.corner_triggered.emit(side, "on", new_sector)

    @staticmethod
    def _note_for_sector(cfg, sector: int) -> Optional[int]:
        if cfg.scale_quantize_enabled:
            from .scales import note_for_sector
            return note_for_sector(cfg.scale_root, cfg.scale_name, sector, cfg.n)
        cfg.ensure_notes()
        if 0 <= sector < len(cfg.notes):
            return cfg.notes[sector]
        return None

    def _poll_hat(self, reader, mapping, midi, note_on, note_off) -> None:
        _buttons, _axes, hats = self._active_mappings_view(mapping)
        hat_x, hat_y = reader.get_hat(0)
        current = {
            "up":    hat_y ==  1,
            "down":  hat_y == -1,
            "left":  hat_x == -1,
            "right": hat_x ==  1,
        }
        for direction, note in hats.items():
            now = current[direction]
            was = self._prev_hat[direction]
            # Get per-hat channel, falling back to global
            hat_channel = self._channel_for_hat(mapping, direction)
            hat_note_on = 0x90 | hat_channel
            hat_note_off = 0x80 | hat_channel
            if now and not was:
                midi.port.send_message([hat_note_on, note, 127])
                self._rtp_send(hat_note_on, note, 127)
                self.midi_sent.emit()
                _usage_stats.tracker().record("hat", direction)
            elif not now and was:
                midi.port.send_message([hat_note_off, note, 0])
                self._rtp_send(hat_note_off, note, 0)
                self.midi_sent.emit()
            if now != was:
                self._prev_hat[direction] = now
                self.hat_state.emit(direction, now)

    def _poll_dualsense(self, mapping, midi, cc, now: float) -> None:
        handle = self._ds_handle
        if handle is None:
            return
        state = handle.read_state()
        if state is None:
            return

        # Battery — throttled to once every 5s
        if now - self._last_battery_poll >= self._battery_interval:
            snapshot = (state.battery.level_percent,
                        state.battery.charging,
                        state.battery.fully_charged)
            if snapshot != self._prev_battery:
                self._prev_battery = snapshot
                self.battery_changed.emit(*snapshot)
            self._last_battery_poll = now

            # Battery alert: fire once on threshold breach, reset on recovery
            self._check_battery_alert(mapping, midi, state.battery.level_percent)

        # Touchpad — primary finger always; second finger when two_finger mode on.
        if mapping.touchpad.enabled:
            tp_cfg = mapping.touchpad
            # DualSense touchpad click is button index 13 on the pygame layer.
            # click_to_arm uses this to gate the CC output.
            if tp_cfg.click_to_arm:
                # Note: the reader might not have button 13 if it's an older
                # or non-DualSense controller. Default to "not armed" in that case.
                self._touch_armed = False
                if 13 < self._reader.num_buttons() if self._reader else False:
                    self._touch_armed = bool(self._reader.get_button(13))

            ta = state.touch_a

            # Gesture mode: swipes + pinches (feature #8). Gesture wins if both
            # gesture_enabled and zone_mode are True.
            # Gesture mode: swipes + pinches (feature #8). Gesture wins if both
            # gesture_enabled and zone_mode are True.
            use_gesture = tp_cfg.gesture_enabled
            use_zone = tp_cfg.zone_mode and not tp_cfg.gesture_enabled

            # Track gesture state: touch start position + two-finger distance
            if use_gesture:
                if ta.active:
                    x_norm, y_norm = ta.normalized()
                    # Finger down: record start position if not already set
                    if self._touch_start_xy is None:
                        self._touch_start_xy = (x_norm, y_norm)
                        # Two-finger pinch: track initial separation
                        tb = state.touch_b
                        if tb.active and tp_cfg.two_finger:
                            bx, by = tb.normalized()
                            dist = ((x_norm - bx) ** 2 + (y_norm - by) ** 2) ** 0.5
                            self._touch_start_two_finger_distance = dist
                    
                    # Always update last position for swipe detection on release
                    self._touch_last_xy = (x_norm, y_norm)
                    
                    # Check for pinch in two-finger mode
                    if tp_cfg.two_finger:
                        tb = state.touch_b
                        if tb.active and self._touch_start_two_finger_distance is not None:
                            bx, by = tb.normalized()
                            dist = ((x_norm - bx) ** 2 + (y_norm - by) ** 2) ** 0.5
                            self._detect_pinch(midi, mapping.midi_channel, tp_cfg, dist,
                                              self._touch_start_two_finger_distance)
                else:
                    # Finger lifted: detect swipe using tracked start and end positions
                    if self._touch_start_xy is not None and self._touch_last_xy is not None:
                        self._detect_swipe(midi, mapping.midi_channel, tp_cfg, 
                                          self._touch_start_xy, self._touch_last_xy)
                    self._touch_start_xy = None
                    self._touch_last_xy = None
                    self._touch_start_two_finger_distance = None
                    self.touchpad_xy.emit(False, 0.0, 0.0)

            use_zone = tp_cfg.zone_mode and not tp_cfg.gesture_enabled

            # Track gesture state: touch start position + two-finger distance
            if use_gesture:
                if ta.active:
                    # Finger down: record start position
                    if self._touch_start_xy is None:
                        x_norm, y_norm = ta.normalized()
                        self._touch_start_xy = (x_norm, y_norm)
                        # Two-finger pinch: track initial separation
                        tb = state.touch_b
                        if tb.active and tp_cfg.two_finger:
                            bx, by = tb.normalized()
                            dist = ((x_norm - bx) ** 2 + (y_norm - by) ** 2) ** 0.5
                            self._touch_start_two_finger_distance = dist
                else:
                    # Finger lifted: detect swipe
                    if self._touch_start_xy is not None:
                        self._detect_swipe(midi, mapping.midi_channel, tp_cfg)
                    self._touch_start_xy = None
                    self._touch_start_two_finger_distance = None
                    self.touchpad_xy.emit(False, 0.0, 0.0)
                
                # Two-finger pinch detection
                if tp_cfg.two_finger:
                    tb = state.touch_b
                    if tb.active and self._touch_start_two_finger_distance is not None:
                        bx, by = tb.normalized()
                        x_norm, y_norm = ta.normalized()
                        dist = ((x_norm - bx) ** 2 + (y_norm - by) ** 2) ** 0.5
                        self._detect_pinch(midi, mapping.midi_channel, tp_cfg, dist,
                                          self._touch_start_two_finger_distance)

            # Zone mode: drum pad-style grid (feature #9)
            if use_zone and ta.active:
                x_norm, y_norm = ta.normalized()
                self.touchpad_xy.emit(True, x_norm, y_norm)
                self._send_zone_note(midi, cc, mapping.midi_channel, tp_cfg, x_norm, y_norm)
            elif use_zone and not ta.active:
                # Zone mode: finger lifted → note-off for current zone
                if self._prev_touchpad_zone is not None:
                    channel = mapping.midi_channel & 0x0F
                    note_off = 0x80 | channel
                    # Get the note for the previous zone
                    zone_idx = self._prev_touchpad_zone
                    note = tp_cfg.zone_notes[zone_idx] if zone_idx < len(tp_cfg.zone_notes) else tp_cfg.zone_notes[-1] if tp_cfg.zone_notes else 36
                    try:
                        midi.port.send_message([note_off, note, 0])
                    except Exception:
                        pass
                    self.midi_sent.emit()
                    self._prev_touchpad_zone = None
                self.touchpad_xy.emit(False, 0.0, 0.0)
            elif not use_zone:
                # Original CC mode (not zone mode)
                should_send = (ta.active or not tp_cfg.require_contact)
                if tp_cfg.click_to_arm:
                    should_send = should_send and self._touch_armed

                if should_send:
                    x_norm, y_norm = ta.normalized()
                    self.touchpad_xy.emit(ta.active, x_norm, y_norm)
                    self._send_touch_cc(midi, cc, tp_cfg.x_cc, x_norm, tp_cfg, "x")
                    self._send_touch_cc(midi, cc, tp_cfg.y_cc, y_norm, tp_cfg, "y")
                elif self._prev_touch_cc:
                    # Finger lifted — reset the GUI but keep the last MIDI value
                    # (Kaoss Pad behaviour: release leaves the modulator where it was).
                    self.touchpad_xy.emit(False, 0.0, 0.0)

                if tp_cfg.two_finger:
                    tb = state.touch_b
                    # Only fire the secondary CCs while the second finger is down,
                    # so producers can use 2-finger mode as a momentary modulator.
                    if tb.active:
                        should_send_b = not tp_cfg.click_to_arm or self._touch_armed
                        if should_send_b:
                            bx, by = tb.normalized()
                            self._send_touch_cc(midi, cc, tp_cfg.b_x_cc, bx, tp_cfg, "x")
                            self._send_touch_cc(midi, cc, tp_cfg.b_y_cc, by, tp_cfg, "y")

    def _check_battery_alert(self, mapping: Mapping, midi: OpenedPort,
                             percent: int) -> None:
        """Check battery level and fire MIDI note alert if threshold breached.

        Fires once when percent < threshold, resets when percent >= threshold.
        """
        cfg = mapping.battery_alert
        if not cfg.enabled:
            return

        threshold = cfg.threshold_percent
        below_threshold = percent < threshold

        if below_threshold and not self._battery_alert_fired:
            # Threshold just breached — fire the alert
            channel = (cfg.channel_override if cfg.channel_override is not None
                       else mapping.midi_channel) & 0x0F
            note_on = 0x90 | channel
            midi.port.send_message([note_on, cfg.note, cfg.velocity])
            self.midi_sent.emit()
            self._battery_alert_fired = True
        elif not below_threshold and self._battery_alert_fired:
            # Battery recovered above threshold — reset the alert so it fires again
            # on the next low-battery event
            self._battery_alert_fired = False

    def _fire_corner_haptic(self, side: str, mapping: Mapping) -> None:
        """Fire a short haptic pulse on the stick's matching trigger.

        L-side corner → L2 trigger pulse. R-side corner → R2 trigger pulse.
        """
        cfg = mapping.left_stick_corners if side == "L" else mapping.right_stick_corners
        if not cfg.corner_haptic_feedback:
            return

        # Use the existing haptic infrastructure: write the feedback effect
        # for ~_HAPTIC_PULSE_MS then revert via a timer
        binding = HapticInputBinding(
            trigger="L2" if side == "L" else "R2",
            source="note",
            midi_id=0,
            effect="feedback",
            intensity_scale=1.0,
        )
        self._fire_haptic(binding, intensity=1.0)

    def _send_touch_cc(self, midi, cc, cc_num: int, normalized: float,
                       cfg: Optional["Mapping.TouchpadConfig"] = None,
                       axis: str = "x") -> None:
        """Send a shaped touchpad CC value.

        If cfg is provided, applies curve + deadzone shaping via
        shaping.apply_touchpad_axis. The axis param ("x" or "y") selects
        which curve/amount to apply. For relative mode, we track and update
        the per-axis state.
        """
        from .mapping import TouchpadConfig
        if cfg is None:
            cfg = TouchpadConfig()

        # Apply shaping if provided
        if cfg is not None:
            curve = cfg.x_curve if axis == "x" else cfg.y_curve
            curve_amt = cfg.x_curve_amount if axis == "x" else cfg.y_curve_amount
            prev = self._prev_touch_value.get(f"{axis}_{cc_num}", 0.5)
            shaped = shaping.apply_touchpad_axis(
                normalized,
                mode=cfg.mode,
                inner_deadzone=cfg.inner_deadzone,
                curve=curve,
                curve_amount=curve_amt,
                prev_value=prev,
            )
            # For relative mode, store the new value for next tick
            if cfg.mode == "relative":
                self._prev_touch_value[f"{axis}_{cc_num}"] = shaped
            normalized = shaped

        val = max(0, min(127, int(round(normalized * 127))))
        key = f"touch_{cc_num}"
        if self._prev_touch_cc.get(key) != val:
            midi.port.send_message([cc, cc_num, val])
            self.midi_sent.emit()
            self._prev_touch_cc[key] = val

    def _send_zone_note(self, midi, cc, channel: int, cfg, x_norm: float,
                        y_norm: float) -> None:
        """Handle zone mode: divide touchpad into NxN grid and fire notes.

        Each zone corresponds to a MIDI note. When the finger moves into a new
        zone, we fire note-off for the old zone and note-on for the new zone.
        Hysteresis prevents edge chatter: only switch zones when crossing
        boundaries by more than 0.05 (5% of pad travel).
        """
        from .mapping import TouchpadConfig
        if cfg is None:
            cfg = TouchpadConfig()

        grid = cfg.zone_grid
        # Compute zone index: zx and zy clamp to [0, grid-1]
        zx = int(x_norm * grid)
        zy = int(y_norm * grid)
        zx = max(0, min(grid - 1, zx))
        zy = max(0, min(grid - 1, zy))
        zone_idx = zy * grid + zx

        # Hysteresis: apply 0.05 bias when exiting a zone to prevent chatter
        bias = self._touchpad_zone_bias.get(self._prev_touchpad_zone, 0.0)
        if self._prev_touchpad_zone is not None and zone_idx != self._prev_touchpad_zone:
            # Only switch zones if we've moved far enough (> 0.05 past boundary)
            # Recalculate with applied bias
            zx_biased = int((x_norm - bias) * grid)
            zy_biased = int((y_norm - bias) * grid)
            zx_biased = max(0, min(grid - 1, zx_biased))
            zy_biased = max(0, min(grid - 1, zy_biased))
            zone_idx_biased = zy_biased * grid + zx_biased
            if zone_idx_biased == self._prev_touchpad_zone:
                # Still in the old zone with hysteresis — don't switch yet
                return
            # Zone change confirmed — set new bias for exiting
            self._touchpad_zone_bias[zone_idx] = 0.05

        # Fire zone change: note-off for old, note-on for new
        if zone_idx != self._prev_touchpad_zone:
            channel_byte = channel & 0x0F
            note_off = 0x80 | channel_byte
            note_on = 0x90 | channel_byte

            # Send note-off for previous zone
            if self._prev_touchpad_zone is not None:
                old_note = (cfg.zone_notes[self._prev_touchpad_zone]
                            if self._prev_touchpad_zone < len(cfg.zone_notes)
                            else (cfg.zone_notes[-1] if cfg.zone_notes else 36))
                try:
                    midi.port.send_message([note_off, old_note, 0])
                except Exception:
                    pass

            # Send note-on for new zone
            new_note = (cfg.zone_notes[zone_idx]
                        if zone_idx < len(cfg.zone_notes)
                        else (cfg.zone_notes[-1] if cfg.zone_notes else 36))
            try:
                midi.port.send_message([note_on, new_note, cfg.zone_velocity])
            except Exception:
                pass

            self.midi_sent.emit()
            self._prev_touchpad_zone = zone_idx

    # ---------------------------------------------------------- MIDI clock

    # ---------------------------------------------------------- beat-grid quantization

    @staticmethod
    def _grid_duration_ms(bpm: float, grid: str) -> float:
        """Return the duration of one grid cell in milliseconds.

        Supports standard and triplet subdivisions:
          "1/4"   = one quarter-note
          "1/8"   = one eighth-note
          "1/8t"  = one eighth-note triplet (2/3 of a quarter)
          "1/16"  = one sixteenth-note
          "1/16t" = one sixteenth-note triplet (1/3 of a quarter)
          "1/32"  = one thirty-second-note
        """
        beat_ms = 60_000.0 / max(bpm, 1.0)   # ms per quarter-note
        return {
            "1/4":   beat_ms,
            "1/8":   beat_ms / 2.0,
            "1/8t":  beat_ms * 2.0 / 3.0,
            "1/16":  beat_ms / 4.0,
            "1/16t": beat_ms / 6.0,
            "1/32":  beat_ms / 8.0,
        }.get(grid, beat_ms / 4.0)   # unknown → 1/16 fallback

    def _quantize_delay_ms(self, qcfg: "QuantizeConfig") -> float:
        """Compute milliseconds to delay until the next grid boundary.

        Uses `_clock_beat_epoch` (set by the clock thread each quarter-note)
        to determine the current beat phase.  If the clock is not running the
        epoch is 0.0 and we fall back to an immediate send (delay = 0).

        Swing: off-beat grid cells (odd-numbered boundaries within a beat)
        are pushed forward by ``swing_pct``% of the grid duration.
        """
        bpm = self._clock_bpm_live
        beat_epoch = self._clock_beat_epoch
        if beat_epoch == 0.0:
            return 0.0

        grid_ms = self._grid_duration_ms(bpm, qcfg.grid)
        beat_ms = 60_000.0 / max(bpm, 1.0)
        cells_per_beat = max(1, round(beat_ms / grid_ms))

        now_ms = time.perf_counter() * 1000.0
        epoch_ms = beat_epoch * 1000.0
        elapsed_in_beat = (now_ms - epoch_ms) % beat_ms

        # Which cell boundary is next?
        cell_index = int(elapsed_in_beat / grid_ms)
        next_cell = cell_index + 1
        delay = (next_cell * grid_ms) - elapsed_in_beat

        # Wrap around to avoid negative/over-beat delays from float drift
        if delay <= 0 or delay > beat_ms:
            delay = grid_ms

        # Apply swing to off-beat cells (odd indices within the beat).
        if qcfg.swing_pct > 0 and next_cell % 2 == 1:
            delay += grid_ms * (qcfg.swing_pct / 100.0)

        return max(0.0, delay)

    def _schedule_quantized_note(
        self,
        status: int,
        note: int,
        velocity: int,
        delay_ms: float,
    ) -> None:
        """Schedule a note-on via QTimer.singleShot after delay_ms.

        If delay_ms <= 1 we just send immediately to avoid unnecessary timer
        overhead for notes that are already essentially on the grid.
        """
        if delay_ms <= 1.0:
            self._send_quantized(status, note, velocity)
            return
        QTimer.singleShot(
            int(delay_ms),
            lambda s=status, n=note, v=velocity: self._send_quantized(s, n, v),
        )

    def _send_quantized(self, status: int, note: int, velocity: int) -> None:
        """Deliver a quantize-deferred note-on to the MIDI port."""
        midi = self._midi
        if midi is None:
            return
        try:
            midi.port.send_message([status, note, velocity])
            self._rtp_send(status, note, velocity)
            self._record_midi_send(status, note, velocity)
            self.midi_sent.emit()
            self._emit_midi_message(
                "sent", status, note, velocity,
                f"NOTE-ON #{note} (quantized)",
            )
        except Exception:
            pass

    def _sync_midi_clock(self) -> None:
        """Start or stop the clock thread to match the current mapping config."""
        clk = self._state.mapping.midi_clock
        if clk.enabled and self._midi is not None:
            self._start_midi_clock(clk.bpm)
        else:
            self._stop_midi_clock()

    def _start_midi_clock(self, bpm: float) -> None:
        """Spin up a daemon thread that emits 0xF8 at 24 PPQN for bpm."""
        bpm = max(60.0, min(240.0, float(bpm)))
        if self._clock_running and self._clock_thread is not None:
            if getattr(self._clock_thread, "_clock_bpm", None) == bpm:
                return
            self._stop_midi_clock()
        self._clock_running = True
        t = threading.Thread(target=self._run_midi_clock_loop, args=(bpm,),
                             daemon=True, name="midi-clock")
        t._clock_bpm = bpm  # type: ignore[attr-defined]
        self._clock_thread = t
        t.start()

    def _stop_midi_clock(self) -> None:
        """Signal the clock thread to stop and wait for it to exit."""
        if not self._clock_running:
            return
        self._clock_running = False
        t = self._clock_thread
        if t is not None and t.is_alive():
            t.join(timeout=0.5)
        self._clock_thread = None

    def _run_midi_clock_loop(self, bpm: float) -> None:
        """Clock thread body: sends 0xF8 at 24 PPQN for bpm with drift correction."""
        interval = 60.0 / (bpm * 24.0)
        next_tick = time.perf_counter()
        self._clock_bpm_live = bpm
        tick_count = 0
        while self._clock_running:
            # Record beat epoch every 24 ticks (one quarter-note).
            if tick_count % 24 == 0:
                self._clock_beat_epoch = time.perf_counter()
            midi = self._midi
            if midi is not None:
                try:
                    midi.port.send_message([0xF8])
                except Exception:
                    pass
            tick_count += 1
            next_tick += interval
            now = time.perf_counter()
            remaining = next_tick - now
            if remaining > 0:
                time.sleep(remaining)

    def _poll_clock_buttons(self, reader, midi, clk,
                            n_buttons: int) -> None:
        """Check tap, start, and stop buttons on each poll tick (press-edge only)."""
        # Tap-tempo
        if 0 <= clk.tap_button < n_buttons:
            tap_btn = clk.tap_button
            pressed = bool(reader.get_button(tap_btn))
            was = self._prev_buttons.get(tap_btn, False)
            if pressed and not was:
                self._record_tap(clk)
            self._prev_buttons[tap_btn] = pressed

        # Start button
        if clk.send_start_stop and 0 <= clk.start_button < n_buttons:
            start_btn = clk.start_button
            pressed = bool(reader.get_button(start_btn))
            was = self._prev_buttons.get(start_btn, False)
            if pressed and not was:
                if midi is not None:
                    try:
                        midi.port.send_message([0xFA])
                    except Exception:
                        pass
                self._start_midi_clock(clk.bpm)
            self._prev_buttons[start_btn] = pressed

        # Stop button
        if clk.send_start_stop and 0 <= clk.stop_button < n_buttons:
            stop_btn = clk.stop_button
            pressed = bool(reader.get_button(stop_btn))
            was = self._prev_buttons.get(stop_btn, False)
            if pressed and not was:
                self._stop_midi_clock()
                if midi is not None:
                    try:
                        midi.port.send_message([0xFC])
                    except Exception:
                        pass
            self._prev_buttons[stop_btn] = pressed

    def _record_tap(self, clk) -> None:
        """Record a tap and recompute BPM from the last 4 taps.

        Formula: BPM = 60 / mean(inter-tap intervals). Clamped 60..240.
        Restarts the clock immediately at the new tempo.
        """
        now = time.perf_counter()
        self._tap_times.append(now)
        if len(self._tap_times) > 4:
            self._tap_times = self._tap_times[-4:]
        if len(self._tap_times) < 2:
            return
        diffs = [
            self._tap_times[i] - self._tap_times[i - 1]
            for i in range(1, len(self._tap_times))
        ]
        avg_diff = sum(diffs) / len(diffs)
        if avg_diff <= 0:
            return
        new_bpm = max(60.0, min(240.0, 60.0 / avg_diff))
        clk.bpm = new_bpm
        self._start_midi_clock(new_bpm)

    # ---------------------------------------------------------- shutdown

    def _silence_all(self, midi: OpenedPort, mapping: Mapping, channel: int) -> None:
        note_off = 0x80 | channel
        for btn_idx, note in mapping.buttons.items():
            if self._prev_buttons.get(btn_idx):
                try:
                    midi.port.send_message([note_off, note, 0])
                except Exception:
                    pass
        for direction, note in mapping.hats.items():
            if self._prev_hat.get(direction):
                try:
                    midi.port.send_message([note_off, note, 0])
                except Exception:
                    pass
        for side in ("L", "R"):
            held = self._prev_corner_notes.get(side)
            if held is not None:
                try:
                    midi.port.send_message([note_off, held, 0])
                except Exception:
                    pass

    def _cleanup(self) -> None:
        # Stop MIDI clock thread before anything else so it doesn't write to
        # a port we're about to close.
        self._stop_midi_clock()
        # Close the input port FIRST so no more callback writes land while
        # we're tearing the HID handle down. cancel_callback inside
        # close_input_port blocks until any in-flight callback returns.
        if self._midi_in is not None:
            close_input_port(self._midi_in)
            self._midi_in = None
        # Close the passthrough input port so its callback thread is also done.
        if self._passthrough_input is not None:
            close_input_port(self._passthrough_input)
            self._passthrough_input = None
        for t in self._haptic_revert_timers:
            try:
                t.cancel()
            except Exception:
                pass
        self._haptic_revert_timers.clear()

        close_port(self._midi)
        self._midi = None
        if self._osc is not None:
            self._osc.close()
            self._osc = None
        if self._osc_receiver is not None:
            self._osc_receiver.stop()
            self._osc_receiver = None
        self._prev_osc_axes.clear()
        if self._rtp_sender is not None:
            self._rtp_sender.stop()
            self._rtp_sender = None
        # Reset triggers to neutral before we hand the controller back to the
        # OS — otherwise the last-applied effect lingers until something else
        # talks to the controller.
        if self._mac_haptic_handle is not None:
            try:
                self._mac_haptic_handle.set_trigger_effect("L", "off")
                self._mac_haptic_handle.set_trigger_effect("R", "off")
                self._mac_haptic_handle.close()
            except Exception:
                pass
            self._mac_haptic_handle = None
        if self._ds_handle is not None:
            if self._ds_handle.wired:
                try:
                    ds.write_trigger_effects(self._ds_handle, "off", "off")
                except Exception:
                    pass
            self._ds_handle.close()
            self._ds_handle = None
        self._last_haptic_pair = (None, None)
        if self._reader is not None:
            self._reader.close()
            self._reader = None
        self._prev_buttons.clear()
        self._prev_cc.clear()
        self._prev_touch_cc.clear()
        self._prev_corner_notes = {"L": None, "R": None}
        self._prev_battery = None
        for k in self._prev_hat:
            self._prev_hat[k] = False

    def _detect_swipe(self, midi, channel: int, cfg, start_xy, end_xy) -> None:
        """Detect swipe gesture (up/down/left/right) and fire MIDI note.

        Compares end vs start position. If |dx| > swipe_min_distance and
        |dx| > |dy|, fire left/right. If |dy| > swipe_min_distance and
        |dy| > |dx|, fire up/down.
        """
        start_x, start_y = start_xy
        end_x, end_y = end_xy
        
        dx = end_x - start_x
        dy = end_y - start_y
        
        # Check which direction has the largest displacement
        abs_dx = abs(dx)
        abs_dy = abs(dy)
        
        # Require minimum distance to register
        if abs_dx < cfg.swipe_min_distance and abs_dy < cfg.swipe_min_distance:
            return
        
        channel_byte = channel & 0x0F
        note_on = 0x90 | channel_byte
        note = 0
        
        # Determine primary swipe direction (whichever exceeds min_distance most)
        if abs_dx > abs_dy and abs_dx >= cfg.swipe_min_distance:
            # Horizontal swipe
            note = cfg.swipe_right_note if dx > 0 else cfg.swipe_left_note
        elif abs_dy >= cfg.swipe_min_distance:
            # Vertical swipe (note: Y increases downward, so negative dy = up)
            note = cfg.swipe_up_note if dy < 0 else cfg.swipe_down_note
        else:
            return
        
        try:
            midi.port.send_message([note_on, note, cfg.gesture_velocity])
            self.midi_sent.emit()
        except Exception:
            pass

    def _detect_pinch(self, midi, channel: int, cfg, current_dist: float,
                      start_dist: float) -> None:
        """Detect pinch gesture (in/out) and fire MIDI note.

        current_dist < start_dist * 0.7 -> pinch_in
        current_dist > start_dist * 1.4 -> pinch_out
        """
        if start_dist is None or start_dist == 0:
            return
        
        ratio = current_dist / start_dist
        channel_byte = channel & 0x0F
        note_on = 0x90 | channel_byte
        
        if ratio < 0.7:
            # Pinch inward
            note = cfg.pinch_in_note
        elif ratio > 1.4:
            # Pinch outward
            note = cfg.pinch_out_note
        else:
            return  # Not far enough to register as pinch
        
        try:
            midi.port.send_message([note_on, note, cfg.gesture_velocity])
            self.midi_sent.emit()
        except Exception:
            pass


    # ---------------------------------------------------------- telemetry

    def _emit_axis(self, idx: int, value: float) -> None:
        now = time.perf_counter()
        if now - self._last_telemetry >= self._telemetry_interval:
            self.axis_value.emit(idx, value)
            self._last_telemetry = now


class BridgeController(QObject):
    """Thin GUI-side wrapper that owns the worker and its thread."""

    def __init__(self, parent: Optional[QObject] = None,
                 slot_index: int = 0,
                 midi_port_name: Optional[str] = None,
                 demo: bool = False,
                 keyboard: bool = False,
                 mouse: bool = False) -> None:
        super().__init__(parent)
        self.slot_index = max(0, int(slot_index))
        self.worker = BridgeWorker(
            slot_index=self.slot_index,
            midi_port_name=midi_port_name,
            demo=demo,
            keyboard=keyboard,
            mouse=mouse,
        )
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start)
        self.worker.stopped.connect(self.thread.quit)

    def start(self) -> None:
        if not self.thread.isRunning():
            self.thread.start()

    def stop(self) -> None:
        self.worker.stop()

    def recalibrate(self) -> None:
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self.worker, "recalibrate", Qt.QueuedConnection)

    def shutdown(self) -> None:
        self.worker.stop()
        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(2000)
