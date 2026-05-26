# Contributing

Cheers for considering a contribution. This guide gets you set up locally, then walks through the conventions we expect in a PR.

If you're new to the codebase, skim the [architecture doc](./architecture.md) first — it covers the module layout and threading model, which are the two things most likely to bite you.

## Quick setup

```bash
git clone <repo-url>
cd PS5-MIDI-Bridge
python -m venv .venv
source .venv/bin/activate                    # Windows: .venv\Scripts\activate
pip install -e ".[dev,build]"
```

Python 3.9+ required. PySide6 ships its own Qt runtime, so no system Qt install needed.

## Run from source

Two equivalent options:

```bash
gamepad-midi-bridge                          # console script from pyproject
python -m gamepad_midi_bridge                # module entrypoint
```

Headless run (kiosks / rigs / quick sanity check without the GUI):

```bash
gamepad-midi-bridge --headless --debug
```

Useful flags during dev: `--reset-config` (wipe stored settings), `--log-path` (print log location and exit).

## Tests

```bash
pytest tests/
```

Tests focus on the deterministic bits: calibration math, mapping serialisation round-trips, corner quantizer hysteresis, OSC packet builder. Anything that needs real hardware (HID, MIDI port creation, controller input) is mocked.

If you're adding logic that doesn't have a test, write one. If you're touching something with an existing test, run it.

## Linting

```bash
ruff check .
ruff format .
```

Both must pass before a PR is mergeable. CI runs them on every push.

## Style rules

- **4-space indent.** No tabs.
- **Type hints everywhere.** New code without annotations gets bounced.
- **Docstrings explain WHY.** The code already shows what. If the docstring just restates the function name in English, delete it.
- **No emoji in code, comments, or strings.** UI labels stay text-only.
- **Never commit credentials, license private keys, or `scripts/private_key.pem`.** The Ed25519 signing key lives in the store repo behind Netlify env vars, never here.
- **No `npx`.** This is a Python project, but the rule generalises — install tools properly, don't shim them.
- **Prefer dataclasses over loose dicts.** `mapping.py` is the reference.

## Adding a new connector

Use `connectors/resolume.py` as your reference implementation — it's the most complete and covers every pattern.

1. Create `src/gamepad_midi_bridge/connectors/<host>.py`.
2. Subclass `Connector` from `base.py`.
3. Implement:
   - `display_name` — what the Connectors tab shows
   - `detect()` — scan the filesystem, return one `HostInstallation` per install found
   - `install(host)` — copy your template into the host's user dir, return `InstallResult`
   - `uninstall(host)` — remove what `install()` put there
   - `is_installed(host)` — quick boolean check
   - `post_install_steps(host)` — human-readable instructions shown in the GUI
4. Drop your template file into `connectors/templates/`.
5. Register the connector in `connectors/__init__.py::all_connectors()`.
6. Add a test in `tests/test_connectors_<host>.py` covering `detect()` against a mocked filesystem and `install()` → `is_installed()` → `uninstall()` round-trip.

Keep `install()` atomic — write to a temp file then rename, never partial-write into the target location. Users will quit the app mid-install at least once.

## PR checklist

Before opening a PR:

- [ ] `pytest tests/` passes locally
- [ ] `ruff check .` and `ruff format .` clean
- [ ] README updated if you changed user-visible behaviour
- [ ] CHANGELOG updated under `## [Unreleased]` if you changed user-visible behaviour
- [ ] No Pro-feature lock removed (see below)
- [ ] No emoji added
- [ ] No credentials, keys, or `.env` files committed
- [ ] New modules have docstrings, new functions have type hints

**Never remove a Pro lock to "fix a bug".** If a free user hit a Pro path and it crashed, the fix is to handle the gate cleanly — show the upsell dialog or no-op — not delete the gate.

## Branching

- `main` is always shippable. CI passes, the GUI launches, the engine bridges.
- Feature branches: `feature/<short-description>` or `fix/<short-description>`.
- Open a PR against `main`. We squash-merge — your branch's commits collapse into one descriptive commit at merge time, so your local history can be as messy as you like.
- Tag releases on `main` only. See the [release checklist](./release-checklist.md).

## Questions

Open a GitHub issue or check the Help tab in the running app — the same FAQ ships with the binary.
