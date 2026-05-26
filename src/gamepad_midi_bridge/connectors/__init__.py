"""Connector registry. Add new hosts here."""
from __future__ import annotations

from typing import List

from .base import Connector, HostInstallation, InstallResult
from .resolume import ResolumeConnector
from .ableton import AbletonConnector
from .touchdesigner import TouchDesignerConnector
from .vdmx import VDMXConnector
from .madmapper import MadMapperConnector
from .reaper import ReaperConnector
from .obs import ObsConnector


def all_connectors() -> List[Connector]:
    """Return one instance of every available connector."""
    return [
        ResolumeConnector(),
        AbletonConnector(),
        TouchDesignerConnector(),
        VDMXConnector(),
        MadMapperConnector(),
        ReaperConnector(),
        ObsConnector(),
    ]


__all__ = [
    "Connector",
    "HostInstallation",
    "InstallResult",
    "ResolumeConnector",
    "AbletonConnector",
    "TouchDesignerConnector",
    "VDMXConnector",
    "MadMapperConnector",
    "ReaperConnector",
    "ObsConnector",
    "all_connectors",
]
