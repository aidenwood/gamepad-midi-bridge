# 90-second product demo script

Aim: someone with no audio/VJ background grasps why this exists by the end. No
voiceover required — text overlays + screen + controller cam.

## Setup
- DualSense plugged in over USB
- Ableton Live + Resolume both open
- Bridge running, with the "Resolume default" preset loaded
- Camera angle: dim teal room light, controller in foreground, monitor reflection in lens

## Shot list

### 00:00 – 00:08 — Hook
- Camera holds on the DualSense in your hands
- Overlay: **"Your gamepad is already a MIDI controller."**
- One face-button press → an Ableton clip launches on screen
- Overlay (fade): **"It just didn't know it yet."**

### 00:08 – 00:20 — The two-second setup
- Cut to the app's first-run wizard (record fresh: `gamepad-midi-bridge --reset-config`)
- Quick montage: controller detected → MIDI port live → connector picker → calibration → "You're ready"
- Overlay: **"Three minutes. No drivers."**

### 00:20 – 00:35 — The flex
- Cut to Resolume, full-screen visual
- Push the left stick in a slow circle → layer transform XY moves with it
- Squeeze L2 → master speed warps
- Tap face buttons → clips on layer 1 fire
- Push the left stick **all the way to a corner** → drum hit (8-corner mode)
- Overlay: **"Sticks become buttons. Triggers become faders. Touchpad becomes a Kaoss Pad."**

### 00:35 – 00:50 — The Pro magic
- Cut to Ableton drum rack
- Two-finger glide on the DualSense touchpad → filter cutoff + resonance sweep
- L2 trigger: adaptive haptic kicks in as the build climbs (vibration effect)
- Drop hits, R2 trigger resists like a weapon trigger
- Overlay: **"Adaptive triggers, touchpad XY, edge buttons, multi-controller — Pro."**

### 00:50 – 01:10 — Why it's not janky
- Quick cut sequence:
  - Status bar showing "**142/s**" MIDI throughput while sticks move
  - Connectors tab with green ticks next to Resolume + Ableton + REAPER
  - Marketplace tab with the 8 seed presets visible
- Overlay: **"Cross-platform. Offline-first. Built for live."**

### 01:10 – 01:25 — Brand close
- Hard cut to the app icon on a clean dark background
- Wordmark fade in: **GAMEPAD → MIDI BRIDGE**
- Beneath: **"$49 one-time. Free tier with no time limit."**
- URL: **midi.aidxn.com**

### 01:25 – 01:30 — Tag
- 1-second card: **"by Aidxn Design"** (teal on dark)

## Music
- Sub-bass + reverbed snare 110 BPM works. Avoid copyrighted stems.
- Cue swap on the 00:35 mark (the Pro magic section) so the audio reflects the energy shift.

## Captions / accessibility
- Open captions on every overlay (don't trust YouTube auto-caption for product names)
- Alt-text for the thumbnail: "DualSense controller wired to Ableton Live and Resolume"

## Distribution checklist
- 16:9 master at 1080p60 for YouTube + store landing
- 9:16 60-second cutdown for Reels/TikTok (drop the second Pro segment + the comparison)
- 1:1 30-second silent cut for the in-app first-run wizard (autoplay-safe)
- Upload to YouTube → grab the unlisted embed ID → replace `PLACEHOLDER_VIDEO_ID`
  in `PS5-MIDI-Bridge-Store/src/pages/index.astro` (4 occurrences)
