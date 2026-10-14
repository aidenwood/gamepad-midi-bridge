"""Decision logic for the Windows helper-app auto-launch.

The launch itself can't run off Windows, but the decide-what-to-launch logic is
injectable, so we verify it here on any platform.
"""
from __future__ import annotations

from gamepad_midi_bridge import windows_sidecar as ws
from gamepad_midi_bridge.windows_sidecar import (
    HelperApp, ensure_helper, ensure_helpers_running,
)


def _app(tmp_exe):
    return HelperApp(label="loopMIDI", process_name="loopMIDI.exe",
                     candidate_paths=(str(tmp_exe),))


def test_skips_launch_when_already_running(tmp_path):
    exe = tmp_path / "loopMIDI.exe"
    exe.write_text("x")
    launched = []
    status = ensure_helper(
        _app(exe),
        is_running=lambda _name: True,
        launcher=lambda p: launched.append(p),
    )
    assert launched == []
    assert "already running" in status


def test_launches_when_installed_and_not_running(tmp_path):
    exe = tmp_path / "loopMIDI.exe"
    exe.write_text("x")
    launched = []
    status = ensure_helper(
        _app(exe),
        is_running=lambda _name: False,
        launcher=lambda p: launched.append(p),
    )
    assert launched == [str(exe)]
    assert "launched" in status


def test_reports_not_installed_when_no_exe(tmp_path):
    missing = tmp_path / "nope.exe"
    launched = []
    status = ensure_helper(
        HelperApp("DS4Windows", "DS4Windows.exe", (str(missing),)),
        is_running=lambda _name: False,
        launcher=lambda p: launched.append(p),
    )
    assert launched == []
    assert "not installed" in status


def test_ds4_opt_in(tmp_path, monkeypatch):
    # Off Windows ensure_helpers_running no-ops, so force the platform.
    monkeypatch.setattr(ws.sys, "platform", "win32")
    seen = []
    ensure_helpers_running(
        launch_ds4=False,
        is_running=lambda name: seen.append(name) or False,
        launcher=lambda p: None,
    )
    assert "loopMIDI.exe" in seen
    assert "DS4Windows.exe" not in seen  # opt-in only

    seen.clear()
    ensure_helpers_running(
        launch_ds4=True,
        is_running=lambda name: seen.append(name) or False,
        launcher=lambda p: None,
    )
    assert "DS4Windows.exe" in seen


def test_noop_off_windows(monkeypatch):
    monkeypatch.setattr(ws.sys, "platform", "darwin")
    assert ensure_helpers_running(launch_ds4=True) == []
