"""Shared pytest fixtures.

Every test that touches the filesystem goes through `tmp_user_data` so the
suite never reads or writes the user's real config directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Make the in-tree `src/` package importable without `pip install -e .`.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def tmp_user_data(tmp_path, monkeypatch):
    """Redirect user_data_dir + every derived path to a temp directory.

    Patches the canonical `paths.user_data_dir` and every per-module re-import
    of it (license, portable) so the runtime stays internally consistent even
    after the modules have already pulled the name into their local namespace.
    """
    from gamepad_midi_bridge import paths as paths_mod
    from gamepad_midi_bridge import license as license_mod
    from gamepad_midi_bridge import portable as portable_mod

    def fake_user_data_dir() -> Path:
        d = tmp_path / "user_data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(paths_mod, "user_data_dir", fake_user_data_dir)
    # The license + portable modules imported `license_path` / `presets_dir`
    # by name, so they bypass the patched `user_data_dir` unless we redirect
    # those re-exports too.
    monkeypatch.setattr(license_mod, "license_path",
                        lambda: fake_user_data_dir() / "license.key")
    monkeypatch.setattr(portable_mod, "license_path",
                        lambda: fake_user_data_dir() / "license.key")
    monkeypatch.setattr(portable_mod, "presets_dir",
                        lambda: _ensure_dir(fake_user_data_dir() / "presets"))

    # Reset the license module's process-wide cache between tests.
    monkeypatch.setattr(license_mod, "_cached_state", None, raising=False)

    yield fake_user_data_dir()


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
