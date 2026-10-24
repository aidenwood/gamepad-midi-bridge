#!/usr/bin/env python3
"""Controller diagnostic — what SDL sees, and what the app decided about it.

Run this when a pad "isn't bridging properly". It answers, in one paste, the
three questions that otherwise take three round trips:

  1. Does SDL see the pad at all, and what does it call it?
  2. Which profile did ``sdl_profiles.profile_for`` resolve, and from what
     VID:PID? (A wrong profile is why an Xbox left trigger once drove the
     right stick — see sdl_profiles.py.)
  3. When you move a control, which CANONICAL axis/button actually changes?
     This is the one that catches a mis-resolved profile instantly: press
     L2 and the report should say ``L2``, not ``RX``.

Usage:
    .venv/bin/python scripts/controller_report.py              # 15s watch
    .venv/bin/python scripts/controller_report.py --seconds 30
    .venv/bin/python scripts/controller_report.py --raw        # device indices too

No MIDI port is opened and no mapping is loaded — this reads the controller
and nothing else, so it is safe to run while the app itself is open.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

REPO_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if REPO_SRC not in sys.path:
    sys.path.insert(0, REPO_SRC)

CANONICAL_AXES = ("LX", "LY", "RX", "RY", "L2", "R2")
CANONICAL_BUTTONS = (
    "A/Cross", "B/Circle", "X/Square", "Y/Triangle", "LB/L1", "RB/R1",
    "View/Share", "Menu/Options", "LS/L3", "RS/R3", "Guide/PS",
)
# A trigger rests at -1.0, so it is "moved" relative to its own rest value,
# not relative to zero. Baselines are captured before the watch starts.
MOVE_THRESHOLD = 0.25


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=15.0,
                    help="how long to watch for movement (default 15)")
    ap.add_argument("--raw", action="store_true",
                    help="also print un-remapped device indices")
    args = ap.parse_args()

    import pygame

    from gamepad_midi_bridge.control_labels import (
        display_name,
        family_for,
        vid_pid_from_guid,
    )
    from gamepad_midi_bridge.controller import ControllerReader
    from gamepad_midi_bridge.sdl_profiles import profile_for

    pygame.init()
    pygame.joystick.init()
    pygame.event.pump()

    count = pygame.joystick.get_count()
    print(f"SDL sees {count} controller(s)\n")
    if count == 0:
        print("Nothing plugged in as far as SDL is concerned.")
        print("  - USB: try a different cable; a charge-only cable enumerates")
        print("    as nothing at all.")
        print("  - Bluetooth: macOS can show a pad as paired but not connected.")
        print("    Check System Settings > Bluetooth says 'Connected'.")
        print("  - Xbox pads need to be woken with the Xbox button after pairing.")
        return 1

    reader = ControllerReader(slot_index=0)
    info = reader.detect()
    if info is None:
        print("SDL listed a controller but the app could not open it.")
        return 1

    vid, pid = vid_pid_from_guid(info.guid)
    axis_map, button_map, dpad_buttons = profile_for(
        info.guid, info.num_hats, info.num_buttons)

    print(f"  raw SDL name   : {info.raw_name!r}")
    print(f"  app shows it as: {display_name(info.raw_name, info.guid)!r}")
    print(f"  label family   : {family_for(display_name(info.raw_name, info.guid))}")
    print(f"  GUID           : {info.guid}")
    print(f"  VID:PID        : {vid:04x}:{pid:04x}")
    print(f"  axes/buttons/hats: {info.num_axes}/{info.num_buttons}/{info.num_hats}")
    print()
    print("  resolved profile")
    print("    canonical -> device axis  : "
          + ", ".join(f"{CANONICAL_AXES[c]}=a{axis_map.get(c, c)}" for c in range(6)))
    print("    canonical -> device button: "
          + ", ".join(f"{c}=b{button_map.get(c, c)}" for c in range(11)))
    print(f"    d-pad via buttons         : {dpad_buttons or 'no (uses hat 0)'}")
    print()

    baseline_axes = [reader.get_axis(i) for i in range(6)]
    print("  resting axis values: "
          + ", ".join(f"{CANONICAL_AXES[i]}={baseline_axes[i]:+.2f}"
                      for i in range(6)))
    print()
    print(f"Move every control now — watching for {args.seconds:.0f}s.")
    print("Expect: press L2 and see 'L2'. Seeing 'RX' instead means the "
          "profile is wrong for this pad.\n")

    seen_axes: dict[int, float] = {}
    seen_buttons: set[int] = set()
    seen_hat = False
    seen_raw_axes: dict[int, float] = {}
    seen_raw_buttons: set[int] = set()

    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        reader.pump()
        for i in range(6):
            delta = abs(reader.get_axis(i) - baseline_axes[i])
            if delta > MOVE_THRESHOLD and delta > seen_axes.get(i, 0.0):
                seen_axes[i] = delta
                print(f"  axis   {CANONICAL_AXES[i]:<3} moved "
                      f"(device a{axis_map.get(i, i)}, Δ{delta:.2f})")
        for i in range(11):
            if reader.get_button(i) and i not in seen_buttons:
                seen_buttons.add(i)
                print(f"  button {CANONICAL_BUTTONS[i]:<12} pressed "
                      f"(device b{button_map.get(i, i)})")
        if reader.get_hat(0) != (0, 0) and not seen_hat:
            seen_hat = True
            print("  d-pad  registered")
        if args.raw:
            for i in range(info.num_axes):
                delta = abs(reader.get_raw_axis(i))
                if delta > 0.6 and delta > seen_raw_axes.get(i, 0.0):
                    seen_raw_axes[i] = delta
            for i in range(info.num_buttons):
                if reader.get_raw_button(i):
                    seen_raw_buttons.add(i)
        time.sleep(0.01)

    print("\n--- summary ---")
    untouched = [CANONICAL_AXES[i] for i in range(6) if i not in seen_axes]
    print(f"  axes that moved   : "
          f"{', '.join(CANONICAL_AXES[i] for i in sorted(seen_axes)) or 'none'}")
    print(f"  axes that did not : {', '.join(untouched) or 'none'}")
    print(f"  buttons that fired: "
          f"{', '.join(CANONICAL_BUTTONS[i] for i in sorted(seen_buttons)) or 'none'}")
    print(f"  d-pad             : {'yes' if seen_hat else 'no'}")
    if args.raw:
        print(f"  raw device axes   : {sorted(seen_raw_axes) or 'none'}")
        print(f"  raw device buttons: {sorted(seen_raw_buttons) or 'none'}")
    if untouched:
        print("\n  Anything listed under 'did not' that you actually moved is a "
              "profile mismatch. Re-run with --raw and send both lists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
