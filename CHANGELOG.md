# Changelog

Versions follow semver: `MAJOR.MINOR.PATCH`.

## [Unreleased]

Preparing v3.0.0. Public downloads remain on the previous release until hardware verification is complete.

- Live and Setup share a purple header with Phosphor icons, Connect, Output, Status and contextual Learn help.
- Controller discovery no longer shuts down the joystick subsystem while a bridge is using it. Scanning or starting a second controller preserves the first controller's handle.
- Readers stay attached to their device instance when another controller is unplugged and device indices change.
- Connect lists detected controllers and offers a Pro two-controller connection. Status reports each slot's state, MIDI port, channel and sent-message count.
- A lost slot reconnects independently, preserving the other controller's connection. Failed starts clean up their worker thread so another connection can be attempted.
- The paired MIDI/Console dock can expand to half the window height and remembers its dragged height during the session.
- Stick-calibration instructions and results are non-modal toasts. The initial hands-off instruction is highlighted; completion dismisses automatically.
- The controller-input test is opened explicitly from Status and receives raw button/axis input.
- Packaged builds include the host connector templates, so Ableton Remote Script export and Resolume, OBS, REAPER, MadMapper and TouchDesigner template actions can read their bundled files.

## [2.2.1] - 2026-10-22

**Three crashes, and an Xbox pad that finally knows what it is.** Everything below came out of reviewing a recorded first-use session frame by frame.

- **The app no longer crashes every time you plug a controller in.** The first-connect test wizard was handed the `controller_info` *Signal* instead of the controller it carries, and died asking a Qt object for `num_buttons`. The guard above it tested that same Signal for `None`, which a SignalInstance never is, so it never caught anything. Worse than a first-run bug: a controller is only marked "seen" once the wizard *completes*, so a wizard that cannot open never marks it, and the crash repeated on every connect forever.
- **Activating a Pro licence no longer crashes.** The tier label was built inside the About tab, which loads lazily — so buying Pro and pasting the key from the Mapping or Presets tab, or via a `ucmd://` link, hit an `AttributeError` on the paid-conversion path unless you happened to have opened About first.
- **Xbox controllers are identified properly.** Microsoft's USB descriptor sets the product string to the literal word "Controller", so that is what the app displayed — and because the button-naming code matches on that same string, the pad also fell through to generic `Btn 1/2/3/4` labels. The real VID:PID was already being read into the SDL GUID and thrown away. Names now come from there, which fixes the title and the A/B/X/Y labels together.
- **The Visualise tab follows your controller.** It was hardcoded PlayStation, so an Xbox user saw A/B/X/Y on the Live tab and Cross/Circle/Square/Triangle on Visualise in the same session — over a touchpad their hardware doesn't have. Labels, face glyphs, shoulder and trigger names and the touchpad now all follow the connected pad.
- **The Mapping tab shows what you're pressing.** The firing row lights up, and a new Live column shows the real velocity or CC value that went out — taken from the outgoing MIDI itself, so it cannot disagree with what your DAW receives. The highlight is driven by the physical control rather than the note number, so it stays correct under the shift layer and A/B compare.
- **Editing a MIDI note in the Mapping table actually saves it.** The cells have been editable since the table was written and nothing listened, so every edit was silently discarded on the next refresh while the controller kept sending the old note.
- **Press lamps on the MIDI activity panel.** Sixteen per-channel lamps in the panel header — bright for notes, dim for CCs — so you can confirm MIDI is leaving the app without expanding a scrolling text log. They work while the panel is collapsed.
- **D-pad presses show up in the MIDI activity panel.** They were sending real MIDI while appearing nowhere in the log or console; every other input type reported itself.
- **Triggers no longer collapse to zero at half-press.** Pressure was remapped only when the raw value was negative, on the theory that some platform reports triggers as 0..1 natively — none does. The result was a cliff in the middle of every stroke: CC climbed to 63 over the first half of travel, snapped to 0 at the midpoint, then climbed to 127 over the second half. This hit DualSense and Xbox alike.
- **Trigger bars stop freezing at full.** The UI throttles to 30 Hz while the poll loop runs at 100, and a sample the throttle dropped was never re-sent. A spring-loaded trigger returns to rest inside a single 33 ms window, so the meter kept painting the full-press value for the rest of the session with the pad untouched on the desk. Dropped samples are now held and flushed on the next tick.
- **Stop clears every meter.** The Split View "Live Preview" was only reset by a controller-info event that never fires on stop, so it carried pre-stop values into the next run's calibration — the other half of why triggers looked pinned during "keep your hands off the controller".
- **The axis oscilloscope draws the first half of a trigger pull.** It clamped the raw -1..+1 reading into 0..1 instead of remapping it, so the trace sat flat at zero until the midpoint.

## [2.2.0] - 2026-10-15

**First Windows bug-fix pass — console windows, frozen UI, and wrong controller labels.** Everything below came out of a Windows user's screen recording.

- **No more black console windows flashing over your DAW.** The Bluetooth tab polled `powershell.exe` every 6 seconds for the whole session, and nothing passed `CREATE_NO_WINDOW` — so Windows allocated a fresh console each time and it stole foreground focus. Every subprocess call now suppresses its console (new `proc.py`), covering the Bluetooth scan, the `ms-settings:` launcher, the `tasklist` helper check, and the Ableton/REAPER version probes.
- **The app no longer freezes every 6 seconds.** That same scan ran synchronously on the GUI thread. It now runs on the thread pool, and only while the Bluetooth tab is actually visible. This was also why clicking Mapping or Templates could appear to do nothing — the click sat queued behind a PowerShell cold start.
- **Bluetooth device count is real now.** `Get-PnpDevice -Class Bluetooth` also returns the radio, the BTHENUM/BTHLE enumerators, and one child node per advertised service, all of which were counted and reported as paired — hence "20 connected, 20 paired" on a laptop with two devices. Filtered to real `BTHENUM\\Dev_*` / `BTHLEDEVICE` peripherals and de-duplicated by MAC.
- **Latency stat is accurate.** Input timestamps were queued in a FIFO and popped one per MIDI send, but inputs that emit no MIDI (unmapped button, axis inside the deadzone, throttled CC) were never popped. The queue became a permanent backlog and each send paired with a timestamp from minutes earlier — an idle controller read `33053.4 ms`. Now a single overwrite-on-input slot, matching `latency_test.LatencyTracker`.
- **"CONSOLE" and "MIDI ACTIVITY" headers no longer clip.** Both were `setFixedHeight(36)` while the A+/A- buttons rescale the app font; at 1.4x the header needs 39px. Height is now derived from the title's font metrics.
- **New "No DAW routing" badge.** On Windows with no loopMIDI port the bridge falls back to the built-in GS Wavetable Synth — audible, but your DAW receives nothing. It said so once in a status line that the next message overwrote. Now a persistent badge with a dialog explaining the loopMIDI fix.
- **Console button pulses green / amber / red** when an unseen message lands, so an error is visible without the console open.
- **Xbox controllers are labelled correctly.** The UI hardcoded PlayStation names, so an Xbox One Controller showed Cross / Circle / Square / Triangle / Share / Options / PS — plus a touchpad it doesn't have. New `control_labels.py` owns the names: Xbox gets A/B/X/Y, LB/RB, LT/RT, View/Menu/Guide, and no touchpad.
- **Windows no longer crashes on startup when a MIDI port refuses to open.** `open_port` let rtmidi's own `SystemError` ("MidiOutWinMM::openPort: error creating Windows MM MIDI output port") escape untyped, but every caller — including the first-run wizard — only catches `MidiPortError`. A port that Windows enumerates but won't hand out (claimed by another app, or the GS synth with no usable audio device) crashed the app before the window appeared. We now try each candidate port in preference order and always raise the typed error.
- **Tray / menu bar shows live status.** The icon's menu carries a read-only block — running state, attached controller, and the MIDI port, flagged when it isn't routable to a DAW — plus Panic. The window is often minimised to the tray while bridging, so that was the one place the state wasn't visible.
- **Live view rebuilt.** Named control pills instead of anonymous numbered squares, a D-pad rail, a face-button rail, and live numeric X/Y under each stick so stick drift is visible at rest.

## [2.1.5] - 2026-06-06

**Live input now flows on macOS — visualiser, MIDI, and stats update in real time.** Bridge worker polls joystick state from its own QThread, but SDL's HIDAPI backend on macOS hooks IOHIDManager callbacks that only fire on the thread which initialised the video subsystem (the main thread). The worker's `pygame.event.pump()` therefore never serviced HID reports, so `get_axis()` / `get_button()` returned the values captured at controller-attach time forever — controller showed connected but every visualiser stayed frozen at zero and Total MIDI Messages held at 0.

The QApplication entry point now spins a 120 Hz `QTimer` on the main thread that pumps SDL events. Bridge worker behaviour unchanged.

## [2.1.4] - 2026-06-06

**Bluetooth-connected controllers now detected on macOS.** SDL2 on macOS 12+ silently fails to enumerate Bluetooth-paired DualSense + Xbox controllers under its default IOHID backend — the OS exposes them only via GameController.framework, which SDL's IOHID path doesn't follow. Enabled SDL's bundled HIDAPI backend with `SDL_JOYSTICK_HIDAPI=1` (+ per-controller hints) so pygame sees both USB and Bluetooth transports. cython-hidapi is already a hard dep so no install changes.

## [2.1.3] - 2026-06-06

**Help tab no longer crashes on macOS 26.5.** The decorative 3D logo in the Help hero (a `QWebEngineView` instance) was crashing Chromium child-process startup inside `PySide::getWrapperForQObject`, which pygame's signal parachute then turned into an `EXC_BAD_ACCESS` app crash. The 3D logo now respects the same `GMB_ENABLE_3D=1` opt-in env var that the background visualiser already uses — opt-in by default so Help is safe.

## [2.1.2] - 2026-06-06

**License activation + About-page button rendering.** Two regressions found while testing v2.1.1 end-to-end:

- **License activation now accepts standard URL-safe base64 keys.** The storefront issuer strips trailing `=` padding per RFC 4648 §5; the desktop decoder required the padding and bailed with `Incorrect padding`. Every real licence ever emailed was undecodeable. Decoder now re-adds padding before decode so both forms work.
- **About-tab button text no longer clips to a middle band.** Added explicit `min-height` to the UIButton stylesheet — Qt on macOS was otherwise letting QPushButton compress to the native ~16px button height, slicing ascenders + descenders off every label.

## [2.1.1] - 2026-06-06

**macOS Gatekeeper fix.** PyInstaller's ad-hoc signature was being invalidated by our own Info.plist patch step, which caused macOS to show "this app is damaged and can't be opened" on freshly downloaded builds. The build script now re-signs the bundle after patching, so Gatekeeper sees a valid ad-hoc seal and falls back to the standard "from an unidentified developer" prompt — users right-click → Open and they're in. No behaviour changes to the app itself.

## [2.1.0] - 2026-06-06

**Better unzip compatibility.** Refreshed macOS / Windows / Linux release bundles to use a delivery path that survives third-party download proxies and macOS Archive Utility's stricter zip validation. Customers who saw "Error 94 — Bad message" expanding the v2.0.0 macOS zip should re-download from the website.

No behavioural changes to the app itself — pure packaging + distribution fix.

## [1.0.0] - 2026-05-26

**First public release.** Turn any PS5 or Xbox controller into a cross-platform MIDI controller — calibration, mapping, marketplace, seven DAW/VJ connectors, and adaptive trigger haptics. Free tier covers live bridging end-to-end; Pro tier unlocks the editor, multi-controller, OSC, and the marketplace publisher.

### Engine
- DualSense parallel HID layer — battery, touchpad XY (both fingers), wired vs
  Bluetooth detect, adaptive trigger output (USB direct + Bluetooth via 78-byte
  `0x31` framing with IEEE 802.3 CRC32)
- macOS adaptive triggers route through Apple's `GCController` (raw HID writes
  blocked post-Catalina) — auto-detected via `pyobjc-framework-GameController`
- Stick drift auto-calibration on start + on-demand
- Stick edge quantizer — push to a corner to fire a MIDI note, 4 / 8 / 16
  sectors, hysteresis prevents chatter
- Touchpad XY → MIDI CC (Kaoss Pad-style modulator), plus two-finger mode
- Multi-controller orchestrator — daisy-chain two pads on separate MIDI
  channels + virtual ports (Pro)
- OSC 1.0 UDP backend — runs alongside or in place of MIDI, per-control
  address mapping

### Host connectors (seven shipped)
- **Resolume Arena** — XML map writer, schema verified against four factory
  presets
- **Ableton Live 11+** — Python 3 Remote Script, installs into User Library
- **TouchDesigner 2022+** — JSON descriptor for the MIDI Mapper palette
- **VDMX** — programmatic plist template
- **MadMapper 5+** — XML device descriptor
- **REAPER** — `.ReaperKeyMap` plain-text file
- **OBS Studio** — Python helper script using obs-websocket v5

### App
- PySide6 GUI, eight tabs: Live, Mapping, Presets, Marketplace, Connectors,
  Settings, Help, About
- First-launch onboarding wizard (controller detect → MIDI test →
  connector picker → calibration)
- System tray / menu bar icon with start/stop/show/quit
- Auto-update banner (silent on failure, opt-out in Settings)
- Demo mode (`--demo` flag or `GMB_DEMO=1` env var) — synthetic controller
  for CI, demo videos, and DAW testing with no hardware
- Crash reporter (writes to `user_data_dir/crashes/`, never phones home)
- Rotating log file at `user_data_dir/logs/app.log`
- MIDI throughput readout in status bar (N/s rounded)
- Headless mode (`--headless`) for kiosks and performance rigs
- CLI flags: `--version`, `--reset-config`, `--export-pack`,
  `--import-pack`, `--log-path`, `--debug`, `--demo`
- `gmb://` URL scheme — one-click license activation + preset import
- Last-mapping autosave (persists across launches and into headless mode)
- Portable config bundles (`.gmbpack`) — mapping + presets + license in
  a single zip
- Global Ctrl/Cmd+Enter toggles the bridge from any tab
- 4 starter presets bundled and seeded on first launch

### Marketplace + store
- In-app Marketplace tab — browse + install presets shared by other users
- Supabase schema with RLS, trusted-author auto-approve, full-text search
- 8 seed presets ready to ingest on day one
- Astro store site at `midi.aidxn.com` — landing, recovery, success,
  privacy, terms, admin dashboard, OG image generator
- Stripe Checkout → Netlify Function → Ed25519-signed license email via
  Resend; idempotent on webhook retries, enumeration-safe recovery
- Admin dashboard at `/admin/dashboard?key=ADMIN_TOKEN` — DAU,
  connector install rates, onboarding funnel

### Quality
- 47 pytest tests covering pure-logic modules
- GitHub Actions CI: test on push (mac/Linux/Windows), lint on PR,
  build artifacts on tag (`v*.*.*`) attached to a GitHub Release
- Dependabot weekly
- Privacy posture: opt-in telemetry, server-side identity stripping,
  90-day retention plan documented

### Brand
- Original SVG icon (analog stick + travel envelope + radial MIDI ticks)
- Full ICNS / ICO / 7 PNG sizes / favicon SVG
- 8 dark-theme tab screenshots in `docs/screenshots/`

### Notes
- License keys verify offline via Ed25519. Issuer keys live in Netlify env
  vars only — never in the repo or the desktop bundle.
- macOS bow / galloping / machine adaptive-trigger effects fall back to
  "off" (Sony libpad SDK only, not in Apple's framework). USB Win+Linux
  gets all seven.
- Ableton connector targets Live 11+ only (Python 3 mandatory).
- Xbox impulse-trigger haptics deferred to V2 (no Python binding for
  Windows.Gaming.Input).
