# Hall: General App Design

Boot path, Qt setup, the BridgeWorker engine, logging, on-disk config, and the hardware-free demo modes (synthetic / keyboard / mouse). Read this hall before touching `__main__.py`, `app.py`, `bridge.py`, `logger.py`, `paths.py`, or anything to do with packaging.

### Startup & Qt Setup

Entry point is `gamepad_midi_bridge.__main__:main` (declared in `pyproject.toml` `[project.scripts]`). It parses argparse flags, installs the crash hook, sets up logging, then either branches into a CLI sub-command (`--reset-config`, `--export-pack`, `--import-pack`, `--log-path`), `_do_headless()`, or `from .app import run` for the GUI.

```python
# __main__.py — main() shape
install_crash_hook()
args = _build_parser().parse_args()
# ...short-circuit flags...
setup_logging(console=args.debug)
if args.headless:
    return _do_headless(args.deep_link, demo=args.demo, keyboard=args.keyboard, mouse=args.mouse)
from .app import run
return run(sys.argv)
```

- The packaged binary is named **`Universal Controller MIDI`** — both the macOS `.app` bundle (`bundle_identifier='design.aidxn.gamepad-midi-bridge'`) and the Windows / Linux executable use this name. Build via `python build.py` which writes per-OS PyInstaller args.
- `Universal Controller MIDI.spec` is the canonical PyInstaller spec. `Gamepad MIDI Bridge.spec` is the legacy/old name flagged for deletion — do not edit it.
- macOS `Info.plist` keys live in `build.py` (`MACOS_PLIST_KEYS`): `NSBluetoothAlwaysUsageDescription`, `NSGameControllerUsageDescription`, `NSAppleEventsUsageDescription`, etc. Missing strings = TCC kill on first IOBluetooth / GCController touch.
- On exit `__main__` calls `os._exit()` to bypass Python finaliser teardown — works around a PySide6/Shiboken `destructionVisitor` segfault on macOS. Don't replace with `sys.exit()`.
- GUI path picks demo/keyboard/mouse/background from env vars (`GMB_DEMO`, `GMB_KEYBOARD`, `GMB_MOUSE`, `GMB_BACKGROUND`) — set by `__main__` from argparse so `app.run()` doesn't need to re-plumb.

### Bridge Engine

`bridge.BridgeWorker(QObject)` runs on a `QThread` owned by `bridge.BridgeController`. Owns the controller reader, MIDI port, calibration state, OSC sender/receiver, MIDI-in port, RTP sender, pattern engine, A/B-compare cache, recording buffers, and a long list of per-tick state dicts.

```python
# bridge.py — public signals + entry slot
class BridgeWorker(QObject):
    status = Signal(str); started = Signal(str, str); stopped = Signal()
    error = Signal(str); controller_info = Signal(object)
    axis_value = Signal(int, float); button_state = Signal(int, bool)
    battery_changed = Signal(int, bool, bool); touchpad_xy = Signal(bool, float, float)
    midi_sent = Signal(); midi_message = Signal(str, int, int, int, int, str)
    preset_change_requested = Signal(str)  # Program-Change → preset hot-swap
    @Slot()
    def start(self) -> None: ...  # opens reader, MIDI port, then _loop()
    @Slot()
    def stop(self) -> None: self._running = False
```

- The inner `_loop()` pumps `reader.pump()` → `_poll_buttons` → `_poll_axes` → `_poll_polar_sticks` → `_poll_corners` → `_poll_hat` → `_poll_dualsense` then sleeps the remainder of `1/poll_hz`. Keep the loop hot. Never block. Anything heavy goes in a slot on the GUI side over a queued connection.
- `set_mapping()` is callable mid-run. It updates `_state.mapping`, re-syncs OSC/MIDI-in/passthrough/clock/RTP/corner-detectors, re-applies haptics, and reopens the MIDI port if the name override changed.
- `panic()` sends CC 123 + CC 120 + every note-off across all 16 channels (~2080 messages). Emergency stop only.
- `send_test_note(channel, note, velocity, duration_ms)` schedules note-off via a `QTimer` stored in `_test_note_timers` to keep it alive.
- MIDI sends route through `_send_note_on`/`_send_note_off`/`_send_cc`. These branch on `_use_midi2()` (UMP-aware) and call `_emit_midi_message` for the activity log + `_record_midi_send` for macro/pattern recording + `_rtp_send` for the RTP-MIDI sender.
- Haptic-input MIDI callback runs on librtmidi's C thread. Direct HID writes from there are safe IFF you hold `self._haptic_lock` — never marshal to the worker's QThread, it never spins a Qt event loop.

### Logging & Crashes

Two cooperating modules — `logger.py` (rotating file log) and `crash_reporter.py` (atexit + uncaught-exception writer).

```python
# logger.py — setup() is idempotent; returns the log path
def setup(level: int = logging.INFO, console: bool = False) -> Path:
    # configures a RotatingFileHandler under user_data_dir()/logs/app.log
```

- Log lives at `user_data_dir()/logs/app.log`. `gamepad-midi-bridge --log-path` prints it for bug reports.
- `crash_reporter.install_hook()` is called in `main()` BEFORE arg parsing so crashes during arg parse still get captured.
- Crash files go in `crash_dir()` with timestamped names. They're plain text — users zip and attach. Never phones home; opt-in telemetry is separate.
- Use `logging.getLogger(__name__)` from modules; never print to stderr directly except in CLI sub-commands.

### Settings & Config

`paths.py` is the canonical location resolver — pure stdlib, no `platformdirs` dependency so PyInstaller stays lean.

```python
# paths.py — user_data_dir() per-OS resolution
def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
```

- `config_path()` returns the single JSON config file. Both telemetry opt-in and updater opt-out live there — no second config to manage.
- `license_path()` returns the licence blob location. Licence verification reads + caches once per process.
- `presets_dir()`, `snapshots_dir`, `autosaves_dir`, `crash_dir` all derive from `user_data_dir()`.
- `settings_export.SettingsManager` is the typed key/value store with namespace (`ui.window_width` etc.) and JSON round-trip. Use for UI prefs, last-port-name, theme — not for licence / mapping (those have dedicated files).
- `--reset-config` unlinks `config_path()` only. Mapping, presets, licence are kept.

### Keyboard/Mouse Demo Mode

Three drop-in alternatives to `ControllerReader` for hardware-free work — same interface so `bridge.BridgeWorker` doesn't need to know which is active:

| Mode | Reader class | Flag / env | Use |
| --- | --- | --- | --- |
| Synthetic | `demo_controller.SyntheticControllerReader` | `--demo` / `GMB_DEMO=1` | Demo videos, CI, connector smoke tests. Sticks sweep sine/cos, triggers ramp, buttons pulse. |
| Keyboard | `keyboard_controller.KeyboardControllerReader` | `--keyboard` / `GMB_KEYBOARD=1` | WASD + arrows + keys. Needs `install_keyboard_filter(app)` on the QApplication. |
| Mouse | `mouse_controller.MouseControllerReader` | `--mouse` / `GMB_MOUSE=1` | Cursor + clicks. Needs `install_mouse_filter(app)` on the QApplication. |

```python
# bridge.BridgeWorker.start() — reader selection
if self._keyboard:
    self._reader = KeyboardControllerReader(slot_index=self._slot_index)
elif self._mouse:
    self._reader = MouseControllerReader(slot_index=self._slot_index)
elif self._demo:
    self._reader = SyntheticControllerReader(slot_index=self._slot_index)
else:
    self._reader = ControllerReader(slot_index=self._slot_index)
```

- Headless mode honours `--demo`, `--keyboard`, `--mouse` and installs the right Qt event filter on the `QCoreApplication`.
- The keyboard/mouse buses are singletons (`keyboard_bus.KeyboardBus`, `mouse_bus.MouseBus`). They register a Qt event filter and broadcast key/mouse state — readers read from the bus, never directly from Qt events.
- Don't add hardware-specific behaviour to the demo readers. They exist to validate mappings; any DualSense-specific feature (battery, touchpad, haptics) must degrade gracefully when the reader isn't `ControllerReader`.

### Qt Lifetime, Teardown & Layout Traps

Hard-won PySide6/Qt6 rules. These caused real macOS crashes/bugs (2026-06-17) — don't relearn them.

- **Hard-exit at the event-loop boundary. Never let PySide6 tear widgets down.**
  When the Qt event loop returns, `app.run()` performs an immediate hard process
  exit (`os` low-level exit, value = rc) — no widget deleteLater, no
  processEvents, no gc collect, no Python finaliser. Reason: Shiboken's
  `destructionVisitor` segfaults (`EXC_BAD_ACCESS` in `QObject` destructor) while
  sweeping any live Qt wrapper (QSlider, QDoubleSpinBox, …) whose C++ side is
  being deleted. closeEvent + `autobackup.mark_clean_shutdown` already ran inside
  the loop, so nothing is left to flush; the OS reclaims memory. Every entry
  point must funnel here: `console_entry` (hard-exits in a `finally`),
  `python -m`, the PyInstaller `scripts/app_entry.py` (→ `console_entry`), and
  direct `run()`. Don't add a "tidy teardown" — it reintroduces the segfault.
- **Ctrl-C → `SIGINT` set to `SIG_DFL` in `run()`.** Qt swallows SIGINT, and when
  it surfaces it unwinds into Python's finaliser → the same teardown segfault.
  Restoring the default handler makes the OS terminate the process directly.
- **A `QSplitter` honours each child's `minimumSizeHint` as a hard floor.** A
  `QTabWidget`'s `minimumSizeHint` is the MAX over ALL pages, so one tall
  unscrolled page (e.g. About at ~1080 px) forces the whole content area taller
  than the window and squeezes sibling panes (the bottom Console/MIDI dock) to
  their minimum — they look "stuck collapsed". Fixes: scroll-wrap tall tab pages
  (`_scrollable()` in main_window) AND `ResponsiveTabWidget.minimumSizeHint`
  caps its height so no page can break a sibling pane.
- Verify splitter behaviour by reading `splitter.sizes()` after a `singleShot(0)`
  settle — not by visibility (always reports hidden until the top-level window is
  shown; check `not w.isHidden()`).

### Learn mode (hover-to-learn) — `ui/learn_mode.py`

Toolbar-toggled discoverability layer. When the **Learn** toggle is on, hovering
any tagged widget pops a card near the cursor explaining it; off = silent. This
is a **deep, ongoing sweep** — the whole app should be covered over time.

- **To make a control learnable:** `from .learn_mode import learn` then
  `learn(widget, "Short title", "One or two plain-English sentences — what it
  does + why you'd use it.")`. Tag the most meaningful container (e.g. a card),
  not every child — the resolver walks up to 6 parents to find the nearest tag.
- **Architecture:** `learn()` stores dynamic properties; `LearnController` polls
  `QApplication.widgetAt(QCursor.pos())` at ~11 Hz *only while active* (mouse
  tracking / `WA_Hover` aren't universal, so polling is the reliable path). The
  overlay is `WA_TransparentForMouseEvents` so it never steals hover.
- **Coverage tracker:** done — top toolbar (`_register_toolbar_learn`). TODO —
  Mapping, Live, Connectors, Presets, Settings, Bluetooth, Nodes, Marketplace,
  Templates, Visualise, Help/About. Add a `_register_*_learn()` per tab and call
  it once the tab is built.
- Voice: plain English, audience = a VJ/Ableton user who isn't a MIDI expert.
  No jargon without a gloss. Keep to ~1–2 sentences (the card wraps at 300 px).

### Qt/PySide6 tooling — use it, don't guess from memory

Training data is unreliable on Qt 6.x APIs. For any Qt/PySide6 API question
(signals, slots, defaults, since-version, lifetime, layout behaviour) consult a
live source BEFORE answering:

- **qt-docs MCP** (`qt_documentation_search` / `qt_documentation_read`) — official Qt 6 docs; applies to PySide6 (same API).
- **context7** — `resolve-library-id` → `/websites/doc_qt_io_qtforpython-6` (official Qt for Python, 100k+ snippets) or `/erriez/pyside6-getting-started`; `/pytest-dev/pytest-qt` for tests.
- **`pyside6-ui-engineer`** skill (user-level) — Widgets-surface selection, layout/hierarchy, model/view, threading, UX passes. Our app is PySide6 **Widgets** (not QML/C++), so the official `qt-cpp-*` / `qt-qml-*` skills are off-stack here.
