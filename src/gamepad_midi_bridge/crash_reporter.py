"""Lightweight crash reporter — writes a dated crash file users can attach
to bug reports. Never phones home; opt-in telemetry has its own path.
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Type

from . import __version__
from .paths import user_data_dir


def crash_dir() -> Path:
    d = user_data_dir() / "crashes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_report(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    tb,
) -> Path:
    """Write a single crash report. Returns the file path."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = crash_dir() / f"crash-{stamp}.txt"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"Gamepad MIDI Bridge crash report\n")
        f.write(f"version: {__version__}\n")
        f.write(f"python:  {sys.version}\n")
        f.write(f"platform:{sys.platform}\n")
        f.write(f"when:    {datetime.now(timezone.utc).isoformat()}\n")
        f.write("=" * 60 + "\n")
        traceback.print_exception(exc_type, exc_value, tb, file=f)
    return path


def install_hook() -> None:
    """Replace `sys.excepthook` so unhandled errors land in a file."""
    previous = sys.excepthook

    def hook(exc_type, exc_value, tb) -> None:
        try:
            path = write_report(exc_type, exc_value, tb)
            sys.stderr.write(f"\nCrash report saved to {path}\n")
        except Exception:
            pass
        # Chain to the previous hook so the OS still sees the failure.
        if previous is not None and previous is not sys.__excepthook__:
            try:
                previous(exc_type, exc_value, tb)
            except Exception:
                pass
        sys.__excepthook__(exc_type, exc_value, tb)

    sys.excepthook = hook
