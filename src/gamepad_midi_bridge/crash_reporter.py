"""Lightweight crash reporter — writes a dated crash file users can attach
to bug reports. Never phones home; opt-in telemetry has its own path.
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Type
import zipfile
import tempfile
import shutil
import re

from . import __version__
from .paths import user_data_dir


def crash_dir() -> Path:
    d = user_data_dir() / "crashes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def report_text(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    tb,
) -> str:
    """Render the full crash report as a string.

    Split out from ``write_report`` so the crash dialog can show the user the
    exact same text that lands on disk — one definition, two consumers.
    """
    header = (
        "Universal Controller MIDI crash report\n"
        f"version: {__version__}\n"
        f"python:  {sys.version}\n"
        f"platform:{sys.platform}\n"
        f"when:    {datetime.now(timezone.utc).isoformat()}\n"
        + "=" * 60 + "\n"
    )
    body = "".join(traceback.format_exception(exc_type, exc_value, tb))
    return header + body


def write_report(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    tb,
) -> Path:
    """Write a single crash report. Returns the file path."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = crash_dir() / f"crash-{stamp}.txt"
    path.write_text(report_text(exc_type, exc_value, tb), encoding="utf-8")
    return path


def export_bundle() -> Path:
    """Create a zip bundle of crash reports, logs, and sanitised config.
    
    Returns the path to the generated zip file on the Desktop.
    Bundle includes:
      - All crash reports from user_data_dir/crashes/
      - Last 1MB of app.log (truncated if larger)
      - Sanitised config.json (with sensitive keys redacted)
    """
    desktop = Path.home() / "Desktop"
    desktop.mkdir(exist_ok=True)
    
    # Timestamp for filename
    from datetime import datetime
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    bundle_path = desktop / f"crash-bundle-{stamp}.zip"
    
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add crash reports
        crashes_dir = user_data_dir() / "crashes"
        if crashes_dir.exists():
            for crash_file in crashes_dir.glob("*.txt"):
                arcname = f"crashes/{crash_file.name}"
                zf.write(crash_file, arcname=arcname)
        
        # Add last 1MB of app.log
        logs_dir = user_data_dir() / "logs"
        log_file = logs_dir / "app.log" if logs_dir.exists() else None
        if log_file and log_file.exists():
            size = log_file.stat().st_size
            if size > 1024 * 1024:  # > 1MB
                # Read last 1MB
                with open(log_file, "rb") as f:
                    f.seek(-1024*1024, 2)
                    log_content = f.read().decode("utf-8", errors="ignore")
            else:
                log_content = log_file.read_text(encoding="utf-8", errors="ignore")
            
            # Add to zip
            zf.writestr("logs/app.log", log_content)
        
        # Add sanitised config
        config_file = user_data_dir() / "config.json"
        if config_file.exists():
            config_content = config_file.read_text(encoding="utf-8")
            # Redact sensitive keys
            config_content = _redact_sensitive(config_content)
            zf.writestr("config.json", config_content)
    
    return bundle_path


def _redact_sensitive(content: str) -> str:
    """Replace values of sensitive keys with [REDACTED]."""
    # Pattern matches: "anything_with_email_license_token_secret_key_password_stripe_api": "value"
    # Matches any key containing these patterns
    pattern = r'"([^"]*(?:email|license|token|secret|key|password|stripe|api)[^"]*)"\s*:\s*"[^"]*"'
    
    def replace_value(match):
        key_part = match.group(1)  # e.g., 'email' or 'license_key'
        return f'"{key_part}": "[REDACTED]"'
    
    return re.sub(pattern, replace_value, content, flags=re.IGNORECASE)


# Headless / CLI runs must never try to pop a window. ``__main__`` flips this
# off before entering the headless branch.
_gui_dialog_enabled = True

# A crash inside the crash handler would recurse forever. One dialog per
# process is all anyone needs.
_dialog_shown = False


def disable_gui_dialog() -> None:
    """Suppress the crash dialog (headless mode, kiosk rigs, CI)."""
    global _gui_dialog_enabled
    _gui_dialog_enabled = False


def _show_dialog(text: str, path: Optional[Path]) -> None:
    """Best-effort GUI crash dialog. Never raises."""
    global _dialog_shown
    if not _gui_dialog_enabled or _dialog_shown:
        return
    _dialog_shown = True
    try:
        from .ui.crash_dialog import show_crash_dialog
        show_crash_dialog(text, path, __version__)
    except Exception:
        # Qt unavailable or already torn down — the file on disk is still
        # there, and app_entry's native fallback covers import-time failures.
        pass


def install_hook() -> None:
    """Replace `sys.excepthook` so unhandled errors land in a file and a dialog.

    The dialog matters most on Windows: ``build.py`` ships with ``--noconsole``,
    which leaves ``sys.stdout``/``sys.stderr`` as ``None``, so a written-to-disk
    report is invisible to the user. Without the dialog the app simply
    disappears and we get a support email with nothing in it.
    """
    previous = sys.excepthook

    def hook(exc_type, exc_value, tb) -> None:
        text = ""
        path: Optional[Path] = None
        try:
            text = report_text(exc_type, exc_value, tb)
        except Exception:
            pass
        try:
            path = write_report(exc_type, exc_value, tb)
        except Exception:
            pass
        try:
            # `--noconsole` builds have sys.stderr set to None; guard rather
            # than relying on the surrounding except to swallow it.
            if sys.stderr is not None and path is not None:
                sys.stderr.write(f"\nCrash report saved to {path}\n")
        except Exception:
            pass

        if text:
            _show_dialog(text, path)

        # Chain to the previous hook so the OS still sees the failure.
        if previous is not None and previous is not sys.__excepthook__:
            try:
                previous(exc_type, exc_value, tb)
            except Exception:
                pass
        try:
            sys.__excepthook__(exc_type, exc_value, tb)
        except Exception:
            # Default hook writes to stderr, which is None under --noconsole.
            pass

    sys.excepthook = hook
