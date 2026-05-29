"""Tests for crash reporter bundle export."""
import json
import zipfile
from pathlib import Path
from gamepad_midi_bridge.crash_reporter import export_bundle, _redact_sensitive


def test_export_bundle_creates_zip(tmp_path, monkeypatch):
    """export_bundle creates a valid zip file on Desktop."""
    # Mock user_data_dir and Path.home to use tmp_path
    def mock_user_data_dir():
        user_data = tmp_path / "Application Support" / "Universal Controller MIDI"
        user_data.mkdir(parents=True, exist_ok=True)
        return user_data
    
    def mock_home():
        return tmp_path
    
    monkeypatch.setattr("gamepad_midi_bridge.crash_reporter.user_data_dir", mock_user_data_dir)
    monkeypatch.setattr(Path, "home", mock_home)
    
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    
    # Create some dummy data to bundle
    user_data = mock_user_data_dir()
    crashes = user_data / "crashes"
    crashes.mkdir(parents=True, exist_ok=True)
    
    # Write a dummy crash file
    crash_file = crashes / "crash-20260101-120000.txt"
    crash_file.write_text("Test crash report")
    
    # Call export_bundle
    bundle_path = export_bundle()
    
    # Verify zip was created
    assert bundle_path.exists()
    assert bundle_path.suffix == ".zip"
    assert bundle_path.parent == desktop
    
    # Verify contents
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        assert any("crash-" in n for n in names), "No crash files in bundle"


def test_redaction_removes_sensitive_keys():
    """_redact_sensitive replaces sensitive values with [REDACTED]."""
    config_json = json.dumps({
        "email": "user@example.com",
        "license_key": "abc123xyz",
        "stripe_api_key": "sk_live_12345",
        "api_token": "secret_token_here",
        "safe_field": "this_is_ok"
    })
    
    redacted = _redact_sensitive(config_json)
    
    # Sensitive values should be redacted
    assert "[REDACTED]" in redacted
    assert "user@example.com" not in redacted
    assert "abc123xyz" not in redacted
    assert "sk_live_12345" not in redacted
    assert "secret_token_here" not in redacted
    
    # Safe field should remain unchanged or have its value redacted depending on key name
    assert "safe_field" in redacted


def test_redaction_preserves_safe_keys():
    """_redact_sensitive preserves safe configuration keys."""
    config_json = json.dumps({
        "poll_rate": 100,
        "midi_channel": 1,
        "version": "1.0",
        "safe_string": "some_value"
    })
    
    redacted = _redact_sensitive(config_json)
    
    # Safe keys should mostly be preserved
    assert "poll_rate" in redacted
    assert "midi_channel" in redacted
    assert "version" in redacted


def test_export_bundle_graceful_missing_files(tmp_path, monkeypatch):
    """export_bundle handles missing crashes/logs gracefully."""
    # Mock user_data_dir and Path.home to use tmp_path
    def mock_user_data_dir():
        user_data = tmp_path / "Application Support" / "Universal Controller MIDI"
        user_data.mkdir(parents=True, exist_ok=True)
        return user_data
    
    def mock_home():
        return tmp_path
    
    monkeypatch.setattr("gamepad_midi_bridge.crash_reporter.user_data_dir", mock_user_data_dir)
    monkeypatch.setattr(Path, "home", mock_home)
    
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    
    # Don't create any crash or log files — test that export still works
    bundle_path = export_bundle()
    
    # Verify zip was created even without crashes
    assert bundle_path.exists()
    assert bundle_path.suffix == ".zip"
    
    # Bundle may be empty or minimal, but should be a valid zip
    with zipfile.ZipFile(bundle_path, "r") as zf:
        # Should at least not raise an error on read
        names = zf.namelist()
        assert isinstance(names, list)
