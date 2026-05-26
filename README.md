# Gamepad → MIDI Bridge

Turn a PS5 DualSense or Xbox controller into a MIDI controller. Cross-platform desktop app for VJs, music producers, and live performers.

- Auto-calibrates stick drift on startup
- Sticks → CCs, buttons → notes, D-pad → notes
- Native virtual MIDI ports on macOS and Linux
- Bundled loopMIDI installer on Windows (no manual setup)
- Free tier: live bridging with the default mapping
- Pro tier: custom mapping editor, preset save/load

## Run from source

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[build]"
gamepad-midi-bridge
```

Python 3.9+ required. PySide6 ships its own Qt runtime so no system Qt is needed.

## Build distributable

```bash
python build.py                    # builds for the current OS
```

Outputs land in `dist/`. Per-OS specifics:

- **macOS** — `.app` bundle (codesign + notarize separately for distribution)
- **Windows** — `.exe` directory, optionally wrapped by Inno Setup (`build/windows/installer.iss`)
- **Linux** — single-file binary + `.desktop` file

## Architecture

```
QApplication
 └── MainWindow (Qt thread)
      ├── BridgeWorker (QThread)
      │    ├── ControllerReader (pygame)
      │    ├── Calibration
      │    └── MidiBackend (rtmidi)
      └── UI tabs: Live, Mapping (Pro), Presets (Pro), Settings
```

The bridge engine runs in its own QThread. Stick/button events stream back to the GUI through Qt signals so the UI never blocks the MIDI loop.

## Licensing

Free vs Pro is gated through `src/gamepad_midi_bridge/license.py`. V1 ships with all Pro features locked behind an upgrade dialog. Offline activation via Ed25519-signed keys is wired up but disabled until a purchase flow exists.

## Layout

- `src/gamepad_midi_bridge/` — application code
- `build/` — per-OS packaging configs (Inno Setup, Info.plist, .desktop)
- `scripts/generate_license.py` — issuer-side key generation for Pro licenses
