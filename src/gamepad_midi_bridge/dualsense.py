"""DualSense raw HID access — parallel to pygame.

pygame-ce reads the controller through SDL2's gamepad layer. SDL2 doesn't
expose battery, touchpad, or adaptive triggers. So we open a *second* HID
handle on the same device (read-only for input, write for triggers) and
parse the raw report ourselves.

Reference: https://github.com/nondebug/dualsense and the SensePost write-up.

Why not pydualsense / dualsense-controller:
    - Both Win+Linux only (no macOS bus_type fix)
    - pydualsense is GPL-incompatible-adjacent (dep tree)
    - dualsense-controller uses a callback thread that can fight pygame's
      event pump

V1.1: battery, touchpad, wired/BT detection, input parsing.
V1.1b: adaptive trigger OUTPUT. Works on Win+Linux via hidapi. macOS blocks
raw HID writes post-Catalina, so on darwin the bridge falls back to
`mac_haptics.py` which uses Apple's GCController framework via PyObjC.
V1.1c: adaptive triggers over **Bluetooth**. Sony's firmware silently drops
raw `0x02` reports on BT — only the 78-byte `0x31` framed report with a
CRC32 (IEEE 802.3, seeded by an `0xA2` prefix byte) is accepted. We now
build that frame transport-appropriately so haptics work on both buses.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import List, Optional

import hid


DUALSENSE_VID = 0x054C
DUALSENSE_PID = 0x0CE6   # PS5 DualSense
DUALSENSE_EDGE_PID = 0x0DF2   # DualSense Edge


# hidapi bus_type values
BUS_USB = 0x01
BUS_BLUETOOTH = 0x05


@dataclass
class TouchPoint:
    """One of two simultaneous touch contacts."""
    active: bool
    touch_id: int
    x: int           # 0..1919
    y: int           # 0..1079

    def normalized(self) -> tuple[float, float]:
        """0.0..1.0 in each axis. (0,0) is top-left."""
        return (self.x / 1919.0, self.y / 1079.0)


@dataclass
class BatteryStatus:
    level_percent: int   # 0..100, rounded to nearest 10
    charging: bool
    fully_charged: bool


@dataclass
class DualSenseState:
    battery: BatteryStatus
    touch_a: TouchPoint
    touch_b: TouchPoint


@dataclass
class DualSenseDevice:
    """Discovery record. Use `open()` to get a working handle."""
    path: bytes
    bus_type: int
    product_id: int
    serial_number: str

    @property
    def wired(self) -> bool:
        return self.bus_type == BUS_USB

    def open(self) -> "DualSenseHandle":
        h = hid.device()
        h.open_path(self.path)
        h.set_nonblocking(True)
        return DualSenseHandle(h, wired=self.wired)


def enumerate_devices() -> List[DualSenseDevice]:
    """Return every connected DualSense (standard + Edge)."""
    found: List[DualSenseDevice] = []
    for pid in (DUALSENSE_PID, DUALSENSE_EDGE_PID):
        for d in hid.enumerate(DUALSENSE_VID, pid):
            found.append(DualSenseDevice(
                path=d["path"],
                bus_type=int(d.get("bus_type", 0)),
                product_id=int(d.get("product_id", pid)),
                serial_number=str(d.get("serial_number") or ""),
            ))
    return found


def find_first() -> Optional[DualSenseDevice]:
    devices = enumerate_devices()
    return devices[0] if devices else None


# --------------------------------------------------------------- input parsing


class DualSenseHandle:
    """Owns the HID handle for one DualSense. Read-only in V1.1."""

    # USB input report 0x01 layout (subset we care about):
    #   byte 53        — battery (low nibble = level 0-10, bit 4 = charging,
    #                    bit 5 = fully charged)
    #   bytes 33-36    — touch A
    #   bytes 37-40    — touch B
    # BT input report 0x31 has 1 extra prefix byte; we offset by +1 when BT.

    _USB_REPORT_SIZE = 64
    _BT_REPORT_SIZE = 78

    def __init__(self, handle: hid.device, wired: bool) -> None:
        self._h = handle
        self._wired = wired

    # ---- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._h.close()
        except Exception:
            pass

    @property
    def wired(self) -> bool:
        return self._wired

    # ---- polling -----------------------------------------------------------

    def read_state(self) -> Optional[DualSenseState]:
        """Non-blocking read. Returns None if no fresh report available."""
        size = self._USB_REPORT_SIZE if self._wired else self._BT_REPORT_SIZE
        buf = self._h.read(size)
        if not buf:
            return None
        # BT reports prefix the standard payload with one byte; skip it so the
        # offsets below match the USB layout regardless of transport.
        offset = 0 if self._wired else 1
        if len(buf) < offset + 54:
            return None
        return DualSenseState(
            battery=_parse_battery(buf, offset),
            touch_a=_parse_touch(buf, offset + 33),
            touch_b=_parse_touch(buf, offset + 37),
        )


def _parse_battery(buf, offset: int) -> BatteryStatus:
    raw = buf[offset + 53]
    level = (raw & 0x0F)               # 0..10
    return BatteryStatus(
        level_percent=min(level * 10, 100),
        charging=bool(raw & 0x10),
        fully_charged=bool(raw & 0x20),
    )


# --------------------------------------------------------- adaptive triggers


# Sony adaptive-trigger effect identifiers (byte 0 of the 11-byte block).
TRIGGER_EFFECTS = {
    "off":       0x05,
    "feedback":  0x21,
    "bow":       0x22,
    "galloping": 0x23,
    "weapon":    0x25,
    "vibration": 0x26,
    "machine":   0x27,
}


def _trigger_block(effect: str) -> bytes:
    """Return an 11-byte trigger effect block, padded with zeros after the
    effect-specific parameters. Defaults are tuned for a noticeable feel
    without being so strong that the controller stalls.
    """
    eid = TRIGGER_EFFECTS.get(effect, TRIGGER_EFFECTS["off"])
    block = bytearray(11)
    block[0] = eid
    if effect == "feedback":
        # start_position, resistive_strength (0..255)
        block[1] = 0
        block[2] = 200
    elif effect == "weapon":
        # start, end, strength
        block[1] = 0x02
        block[2] = 0x07
        block[3] = 0xE0
    elif effect == "vibration":
        # start, amplitude, frequency_hz
        block[1] = 0
        block[2] = 200
        block[3] = 20
    elif effect == "bow":
        block[1] = 0x01
        block[2] = 0x08
        block[3] = 0xE0
        block[4] = 0xE0
    elif effect == "galloping":
        block[1] = 0x00
        block[2] = 0x09
        block[3] = 0x02
        block[4] = 0x07
        block[5] = 0x07
    elif effect == "machine":
        block[1] = 0x00
        block[2] = 0x09
        block[3] = 0x07
        block[4] = 0x07
        block[5] = 0xFF
        block[6] = 0xFF
    # "off" and unknowns leave the rest of the block at zero.
    return bytes(block)


def _crc32_dualsense(data: bytes) -> int:
    """CRC32 used by DualSense BT output framing.

    Sony picked the bog-standard IEEE 802.3 polynomial (0xEDB88320) which is
    exactly what `zlib.crc32` implements — no custom poly, no reflection
    tricks, no XOR-out twist. We isolate it in a named helper so future
    debuggers grep the right thing rather than wondering why zlib shows up.
    """
    return zlib.crc32(data) & 0xFFFFFFFF


def _bt_output_packet(l2_block: bytes, r2_block: bytes) -> bytes:
    """Build the 78-byte BT output frame (incl. 0xA2 CRC seed prefix).

    Layout (per nondebug/dualsense reverse engineering):
        [0]    0xA2  — CRC seed prefix; *included* in CRC calc but NOT sent
                       over the wire. The actual HID write starts at [1].
        [1]    0x31  — BT output report ID
        [2]    0x02  — tag byte (flags-compat marker; tag=2 message)
        [3]    0xFF  — flags1: enable every sub-feature (rumble + triggers
                       + LEDs + audio); we only care about the trigger bits
                       but the firmware accepts the whole mask.
        [4]    0xF7  — flags2
        [5..12]      — rumble/audio/etc, left zero
        [13..23]     — R2 trigger block (11 bytes)
        [24..34]     — L2 trigger block (11 bytes)
        [35..73]     — LED/lightbar/mute placeholders, left zero
        [74..77]     — little-endian CRC32 over bytes [0..73] inclusive

    Returns the full 78-byte buffer; caller slices [1:78] for the actual
    HID write (77 bytes payload from the OS's perspective).
    """
    pkt = bytearray(78)
    pkt[0] = 0xA2        # CRC seed prefix (transport quirk, not sent)
    pkt[1] = 0x31        # BT output report ID
    pkt[2] = 0x02        # tag = 2
    pkt[3] = 0xFF        # flags1
    pkt[4] = 0xF7        # flags2
    pkt[13:24] = r2_block
    pkt[24:35] = l2_block
    crc = _crc32_dualsense(bytes(pkt[0:74]))
    pkt[74:78] = crc.to_bytes(4, "little")
    return bytes(pkt)


def write_trigger_effects(
    handle: "DualSenseHandle",
    l2_effect: Optional[str],
    r2_effect: Optional[str],
) -> bool:
    """Push trigger-effect output report to the controller.

    Pass `None` (or "off") to disable that trigger. Returns True if the OS
    accepted the write — does not mean the user felt anything; macOS still
    no-ops silently. BT now works because we build the framed `0x31` report
    with a CRC32 tail; firmware drops malformed frames without complaint.
    """
    if l2_effect is None and r2_effect is None:
        return True
    # Always send a full report: any trigger we want untouched gets "off"
    # rather than carrying over previous state (firmware does not merge).
    r2_block = _trigger_block(r2_effect or "off")
    l2_block = _trigger_block(l2_effect or "off")
    try:
        if handle.wired:
            # USB path — keep the proven 48-byte 0x02 framing untouched.
            flags1 = 0xFF
            flags2 = 0xF7
            pkt = bytearray(48)
            pkt[0] = 0x02
            pkt[1] = flags1
            pkt[2] = flags2
            pkt[11:22] = r2_block
            pkt[22:33] = l2_block
            return handle._h.write(bytes(pkt)) > 0
        # BT path — strip the 0xA2 CRC seed before writing; only [1:78] goes
        # to the OS. Firmware re-prepends 0xA2 internally to verify the CRC.
        full = _bt_output_packet(l2_block, r2_block)
        return handle._h.write(full[1:78]) > 0
    except Exception:
        return False


def _parse_touch(buf, base: int) -> TouchPoint:
    b0 = buf[base]
    b1 = buf[base + 1]
    b2 = buf[base + 2]
    b3 = buf[base + 3]
    active = not (b0 & 0x80)           # bit 7 clear = contact present
    touch_id = b0 & 0x7F
    x = ((b2 & 0x0F) << 8) | b1
    y = (b3 << 4) | (b2 >> 4)
    return TouchPoint(active=active, touch_id=touch_id, x=x, y=y)


# ----------------------------------------------------------- sanity self-check
#
# Reference CRC32 for the "all off" BT packet (both triggers = off, all other
# bytes zero apart from the framing constants 0xA2/0x31/0x02/0xFF/0xF7 and the
# `off` trigger ID 0x05 at the two block starts):
#
#     expected CRC32 (integer, hex):                       0x81C5A8D1
#     bytes on wire at [74:78] (little-endian):            D1 A8 C5 81
#
# If a future change flips a framing byte by accident this hex will move,
# giving us a fast regression tripwire long before plugging into hardware.
# (Sony silently drops bad-CRC frames — no error, just dead haptics.)

if __name__ == "__main__":
    off_block = _trigger_block("off")
    off_pkt = _bt_output_packet(off_block, off_block)
    off_crc = int.from_bytes(off_pkt[74:78], "little")
    print(f"off+off BT packet CRC32 = 0x{off_crc:08X}")

    weapon_block = _trigger_block("weapon")
    vib_block = _trigger_block("vibration")
    demo_pkt = _bt_output_packet(weapon_block, vib_block)
    demo_crc = int.from_bytes(demo_pkt[74:78], "little")
    print(f"weapon (L2) + vibration (R2) CRC32 = 0x{demo_crc:08X}")
    print(f"packet length sent over wire = {len(demo_pkt[1:78])} bytes")
    print(f"first 8 bytes of payload    = {demo_pkt[1:9].hex(' ')}")
    print(f"R2 block @ [13:24]          = {demo_pkt[13:24].hex(' ')}")
    print(f"L2 block @ [24:35]          = {demo_pkt[24:35].hex(' ')}")
    print(f"CRC tail                    = {demo_pkt[74:78].hex(' ')}")
