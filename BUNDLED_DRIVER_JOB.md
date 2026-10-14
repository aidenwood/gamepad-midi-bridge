# Job: Bundle our own virtual MIDI driver on Windows

**Created 2026-06-17. Start: later today.** Owner: Aiden.

## Why

Windows has no kernel virtual-MIDI port. Today the app's Windows path
(`src/gamepad_midi_bridge/midi_backend.py`) does a tiered fallback:

1. Auto-detect an existing **loopMIDI** port (any port whose name contains
   `loopmidi`, or our `Universal Controller MIDI` / legacy `ps5-bridge` name).
2. Else play through the **built-in GS Wavetable synth** so notes are audible
   instantly with zero install.
3. Else any available output port; error only if there are none.

That's the "instant working" interim. The end goal: **the installer bundles a
signed virtual-MIDI driver and the app creates its own routable port at launch**
— no loopMIDI download, matching what `midi.aidxn.com/docs/installation/
virtual-port-windows` already (prematurely) advertises.

## RECOMMENDED near-term path — first-run setup assistant (not a kernel driver)

Aiden's call (2026-06-17): rather than license/sign a kernel driver, ship a
**requirements checker + a "Set up Windows MIDI" button that launches a
PowerShell script in its own window**. Revives the earlier loopMIDI + DS4Windows
PowerShell script Aiden already wrote, but driven from the app so less-techy
users never touch a terminal manually. The app opens → checks requirements →
one click runs setup → re-checks → green.

Wired up 2026-06-17: the script lives at
`src/gamepad_midi_bridge/resources/windows/setup-midi.ps1` (bundled via the
existing `--add-data RESOURCES` rule) and the onboarding MIDI step has a
**"Set up Windows MIDI for me"** button (`ui/onboarding.py → _run_windows_setup`)
that launches it in its own console. Still needs a Windows test pass.

What the script does:
1. Detect loopMIDI; if missing, **download from the official URL and silent-install**
   (`/VERYSILENT /NORESTART`). Downloading at runtime means we never redistribute
   loopMIDI — sidesteps its licensing entirely.
2. Ensure a loopMIDI port named `Universal Controller MIDI` exists (seed
   loopMIDI's config + add to startup), so the app's tier-1 auto-detect routes to it.
3. (Optional) detect DS4Windows for DualSense-over-Bluetooth users and point them at it.
4. Re-run checks and report PASS/FAIL per item.

Caveats to handle when building:
- **Execution policy / SmartScreen.** Launch via
  `powershell.exe -ExecutionPolicy Bypass -NoProfile -File <script>`. Signing the
  script (or the app signing cert) cuts the warning. Installing loopMIDI needs
  **elevation** — relaunch the script `-Verb RunAs` for the install step only.
- **loopMIDI port creation has no clean CLI.** Pre-seed `%APPDATA%\loopMIDI`
  config or drive the tray app; verify the exact mechanism on a real Windows box.
- **Can't be verified from macOS.** Needs a Windows test pass before shipping.

This is L-effort but unblocked (no licence conversation). The kernel-driver
options below stay as the longer-term "zero-dependency" goal.

## Longer-term — which bundled driver (if we ever go kernel-level)

- **teVirtualMIDI SDK** (Tobias Erichsen, same driver behind loopMIDI/rtpMIDI).
  Signed, multi-client, proven across every Windows DAW. **Commercial
  redistribution requires a paid licence agreement with Tobias** — this is the
  gating item. Email him, get terms, before writing integration code.
- **loopMIDI silent install** — bundle the loopMIDI installer and run it silently
  on first launch. Lower-effort, but still ships loopMIDI's UX/branding and has
  its own redistribution terms to confirm.
- **Windows MIDI Services (WinMIDI 2.0)** — Microsoft's native app-to-app stack.
  Future-proof, no third-party licence, but still preview on Win11 24H2 / not GA.
  Not viable as the only path yet.

Recommendation: pursue the teVirtualMIDI licence (best UX, what the docs claim);
keep WinMIDI 2.0 as the eventual replacement once GA.

## Integration sketch (once licensed)

- Ship `teVirtualMIDIx64.dll` + the signed `.inf`/driver in the PyInstaller
  bundle (`Universal Controller MIDI.spec` → add to `--add-binary` / datas) and
  register it via the installer (`pnputil /add-driver … /install`, elevated).
- New `midi_backend` Windows branch: bind the teVirtualMIDI DLL via `ctypes`,
  call `virtualMIDICreatePortEx2` to create a port named `DEFAULT_PORT_NAME` at
  startup. Insert it as **tier 0** (above loopMIDI auto-detect); keep loopMIDI →
  GS Wavetable as fallbacks if driver create fails.
- Installer must auto-elevate for driver setup (already claimed in store copy).
- EDR/Defender ASR can quarantine driver installs — surface a clear retry path
  (the store troubleshooting section already documents this flow).

## When this ships, reconcile the store

`virtual-port-windows.astro` and `downloads.astro` currently describe the bundled
driver as if it already exists. Once real:
- Remove the "+ loopMIDI download opens in a new tab" auto-open on the Windows
  download button (`downloads.astro`), or downgrade loopMIDI to optional.
- The fabricated PowerShell/registry/`pnputil` sections become accurate — verify
  paths against the real install location before trusting them.

## Hardening pass (2026-06-17) — what's done, what a Windows box must verify

The setup-assistant was hardened to its practical ceiling from a Mac:
- **Install** (`Install-LoopMidi`) now degrades gracefully — any download/extract/
  install failure opens the official loopMIDI page instead of crashing, and the
  main flow re-checks `Test-LoopMidiInstalled` rather than assuming success.
- **Port** (`New-LoopMidiPort`) no longer pokes the undocumented registry. It just
  launches loopMIDI and re-enumerates — because the app already auto-detects ANY
  loopMIDI port (matches `loopmidi` in the device name), so loopMIDI's default
  port "just works"; if a build starts portless, the user adds one port (any
  name) in ~5 s and re-checks.

**Still needs a real Windows box (cannot be done from macOS — no `pwsh`):**
1. Pin `LoopMidiUrl` to a current versioned zip on tobias-erichsen.de and confirm it downloads.
2. Confirm the Inno Setup silent switches (`/VERYSILENT /NORESTART /SUPPRESSMSGBOXES`) install without prompts (UAC aside).
3. Confirm a fresh loopMIDI launch exposes a port the app's `Test-PortExists` / `open_port` sees.
4. Confirm the onboarding "Set up Windows MIDI for me" button launches the script with its own console + the Re-check loop closes the flow.

## Effort

L. Blocked on the licence conversation (for a true bundled driver) and on a
Windows test pass (for the loopMIDI auto-install) — not on more Mac-side code.
