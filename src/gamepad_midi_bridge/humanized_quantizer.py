"""Humanized quantizer: grid quantization + per-event jitter + groove templates.

Pure stdlib module for combining quantize_grid, groove_template, and random jitter
to make quantized events feel less mechanical. Supports seeded RNG for reproducibility.
"""

import math
import random
from dataclasses import dataclass, asdict
from typing import Dict, Optional

from . import bpm_sync, quantize_grid, groove_template


@dataclass
class HumanizedQuantizerConfig:
    """Configuration for humanized quantization.

    Attributes:
        enabled: Whether humanized quantization is active.
        bpm: Tempo in beats per minute (clamped 20–300).
        subdivision: Subdivision to snap to (validated; unknown → "1/16").
        humanize_ms: Standard deviation of timing jitter in milliseconds (clamped 0–50).
        velocity_humanize: Maximum random velocity offset ± (clamped 0–40).
        groove_template_name: Groove template to apply (validated; unknown → "straight").
        groove_intensity: Scaling factor for groove offsets (clamped 0–2).
        seed: Optional random seed for deterministic behavior.
    """

    enabled: bool = False
    bpm: float = 120.0
    subdivision: str = "1/16"
    humanize_ms: float = 5.0
    velocity_humanize: int = 5
    groove_template_name: str = "straight"
    groove_intensity: float = 1.0
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Clamp BPM to 20–300 range
        self.bpm = max(20.0, min(300.0, self.bpm))

        # Validate subdivision; default to "1/16" if unknown
        if self.subdivision not in bpm_sync.SUBDIVISIONS:
            self.subdivision = "1/16"

        # Clamp humanize_ms to 0–50
        self.humanize_ms = max(0.0, min(50.0, self.humanize_ms))

        # Clamp velocity_humanize to 0–40
        self.velocity_humanize = max(0, min(40, self.velocity_humanize))

        # Validate groove template name; default to "straight" if unknown
        if self.groove_template_name not in groove_template.BUILTIN_GROOVES:
            self.groove_template_name = "straight"

        # Clamp groove_intensity to 0–2
        self.groove_intensity = max(0.0, min(2.0, self.groove_intensity))

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with all config fields.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "HumanizedQuantizerConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with config fields.

        Returns:
            HumanizedQuantizerConfig instance with validated values.

        Examples:
            >>> cfg = HumanizedQuantizerConfig.from_dict({
            ...     "enabled": True,
            ...     "bpm": 140,
            ...     "subdivision": "1/8",
            ...     "humanize_ms": 10.0,
            ...     "velocity_humanize": 5,
            ...     "groove_template_name": "swing_light",
            ...     "groove_intensity": 0.8,
            ...     "seed": 42
            ... })
            >>> cfg.bpm
            140.0
        """
        return HumanizedQuantizerConfig(
            enabled=data.get("enabled", False),
            bpm=data.get("bpm", 120.0),
            subdivision=data.get("subdivision", "1/16"),
            humanize_ms=data.get("humanize_ms", 5.0),
            velocity_humanize=data.get("velocity_humanize", 5),
            groove_template_name=data.get("groove_template_name", "straight"),
            groove_intensity=data.get("groove_intensity", 1.0),
            seed=data.get("seed"),
        )


class HumanizedQuantizer:
    """Quantizer combining grid, groove, and jitter for natural-feeling timing.

    Attributes:
        cfg: HumanizedQuantizerConfig instance.
        ref_start_s: Reference start time for the grid (origin).
    """

    def __init__(self, cfg: HumanizedQuantizerConfig, ref_start_s: float = 0.0) -> None:
        """Initialize the humanized quantizer.

        Args:
            cfg: HumanizedQuantizerConfig with bpm, subdivision, jitter, and groove settings.
            ref_start_s: Reference start time in seconds (default: 0.0).
        """
        self.cfg = cfg
        self.ref_start_s = ref_start_s
        # Create a fresh Random instance with the configured seed for reproducibility
        self._rng = random.Random(cfg.seed)

    def quantize_time(self, now_s: float, grid_index: Optional[int] = None) -> float:
        """Quantize and humanize an event time.

        Steps:
        1. Snap to the grid using quantize_grid.next_grid_time.
        2. Compute grid_index from elapsed time if not provided.
        3. Apply groove offset using groove_template.apply_groove.
        4. Add Gaussian jitter ~ Normal(0, humanize_ms / 1000).
        5. Return final time.

        Args:
            now_s: Current time in seconds.
            grid_index: Optional grid index for groove calculation. If not provided,
                computed from elapsed time.

        Returns:
            Quantized and humanized time in seconds.

        Examples:
            >>> cfg = HumanizedQuantizerConfig(
            ...     enabled=True, bpm=120, subdivision="1/4",
            ...     humanize_ms=0, velocity_humanize=0, seed=42
            ... )
            >>> q = HumanizedQuantizer(cfg)
            >>> t = q.quantize_time(0.3)
            >>> abs(t - 0.5) < 0.001  # Should snap to 0.5 (quarter note at 120 BPM)
            True
        """
        # Step 1: Snap to grid
        grid_cfg = quantize_grid.QuantizeGridConfig(
            enabled=True,
            bpm=self.cfg.bpm,
            subdivision=self.cfg.subdivision,
            mode="nearest",
            swing_percent=50.0,
        )
        grid_time_s = quantize_grid.next_grid_time(now_s, self.ref_start_s, grid_cfg)

        # Step 2: Compute grid_index if not provided
        if grid_index is None:
            grid_step_s = bpm_sync.subdivision_ms(self.cfg.bpm, self.cfg.subdivision) / 1000.0
            elapsed = grid_time_s - self.ref_start_s
            if grid_step_s > 0:
                grid_index = int(round(elapsed / grid_step_s))
            else:
                grid_index = 0

        # Step 3: Apply groove offset
        groove_cfg = groove_template.GrooveConfig(
            enabled=True,
            template_name=self.cfg.groove_template_name,
            intensity=self.cfg.groove_intensity,
        )
        grooved_time_s = groove_template.apply_groove(grid_time_s, grid_index, groove_cfg)

        # Step 4: Add Gaussian jitter
        if self.cfg.humanize_ms > 0:
            jitter_s = self._rng.gauss(0.0, self.cfg.humanize_ms / 1000.0)
            final_time_s = grooved_time_s + jitter_s
        else:
            final_time_s = grooved_time_s

        return final_time_s

    def humanize_velocity(self, base_velocity: int) -> int:
        """Apply random humanization offset to a velocity value.

        Returns a velocity offset by a uniformly-distributed random value in the
        range [-velocity_humanize, +velocity_humanize], clamped to [1, 127].

        Args:
            base_velocity: Base MIDI velocity (0–127).

        Returns:
            Humanized velocity, clamped to [1, 127].

        Examples:
            >>> cfg = HumanizedQuantizerConfig(
            ...     enabled=True, velocity_humanize=5, seed=42
            ... )
            >>> q = HumanizedQuantizer(cfg)
            >>> vel = q.humanize_velocity(100)
            >>> 95 <= vel <= 105
            True
            >>> vel = q.humanize_velocity(100)
            >>> vel != 100  # seed=42 produces variation
            True
        """
        if self.cfg.velocity_humanize == 0:
            return base_velocity

        offset = self._rng.randint(-self.cfg.velocity_humanize, self.cfg.velocity_humanize)
        humanized = base_velocity + offset
        # Clamp to valid MIDI range [1, 127]
        return max(1, min(127, humanized))

    def reset(self) -> None:
        """Reset the internal RNG to its initial seed.

        Useful for replaying the same sequence of humanization offsets.

        Examples:
            >>> cfg = HumanizedQuantizerConfig(seed=42, velocity_humanize=5)
            >>> q = HumanizedQuantizer(cfg)
            >>> v1 = q.humanize_velocity(100)
            >>> q.reset()
            >>> v2 = q.humanize_velocity(100)
            >>> v1 == v2
            True
        """
        self._rng = random.Random(self.cfg.seed)

    def seeded_at(self) -> Optional[int]:
        """Return the configured seed, if any.

        Returns:
            The seed value, or None if not seeded.

        Examples:
            >>> cfg = HumanizedQuantizerConfig(seed=42)
            >>> q = HumanizedQuantizer(cfg)
            >>> q.seeded_at()
            42
            >>> cfg_unseeded = HumanizedQuantizerConfig(seed=None)
            >>> q2 = HumanizedQuantizer(cfg_unseeded)
            >>> q2.seeded_at() is None
            True
        """
        return self.cfg.seed
