"""Connector registry. Add new hosts here."""
from __future__ import annotations

from typing import List

from .base import Connector, HostInstallation, InstallResult
from .resolume import ResolumeConnector
from .ableton import AbletonConnector


def all_connectors() -> List[Connector]:
    """Return one instance of every available connector."""
    return [
        ResolumeConnector(),
        AbletonConnector(),
    ]


__all__ = [
    "Connector",
    "HostInstallation",
    "InstallResult",
    "ResolumeConnector",
    "AbletonConnector",
    "all_connectors",
]
