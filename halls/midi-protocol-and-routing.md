# Hall: MIDI Protocol & Routing

Everything wire-protocol: virtual port I/O, message types + SysEx, transport / clock, mute / solo / routing matrix, CC features, stuck-note safety, the activity log, OSC + RTP-MIDI, MIDI Learn, and the per-host connector auto-installers. Modules here are mostly pure-stdlib helpers around python-rtmidi; the bridge integrates them in `bridge.py`.

### Port & I/O Backend

`midi_backend.py` owns the OUT port. `midi_input.py` mirrors it for IN. Both wrap python-rtmidi and abstract over the macOS/Linux (true virtual port) vs Windows (loopMIDI attach by name) difference.

```python
# midi_backend.py — canonical open
DEFAULT_PORT_NAME = "Universal Controller MIDI"
WINDOWS_FALLBACK_NAMES = ("ps5-bridge", "Universal Controller MIDI")

@dataclass
class OpenedPort:
    port: rtmidi.MidiOut
    name: str
    virtual: bool  # True on macOS/Linux, False when attaching loopMIDI on Win

def open_port(preferred_name: str = DEFAULT_PORT_NAME) -> OpenedPort:
    # macOS/Linux: rtmidi.open_virtual_port — true CoreMIDI / ALSA port
    # Windows: loopMIDI must already exist with a matching port name
```

- INPUT port name is distinct: `INPUT_PORT_NAME = "Universal Controller MIDI (in)"` (`midi_input.py`). Users on Windows need a SECOND loopMIDI port for haptic-in.
- The rtmidi callback (`set_callback`) fires on librtmidi's **C thread**. Never block. Never marshal back to BridgeWorker's QThread (it never spins a Qt event loop — queued slots never fire). Hold `BridgeWorker._haptic_lock` if you touch HID; otherwise just emit a Qt signal and let the GUI thread handle it.
- `close_port()` and `close_input_port()` are no-op-on-`None` — call them defensively from cleanup paths.
- `midi_port_matcher.py` is the fuzzy-match helper used to pick the right port when a DAW renames ports between sessions.

### Message Types & SysEx

`sysex_builder.py`, `sysex_parser.py`, `sysex_chunker.py`, and `hex_string_parser.py` are the pure-stdlib SysEx toolkit. No rtmidi imports in any of them — they hand back lists of bytes the bridge can `send_message` directly.

```python
# sysex_builder.py — constants
SYSEX_START = 0xF0    # 240
SYSEX_END   = 0xF7    # 247
MANUFACTURERS = {
    "roland": 0x41, "yamaha": 0x43, "korg": 0x42, "akai": 0x47,
    "alesis": 0x00, "novation": 0x40, "elektron": 0x60,
    "universal_non_realtime": 0x7E, "universal_realtime": 0x7F,
}
```

- SysEx data bytes are 7-bit (0..127). Status bytes (`0xF0`, `0xF7`) are the exception. Don't pass MIDI status bytes through SysEx data ranges.
- `sysex_chunker.chunk(message, max_bytes)` is the canonical splitter for hardware that has receive buffer limits (older Roland gear @ 256 bytes). Default to 1024 unless the device needs less.
- Standard message helpers: GM/GS/XG reset, universal device inquiry, program change with bank select, Roland-style manufacturer dumps. Add new builders as pure functions; never reach back into the bridge.

### Transport & Sync

`daw_transport.py` carries MIDI Machine Control (MMC) + standard transport helpers. `midi_clock_estimator.py` reverse-engineers a BPM from incoming `0xF8` clock pulses. `tempo_tap.py` is the user-driven counterpart.

```python
# bridge.py — clock-loop epoch tracking
self._clock_beat_epoch: float = 0.0   # perf_counter timestamp of last beat start
self._clock_bpm_live: float = 120.0   # BPM currently running in the clock thread
```

- Clock loop runs in its own daemon thread (`_clock_thread`), driven by `_sync_midi_clock()`. Updates `_clock_beat_epoch` every quarter-note so the quantize helpers can compute beat phase without separate bookkeeping.
- Tap-tempo: `_tap_times` ring of the last 4 timestamps. Compute BPM as 60 / mean(intervals). Clear after 2 s of idle so stale taps don't bias the next set.
- MMC messages live in SysEx land (`0x7F`-prefixed universal real-time). Use `daw_transport.build_mmc_play()` etc., never raw bytes inline.

### Routing & Muxing

Three composable layers:

| Module | Purpose |
| --- | --- |
| `channel_mute.ChannelMute` | per-channel mute + solo, solo-wins-mute semantics |
| `routing_matrix.RoutingMatrixConfig` | 16×16 input-channel → output-channel(s) matrix |
| `midi_filter.MidiFilter` | message-type filtering + transforms (transpose, channel remap) |

```python
# routing_matrix.py — config shape (default = identity matrix)
@dataclass
class RoutingMatrixConfig:
    enabled: bool
    matrix: list[list[bool]]      # 16x16, matrix[in_ch][out_ch] = True
    pass_through_unrouted: bool   # True: unrouted rows pass through to same ch
```

- Solo-wins semantics: if ANY solo bit is set, ONLY soloed channels pass. Mute always wins for soloed-and-muted channels (silenced).
- Routes can broadcast: one row with multiple `True`s splits one input across multiple outputs. Receivers see one message per output channel.
- Passthrough is a separate concept (`PassthroughConfig` in `mapping.py` + `BridgeWorker._sync_passthrough`) — it forwards messages from one input port into our output port with optional channel remap + transpose. Don't conflate it with the routing matrix.

### CC Features

- `cc_smoother.py` — modes: `one_pole`, `slew`, `moving_avg`, `none`. All support deadband suppression (changes below threshold ignored).
- `cc_bitcrush.py` — quantises CC values to a step ladder for lo-fi feel.
- `cc_snapshot.py` — captures + recalls full CC state across all channels.
- `cc_sweep.py` — stateful generator emitting CC values along envelope curves.
- `cc_input_lfo_detector.py` — analyses incoming CC streams to identify modulation sources (sine vs random vs ramp).
- `cc_throttle.py` — rate limit per (channel, cc) before flooding downstream.

Per-(axis, cc) smoothing state for the bridge lives in `BridgeWorker._cc_smooth_state: Dict[tuple, tuple]` keyed by `(axis_idx, cc_num) → (current, target, started_at_ms)`. Reset on `set_mapping` to avoid bleed-over between presets.

### Stuck Note Safety

```python
# stuck_note_detector.py — config + clamp
@dataclass
class StuckNoteConfig:
    enabled: bool = False
    stuck_after_s: float = 10.0   # clamped 0.5..3600
    auto_release: bool = False
```

- Track note-on / note-off pairs per `(channel, note)`. Flag when held longer than `stuck_after_s`.
- `auto_release=True` sends a note-off automatically. Default false so the UI can prompt — auto-release can mask real bugs in a user's mapping.
- `BridgeWorker.panic()` is the nuclear option (CC 123 + CC 120 + every note-off on every channel). Bind it to a clearly-labelled UI button, never to a controller input where a misfire would be costly.

### MIDI Activity Log

```python
# midi_activity_log.py — one event in the ring buffer
@dataclass
class MidiEvent:
    timestamp_s: float
    direction: str            # "in" or "out"
    message_bytes: List[int]
    port_name: str = ""
    tags: List[str] = field(default_factory=list)
    kind: str = "unknown"     # note_on, note_off, cc, pitch_bend, program_change,
                              # aftertouch, sysex, clock, unknown
    channel: Optional[int] = None   # 1-16 or None
```

- Pure-stdlib ring buffer; no Qt. Suitable for headless and UI contexts.
- BridgeWorker emits the `midi_message` Qt signal for the activity panel; that's separate from the persistent `midi_activity_log` buffer. Both layers are intentional — keep them.
- Classification (`kind`) happens once on insert by inspecting the status nibble. Do NOT re-classify on every read.

### OSC & RTP-MIDI

`osc_backend.py` does OSC 1.0 over UDP (no bundles). `rtp_midi.py` does a simplified RFC 4695/6295 subset — one MIDI message per UDP datagram, no session negotiation, no journal.

```python
# osc_backend.py — sender + receiver shapes
@dataclass
class OscSender:
    host: str
    port: int
    def send(self, address: str, value: int | float | str) -> None: ...

class OscReceiver:
    def __init__(self, port: int) -> None: ...
    def set_callback(self, cb: Callable[[str, list], None]) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

- OSC mode in `mapping.OscConfig`: `mode="alongside"` sends both MIDI + OSC, `mode="only"` skips MIDI entirely. Check `BridgeWorker._osc_only()` on the hot path before spending CPU on MIDI shaping when OSC-only is set.
- OSC bindings store `axis_addresses[axis_idx] -> address` and `button_addresses[btn_idx] -> address`. Convention: triggers send `1.0` on press, `0.0` on release; axes send the normalised float.
- OSC IN (receiver) runs on a daemon thread. Callback fires there — synthesize a `HapticInputBinding` and reuse `_fire_haptic` rather than building a parallel path.
- RTP-MIDI is single-hop LAN only. Don't enable it for cross-internet links; without the journal section there's no retransmit. `_rtp_send(status, data1, data2)` is the no-op-when-disabled forwarder used by every MIDI send site.

### MIDI Learn

```python
# midi_learn.py — one binding
@dataclass
class MidiLearnBinding:
    cc: int            # 0..127
    channel: int       # 1..16
    target_path: str   # dotted, e.g. "triggers.L2.cc_value_max"
    min_value: float
    max_value: float
    enabled: bool = True
```

- Pure data + scaling layer — no Qt, no global state, no bridge integration shortcuts.
- The bridge applies bindings when an incoming CC matches one. Scale via `min_value..max_value` linearly; non-linear curves are NOT supported here on purpose (keep the learn flow simple).
- Persisted as part of the mapping (`MidiLearnConfig`) — survives preset save/load.

### MIDI 2.0 / UMP

`midi2.py` provides `pack_midi2_note_on`, `pack_midi2_cc`, `scale_7bit_to_16bit`, `scale_7bit_to_32bit`, and `is_supported(port)` (best-effort probe — most rtmidi ports speak MIDI 1.0 only).

```python
# bridge.py — UMP path is gated on per-port probe
def _use_midi2(self) -> bool:
    m2 = self._state.mapping.midi2
    if not m2.enabled: return False
    return self._midi2_supported  # set by _probe_midi2_support()
```

- Probe runs ONCE per port-open in `_probe_midi2_support`. Cache the result; never re-probe per message.
- Note Off is always MIDI 1.0 even in UMP mode — UMP note-off is an "optional upgrade" and not all receivers honour it.
- `m2.group` is the UMP group (0..15). Default 0. Don't expose this unless the user has explicitly asked for multi-group routing.

### Connector Auto-Installers

Each connector implements `install(host: HostInstallation) -> InstallResult` using `shutil.copytree` / `shutil.copyfile`. Templates ship in `src/gamepad_midi_bridge/connectors/templates/` and are bundled by the PyInstaller `package_data` glob in `pyproject.toml`.

```python
# connectors/base.py — contract every connector implements
@dataclass
class HostInstallation:
    name: str           # "Resolume Arena 7"
    version: str        # "7"
    config_dir: Path    # where we write our integration file
    extra: dict

@dataclass
class InstallResult:
    success: bool
    written_path: Optional[Path]
    message: str

class Connector:
    display_name: str = "Generic Connector"; slug: str = "generic"
    pro_only: bool = False
    def detect(self) -> List[HostInstallation]: ...
    def install(self, host: HostInstallation) -> InstallResult: ...
    def uninstall(self, host: HostInstallation) -> InstallResult: ...
    def is_installed(self, host: HostInstallation) -> bool: ...
    def verify(self, host, stale_threshold=30*24*3600) -> Tuple[str, str]: ...
```

Per-host install paths (cheat sheet):

| Host | macOS | Windows | Linux |
| --- | --- | --- | --- |
| Ableton Live | `~/Music/Ableton/User Library/Remote Scripts/Universal Controller MIDI/` | `~/Documents/Ableton/User Library/Remote Scripts/Universal Controller MIDI/` | n/a (no native Live) |
| Resolume Arena | `~/Documents/Resolume Arena/Shortcuts/` | `%USERPROFILE%\Documents\Resolume Arena\Shortcuts\` | varies |
| TouchDesigner | project-extension drop-in | project-extension drop-in | project-extension drop-in |
| VDMX | `~/Library/Application Support/VDMX5/plugins/` | n/a | n/a |
| MadMapper | preset/shortcut bundle | preset/shortcut bundle | preset/shortcut bundle |
| REAPER | `~/Library/Application Support/REAPER/Effects/` | `%APPDATA%\REAPER\Effects\` | `~/.config/REAPER/Effects/` |
| OBS | scene-collection JSON | scene-collection JSON | scene-collection JSON |

- Templates: `connectors/templates/<host>/...` — bundled file copies. Don't edit installed copies; edit templates and reinstall.
- `verify(host, stale_threshold)` returns `('verified', details)` / `('outdated', details)` / `('missing', details)`. Default stale threshold 30 days — file mtime older than that flags `outdated`.
- `is_installed()` is path-presence only; `verify()` is the multi-step probe used by the Connectors tab.
- Ableton Live: Live 11+ only (Python 3 Remote Scripts). Live 9/10 ran Python 2 — explicitly unsupported. Documented in `connectors/ableton.py`.
- Each connector self-classifies via `pro_only: bool`. Most are free tier — gating legit users behind Pro for connector install is hostile.
