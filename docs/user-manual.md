# Universal Controller MIDI — User Manual

Welcome. This manual covers everything from first plug-in to running headless on a stage rig. If you only have two minutes, the Quick Start gets you bridging in under a minute.

---

## Quick Start

1. **Plug in a controller.** PS5 DualSense or any Xbox controller over USB or Bluetooth. The Live tab shows it the moment SDL detects it.
2. **Install the virtual MIDI port.** macOS and Linux create the port automatically the first time you click Start. On Windows, the app prompts you to install `loopMIDI` once — accept the prompt and relaunch.
3. **Click Start.** The status badge turns green and the meter strip begins streaming values from sticks and buttons.
4. **Point your DAW at the port.** Open the MIDI input list in Ableton, Logic, Reaper, FL Studio, Resolume, TouchDesigner — whichever — and enable the input named **Universal Controller MIDI**.

That's it. The default mapping is musically sensible out of the box, so you can be triggering clips or modulating filters within a minute of opening the app.

> **Tip.** Cmd/Ctrl + Enter toggles bridging from any tab. Cmd/Ctrl + R re-runs calibration without restarting.

---

## Calibration

Every analog stick drifts a little. Even brand-new controllers report a small non-zero rest position that the app needs to subtract before mapping to MIDI.

**Auto-calibration runs on every Start.** Hold the sticks still for one second and the bridge captures the rest position, then applies an asymmetric deadzone around it so you get full range in the direction you actually push.

**Re-run calibration when:**

- You've swapped controllers mid-session
- The sticks feel sticky or off-centre
- You see ghost CC traffic on the meter with hands off the controller

Use the Recalibrate button on the Live tab, the Calibrate menu in Settings, or the keyboard shortcut.

If your sticks still jitter at rest after calibration, the hardware is worn out — no amount of software fixes a failing potentiometer.

---

## Mapping

### Defaults

The default mapping is built around general-purpose musical control. Out of the box:

| Control | Output |
| --- | --- |
| Face buttons (×, ○, □, △ / A, B, X, Y) | MIDI notes 60–63 (C4–D#4) |
| Shoulder + thumb buttons | MIDI notes 64–69 |
| Stick clicks + Share / Options | MIDI notes 71–77 |
| Left stick X / Y | MIDI CC 3, CC 4 |
| Right stick X / Y | MIDI CC 5, CC 6 |
| L2 trigger | MIDI CC 1 (mod wheel) |
| R2 trigger | MIDI CC 2 (breath) |
| D-pad up/down/left/right | MIDI notes 78–81 |

All output sits on **MIDI channel 1** by default.

### Editing the mapping (Pro)

The Mapping tab lets you reassign every button, axis, and hat. Click any row to remap. Changes persist to `last_mapping.json` automatically — no Save button required — so the next launch picks up exactly where you left off.

The mapping editor is a Pro feature. Free tier ships the default mapping read-only.

---

## Stick Corner Buttons (Pro)

Instead of treating sticks as continuous CC streams, you can quantize each stick into 4, 8, or 16 directional sectors. Push the stick past the outer ring and the sector you're pointing at fires a MIDI note. Pull back inside the inner ring and the note releases.

Useful for:

- Clip-launch grids (8 sectors = a row of 8 clips, one stick)
- Drum pads where you want to play with thumbs, not fingers
- Triggering scenes by direction in Resolume or VDMX

Configure under **Mapping → Stick corners**. The two thresholds (`r_enter` = 0.92, `r_exit` = 0.75) give you a hysteresis ring that prevents jitter at the boundary. Defaults to chromatic sweep starting at C6 (MIDI note 96), but every sector is individually editable.

---

## Touchpad XY (Pro)

DualSense only. The touchpad becomes a Kaoss Pad-style 2D modulator: X position drives one CC, Y drives another.

- Default CCs: 16 (X) and 17 (Y)
- Only sends while you're actually touching the pad, by default — release your finger and the CC stream stops where it was
- Toggle continuous mode if you want the CC to spring back to centre on release

Enable in **Mapping → Touchpad**. Great for filter sweeps, send levels, or VJ blur amount + saturation in a single gesture.

---

## Adaptive Triggers (Pro)

DualSense only. The L2 and R2 triggers have motors inside — the same ones the PS5 uses for feel effects. The bridge exposes seven effects you can attach to each trigger independently:

| Effect | Feel | OS support |
| --- | --- | --- |
| Off | Standard spring | All |
| Feedback | Resistance from a chosen position | All |
| Weapon | Hard stop at trigger point | All |
| Vibration | Continuous buzz | All |
| Bow | Tension that releases past breakpoint | Win + Linux only |
| Galloping | Rhythmic kick | Win + Linux only |
| Machine | Stuttered grind | Win + Linux only |

**OS notes.**

- Windows + Linux talk to DualSense raw HID — full effect set, USB or Bluetooth (Bluetooth uses CRC32-framed packets).
- macOS routes through Apple's `GCController` framework because Apple blocks raw HID writes post-Catalina. Bow / Galloping / Machine fall back to "Off" — Apple's framework doesn't expose them. Install `pyobjc-framework-GameController` in your Python environment if you're running from source.

Attach effects under **Mapping → Adaptive triggers**.

---

## Connectors

The Connectors tab auto-detects which host applications you have installed and one-click installs the matching control map. You still need to enable our virtual MIDI port inside the host — the connector handles everything else.

### Resolume Arena

Installs an XML map verified against four factory presets. Drops into the Resolume user shortcuts directory. After install: open Resolume, choose **Shortcuts → Open** and pick the bridge's map.

### Ableton Live 11+

Installs a Python 3 Remote Script to your User Library:

- macOS: `~/Music/Ableton/User Library/Remote Scripts/Universal Controller MIDI/`
- Windows: `~/Documents/Ableton/User Library/Remote Scripts/Universal Controller MIDI/`

After install: launch Live, open **Preferences → Link, Tempo & MIDI**, set Control Surface to "Universal Controller MIDI" with Input set to our virtual port.

Live 10 and earlier are not supported (they ran Python 2).

### TouchDesigner 2022+

Installs a `.json` palette file that wires standard channels to operators. Drag the palette into your network after install.

### VDMX

Installs a programmatically generated plist template into VDMX's plugin directory. Open VDMX and the bridge appears as a MIDI source with pre-mapped controls.

### MadMapper 5+

Installs a `.mmidi` device file into MadMapper's device library. Open MadMapper → Devices → MIDI to use it.

### REAPER

Installs a `.ReaperKeyMap` plain-text key map. After install: REAPER → Actions → Show action list → Key map → Import.

---

## OSC Output (Pro)

When MIDI's 7-bit resolution or 16-channel ceiling gets in your way, switch to OSC. The Settings panel exposes:

- **Mode** — *Alongside* (MIDI + OSC simultaneously) or *Only* (OSC only, no MIDI port opened)
- **Host** — default `127.0.0.1`
- **Port** — default `7000` (Resolume's default OSC input)

OSC addresses are per-control. Defaults follow the convention `/gamepad/<control>/<idx>`, but every address is editable. Empty maps mean no OSC for that control — the rest still send.

Use OSC when:

- Talking to Resolume Arena, TouchDesigner, or MadMapper natively
- You want sub-millisecond timing without MIDI's serial bottleneck
- You need full-range float values, not 0–127 ints

---

## Multi-controller (Pro)

Plug in two controllers and the bridge can drive them in parallel, each on its own MIDI channel and its own virtual port. Useful for:

- Stereo control (left controller = left channel modulator, right = right)
- Two-performer setups
- Splitting your rig: one controller for clips, one for FX

Settings → **Active controllers** has three modes:

- **Off** — always single-slot (default, free + Pro)
- **Auto** — use both if Pro and two are connected
- **Force two** — error if fewer than two controllers are present (rehearsal-safe)

The second slot's virtual port appears as **Universal Controller MIDI 2** in your DAW's MIDI input list.

---

## Presets and Marketplace

### Save your own

The Presets tab lists every saved mapping. Save the current mapping with a name, switch presets with one click, export to a `.gmbpack` file (mapping + presets + license bundled together) to move setups between machines.

Presets live at `<user_data_dir>/presets/*.json` — see [Where state lives](#where-state-lives).

### Share via Marketplace

The Marketplace tab browses presets published by other users. Click Install and the preset lands in your local library. Trusted authors auto-approve; everyone else passes a moderation queue first.

To publish your own, sign in via the Marketplace tab and submit your preset — the Supabase-backed schema handles versioning + full-text search.

---

## Headless Mode

For kiosks, festival rigs, and dev rigs without a screen:

```bash
gamepad-midi-bridge --headless
```

Loads the last-used mapping automatically and starts bridging immediately. No GUI, no tray icon — just the engine.

Other useful CLI flags:

- `--version` — print version and exit
- `--reset-config` — wipe `config.json` and exit (use when settings get into a weird state)
- `--export-pack <file>` — dump a `.gmbpack` of current mapping + presets + license
- `--import-pack <file>` — restore from a `.gmbpack`
- `--log-path` — print the log file location and exit
- `--debug` — verbose stdout logging

The `gmb://` URL scheme handles one-click license activation and preset imports — clicking a `gmb://activate/<key>` or `gmb://preset/<id>` link in your browser opens the app and runs the action.

---

## Updates

When a new version is published, a banner appears at the top of the main window. Click to download from the store; the dismiss button mutes the banner until the next release.

To opt out of update checks entirely: **Settings → Updates → Check for updates** → off. The check is a single anonymous request to the store's update endpoint, no identifying fields.

---

## Troubleshooting

**Controller not detected.** Quit, reconnect, relaunch. SDL2's hot-plug detection on macOS occasionally misses connections that happen while the app is already running.

**No sound from your DAW.** Open the DAW's MIDI input list and explicitly enable the **Universal Controller MIDI** input. Ableton ships with all MIDI inputs off by default — the most common "it's not working" cause.

**Stick still drifts after calibration.** Auto-calibration handles fixed-offset drift. If your sticks jitter at rest, the hardware is worn — software can't compensate for a failing potentiometer.

**Adaptive triggers feel nothing on macOS.** Install `pyobjc-framework-GameController` in your Python environment. Apple's `GCController` framework is mandatory because raw HID writes are blocked.

**Some Pro effects are missing on macOS.** Bow / Galloping / Machine require Sony's libpad SDK, which Apple's framework doesn't expose. They fall back to "off" silently.

**Bridge crashed.** Crash reports land in `<user_data_dir>/crashes/`. Attach the latest report when emailing support — no automatic upload, ever.

**Windows: no virtual MIDI port option.** Install loopMIDI. The bridge prompts on first run; if you dismissed it, grab it from `tobias-erichsen.de/software/loopmidi.html` and relaunch.

The in-app **Help** tab mirrors this list and adds clickable buttons to open your log file, crash folder, and the GitHub issues page.

---

## Privacy

**Default: nothing leaves your machine.** No accounts, no analytics, no phone-home.

**Opt-in additions:**

- *Update check* (default on) — a single anonymous request to `midi.aidxn.com` at launch to compare versions. No identifying fields. Toggle in **Settings → Updates**.
- *Anonymous usage stats* (default off) — counts feature usage so we know where to invest. Toggle in **Settings → Privacy**. Server strips identifying fields server-side as belt-and-braces.

Crash reports are **never uploaded**. They land in `<user_data_dir>/crashes/` and stay there unless you attach one to a support email.

Logs rotate at 2 MB × 3 files. License keys verify offline via Ed25519 — no online activation server is ever contacted.

---

### Where state lives

| File | What's in it |
| --- | --- |
| `<user_data_dir>/config.json` | Opt-in flags, multi-controller mode, UI prefs |
| `<user_data_dir>/last_mapping.json` | Auto-saved current mapping |
| `<user_data_dir>/presets/*.json` | Named presets |
| `<user_data_dir>/license.key` | Pro license (if activated) |
| `<user_data_dir>/logs/app.log` | Rotated structured logs |
| `<user_data_dir>/crashes/*.txt` | Crash reports (never uploaded) |

`<user_data_dir>` resolves to:

- macOS: `~/Library/Application Support/Universal Controller MIDI/`
- Windows: `%APPDATA%\Universal Controller MIDI\`
- Linux: `$XDG_DATA_HOME/Universal Controller MIDI/` (defaults to `~/.local/share/Universal Controller MIDI/`)

---

Need more depth? The [architecture doc](./architecture.md) covers the engine internals and threading model. For bug reports and feature requests, the GitHub issues link is on the Help tab.
