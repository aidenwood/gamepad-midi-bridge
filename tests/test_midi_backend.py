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


class _UnopenableMidiOut(_FakeMidiOut):
    """rtmidi that enumerates ports but refuses to open some of them.

    Reproduces the CI failure that blocked the v2.2.0 release: Windows lists
    "Microsoft GS Wavetable Synth 0", but opening it raises

        _rtmidi.SystemError: MidiOutWinMM::openPort: error creating Windows
        MM MIDI output port.

    That is not a MidiPortError, and every caller (including the first-run
    wizard's _poll_midi) only catches MidiPortError — so it escaped and
    crashed the app on startup.
    """

    def __init__(self, ports, unopenable):
        super().__init__(ports)
        self._unopenable = set(unopenable)
        self.attempts = []

    def open_port(self, index):
        self.attempts.append(index)
        if index in self._unopenable:
            raise SystemError(
                "MidiOutWinMM::openPort: error creating Windows MM MIDI "
                "output port."
            )
        self.opened_index = index


def _patch_unopenable(monkeypatch, ports, unopenable):
    fake = _UnopenableMidiOut(ports, unopenable)
    monkeypatch.setattr(midi_backend.rtmidi, "MidiOut", lambda: fake)
    return fake


def test_backend_error_becomes_midi_port_error(win32, monkeypatch):
    """The exact CI crash: the only port exists but will not open."""
    fake = _patch_unopenable(monkeypatch, ["Microsoft GS Wavetable Synth 0"], {0})
    with pytest.raises(MidiPortError) as excinfo:
        open_port()
    # Callers show this text to the user, so it has to name the fix.
    assert "loopMIDI" in str(excinfo.value)
    assert fake.attempts == [0]


def test_falls_through_to_a_port_that_opens(win32, monkeypatch):
    """A dead first choice must not stop us finding a working port."""
    ports = ["Microsoft GS Wavetable Synth 0", "Some USB Synth"]
    fake = _patch_unopenable(monkeypatch, ports, {0})
    opened = open_port()
    assert opened.name == "Some USB Synth"
    assert opened.fallback is True
    assert fake.attempts == [0, 1]


def test_dead_loopmidi_falls_back_to_the_synth(win32, monkeypatch):
    """loopMIDI present but claimed by another app — still make noise."""
    ports = ["loopMIDI Port", "Microsoft GS Wavetable Synth 0"]
    fake = _patch_unopenable(monkeypatch, ports, {0})
    opened = open_port()
    assert opened.name == "Microsoft GS Wavetable Synth 0"
    # Not a routed port, so the UI must show the "no DAW routing" warning.
    assert opened.fallback is True
    assert fake.attempts == [0, 1]


def test_working_loopmidi_is_not_marked_fallback(win32, monkeypatch):
    """Guard the happy path while we're in here."""
    fake = _patch_unopenable(monkeypatch, ["loopMIDI Port", "Other"], set())
    opened = open_port()
    assert opened.name == "loopMIDI Port"
    assert opened.fallback is False
    assert fake.attempts == [0]


def test_never_leaks_a_raw_backend_exception(win32, monkeypatch):
    """Nothing but MidiPortError may escape, whatever rtmidi throws."""
    _patch_unopenable(monkeypatch, ["A", "B", "C"], {0, 1, 2})
    with pytest.raises(MidiPortError):
        open_port()
