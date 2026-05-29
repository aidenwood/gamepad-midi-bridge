"""Groove-template library for micro-timing offsets on beat grids.

Pure stdlib module for applying groove templates (swing, shuffle, drag, push, etc.)
to a quantized beat grid. Groove templates add micro-timing offsets to events
without quantizing them—giving grids the human feel of being "behind", "ahead",
or "swung" while remaining metronomically aligned.

Grooves are defined as a list of per-subdivision offsets over one bar. For example,
a 1/16 grid over 4/4 time has 16 offsets (one per sixteenth note). Each groove
template can be scaled by intensity (0..2) to vary the effect strength.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class GrooveTemplate:
    """A groove template defining micro-timing offsets per subdivision.

    Attributes:
        name: Unique identifier for the groove (e.g. "swing_light").
        offsets_ms: List of timing offsets in milliseconds, one per subdivision.
            For a 1/16 grid, this is a 16-element list; each entry shifts that
            grid index forward (positive) or backward (negative).
        description: Human-readable description of the groove style.
    """

    name: str
    offsets_ms: List[float]
    description: str = ""

    def to_dict(self) -> Dict[str, any]:
        """Serialize groove to a dictionary for storage.

        Returns:
            Dictionary with keys: name, offsets_ms, description.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "GrooveTemplate":
        """Deserialise groove from a dictionary.

        Args:
            data: Dictionary with keys: name, offsets_ms, description.

        Returns:
            GrooveTemplate instance.

        Examples:
            >>> d = {"name": "swing", "offsets_ms": [0, 15, 0, 15], "description": "Light swing"}
            >>> gt = GrooveTemplate.from_dict(d)
            >>> gt.name
            'swing'
        """
        return GrooveTemplate(
            name=data.get("name", "straight"),
            offsets_ms=data.get("offsets_ms", [0.0] * 16),
            description=data.get("description", ""),
        )


@dataclass
class GrooveConfig:
    """Configuration for applying groove templates to a grid.

    Attributes:
        enabled: Whether groove is active.
        template_name: Name of the groove template to use (validated; unknown → "straight").
        intensity: Scaling factor for offsets (clamped 0..2; 1.0 = normal, 0.5 = half, 2.0 = double).
    """

    enabled: bool = False
    template_name: str = "straight"
    intensity: float = 1.0

    def __post_init__(self) -> None:
        """Validate and clamp config values."""
        # Validate template name; default to "straight" if unknown
        if self.template_name not in BUILTIN_GROOVES:
            self.template_name = "straight"

        # Clamp intensity to 0..2
        self.intensity = max(0.0, min(2.0, self.intensity))

    def to_dict(self) -> Dict[str, any]:
        """Serialize config to a dictionary for storage.

        Returns:
            Dictionary with keys: enabled, template_name, intensity.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, any]) -> "GrooveConfig":
        """Deserialise config from a dictionary.

        Args:
            data: Dictionary with keys: enabled, template_name, intensity.

        Returns:
            GrooveConfig instance with validated values.

        Examples:
            >>> config = GrooveConfig.from_dict({"enabled": True, "template_name": "swing_light", "intensity": 0.8})
            >>> config.enabled
            True
            >>> config.intensity
            0.8
        """
        return GrooveConfig(
            enabled=data.get("enabled", False),
            template_name=data.get("template_name", "straight"),
            intensity=data.get("intensity", 1.0),
        )


# Built-in groove templates (16-entry patterns for 1/16 grid over 4/4)
BUILTIN_GROOVES: Dict[str, GrooveTemplate] = {
    "straight": GrooveTemplate(
        name="straight",
        offsets_ms=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        description="No swing; perfectly quantized grid.",
    ),
    "swing_light": GrooveTemplate(
        name="swing_light",
        offsets_ms=[0, 15, 0, 15, 0, 15, 0, 15, 0, 15, 0, 15, 0, 15, 0, 15],
        description="Light 1/16 swing: every odd sixteenth nudged forward 15ms.",
    ),
    "swing_heavy": GrooveTemplate(
        name="swing_heavy",
        offsets_ms=[0, 40, 0, 40, 0, 40, 0, 40, 0, 40, 0, 40, 0, 40, 0, 40],
        description="Heavy 1/16 swing: every odd sixteenth nudged forward 40ms.",
    ),
    "shuffle": GrooveTemplate(
        name="shuffle",
        offsets_ms=[0, 30, 0, 30, 0, 30, 0, 30, 0, 30, 0, 30, 0, 30, 0, 30],
        description="Shuffle feel: alternating pattern every sixteenth.",
    ),
    "drag": GrooveTemplate(
        name="drag",
        offsets_ms=[-8, -8, -8, -8, -8, -8, -8, -8, -8, -8, -8, -8, -8, -8, -8, -8],
        description="Drag (behind-the-beat): all sixteenths pulled back 8ms.",
    ),
    "push": GrooveTemplate(
        name="push",
        offsets_ms=[6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6],
        description="Push (ahead-of-the-beat): all sixteenths pushed forward 6ms.",
    ),
}


def get_template(name: str) -> GrooveTemplate:
    """Retrieve a groove template by name.

    Args:
        name: Groove template name (e.g. "swing_light").

    Returns:
        GrooveTemplate instance. If name is unknown, returns "straight".

    Examples:
        >>> gt = get_template("swing_light")
        >>> gt.offsets_ms[1]
        15
        >>> gt = get_template("nonexistent")
        >>> gt.name
        'straight'
    """
    return BUILTIN_GROOVES.get(name, BUILTIN_GROOVES["straight"])


def apply_groove(grid_time_s: float, grid_index: int, cfg: GrooveConfig) -> float:
    """Apply groove offsets to a grid-aligned time.

    Args:
        grid_time_s: A grid-aligned time in seconds.
        grid_index: Index into the groove template (e.g. which sixteenth in a bar).
        cfg: GrooveConfig with template_name and intensity.

    Returns:
        Groove-adjusted time in seconds (grid_time_s + offset in seconds).

    Examples:
        >>> cfg = GrooveConfig(enabled=True, template_name="swing_light", intensity=1.0)
        >>> apply_groove(1.0, 1, cfg)  # odd index, swing_light
        1.015
        >>> apply_groove(1.0, 0, cfg)  # even index, no offset
        1.0
        >>> cfg_half = GrooveConfig(enabled=True, template_name="swing_light", intensity=0.5)
        >>> apply_groove(1.0, 1, cfg_half)
        1.0075
    """
    if not cfg.enabled:
        return grid_time_s

    template = get_template(cfg.template_name)

    # Get offset for this grid index (wrap modulo template length)
    offset_ms = template.offsets_ms[grid_index % len(template.offsets_ms)]

    # Scale by intensity and convert to seconds
    scaled_offset_s = (offset_ms * cfg.intensity) / 1000.0

    return grid_time_s + scaled_offset_s


def list_groove_names() -> List[str]:
    """List all available built-in groove template names.

    Returns:
        Sorted list of groove names.

    Examples:
        >>> names = list_groove_names()
        >>> len(names)
        6
        >>> "swing_light" in names
        True
    """
    return sorted(list(BUILTIN_GROOVES.keys()))


def build_custom(
    name: str, pattern: List[float], description: str = ""
) -> GrooveTemplate:
    """Build a custom groove template from a pattern.

    Args:
        name: Unique identifier for the custom groove.
        pattern: List of offsets in milliseconds. Padded with zeros to 16 entries,
            or truncated to 16 if longer. Each offset is clamped to [-200, +200]ms.
        description: Optional description.

    Returns:
        GrooveTemplate with validated and normalized offsets.

    Examples:
        >>> gt = build_custom("my_groove", [0, 20, 0, 20])
        >>> len(gt.offsets_ms)
        16
        >>> gt.offsets_ms[1]
        20
        >>> gt = build_custom("oversized", list(range(20)))
        >>> len(gt.offsets_ms)
        16
        >>> gt = build_custom("clamped", [300, -300])
        >>> gt.offsets_ms[0]
        200
        >>> gt.offsets_ms[1]
        -200
    """
    # Pad or truncate to 16 entries
    normalized = list(pattern[:16])  # Truncate if longer
    normalized.extend([0.0] * (16 - len(normalized)))  # Pad if shorter

    # Clamp each offset to [-200, +200]
    clamped = [max(-200.0, min(200.0, offset)) for offset in normalized]

    return GrooveTemplate(name=name, offsets_ms=clamped, description=description)
