# Hall: Node-Graph Input Layer

A composable transform layer between raw controller input and MIDI output, surfaced (in Phase 2) as a TouchDesigner-style node-graph canvas attached to the visualiser. Phase 1 backend only — every value here is fully usable without a Qt loop attached. Read this hall before touching anything under `src/gamepad_midi_bridge/nodes/`.

### Architecture in one diagram

```
ControllerSource(s) ──wires──> Node(s) ──wires (with optional ⚙ transform)──> SymbolicSink(s)
       ↑                                                                              ↓
   bridge tick                                                                Resolver: symbol → MIDI
   reads stick/btn                                                            (raw `midi.cc:N@ch:C` now,
   pushes snapshot                                                             connectors in Phase 2)
```

The graph is a DAG (cycles are refused at evaluation time). Per-tick the evaluator walks topologically, applies each node's `apply(params, inputs, state)`, runs any `InlineTransform` on each `Connection` as the value travels, and accumulates `Send(symbol, value)` pairs at the sinks.

### Where each piece lives

| File | What |
|---|---|
| `nodes/model.py` | `Node`, `NodeSpec`, `ParamSpec`, `PinSpec`, `Connection`, `InlineTransform`, `ControllerSource`, `SymbolicSink`, `NodeGraph` |
| `nodes/registry.py` | `NodeRegistry` — first-party + user-folder loader, override semantics, wire-eligibility validation |
| `nodes/builtins/*.py` | One module per first-party node. Each exposes a module-level `NODES = [NodeSpec(...)]` list, picked up automatically by `load_builtins()`. |
| `nodes/evaluator.py` | `evaluate(graph, registry, source_values, state_store) -> List[Send]` |
| `nodes/sinks.py` | Symbolic → raw-MIDI resolver. Phase 1: handles `midi.cc:N@ch:C` and `midi.note:N@ch:C`; Phase 2: connector subsystem extends it. |
| `nodes/serialise.py` | `graph_from_dict` — Mapping.from_dict's path back from the JSON form into live dataclasses. |

### Categories Room (TouchDesigner-style grouping)

Every NodeSpec declares one of these categories. The Phase-2 picker iterates `CATEGORIES` (declared in `nodes/model.py`) in `sort_priority` order — categories with no registered nodes are simply absent from the picker. `NodeRegistry.by_category()` yields the populated subset.

| Category | What lives here | Picker colour token |
|---|---|---|
| **input** | Controller surfaces (currently first-class via `ControllerSource` — placeholder for future node-shaped sources). | `ACCENT_TEAL` |
| **gate** | Conditional firing — boolean / edge / time-based. | `ACCENT_AMBER` |
| **shape** | 1-D scalar reshape — range, curve, sign, clamp. | `ACCENT_TEAL` |
| **spatial** | Multi-axis transforms — polar, axis pick, vec math. | `FOCUS_RING` |
| **modulator** | Time-driven generators + samplers. | `ACCENT_CORAL` |
| **logic** | Multi-input boolean — chord, future and/or/not/compare. | `ACCENT_AMBER` |
| **music** | Note-aware operators (reserved for Phase 2 — scale quantize, chord build, transpose). | `ACCENT_TEAL` |
| **output** | MIDI / OSC destinations (currently first-class via `SymbolicSink`). | `ACCENT_CORAL` |

User-authored nodes can declare any of the above. Inventing a brand-new category string is allowed but the node lands at the bottom of the picker (priority 999) until a `CategoryMeta` for that string is added to `CATEGORIES`.

### Nodes Room

The shipped first-party catalogue grew from 14 (Phase 1) to **78** across Phase 2 — the per-node lists below are summaries; the canonical source for every spec is `src/gamepad_midi_bridge/nodes/builtins/*.py` and `NodeRegistry.all()` enumerates them at runtime.

| Category | Count | Members |
|---|---|---|
| **gate** | 12 | `live_gate`, `edge_gate`, `tap_vs_hold`, `toggle`, `multi_tap`, `hold_threshold`, `momentary_inverse`, `panic_once`, `double_click`, `pulse`, `release_edge`, `latch_value` |
| **shape** | 21 | `range_remap`, `curve`, `invert`, `clamp`, `smooth_lerp`, `slew_limit`, `add_offset`, `multiply`, `absolute`, `mirror`, `wrap`, `step_quantize`, `power_curve`, `hysteresis`, `dead_zone`, `sign`, `square`, `bias`, `ceil`, `floor`, `exponential` |
| **spatial** | 9 | `polar`, `axis_pick`, `vec2_swap`, `vec2_rotate`, `vec2_clamp_radius`, `vec2_normalize`, `vec2_scale`, `radial_sector`, `flick_detect`, `xy_quadrant` |
| **modulator** | 15 | `lfo`, `sample_hold`, `delay_line`, `envelope_follower`, `accumulator`, `arpeggio`, `attack_release`, `peak_hold`, `valley_hold`, `ramp_generator`, `tap_tempo`, `noise_random`, `adsr`, `random_walk`, `chase_to_target` |
| **logic** | 11 | `chord_detect`, `not_gate`, `and_gate`, `or_gate`, `xor_gate`, `comparator`, `counter`, `mux_2`, `mux_4`, `range_check`, `is_nonzero` |
| **music** | 9 | `transpose`, `octave_shift`, `scale_quantize`, `velocity_curve`, `chord_build`, `chord_inversion`, `arpeggiator_pattern`, `note_to_cc`, `cc_to_note` |

`wire_eligible` means the node can sit inline on a `Connection`'s ⚙ menu without needing a full node card on the canvas. The registry enforces 1-in/1-out for any spec that opts in. About half the catalogue (the simple 1-in/1-out transforms) is wire-eligible; multi-input + stateful + multi-output nodes need a full card.

#### Notable patterns surfaced by the catalogue

- **One press → multiple events**: `arpeggio` (repeat-while-held), `multi_tap` (count taps), `pulse` (timed one-shot), `ramp_generator` (3-phase envelope plays out from one press).
- **Curve adjustments**: `curve` (5 shapes), `power_curve`, `bias` (Schlick), `exponential`, `square`, `mirror`, `wrap`, `dead_zone`, plus the legacy stick deadzone fields.
- **Timing**: `delay_line` (N-tick lag), `tap_tempo` (BPM from taps), `pulse` (fixed-length pulse), `attack_release` / `adsr` / `ramp_generator` envelopes.
- **Music**: `scale_quantize` (10 scales), `chord_build` (9 chord types), `chord_inversion`, `arpeggiator_pattern` (up/down/updown/random), `transpose`, `octave_shift`, `velocity_curve`, `note_to_cc` / `cc_to_note`.

### Adding a new node

1. Create `src/gamepad_midi_bridge/nodes/builtins/<your_node>.py`.
2. Define a pure-ish `_apply(params, inputs, state) -> dict[pin_name, value]`. `state` is a mutable dict scoped to this node instance — read + write keys to persist across ticks for stateful behaviour (LFOs, latches, counters). Leave `state` alone if your node is stateless.
3. Build a `NodeSpec(kind=..., label=..., category=..., description=..., short_description=..., params=(...), inputs=(...), outputs=(...), wire_eligible=True|False, apply=_apply)`.
4. Expose it via `NODES = [SPEC]` at module level. The loader auto-discovers it on next launch — no registry edits needed.
5. Write tests under `tests/test_node_graph.py` modelled after the existing seed-node tests.

```python
# Minimum-shape new node — passes through, doubles its input.
from ..model import NodeSpec, PinSpec
def _apply(params, inputs, state=None):
    v = inputs.get('in') or 0.0
    return {'out': float(v) * 2.0}
SPEC = NodeSpec(
    kind='example_double',
    label='Example Double',
    category='transform',
    description='Multiplies the input scalar by 2.',
    short_description='Doubles input.',
    inputs=(PinSpec('in', 'in', 'Scalar.'),),
    outputs=(PinSpec('out', 'out', 'Scalar.'),),
    wire_eligible=True,
    apply=_apply,
)
NODES = [SPEC]
```

### User / community nodes

`NodeRegistry.load_user_dir(path)` scans a folder for `.py` files (skipping `_*`) and registers any `NODES` list it finds. The intended location is `<user_data_dir>/user_nodes/` — same convention TouchDesigner uses for `.tox` extensions. Same NodeSpec contract as builtins; failures in one user module never block the others (logged and skipped).

Future hook: a marketplace of community nodes shipped as `.gmbnode` bundles (zip of a `.py` plus assets), delivered via the storefront's existing preset marketplace infrastructure.

### Symbolic sinks vs raw MIDI

Sinks describe **what to send** as a string, not how:

```
midi.cc:7@ch:1                              ← raw, handled in Phase 1
midi.note:60@ch:1                           ← raw, handled in Phase 1
resolume.layer:1.effect:Frost.opacity       ← symbolic, log-only in Phase 1
ableton.track:Bass.send:A                   ← symbolic, log-only in Phase 1
```

Channels are **1-based in the symbol** (matches every DAW + Resolume), **0-based in the MIDI status byte** (matches python-rtmidi). Conversion lives in `sinks.resolve()` so no caller has to think about it.

Phase 2 will wire the connectors module (`connectors/resolume.py`, etc.) into the resolver so symbolic destinations get bound at preset-load time and `_poll_node_graph` emits real MIDI for them too.

### Bridge integration

`BridgeWorker._poll_node_graph(reader, mapping)` runs once per tick when `mapping.node_graph` is non-empty. The Phase-1 experimental opt-in `GMB_NODE_GRAPH=1` was retired once the canvas + auto-save made the graph a first-class user-facing feature. Set `GMB_NODE_GRAPH=0` to force-disable if a user wants to keep the canvas while suppressing its MIDI output (rare diagnostic path).

It builds a per-source snapshot from the live reader, calls `evaluate(...)`, and dispatches each `Send`:
- Raw `midi.*` symbols → emit via the existing MIDI port handle.
- Anything else → throttled status-bar log at 5 Hz so the UI doesn't get spammed.

The whole call is wrapped in `try/except` so any node-graph bug is contained — the existing flag-based input path that's been running on stage for years is never put at risk by an experimental graph.

### Phase 2 hooks (NOT YET IMPLEMENTED)

When the canvas UI lands, expect:
- `position: (x, y)` on every `Node`, `ControllerSource`, `SymbolicSink` to drive canvas placement (already in the dataclasses).
- `ParamSpec.description` rendered as a TouchDesigner-style hover popover.
- `Connection.inline_transform` editable from the ⚙ menu on the wire midpoint.
- A connector-aware resolver registered into `sinks.resolve()` so Resolume/Ableton/etc. symbols actually send MIDI.
- A `QGraphicsScene` host inside the Visualise tab with pan + Cmd-scroll zoom + bezier-wire rendering.

### Things that would break compatibility

- Renaming a node's `kind` — existing presets reference it by string.
- Removing a `PinSpec` from a NodeSpec — connections referencing the gone pin would orphan.
- Changing the `apply` signature beyond optional kwargs — existing user nodes that didn't update would crash on call. (Phase 1 already paid this cost once when state was added; do it carefully if there's a next time.)
- Anything in `Mapping.to_dict` that emits `node_graph` for an empty/None graph — old-shape presets must round-trip byte-identical at the graph key (tested).
