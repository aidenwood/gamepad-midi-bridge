"""Cross-platform PyInstaller wrapper.

Run `python build.py` on each OS you want to ship for. Output lands in `dist/`.

Why a custom script instead of a hand-edited .spec file: PyInstaller's per-OS
flags differ enough (mac --windowed, win --noconsole, linux --onefile) that a
single .spec gets ugly fast. This script keeps the per-OS logic in one place.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src" / "gamepad_midi_bridge"
# PyInstaller can't honour package-relative imports when running the bootstrap
# script, so we point it at a tiny wrapper that imports the package properly.
ENTRY = ROOT / "scripts" / "app_entry.py"
RESOURCES = SRC / "resources"
QSS = SRC / "ui" / "styles.qss"
APP_NAME = "Universal Controller MIDI"
APP_ID = "design.aidxn.gamepad-midi-bridge"


def datafile(src: Path, dest: str) -> str:
    """PyInstaller's --add-data uses `:` on macOS/Linux and `;` on Windows."""
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dest}"


def build() -> None:
    system = platform.system()
    dist = ROOT / "dist"
    if dist.exists():
        shutil.rmtree(dist)

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", APP_NAME,
        "--windowed",                    # no terminal window on any OS
        "--add-data", datafile(QSS, "gamepad_midi_bridge/ui"),
    ]

    if RESOURCES.exists() and any(RESOURCES.iterdir()):
        args += ["--add-data", datafile(RESOURCES, "gamepad_midi_bridge/resources")]

    icon = _find_icon(system)
    if icon is not None:
        args += ["--icon", str(icon)]

    if system == "Darwin":
        args += ["--osx-bundle-identifier", APP_ID]
    elif system == "Windows":
        args += ["--noconsole"]
    else:  # Linux
        args += ["--onefile"]

    args.append(str(ENTRY))

    print("Running:", " ".join(args))
    subprocess.check_call(args, cwd=ROOT)
    print(f"\nBuild complete → {dist}")


def _find_icon(system: str) -> Path | None:
    """Pick the right icon format per OS. Missing icons are non-fatal."""
    candidates = {
        "Darwin":  RESOURCES / "icon.icns",
        "Windows": RESOURCES / "icon.ico",
        "Linux":   RESOURCES / "icon.png",
    }
    icon = candidates.get(system)
    return icon if icon and icon.exists() else None


if __name__ == "__main__":
    build()
