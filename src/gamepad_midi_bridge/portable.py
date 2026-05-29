"""Portable config bundles — `.gmbpack` files.

A `.gmbpack` is just a zip with a known shape:

    manifest.json       — version + creator + timestamp
    mapping.json        — the current mapping (Mapping.to_dict)
    presets/<name>.json — every preset in user_data_dir/presets
    snapshots/...       — named user snapshots (optional)
    autosaves/...       — timestamped autosaves (optional, can be large)
    license.key         — the user's Pro license blob, optional

Useful for moving a rig between machines, or sharing a complete loadout
with a collaborator. The license-blob is portable because Ed25519
signatures verify offline — but obviously the receiver only gets Pro on
THEIR install if the key was issued to them (the signed payload carries
the buyer's email, the verifier doesn't care which machine reads it).

GMBPACK_VERSION history:
  1: initial release (mapping + presets + license)
  2: added snapshots + autosaves support, dedup on import by slug
"""
from __future__ import annotations

import io
import json
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from . import __version__
from .mapping import Mapping
from .paths import license_path, presets_dir, user_data_dir


GMBPACK_VERSION = 2


@dataclass
class PackReport:
    """Summary of what was written or read from a .gmbpack."""
    mapping_present: bool
    preset_count: int
    license_present: bool
    snapshot_count: int = 0
    autosave_count: int = 0
    creator_version: Optional[str] = None
    created_at: Optional[str] = None


def export_pack(
    dest: Path,
    mapping: Mapping,
    include_license: bool = True,
    include_snapshots: bool = True,
    include_autosaves: bool = False,
) -> PackReport:
    """Write a .gmbpack containing the current mapping + presets + snapshots/autosaves.

    Args:
        dest: Path to write (`.gmbpack` suffix auto-added if missing).
        mapping: The mapping to bundle.
        include_license: Include license.key if it exists (default True).
        include_snapshots: Include named snapshots from snapshots/ (default True).
        include_autosaves: Include timestamped autosaves (default False — can be large).

    Writes atomically to a tempfile, then renames to `dest`.
    Returns a PackReport with counts of what was bundled.
    """
    if dest.suffix != ".gmbpack":
        dest = dest.with_suffix(".gmbpack")

    manifest = {
        "gmbpack_version": GMBPACK_VERSION,
        "creator_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    preset_count = 0
    snapshot_count = 0
    autosave_count = 0
    license_present = False

    # Write to temp first, then atomic rename
    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("mapping.json", json.dumps(mapping.to_dict(), indent=2))

            # Presets
            for p in sorted(presets_dir().glob("*.json")):
                z.write(p, arcname=f"presets/{p.name}")
                preset_count += 1

            # Named snapshots
            if include_snapshots:
                snapshots_dir = user_data_dir() / "snapshots"
                if snapshots_dir.exists():
                    for p in sorted(snapshots_dir.glob("*.json")):
                        z.write(p, arcname=f"snapshots/{p.name}")
                        snapshot_count += 1

            # Autosaves (timestamped)
            if include_autosaves:
                autosaves_dir = user_data_dir() / "autosaves"
                if autosaves_dir.exists():
                    for p in sorted(autosaves_dir.glob("*.json")):
                        z.write(p, arcname=f"autosaves/{p.name}")
                        autosave_count += 1

            # License
            if include_license and license_path().exists():
                z.write(license_path(), arcname="license.key")
                license_present = True

        # Atomic rename
        tmp_path.replace(dest)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return PackReport(
        mapping_present=True,
        preset_count=preset_count,
        snapshot_count=snapshot_count,
        autosave_count=autosave_count,
        license_present=license_present,
        creator_version=__version__,
        created_at=manifest["created_at"],
    )


def import_pack(
    source: Path,
    *,
    replace_license: bool = False,
    preset_conflict_callback: Optional[Callable[[str, str], bool]] = None,
    snapshot_conflict_callback: Optional[Callable[[str, str], bool]] = None,
) -> tuple[Optional[Mapping], PackReport]:
    """Load a .gmbpack from disk.

    Args:
        source: Path to the .gmbpack file.
        replace_license: If True and the pack contains a license, overwrite
            the user's existing license blob. Default False.
        preset_conflict_callback: Called if a preset slug already exists.
            Signature: (slug: str, pack_name: str) -> bool.
            Return True to overwrite, False to auto-suffix with "_imported".
            If None, auto-suffixes by default.
        snapshot_conflict_callback: Called if a snapshot slug already exists.
            Same semantics as preset_conflict_callback.

    Returns the new mapping (or None if missing) plus a report of what landed.
    """
    if not source.exists():
        raise FileNotFoundError(source)

    with zipfile.ZipFile(source, "r") as z:
        names = set(z.namelist())

        manifest = {}
        if "manifest.json" in names:
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))

        mapping: Optional[Mapping] = None
        if "mapping.json" in names:
            mapping = Mapping.from_dict(json.loads(z.read("mapping.json").decode("utf-8")))

        # Presets with dedup
        preset_count = 0
        for n in names:
            if not n.startswith("presets/") or not n.endswith(".json"):
                continue
            filename = Path(n).name
            slug_without_ext = filename[:-5]  # strip .json
            target = presets_dir() / filename

            # Check for conflict
            if target.exists():
                should_overwrite = False
                if preset_conflict_callback:
                    should_overwrite = preset_conflict_callback(slug_without_ext, filename)
                if not should_overwrite:
                    # Auto-suffix: preset.json -> preset_imported.json
                    filename = f"{slug_without_ext}_imported.json"
                    target = presets_dir() / filename

            target.write_bytes(z.read(n))
            preset_count += 1

        # Snapshots with dedup
        snapshot_count = 0
        for n in names:
            if not n.startswith("snapshots/") or not n.endswith(".json"):
                continue
            filename = Path(n).name
            slug_without_ext = filename[:-5]  # strip .json
            snapshots_dir_path = user_data_dir() / "snapshots"
            snapshots_dir_path.mkdir(parents=True, exist_ok=True)
            target = snapshots_dir_path / filename

            # Check for conflict
            if target.exists():
                should_overwrite = False
                if snapshot_conflict_callback:
                    should_overwrite = snapshot_conflict_callback(slug_without_ext, filename)
                if not should_overwrite:
                    # Auto-suffix: snapshot.json -> snapshot_imported.json
                    filename = f"{slug_without_ext}_imported.json"
                    target = snapshots_dir_path / filename

            target.write_bytes(z.read(n))
            snapshot_count += 1

        # Autosaves (always import, no dedup needed — timestamped)
        autosave_count = 0
        for n in names:
            if not n.startswith("autosaves/") or not n.endswith(".json"):
                continue
            filename = Path(n).name
            autosaves_dir_path = user_data_dir() / "autosaves"
            autosaves_dir_path.mkdir(parents=True, exist_ok=True)
            target = autosaves_dir_path / filename
            target.write_bytes(z.read(n))
            autosave_count += 1

        license_present = "license.key" in names
        if license_present and replace_license:
            license_path().write_bytes(z.read("license.key"))

    return mapping, PackReport(
        mapping_present=mapping is not None,
        preset_count=preset_count,
        snapshot_count=snapshot_count,
        autosave_count=autosave_count,
        license_present=license_present,
        creator_version=manifest.get("creator_version"),
        created_at=manifest.get("created_at"),
    )


def list_contents(source: Path) -> List[str]:
    """Peek inside a .gmbpack without unpacking — for a 'preview' dialog."""
    with zipfile.ZipFile(source, "r") as z:
        return z.namelist()
