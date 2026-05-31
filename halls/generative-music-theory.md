# Hall: Generative & Music Theory

Scales, chords, key-quantization, rhythm grids, groove templates, glide / delay, LFOs, time-based sequencing, macros, effects, pad layouts, and multi-controller orchestration. Modules here are pure-stdlib + math — no Qt, no rtmidi, no hardware. Caller supplies note numbers and timestamps; modules return new note numbers, new timestamps, or generators.

### Scales & Intervals

```python
# scales.py — semitone offsets from root, modulo 12
SCALES = {
    "major":          (0, 2, 4, 5, 7, 9, 11),
    "minor":          (0, 2, 3, 5, 7, 8, 10),
    "dorian":         (0, 2, 3, 5, 7, 9, 10),
    "mixolydian":     (0, 2, 4, 5, 7, 9, 10),
    "minor_pent":     (0, 3, 5, 7, 10),
    "blues":          (0, 3, 5, 6, 7, 10),
    # ...
}
```

- Always interval-from-root tuples, never note-name strings. Note names are a UI layer concern.
- `note_transpose.py` — global transposition with clamp to 0..127. Use this before any scale snap, not after.
- `note_range.py` — forces outgoing notes into a configured range by octave-shifting. Different from `note_range_analyzer.py` (analytics).

### Chords & Progressions

```python
# chord_shapes.py — pure functions on note lists
def voicing(root: int, shape: str) -> list[int]: ...
def invert(notes: list[int], n: int = 1) -> list[int]: ...
def transpose(notes: list[int], semitones: int) -> list[int]: ...

# chord_progression.py
class ChordProgressionCycler:
    def next(self) -> list[int]: ...
    def reset(self) -> None: ...
```

- `chord_shapes.py` is stateless. `chord_progression.ChordProgressionCycler` walks through a configured shape list — one shape per call.
- `scale_chord_builder.py` composes triads and seventh chords from scale degrees (build a I–IV–V in any scale without hardcoding intervals).
- Don't store chord state inside `Mapping`. Persist the progression as a list of shapes + a reset rule; rebuild the cycler on preset load.

### Quantization & Keying

```python
# pitch_key_quantizer.py — snap to nearest in-key note
def snap_to_scale(note: int, root: int, scale_intervals: tuple[int, ...]) -> int: ...
```

- Snap-to-scale runs BEFORE any glide / delay / macro — quantising downstream of those introduces drift.
- `pitch_wheel_sensitivity.py` and `pitch_bend_range.py` are MIDI-protocol concerns (RPN messages), not music theory — they live here because they shape pitch but they touch the MIDI byte layer.

### Rhythm & Grid

```python
# euclidean.py — Bjorklund's algorithm
def euclidean(steps: int, pulses: int, rotation: int = 0) -> list[bool]: ...

# polyrhythm.py — interlocking Euclidean patterns (3-against-4, etc.)
@dataclass
class PolyrhythmConfig:
    patterns: list[tuple[int, int]]  # [(steps, pulses), ...]
    base_bpm: float
```

- Euclidean rotation is in steps, not radians. Negative rotation rotates the other direction.
- `groove_template.py` — micro-timing offsets on beat grids (MPC swing, Linn swing, custom curves). Apply as `time += offset(beat_position)`.
- `quantize_grid.py` — quantise note events to a beat grid. `humanized_quantizer.py` adds per-event jitter on top so quantised playing doesn't sound robotic.
- `time_signature.py` — bar lengths, downbeats, beat positions. Use for "fire on bar boundary" logic, not for raw rhythm generation.

### Glide & Delay

```python
# glide.py — smoothly interpolate target values (notes or CC) over time
class GlideController:
    def __init__(self, glide_ms: float, mode: str = "linear") -> None: ...
    def step(self, target: float, dt_ms: float) -> float: ...

# tap_delay.py — fire a note plus N delayed copies at decreasing velocity
def schedule_taps(note: int, vel: int, n: int, delay_ms: int, decay: float) -> list[tuple[int, int, int]]:
    # Returns list of (delay_ms, note, velocity) tuples
```

- Glide modes: `linear`, `ease_in`, `ease_out`, `ease_in_out`. State per-controller — keep one per voice.
- `tap_delay.py` returns the schedule; the caller (BridgeWorker) is responsible for actually firing via QTimer. Pure-function intent: makes the math testable.
- Don't combine glide + tap-delay in one helper. Compose at the bridge layer.

### LFO & Modulation

```python
# lfo_waveforms.py — pure function generators
def sine(phase: float) -> float: ...      # phase 0..2pi → -1..1
def triangle(phase: float) -> float: ...
def saw(phase: float) -> float: ...
def square(phase: float, pulse_width: float = 0.5) -> float: ...
def random_smooth(phase: float, seed: int) -> float: ...

# lfo_bank.py — N independent LFOs with optional phase sync
@dataclass
class LfoBankConfig:
    lfos: list[LfoConfig]
    global_phase_sync: bool = False
```

- LFO phase is in radians 0..2π. Don't track wall-clock time directly — compute phase from `(now - epoch) * frequency * 2π`.
- `lfo_bpm_sync.py` derives LFO rate from the live BPM. `lfo_phase_scope.py` is the UI sampler that doesn't drive sound.
- Bridge-side state: `BridgeWorker._lfo_phase: Dict[int, float]` keyed by axis index. Reset on `set_mapping` so a different preset doesn't inherit the wrong phase.
- `random_walk.py` is the smooth-random alternative to a noisy LFO — CC values drift inside configured bounds.

### Sequencing & Timing

```python
# timed_note_scheduler.py — queue notes at future timestamps with cancellation
class TimedNoteScheduler:
    def schedule(self, t_ms: float, note: int, vel: int, ch: int) -> int: ...  # → handle
    def cancel(self, handle: int) -> bool: ...
    def step(self, now_ms: float) -> list[tuple[int, int, int]]: ...  # fired events

# bpm_sync.py — beat-grid sync helpers
def beat_position(now_ms: float, bpm: float, epoch_ms: float) -> float: ...
def quantize_to_beat(t_ms: float, bpm: float, epoch_ms: float, division: float) -> float: ...
```

- `pattern.PatternEngine` is the continuous-loop recorder with overdub. State machine: `IDLE → ARMED → RECORDING → PLAYING → OVERDUB → ...`. Bridge owns one engine per worker — see `BridgeWorker._pattern_engine`.
- `tempo_tap.py` infers BPM from a sequence of taps. `note_bpm_estimator.py` does the same from note onsets (passive listening).
- Don't write your own scheduler. Compose `TimedNoteScheduler` with a per-tick `step(now_ms)` call inside the bridge loop.

### Macros & Effects

```python
# macro_library.py — named parametric macro sequences
MACRO_KINDS = ("flam", "drumroll", "glissando", "portamento", "trill", "tremolo")

# mapping.py — recorded macro shape
@dataclass
class MacroEvent:
    delay_ms: int
    status: int
    data1: int
    data2: int

@dataclass
class Macro:
    name: str
    events: list[MacroEvent]
    duration_ms: int
```

- `BridgeWorker.start_recording() / stop_recording() / cancel_recording()` capture outbound MIDI as a `Macro`. Returned `Macro.name` is empty — caller assigns and appends to `mapping.macros`.
- Playback: `BridgeWorker._play_macro(macro, midi)` schedules every event via `QTimer.singleShot` at absolute `delay_ms` offsets. Multiple playbacks are independent.
- `macro_library.py` provides parametric builders — `flam(note, intensity, count)`, `glissando(start, end, ms)` etc. — that emit `Macro` objects. Use these for built-in effects; recorded macros use the recorder path.

### Pad Layout Assistant

```python
# pad_layout.py — auto-assign N pad buttons to a scale ergonomically
def assign_pads(n_buttons: int, scale: tuple[int, ...], root: int = 60) -> dict[int, int]:
    # Returns {button_index: midi_note}
    # Honours physical ergonomics — adjacent buttons get adjacent scale degrees
```

- Pad layout is read-only-ergonomic: don't let it reorder based on usage stats. Predictability beats optimisation here.
- `corner_quantizer.py` (in controller-input hall) turns a stick into 4/8/16 buttons; pad-layout assignment then maps those into scale degrees.

### Multi-Controller Orchestration

```python
# multi.py — Pro feature, 1..2 BridgeControllers
MODE_OFF = "off"           # single slot always (default)
MODE_AUTO = "auto"         # both slots if Pro + 2 detected
MODE_FORCE_TWO = "force_two"  # Pro-only, error if <2 connected
MAX_SLOTS = 2

def port_name_for_slot(slot_index: int) -> str:
    # Slot 0 keeps DEFAULT_PORT_NAME so existing DAW routings survive upgrades.
    # Slot 1+ suffixes: "Universal Controller MIDI 2".

def mapping_for_slot(base: Mapping, slot_index: int) -> Mapping:
    # Deep-copies + channel-bumps. Slot 0 = base.midi_channel, slot 1 = +1, etc.

def desired_slot_count(mode: str, detected: Optional[int] = None) -> int:
    # Free tier always returns 1. force_two raises if <2 connected.
```

- Free tier always returns 1 slot regardless of mode — multi-controller is gated by `license.feature_enabled("multi_controller")`.
- Each slot gets its own MIDI port name and its own deep-copied mapping with a bumped channel. DAW receives controller 1 on channel 1, controller 2 on channel 2 (default; user can edit per slot in Pro editor).
- Signals are NOT slot-tagged. The GUI wires each slot's worker to its own meter directly. This keeps `BridgeWorker` untouched on the single-controller path.
- `_demo_env()` / `_keyboard_env()` honour `GMB_DEMO` / `GMB_KEYBOARD` so all slots opt into synthetic / keyboard input together — don't mix real + synthetic.
