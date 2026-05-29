"""Bridge engine — runs the controller-poll/MIDI-send loop in its own QThread.

Signals stream controller and status updates back to the GUI without blocking
the main loop. Keep the inner loop hot — anything heavy belongs in slots on
the GUI side.

V1.1: optional parallel DualSense HID handle gives us battery, touchpad, and
edge-quantized stick corners on top of the SDL2-driven pygame input.
"""
from __future__ import annotations

import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QMetaObject, QObject, QThread, Q_ARG, Qt, Signal, Slot,
)

from . import dualsense as ds
from .calibration import calibrate
from .controller import ControllerInfo, ControllerReader
from .demo_controller import SyntheticControllerReader
from .keyboard_controller import KeyboardControllerReader
from .corner_quantizer import CornerDetector, decode_switch
from .mapping import HapticInputBinding, L2_AXIS, Macro, MacroEvent, Mapping, MidiClockConfig, R2_AXIS, STICK_AXES
from . import shaping
from .midi_backend import DEFAULT_PORT_NAME, MidiPortError, OpenedPort, close_port, open_port
from . import presets as _presets
from .midi_input import (
    INPUT_PORT_NAME, MidiInputError, OpenedInputPort,
    close_input_port, open_input_port, set_callback as set_input_callback,
)
from .osc_backend import OscReceiver, OscSender


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
                 keyboard: bool = False) -> None:
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
        self._prev_hat = {"up": False, "down": False, "left": False, "right": False}
        self._prev_corner_notes: Dict[str, Optional[int]] = {"L": None, "R": None}
        self._prev_touch_cc: Dict[str, int] = {}
        self._prev_touch_value: Dict[str, float] = {}  # tracks relative-mode state per axis
        self._touch_armed: bool = False  # for click_to_arm mode
        self._prev_touchpad_zone: Optional[int] = None  # zone index for hysteresis
        self._touchpad_zone_bias: Dict[int, float] = {}  # hysteresis bias per zone
        self._prev_battery: Optional[tuple] = None
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
        # Feedback-loop guard: track recent outbound CC messages to detect echoes
        # Deque of (channel, cc_number, value, timestamp) tuples, max 50 entries
        self._recent_outbound_cc: deque = deque(maxlen=50)
        self._feedback_guard_window_ms = 50  # Drop messages within 50ms of send
        # Macro recorder state — capture MIDI sends with relative timestamps.
        self._recording: bool = False
        self._recording_start_ms: float = 0.0
        self._recording_events: List[MacroEvent] = []
        # Setlist mode — current position in the ordered preset list.
        self._setlist_index: int = 0

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
        self._sync_midi_clock()

    @Slot()
    def start(self) -> None:
        """Entry point — invoked once when the worker's thread starts."""
        if self._keyboard:
            self._reader = KeyboardControllerReader(slot_index=self._slot_index)
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

        self._maybe_open_dualsense(info)
        self._sync_corner_detectors()
        self._apply_haptics()
        self._sync_osc_sender()
        self._sync_haptic_input()

        # Auto-calibrate on first start. UI may also trigger recalibration.
        self._run_calibration()

        self.started.emit(info.name, self._midi.name)
        self.status.emit(f"Bridging {info.name} → {self._midi.name}")
        self._running = True
        self._loop()

    @Slot()
    def stop(self) -> None:
        self._running = False

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
        """
        if not self._recording:
            return
        delay_ms = int((time.time() * 1000.0) - self._recording_start_ms)
        self._recording_events.append(MacroEvent(
            delay_ms=max(0, delay_ms),
            status=status,
            data1=data1,
            data2=data2,
        ))

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

    def _poll_buttons(self, reader, mapping, midi, note_on, note_off, n_buttons) -> None:
        # --- MIDI clock button handling (tap-tempo, start, stop) ---
        clk = mapping.midi_clock
        if clk.enabled:
            self._poll_clock_buttons(reader, midi, clk, n_buttons)

        # --- Setlist step-through ---
        self._poll_setlist_buttons(reader, mapping, n_buttons)

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
                        self.midi_sent.emit()
                        self._emit_midi_message("sent", btn_note_on, note, btn_cfg.gate_release_value, f"NOTE-ON #{note}")
                    self._send_osc_button(btn_idx, False)
                    self._prev_buttons[btn_idx] = False
                    self.button_state.emit(btn_idx, False)
                    continue

            if pressed and not was:
                # Macro playback: if this button is bound to a macro, play it
                # instead of (or in addition to) the normal note. Each playback
                # gets its own QTimer chain so simultaneous macros work fine.
                macro_name = mapping.macro_bindings.get(btn_idx)
                if macro_name:
                    macro = next((m for m in mapping.macros if m.name == macro_name), None)
                    if macro:
                        self._play_macro(macro, midi)
                if not osc_only:
                    midi.port.send_message([btn_note_on, note, 127])
                    self._record_midi_send(btn_note_on, note, 127)
                    self.midi_sent.emit()
                    self._emit_midi_message("sent", btn_note_on, note, 127, f"NOTE-ON #{note}")
                self._send_osc_button(btn_idx, True)
            elif not pressed and was:
                if not osc_only:
                    midi.port.send_message([btn_note_off, note, 0])
                    self._record_midi_send(btn_note_off, note, 0)
                    self.midi_sent.emit()
                    self._emit_midi_message("sent", btn_note_off, note, 0, f"NOTE-OFF #{note}")
                self._send_osc_button(btn_idx, False)
            if pressed != was:
                self._prev_buttons[btn_idx] = pressed
                self.button_state.emit(btn_idx, pressed)

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
            else:
                # Other axes (HID hats, generic analogs) use the legacy
                # -1..1 → 0..127 remap so unknown controllers keep working.
                val = int(round((raw + 1.0) * 63.5))
                val = max(0, min(127, val))
            if self._prev_cc.get(axis_idx) != val:
                if not osc_only:
                    axis_channel = self._channel_for_axis(mapping, axis_idx)
                    axis_cc = 0xB0 | axis_channel
                    midi.port.send_message([axis_cc, cc_num, val])
                    self._record_outbound_cc(axis_channel, cc_num, val)
                    self._record_midi_send(axis_cc, cc_num, val)
                    self.midi_sent.emit()
                    self._emit_midi_message("sent", axis_cc, cc_num, val, f"CC#{cc_num}")
                # OSC sends a 0..1 float, MIDI a 0..127 int — keep both
                # streams in lock-step but de-dup against last-sent 0..127.
                if self._osc is not None and self._prev_osc_axes.get(axis_idx) != val:
                    self._send_osc_axis(axis_idx, val / 127.0)
                    self._prev_osc_axes[axis_idx] = val
                self._prev_cc[axis_idx] = val
                self._emit_axis(axis_idx, raw)

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
                self.midi_sent.emit()
            elif not now and was:
                midi.port.send_message([hat_note_off, note, 0])
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
        while self._clock_running:
            midi = self._midi
            if midi is not None:
                try:
                    midi.port.send_message([0xF8])
                except Exception:
                    pass
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
                 keyboard: bool = False) -> None:
        super().__init__(parent)
        self.slot_index = max(0, int(slot_index))
        self.worker = BridgeWorker(
            slot_index=self.slot_index,
            midi_port_name=midi_port_name,
            demo=demo,
            keyboard=keyboard,
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
