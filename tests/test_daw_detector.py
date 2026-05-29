"""Tests for gamepad_midi_bridge.daw_detector."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from gamepad_midi_bridge import daw_detector as dd
from gamepad_midi_bridge.daw_detector import DetectedApp, detect_installed_apps


# ---------------------------------------------------------------------------
# DetectedApp dataclass
# ---------------------------------------------------------------------------

class TestDetectedApp:
    def test_to_dict_round_trip(self):
        app = DetectedApp(name="Ableton Live", path=Path("/Applications/Ableton.app"),
                          connector_target="ableton")
        d = app.to_dict()
        restored = DetectedApp.from_dict(d)
        assert restored.name == app.name
        assert restored.path == app.path
        assert restored.connector_target == app.connector_target

    def test_to_dict_has_expected_keys(self):
        app = DetectedApp(name="REAPER", path=Path("/Applications/REAPER.app"),
                          connector_target="reaper")
        d = app.to_dict()
        assert set(d.keys()) == {"name", "path", "connector_target"}

    def test_path_field_is_path_object(self):
        app = DetectedApp.from_dict(
            {"name": "OBS Studio", "path": "/Applications/OBS.app",
             "connector_target": "obs"}
        )
        assert isinstance(app.path, Path)


# ---------------------------------------------------------------------------
# detect_installed_apps — basic contract
# ---------------------------------------------------------------------------

class TestDetectInstalledApps:
    def test_returns_list(self, tmp_user_data):
        result = detect_installed_apps(force=True)
        assert isinstance(result, list)

    def test_does_not_raise(self, tmp_user_data):
        """Must never raise regardless of platform."""
        # call twice — second goes through cache
        detect_installed_apps(force=True)
        detect_installed_apps()

    def test_each_element_is_detected_app(self, tmp_user_data):
        for app in detect_installed_apps(force=True):
            assert isinstance(app, DetectedApp)
            assert app.name
            assert app.connector_target

    def test_returns_empty_list_on_bad_platform(self, tmp_user_data, monkeypatch):
        """If all platform detection raises, result is []."""
        monkeypatch.setattr(dd, "_detect_macos",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(dd, "_detect_windows",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(dd, "_detect_linux",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))

        # Patch platform so the right branch is exercised with a broken detector
        original_platform = sys.platform
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(dd, "_detect_macos",
                            lambda *a, **kw: 1 / 0)  # ZeroDivisionError
        result = detect_installed_apps(force=True)
        assert result == []


# ---------------------------------------------------------------------------
# macOS path detection via monkeypatch
# ---------------------------------------------------------------------------

class TestMacOSDetection:
    def test_ableton_glob_returns_detected_app(self, tmp_path):
        """Fake /Applications/ with an Ableton Live app and verify detection."""
        fake_applications = tmp_path / "Applications"
        fake_applications.mkdir()
        ableton_app = fake_applications / "Ableton Live 11 Suite.app"
        ableton_app.mkdir()

        results = dd._detect_macos(applications_dir=fake_applications)
        names = [r.name for r in results]
        assert "Ableton Live" in names

    def test_ableton_connector_target_is_ableton(self, tmp_path):
        fake_applications = tmp_path / "Applications"
        fake_applications.mkdir()
        (fake_applications / "Ableton Live 12 Suite.app").mkdir()

        results = dd._detect_macos(applications_dir=fake_applications)
        ableton = next(r for r in results if r.name == "Ableton Live")
        assert ableton.connector_target == "ableton"

    def test_ableton_path_is_path_object(self, tmp_path):
        fake_applications = tmp_path / "Applications"
        fake_applications.mkdir()
        app_path = fake_applications / "Ableton Live 11.app"
        app_path.mkdir()

        results = dd._detect_macos(applications_dir=fake_applications)
        ableton = next(r for r in results if r.name == "Ableton Live")
        assert isinstance(ableton.path, Path)
        assert ableton.path == app_path

    def test_resolume_arena_detected(self, tmp_path):
        fake_applications = tmp_path / "Applications"
        fake_applications.mkdir()
        (fake_applications / "Resolume Arena.app").mkdir()

        results = dd._detect_macos(applications_dir=fake_applications)
        slugs = [r.connector_target for r in results]
        assert "resolume" in slugs

    def test_touchdesigner_detected(self, tmp_path):
        fake_applications = tmp_path / "Applications"
        fake_applications.mkdir()
        (fake_applications / "TouchDesigner.app").mkdir()

        results = dd._detect_macos(applications_dir=fake_applications)
        names = [r.name for r in results]
        assert "TouchDesigner" in names

    def test_empty_applications_returns_empty(self, tmp_path):
        fake_applications = tmp_path / "EmptyApps"
        fake_applications.mkdir()
        assert dd._detect_macos(applications_dir=fake_applications) == []

    def test_missing_applications_returns_empty(self, tmp_path):
        non_existent = tmp_path / "DoesNotExist"
        assert dd._detect_macos(applications_dir=non_existent) == []

    def test_no_duplicate_entries_for_same_app(self, tmp_path):
        """Even if two Ableton versions exist, only one entry per type."""
        fake_applications = tmp_path / "Applications"
        fake_applications.mkdir()
        (fake_applications / "Ableton Live 11.app").mkdir()
        (fake_applications / "Ableton Live 12.app").mkdir()

        results = dd._detect_macos(applications_dir=fake_applications)
        ableton_count = sum(1 for r in results if r.name == "Ableton Live")
        assert ableton_count == 1


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

class TestCache:
    def test_cache_written_after_scan(self, tmp_user_data, tmp_path):
        detect_installed_apps(force=True)
        assert dd._cache_path().exists()

    def test_cache_returned_on_second_call(self, tmp_user_data, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        fake_apps = tmp_path if hasattr(self, "_tmp") else Path("/nonexistent_test_apps")
        # Prime the cache with a known value
        apps = [DetectedApp(name="FakeApp", path=Path("/fake"),
                            connector_target="fake")]
        dd._save_cache(apps)

        # Swap the real detector to prove we're reading from cache, not re-scanning
        monkeypatch.setattr(dd, "_detect_macos", lambda *a, **kw: [])
        result = detect_installed_apps(force=False)
        assert any(a.name == "FakeApp" for a in result)

    def test_stale_cache_triggers_rescan(self, tmp_user_data, monkeypatch):
        """Cache older than 24 h must be ignored."""
        stale_time = (datetime.now() - timedelta(hours=25)).isoformat()
        payload = {
            "cached_at": stale_time,
            "apps": [{"name": "StaleApp", "path": "/stale",
                      "connector_target": "stale"}],
        }
        dd._cache_path().write_text(json.dumps(payload))

        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(dd, "_detect_macos", lambda *a, **kw: [])
        result = detect_installed_apps(force=False)
        assert not any(a.name == "StaleApp" for a in result)

    def test_corrupt_cache_triggers_rescan(self, tmp_user_data, monkeypatch):
        dd._cache_path().write_text("not valid json {{{{")
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(dd, "_detect_macos", lambda *a, **kw: [])
        result = detect_installed_apps(force=False)
        assert isinstance(result, list)
