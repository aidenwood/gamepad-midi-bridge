"""`python -m gamepad_midi_bridge` and the console-script entry point."""
from __future__ import annotations

import sys

from .app import run


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
