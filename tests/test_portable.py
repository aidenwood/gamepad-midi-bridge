"""`.gmbpack` round-trip tests."""
from __future__ import annotations

import json
import zipfile

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
