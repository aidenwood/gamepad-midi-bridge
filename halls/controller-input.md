# Hall: Controller Input

Everything between the physical pad and the bridge's normalised axis/button state — sticks (calibration, drift, gestures, zones, velocity), triggers (calibration, asymmetry, pressure, curves), aftertouch, velocity shaping, IMU + haptics, Bluetooth discovery, and the cross-platform controller mess. Modules in this hall are mostly pure-stdlib analysers; the side-effectful bits live in `dualsense.py`, `mac_haptics.py`, and `controller.py`.

### Stick Calibration & Drift

`calibration.calibrate(reader, duration_sec=1.0, sample_count=60, on_progress=...)` samples the stick axes for the configured duration with the user's hands off and returns per-axis offsets. The bridge then subtracts that offset every read. `stick_calibration.py` and `stick_drift_detector.py` are richer pure-data analysers used by the UI to surface a per-stick health report.

```python
# calibration.py — the canonical bridge-side calibration call
@dataclass
class CalibrationResult:
    offsets: Dict[int, float]
    severe_axes: list       # |offset| > 0.30 — recommend repair
    significant_axes: list  # |offset| > 0.05

def calibrate(reader, duration_sec=1.0, sample_count=60, on_progress=None) -> CalibrationResult: ...
```

- Thresholds live in `calibration.py`: `SEVERE_DRIFT_THRESHOLD = 0.30`, `SIGNIFICANT_THRESHOLD = 0.05`. Don't drift them silently — UI copy quotes these numbers.
- Only axes in `mapping.STICK_AXES` (`frozenset({0, 1, 2, 3})`) get calibrated. L2/R2 (axes 4, 5) are triggers and have their own normalisation.
- `BridgeWorker._run_calibration()` runs on the worker thread; progress is emitted via `calibration_progress` (0.0..1.0) so the GUI can drive a progress bar without coupling.
- `stick_calibration.StickCalibrationResult` exposes `center_x`, `center_y`, `deadzone_radius`, `sample_count`, `stable` for the visual calibration tab — separate from the bridge's per-axis offset model.
- `stick_drift_detector.DriftReport` adds severity buckets (`none`/`minor`/`moderate`/`severe`) for the "is your controller dying?" widget.

### Stick Gesture & Zones

`stick_gesture.py` and `stick_zones.py` are pure stateful analysers — feed them stick samples, ask what the user did.

```python
# stick_gesture.py
Gesture = str  # "swipe_up", "swipe_down", "swipe_left", "swipe_right",
              # "circle_cw", "circle_ccw"

@dataclass
class StickGestureConfig:
    enabled: bool
    swipe_min_magnitude: float   # 0.1..2.0
    # ...angle accumulation thresholds for circle detection
```

- Swipes fire once on a magnitude-and-direction edge. Circles need accumulated angle change — reset state when the user releases the stick (deadzone re-enter).
- `stick_zones.ZONE_4` / `ZONE_8` / `ZONE_9` are the named-zone tables. Each zone maps to a MIDI note via `StickZoneConfig.zone_notes`. Hysteresis at the zone boundary is the caller's job (see `BridgeWorker._prev_touchpad_zone` for the precedent — same pattern applies).
- `corner_quantizer.CornerDetector(n, r_enter, r_exit)` is the bridge-integrated alternative — turns a stick into 4/8/16 buttons with explicit hysteresis. `BridgeWorker._build_detector(cfg)` is the canonical construction site; it returns `None` when `cfg.enabled is False`.

### Stick Velocity & Analytics

Stick velocity tracking is purely analytical — no MIDI side effects, no Qt. `stick_velocity.py` exposes `StickVelocityConfig` + a `feed(x, y, t)` API that returns `(vx, vy, speed, accel)` in axis_units/sec.

```python
# stick_velocity.py — config shape (state lives in the tracker class)
@dataclass
class StickVelocityConfig:
    enabled: bool
    smoothing: float  # one-pole alpha 0..0.99
    # ...history window size, etc.
```

- Velocity feeds the `StickFlickConfig` MIDI feature in `mapping.py` (velocity-sensitive note-on when speed crosses `speed_threshold` and magnitude passes 0.7 on rising edge).
- `stick_deadzone_analyzer.py`, `stick_deflection_rose.py`, `stick_onset.py`, `stick_freeze.py` are also pure-stdlib — don't import Qt into any of them.
- Bridge-side state for stick flick lives in `BridgeWorker._flick_state: Dict[int, tuple]` keyed by axis index → `(prev_shaped_val, prev_timestamp)`. Same shape for `_bow_state`, `_stick_chord_state`, `_stick_chord_values`.

### Trigger & Pressure

`mapping.TriggerConfig` is the source of truth for what L2 / R2 do per preset. Pure analysis helpers live in `trigger_calibration.py`, `trigger_pressure_stats.py`, `trigger_asymmetry.py`, `trigger_cadence_detector.py`, `trigger_curve_preview.py`, `trigger_crossfade_preview.py`, `trigger_pull_classifier.py`, `trigger_response_time.py`, `trigger_noise_gate.py`.

```python
# mapping.py — TriggerConfig (per-trigger shaping)
@dataclass
class TriggerConfig:
    mode: str = "linear"          # linear | ceiling | inverted | latch
    ceiling: int = 127
    latch_threshold: float = 0.5
    gate_button: Optional[int] = None       # require this btn held to fire
    gate_release_value: int = 0
    tactile_click: bool = True              # 30ms haptic on latch crossings
    aftertouch: TriggerAftertouchConfig = ...
    bow_mode: bool = False; bow_cc: int = 11
    crossfade_enabled: bool = False; crossfade_cc_b: int = 0
```

- Trigger axis indices are constants: `L2_AXIS = 4`, `R2_AXIS = 5` (`mapping.py`). Use the constants, not literals.
- Per-tick latch state lives in `BridgeWorker._trigger_states[L2_AXIS|R2_AXIS]: shaping.TriggerState`. Stateless trigger modes ignore it.
- Gate-button release edge: `_trigger_gate_was_held` records previous-tick hold so we emit `gate_release_value` exactly once instead of leaving the receiver stuck on the last value.
- `trigger_noise_gate` squelches sub-threshold fluctuations BEFORE shaping; doing it post-shape causes stairstep glitches.

### Aftertouch & Force Sensing

`aftertouch_curve.py` is pure-function curve transforms from normalised 0..1 → MIDI 0..127 with curves `linear`, `soft`, `hard`, `stepped`, `exponential`, `logarithmic` (canonical list: `AFTERTOUCH_CURVE_MODES`). `aftertouch_peak_analyzer.py` and `aftertouch_usage_log.py` are analytical sidecars.

```python
# aftertouch_curve.py — canonical curve modes tuple
AFTERTOUCH_CURVE_MODES = (
    "linear", "soft", "hard", "stepped", "exponential", "logarithmic"
)
DEFAULT_AFTERTOUCH_CURVE_MODE = "linear"
```

- Trigger second-stage aftertouch lives in `TriggerAftertouchConfig(enabled, threshold=0.85, channel_override=-1)`. Above the threshold, channel-pressure (`0xD0`) is emitted proportional to how far past threshold the trigger is pressed.
- `BridgeWorker._at_active[axis]` tracks whether aftertouch is currently engaged for each trigger axis — used for edge detection so we emit one zero-pressure message on release.
- Polyphonic aftertouch (`0xA0`) is rate-limited to 30 Hz in `_poly_at_last_send_ms` to avoid spamming downstream synths. Per-(button, note) last-pressure dedup lives in `_poly_at_last_pressure`.

### Velocity Shaping

`velocity_curve.py` is the pure-function module the UI previews. `VELOCITY_CURVE_MODES = ("linear", "soft", "hard", "fixed", "exponential", "logarithmic", "s_curve")`. `velocity_curve_suggester.py` picks a curve based on the user's pull style or velocity histogram. `velocity_quantizer.py`, `velocity_gate.py`, and `velocity_histogram.py` round out the shaping toolbox.

```python
# velocity_curve.py — canonical modes (used by UI dropdowns + validation)
VELOCITY_CURVE_MODES = (
    "linear", "soft", "hard", "fixed", "exponential", "logarithmic", "s_curve"
)
```

- `velocity_gate.gate(v, threshold, mode)` either drops sub-threshold notes or remaps them. Use `mode="drop"` for percussion, `mode="floor"` for melodic.
- Histogram bucket count is bounded `4..32` (`HistogramConfig.__post_init__`); 8 is the default for the meter widget.
- Never store curve state — curves are deterministic and stateless. State (recent samples, smoothing) lives in shaping classes, not curve modules.

### IMU/Haptics & Shaping

`imu_helper.py` is **pure stdlib + pure functions** — no hardware reads, no OS guards. Caller supplies floats. `mac_haptics.py` is where the actual macOS-specific code lives (PyObjC + Apple's `GameController` framework).

```python
# imu_helper.py — per-axis IMU processor
class ImuAxisProcessor:
    def __init__(self, cfg: ImuAxisConfig) -> None: ...
    def feed(self, raw: float) -> Optional[int]:
        # deadzone → gain → invert → one-pole smoothing → bipolar/unipolar map
        # returns CC 0..127 or None when cfg.enabled=False
```

- `ImuMappingConfig` holds six `ImuAxisConfig`s (`gyro_x/y/z`, `accel_x/y/z`). `ImuMapping.process(gyro, accel)` returns `List[Tuple[cc, channel, value]]` for every enabled axis.
- macOS adaptive triggers go through `mac_haptics.MacHapticsHandle` (GCController). Apple exposes only `off`, `feedback`, `weapon`, `vibration`, and (macOS 12+) `slopeFeedback`. Sony's richer effects (`bow`, `galloping`, `machine`) degrade to `setModeOff()` on mac — that's intentional.
- Windows / Linux haptics go through hidapi (`dualsense.write_trigger_effects`). USB and Bluetooth both supported. BT uses a CRC32-framed report; both paths are inside the same call.
- `haptic_presets.py` is pure data — named haptic effect descriptors (`kick`, `snap`, `click`, `buzz`, `heartbeat`, `tick`, `flash`, `drum_roll`) with type, intensity, duration, pulse, frequency. Consumed by other code; never writes hardware itself.
- `shaping.py` holds all the per-tick shapers + `TriggerState` (latch on/off) + `apply_trigger(...)` — keep `bridge._loop()` free of math by funnelling through here.

### Bluetooth & Discovery

`bluetooth.py` does discovery only — the OS handles pairing. `list_devices()` is the cross-platform API; per-OS implementations sit behind it.

```python
# bluetooth.py — public dataclass
@dataclass
class BluetoothDevice:
    name: str
    address: str          # canonical MAC: aa:bb:cc:dd:ee:ff
    # ...rssi, battery, connection state where exposed
```

- macOS: IOBluetooth via PyObjC, lazy-loaded. Graceful no-op if PyObjC isn't installed.
- Windows: `Get-PnpDevice` PowerShell queries.
- Linux: `bluetoothctl` subprocess.
- Never attempt programmatic pairing. UI exposes a "Open Bluetooth settings" button instead; users pair through the trusted OS UI once per device.
- Battery / RSSI fields may be `None` on any platform — UI must handle that.

### Cross-Platform Controllers

`controller.ControllerReader` is the pygame-ce / SDL2 wrapper. `dualsense.py` is the parallel hidapi handle for the bits SDL2 doesn't expose.

```python
# controller.py — keep SDL headless so we don't pop a window
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # MUST be before `import pygame`
import pygame

@dataclass
class ControllerInfo:
    name: str; num_axes: int; num_buttons: int; num_hats: int; guid: str

class ControllerReader:
    """Polls one connected joystick by pygame index. One reader per bridge."""
```

- Only `pygame.joystick` is initialised — never `pygame.display` or `pygame.audio`. Keeps the PyInstaller bundle lean and prevents the dummy window flash.
- DualSense detection: `BridgeWorker._maybe_open_dualsense(info)` matches `"dualsense"` or `"dual sense"` (case-insensitive) in the SDL controller name. On macOS the name is `"DualSense Wireless Controller"`; Windows via XInput-passthrough varies — match generously.
- `dualsense.find_first()` returns a device handle if hidapi sees one. `dev.open()` gives you a `DualSenseHandle` (input + adaptive triggers + battery + touchpad + wired/BT detection).
- Multi-controller (`multi.py`) uses `slot_index` on every reader so two pygame joysticks can coexist. Slot 0 keeps the default port name; slot 1+ suffixes with the slot number.
- Don't import pydualsense, dualsense-controller, or pyPS4Controller. They each have a fatal flaw documented in `dualsense.py` (Win/Linux only, GPL adjacency, callback thread fights pygame).
