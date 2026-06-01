# Security policy

## Reporting a vulnerability

Email **security@aidxn.com** with:
- A clear description of the issue
- Steps to reproduce, or a proof of concept
- Affected version (you can find it via the app's About tab or `gamepad-midi-bridge --version`)
- Your name and how you'd like to be credited (optional)

We'll acknowledge within **3 business days** and target a fix within **14 days** for critical issues. Coordinated disclosure preferred — please don't publish before we've shipped a fix.

Do NOT open a public GitHub issue for security reports.

## Scope

In scope:
- The desktop app (`gamepad-midi-bridge`) on macOS, Windows, Linux
- The store site at `midi.aidxn.com`
- The Netlify Functions: `stripe-webhook`, `resend-license`, `telemetry`, `presets-list`, `preset-get`
- The Ed25519 license verifier in `src/gamepad_midi_bridge/license.py`

Out of scope:
- Vulnerabilities in upstream dependencies (please report to that project)
- Issues that require physical access to the user's machine
- DAW or VJ host application bugs (Resolume, Ableton, etc.)
- The macOS Gatekeeper "Open Anyway" first-launch flow — that's expected until we ship codesigning
- Social engineering, spam, denial-of-service via marketplace uploads (rate-limited and reviewed)

## Hall of fame

Reporters credited here once a fix has shipped. (Empty so far — be the first.)

## Cryptographic posture

- License keys: Ed25519 signature over a JSON payload, verified offline
- Private signing key: held only in Netlify environment variables, scoped to one site, never in the repo
- Public key: embedded in `license.py`, rotated via key versioning (`keyVersion` field on each blob)
- License key rotation policy: documented in `docs/release-checklist.md`

## Privacy

The desktop app does not transmit any data by default. Telemetry is opt-in, identity-stripped server-side, and never includes mapping or preset contents. Full policy at `midi.aidxn.com/privacy`.
