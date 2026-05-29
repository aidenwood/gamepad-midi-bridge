"""`.gmbpack` round-trip tests."""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from gamepad_midi_bridge.mapping import Mapping
from gamepad_midi_bridge.portable import (
    GMBPACK_VERSION,
    export_pack,
    import_pack,
    list_contents,
)


def test_round_trip_preserves_mapping_fields(tmp_user_data, tmp_path):
    m = Mapping(name="Pack-Trip", midi_channel=5, deadzone=0.08, poll_hz=150)
    m.l2_haptic_effect = "weapon"

    dest = tmp_path / "loadout.gmbpack"
    report = export_pack(dest, m, include_license=False)
    assert report.mapping_present is True
    assert report.preset_count == 0
    assert report.license_present is False
    assert dest.exists()

    restored, in_report = import_pack(dest)
    assert restored is not None
    assert restored.name == "Pack-Trip"
    assert restored.midi_channel == 5
    assert restored.deadzone == 0.08
    assert restored.poll_hz == 150
    assert restored.l2_haptic_effect == "weapon"
    assert in_report.mapping_present is True
    assert in_report.preset_count == 0


def test_manifest_contains_required_fields(tmp_user_data, tmp_path):
    dest = tmp_path / "manifest_test.gmbpack"
    export_pack(dest, Mapping(), include_license=False)

    with zipfile.ZipFile(dest, "r") as z:
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
    assert manifest["gmbpack_version"] == GMBPACK_VERSION
    assert "creator_version" in manifest
    assert "created_at" in manifest


def test_empty_presets_folder_yields_zero_entries(tmp_user_data, tmp_path):
    """No preset files on disk -> zero preset entries inside the pack."""
    dest = tmp_path / "no_presets.gmbpack"
    report = export_pack(dest, Mapping(), include_license=False)
    assert report.preset_count == 0
    with zipfile.ZipFile(dest, "r") as z:
        preset_names = [n for n in z.namelist() if n.startswith("presets/")]
    assert preset_names == []


def test_list_contents_returns_expected_filenames(tmp_user_data, tmp_path):
    """`list_contents` is the dialog preview helper — must surface manifest + mapping."""
    dest = tmp_path / "preview.gmbpack"
    export_pack(dest, Mapping(), include_license=False)
    names = list_contents(dest)
    assert "manifest.json" in names
    assert "mapping.json" in names


def test_presets_round_trip(tmp_user_data, tmp_path):
    """Presets on disk get bundled in and restored on import."""
    from gamepad_midi_bridge import portable as portable_mod

    presets = portable_mod.presets_dir()
    (presets / "alpha.json").write_text(json.dumps({"name": "alpha"}))
    (presets / "beta.json").write_text(json.dumps({"name": "beta"}))

    dest = tmp_path / "with_presets.gmbpack"
    report = export_pack(dest, Mapping(), include_license=False)
    assert report.preset_count == 2

    # Wipe + re-import
    for p in presets.glob("*.json"):
        p.unlink()

    _, in_report = import_pack(dest)
    assert in_report.preset_count == 2
    assert (presets / "alpha.json").exists()
    assert (presets / "beta.json").exists()


def test_dest_suffix_auto_added(tmp_user_data, tmp_path):
    """Missing .gmbpack suffix gets appended automatically."""
    dest = tmp_path / "no_suffix"
    export_pack(dest, Mapping(), include_license=False)
    assert (tmp_path / "no_suffix.gmbpack").exists()


def test_export_pack_with_snapshots(tmp_user_data, tmp_path):
    """Snapshots are included when include_snapshots=True."""
    from gamepad_midi_bridge import portable as portable_mod

    snapshots_dir = portable_mod.user_data_dir() / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "live_set_v1.json").write_text(json.dumps({
        "name": "Live Set v1",
        "_snapshot_name": "Live Set v1"
    }))
    (snapshots_dir / "studio_v2.json").write_text(json.dumps({
        "name": "Studio v2",
        "_snapshot_name": "Studio v2"
    }))

    dest = tmp_path / "with_snapshots.gmbpack"
    report = export_pack(dest, Mapping(), include_license=False, include_snapshots=True)
    assert report.snapshot_count == 2

    with zipfile.ZipFile(dest, "r") as z:
        names = z.namelist()
        assert "snapshots/live_set_v1.json" in names
        assert "snapshots/studio_v2.json" in names


def test_export_pack_exclude_snapshots(tmp_user_data, tmp_path):
    """Snapshots are excluded when include_snapshots=False."""
    from gamepad_midi_bridge import portable as portable_mod

    snapshots_dir = portable_mod.user_data_dir() / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "live_set.json").write_text(json.dumps({"name": "Live"}))

    dest = tmp_path / "no_snapshots.gmbpack"
    report = export_pack(dest, Mapping(), include_license=False, include_snapshots=False)
    assert report.snapshot_count == 0

    with zipfile.ZipFile(dest, "r") as z:
        names = z.namelist()
        snapshot_files = [n for n in names if n.startswith("snapshots/")]
        assert snapshot_files == []


def test_export_pack_with_autosaves(tmp_user_data, tmp_path):
    """Autosaves are included when include_autosaves=True."""
    from gamepad_midi_bridge import portable as portable_mod

    autosaves_dir = portable_mod.user_data_dir() / "autosaves"
    autosaves_dir.mkdir(parents=True, exist_ok=True)
    (autosaves_dir / "2026-05-30-1500.json").write_text(json.dumps({"name": "autosave1"}))
    (autosaves_dir / "2026-05-30-1600.json").write_text(json.dumps({"name": "autosave2"}))

    dest = tmp_path / "with_autosaves.gmbpack"
    report = export_pack(dest, Mapping(), include_license=False, include_autosaves=True)
    assert report.autosave_count == 2

    with zipfile.ZipFile(dest, "r") as z:
        names = z.namelist()
        assert "autosaves/2026-05-30-1500.json" in names
        assert "autosaves/2026-05-30-1600.json" in names


def test_export_pack_exclude_autosaves(tmp_user_data, tmp_path):
    """Autosaves are excluded by default (include_autosaves=False)."""
    from gamepad_midi_bridge import portable as portable_mod

    autosaves_dir = portable_mod.user_data_dir() / "autosaves"
    autosaves_dir.mkdir(parents=True, exist_ok=True)
    (autosaves_dir / "2026-05-30-1500.json").write_text(json.dumps({"name": "big"}))

    dest = tmp_path / "no_autosaves.gmbpack"
    report = export_pack(dest, Mapping(), include_license=False, include_autosaves=False)
    assert report.autosave_count == 0

    with zipfile.ZipFile(dest, "r") as z:
        autosave_files = [n for n in z.namelist() if n.startswith("autosaves/")]
        assert autosave_files == []


def test_export_pack_atomic_write(tmp_user_data, tmp_path):
    """Export writes to tempfile and renames atomically."""
    dest = tmp_path / "atomic.gmbpack"
    report = export_pack(dest, Mapping(), include_license=False)

    # Should have completed successfully and be readable
    assert dest.exists()
    with zipfile.ZipFile(dest, "r") as z:
        assert "manifest.json" in z.namelist()
        assert "mapping.json" in z.namelist()


def test_import_pack_snapshots_round_trip(tmp_user_data, tmp_path):
    """Snapshots survive export and import round trip."""
    from gamepad_midi_bridge import portable as portable_mod

    snapshots_dir = portable_mod.user_data_dir() / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "beats.json").write_text(json.dumps({
        "name": "Beats",
        "_snapshot_name": "Beats"
    }))

    dest = tmp_path / "snap_roundtrip.gmbpack"
    export_pack(dest, Mapping(), include_license=False, include_snapshots=True)

    # Wipe and reimport
    for p in snapshots_dir.glob("*.json"):
        p.unlink()
    assert len(list(snapshots_dir.glob("*.json"))) == 0

    _, report = import_pack(dest)
    assert report.snapshot_count == 1
    assert (snapshots_dir / "beats.json").exists()


def test_import_pack_preset_dedup_auto_suffix(tmp_user_data, tmp_path):
    """Existing preset slug gets auto-suffixed with _imported when conflict occurs."""
    from gamepad_midi_bridge import portable as portable_mod

    presets = portable_mod.presets_dir()
    (presets / "drums.json").write_text(json.dumps({"name": "drums_old"}))

    # Create a pack with a preset that would conflict
    dest = tmp_path / "drums_conflict.gmbpack"
    export_pack(dest, Mapping(), include_license=False)

    # Manually add drums.json to the zip to simulate a conflict
    with tempfile.NamedTemporaryFile(suffix=".gmbpack", delete=False) as f:
        conflict_pack = Path(f.name)

    shutil.copy(dest, conflict_pack)
    with zipfile.ZipFile(conflict_pack, "a") as z:
        z.writestr("presets/drums.json", json.dumps({"name": "drums_new"}))

    # Import without callback — should auto-suffix
    _, report = import_pack(conflict_pack)
    assert (presets / "drums.json").exists()
    assert (presets / "drums_imported.json").exists()


def test_import_pack_preset_dedup_with_callback(tmp_user_data, tmp_path):
    """Preset conflict callback can choose to overwrite."""
    from gamepad_midi_bridge import portable as portable_mod

    presets = portable_mod.presets_dir()
    old_content = {"name": "drums_old", "version": 1}
    (presets / "drums.json").write_text(json.dumps(old_content))

    # Create a pack with conflicting preset
    dest = tmp_path / "drums_callback.gmbpack"
    export_pack(dest, Mapping(), include_license=False)

    with tempfile.NamedTemporaryFile(suffix=".gmbpack", delete=False) as f:
        conflict_pack = Path(f.name)

    shutil.copy(dest, conflict_pack)
    new_content = {"name": "drums_new", "version": 2}
    with zipfile.ZipFile(conflict_pack, "a") as z:
        z.writestr("presets/drums.json", json.dumps(new_content))

    # Import with callback that chooses to overwrite
    def always_overwrite(slug, name):
        return True

    _, report = import_pack(conflict_pack, preset_conflict_callback=always_overwrite)
    imported = json.loads((presets / "drums.json").read_text())
    assert imported["version"] == 2


def test_import_pack_snapshot_dedup(tmp_user_data, tmp_path):
    """Existing snapshot slug gets auto-suffixed on conflict."""
    from gamepad_midi_bridge import portable as portable_mod

    snapshots_dir = portable_mod.user_data_dir() / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "live.json").write_text(json.dumps({
        "name": "Live Old",
        "_snapshot_name": "Live Old"
    }))

    # Create a pack with conflicting snapshot
    dest = tmp_path / "snap_conflict.gmbpack"
    export_pack(dest, Mapping(), include_license=False)

    with tempfile.NamedTemporaryFile(suffix=".gmbpack", delete=False) as f:
        conflict_pack = Path(f.name)

    shutil.copy(dest, conflict_pack)
    with zipfile.ZipFile(conflict_pack, "a") as z:
        z.writestr("snapshots/live.json", json.dumps({
            "name": "Live New",
            "_snapshot_name": "Live New"
        }))

    _, report = import_pack(conflict_pack)
    assert (snapshots_dir / "live.json").exists()
    assert (snapshots_dir / "live_imported.json").exists()
