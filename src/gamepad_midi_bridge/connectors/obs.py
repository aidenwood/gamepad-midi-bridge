"""OBS Studio connector via obs-websocket.

OBS Studio (28+) ships with obs-websocket v5 built in. We don't write
into OBS's scene-collection files (too fragile and OBS rewrites them
on every save) — instead we drop a standalone helper script the user
runs alongside OBS that listens for our MIDI and translates it into
obs-websocket calls.

Detection: scan for an OBS install. We don't need OBS to be running at
install time, just present.

Install: write the helper script + a one-page README into a
`Gamepad MIDI Bridge` subfolder of the user's Documents. The README
tells them how to configure their obs-websocket password.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from .base import Connector, HostInstallation, InstallResult, documents_dir


SUBFOLDER = "Gamepad MIDI Bridge (OBS)"
HELPER_NAME = "obs_bridge_helper.py"
README_NAME = "README.md"
TEMPLATE_FILENAME = "obs_helper.py"


class ObsConnector(Connector):
    display_name = "OBS Studio"
    slug = "obs"
    description = (
        "Drop a Python helper script you run alongside OBS. It listens to "
        "the bridge's MIDI port and triggers scene switches, mute toggles, "
        "and source visibility via obs-websocket."
    )

    # ------------------------------------------------ detection

    def detect(self) -> List[HostInstallation]:
        candidates = self._candidate_paths()
        out: List[HostInstallation] = []
        for path in candidates:
            if not path.exists():
                continue
            dest = documents_dir() / SUBFOLDER
            out.append(HostInstallation(
                name="OBS Studio",
                version="28+",
                config_dir=dest,
                extra={"obs_app_path": str(path)},
            ))
            break   # one entry is enough; we don't care which install
        return out

    def _candidate_paths(self) -> List[Path]:
        if sys.platform == "darwin":
            return [Path("/Applications/OBS.app")]
        if sys.platform == "win32":
            import os
            program_files = [
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
                Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
            ]
            return [pf / "obs-studio" / "bin" / "64bit" / "obs64.exe"
                    for pf in program_files]
        # Linux — Flatpak + native installs both expose `obs` on PATH.
        return [Path("/usr/bin/obs"), Path("/usr/local/bin/obs")]

    # ------------------------------------------------ install

    def install(self, host: HostInstallation) -> InstallResult:
        try:
            host.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return InstallResult(False, None, f"Couldn't create {host.config_dir}: {e}")

        template = _template_path(TEMPLATE_FILENAME)
        if not template.exists():
            return InstallResult(
                False, None,
                f"Template missing — {template.name} not bundled with this build.",
            )

        helper_dest = host.config_dir / HELPER_NAME
        readme_dest = host.config_dir / README_NAME
        try:
            helper_dest.write_bytes(template.read_bytes())
            readme_dest.write_text(_README_BODY, encoding="utf-8")
        except Exception as e:
            return InstallResult(False, None, f"Couldn't write helper: {e}")

        return InstallResult(
            True, helper_dest,
            f"Helper written to {helper_dest}. Read the README next to it.",
        )

    def uninstall(self, host: HostInstallation) -> InstallResult:
        helper = host.config_dir / HELPER_NAME
        readme = host.config_dir / README_NAME
        removed = False
        for f in (helper, readme):
            if f.exists():
                try:
                    f.unlink()
                    removed = True
                except Exception:
                    pass
        return InstallResult(removed, helper if removed else None,
                             "Removed helper script." if removed else "Nothing to remove.")

    def is_installed(self, host: HostInstallation) -> bool:
        return (host.config_dir / HELPER_NAME).exists()

    def post_install_steps(self, host: HostInstallation) -> str:
        return (
            "1. Open OBS → Tools → WebSocket Server Settings.\n"
            "2. Enable + note the password.\n"
            f"3. Open {host.config_dir / HELPER_NAME} in a terminal:\n"
            "     python obs_bridge_helper.py --password <password>\n"
            "4. Keep the helper running while you perform.\n"
            "5. Face buttons cycle scenes; D-pad mutes/unmutes Mic; "
            "L1/R1 toggle camera source visibility."
        )


_README_BODY = """# Gamepad MIDI Bridge — OBS helper

This Python script bridges MIDI from "Gamepad MIDI Bridge" into your
running OBS instance via obs-websocket v5.

## Prereqs

```
pip install obsws-python==1.6.* python-rtmidi==1.5.*
```

OBS 28 or newer ships with obs-websocket built in. Enable it in
Tools → WebSocket Server Settings and copy the password.

## Run

```
python obs_bridge_helper.py --password YOUR_OBS_PASSWORD
```

Optional flags:

- `--host` — default 127.0.0.1
- `--port` — default 4455 (obs-websocket default)
- `--midi-port` — substring of the MIDI port name to listen on
                   (default: "Gamepad MIDI Bridge")

## What's mapped

- **Face buttons 0-3** → cycle through your first four scenes
- **Shoulder buttons (4 = L1, 5 = R1)** → toggle visibility of the first
  source in the current scene (typically your camera overlay)
- **D-pad up / down** → mute / unmute the first audio source
- **D-pad left / right** → previous / next scene

Edit the `ACTIONS` dict at the top of the helper to change the bindings.
"""


def _template_path(filename: str) -> Path:
    return Path(__file__).parent / "templates" / filename
