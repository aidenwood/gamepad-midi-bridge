"""Guard the PySide6 teardown-segfault fix.

Every entry point that launches the GUI MUST hard-exit via os._exit so Python's
finaliser never runs Shiboken's destructionVisitor (which segfaults sweeping a
live QDoubleSpinBox wrapper on macOS). See scripts/app_entry.py + __main__.py.
"""
from __future__ import annotations

from pathlib import Path

from gamepad_midi_bridge import __main__ as entry


def test_console_entry_hard_exits_with_main_rc(monkeypatch):
    monkeypatch.setattr(entry, "main", lambda: 7)
    called = {}

    def fake_exit(code):
        called["code"] = code
        raise SystemExit(code)  # stand in for the real process-ending os._exit

    import os
    monkeypatch.setattr(os, "_exit", fake_exit)

    try:
        entry.console_entry()
    except SystemExit:
        pass
    assert called.get("code") == 7  # main's rc is forwarded to os._exit


def test_console_entry_hard_exits_even_when_main_raises(monkeypatch):
    # Abnormal exit (Ctrl-C / any exception) must STILL hard-exit, or the
    # interpreter finalises and segfaults. The os._exit lives in a finally.
    def boom():
        raise KeyboardInterrupt
    monkeypatch.setattr(entry, "main", boom)
    called = {}

    def fake_exit(code):
        called["code"] = code
        raise SystemExit(code)

    import os
    monkeypatch.setattr(os, "_exit", fake_exit)
    try:
        entry.console_entry()
    except SystemExit:
        pass
    assert called.get("code") == 130  # KeyboardInterrupt → still hard-exits


def test_pyinstaller_entry_routes_through_console_entry():
    # The PyInstaller bootstrap must NOT use the old main()+sys.exit() pattern
    # that lets the interpreter finalise and segfault.
    src = (Path(__file__).resolve().parents[1] / "scripts" / "app_entry.py").read_text()
    assert "console_entry()" in src
    assert "sys.exit(main())" not in src


def test_gui_launching_scripts_hard_exit():
    """Any script that builds a real QApplication must hard-exit too.

    The module docstring says *every* entry point that launches the GUI, but
    the invariant was only enforced for console_entry and the PyInstaller
    bootstrap. scripts/generate_screenshots.py builds a MainWindow and ended
    with `sys.exit(main())`, so Python finalised, Shiboken's destructionVisitor
    swept live Qt wrappers, and it segfaulted in Py_FinalizeEx — six macOS
    crash reports on 2026-10-24 came from exactly that script.
    """
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    offenders = []
    for path in sorted(scripts_dir.glob("*.py")):
        src = path.read_text()
        builds_gui = "QApplication(" in src or "MainWindow(" in src
        if not builds_gui:
            continue
        if "os._exit" not in src and "console_entry()" not in src:
            offenders.append(path.name)
    assert not offenders, (
        "GUI-launching scripts missing a hard exit (they will segfault on "
        f"interpreter shutdown): {offenders}"
    )


def test_generate_screenshots_does_not_use_sys_exit_main():
    """Pin the specific regression: the plain sys.exit(main()) pattern."""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "generate_screenshots.py").read_text()
    assert "sys.exit(main())" not in src
    assert "os._exit" in src
