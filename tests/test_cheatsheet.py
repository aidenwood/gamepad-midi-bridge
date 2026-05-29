"""Tests for cheatsheet.render_cheatsheet.

QPdfWriter requires a QCoreApplication to be running.  We create a minimal
QApplication once per process via an autouse session-scoped fixture.  This
mirrors the approach used in test_visualise_tab.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# QApplication fixture — required for QPdfWriter
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure a QApplication exists for the whole test session."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    yield app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_mapping():
    from gamepad_midi_bridge.mapping import Mapping
    return Mapping()


def _empty_mapping():
    from gamepad_midi_bridge.mapping import Mapping
    return Mapping(
        name="Empty",
        buttons={},
        axes={},
        hats={},
    )


def _sparse_mapping():
    from gamepad_midi_bridge.mapping import Mapping, ButtonConfig
    m = Mapping(name="Sparse")
    # Only map a couple of buttons and add one button_config
    m.buttons = {0: 36, 3: 48}
    m.axes = {4: 1}  # L2 → CC 1
    m.hats = {}
    m.button_configs = {0: ButtonConfig(gate_button=5, gate_release_value=0)}
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_render_writes_nonempty_file(tmp_path):
    """render_cheatsheet must produce a non-empty file at the given path."""
    from gamepad_midi_bridge.cheatsheet import render_cheatsheet

    out = tmp_path / "test_default.pdf"
    render_cheatsheet(_default_mapping(), out)

    assert out.exists(), "PDF file was not created"
    assert out.stat().st_size > 0, "PDF file is empty"


def test_output_has_pdf_magic_bytes(tmp_path):
    """The output file must start with the %PDF magic string."""
    from gamepad_midi_bridge.cheatsheet import render_cheatsheet

    out = tmp_path / "magic.pdf"
    render_cheatsheet(_default_mapping(), out)

    with out.open("rb") as fh:
        header = fh.read(4)
    assert header == b"%PDF", f"Expected %PDF header, got {header!r}"


def test_empty_mapping_renders_without_crash(tmp_path):
    """A mapping with no buttons/axes/hats must not raise."""
    from gamepad_midi_bridge.cheatsheet import render_cheatsheet

    out = tmp_path / "empty.pdf"
    render_cheatsheet(_empty_mapping(), out)

    assert out.exists()
    assert out.stat().st_size > 0


def test_sparse_button_configs_renders_without_crash(tmp_path):
    """A mapping with partial button_configs must not raise."""
    from gamepad_midi_bridge.cheatsheet import render_cheatsheet

    out = tmp_path / "sparse.pdf"
    render_cheatsheet(_sparse_mapping(), out)

    assert out.exists()
    assert out.stat().st_size > 0
