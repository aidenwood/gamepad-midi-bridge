"""`python -m gamepad_midi_bridge` and the console-script entry point.

Most users launch the GUI directly. CLI flags exist for power users and
deployment scenarios (kiosks, performance rigs).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import APP_NAME, __version__
from .crash_reporter import install_hook as install_crash_hook
from .logger import setup as setup_logging, log_path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gamepad-midi-bridge",
        description=f"{APP_NAME} — turn a gamepad into a MIDI controller.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--headless", action="store_true",
                   help="Run the bridge with no GUI. Useful for performance rigs and kiosks.")
    p.add_argument("--background", action="store_true",
                   help="Start the app in the system tray, hiding the main window. "
                        "The bridge starts automatically. Use tray icon to show window.")
    p.add_argument("--reset-config", action="store_true",
                   help="Wipe the config file (mapping settings, opt-ins, "
                        "onboarding flag) and exit.")
    p.add_argument("--export-pack", metavar="PATH",
                   help="Export current mapping + presets + license to a "
                        ".gmbpack file and exit.")
    p.add_argument("--import-pack", metavar="PATH",
                   help="Import a .gmbpack file and exit.")
    p.add_argument("--log-path", action="store_true",
                   help="Print where the log file lives and exit.")
    p.add_argument("--debug", action="store_true",
                   help="Verbose logging to both file and stderr.")
    p.add_argument("--demo", action="store_true",
                   help="Run with a synthetic controller (no hardware). "
                        "Useful for demos, CI, and DAW connector testing.")
    p.add_argument("deep_link", nargs="?", default=None,
                   help="Optional gmb:// URL handed in by the OS URL handler.")
    return p


def _do_reset_config() -> int:
    from .paths import config_path
    cfg = config_path()
    if cfg.exists():
        cfg.unlink()
        print(f"Wiped {cfg}")
    else:
        print(f"No config to wipe at {cfg}")
    return 0


def _do_export_pack(path_str: str) -> int:
    from .mapping import Mapping
    from .paths import user_data_dir
    from .portable import export_pack

    # We don't have access to the current mapping from CLI — load the
    # last-used one if it was persisted, otherwise fall back to defaults.
    last = user_data_dir() / "last_mapping.json"
    mapping = Mapping()
    if last.exists():
        try:
            mapping = Mapping.from_dict(json.loads(last.read_text(encoding="utf-8")))
        except Exception:
            pass

    report = export_pack(Path(path_str), mapping)
    print(f"Exported to {path_str} — {report.preset_count} preset(s), "
          f"license {'included' if report.license_present else 'omitted'}")
    return 0


def _do_import_pack(path_str: str) -> int:
    from .portable import import_pack
    mapping, report = import_pack(Path(path_str), replace_license=True)
    print(f"Imported {report.preset_count} preset(s)"
          + (", mapping restored" if mapping is not None else "")
          + (", license replaced" if report.license_present else "")
          + f" — pack made by v{report.creator_version}")
    return 0


def _do_headless(deep_link: str | None, demo: bool = False) -> int:
    """Run the bridge with no GUI. Uses QCoreApplication for the event loop."""
    import logging
    from PySide6.QtCore import QCoreApplication

    log = logging.getLogger("headless")
    from .bridge import BridgeController
    from .mapping import Mapping

    app = QCoreApplication(sys.argv)
    bridge = BridgeController(demo=demo)
    bridge.worker.set_mapping(Mapping())
    bridge.worker.status.connect(lambda msg: log.info("status: %s", msg))
    bridge.worker.error.connect(lambda msg: log.error("error: %s", msg))
    bridge.worker.started.connect(
        lambda c, p: log.info("started: %s -> %s", c, p))
    bridge.worker.stopped.connect(lambda: log.info("stopped"))

    bridge.start()
    log.info("Headless mode — Ctrl+C to stop")
    try:
        loop = getattr(app, "exec")
        return loop()
    except KeyboardInterrupt:
        bridge.shutdown()
        return 0


def main() -> int:
    install_crash_hook()
    args = _build_parser().parse_args()

    if args.log_path:
        print(log_path())
        return 0

    if args.reset_config:
        return _do_reset_config()

    if args.export_pack:
        setup_logging(console=args.debug)
        return _do_export_pack(args.export_pack)

    if args.import_pack:
        setup_logging(console=args.debug)
        return _do_import_pack(args.import_pack)

    setup_logging(console=args.debug)

    if args.headless:
        return _do_headless(args.deep_link, demo=args.demo)

    # GUI path picks demo and background up from env vars.
    if args.demo:
        import os
        os.environ["GMB_DEMO"] = "1"
    if args.background:
        import os
        os.environ["GMB_BACKGROUND"] = "1"

    from .app import run
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
