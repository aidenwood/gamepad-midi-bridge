"""Centralised logging setup.

Writes a rotating log to `user_data_dir/logs/app.log`. Keeps the GUI quiet —
tracebacks land on disk so users can attach the file when filing a bug.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import user_data_dir


_configured = False


def setup(level: int = logging.INFO, console: bool = False) -> Path:
    """Wire stdlib logging once. Returns the log file path so callers can mention it."""
    global _configured
    log_dir = user_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    if _configured:
        return log_path

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(level)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler(stream=sys.stderr)
        stream.setFormatter(formatter)
        root.addHandler(stream)

    _configured = True
    return log_path


def log_path() -> Path:
    return user_data_dir() / "logs" / "app.log"
