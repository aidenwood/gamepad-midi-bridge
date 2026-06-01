# Hall: Analytics, Telemetry, Licensing

Free vs Pro gating (Ed25519 offline-verified licence), opt-in telemetry, note / velocity / control analytics, latency, battery + device, DAW + app detection, audio-reactive sim, usage stats, crash reporter, and the soft updater.

### Licensing & Gating

Ed25519-signed JSON blob, verified offline against `PUBLIC_KEY_PEM` in `license.py`. The Stripe webhook on `midi.aidxn.com` signs blobs with the matching private key (lives only in that Netlify project's env vars) and delivers them via Resend.

```python
# license.py — public surface
PUBLIC_KEY_PEM: bytes = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEANE5ihyMUoHerpfxmquOtXLwjrj5d/9V+7dzny4O5krY=
-----END PUBLIC KEY-----
"""

PRO_FEATURES: Set[str] = {
    "mapping_editor", "presets", "multi_controller", "osc_output",
}

@dataclass
class LicenseState:
    is_pro: bool
    email: Optional[str] = None
    reason: Optional[str] = None

def state() -> LicenseState: ...
def is_pro() -> bool: return True   # !! TESTING UNLOCK — see note
def feature_enabled(feature: str) -> bool: ...
def activate_from_string(blob: str) -> LicenseState: ...
def deactivate() -> None: ...
```

- The `PUBLIC_KEY_PEM` above is the **TEST** key (matches `scripts/public_key.test.pem` + `private_key.test.pem`). `LAUNCH.md` step 1.0 says swap to production public key (paste `scripts/public_key.pem`) before tagging v2.0.0.
- `is_pro()` currently **hard-returns `True`** for the bring-up testing window. Revert to `return state().is_pro` before any release build ships — otherwise the signed-licence gate is bypassed entirely.
- Licence blob format: `base64url(payload).base64url(signature)`. Payload is JSON `{"email": "...", "tier": "pro", "issued_at": "..."}`. Signed with Ed25519 over `payload_bytes`.
- `_load_and_verify()` fails closed — any exception (cryptography missing, malformed blob, bad signature) returns `LicenseState(is_pro=False, reason=...)`. Never let licence-load throw to callers.
- Per-feature gating: `feature_enabled(name)`. Free features return `True` unconditionally; Pro features check `is_pro()`.
- Migrations for the `licenses` / `purchases` tables live in the **Store repo only** (`PS5-MIDI-Bridge-Store/supabase/migrations/`). This desktop project reads with the public anon key — never `apply_migration` from here.

### Telemetry

**Principle: telemetry is for analytics, not surveillance. Never sly. Always known. Easy to stop.** Aiden's rule — if a user can't see exactly what's being sent and flip it off in one click, the implementation has failed.

```python
# telemetry.py — opt-in anonymous events
TELEMETRY_URL = "https://midi.aidxn.com/api/telemetry"
TIMEOUT_SEC = 4

def is_enabled() -> bool: ...  # default OFF; reads config_path() telemetry_enabled
def set_enabled(enabled: bool) -> None: ...
def send_event(event: str, **fields: Any) -> None:
    # Fire-and-forget on a daemon thread. No-op when disabled.
```

**Required UX commitments (non-negotiable — flag any code that breaks these):**
- **Default OFF.** First-launch onboarding screen shows "Help improve the app" toggle with the exact list of fields sent. User must affirmatively opt in.
- **Always-visible status.** Settings → Privacy panel has a live "Telemetry: ON / OFF" indicator. Status bar shows a small dot when telemetry is enabled — never hidden chrome.
- **One-click off.** Single toggle in Settings. No "are you sure" dialog, no friction. Disable is immediate and persistent.
- **Inspect what's sent.** Settings → Privacy → "View recent telemetry payloads" — last 50 events in plain JSON, read-only. If a user can't audit it, it's sly.
- **No silent re-enable.** Updates never flip the flag back on. Migration path on schema change defaults to the user's prior value, falling back to OFF.

**Data rules:**
- Fields sent: `event`, `app_version`, `os`, `os_version`, plus the kwargs the caller passes.
- Fields NEVER sent: mapping contents, preset names/JSON, controller serial numbers, IP-identifiable info (Netlify edge strips IP from the bucket), timing data that could correlate to a specific user.
- Opt-in flag (`telemetry_enabled: bool`) lives in the same `config_path()` JSON as the updater opt-out — one config file, two preferences.

**Endpoint status:**
- `https://midi.aidxn.com/api/telemetry` is hardcoded at `telemetry.py:32`. The Netlify Function `netlify/functions/telemetry.ts` exists in the Store repo (since 2026-05-26) — endpoint may already be live; needs DNS + curl verification.
- No env-var override yet; staging requires monkey-patching the constant.
- Posts run on a daemon thread; failures are silent (`urllib.error.URLError` swallow). Telemetry never affects app behaviour or UX latency.
- Migrations for the telemetry bucket live in the Store repo's Supabase migrations. Don't manage schema from here.

### Note Analytics

The `note_*.py` module family is all pure-stdlib analytics — no Qt, no rtmidi, no globals. Each one has a `Config` dataclass, a stateful class with `record(event)` / `summary() / to_dict()`, and clear bucketing semantics.

```python
# performance_stats.py — composes the note-analytics modules into one report
@dataclass
class PerformanceReport:
    note_frequency: NoteFrequencyReport
    note_duration: NoteDurationReport
    velocity_histogram: HistogramReport
    stuck_notes: list[StuckNoteRecord]
```

- `note_frequency.py` — per-note play counts.
- `note_duration_stats.py` — note-on → note-off durations with stat summaries.
- `note_hold_distribution.py` — buckets durations into categorical bins for UI display.
- `note_interval_distribution.py` — semitone intervals between consecutive notes.
- `note_octave_tracker.py` / `note_range_analyzer.py` / `note_quartile_analyzer.py` — pitch range + distribution.
- `note_retrigger_detector.py` — chatter / rapid re-press detection.
- `note_overlap_detector.py` — same-channel collision flags.
- `note_timing_accuracy.py` — note-timing meter against a BPM grid.
- `note_flow.py` — time-bucketed event timeline for visualisation.
- `note_hammer_on.py` — guitar-style hammer-on / pull-off detection.

When adding analytics, follow the existing pattern: stateful class + JSON round-trip + pure-stdlib + zero side effects.

### Velocity & Control Heatmaps

```python
# velocity_histogram.py — ring-buffered velocity distribution
@dataclass
class HistogramConfig:
    bucket_count: int = 8       # clamped 4..32
    max_samples: int = 10000    # clamped 100..1_000_000

# control_heatmap.py — per-control activity counter
@dataclass
class ControlHit:
    control_type: str   # button | axis | trigger | hat | touchpad
    control_id: str     # button.0 | L2 | left_stick_x | ...
    count: int
    last_at: Optional[float]
```

- Both modules are ring-buffered to bound memory. `velocity_histogram.HistogramConfig.max_samples` defaults to 10K — enough for a 2-hour session at moderate density.
- `usage_stats.UsageRecord(kind, index, count, last_used_ms)` is the bridge-side counter; `control_heatmap` is the analytics-side report. They overlap intentionally — the bridge keeps it cheap (no timestamps history); the heatmap keeps it detailed.
- Surface heatmap data in the Usage tab; never use it to auto-reorganise the UI without user consent.

### Device & Battery

```python
# battery_history.py — sampled battery percentages over time
@dataclass
class BatterySample:
    percent: int        # 0..100
    timestamp_s: float
    is_charging: bool
```

- Estimates drain rate via linear regression over the last N samples. Predicts remaining minutes.
- `BridgeWorker._battery_alert_fired` is the once-per-low-state edge guard — fires the "battery low" toast once per low episode, resets on charge.
- `controller_history.py` — persists controller fingerprints (name + GUID + first-seen, last-seen, total-sessions). Surfaces "welcome back, you've been using this controller for 47 sessions" friendly nudges.

### Performance & Latency

```python
# latency_analyzer.py — round-trip MIDI latency stats
@dataclass
class LatencyMeasurement:
    sent_at_s: float
    received_at_s: float
    label: str = ""
    @property
    def latency_ms(self) -> float: ...
```

- `latency_test.py` is the self-test driver — sends a known note, waits for the matching loopback, records the delta. Bridge gates this with `_latency_test_active: bool` so the hot path has zero overhead in normal operation.
- `performance_stats.py` composes note_frequency + note_duration_stats + velocity_histogram + stuck_note_detector into one `PerformanceReport`. Use this for the Performance tab; don't compose those four manually elsewhere.
- 30 Hz GUI telemetry cap: `BridgeWorker._telemetry_interval = 1.0 / 30.0`. Even at 100 Hz polling, GUI signals throttle so QML doesn't drown in updates.

### Activity & Session Logs

```python
# activity_log.py — module-level singleton ring buffer
RING_BUFFER_SIZE = 200
def log() -> ActivityLog: ...    # singleton accessor
# Connect activity_log_updated signal (on log().signaller) to UI for live refresh
```

- Levels: `info`, `warn`, `error`. Use `error` only for things the user must know (port lost, controller disconnected). Routine events stay `info`.
- Distinct from `midi_activity_log.py` — that one is per-MIDI-event; this one is per-bridge-event (start, stop, calibration, preset load).
- The Qt signaller on `log().signaller.activity_log_updated` lets the UI refresh without polling.

### DAW & App Detection

```python
# daw_detector.py — scan installed apps, cache to JSON
@dataclass
class DetectedApp:
    name: str
    version: str
    install_path: Path
    category: str   # "daw" | "vj" | "video"
def detect_installed_apps(force: bool = False) -> list[DetectedApp]: ...
```

- Results cache to `user_data_dir()/daw_detector_cache.json`. Stale after 24 h or `force=True`.
- `daw_autodetect.py` is the simpler "what MIDI ports are open, what does that imply about the running DAW?" sidecar — used to pre-pick a connector during onboarding.
- Linux: many DAWs install via package manager — detection there is name-pattern + `which` rather than file scanning.
- Never auto-launch a DAW. Detection is informational only.

### Color Helpers

```python
# color_helpers.py — pure math, no Qt
def rgb_to_hsv(r, g, b) -> tuple[float, float, float]: ...
def hsv_to_rgb(h, s, v) -> tuple[int, int, int]: ...
def palette(n: int, hue_base: float = 0.0) -> list[tuple[int, int, int]]: ...
```

- RGB ints `0..255`. HSV `(0..1, 0..1, 0..1)`. Don't accept Qt `QColor` here — keep it framework-free.
- `led_brightness_curve.py` is the trigger-driven sidecar for smooth lightbar fades. Pure-function curve transforms (linear, ease-in/out, exponential).
- `lightbar.py` is the actual side-effectful writer to the DualSense (uses `dualsense.py` HID handle). Don't import it from analytics code.

### Audio-Reactive Simulation

```python
# audio_reactive_sim.py — synthetic amplitude → CC, no real audio
# audio_bands_sim.py — 4-band variant (sub-bass / bass / mid / high)
# Modes: direct_follow | peak_hold | envelope_follower
# Threshold + gain + invert + clamp to [min_cc, max_cc] then 0..127
```

- The simulator never captures real audio (and the macOS `NSMicrophoneUsageDescription` Info.plist key is precautionary only — current build does not record audio).
- 4-band variant uses fixed crossover frequencies; don't let the user reconfigure these in v1 — it complicates the CC-mapping UI for no real upside.
- Use for visual demos and "what would audio-reactive look like" preview; real-audio support is a future feature.

### Usage Stats

```python
# usage_stats.py — per-control press counts (no PySide6 dep)
@dataclass
class UsageRecord:
    kind: str               # "button" | "axis" | "hat" | "corner"
    index: Union[int, str]
    count: int
    last_used_ms: int
```

- Imported from the bridge worker thread — no Qt allowed. Use `threading.Lock` for any cross-thread access.
- Distinct from `control_heatmap.py` (deeper analytics) — `usage_stats` is the cheap fast counter; `control_heatmap` is the rich report.

### Crash Reporter

```python
# crash_reporter.py
def install_hook() -> None: ...                     # set sys.excepthook
def crash_dir() -> Path: ...                        # user_data_dir/crashes
```

- Called in `__main__.main()` **before** arg parsing so crashes during arg parse get captured.
- Crash file format: dated `.txt` with full traceback + `__version__` + Python version + OS info. Users zip and attach to bug reports.
- Never phones home. Telemetry is the separate opt-in path; the two systems intentionally don't share infrastructure.
- Includes a `zipfile`-based "package this crash + recent log + last mapping" helper for support workflows.

### Updater

```python
# updater.py — background check, never auto-installs
# Endpoint: midi.aidxn.com/api/version
# Response: {"latest": "0.2.0", "notes_url": "...", "download_url": "...",
#            "minimum_supported": "0.1.0"}
# Channels: stable | beta | dev
```

- Runs on a worker thread on startup. Emits a Qt signal back to the GUI if a newer version is available. UI surfaces a banner that links to release notes; user installs manually.
- Opt-out lives in `config_path()` JSON next to the telemetry flag.
- Channel selection: stable users see only stable releases; beta sees `v1.2.0-beta.N`, `v1.2.0-rc.N`, and stable; dev sees everything.
- Never auto-download or auto-install. The banner is a courtesy, not a phone-home.
