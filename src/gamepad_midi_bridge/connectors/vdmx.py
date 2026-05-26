"""VDMX workspace template connector.

VDMX is mac-only — no Windows or Linux build exists. We write a workspace
template into VDMX's user templates folder so the user can pick it from the
File → Open Template menu and land on a workspace pre-wired to the bridge's
virtual MIDI port.

Install path:
    ~/Documents/VDMX/Templates/Universal Controller MIDI.vdmx5

VDMX5 files are plist-based XML. We build a minimal valid plist programmatically
via `plistlib` rather than shipping a binary blob — easier to maintain and
inspect, and avoids carrying a 100KB sample workspace in the repo. The plist
declares a MIDI input control source + 8 sliders bound to CCs 1–6 + the first
four face buttons bound to clip launch in Layer 1.
"""
from __future__ import annotations

import plistlib
import re
import sys
from pathlib import Path
from typing import List

from .base import Connector, HostInstallation, InstallResult


TEMPLATE_FILENAME = "Universal Controller MIDI.vdmx5"


class VDMXConnector(Connector):
    display_name = "VDMX"
    slug = "vdmx"
    description = (
        "Drop a workspace template into VDMX's Templates folder. Open it via "
        "File → Open Template. Sliders pre-bound to triggers + sticks; first "
        "four clip cells bound to face buttons."
    )

    # ------------------------------------------------ detection

    def detect(self) -> List[HostInstallation]:
        """Mac-only. Scan /Applications for VDMX*.app."""
        if sys.platform != "darwin":
            return []

        apps_dir = Path("/Applications")
        if not apps_dir.exists():
            return []

        templates_dir = Path.home() / "Documents" / "VDMX" / "Templates"

        found: List[HostInstallation] = []
        pattern = re.compile(r"^VDMX(\d*)\.app$")
        for app in sorted(apps_dir.iterdir()):
            match = pattern.match(app.name)
            if not match:
                continue
            version = match.group(1) or "5"
            found.append(HostInstallation(
                name=app.stem,
                version=version,
                config_dir=templates_dir,
                extra={"app_path": str(app)},
            ))
        return found

    # ------------------------------------------------ install

    def install(self, host: HostInstallation) -> InstallResult:
        try:
            host.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't create {host.config_dir}: {e}")

        dest = host.config_dir / TEMPLATE_FILENAME
        try:
            with dest.open("wb") as f:
                plistlib.dump(_build_workspace_plist(), f)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't write {dest}: {e}")

        return InstallResult(
            True, dest,
            f"Installed for {host.name}. Open VDMX and pick 'Gamepad MIDI "
            "Bridge' from File → Open Template.",
        )

    def uninstall(self, host: HostInstallation) -> InstallResult:
        dest = host.config_dir / TEMPLATE_FILENAME
        if not dest.exists():
            return InstallResult(True, None, f"Nothing to remove for {host.name}.")
        try:
            dest.unlink()
        except Exception as e:
            return InstallResult(False, None, f"Couldn't remove {dest}: {e}")
        return InstallResult(True, dest, f"Removed template from {host.name}.")

    def is_installed(self, host: HostInstallation) -> bool:
        return (host.config_dir / TEMPLATE_FILENAME).exists()

    def post_install_steps(self, host: HostInstallation) -> str:
        return (
            "1. Open VDMX.\n"
            "2. File → Open Template → pick 'Universal Controller MIDI'.\n"
            "3. Workspace loads with the bridge virtual MIDI port as input "
            "and controls pre-mapped.\n"
            "4. If the port isn't auto-selected, open Workspace Inspector → "
            "MIDI and pick 'Universal Controller MIDI'."
        )


# --------------------------------------------------------------- workspace plist

def _build_workspace_plist() -> dict:
    """Build a minimal VDMX5 workspace dict.

    VDMX5 files declare an array of "plugins" — each one a control surface,
    layer, MIDI input source, etc. We declare:
      - one MIDI input source listening to 'Universal Controller MIDI'
      - one slider plugin with 8 sliders bound to CCs 1, 2, 3, 4, 5, 6, 16, 17
      - one Layer Source plugin with the first 4 clip slots bound to notes 60-65

    Schema is reverse-engineered from a saved VDMX template; flagged
    medium-confidence — real VDMX may demand additional `version`/`uuid`
    fields. Users can re-save the workspace to canonicalise.
    """
    midi_source = {
        "pluginClass": "MIDIInputSourcePlugin",
        "name": "Universal Controller MIDI In",
        "midiDeviceName": "Universal Controller MIDI",
        "midiChannel": 1,
    }

    slider_bindings = [
        {"name": "Trigger L",  "cc": 1},
        {"name": "Trigger R",  "cc": 2},
        {"name": "Stick L X",  "cc": 3},
        {"name": "Stick L Y",  "cc": 4},
        {"name": "Stick R X",  "cc": 5},
        {"name": "Stick R Y",  "cc": 6},
        {"name": "Touchpad X", "cc": 16},
        {"name": "Touchpad Y", "cc": 17},
    ]
    sliders_plugin = {
        "pluginClass": "ControlSurfaceSlidersPlugin",
        "name": "Gamepad Sliders",
        "sliders": [
            {
                "name": s["name"],
                "min": 0.0,
                "max": 1.0,
                "value": 0.0,
                "midiReceiver": {
                    "type": "cc",
                    "channel": 1,
                    "cc": s["cc"],
                    "source": "Universal Controller MIDI",
                },
            }
            for s in slider_bindings
        ],
    }

    clip_notes = [60, 62, 64, 65]
    layer_plugin = {
        "pluginClass": "LayerSourcePlugin",
        "name": "Gamepad Layer 1",
        "clips": [
            {
                "slot": i,
                "midiReceiver": {
                    "type": "note",
                    "channel": 1,
                    "note": note,
                    "source": "Universal Controller MIDI",
                },
            }
            for i, note in enumerate(clip_notes)
        ],
    }

    return {
        "version": "5",
        "name": "Universal Controller MIDI",
        "description": "Pre-wired workspace for the Universal Controller MIDI.",
        "plugins": [midi_source, sliders_plugin, layer_plugin],
    }
