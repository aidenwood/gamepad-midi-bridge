"""Portable config bundles — `.gmbpack` files.

A `.gmbpack` is just a zip with a known shape:

    manifest.json       — version + creator + timestamp
    mapping.json        — the current mapping (Mapping.to_dict)
    presets/<name>.json — every preset in user_data_dir/presets
    license.key         — the user's Pro license blob, optional

Useful for moving a rig between machines, or sharing a complete loadout
with a collaborator. The license-blob is portable because Ed25519
signatures verify offline — but obviously the receiver only gets Pro on
THEIR install if the key was issued to them (the signed payload carries
the buyer's email, the verifier doesn't care which machine reads it).
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from . import __version__
from .mapping import Mapping
from .paths import license_path, presets_dir


GMBPACK_VERSION = 1


@dataclass
class PackReport:
    """Summary of what was written or read from a .gmbpack."""
    mapping_present: bool
    preset_count: int
    license_present: bool
    creator_version: Optional[str] = None
    created_at: Optional[str] = None


def export_pack(dest: Path, mapping: Mapping, include_license: bool = True) -> PackReport:
    """Write a .gmbpack containing the current mapping + every preset on disk."""
    if dest.suffix != ".gmbpack":
        dest = dest.with_suffix(".gmbpack")

    manifest = {
        "gmbpack_version": GMBPACK_VERSION,
        "creator_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    preset_count = 0
    license_present = False

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("mapping.json", json.dumps(mapping.to_dict(), indent=2))
        for p in sorted(presets_dir().glob("*.json")):
            z.write(p, arcname=f"presets/{p.name}")
            preset_count += 1
        if include_license and license_path().exists():
            z.write(license_path(), arcname="license.key")
            license_present = True

    return PackReport(
        mapping_present=True,
        preset_count=preset_count,
        license_present=license_present,
        creator_version=__version__,
        created_at=manifest["created_at"],
    )


def import_pack(source: Path, *, replace_license: bool = False) -> tuple[Optional[Mapping], PackReport]:
    """Load a .gmbpack from disk.

    `replace_license`: if True and the pack contains a license, overwrite the
    user's existing license blob. Default False — we ask the user separately
    via the GUI before clobbering their key.

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

        preset_count = 0
        for n in names:
            if not n.startswith("presets/") or not n.endswith(".json"):
                continue
            target = presets_dir() / Path(n).name
            target.write_bytes(z.read(n))
            preset_count += 1

        license_present = "license.key" in names
        if license_present and replace_license:
            license_path().write_bytes(z.read("license.key"))

    return mapping, PackReport(
        mapping_present=mapping is not None,
        preset_count=preset_count,
        license_present=license_present,
        creator_version=manifest.get("creator_version"),
        created_at=manifest.get("created_at"),
    )


def list_contents(source: Path) -> List[str]:
    """Peek inside a .gmbpack without unpacking — for a 'preview' dialog."""
    with zipfile.ZipFile(source, "r") as z:
        return z.namelist()
