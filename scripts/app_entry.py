"""PyInstaller entry point.

`__main__.py` uses relative imports because it doubles as
`python -m gamepad_midi_bridge`. PyInstaller can't honour that when the
file is run as the bootstrap script, so we wrap the package call here.
"""
from __future__ import annotations

import sys

from gamepad_midi_bridge.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
