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
from .corner_quantizer import CornerDetector, decode_switch
from .mapping import HapticInputBinding, L2_AXIS, Mapping, R2_AXIS, STICK_AXES
from . import shaping
from .midi_backend import DEFAULT_PORT_NAME, MidiPortError, OpenedPort, close_port, open_port
from . import presets as _presets
from .midi_input import (
    INPUT_PORT_NAME, MidiInputError, OpenedInputPort,
    close_input_port, open_input_port, set_callback as set_input_callback,
)
from .osc_backend import OscSender


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

    # --- V1.1c haptic-input: emitted whenever an incoming MIDI message
    # fired a trigger effect. (side="L"/"R", effect name, intensity 0..1).
    haptic_event = Signal(str, str, float)

    def __init__(self, slot_index: int = 0,
                 midi_port_name: Optional[str] = None,
                 demo: bool = False) -> None:
        """Multi-controller plumbing — slot_index picks which pygame joystick
        this worker binds to, and midi_port_name overrides the virtual port so
        two workers don't fight over a single "Universal Controller MIDI" port name.
        `demo` swaps the pygame reader for a synthetic one so the bridge can
        be exercised end-to-end without hardware (recording demo videos, CI).
        Both default to the V1.1 single-controller behaviour.
        """
        super().__init__()
        self._slot_index = max(0, int(slot_index))
        self._midi_port_name = midi_port_name or DEFAULT_PORT_NAME
        self._demo = bool(demo)
        self._state = BridgeState()
        self._reader: Optional[ControllerReader] = None
        self._midi: Optional[OpenedPort] = None
        self._ds_handle: Optional[ds.DualSenseHandle] = None
        self._mac_haptic_handle = None     # set on darwin if mac_haptics opens
        self._osc: Optional[OscSender] = None
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
        self._prev_hat = {"up": False, "down": False, "left": False, "right": False}
        self._prev_corner_notes: Dict[str, Optional[int]] = {"L": None, "R": None}
        self._prev_touch_cc: Dict[str, int] = {}
        self._prev_touch_value: Dict[str, float] = {}  # tracks relative-mode state per axis
        self._touch_armed: bool = False  # for click_to_arm mode
        self._prev_battery: Optional[tuple] = None
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

    # ---------------------------------------------------------------- public API

    def set_mapping(self, mapping: Mapping) -> None:
        self._state.mapping = mapping
        self._cache_b_mapping(mapping)
        self._sync_corner_detectors()
        self._apply_haptics()
        self._sync_osc_sender()
        self._sync_haptic_input()

    @Slot()
    def start(self) -> None:
        """Entry point — invoked once when the worker's thread starts."""
        self._reader = (SyntheticControllerReader(slot_index=self._slot_index)
                        if self._demo
                        else ControllerReader(slot_index=self._slot_index))
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
            return
        # Reopen on host/port change so we don't keep stale state.
        if self._osc is None or self._osc.host != cfg.host or self._osc.port != cfg.port:
            if self._osc is not None:
                self._osc.close()
            self._osc = OscSender(host=cfg.host, port=cfg.port)
        self._prev_osc_axes.clear()

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
        """Open / close the virtual MIDI input port based on mapping.haptic_input.

        Re-entrant: called on start() AND every set_mapping() so the user can
        toggle the feature live from the Settings panel. If the port can't
        open (no loopMIDI on Windows, broken CoreMIDI, etc.) we surface it
        through `status` so the GUI shows the failure without crashing.
        """
        cfg = self._state.mapping.haptic_input
        if not cfg.enabled:
            if self._midi_in is not None:
                close_input_port(self._midi_in)
                self._midi_in = None
            return
        if self._midi_in is not None:
            # Already open — just keep using it. Bindings live on `self._state`
            # so changes propagate without re-opening the port.
            return
        try:
            self._midi_in = open_input_port(INPUT_PORT_NAME)
            set_input_callback(self._midi_in, self._on_midi_in)
            self.status.emit(
                f"Haptic-in listening on '{self._midi_in.name}'"
            )
        except MidiInputError as e:
            self.status.emit(f"Haptic-in unavailable: {e}")
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
        cfg = self._state.mapping.haptic_input
        if not cfg.enabled or not cfg.bindings:
            return
        try:
            status_byte = message[0]
        except IndexError:
            return
        msg_type = status_byte & 0xF0
        channel = status_byte & 0x0F
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
        # NOTE_OFF, polyphonic aftertouch, program change, etc. are no-ops —
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

    def _fire_haptic(self, binding: HapticInputBinding, intensity: float) -> None:
        """Write the trigger effect and schedule a revert to the static config."""
        side = "L" if binding.trigger.upper() == "L2" else "R"
        # Build the (l2, r2) tuple — only touch the bound side, leave the
        # other at its static config so the user's existing L2/R2 'feel'
        # selection survives the pulse on the opposite trigger.
        m = self._state.mapping
        if side == "L":
            new_pair = (binding.effect, m.r2_haptic_effect)
        else:
            new_pair = (m.l2_haptic_effect, binding.effect)
        with self._haptic_lock:
            self._write_trigger_pair(*new_pair)
            self._last_haptic_pair = new_pair
        self.haptic_event.emit(side, binding.effect, intensity)

        # Schedule a revert so the trigger relaxes back to the user's static
        # 'feel'. Each binding gets its own timer; if a flurry of notes lands
        # on the same trigger we just keep refreshing the latest revert.
        t = threading.Timer(_HAPTIC_PULSE_MS / 1000.0, self._revert_to_static)
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

    def _poll_buttons(self, reader, mapping, midi, note_on, note_off, n_buttons) -> None:
        buttons, _axes, _hats = self._active_mappings_view(mapping)
        osc_only = self._osc_only()
        for btn_idx, note in buttons.items():
            if btn_idx >= n_buttons:
                continue
            pressed = reader.get_button(btn_idx)
            was = self._prev_buttons.get(btn_idx, False)
            if pressed and not was:
                if not osc_only:
                    midi.port.send_message([note_on, note, 127])
                    self.midi_sent.emit()
                self._send_osc_button(btn_idx, True)
            elif not pressed and was:
                if not osc_only:
                    midi.port.send_message([note_off, note, 0])
                    self.midi_sent.emit()
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
                    midi.port.send_message([cc, cc_num, val])
                    self._record_outbound_cc(mapping.midi_channel, cc_num, val)
                    self.midi_sent.emit()
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
            if now and not was:
                midi.port.send_message([note_on, note, 127])
                self.midi_sent.emit()
            elif not now and was:
                midi.port.send_message([note_off, note, 0])
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
                 demo: bool = False) -> None:
        super().__init__(parent)
        self.slot_index = max(0, int(slot_index))
        self.worker = BridgeWorker(
            slot_index=self.slot_index,
            midi_port_name=midi_port_name,
            demo=demo,
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
