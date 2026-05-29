# Feature Brainstorm — 25 next-up ideas

Drafted 2026-05-30 during autonomous loop. Sister doc to `TELEMETRY_PLAN.md`.
Each entry has: title, one-line value, ~3 implementation notes, rough effort
(S/M/L), feature category (mapping / stage / workflow / hardware / midi / privacy).

Order is rough priority — top of each section first. Pick what excites you;
none of these are blocked on anything shipped.

---

## 1. Per-button modifier gate (extend the trigger gate pattern)
- Value: any face button can become a "hold to enable" mod, not just dpad-for-triggers.
- Notes: extend `ButtonConfig` (new dataclass) with `gate_button: Optional[int]`. Reuse `shaping.gate_decision`. Same semantics as trigger gate.
- Effort: S. Category: mapping.

## 2. Shift-layer mappings (Pro)
- Value: doubles the mappable surface — hold any button = whole different note/CC set.
- Notes: `Mapping.shift_button: Optional[int]`. When held, overlay an alt `axes`/`buttons` dict. UI: tabbed mapping editor "Default | Shift".
- Effort: M. Category: mapping.

## 3. Per-mapping channel override
- Value: route different buttons/sticks to different MIDI channels in one preset.
- Notes: `channel: Optional[int]` per ButtonConfig/StickConfig — falls back to global.
- Effort: S. Category: midi.

## 4. Visual mapping "press to capture" wizard
- Value: click a row, app waits for next controller press, auto-fills the index.
- Notes: new dialog in `mapping_editor.py`. Modal blocks input, listens to `BridgeWorker.button_state`, captures first non-zero.
- Effort: M. Category: workflow.

## 5. Curve-amount live preview in mapping editor
- Value: sliders for inner_deadzone/outer_clamp/curve_amount show a tiny sparkline of the resulting response.
- Notes: QPainter-drawn 80x40 widget. Re-renders on slider change. Uses existing `shaping.apply_stick_shape`.
- Effort: M. Category: mapping.

## 6. MIDI feedback loop guard
- Value: detect if a CC the app emits is also being routed back IN (causes runaway).
- Notes: track recent outbound CCs (per channel, per CC, last 50ms). Drop inbound matches. Log warning.
- Effort: S. Category: midi.

## 7. Preset A/B compare button
- Value: while playing live, hold Tab key (or pad button) to swap to a B preset, release to revert.
- Notes: `Mapping.b_overlay: Optional[Mapping]`. Swap the active mapping reference on key state. Global shortcut.
- Effort: M. Category: stage.

## 8. Touchpad gesture macros
- Value: swipe up = play, swipe down = stop, two-finger pinch = panic note-off.
- Notes: detect movement direction + magnitude from touchpad XY deltas. Threshold-driven. Configurable per gesture.
- Effort: M. Category: hardware.

## 9. Multi-zone touchpad (4-quadrant pads)
- Value: divide touchpad into 4/8 zones, each fires a different note like an MPC pad.
- Notes: extend `TouchpadConfig` with `zone_mode` + `zone_notes: List[int]`. Hysteresis to avoid edge chatter.
- Effort: M. Category: hardware.

## 10. Adaptive trigger "tactile click" at threshold
- Value: trigger gives a haptic click at the latch threshold so user feels exactly where it fires.
- Notes: when `mode="latch"`, fire a `"feedback"` haptic effect at threshold. Bypassable.
- Effort: S. Category: hardware.

## 11. Stick rumble on edge-quantize fire
- Value: confirmation haptic when the user pushes a stick into a quantized corner.
- Notes: hook into `corner_triggered` signal. Fire short trigger vibration on the SAME side's trigger.
- Effort: S. Category: hardware.

## 12. Headless live-rig mode in tray menu
- Value: minimise to tray, app runs forever, no main window — for stage rigs.
- Notes: `--background` CLI flag. Tray icon already exists. Disable Live tab updates while hidden to save battery.
- Effort: S. Category: stage.

## 13. Battery-low MIDI alert
- Value: emit a configurable note/CC when DualSense battery drops below 15%.
- Notes: hook `battery_changed` signal. Send once per threshold crossing. Configurable in Settings.
- Effort: S. Category: stage.

## 14. Auto-reconnect with countdown
- Value: when controller drops mid-set, app shows a 10s countdown + auto-retries; flashes "RECONNECTED" big.
- Notes: detect `controller_info(None)` after start. QTimer 1s ticks. Re-init bridge on success.
- Effort: M. Category: stage.

## 15. Preset hot-swap via MIDI Program Change
- Value: send PC#0 from your DAW → preset 0 loads. PC#1 → preset 1. Lets the DAW drive the controller config.
- Notes: `HapticInputConfig`-style binding. Listen on a config'd channel for PC messages. Map to preset slugs.
- Effort: M. Category: stage.

## 16. OSC bidirectional (incoming OSC → haptics)
- Value: TouchDesigner sends OSC back → trigger rumble pulses.
- Notes: extend `OscConfig` with `listen_port`. Bind paths to haptic effects like the existing MIDI input bindings.
- Effort: M. Category: midi.

## 17. Marketplace preset preview in-app
- Value: hover a preset card, see its mapping graph (axes → CCs, buttons → notes) before installing.
- Notes: SVG renderer in marketplace tab. Read `json_blob`, draw the connection diagram. Static is fine.
- Effort: M. Category: workflow.

## 18. Inspector wiring for Marketplace + Live tabs
- Value: click any marketplace card or live axis → inspector shows full details.
- Notes: emit `selection_changed` signal from each tab matching the mapping editor pattern. Register a renderer per tab in `main_window`.
- Effort: S each. Category: workflow.

## 19. Mapping diff between two presets
- Value: pick preset A + B, see a side-by-side "what's different" view.
- Notes: pure-python diff over the `Mapping.to_dict()` shape. Render as a side panel widget.
- Effort: M. Category: workflow.

## 20. Export mapping as printable cheat sheet (PDF)
- Value: print a card showing what every button/stick does for your current preset — for the gig bag.
- Notes: reportlab or QPagedPaintDevice. One A5 page. Visual diagram of controller with labels.
- Effort: M. Category: workflow.

## 21. Per-axis input visualiser tab
- Value: oscilloscope strip per axis showing the last 5s of values — debug stick drift, see CCs in real time.
- Notes: extend existing `visualise_tab.py`. Ring-buffer of (timestamp, value). QPainter draw.
- Effort: M. Category: workflow.

## 22. Crash report bundle export
- Value: one-click "export the last crash + logs + config" to a zip the user emails support.
- Notes: `crash_reporter.py` already writes to disk. Add `export_bundle()` that zips crashes/ + last 1MB of logs + sanitised config.
- Effort: S. Category: privacy.

## 23. Per-preset MIDI port name
- Value: each preset can open a uniquely-named virtual port (e.g. "DualSense — Ableton", "DualSense — Resolume") so you can route them differently in your DAW.
- Notes: `Mapping.midi_port_name: Optional[str]`. Falls back to default. Bridge spins up a new port when the preset loads.
- Effort: M. Category: midi.

## 24. Scale-quantize mode for stick-as-note
- Value: stick magnitude maps to a note from a chosen scale instead of raw chromatic — instant musical scales.
- Notes: `scale: str` (e.g. "major", "minor", "dorian"), `root_note: int`. Apply in shaping after corner detect.
- Effort: M. Category: midi.

## 25. Preset auto-backup to local disk
- Value: app saves a timestamped copy of the active mapping every 60s. Never lose live edits.
- Notes: QTimer in MainWindow. Write to `~/.config/gamepad-midi-bridge/autosaves/YYYY-MM-DD-HHMM.json`. Keep last 30, prune older.
- Effort: S. Category: workflow.

---

## Suggested first batch (next sprint)

If picking 5 to ship together, I'd do **1, 4, 12, 14, 25** — all small-to-medium, all visibly improve the stage-performance experience without needing new UI sub-systems.

If picking 5 that show off the product, I'd do **2 (shift layer), 7 (A/B compare), 8 (touchpad gestures), 15 (PC preset hot-swap), 20 (printable cheat sheet)** — these are the "wow that's cool" demos for marketing clips.
