# Architecture

Quick orientation for anyone forking, contributing, or just trying to understand why the code is laid out the way it is. Pair this with the [contributing guide](./contributing.md) if you want to land a PR.

## High-level flow

```
+-----------------+          QThread          +-------------------+
|  pygame-ce      |   axis/button events     |  BridgeWorker     |
|  (SDL2 input)   | -----------------------> |  - calibration    |
+-----------------+                          |  - corner quantz  |
                                             |  - mapping apply  |
+-----------------+   HID I/O                |                   |
|  hidapi         | <----------------------> |                   |
|  DualSense      |  battery, touchpad,      |                   |
|  extras         |  adaptive trigger writes |                   |
+-----------------+                          +---------+---------+
                                                       |
                                       Qt signals      |  python-rtmidi
                                       (queued)        v
+--------------+                         +----------------------------+
|  PySide6 GUI | <----------- meter -----|  virtual MIDI port         |
|  MainWindow  |   updates               |  "Gamepad MIDI Bridge"     |
+--------------+                         +-------------+--------------+
                                                       |
                                       +---------------+---------------+
                                       v                               v
                                +--------------+              +-----------------+
                                |  DAW / VJ    |              |  OscSender      |
                                |  host        |              |  UDP -> host    |
                                +--------------+              +-----------------+
                                                                       |
                                                                       v
                                                          Resolume / TouchDesigner /
                                                          MadMapper / ...
```

The MIDI loop and the DualSense HID loop both live inside the `BridgeWorker`. The GUI never touches either directly — every interaction goes through Qt signals.

## Module map

Everything lives under `src/gamepad_midi_bridge/`.

### Engine

- **`bridge.py`** — `BridgeWorker` (QObject moved into a QThread). Owns the input → mapping → MIDI/OSC pipeline. `_loop()` polls at `mapping.poll_hz` (default 100 Hz).
- **`controller.py`** — Thin wrapper over pygame-ce / SDL2 joystick. Exposes `ControllerReader`, `ControllerInfo`, `available_count()`.
- **`dualsense.py`** — Optional HID layer (battery, touchpad, wired/BT detect, adaptive trigger writes). Uses raw `hidapi` on Windows/Linux; macOS routes through `mac_haptics.py`.
- **`mac_haptics.py`** — PyObjC `GCController` fallback for macOS where Apple blocks raw HID writes post-Catalina.
- **`calibration.py`** — Stick drift detection: captures rest position on Start, applies hysteresis around it.
- **`corner_quantizer.py`** — Stick → sector detector with `r_enter` / `r_exit` hysteresis rings.
- **`mapping.py`** — `Mapping` dataclass, schema, JSON serialisation. See [Mapping schema versioning](#mapping-schema-versioning).
- **`midi_backend.py`** — `python-rtmidi` wrapper. Opens / closes virtual ports. Constant: `DEFAULT_PORT_NAME = "Gamepad MIDI Bridge"`.
- **`osc_backend.py`** — Hand-rolled OSC 1.0 sender over UDP (no `python-osc` dependency). `OscSender` is dataclass-style with `host`, `port` (default 7000), `send(address, *args)`.
- **`multi.py`** — Multi-controller orchestrator. Holds 1..2 `BridgeController` instances, decides slot count from license tier + connected count + user mode (`MODE_OFF` / `MODE_AUTO` / `MODE_FORCE_TWO`). `port_name_for_slot(i)` suffixes the virtual port name so two bridges coexist.

### App scaffolding

- **`app.py`** — `QApplication` bootstrap, CLI flag parsing, `gmb://` URL handler.
- **`__main__.py`** — `python -m gamepad_midi_bridge` entry point.
- **`paths.py`** — Cross-platform user data directory (no `platformdirs` dep, keeps PyInstaller bundles lean).
- **`portable.py`** — `.gmbpack` import/export (mapping + presets + license as one file).
- **`presets.py`** — Preset save/load helpers.
- **`license.py`** — Ed25519 offline verification. `PUBLIC_KEY_PEM` embedded at module scope. See [Licensing](#licensing).
- **`telemetry.py`** — Opt-in anonymous usage stats (default off). `is_enabled()` reads `config.json`.
- **`updater.py`** — `UpdateChecker` (QObject) hits the store endpoint, emits a signal when a newer version is available. Opt-out via Settings.
- **`crash_reporter.py`** — `sys.excepthook` installer. Writes plain-text reports to `<user_data_dir>/crashes/`. Never phones home.
- **`logger.py`** — Structured logging to `<user_data_dir>/logs/app.log`, rotated at 2 MB × 3.

### Host connectors

- **`connectors/base.py`** — `Connector` abstract base, `HostInstallation` dataclass (host name + path + version), `InstallResult` (success bool + message).
- **`connectors/resolume.py`** — Reference implementation. Reading this first will save you time when adding a new one.
- **`connectors/ableton.py`** — Ableton Live 11+ Remote Script installer.
- **`connectors/touchdesigner.py`**, **`vdmx.py`**, **`madmapper.py`**, **`reaper.py`** — One file each.
- **`connectors/templates/`** — Bundled host config files (XML, plist, ReaperKeyMap, JSON palette, Ableton Python source).
- **`connectors/__init__.py`** — `all_connectors()` returns the registered list.

### GUI

- **`ui/main_window.py`** — Top-level window, tab host, status bar, keyboard shortcuts.
- **`ui/onboarding.py`** — First-launch wizard (controller detect → MIDI test → connector picker → calibration).
- **`ui/controller_meter.py`** — Live stick/button visualisation.
- **`ui/mapping_editor.py`** — Mapping tab UI (Pro-gated).
- **`ui/preset_manager.py`** — Preset list + save/load.
- **`ui/marketplace_tab.py`** — Browse + install community presets.
- **`ui/connectors_tab.py`** — Per-host detect/install/uninstall.
- **`ui/settings_panel.py`** — Update opt-in, telemetry opt-in, multi-controller mode.
- **`ui/help_tab.py`** — FAQ, troubleshooting, log/crash folder buttons, keyboard cheat-sheet. Owns the `QShortcut` instances itself so the cheat-sheet always matches reality.
- **`ui/calibration_dialog.py`** — Modal during the calibration capture window.
- **`ui/pro_lock.py`** — Upsell dialog when a free user hits a Pro feature.
- **`ui/tray.py`** — System tray / menu bar icon.
- **`ui/styles.qss`** — Global stylesheet.

## Threading model

- **Main thread.** `QApplication`, `MainWindow`, all `QWidget` subclasses. Anything that draws.
- **Bridge thread.** One `QThread` per `BridgeWorker`. With multi-controller enabled, you get up to two of these. Each owns its own MIDI port, OSC sender, and DualSense HID handle.
- **Updater thread.** `UpdateChecker._worker()` runs on a `QThread` so the network request never blocks the GUI.

Inter-thread comms uses Qt's default **queued signal connections**. Stick/button events emitted from `BridgeWorker` deliver into the main thread's event loop as queued slot calls — thread-safe by default, no manual locking. The GUI never blocks the MIDI loop because the MIDI loop never waits on the GUI.

The bridge worker's `_loop()` is a tight polling loop. It deliberately doesn't use Qt's event loop for input polling — the latency cost would be visible.

## Mapping schema versioning

`SCHEMA_VERSION = 2` (current). Lives in `mapping.py`.

- **v1** — original mapping (buttons, axes, hats, channel, deadzone, poll_hz)
- **v2** — adds `left_stick_corners`, `right_stick_corners`, `touchpad`, `osc`, `l2_haptic_effect`, `r2_haptic_effect`

**Compatibility rule.** Old presets without the new v2 fields load fine — `Mapping.from_dict()` uses `dict.get()` with defaults everywhere. We only bump `SCHEMA_VERSION` on **incompatible** changes that would silently misbehave when read by an older parser. Add a field with a sensible default? Schema stays. Rename or reinterpret a field? Schema bumps and migration logic gets added.

When you do bump the schema:

1. Add the new version to `SCHEMA_VERSION`.
2. Add migration in `Mapping.from_dict()` that branches on the incoming `schema_version`.
3. Keep at least one round-trip test in `tests/` proving v(N-1) preset files still load.

## Connector framework

Every connector subclasses `Connector` and implements:

- `detect() -> List[HostInstallation]` — scan the filesystem for installed copies of the host
- `install(host) -> InstallResult` — copy our template into the host's user directory
- `uninstall(host) -> InstallResult` — remove what `install()` put there
- `is_installed(host) -> bool` — quick check
- `post_install_steps(host) -> str` — human-readable next steps for the GUI

Templates live in `connectors/templates/`. Read `connectors/resolume.py` as the reference — it covers the four most common patterns (XML rewrite, atomic copy, version probe, post-install instructions).

To register a new connector, append it inside `connectors/__init__.py::all_connectors()`. The Connectors tab populates itself from that list.

## Licensing

**Ed25519, fully offline.** `license.py` embeds the issuer's **public** key as `PUBLIC_KEY_PEM`. Verification happens at process start and never touches the network.

- Issuer (private key) lives outside this repo — in the store repo at `PS5-MIDI-Bridge-Store/scripts/`, behind Netlify env vars. **Never** commit `scripts/private_key.pem`.
- A license key is a base64 blob: payload (JSON: email, tier, issued-at) + Ed25519 signature.
- `activate_from_string(blob)` writes to `<user_data_dir>/license.key` and re-runs `_load_and_verify()`.
- `is_pro()` / `feature_enabled(name)` are the gates the GUI calls.

`pro_lock.py` shows the upsell dialog when a free user hits a Pro path. **Never remove a Pro lock unless the user has a valid license** — see [contributing](./contributing.md).

## Where state lives

All under `<user_data_dir>` (resolved by `paths.user_data_dir()`):

| Path | Purpose |
| --- | --- |
| `config.json` | opt-in flags, multi-controller mode, UI prefs |
| `last_mapping.json` | auto-saved current mapping, restored on launch + headless |
| `presets/*.json` | named presets |
| `license.key` | Pro license blob (Ed25519 verified) |
| `logs/app.log` | rotating structured logs (2 MB × 3) |
| `crashes/*.txt` | crash reports (never auto-uploaded) |

Platform-specific roots:

- macOS: `~/Library/Application Support/Gamepad MIDI Bridge/`
- Windows: `%APPDATA%\Gamepad MIDI Bridge\`
- Linux: `$XDG_DATA_HOME/Gamepad MIDI Bridge/` (default `~/.local/share/Gamepad MIDI Bridge/`)

---

Ready to contribute? Read the [contributing guide](./contributing.md) next.
