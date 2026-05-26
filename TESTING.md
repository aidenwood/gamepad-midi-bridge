# Beta testing checklist — V1

Aimed at the first real test session. ~20 minutes top to bottom.

## What you need

- macOS arm64 machine
- DualSense controller (USB or Bluetooth) — Xbox works too but most Pro features are DualSense-only
- A DAW or VJ app to point the MIDI at: Ableton, Resolume, GarageBand, etc.
- The bundled .app at `dist/Gamepad MIDI Bridge.app` (or the zip in the same folder)

## Install

```
open "dist/Gamepad MIDI Bridge.app"
```

If macOS gripes about an unsigned app: System Settings → Privacy & Security → "Open Anyway". Codesigning ships in a later milestone.

## 1. First-run wizard (2 min)

- Should auto-open on first launch
- Walks through: welcome → controller detect → MIDI port test → connector picker → calibration prompt → done
- Click "Start Bridging" on the last screen — main window should already be running the bridge

**Expect:** Wizard finishes, status bar shows "Bridging DualSense Wireless Controller → Gamepad MIDI Bridge".

## 2. Free tier sanity (3 min)

In your DAW, route MIDI input from "Gamepad MIDI Bridge". You should see:
- Move L stick → CC 3 + CC 4 cycle 0→127
- Move R stick → CC 5 + CC 6 cycle 0→127
- L2 / R2 triggers → CC 1 + CC 2
- Press face buttons (Cross/Circle/Square/Triangle) → MIDI notes 60, 62, 64, 65
- D-pad → notes 78-81
- Status bar shows a "N/s" rate readout when you wiggle the sticks

**Expect:** Activity dot pulses teal on every event; rate readout climbs into the 100-200/s range while sticks move.

## 3. Calibration (1 min)

Settings tab → Calibration → Re-calibrate sticks. Don't touch the controller for 1 second. Dialog reports offsets. If any axis shows > 0.30, the controller has hardware drift that software can't fully fix.

## 4. Pro features (locked overlays) (1 min)

These should appear with "Pro" badges and lock overlays. Free-tier sanity check:
- Mapping tab — full table visible behind a Pro-upgrade overlay
- Presets tab — same
- Settings → Stick corners / Touchpad / Adaptive triggers / OSC output — all enabled controls greyed out

**To unlock:** About tab → Enter license key → paste a signed Ed25519 blob. Until your Stripe pipeline is live, generate a dev license with:

```
.venv/bin/python scripts/generate_license.py keygen      # one-time
.venv/bin/python scripts/generate_license.py sign --email you@aidxn.com
```

Copy the printed blob, paste it into "Enter license key" in the app.

**Expect:** "Pro unlocked" dialog, Pro panels' lock overlays disappear.

## 5. Adaptive triggers (Pro, mac-only test) (2 min)

Settings → Adaptive triggers — set L2 to "Weapon", R2 to "Vibration". You should feel the trigger resist (Weapon) and buzz (Vibration) on the DualSense. macOS routes through Apple's GameController framework — requires `pyobjc-framework-GameController` installed in your Python env (already done locally).

**Expect:** Both triggers feel different to before. "Off" returns them to default.

## 6. Stick corners (Pro) (2 min)

Settings → Stick corners → Left stick = "8 corners". Save. Now push the L stick fully to each of the 8 compass points. Each should fire a unique MIDI note (default chromatic from C6).

**Expect:** 8 distinct notes per push, hysteresis prevents chatter on the boundaries.

## 7. Touchpad XY (Pro) (1 min)

Settings → Touchpad → tick "Enable touchpad as XY MIDI surface". Touch the DualSense touchpad and slide your finger. CC 16 (X) and CC 17 (Y) should update in your DAW.

**Two-finger mode:** Tick that checkbox, put a 2nd finger on the pad — CCs 18 + 19 update only while the 2nd finger is down.

## 8. Connectors (3 min)

Connectors tab. If you have Resolume / Ableton / TouchDesigner / VDMX / MadMapper / Reaper installed, they'll show as detected. Click "Install" on one.

- **Resolume** — opens Shortcuts menu → Application Map → pick "Gamepad MIDI Bridge"
- **Ableton** — restart Live → Prefs → MIDI → Control Surface dropdown → pick "Gamepad MIDI Bridge"

## 9. Portable config (1 min)

About tab → Export config → save a `.gmbpack` file. Reset config (`gamepad-midi-bridge --reset-config` from terminal) then re-import the pack via About tab. Mapping should restore.

## 10. OSC output (Pro) (2 min)

Settings → OSC output → enable. Default host 127.0.0.1, port 7000 (Resolume's listen port). Open Resolume → Preferences → OSC → enable input on port 7000.

You'll need to bind the OSC addresses to Resolume parameters separately for now (the address-per-control editor lives in the preset JSON — Pro UI for this is a v1.1.x).

## 11. CLI flags (1 min)

From terminal:

```
"dist/Gamepad MIDI Bridge.app/Contents/MacOS/Gamepad MIDI Bridge" --version
"dist/Gamepad MIDI Bridge.app/Contents/MacOS/Gamepad MIDI Bridge" --log-path
"dist/Gamepad MIDI Bridge.app/Contents/MacOS/Gamepad MIDI Bridge" --headless
```

## Things to watch for and report

- Latency feels right (no audible delay between gamepad input and DAW response)
- Calibration handles your specific drift profile
- Tray icon shows up in the macOS menu bar
- Status bar `N/s` readout reflects what you're doing
- No crashes; if anything dies, check `~/Library/Application Support/Gamepad MIDI Bridge/crashes/` and attach the file

## Known gaps for V1.x

- macOS adaptive triggers: bow / galloping / machine effects fall back to "off" (Sony libpad SDK only, not in Apple's framework)
- BT haptics: framing tested via CRC but not yet validated against a real DualSense over BT — feedback welcome
- No app codesigning yet (manual "Open Anyway" required on first launch)
- Xbox impulse-trigger haptics deferred to v2 (no Python binding for GameInput)
- Mapping editor + preset editor UI is read-only until v1.1 — for now, edit preset JSON files directly in `~/Library/Application Support/Gamepad MIDI Bridge/presets/`
