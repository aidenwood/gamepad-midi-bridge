# Hall: Mapping & Presets

The mapping schema (v4), validation, integrity, dedup, clone/mirror, fingerprinting, migration, naming, tagging, audit, preset loading, snapshots, autobackup, bank/favourites organisation, and the `.gmbpack` portable bundle format. Modules here are mostly pure-stdlib dict transforms — no Qt, no rtmidi.

### Core Mapping Struct & I/O

```python
# mapping.py — root constants + version
SCHEMA_VERSION = 4
STICK_AXES = frozenset({0, 1, 2, 3})
L2_AXIS = 4
R2_AXIS = 5
COLOR_TAGS = ("none","red","orange","yellow","green","teal","blue","purple","pink")
```

- `Mapping` is the top-level dataclass. Nested configs: `TriggerConfig`, `TriggerAftertouchConfig`, `StickFlickConfig`, `StickLfoConfig`, `PassthroughConfig`, `PatternRecorderConfig`, `QuantizeConfig`, `Midi2Config`, `MidiClockConfig`, `OscConfig`, `HapticInputBinding`, `ProgramChangeConfig`, `RoutingMatrixConfig`, `ChannelMute`, `MidiLearnConfig`, `Macro`, and the per-button/per-axis/per-hat dicts.
- Serialise via `Mapping.to_dict()` (uses `dataclasses.asdict`). Deserialise via `Mapping.from_dict(d)` — tolerant to missing keys (relies on `dict.get` with defaults).
- Schema version 4 is V1.3 (touchpad shaping options). v3 added per-trigger shaping + haptic input. v2 (V1.1) added corner-quantized stick buttons, touchpad XY CCs, adaptive-trigger haptic effect names. Old presets without new fields load with defaults — never drop unknown keys silently in non-migration code.
- `STICK_AXES` is a `frozenset` deliberately — calibration code iterates it via `sorted(STICK_AXES)`. Don't widen this to include triggers, that's an existing assumption load-bearing in `calibrate()`.

### Validation & Integrity

```python
# mapping_validator.py — never raises
def validate(d: dict) -> tuple[bool, list[str]]:
    # Returns (ok, error_messages). UI surfaces errors; loader rejects on False.
```

- `mapping_validator.py` validates untrusted JSON dicts (loaded files, share links, marketplace downloads). Never raises — always returns errors as a list.
- `mapping_integrity.py` is the deeper structural check used pre-save. Catches things like dangling references (a `gate_button` index pointing at a button slot that doesn't exist).
- `mapping_json_format.py` provides `pretty(d)` and `minify(d)` for save vs share-link emission.
- `mapping_slug_validator.py` enforces kebab-case slugs, unicode normalisation, reserved-word checks, length constraints. Don't write a parallel slug normaliser.

### Cleanup & Merge

```python
# mapping_cleanup.py and mapping_merge.py — pure dict transforms, no Mapping import
def clean_mapping(d: dict) -> dict: ...
def merge_mappings(base: dict, overlay: dict, strategy: str = "overlay") -> dict: ...
```

- Cleanup removes empty dicts, default-equivalent fields, and orphaned entries. Use before saving to disk to keep files small + diff-friendly.
- Merge strategies: `overlay` (overlay wins on conflict), `union` (combine non-conflicting), `intersect` (only keys present in both). Default to `overlay`.
- These modules never import `Mapping` directly. Keep them dict-in, dict-out so they're reusable for share-links + marketplace previews where you don't want to instantiate the full dataclass.

### Diffing & Search

`mapping_diff.py` does pure-function diffs over `Mapping` objects (or dicts). `mapping_diff_pretty.py` renders a UI-friendly version with categorisation. `mapping_search.py` finds where a specific note/CC/channel is used. `mapping_regex_search.py` adds regex-based value+key matching.

```python
# mapping_diff.py — diff result shape
@dataclass
class MappingDiff:
    added: dict     # key paths added in `b` not in `a`
    removed: dict   # key paths in `a` not in `b`
    changed: dict   # key paths with different values
```

- Diff is recursive over nested dataclasses-as-dicts. Don't try to diff at the dataclass level — always convert to dict first.
- `mapping_search.find_uses(d, target)` returns every path that references `target` (note number, CC, channel). Use this before letting a user change a global default — it catches "you'll silently break 3 mappings".

### Fingerprinting & Dedup

```python
# mapping_fingerprint.py — deterministic SHA-256 over canonical JSON
def canonical_json(data: Any) -> str: ...  # sorted keys, no whitespace
def fingerprint(d: dict) -> str: ...       # hex SHA-256
```

- Marketplace dedup is the primary use case ("is this preset already in your library?"). Comparing fingerprints is cheaper than diffing.
- `mapping_similarity.py` adds fuzzy similarity scoring (0..1) for clone detection — useful when the user has tweaked a marketplace preset and we want to surface "this looks like X with 3 changes".
- Always include `mapping_cloner.RESET_KEYS` (slug, marketplace_id, downloaded_at, shared_by, last_modified) when computing fingerprints for content equivalence — otherwise two clones look different just because of metadata.

### Cloning & Mirroring

```python
# mapping_cloner.py — top-level keys reset on clone
RESET_KEYS = {"slug", "marketplace_id", "downloaded_at", "shared_by", "last_modified"}

# mapping_mirror.py — flip everything around center=60 (middle C)
def mirror_full_mapping(d: dict, center: int = 60, mirror_axes: bool = True) -> dict: ...
```

- Cloning always deep-copies (`copy.deepcopy`) and resets `RESET_KEYS` so a clone is a distinct preset, not an alias.
- Mirroring is for left-handed players + inverted layouts. `mirror_buttons`, `mirror_axes_pairs` (swap left/right stick axes), `mirror_chords`, `mirror_macros` are all composable — `mirror_full_mapping` is the convenience wrapper.
- Mirror modules return NEW dicts/lists; input is never mutated. This is a load-bearing invariant — don't change to in-place.

### Migration & Versioning

```python
# mapping_migrator.py — registered migration functions
CURRENT_SCHEMA: int = 5
MIGRATIONS: Dict[int, Callable[[dict], dict]] = {}  # 1: v1→v2, 2: v2→v3, ...

def migrate_v1_to_v2(d: dict) -> dict:
    # v2 added per-trigger shaping (triggers dict)
    ...
```

- `CURRENT_SCHEMA` in `mapping_migrator.py` may LEAD `mapping.SCHEMA_VERSION` while a migration is being prepared. The loader runs the chain `v_loaded → ... → CURRENT_SCHEMA` then bumps the `schema_version` field on save.
- Every migration is a pure dict transform. Never reach back into the `Mapping` dataclass — it may have been refactored.
- `mapping_version_tracker.py` is the user-facing snapshots-and-diffing across edit history. `mapping_changelog.py` is the append-only mutation log with rollback support. They're parallel, intentional — one is "human save points", the other is "every keystroke audit".

### Naming & Slug Validation

```python
# mapping_naming_suggester.py
def suggest_name(d: dict) -> list[str]:
    # Returns 3 friendly-name candidates based on mapping contents
    # ("Pad Drumkit + Wide Sticks", "Latch L2 Lead", etc.)
```

- Slug validation: lowercase, kebab-case, ASCII-only after normalisation, max ~50 chars. See `mapping_slug_validator.py` for the canonical implementation.
- Name suggestion looks at: which controls are mapped, which presets seem similar, which tags apply. Keep this deterministic — same input → same suggestions, so users don't see different names if they reroll.

### Tagging & Organization

- `mapping_tags.py` — central registry of canonical tags. Use the registry slugs (`drumkit`, `lead`, `pad`, `bass`, `vj`, `ableton`, etc.); don't invent freeform tags.
- `mapping_auto_tagger.py` — extracts tags with confidence scores by inspecting mapping contents. Surfaces low-confidence tags as suggestions, auto-applies high-confidence ones.
- `mapping_banks.MappingBank(name, slug, preset_slugs, description)` groups related presets ("Live Set 1" = [lead, pad, bass]). Banks are pure-data — they don't own the presets, they reference them by slug.

### Analytics & Audit

```python
# mapping_audit.py — coverage report
@dataclass
class MappingAuditReport:
    mapped_buttons: list[int]; unmapped_buttons: list[int]
    mapped_axes: list[int]; unmapped_axes: list[int]
    # ...similar for hats, corners, touchpad, triggers, IMU
```

- `mapping_audit_formatter.py` renders the report as text/markdown/HTML for the audit tab.
- `mapping_size_budget.py` flags presets growing past sane size (~50 KB). Mostly catches "user pasted a 500-event macro three times".
- `mapping_tour.py` produces an ordered feature walkthrough for the in-app tour ("first we'll set up sticks, then triggers, then haptics...").

### Recommendations & Sharing

- `mapping_recommender.py` — analyses a mapping and suggests improvements ("you've got triggers in linear mode; with ceiling=80 you'd get more dynamic headroom").
- `mapping_share_link.py` — compresses a mapping dict to a URL-safe string (gzip + base64url) for share links. Round-trip is lossless. Long mappings overflow URL length budgets; surface a warning past ~2000 chars.
- `mapping_csv.py` — CSV export for spreadsheet-driven editing.
- `mapping_docs.py` — Markdown export for human-readable rig documentation.

### Preset System

```python
# presets.py — Pro feature, gated at UI layer (not at file I/O)
def load_preset_by_slug(slug: str) -> Optional[Mapping]: ...
def save_preset(mapping: Mapping, slug: str) -> Path: ...
def list_presets() -> list[Path]: ...

# Bundled starter presets seed on first launch (the _SEED_MARKER file gates
# re-seeding so users can delete starters without them coming back).
```

- Presets live in `paths.presets_dir()` as one JSON per preset. Slug is the filename stem.
- `_BUNDLED_DIR = src/gamepad_midi_bridge/resources/presets/` — bundled starters copied on first launch. `_SEED_MARKER = ".seeded"` prevents re-copy.
- Pro gating: `license.feature_enabled("presets")` at the UI layer. The file I/O is unconditional — the bridge needs to load whatever the user has on disk.
- Don't write presets from a worker thread — UI thread only, so the user's "save" action can surface errors.

### Preset Navigation

```python
# setlist_navigator.SetlistNavigator
@dataclass
class SetlistEntry:
    slug: str                 # preset slug
    label: str = ""           # display name
    bookmarked: bool = False
```

- `next() / prev() / jump_to(index) / back()` — `back()` walks the navigation history (not the same as `prev()`, which steps the list order).
- `setlist_shuffle.py` — randomises order with pinned positions and grouping constraints (e.g. "intros stay first, outros stay last, the rest shuffle").
- `setlist_time_tracker.py` — records duration per preset across a session for post-set analysis.
- Bridge-side state: `BridgeWorker._setlist_index: int`. `setlist_step` signal emits `(slug, index, total)` so the GUI loads the preset without the bridge knowing about the filesystem.

### Preset Chains & Blending

- `preset_chain.py` — walks through a list of presets at configured intervals. Useful for live performance "go through these 6 sounds in order at 32-bar boundaries".
- `preset_blend.py` — morphs between two preset configs via linear interpolation on numeric fields. Categorical fields snap at 0.5. Use sparingly — most users want preset SWAPS not blends.

### Template Bundles

```python
# templates.py — pygame DualSense button/axis ordering (load-bearing)
# buttons:  0=Cross 1=Circle 2=Square 3=Triangle 4=L1 5=R1
#           6=Share 7=Options 8=PS 9=L3 10=R3
# axes:     0=LX 1=LY 2=RX 3=RY 4=L2 5=R2
# hats:     "up"/"down"/"left"/"right"
```

- `templates.Template` entries each have a factory function that builds a FRESH `Mapping` per call — no shared-state surprises.
- `instrument_templates.py` — starter mappings organised by playing style (finger-drummer, lead, bass, pad).
- `drum_bundles.py` — drum-kit-specific presets (8-pad kit, 16-pad kit, etc.).
- `daw_bundles.py` — DAW-specific MIDI mappings (Live Drum Rack, FL Studio Performance, Logic Smart Tempo).
- When you add a new template, register it in the templates list — the visual template builder tab autopopulates from there.

### Bank & Favorites

- `mapping_banks.py` — named bank → list of preset slugs (description field is optional metadata).
- `mapping_favourites.FavouriteEntry(preset_slug, stars=0, pinned=False, last_played_at, play_count)` — used by the Favourites widget.
- `mapping_pinned_history.py` — pinned recent items with explicit ordering (vs `mapping_favourites` which sorts by recency / stars).

### Backup

```python
# autobackup.py — timestamped snapshots
def autosaves_dir() -> Path: ...
def write_autosave(mapping: Mapping) -> Path: ...

# snapshots.py — user-named save points
def list_snapshots() -> List[Path]: ...
def save_snapshot(mapping: Mapping, label: str) -> Path: ...
```

- Auto-backup writes on every `set_mapping` after a debounce window (don't write every keystroke). Filename includes UTC timestamp.
- `_clean_shutdown_flag()` is checked on startup — if missing, the previous run crashed and the UI offers to restore the last autosave.
- Named snapshots are user-labelled, distinct from autosaves. Both live under `user_data_dir()` in separate folders.
- `portable.export_pack(path, mapping)` / `portable.import_pack(path, replace_license=True)` produce/consume `.gmbpack` files — zip with `manifest.json`, `mapping.json`, `presets/`, optional `snapshots/`, optional `autosaves/`, optional `license.key`. `GMBPACK_VERSION` is currently 2 (added snapshots + autosaves + slug-based dedup on import).
