# PS5 MIDI Bridge — Project Context

PS5 DualSense / Xbox controller → MIDI bridge. Cross-platform desktop app (macOS / Windows / Linux). Free tier + Pro tier (Ed25519-signed offline licence). Sold via `midi.aidxn.com` (Stripe → Netlify Function → Resend).

## Stack one-liner

Python 3.9+ · PySide6 / Qt6 · pygame-ce (SDL2 input) · python-rtmidi · cython-hidapi · cryptography · PyInstaller packaging · Supabase telemetry (anon-key reads, migrations live in the Store repo) · proprietary licence.

## Commands

- `pip install -e ".[dev,build]"` — dev install (use venv, never npx, this is Python).
- `gamepad-midi-bridge` — launch GUI.
- `gamepad-midi-bridge --headless` — no GUI, kiosk / touring mode.
- `gamepad-midi-bridge --demo|--keyboard|--mouse` — hardware-free input.
- `python build.py` — PyInstaller bundle for the current OS into `dist/`.
- `pytest` — full test suite (47+ tests).
- `ruff check .` — lint.

## Halls (load on demand)

Each hall = one domain. Open the hall you're working in; rooms inside are scoped rules with canonical snippets from this codebase.

- [general-app-design](halls/general-app-design.md) — Qt startup, BridgeWorker engine, logging, settings, demo input (keyboard/mouse). Load when: touching `__main__.py`, `app.py`, `bridge.py`, `logger.py`, `paths.py`, demo controllers, packaging.
- [controller-input](halls/controller-input.md) — sticks, triggers, aftertouch, IMU, haptics, Bluetooth, cross-platform quirks. Load when: editing anything under `stick_*`, `trigger_*`, `aftertouch_*`, `dualsense.py`, `mac_haptics.py`, `bluetooth.py`, `imu_helper.py`, `calibration.py`.
- [midi-protocol-and-routing](halls/midi-protocol-and-routing.md) — ports, message types, SysEx, transport/clock, routing matrix, OSC, RTP-MIDI, MIDI Learn, MIDI 2.0 UMP, connector auto-installers. Load when: editing anything under `midi_*`, `osc_backend.py`, `rtp_midi.py`, `sysex_*`, `routing_matrix.py`, `connectors/`.
- [mapping-and-presets](halls/mapping-and-presets.md) — mapping schema v4, validation, diff/merge/clone/mirror, fingerprint, presets, snapshots, autobackup, banks, favourites, `.gmbpack` portable bundles. Load when: editing anything under `mapping_*`, `presets.py`, `snapshots.py`, `portable.py`, `autobackup.py`, `templates.py`, `setlist_*`.
- [generative-music-theory](halls/generative-music-theory.md) — scales, chords, quantize, rhythm/groove, LFOs, glide, sequencing, macros, pad layout, multi-controller. Load when: editing anything under `scales.py`, `chord_*`, `note_*`, `euclidean.py`, `polyrhythm.py`, `groove_*`, `quantize_*`, `lfo_*`, `glide.py`, `tap_delay.py`, `pattern.py`, `preset_chain.py`, `preset_blend.py`, `macro_library.py`, `pad_layout.py`, `multi.py`.
- [analytics-telemetry-licensing](halls/analytics-telemetry-licensing.md) — licence gating, telemetry, note/velocity/control analytics, latency, battery, DAW detection, updater, crash reporter. Load when: editing `license.py`, `telemetry.py`, `updater.py`, `crash_reporter.py`, anything under `note_*` analytics, `velocity_histogram.py`, `control_heatmap.py`, `battery_history.py`, `latency_*`, `performance_stats.py`, `daw_detector.py`, `usage_stats.py`, `color_helpers.py`, `audio_reactive_sim.py`.

## Project-wide rules

- Never `npx` — Python project, use `pip install` / venv.
- PyInstaller spec: `Universal Controller MIDI.spec` is canonical. `Gamepad MIDI Bridge.spec` is the OLD name and slated for deletion — do not edit it.
- Supabase migrations live in the **Store repo only** (`PS5-MIDI-Bridge-Store/supabase/migrations/`). Desktop reads with the public anon key — never write schema from here.
- License `PUBLIC_KEY_PEM` in `src/gamepad_midi_bridge/license.py` is the PRODUCTION Ed25519 key — matches `scripts/public_key.pem`. The matching private key lives in the storefront's Netlify env (`LICENSE_PRIV_KEY_V1`) and must never enter this repo.
- Telemetry endpoint `https://midi.aidxn.com/api/telemetry` is hardcoded (`telemetry.py:32`) and is NOT yet live. No env-var override yet — wiring deferred.
- BridgeWorker poll loop is hot — heavy work goes in slots on the GUI thread, never inside `_loop`.
- Pure-stdlib analysis modules stay pure: no Qt imports, no hardware reads, caller supplies floats.
