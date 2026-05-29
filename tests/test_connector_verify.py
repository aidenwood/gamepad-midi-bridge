"""Tests for Connector.verify() — the self-test probe added in connector_verify feature.

Covers:
  - missing path  → 'missing'
  - existing path → 'verified'
  - stale mtime   → 'outdated'
  - all 7 shipped connectors respond with a known status string
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from gamepad_midi_bridge.connectors.base import (
    Connector,
    HostInstallation,
    STALE_THRESHOLD_SECONDS,
)
from gamepad_midi_bridge.connectors.ableton import AbletonConnector
from gamepad_midi_bridge.connectors.resolume import ResolumeConnector
from gamepad_midi_bridge.connectors.touchdesigner import TouchDesignerConnector
from gamepad_midi_bridge.connectors.vdmx import VDMXConnector
from gamepad_midi_bridge.connectors.madmapper import MadMapperConnector
from gamepad_midi_bridge.connectors.reaper import ReaperConnector
from gamepad_midi_bridge.connectors.obs import ObsConnector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_host(config_dir: Path) -> HostInstallation:
    return HostInstallation(
        name="Test App",
        version="1",
        config_dir=config_dir,
        extra={},
    )


def _fresh_file(path: Path) -> Path:
    """Create a file with mtime = now."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok", encoding="utf-8")
    return path


def _stale_file(path: Path, age_seconds: int = STALE_THRESHOLD_SECONDS + 1) -> Path:
    """Create a file then wind its mtime back so it appears stale."""
    _fresh_file(path)
    stale_time = time.time() - age_seconds
    os.utime(str(path), (stale_time, stale_time))
    return path


# ---------------------------------------------------------------------------
# Base Connector — verify() logic via _installed_file override
# ---------------------------------------------------------------------------

class _SimpleConnector(Connector):
    """Minimal connector that points verify() at a single configurable file."""
    display_name = "Simple"
    slug = "simple"

    def __init__(self, target_file: Path) -> None:
        self._target = target_file

    def detect(self):
        return []

    def install(self, host):
        ...

    def uninstall(self, host):
        ...

    def is_installed(self, host):
        return self._target.exists()

    def _installed_file(self, host):
        return self._target


def test_verify_missing_returns_missing(tmp_path):
    f = tmp_path / "subdir" / "mapping.xml"
    c = _SimpleConnector(f)
    status, details = c.verify(_make_host(tmp_path))
    assert status == "missing"
    assert str(f) in details


def test_verify_fresh_file_returns_verified(tmp_path):
    f = tmp_path / "mapping.xml"
    _fresh_file(f)
    c = _SimpleConnector(f)
    status, details = c.verify(_make_host(tmp_path))
    assert status == "verified"
    assert str(f) in details


def test_verify_stale_file_returns_outdated(tmp_path):
    f = tmp_path / "mapping.xml"
    _stale_file(f)
    c = _SimpleConnector(f)
    status, details = c.verify(_make_host(tmp_path))
    assert status == "outdated"
    assert "day" in details


def test_verify_custom_threshold_respected(tmp_path):
    """A file 10 s old should be 'verified' with threshold=60 but 'outdated' with threshold=5."""
    f = tmp_path / "mapping.xml"
    _stale_file(f, age_seconds=10)
    c = _SimpleConnector(f)

    assert c.verify(_make_host(tmp_path), stale_threshold=60)[0] == "verified"
    assert c.verify(_make_host(tmp_path), stale_threshold=5)[0] == "outdated"


# ---------------------------------------------------------------------------
# Base Connector — fallback path (no _installed_file override)
# ---------------------------------------------------------------------------

class _FallbackConnector(Connector):
    """Connector that relies on is_installed() — no _installed_file()."""
    display_name = "Fallback"
    slug = "fallback"

    def __init__(self, installed: bool) -> None:
        self._installed = installed

    def detect(self):
        return []

    def install(self, host):
        ...

    def uninstall(self, host):
        ...

    def is_installed(self, host):
        return self._installed


def test_verify_fallback_installed(tmp_path):
    c = _FallbackConnector(installed=True)
    status, _ = c.verify(_make_host(tmp_path))
    assert status == "verified"


def test_verify_fallback_not_installed(tmp_path):
    c = _FallbackConnector(installed=False)
    status, _ = c.verify(_make_host(tmp_path))
    assert status == "missing"


# ---------------------------------------------------------------------------
# All 7 shipped connectors — missing path → 'missing'
# ---------------------------------------------------------------------------

SHIPPED_CONNECTORS = [
    AbletonConnector,
    ResolumeConnector,
    TouchDesignerConnector,
    VDMXConnector,
    MadMapperConnector,
    ReaperConnector,
    ObsConnector,
]


@pytest.mark.parametrize("ConnectorClass", SHIPPED_CONNECTORS,
                         ids=[c.__name__ for c in SHIPPED_CONNECTORS])
def test_shipped_connector_missing_path(tmp_path, ConnectorClass):
    """When config_dir is empty the connector must report 'missing'."""
    c = ConnectorClass()
    host = _make_host(tmp_path / "empty_config")
    status, _ = c.verify(host)
    assert status == "missing"


# ---------------------------------------------------------------------------
# All 7 shipped connectors — placed file → 'verified'
# ---------------------------------------------------------------------------

def _place_installed_file(connector: Connector, host: HostInstallation) -> Path:
    """Create whatever file the connector expects at the install path."""
    f = connector._installed_file(host)
    if f is not None:
        _fresh_file(f)
        return f
    # Fallback connectors that don't implement _installed_file aren't tested here.
    pytest.skip("connector has no _installed_file()")


@pytest.mark.parametrize("ConnectorClass", SHIPPED_CONNECTORS,
                         ids=[c.__name__ for c in SHIPPED_CONNECTORS])
def test_shipped_connector_fresh_file_verified(tmp_path, ConnectorClass):
    c = ConnectorClass()
    host = _make_host(tmp_path / "config")
    _place_installed_file(c, host)
    status, _ = c.verify(host)
    assert status == "verified"


@pytest.mark.parametrize("ConnectorClass", SHIPPED_CONNECTORS,
                         ids=[c.__name__ for c in SHIPPED_CONNECTORS])
def test_shipped_connector_stale_file_outdated(tmp_path, ConnectorClass):
    c = ConnectorClass()
    host = _make_host(tmp_path / "config")
    f = connector_installed_file_or_skip(c, host)
    _stale_file(f)
    status, _ = c.verify(host)
    assert status == "outdated"


def connector_installed_file_or_skip(connector: Connector, host: HostInstallation) -> Path:
    f = connector._installed_file(host)
    if f is None:
        pytest.skip("connector has no _installed_file()")
    return f


# ---------------------------------------------------------------------------
# Verify returns known status strings
# ---------------------------------------------------------------------------

def test_verify_status_values_are_known_strings(tmp_path):
    allowed = {"verified", "outdated", "missing"}
    f = tmp_path / "x.xml"
    c = _SimpleConnector(f)

    # missing
    assert c.verify(_make_host(tmp_path))[0] in allowed

    # verified
    _fresh_file(f)
    assert c.verify(_make_host(tmp_path))[0] in allowed

    # outdated
    _stale_file(f)
    assert c.verify(_make_host(tmp_path))[0] in allowed
