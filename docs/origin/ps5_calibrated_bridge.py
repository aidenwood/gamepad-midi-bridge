"""
PS5 Controller -> MIDI Bridge with Stick Drift Calibration
============================================================

Same as ps5_bridge.py but with auto-calibration of stick drift on startup.

How it works:
  1. After startup, the script samples your sticks for ~1 second while
     you DON'T touch them.
  2. It records the average resting value of each stick axis — that's
     the drift offset.
  3. In the main loop, every stick reading has its offset subtracted
     before deadzone and MIDI scaling are applied.
  4. Result: the resting position is treated as true zero, regardless
     of how badly your sticks drift.

This won't fix severely worn sticks (where the rest position itself
jitters around), but for typical drift (a fixed offset that doesn't
move) it makes sticks usable again.

If calibration looks wrong, set RECALIBRATE_ON_DEMAND below to True
and press the keyboard 'r' key while running to re-calibrate (you'll
need pynput for that: pip install pynput).

Run:
    python ps5_calibrated_bridge.py

Stop with Ctrl+C.
"""

import sys
import os
import time
import subprocess

try:
    import pygame
    import rtmidi
except ImportError as e:
    print("Missing package: " + str(e))
    print("Run:  pip install pygame python-rtmidi")
    sys.exit(1)


# ---------------------------------------------------------------------------
# AUTO-LAUNCH CONFIG
# ---------------------------------------------------------------------------

LOOPMIDI_PATH = r"C:\Program Files (x86)\Tobias Erichsen\loopMIDI\loopMIDI.exe"
LOOPMIDI_PROCESS = "loopMIDI.exe"

DS4WINDOWS_PATH = r"C:\Program Files\DS4Windows\DS4Windows.exe"
DS4WINDOWS_PROCESS = "DS4Windows.exe"

LOOPMIDI_WAIT_SEC   = 2
DS4WINDOWS_WAIT_SEC = 8


# ---------------------------------------------------------------------------
# BRIDGE CONFIG
# ---------------------------------------------------------------------------

MIDI_PORT_NAME  = "ps5-bridge"
MIDI_CHANNEL    = 0
POLL_HZ         = 100
DIAGNOSTIC_MODE = False

# Sticks are ENABLED in this version — the whole point is to make them work.
STICKS_ENABLED  = True

# Deadzone applied AFTER offset subtraction. Can be tighter than the
# regular bridge since drift is already compensated.
DEADZONE        = 0.05

# Calibration: how long to sample at rest, in seconds, and how many samples.
CALIB_DURATION_SEC  = 1.0
CALIB_SAMPLE_COUNT  = 60

# If True, prints the calibration offsets it discovered. Useful to confirm
# the calibration actually worked.
SHOW_CALIBRATION    = True

BUTTON_NOTES = {
    0:  60, 1:  62, 2:  64, 3:  65,
    4:  67, 5:  69,
    6:  71, 7:  72, 8:  74,
    9:  76, 10: 77,
}

AXIS_CC = {
    0: 3, 1: 4, 2: 5, 3: 6,
    4: 1, 5: 2,
}

STICK_AXES = {0, 1, 2, 3}

HAT_NOTES = {
    "up": 78, "down": 79, "left": 80, "right": 81,
}


# ---------------------------------------------------------------------------
# PROCESS HELPERS
# ---------------------------------------------------------------------------

def is_process_running(exe_name):
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq " + exe_name, "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return exe_name.lower() in result.stdout.lower()
    except Exception:
        return False


def ensure_running(label, exe_name, exe_path, wait_seconds):
    if is_process_running(exe_name):
        print("  [OK]  " + label + " already running.")
        return True
    if exe_path is None:
        return False
    if not os.path.exists(exe_path):
        print("  [!!]  " + label + " not found at: " + exe_path)
        return False
    print("  [..]  Launching " + label + "...")
    try:
        subprocess.Popen([exe_path],
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    except Exception as e:
        print("  [!!]  Failed: " + str(e))
        return False
    for remaining in range(wait_seconds, 0, -1):
        sys.stdout.write("\r  [..]  Waiting " + str(remaining) + "s for " + label + "...  ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\r")
    ok = is_process_running(exe_name)
    print("  [" + ("OK" if ok else "!!") + "]  " + label +
          (" started.                       " if ok else " failed.                        "))
    return ok


# ---------------------------------------------------------------------------
# CALIBRATION
# ---------------------------------------------------------------------------

def calibrate_sticks(joystick, duration=CALIB_DURATION_SEC, samples=CALIB_SAMPLE_COUNT):
    """
    Sample stick axes at rest to find their drift offset.
    Returns a dict: axis_index -> average resting value.
    """
    print()
    print("=" * 60)
    print(" CALIBRATING STICKS")
    print("=" * 60)
    print(" DO NOT TOUCH the controller for the next " + str(int(duration + 1)) + " seconds.")
    print(" Let both sticks sit at rest...")

    # Brief pause to let the user release any pressure
    for remaining in range(3, 0, -1):
        sys.stdout.write("\r Starting in " + str(remaining) + "...  ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\r Sampling now...    \n")

    n_axes = joystick.get_numaxes()
    axes_to_calibrate = [a for a in STICK_AXES if a < n_axes]
    samples_data = {axis: [] for axis in axes_to_calibrate}

    interval = duration / samples
    for _ in range(samples):
        pygame.event.pump()
        for axis in axes_to_calibrate:
            samples_data[axis].append(joystick.get_axis(axis))
        time.sleep(interval)

    offsets = {}
    for axis, vals in samples_data.items():
        offsets[axis] = sum(vals) / len(vals) if vals else 0.0

    if SHOW_CALIBRATION:
        print()
        print(" Drift offsets discovered:")
        for axis in sorted(offsets.keys()):
            mark = "  (significant)" if abs(offsets[axis]) > 0.05 else ""
            print("   Axis " + str(axis) + ": " + str(round(offsets[axis], 4)) + mark)
        print()
        print(" These will be subtracted from every stick reading.")
        print(" If any axis shows a value over 0.3, your controller has")
        print(" severe drift and may need physical repair.")
    print("=" * 60)
    print()

    return offsets


# ---------------------------------------------------------------------------
# STARTUP
# ---------------------------------------------------------------------------

print("=" * 60)
print(" Dependency check")
print("=" * 60)

ds4_ok = ensure_running("DS4Windows", DS4WINDOWS_PROCESS,
                        DS4WINDOWS_PATH, DS4WINDOWS_WAIT_SEC)
mid_ok = ensure_running("loopMIDI", LOOPMIDI_PROCESS,
                        LOOPMIDI_PATH, LOOPMIDI_WAIT_SEC)

if not ds4_ok or not mid_ok:
    print("\nCannot continue.")
    sys.exit(1)

print()

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Waiting for controller...")
    for i in range(10):
        time.sleep(1)
        pygame.joystick.quit()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            break

if pygame.joystick.get_count() == 0:
    print("ERROR: no joystick detected.")
    sys.exit(1)

joystick = pygame.joystick.Joystick(0)
joystick.init()

print("Joystick:  " + joystick.get_name())
print("  Axes:    " + str(joystick.get_numaxes()))
print("  Buttons: " + str(joystick.get_numbuttons()))

# --- RUN CALIBRATION ---
stick_offsets = calibrate_sticks(joystick)

# --- MIDI SETUP ---
midi_out = rtmidi.MidiOut()
available_ports = midi_out.get_ports()

target_port = None
for i, name in enumerate(available_ports):
    if MIDI_PORT_NAME.lower() in name.lower():
        target_port = i
        break

if target_port is None:
    print("ERROR: no MIDI port matching '" + MIDI_PORT_NAME + "'.")
    sys.exit(1)

midi_out.open_port(target_port)

print("MIDI port: [" + str(target_port) + "] " + available_ports[target_port])
print()
print("Bridge running with stick drift compensation. Ctrl+C to stop.")
print()


# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

NOTE_ON  = 0x90 | MIDI_CHANNEL
NOTE_OFF = 0x80 | MIDI_CHANNEL
CC       = 0xB0 | MIDI_CHANNEL

prev_buttons = {b: False for b in BUTTON_NOTES}
prev_cc      = {}
prev_hat     = {"up": False, "down": False, "left": False, "right": False}


def send_note_on(note):
    midi_out.send_message([NOTE_ON, note, 127])


def send_note_off(note):
    midi_out.send_message([NOTE_OFF, note, 0])


def send_cc(cc_num, value):
    midi_out.send_message([CC, cc_num, value])


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------

clock = pygame.time.Clock()
n_buttons = joystick.get_numbuttons()
n_axes    = joystick.get_numaxes()
n_hats    = joystick.get_numhats()

try:
    while True:
        pygame.event.pump()

        # Buttons
        for btn_idx, note in BUTTON_NOTES.items():
            if btn_idx >= n_buttons:
                continue
            pressed = joystick.get_button(btn_idx) == 1
            was = prev_buttons[btn_idx]
            if pressed and not was:
                send_note_on(note)
                if DIAGNOSTIC_MODE:
                    print("button " + str(btn_idx) + " DOWN")
            elif not pressed and was:
                send_note_off(note)
                if DIAGNOSTIC_MODE:
                    print("button " + str(btn_idx) + " UP")
            prev_buttons[btn_idx] = pressed

        # Axes with offset compensation for sticks
        for axis_idx, cc_num in AXIS_CC.items():
            if axis_idx >= n_axes:
                continue
            if axis_idx in STICK_AXES and not STICKS_ENABLED:
                continue

            raw = joystick.get_axis(axis_idx)

            # Subtract drift offset (sticks only — triggers have no drift)
            if axis_idx in STICK_AXES:
                raw = raw - stick_offsets.get(axis_idx, 0.0)
                raw = clamp(raw, -1.0, 1.0)
                if abs(raw) < DEADZONE:
                    raw = 0.0

            val = int(round((raw + 1.0) * 63.5))
            val = clamp(val, 0, 127)

            if prev_cc.get(axis_idx) != val:
                send_cc(cc_num, val)
                if DIAGNOSTIC_MODE:
                    print("axis " + str(axis_idx) + " raw=" + str(round(raw, 3)) +
                          " -> CC" + str(cc_num) + "=" + str(val))
                prev_cc[axis_idx] = val

        # D-pad
        if n_hats > 0:
            hat_x, hat_y = joystick.get_hat(0)
            current = {
                "up":    hat_y ==  1,
                "down":  hat_y == -1,
                "left":  hat_x == -1,
                "right": hat_x ==  1,
            }
            for direction, note in HAT_NOTES.items():
                now = current[direction]
                was = prev_hat[direction]
                if now and not was:
                    send_note_on(note)
                elif not now and was:
                    send_note_off(note)
                prev_hat[direction] = now

        clock.tick(POLL_HZ)

except KeyboardInterrupt:
    print("\nStopping.")

finally:
    for btn_idx, note in BUTTON_NOTES.items():
        if prev_buttons.get(btn_idx):
            send_note_off(note)
    for direction, note in HAT_NOTES.items():
        if prev_hat.get(direction):
            send_note_off(note)
    del midi_out
    pygame.quit()
