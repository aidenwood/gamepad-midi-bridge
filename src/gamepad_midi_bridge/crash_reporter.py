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


def write_report(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    tb,
) -> Path:
    """Write a single crash report. Returns the file path."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = crash_dir() / f"crash-{stamp}.txt"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"Universal Controller MIDI crash report\n")
        f.write(f"version: {__version__}\n")
        f.write(f"python:  {sys.version}\n")
        f.write(f"platform:{sys.platform}\n")
        f.write(f"when:    {datetime.now(timezone.utc).isoformat()}\n")
        f.write("=" * 60 + "\n")
        traceback.print_exception(exc_type, exc_value, tb, file=f)
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
