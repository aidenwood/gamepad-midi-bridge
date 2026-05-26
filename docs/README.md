# Universal Controller MIDI — Documentation

Turn a PS5 DualSense or Xbox controller into a MIDI / OSC controller for VJ rigs, DAWs, and live performance.

This folder is the source of truth for everything you can't see by clicking around the app. Plain markdown, no build step, cross-linked below.

## For users

- **[User manual](./user-manual.md)** — Quick start, calibration, default mapping, Pro features (corner buttons, touchpad XY, adaptive triggers), host connectors, OSC, multi-controller, presets, headless mode, troubleshooting, privacy.

## For developers

- **[Architecture](./architecture.md)** — Module map, threading model, mapping schema versioning, connector framework, licensing internals, on-disk state layout.
- **[Contributing](./contributing.md)** — Setup, tests, lint, style rules, how to add a new host connector, PR checklist, branching policy.

## For maintainers

- **[Release checklist](./release-checklist.md)** — Version bump, changelog, tag, CI artefacts, store + blog updates.

## Where things live

- App code — [`src/gamepad_midi_bridge/`](../src/gamepad_midi_bridge/)
- Changelog — [`CHANGELOG.md`](../CHANGELOG.md)
- Build configs — [`build/`](../build/)
- Issuer scripts — [`scripts/`](../scripts/)
- Store + landing page — separate repo at `PS5-MIDI-Bridge-Store/`
