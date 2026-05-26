# Universal Controller MIDI — Ableton Live Remote Script

Wires the default Universal Controller MIDI MIDI map to native Live controls. No
MIDI-learn needed — clip launch, scene nav, mixer, transport all light up the
moment the surface is selected.

## Live version

Live 11+ only. Python 3.

## Default bindings (MIDI channel 1)

| Controller            | MIDI                       | Live action                           |
|-----------------------|----------------------------|---------------------------------------|
| Face buttons (×6)     | Notes 60, 62, 64, 65, 67, 69 | Launch clip slot — tracks 1-6, scene 1 |
| D-pad up/down         | Notes 78 / 79              | Scene bank up / down                  |
| D-pad left/right      | Notes 80 / 81              | Fire previous / next scene            |
| Left stick X/Y        | CC 3 / 4                   | Volume tracks 1 / 2                   |
| Right stick X/Y       | CC 5 / 6                   | Volume tracks 3 / 4                   |
| L2 trigger            | CC 1                       | Master volume                         |
| R2 trigger            | CC 2                       | Crossfader                            |
| Button 6 / 7          | Notes 71 / 72              | Play / Stop                           |
| Button 8 / 9 / 10     | Notes 74 / 76 / 77         | Loop / Metronome / Record             |

## Install

Use the **Connectors** tab in Universal Controller MIDI → click **Install** next to
Ableton Live. The connector copies this folder to:

- macOS: `~/Music/Ableton/User Library/Remote Scripts/Universal Controller MIDI/`
- Windows: `~/Documents/Ableton/User Library/Remote Scripts/Universal Controller MIDI/`

Then in Live:

1. Restart Ableton Live (or quit and reopen).
2. Preferences → Link, Tempo & MIDI → Control Surface dropdown → pick **Universal Controller MIDI**.
3. Set **Input** to the bridge's virtual MIDI port. Output not required.
4. Save the Live set so the Control Surface assignment persists.

## License & redistribution

This Remote Script imports `_Framework` from Ableton's bundled runtime — we do
not ship `_Framework` source. That's the same model every official partner
(Akai, Novation, NI, M-Audio) uses for their Live integrations.
