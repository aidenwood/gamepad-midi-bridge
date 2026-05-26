# Release Checklist

Maintainer-only. Run through this top-to-bottom for every public release.

## 1. Version bump

Edit `src/gamepad_midi_bridge/__init__.py`:

```python
__version__ = "0.X.Y"
```

Semver. PATCH for bug fixes, MINOR for new features, MAJOR for breaking changes (we're still pre-1.0 so MAJOR stays at 0).

## 2. Changelog

In `CHANGELOG.md`:

- Move every entry under `## [Unreleased]` into a new dated section: `## [0.X.Y] — YYYY-MM-DD`.
- Keep `## [Unreleased]` as an empty placeholder for the next cycle.
- Re-read the section. Anything user-visible that's missing? Add it.

## 3. Local verification

```bash
pytest tests/
ruff check .
ruff format --check .
```

Then smoke-test the GUI on all three OSes if you can. Realistically that means macOS (our dev box) for every release, Windows + Linux at least once per MINOR bump:

- Launch the app cold (delete `<user_data_dir>` first to test onboarding)
- Plug in a controller, click Start, confirm MIDI traffic in a DAW
- Click through every tab — no crashes, no missing widgets
- Run `gamepad-midi-bridge --headless --debug` for 30 seconds, kill it, confirm clean exit in the log

If anything wobbles, fix it before tagging. Tagged releases are immutable — pulling a tag back is painful.

## 4. Tag and push

```bash
git tag v0.X.Y
git push origin v0.X.Y
```

CI takes over from here: builds for macOS / Windows / Linux, signs where applicable, publishes the GitHub release with all three platform zips attached.

## 5. Confirm CI artefacts

Wait for the GitHub release to appear. Verify:

- All three platform zips are attached (macOS `.app`, Windows `.exe` directory, Linux single-file binary)
- Release notes are populated from the changelog section
- Download each zip and unzip it locally to confirm it isn't truncated

If CI failed, delete the GitHub release + tag, fix the issue on `main`, re-tag.

## 6. Store landing page

In the `PS5-MIDI-Bridge-Store/` repo:

- Bump version display on the landing page
- Update download links to the new release zips
- If there's a fresh walkthrough video, replace `PLACEHOLDER_VIDEO_ID` with the real YouTube/Vimeo ID
- Deploy

## 7. Blog + social

- Publish a short post on `aidxn.com/blog` — Fireship-style if there's a flashy feature, terse changelog dump if it's a patch release
- Tweet a 30-second clip if there's a visible feature change. No clip for invisible patches — saves the audience the noise

## 8. Post-release sanity

- Re-pull the GitHub release zip on a fresh machine (or VM) and run it. Confirm the in-app updater no longer shows a banner.
- Watch the GitHub issues tab for the next 24 hours.

Done. Reset the changelog placeholder and you're back in normal dev flow.
