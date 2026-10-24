"""Integrity checks over the bundled preset library.

Found 2026-10-24: 16 of the 55 bundled presets are byte-identical to another
one apart from the `name` field. Fifteen of them are the same default mapping
shipped as "Xbox Series X|S — Default", "PS4 DualShock 4 — Default",
"Music Education — Kids C Major", "Twitch — Stinger Transitions + Scenes" and
eleven more. A user picking between them gets exactly the same thing, while
the names promise differentiation that does not exist.

The duplicates are deliberately NOT deleted here — which of them should be
retired versus given real host-specific content is a product call, and
removing a shipped preset could break a setlist that references it by name.

What this file does is stop the problem growing. `KNOWN_DUPLICATE_GROUPS`
is a frozen record of the two groups as found. A NEW duplicate fails the
suite; shrinking an existing group also fails, so the record cannot silently
go stale once someone starts fixing them.
"""

import glob
import json
import os
from pathlib import Path

import pytest

PRESET_DIR = (
    Path(__file__).resolve().parents[1]
    / "src" / "gamepad_midi_bridge" / "resources" / "presets"
)

# Fields that legitimately differ between two otherwise-identical presets and
# do not make them meaningfully different to a user.
_COSMETIC = ("name", "color_tag", "favourite")

# The two groups as they stood when this check was written. Sorted names.
KNOWN_DUPLICATE_GROUPS = [
    sorted([
        "8BitDo Pro 2 — Default + Paddles",
        "Ableton Live — Clip Launcher",
        "Ableton clip launcher",
        "CoGe + VJamm — Bridge Setup",
        "GarageBand — iPad Wireless via Mac Bridge",
        "MFi iOS Bluetooth — Backbone - Kishi",
        "Magic Music Visuals — Audio-Reactive Live",
        "Music Education — Kids C Major",
        "Nintendo Switch Pro Controller — Default",
        "PS4 DualShock 4 — Default",
        "Resolume default",
        "Stadia Controller — Revival",
        "Twitch — Stinger Transitions + Scenes",
        "Xbox + PS5 — Generic Cross-Platform",
        "Xbox Series X-S — Default",
    ]),
    sorted([
        "Kaoss Pad mode",
        "Kaoss Pad — Touchpad XY",
        "Valve Steam Controller — Two Trackpads",
    ]),
]


def _preset_files():
    return sorted(glob.glob(str(PRESET_DIR / "*.json")))


def _fingerprint(path: str) -> str:
    """Everything that makes a preset functionally what it is."""
    with open(path) as fh:
        data = json.load(fh)
    for key in _COSMETIC:
        data.pop(key, None)
    return json.dumps(data, sort_keys=True)


def _duplicate_groups():
    buckets: dict[str, list[str]] = {}
    for path in _preset_files():
        buckets.setdefault(_fingerprint(path), []).append(
            os.path.basename(path)[:-5]
        )
    return sorted(
        (sorted(names) for names in buckets.values() if len(names) > 1),
        key=lambda g: g[0],
    )


class TestPresetsAreWellFormed:
    def test_there_are_presets(self):
        assert len(_preset_files()) > 40

    def test_every_preset_parses(self):
        for path in _preset_files():
            with open(path) as fh:
                json.load(fh)

    def test_every_preset_loads_into_a_mapping(self):
        from gamepad_midi_bridge.mapping import Mapping

        for path in _preset_files():
            with open(path) as fh:
                Mapping.from_dict(json.load(fh))

    def test_name_matches_the_filename(self):
        """A preset whose `name` disagrees with its file is unfindable.

        Allowing for filesystem escaping: `/` and `|` cannot appear in a
        filename, so "Xbox Series X|S — Default" is stored as
        "Xbox Series X-S — Default" and "Drone / Quadcopter" as
        "Drone - Quadcopter". Those are correct, not drift.
        """
        def normalise(value: str) -> str:
            return value.replace("/", "-").replace("|", "-").replace("  ", " ")

        mismatched = []
        for path in _preset_files():
            with open(path) as fh:
                name = json.load(fh).get("name", "")
            stem = os.path.basename(path)[:-5]
            if normalise(name) != normalise(stem):
                mismatched.append((stem, name))
        assert not mismatched, f"name/filename mismatch: {mismatched}"


class TestNoNewDuplicates:
    """The ratchet. Fix duplicates freely; do not add any."""

    def test_no_unexpected_duplicate_group(self):
        found = _duplicate_groups()
        known = {tuple(g) for g in KNOWN_DUPLICATE_GROUPS}
        unexpected = [g for g in found if tuple(g) not in known]
        assert not unexpected, (
            "New functionally-identical presets. Two presets that differ only "
            f"by name mislead whoever picks between them: {unexpected}"
        )

    def test_known_groups_have_not_grown(self):
        found = {g[0]: g for g in _duplicate_groups()}
        for known in KNOWN_DUPLICATE_GROUPS:
            current = found.get(known[0])
            if current is None:
                continue  # group was fixed entirely — handled below
            grew = set(current) - set(known)
            assert not grew, f"duplicate group grew by {sorted(grew)}"

    def test_the_record_is_not_stale(self):
        """If a group shrinks, this file must be updated in the same change.

        Otherwise the known-list quietly becomes fiction and the ratchet stops
        meaning anything — the same way a sitemap that lists a blocked URL
        stops being a sitemap.
        """
        found = {g[0]: g for g in _duplicate_groups()}
        stale = []
        for known in KNOWN_DUPLICATE_GROUPS:
            current = found.get(known[0])
            if current is None:
                stale.append((known[0], "group no longer exists"))
            elif set(current) != set(known):
                stale.append((known[0], f"now {sorted(set(known) - set(current))} fewer"))
        assert not stale, (
            "KNOWN_DUPLICATE_GROUPS is out of date — duplicates were fixed "
            f"without updating this record: {stale}"
        )


@pytest.mark.parametrize("group", KNOWN_DUPLICATE_GROUPS, ids=lambda g: g[0])
def test_known_duplicates_really_are_identical(group):
    """Documents the finding rather than trusting the comment above it."""
    prints = {_fingerprint(str(PRESET_DIR / f"{name}.json")) for name in group}
    assert len(prints) == 1, f"{group[0]} group is no longer identical"
