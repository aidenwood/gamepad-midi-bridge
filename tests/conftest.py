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
    # The license + portable modules imported `license_path` / `presets_dir` / `user_data_dir`
    # by name, so they bypass the patched `user_data_dir` unless we redirect
    # those re-exports too.
    monkeypatch.setattr(license_mod, "license_path",
                        lambda: fake_user_data_dir() / "license.key")
    monkeypatch.setattr(portable_mod, "license_path",
                        lambda: fake_user_data_dir() / "license.key")
    monkeypatch.setattr(portable_mod, "presets_dir",
                        lambda: _ensure_dir(fake_user_data_dir() / "presets"))
    monkeypatch.setattr(portable_mod, "user_data_dir", fake_user_data_dir)

    # Reset the license module's process-wide cache between tests.
    monkeypatch.setattr(license_mod, "_cached_state", None, raising=False)

    yield fake_user_data_dir()


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """One QApplication for the whole session, kept alive until the end.

    Widget tests used to each do `QApplication.instance() or QApplication([])`
    with nothing holding a reference. At interpreter shutdown PySide6 runs
    `destroyQCoreApplication()` over objects Python had already collected,
    which segfaults in `~QObject` — every run ended with "QObject: shared
    QObject was deleted directly. The program is malformed and may crash."
    and dropped a crash report in ~/Library/Logs/DiagnosticReports.

    The suite still passed, so this was pure noise — but noise that would
    hide a genuine crash, which is exactly the failure mode that let a
    crash-on-every-connect ship under 7000 passing tests.

    Session-scoped and autouse so the instance outlives every widget, and
    offscreen so no window ever appears during a run.
    """
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        yield None
        return
    app = QApplication.instance() or QApplication([])
    yield app

    # Holding the QApplication reference stopped the hard crash, but the
    # warning survived it — measured at 6 runs in 8 before this block, which
    # is why it reads as intermittent: it depends on when CPython's GC gets
    # round to the orphaned widgets.
    #
    # The remaining problem is *order*. Widgets a test created without a
    # parent are owned by Python, so they are destroyed whenever the final GC
    # runs — which is during Py_FinalizeEx, after Qt has started shutting
    # down. Destroying them here, while the QApplication is still alive and
    # able to process the resulting deferred deletes, puts them back in a safe
    # order.
    #
    # Note this tears down leftover *widgets*, not the application — that
    # distinction is the point. Calling app.quit()/deleteLater() is still
    # wrong for the reason the original comment gave, and is still not done.
    import gc
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.processEvents()
    gc.collect()
    app.processEvents()
