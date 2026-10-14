# Origin — the script this app grew from

`ps5_calibrated_bridge.py` is the original single-file prototype that
Universal Controller MIDI is based on. Kept here as the canonical "inspo" /
reference, not as runnable code (the shipping app supersedes all of it).

## What it did (the whole pipeline in ~380 lines)

1. **Auto-launched the helper apps** (`ensure_running`) — checked `tasklist`
   for DS4Windows + loopMIDI, `Popen`'d the `.exe` if not running, waited N
   seconds, re-checked. This is the piece worth reviving — see
   `../../BUNDLED_DRIVER_JOB.md` and `src/gamepad_midi_bridge/windows_sidecar.py`.
2. **Read the pad via pygame/SDL** — `joystick.get_axis/get_button/get_hat`.
   Same input layer the app still uses (`controller.py`).
3. **Stick-drift auto-calibration** — sampled sticks at rest for ~1s, subtracted
   the offset. Now `stick_calibration.py` + `BridgeWorker._run_calibration`.
4. **Sent MIDI via python-rtmidi** to the `ps5-bridge` loopMIDI port — buttons →
   notes, 6 axes → CC, d-pad → notes. Now the full mapping engine.

## What the app does that this never did

The prototype only touched buttons + 6 axes + d-pad over SDL. The app adds the
**raw-HID layer** (`dualsense.py`) for everything SDL can't see — adaptive
triggers, touchpad, gyro/IMU, battery, haptics — plus mapping schema v4,
presets, scales/chords, OSC, RTP-MIDI, multi-controller, and licensing.

So the app already "connects MORE of the controller" than this script. The only
genuinely reusable idea here is the **helper-app auto-launch** (open loopMIDI /
DS4Windows), which is why it's preserved.

## `ps5_midi_quick_reference.html` — the on-site field manual

Single-file HTML manual for the real touring rig:
`DualSense → BT dongle → DS4Windows → ps5_bridge.py → loopMIDI "ps5-bridge" → Resolume Arena`.
Cold-start order, 30-second sanity test, troubleshooting, emergency recovery,
latency table, and the full default button→note / axis→CC mapping.

Actionable ideas it surfaces for the app:

1. **DS4Windows is legitimately wanted for the VJ/Resolume use case.** This rig
   *depends* on it (controller presents as Xbox 360 via XInput). That refines the
   `launch_ds4windows` default-off call in `windows_sidecar.py`: off is right for
   music-production users who want raw-HID DualSense features (adaptive triggers,
   touchpad, gyro), but **VJ/show-control users should turn it on** — they don't
   use those features and DS4Windows makes sticks/buttons rock-solid. Worth a
   one-line "VJ / Resolume" hint next to the setting.
2. **Two-script workflow → a "mapping mode" toggle.** The rig kept a second script
   with sticks disabled so stick-drift CC couldn't hijack a DAW/Resolume MIDI-learn
   bind. The app solves drift via calibration, but a **"freeze sticks while
   mapping"** toggle would kill this class of bug outright. (See FEATURE_BRAINSTORM.)
3. **The default mapping table is a ready-made "Resolume VJ" preset** — buttons
   60–77, L2/R2 → CC 1/2, d-pad → 78–81. Could seed a first-party preset.
4. **Troubleshooting recipes** (Steam exclusive-mode grab, ViGEmBus/HidHide,
   stuck notes → panic/all-notes-off, BT range/latency) are field-tested support
   content for the store Windows docs and the in-app help tab.
