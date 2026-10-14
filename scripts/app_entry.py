"""PyInstaller entry point.

`__main__.py` uses relative imports because it doubles as
`python -m gamepad_midi_bridge`. PyInstaller can't honour that when the
file is run as the bootstrap script, so we wrap the package call here.

MUST call ``console_entry`` (not ``main``): it hard-exits via ``os._exit`` to
skip the PySide6/Shiboken ``destructionVisitor`` teardown segfault. Calling
``main`` + ``sys.exit`` returns normally, letting Python's finaliser sweep live
Qt wrappers (e.g. a QDoubleSpinBox) and crash during ``Py_FinalizeEx`` — which
is exactly what the frozen macOS app was doing. Keep this in lockstep with the
``gamepad-midi-bridge`` console script and ``python -m gamepad_midi_bridge``.

LAST-RESORT CRASH HANDLER
-------------------------
``crash_reporter.install_hook`` runs inside ``main()``, so it cannot catch a
failure in the ``import`` below — a missing PyInstaller hidden import or an
unloadable DLL dies before any of our code runs. On Windows that is fatal and
silent: ``build.py`` passes ``--noconsole``, so there is no console to print a
traceback to and the user sees the app flash and vanish.

The handler here is deliberately stdlib-only (``sys``, ``os``, ``traceback``,
``ctypes``) — it must work in exactly the situation where our package failed to
import, so it cannot depend on our package, PySide6, or anything bundled.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime

SUPPORT_EMAIL = "hi@aidxn.com"
APP_NAME = "Universal Controller MIDI"


def _fallback_crash_dir() -> str:
    """Mirror ``paths.user_data_dir`` without importing the package."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(base, APP_NAME, "crashes")
    os.makedirs(d, exist_ok=True)
    return d


def _write_startup_report(text: str) -> str | None:
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(_fallback_crash_dir(), f"startup-crash-{stamp}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path
    except Exception:
        return None


def _native_alert(title: str, message: str) -> None:
    """Show an OS-native message box with no third-party dependencies."""
    try:
        if sys.platform == "win32":
            import ctypes
            # MB_ICONERROR (0x10) | MB_SETFOREGROUND (0x10000)
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10 | 0x10000)
            return
        if sys.platform == "darwin":
            import subprocess
            # Pass the strings as argv entries, never interpolated into a
            # shell command — a traceback is full of quotes and backslashes.
            script = (
                'on run argv\n'
                '  display dialog (item 1 of argv) with title (item 2 of argv) '
                'buttons {"OK"} with icon stop\n'
                'end run'
            )
            subprocess.run(
                ["osascript", "-e", script, message, title],
                check=False,
                timeout=120,
            )
            return
        # Linux: zenity if it happens to be installed, otherwise stderr.
        import subprocess
        subprocess.run(
            ["zenity", "--error", "--no-wrap", "--title", title, "--text", message],
            check=False,
            timeout=120,
        )
    except Exception:
        try:
            if sys.stderr is not None:
                sys.stderr.write(f"{title}\n{message}\n")
        except Exception:
            pass


def _handle_startup_failure(exc: BaseException) -> None:
    detail = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    report = (
        f"{APP_NAME} failed to start\n"
        f"python:  {sys.version}\n"
        f"platform:{sys.platform}\n"
        f"frozen:  {getattr(sys, 'frozen', False)}\n"
        f"when:    {datetime.now().isoformat()}\n"
        + "=" * 60 + "\n"
        + detail
    )
    path = _write_startup_report(report)

    # Keep the dialog body short enough to stay readable in a Win32 message
    # box — the full trace is in the file either way.
    trimmed = detail if len(detail) <= 1500 else detail[-1500:]
    message = (
        f"{APP_NAME} couldn't start.\n\n"
        f"Please send this to {SUPPORT_EMAIL} so we can fix it.\n\n"
    )
    if path:
        message += f"A copy was saved to:\n{path}\n\n"
    message += f"-----\n{trimmed}"

    _native_alert(f"{APP_NAME} - startup error", message)


if __name__ == "__main__":
    try:
        from gamepad_midi_bridge.__main__ import console_entry
    except BaseException as exc:  # noqa: BLE001 - last line of defence
        _handle_startup_failure(exc)
        os._exit(1)

    console_entry()
