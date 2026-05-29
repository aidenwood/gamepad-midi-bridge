"""Polyrhythm sequencer — interlocking Euclidean patterns (e.g. 3-against-4).

Runs two Euclidean patterns simultaneously at different lengths, producing
complex rhythmic interlocks. No Qt dependencies, pure stdlib + dataclass.

Example:
    voice_a = PolyrhythmVoice(pulses=3, steps=8)  # E(3,8)
    voice_b = PolyrhythmVoice(pulses=5, steps=16) # E(5,16)
    cfg = PolyrhythmConfig(enabled=True, voice_a=voice_a, voice_b=voice_b)
    poly = Polyrhythm(cfg)

    # Tick at 1.0s (assuming tick_rate_hz=8.0, so interval=0.125s)
    fires = poly.tick(0.0)      # → [("a", voice_a), ("b", voice_b)]
    fires = poly.tick(0.0625)   # → [] (not enough time elapsed)
    fires = poly.tick(0.125)    # → check E(3,8)[1] and E(5,16)[1]
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from gamepad_midi_bridge.euclidean import bjorklund, rotate


def lcm(a: int, b: int) -> int:
    """Least common multiple of two integers."""
    from math import gcd
    return abs(a * b) // gcd(a, b) if a and b else 0


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp a value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


@dataclass
class PolyrhythmVoice:
    """One voice of a polyrhythm — an Euclidean pattern with MIDI metadata.

    Attributes:
        pulses: Number of events to distribute (clamped 0..32).
        steps: Total number of steps in pattern (clamped 1..32).
        rotation: Pattern offset (default 0).
        note: MIDI note number (clamped 0..127, default 60).
        velocity: MIDI velocity (clamped 1..127, default 100).
        channel: MIDI channel (clamped 1..16, default 1).
    """

    pulses: int
    steps: int
    rotation: int = 0
    note: int = 60
    velocity: int = 100
    channel: int = 1

    def __post_init__(self):
        """Clamp all fields to valid ranges."""
        self.pulses = _clamp(self.pulses, 0, 32)
        self.steps = _clamp(self.steps, 1, 32)
        self.note = _clamp(self.note, 0, 127)
        self.velocity = _clamp(self.velocity, 1, 127)
        self.channel = _clamp(self.channel, 1, 16)

    def to_pattern(self) -> List[int]:
        """Generate this voice's rhythm as a list of 0s and 1s.

        Returns:
            List of 0s and 1s, length = steps. Respects rotation.
        """
        pattern = bjorklund(self.pulses, self.steps)
        return rotate(pattern, self.rotation)


@dataclass
class PolyrhythmConfig:
    """Configuration for a polyrhythm sequencer.

    Attributes:
        enabled: Whether polyrhythm is active (default False).
        voice_a: First voice (default E(3,8)).
        voice_b: Second voice (default E(5,16)).
        tick_rate_hz: Clock rate in Hz (clamped 0.5..50.0, default 8.0).
    """

    enabled: bool = False
    voice_a: PolyrhythmVoice = field(default_factory=lambda: PolyrhythmVoice(pulses=3, steps=8))
    voice_b: PolyrhythmVoice = field(default_factory=lambda: PolyrhythmVoice(pulses=5, steps=16))
    tick_rate_hz: float = 8.0

    def __post_init__(self):
        """Clamp tick_rate_hz to valid range."""
        self.tick_rate_hz = _clamp(
            int(self.tick_rate_hz * 10) / 10,  # Round to 1 decimal
            0.5,
            50.0,
        )

    def to_dict(self) -> dict:
        """Serialize config to a dictionary (including nested voices).

        Returns:
            Dict with keys: enabled, voice_a, voice_b, tick_rate_hz.
            voice_a and voice_b are themselves dicts with
            keys: pulses, steps, rotation, note, velocity, channel.
        """
        return {
            "enabled": self.enabled,
            "voice_a": {
                "pulses": self.voice_a.pulses,
                "steps": self.voice_a.steps,
                "rotation": self.voice_a.rotation,
                "note": self.voice_a.note,
                "velocity": self.voice_a.velocity,
                "channel": self.voice_a.channel,
            },
            "voice_b": {
                "pulses": self.voice_b.pulses,
                "steps": self.voice_b.steps,
                "rotation": self.voice_b.rotation,
                "note": self.voice_b.note,
                "velocity": self.voice_b.velocity,
                "channel": self.voice_b.channel,
            },
            "tick_rate_hz": self.tick_rate_hz,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PolyrhythmConfig":
        """Deserialize config from a dictionary.

        Args:
            data: Dict with nested voice configs (voice_a, voice_b).

        Returns:
            PolyrhythmConfig instance. Missing keys use defaults.
        """
        voice_a_data = data.get("voice_a", {})
        voice_b_data = data.get("voice_b", {})

        voice_a = PolyrhythmVoice(
            pulses=voice_a_data.get("pulses", 3),
            steps=voice_a_data.get("steps", 8),
            rotation=voice_a_data.get("rotation", 0),
            note=voice_a_data.get("note", 60),
            velocity=voice_a_data.get("velocity", 100),
            channel=voice_a_data.get("channel", 1),
        )

        voice_b = PolyrhythmVoice(
            pulses=voice_b_data.get("pulses", 5),
            steps=voice_b_data.get("steps", 16),
            rotation=voice_b_data.get("rotation", 0),
            note=voice_b_data.get("note", 60),
            velocity=voice_b_data.get("velocity", 100),
            channel=voice_b_data.get("channel", 1),
        )

        return cls(
            enabled=data.get("enabled", False),
            voice_a=voice_a,
            voice_b=voice_b,
            tick_rate_hz=data.get("tick_rate_hz", 8.0),
        )


class Polyrhythm:
    """Polyrhythm sequencer — runs two Euclidean patterns simultaneously.

    Tracks step positions for both voices independently, fires them based
    on their individual patterns and a shared clock rate. No global state
    beyond the instance.

    Example:
        cfg = PolyrhythmConfig(enabled=True)
        poly = Polyrhythm(cfg)
        fires = poly.tick(0.0)  # → list of ("voice_name", voice_obj) tuples
    """

    def __init__(self, cfg: PolyrhythmConfig):
        """Initialize polyrhythm with a config.

        Args:
            cfg: PolyrhythmConfig instance.
        """
        self.cfg = cfg
        self._step_a = 0
        self._step_b = 0
        self._last_tick_at: Optional[float] = None

    def tick(self, now_s: float) -> List[Tuple[str, PolyrhythmVoice]]:
        """Advance the sequencer clock and fire any voices at this tick.

        Checks if enough time (1/tick_rate_hz) has elapsed since last tick.
        If so, reads both voice patterns, checks which voice(s) have a pulse
        at their current step, and advances both step counters.

        Args:
            now_s: Current time in seconds (floating point, can be any epoch).

        Returns:
            List of ("voice_name", voice_obj) tuples for voices that fired.
            Empty list if not enough time has elapsed.

        Example:
            poly = Polyrhythm(PolyrhythmConfig(enabled=True))
            fires = poly.tick(0.0)      # 1st tick
            fires = poly.tick(0.05)     # Not enough (< 0.125s)
            fires = poly.tick(0.125)    # 2nd tick fires
        """
        if not self.cfg.enabled:
            return []

        # Check if enough time has elapsed
        if self._last_tick_at is not None:
            interval = 1.0 / self.cfg.tick_rate_hz
            if now_s - self._last_tick_at < interval:
                return []

        self._last_tick_at = now_s

        result: List[Tuple[str, PolyrhythmVoice]] = []

        # Get patterns
        pattern_a = self.cfg.voice_a.to_pattern()
        pattern_b = self.cfg.voice_b.to_pattern()

        # Check voice_a
        if pattern_a[self._step_a] == 1:
            result.append(("a", self.cfg.voice_a))

        # Check voice_b
        if pattern_b[self._step_b] == 1:
            result.append(("b", self.cfg.voice_b))

        # Advance step counters
        self._step_a = (self._step_a + 1) % self.cfg.voice_a.steps
        self._step_b = (self._step_b + 1) % self.cfg.voice_b.steps

        return result

    def reset(self) -> None:
        """Reset step counters to 0 and clear tick timer.

        Used to restart the sequencer from the beginning.
        """
        self._step_a = 0
        self._step_b = 0
        self._last_tick_at = None

    def current_steps(self) -> Tuple[int, int]:
        """Get current step positions for both voices.

        Returns:
            Tuple of (_step_a, _step_b).
        """
        return (self._step_a, self._step_b)

    def combined_length(self) -> int:
        """Get the cycle length where both patterns align.

        Both voices repeat independently, but their combined pattern
        repeats at the LCM of their step counts.

        Returns:
            LCM of voice_a.steps and voice_b.steps.

        Example:
            voice_a = PolyrhythmVoice(pulses=3, steps=8)
            voice_b = PolyrhythmVoice(pulses=5, steps=16)
            poly = Polyrhythm(PolyrhythmConfig(voice_a=voice_a, voice_b=voice_b))
            poly.combined_length()  # → 16
        """
        return lcm(self.cfg.voice_a.steps, self.cfg.voice_b.steps)
