# Changelog

Versions follow semver: `MAJOR.MINOR.PATCH`.

## [Unreleased]

(Nothing yet.)

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
