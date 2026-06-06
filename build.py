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


def _read_version() -> str:
    """Pull __version__ out of the package without importing pygame/Qt."""
    init_text = (SRC / "__init__.py").read_text(encoding="utf-8")
    for line in init_text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


# macOS Info.plist privacy strings.  Without these, the OS kills the app the
# instant we touch IOBluetooth or GCController (TCC crash).
MACOS_PLIST_KEYS = {
    "NSBluetoothAlwaysUsageDescription":
        "Lists paired Bluetooth controllers so you can see "
        "which ones are connected to the bridge.",
    "NSBluetoothPeripheralUsageDescription":
        "Reads battery and signal strength from paired controllers.",
    "NSGameControllerUsageDescription":
        "Reads gamepad input and (on supported devices) drives the "
        "adaptive triggers' haptic feedback.",
    "NSAppleEventsUsageDescription":
        "Sends MIDI events to other applications.",
    # Older macOS asks for microphone permission when the audio toggle
    # (if any) is exercised — we keep this string ready even though the
    # current build does not capture audio. Cheap to ship.
    "NSMicrophoneUsageDescription":
        "Only used if you opt into audio-reactive trigger haptics.",
}


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

    if system == "Darwin":
        _patch_macos_plist(dist / f"{APP_NAME}.app")
        _resign_macos_bundle(dist / f"{APP_NAME}.app")

    # ASCII-only: Windows GitHub runners default stdout to cp1252, so a Unicode
    # arrow here aborts the script (with exit code 1) AFTER PyInstaller has
    # already produced the bundle - taking the whole release down with it.
    print(f"\nBuild complete -> {dist}")


def _patch_macos_plist(app_bundle: Path) -> None:
    """Inject privacy + version keys into the bundled Info.plist.

    PyInstaller writes a minimal Info.plist that omits the NSBluetooth*
    keys — modern macOS responds to that omission by SIGABRTing the
    process the first time we touch IOBluetooth. Adding these via
    `plistlib` keeps the keys in source control (this script) rather than
    forcing every contributor to hand-edit the bundle.
    """
    import plistlib

    plist_path = app_bundle / "Contents" / "Info.plist"
    if not plist_path.exists():
        print(f"  ! Info.plist not found at {plist_path}; skipping plist patch")
        return

    with plist_path.open("rb") as fh:
        data = plistlib.load(fh)

    version = _read_version()
    data.setdefault("CFBundleName", APP_NAME)
    data.setdefault("CFBundleDisplayName", APP_NAME)
    data["CFBundleShortVersionString"] = version
    data["CFBundleVersion"] = version
    data.setdefault("LSMinimumSystemVersion", "11.0")
    data.setdefault("NSHighResolutionCapable", True)

    # Privacy strings — present, accurate, and conservative.
    for key, value in MACOS_PLIST_KEYS.items():
        data[key] = value

    # Custom URL scheme — registers `gmb://` with macOS so deep links from
    # midi.aidxn.com (e.g. ``gmb://activate?key=<license_blob>``) open this
    # app and trigger one-click license activation. The handler lives in
    # ``app.py::_MacOpenUrlFilter`` → ``MainWindow.handle_deep_link``.
    # Also registers ``gamepad-midi-bridge://`` as a long-form alias for
    # places where verbose URLs read better (docs, support links).
    data["CFBundleURLTypes"] = [
        {
            "CFBundleURLName": f"{APP_ID}.gmb",
            "CFBundleURLSchemes": ["gmb", "gamepad-midi-bridge"],
            "CFBundleTypeRole": "Viewer",
        }
    ]

    with plist_path.open("wb") as fh:
        plistlib.dump(data, fh)
    print(f"  Patched {plist_path.relative_to(ROOT)} with privacy + version + URL scheme keys")


def _resign_macos_bundle(app_bundle: Path) -> None:
    """Re-apply an ad-hoc code signature after Info.plist was patched.

    PyInstaller ad-hoc signs the bundle as its last step. Our plist patch
    above mutates Info.plist (a sealed file), which invalidates that seal —
    `spctl --assess` then rejects the app with "invalid Info.plist (plist
    or signature have been modified)" and macOS shows users "this app is
    damaged and can't be opened" with no right-click escape. Re-signing
    now seals the patched bundle so Gatekeeper sees a valid (if unsigned-
    by-Developer-ID) ad-hoc signature, downgrading the message to the
    normal "from an unidentified developer" prompt that users can right-
    click → Open past.
    """
    if not app_bundle.exists():
        print(f"  ! .app bundle not found at {app_bundle}; skipping resign")
        return
    cmd = ["codesign", "--force", "--deep", "--sign", "-", str(app_bundle)]
    subprocess.check_call(cmd)
    print(f"  Re-signed {app_bundle.name} (ad-hoc) to re-seal patched Info.plist")


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
