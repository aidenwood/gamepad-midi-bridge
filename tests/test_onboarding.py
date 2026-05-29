"""Tests for OnboardingWizard — creation, step list, and new feature CTAs.

Requires PySide6 + a QApplication singleton. Uses the same _make_qapp()
pattern as test_capture_dialog to avoid the pytest-qt dependency.
"""
from __future__ import annotations

import sys
import pytest

pyside6 = pytest.importorskip("PySide6", reason="PySide6 not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_qapp():
    """Return (or create) the singleton QApplication."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _make_wizard(tmp_path, monkeypatch, worker=None):
    """Construct a wizard redirected to a temp config dir."""
    from gamepad_midi_bridge import paths as paths_mod

    def fake_user_data_dir():
        d = tmp_path / "user_data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(paths_mod, "user_data_dir", fake_user_data_dir)
    _make_qapp()
    from gamepad_midi_bridge.ui.onboarding import OnboardingWizard
    return OnboardingWizard(worker=worker)


class _FakeWorker:
    def __init__(self):
        self.calls: list = []

    def open_axis_editor(self, axis_index: int) -> None:
        self.calls.append(("open_axis_editor", axis_index))

    def open_settings(self, tab: str) -> None:
        self.calls.append(("open_settings", tab))

    def load_mapping(self, mapping) -> None:
        self.calls.append(("load_mapping", mapping))


class _BrokenWorker:
    def open_axis_editor(self, **_):
        raise RuntimeError("simulated error")

    def open_settings(self, **_):
        raise RuntimeError("simulated error")

    def load_mapping(self, _):
        raise RuntimeError("simulated error")


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------

def test_wizard_creation_does_not_crash(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    assert w is not None
    w.close()


def test_wizard_has_ten_steps(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    assert w._stack.count() == 10
    w.close()


# ---------------------------------------------------------------------------
# New feature steps present in expected positions
# ---------------------------------------------------------------------------

def test_trigger_modes_step_exists(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    assert w._stack.widget(5) is not None
    w.close()


def test_adaptive_haptics_step_exists(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    assert w._stack.widget(6) is not None
    w.close()


def test_polar_stick_step_exists(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    assert w._stack.widget(7) is not None
    w.close()


def test_multizone_touchpad_step_exists(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    assert w._stack.widget(8) is not None
    w.close()


def test_done_step_is_last(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    assert w._stack.widget(w._stack.count() - 1) is not None
    w.close()


# ---------------------------------------------------------------------------
# "Try it now" callbacks — no crash when worker is None
# ---------------------------------------------------------------------------

def test_try_trigger_modes_no_crash_without_worker(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    w._try_trigger_modes()
    w.close()


def test_try_adaptive_haptics_no_crash_without_worker(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    w._try_adaptive_haptics()
    w.close()


def test_try_polar_stick_no_crash_without_worker(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    w._try_polar_stick()
    w.close()


def test_try_drum_pad_template_no_crash_without_worker(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch)
    w._try_drum_pad_template()
    w.close()


# ---------------------------------------------------------------------------
# "Try it now" callbacks dispatch correct calls to worker
# ---------------------------------------------------------------------------

def test_try_trigger_modes_calls_open_axis_editor(tmp_path, monkeypatch):
    worker = _FakeWorker()
    w = _make_wizard(tmp_path, monkeypatch, worker=worker)
    w._try_trigger_modes()
    w.close()
    assert ("open_axis_editor", 4) in worker.calls


def test_try_adaptive_haptics_calls_open_settings(tmp_path, monkeypatch):
    worker = _FakeWorker()
    w = _make_wizard(tmp_path, monkeypatch, worker=worker)
    w._try_adaptive_haptics()
    w.close()
    assert ("open_settings", "haptics") in worker.calls


def test_try_polar_stick_calls_open_axis_editor(tmp_path, monkeypatch):
    worker = _FakeWorker()
    w = _make_wizard(tmp_path, monkeypatch, worker=worker)
    w._try_polar_stick()
    w.close()
    assert ("open_axis_editor", 0) in worker.calls


def test_try_drum_pad_template_calls_load_mapping(tmp_path, monkeypatch):
    from gamepad_midi_bridge.mapping import Mapping
    worker = _FakeWorker()
    w = _make_wizard(tmp_path, monkeypatch, worker=worker)
    w._try_drum_pad_template()
    w.close()
    load_calls = [c for c in worker.calls if c[0] == "load_mapping"]
    assert len(load_calls) == 1
    assert isinstance(load_calls[0][1], Mapping)
    assert load_calls[0][1].name == "Drum Pad"


def test_try_drum_pad_template_kick_is_mapped(tmp_path, monkeypatch):
    """Drum Pad template loaded via wizard has Cross → GM Kick (note 36)."""
    worker = _FakeWorker()
    w = _make_wizard(tmp_path, monkeypatch, worker=worker)
    w._try_drum_pad_template()
    w.close()
    mapping = [c for c in worker.calls if c[0] == "load_mapping"][0][1]
    assert mapping.buttons[0] == 36


# ---------------------------------------------------------------------------
# Worker raising exceptions doesn't propagate
# ---------------------------------------------------------------------------

def test_try_callbacks_survive_worker_exceptions(tmp_path, monkeypatch):
    w = _make_wizard(tmp_path, monkeypatch, worker=_BrokenWorker())
    w._try_trigger_modes()
    w._try_adaptive_haptics()
    w._try_polar_stick()
    w._try_drum_pad_template()
    w.close()
