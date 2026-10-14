"""Tiered Windows MIDI fallback in midi_backend.open_port.

Covers the "instant audible MIDI on Windows" behaviour: loopMIDI wins when
present, otherwise the built-in GS Wavetable synth, otherwise any port, and
only a truly empty port list raises.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import midi_backend
from gamepad_midi_bridge.midi_backend import MidiPortError, open_port


class _FakeMidiOut:
    """Stand-in for rtmidi.MidiOut that records which index was opened."""

    def __init__(self, ports):
        self._ports = ports
        self.opened_index = None
        self.opened_virtual = None

    def get_ports(self):
        return list(self._ports)

    def open_port(self, index):
        self.opened_index = index

    def open_virtual_port(self, name):
        self.opened_virtual = name


@pytest.fixture
def win32(monkeypatch):
    monkeypatch.setattr(midi_backend.sys, "platform", "win32")


def _patch_ports(monkeypatch, ports):
    fake = _FakeMidiOut(ports)
    monkeypatch.setattr(midi_backend.rtmidi, "MidiOut", lambda: fake)
    return fake


def test_prefers_loopmidi_port(win32, monkeypatch):
    ports = ["Microsoft GS Wavetable Synth 0", "Universal Controller MIDI 1"]
    fake = _patch_ports(monkeypatch, ports)
    opened = open_port()
    assert fake.opened_index == 1
    assert opened.virtual is False
    assert opened.fallback is False


def test_auto_detects_default_named_loopmidi_port(win32, monkeypatch):
    # loopMIDI's out-of-the-box port is just called "loopMIDI Port" — we should
    # route to it as a real port (not the GS Wavetable fallback) without a rename.
    ports = ["Microsoft GS Wavetable Synth 0", "loopMIDI Port 1"]
    fake = _patch_ports(monkeypatch, ports)
    opened = open_port()
    assert fake.opened_index == 1
    assert opened.fallback is False
    assert opened.virtual is False


def test_falls_back_to_builtin_synth(win32, monkeypatch):
    ports = ["Some Hardware Synth 0", "Microsoft GS Wavetable Synth 1"]
    fake = _patch_ports(monkeypatch, ports)
    opened = open_port()
    assert fake.opened_index == 1
    assert opened.fallback is True
    assert "Wavetable" in opened.name


def test_falls_back_to_first_port_when_no_synth(win32, monkeypatch):
    ports = ["Some Hardware Synth 0", "Another Device 1"]
    fake = _patch_ports(monkeypatch, ports)
    opened = open_port()
    assert fake.opened_index == 0
    assert opened.fallback is True


def test_raises_only_when_no_ports(win32, monkeypatch):
    _patch_ports(monkeypatch, [])
    with pytest.raises(MidiPortError):
        open_port()


def test_non_windows_creates_virtual_port(monkeypatch):
    monkeypatch.setattr(midi_backend.sys, "platform", "darwin")
    fake = _patch_ports(monkeypatch, [])
    opened = open_port("My Port")
    assert fake.opened_virtual == "My Port"
    assert opened.virtual is True
    assert opened.fallback is False
