"""Bridge engine — runs the controller-poll/MIDI-send loop in its own QThread.

Signals stream controller and status updates back to the GUI without blocking
the main loop. Keep the inner loop hot — anything heavy belongs in slots on
the GUI side.

V1.1: optional parallel DualSense HID handle gives us battery, touchpad, and
edge-quantized stick corners on top of the SDL2-driven pygame input.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from . import dualsense as ds
from .calibration import calibrate
from .controller import ControllerInfo, ControllerReader
from .corner_quantizer import CornerDetector, decode_switch
from .mapping import Mapping, STICK_AXES
from .midi_backend import DEFAULT_PORT_NAME, MidiPortError, OpenedPort, close_port, open_port

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
    calibration_done = Signal(dict, list, list)       # offsets, severe, significant

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

    def __init__(self, slot_index: int = 0,
                 midi_port_name: Optional[str] = None) -> None:
        """Multi-controller plumbing — slot_index picks which pygame joystick
        this worker binds to, and midi_port_name overrides the virtual port so
        two workers don't fight over a single "Gamepad MIDI Bridge" port name.
        Both default to the V1.1 single-controller behaviour.
        """
        super().__init__()
        self._slot_index = max(0, int(slot_index))
        self._midi_port_name = midi_port_name or DEFAULT_PORT_NAME
        self._state = BridgeState()
        self._reader: Optional[ControllerReader] = None
        self._midi: Optional[OpenedPort] = None
        self._ds_handle: Optional[ds.DualSenseHandle] = None
        self._mac_haptic_handle = None     # set on darwin if mac_haptics opens
        self._left_corner: Optional[CornerDetector] = None
        self._right_corner: Optional[CornerDetector] = None
        self._last_haptic_pair: tuple = (None, None)   # (l2, r2) last applied
        self._running = False
        self._prev_buttons: Dict[int, bool] = {}
        self._prev_cc: Dict[int, int] = {}
        self._prev_hat = {"up": False, "down": False, "left": False, "right": False}
        self._prev_corner_notes: Dict[str, Optional[int]] = {"L": None, "R": None}
        self._prev_touch_cc: Dict[str, int] = {}
        self._prev_battery: Optional[tuple] = None
        # Telemetry throttle — emit GUI updates at ~30Hz max even at 100Hz polling
        self._last_telemetry: float = 0.0
        self._telemetry_interval = 1.0 / 30.0
        # Battery + touchpad poll less often — they don't need 100Hz
        self._last_battery_poll: float = 0.0
        self._battery_interval = 5.0

    # ---------------------------------------------------------------- public API

    def set_mapping(self, mapping: Mapping) -> None:
        self._state.mapping = mapping
        self._sync_corner_detectors()
        self._apply_haptics()

    @Slot()
    def start(self) -> None:
        """Entry point — invoked once when the worker's thread starts."""
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

    def _sync_corner_detectors(self) -> None:
        m = self._state.mapping
        self._left_corner = self._build_detector(m.left_stick_corners)
        self._right_corner = self._build_detector(m.right_stick_corners)
        # Reset prev-note tracking when config changes so we don't leak hangs.
        self._prev_corner_notes = {"L": None, "R": None}

    def _apply_haptics(self) -> None:
        """Push current trigger-effect config to the controller.

        Idempotent — if nothing's changed since last apply, no-op. Safe to
        call before a handle exists (it just defers until one does).
        """
        m = self._state.mapping
        pair = (m.l2_haptic_effect, m.r2_haptic_effect)
        if pair == self._last_haptic_pair:
            return

        applied = False
        # macOS goes through GCController; everything else uses hidapi.
        if self._mac_haptic_handle is not None:
            try:
                self._mac_haptic_handle.set_trigger_effect("L", m.l2_haptic_effect or "off")
                self._mac_haptic_handle.set_trigger_effect("R", m.r2_haptic_effect or "off")
                applied = True
            except Exception as e:
                self.status.emit(f"Haptic apply failed: {e}")
        elif self._ds_handle is not None and self._ds_handle.wired:
            # BT haptics needs a CRC32 tail — V2. Wired only for V1.1b.
            applied = ds.write_trigger_effects(
                self._ds_handle, m.l2_haptic_effect, m.r2_haptic_effect,
            )

        if applied:
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

        mapping = self._state.mapping
        offsets = self._state.stick_offsets
        deadzone = mapping.deadzone
        channel = mapping.midi_channel & 0x0F
        note_on = 0x90 | channel
        note_off = 0x80 | channel
        cc = 0xB0 | channel

        interval = 1.0 / max(mapping.poll_hz, 1)
        n_buttons = reader.num_buttons()
        n_axes = reader.num_axes()
        n_hats = reader.num_hats()

        try:
            while self._running:
                t0 = time.perf_counter()
                reader.pump()

                self._poll_buttons(reader, mapping, midi, note_on, note_off, n_buttons)
                self._poll_axes(reader, mapping, offsets, deadzone, midi, cc, n_axes)
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

    def _poll_buttons(self, reader, mapping, midi, note_on, note_off, n_buttons) -> None:
        for btn_idx, note in mapping.buttons.items():
            if btn_idx >= n_buttons:
                continue
            pressed = reader.get_button(btn_idx)
            was = self._prev_buttons.get(btn_idx, False)
            if pressed and not was:
                midi.port.send_message([note_on, note, 127])
                self.midi_sent.emit()
            elif not pressed and was:
                midi.port.send_message([note_off, note, 0])
                self.midi_sent.emit()
            if pressed != was:
                self._prev_buttons[btn_idx] = pressed
                self.button_state.emit(btn_idx, pressed)

    def _poll_axes(self, reader, mapping, offsets, deadzone, midi, cc, n_axes) -> None:
        for axis_idx, cc_num in mapping.axes.items():
            if axis_idx >= n_axes:
                continue
            raw = reader.get_axis(axis_idx)
            if axis_idx in STICK_AXES:
                raw = max(-1.0, min(1.0, raw - offsets.get(axis_idx, 0.0)))
                if abs(raw) < deadzone:
                    raw = 0.0
            val = int(round((raw + 1.0) * 63.5))
            val = max(0, min(127, val))
            if self._prev_cc.get(axis_idx) != val:
                midi.port.send_message([cc, cc_num, val])
                self.midi_sent.emit()
                self._prev_cc[axis_idx] = val
                self._emit_axis(axis_idx, raw)

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
        hat_x, hat_y = reader.get_hat(0)
        current = {
            "up":    hat_y ==  1,
            "down":  hat_y == -1,
            "left":  hat_x == -1,
            "right": hat_x ==  1,
        }
        for direction, note in mapping.hats.items():
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

        # Touchpad — only first touch contact in V1.1 (two-finger gestures = V2)
        if mapping.touchpad.enabled:
            t = state.touch_a
            if t.active or not mapping.touchpad.require_contact:
                x_norm, y_norm = t.normalized()
                self.touchpad_xy.emit(t.active, x_norm, y_norm)
                self._send_touch_cc(midi, cc, mapping.touchpad.x_cc, x_norm)
                self._send_touch_cc(midi, cc, mapping.touchpad.y_cc, y_norm)
            elif self._prev_touch_cc:
                # Finger lifted — reset the GUI but keep the last MIDI value
                # (Kaoss Pad behaviour: release leaves the modulator where it was).
                self.touchpad_xy.emit(False, 0.0, 0.0)

    def _send_touch_cc(self, midi, cc, cc_num: int, normalized: float) -> None:
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
        close_port(self._midi)
        self._midi = None
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
                 midi_port_name: Optional[str] = None) -> None:
        super().__init__(parent)
        self.slot_index = max(0, int(slot_index))
        self.worker = BridgeWorker(
            slot_index=self.slot_index,
            midi_port_name=midi_port_name,
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
