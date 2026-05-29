"""Pure stdlib DAW Transport and MIDI Machine Control (MMC) helpers.

Provides functions to emit MIDI Machine Control (MMC) System Exclusive messages
and common MIDI real-time transport commands (start, stop, continue) for controlling
DAWs and MIDI hardware sequencers.

All functions return lists of bytes (0-127 for data, 0-247 for status) suitable
for direct MIDI output. No Qt or external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Literal

# MIDI constants
SYSEX_START = 0xF0  # 240: Start of exclusive
SYSEX_END = 0xF7    # 247: End of exclusive
UNIVERSAL_REALTIME = 0x7F  # Universal realtime SysEx ID

# MIDI Real-Time Status Bytes
REALTIME_START = 0xFA    # 250: Start playback
REALTIME_STOP = 0xFC     # 252: Stop playback
REALTIME_CONTINUE = 0xFB  # 251: Continue from stop point

# MIDI Common System Messages
SONG_POSITION_POINTER = 0xF2  # 242: Set song position
SONG_SELECT = 0xF3            # 243: Select song
TUNE_REQUEST = 0xF6           # 246: Tune request

# MMC command byte mappings (7-bit payload)
MMC_COMMANDS: Dict[str, int] = {
    "stop": 0x01,
    "play": 0x02,
    "deferred_play": 0x03,
    "fast_forward": 0x04,
    "rewind": 0x05,
    "record_strobe": 0x06,
    "record_exit": 0x07,
    "record_pause": 0x09,
    "pause": 0x09,
    "eject": 0x0A,
    "chase": 0x0B,
    "command_error_reset": 0x0D,
    "mmc_reset": 0x0D,
}

TransportCommand = Literal[
    "play",
    "stop",
    "pause",
    "record_strobe",
    "rewind",
    "fast_forward",
    "locate",
    "continue",
]


def mmc(command: str, device_id: int = 0x7F) -> List[int]:
    """Build an MMC (MIDI Machine Control) System Exclusive message.

    Constructs a standard MMC command message for controlling tape machines,
    hard disk recorders, and DAW transport.

    Args:
        command: MMC command name (stop, play, pause, record_strobe, etc.)
        device_id: Target device ID (0x7F = all devices, default; 0x00-0x7E = specific)

    Returns:
        Complete SysEx message: [F0, 7F, device_id, 06, command_byte, F7]

    Raises:
        KeyError: If command is not in MMC_COMMANDS
    """
    if command not in MMC_COMMANDS:
        raise KeyError(f"Unknown MMC command: {command}")

    device_id = max(0, min(device_id, 0x7F))  # Clamp to 0-127
    command_byte = MMC_COMMANDS[command]
    return [SYSEX_START, UNIVERSAL_REALTIME, device_id, 0x06, command_byte, SYSEX_END]


def mmc_locate(
    hours: int,
    minutes: int,
    seconds: int,
    frames: int,
    device_id: int = 0x7F,
) -> List[int]:
    """Build an MMC LOCATE command with SMPTE timecode.

    Instructs the device to locate to a specific position in SMPTE hours:minutes:seconds:frames.

    Args:
        hours: SMPTE hours (0-23, clamped)
        minutes: SMPTE minutes (0-59, clamped)
        seconds: SMPTE seconds (0-59, clamped)
        frames: SMPTE frames (0-29 for 30fps, clamped)
        device_id: Target device ID (0x7F = all devices, default)

    Returns:
        Complete SysEx message with embedded SMPTE timecode:
        [F0, 7F, device_id, 06, 44, 06, 01, hr, min, sec, fr, F7]
    """
    device_id = max(0, min(device_id, 0x7F))
    hours = max(0, min(hours, 23))
    minutes = max(0, min(minutes, 59))
    seconds = max(0, min(seconds, 59))
    frames = max(0, min(frames, 29))

    return [
        SYSEX_START,
        UNIVERSAL_REALTIME,
        device_id,
        0x06,
        0x44,  # Locate command
        0x06,  # Data length (6 bytes follow)
        0x01,  # SMPTE format type
        hours,
        minutes,
        seconds,
        frames,
        SYSEX_END,
    ]


def realtime_start() -> List[int]:
    """Build a MIDI Real-Time START message.

    Instructs connected devices to begin playback from the current position.

    Returns:
        Single byte: [FA]
    """
    return [REALTIME_START]


def realtime_stop() -> List[int]:
    """Build a MIDI Real-Time STOP message.

    Instructs connected devices to stop playback immediately.

    Returns:
        Single byte: [FC]
    """
    return [REALTIME_STOP]


def realtime_continue() -> List[int]:
    """Build a MIDI Real-Time CONTINUE message.

    Instructs connected devices to resume playback from the last stop point.

    Returns:
        Single byte: [FB]
    """
    return [REALTIME_CONTINUE]


def song_position_pointer(beats_16th: int) -> List[int]:
    """Build a Song Position Pointer (SPP) message.

    Sets the sequencer position to the given number of 16th-note beats from
    the start of the song. Used for sync.

    Args:
        beats_16th: Position in 16th-note beats (0-16383, clamped)

    Returns:
        Three-byte message: [F2, lsb, msb]
        where lsb = beats_16th & 0x7F, msb = (beats_16th >> 7) & 0x7F
    """
    beats_16th = max(0, min(beats_16th, 16383))
    lsb = beats_16th & 0x7F
    msb = (beats_16th >> 7) & 0x7F
    return [SONG_POSITION_POINTER, lsb, msb]


def song_select(song_number: int) -> List[int]:
    """Build a Song Select message.

    Selects a song/sequence number for playback.

    Args:
        song_number: Song number (0-127, clamped)

    Returns:
        Two-byte message: [F3, song_number]
    """
    song_number = max(0, min(song_number, 127))
    return [SONG_SELECT, song_number]


def tune_request() -> List[int]:
    """Build a Tune Request message.

    Requests analog synthesizers to retune. Rarely used with modern DAWs.

    Returns:
        Single byte: [F6]
    """
    return [TUNE_REQUEST]


@dataclass
class TransportPreference:
    """Configuration for transport command emission.

    Attributes:
        enabled: Whether transport control is active (default False)
        device_id: Target device ID for MMC (0x7F = all, clamped to 0-127)
        prefer_mmc: If True, emit MMC for compatible commands; if False,
                    use MIDI real-time bytes where available
    """

    enabled: bool = False
    device_id: int = 0x7F
    prefer_mmc: bool = True

    def __post_init__(self) -> None:
        """Clamp device_id to valid MIDI range."""
        self.device_id = max(0, min(self.device_id, 0x7F))

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> TransportPreference:
        """Construct from dictionary (deserialization)."""
        return cls(**data)


def build_command(
    name: str,
    pref: TransportPreference,
) -> List[List[int]]:
    """Build one or more MIDI messages for a named transport command.

    Routes to either MMC or MIDI real-time depending on pref.prefer_mmc and
    whether a real-time equivalent exists.

    Args:
        name: Transport command name (play, stop, pause, continue, record_strobe, etc.)
        pref: TransportPreference configuration

    Returns:
        List of MIDI messages (each message is a List[int]). Empty list if
        command is unknown.

    Behavior:
        - "play": MMC if prefer_mmc, else realtime_start
        - "stop": MMC if prefer_mmc, else realtime_stop
        - "continue": MMC if prefer_mmc, else realtime_continue
        - "pause", "record_strobe", "rewind", "fast_forward": MMC only
        - "locate": Not supported (requires parameters; see mmc_locate)
        - Unknown: Empty list
    """
    if not pref.enabled:
        return []

    if name == "play":
        if pref.prefer_mmc:
            return [mmc("play", pref.device_id)]
        else:
            return [realtime_start()]
    elif name == "stop":
        if pref.prefer_mmc:
            return [mmc("stop", pref.device_id)]
        else:
            return [realtime_stop()]
    elif name == "continue":
        if pref.prefer_mmc:
            return [mmc("deferred_play", pref.device_id)]
        else:
            return [realtime_continue()]
    elif name == "pause":
        return [mmc("pause", pref.device_id)]
    elif name == "record_strobe":
        return [mmc("record_strobe", pref.device_id)]
    elif name == "rewind":
        return [mmc("rewind", pref.device_id)]
    elif name == "fast_forward":
        return [mmc("fast_forward", pref.device_id)]
    else:
        return []
