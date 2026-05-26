# Changelog

All notable changes land here. Versions follow semver: `MAJOR.MINOR.PATCH`.

## [Unreleased]

Engine, GUI, and ecosystem features built ahead of the first public release.

### Added

**Engine**
- DualSense parallel HID layer (battery, touchpad, wired/BT detect, adaptive triggers)
- Stick drift auto-calibration with hysteresis
- Stick edge quantizer — push to a corner to fire a MIDI note (4 / 8 / 16 sectors)
- Touchpad XY → MIDI CC (Kaoss Pad-style modulator)
- Adaptive trigger haptics — seven effects (off, feedback, weapon, vibration, bow, galloping, machine), USB on Win/Linux + Bluetooth via CRC32 framing + macOS via PyObjC GCController
- Multi-controller support (Pro) — second controller on its own MIDI channel + virtual port
- OSC output backend (UDP, OSC 1.0) — alternative to MIDI for Resolume / TouchDesigner / MadMapper

**Host connectors**
- Resolume Arena (XML map writer, verified against four factory presets)
- Ableton Live 11+ (Python 3 Remote Script)
- TouchDesigner 2022+
- VDMX (programmatic plist template)
- MadMapper 5+
- REAPER (`.ReaperKeyMap` plain text)

**App**
- PySide6 GUI with seven tabs (Live, Mapping, Presets, Marketplace, Connectors, Settings, About)
- First-launch onboarding wizard (controller detect → MIDI test → connector picker → calibration)
- System tray / menu bar icon with start/stop/show/quit
- Global Ctrl/Cmd+Enter to toggle bridging from any tab
- Auto-update banner (silent on failure, opt-out in Settings)
- Crash reporter (writes to `user_data_dir/crashes/`, never phones home)
- Structured logging to `user_data_dir/logs/app.log` (rotated 2MB × 3)
- Headless mode (`--headless`) for kiosks and performance rigs
- CLI flags: `--version`, `--reset-config`, `--export-pack`, `--import-pack`, `--log-path`, `--debug`
- `gmb://` URL scheme for one-click license activation + preset import
- Last-mapping autosave (persists across launches and into headless mode)
- Portable config bundles (`.gmbpack`) — mapping + presets + license in one file

**Marketplace + store**
- In-app Marketplace tab — browse + install presets shared by other users
- Supabase schema with RLS, trusted-author auto-approve, full-text search
- Store at `store.aidxn.com` — landing, recovery, success, privacy, terms
- Stripe Checkout → Netlify Function → Ed25519-signed license email via Resend
- Admin dashboard at `/admin/dashboard?key=...` with daily-active / connector / onboarding views

**Privacy**
- Anonymous usage stats opt-in (default off)
- Update check opt-in (default on, easy toggle in Settings)
- Telemetry receiver strips identifying fields server-side as belt-and-braces

### Notes

- License keys verify offline via Ed25519. Issuer keys live in Netlify env vars only.
- macOS adaptive triggers route through `GCController` because Apple blocks raw HID writes post-Catalina.
- Bow / Galloping / Machine effects fall back to "off" on macOS (require Sony's libpad SDK, not in Apple's framework).
- Ableton connector targets Live 11+ only (Python 3 mandatory; Live 10 used Python 2).
