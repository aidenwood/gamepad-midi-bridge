"""4-band audio-reactive simulator for MIDI CC generation.

This module extends audio_reactive_sim to support independent simulators for
four audio frequency bands: bass, low_mid, high_mid, treble. Each band has its
own AudioReactiveSim instance and emits independent CCs.

Features:
  - 4-band configuration: bass, low_mid, high_mid, treble.
  - Caller passes 4 amplitude levels (one per band) and receives 4 CCs.
  - Each band is an independent AudioReactiveSim with own CC number, channel, mode.
  - Pure stdlib: No Qt, no real audio, deterministic and testable.
  - Reuses AudioReactiveConfig and AudioReactiveSim from audio_reactive_sim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from gamepad_midi_bridge.audio_reactive_sim import (
    AudioReactiveConfig,
    AudioReactiveSim,
)


# Band names in canonical order.
BAND_NAMES = ["bass", "low_mid", "high_mid", "treble"]


@dataclass
class AudioBandConfig:
    """Configuration for a single audio band.

    Attributes:
        name: Band name (e.g., "bass", "low_mid", "high_mid", "treble").
        audio_config: Serialized AudioReactiveConfig as dict for this band.
                      Used to instantiate AudioReactiveSim per band.
    """

    name: str
    audio_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "audio_config": self.audio_config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AudioBandConfig:
        """Deserialize from a dict."""
        return cls(
            name=data.get("name", ""),
            audio_config=data.get("audio_config", {}),
        )


@dataclass
class AudioBandsConfig:
    """Configuration for 4-band audio-reactive MIDI CC simulator.

    Attributes:
        enabled: Whether the 4-band simulator is active.
        bands: List of AudioBandConfig for each band (typically 4).
    """

    enabled: bool = False
    bands: List[AudioBandConfig] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "bands": [band.to_dict() for band in self.bands],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AudioBandsConfig:
        """Deserialize from a dict."""
        bands = [
            AudioBandConfig.from_dict(band_data)
            for band_data in data.get("bands", [])
        ]
        return cls(
            enabled=data.get("enabled", False),
            bands=bands,
        )


class AudioBandsSim:
    """4-band audio-reactive MIDI CC simulator.

    Accepts 4 synthetic audio level samples (bass, low_mid, high_mid, treble)
    and emits independent CCs for each band based on their configurations.
    """

    def __init__(self, cfg: AudioBandsConfig) -> None:
        """Initialize simulator with 4-band config.

        Args:
            cfg: AudioBandsConfig describing the 4 bands and their parameters.
        """
        self.cfg = cfg

        # Build a dict mapping band name -> AudioReactiveSim.
        self._sims: Dict[str, AudioReactiveSim] = {}
        for band_cfg in cfg.bands:
            # Deserialize the audio_config dict into an AudioReactiveConfig.
            audio_cfg = AudioReactiveConfig.from_dict(band_cfg.audio_config)
            self._sims[band_cfg.name] = AudioReactiveSim(audio_cfg)

    def feed(
        self, bass: float, low_mid: float, high_mid: float, treble: float, now_s: float
    ) -> List[Tuple[int, int, int]]:
        """Feed 4 synthetic audio level samples and return list of (cc, channel, value) tuples.

        Args:
            bass: Audio amplitude for bass band (nominally 0..1).
            low_mid: Audio amplitude for low_mid band (nominally 0..1).
            high_mid: Audio amplitude for high_mid band (nominally 0..1).
            treble: Audio amplitude for treble band (nominally 0..1).
            now_s: Current time in seconds.

        Returns:
            List of (cc, channel, value) tuples for each configured band, in BAND_NAMES order.
            If a band is not configured, it is skipped.
        """
        levels = [bass, low_mid, high_mid, treble]
        return self.feed_array(levels, now_s)

    def feed_array(
        self, levels: List[float], now_s: float
    ) -> List[Tuple[int, int, int]]:
        """Feed array of 4 synthetic audio level samples and return list of (cc, channel, value) tuples.

        Args:
            levels: List of 4 audio amplitudes [bass, low_mid, high_mid, treble].
                    Extra elements are ignored; missing elements are treated as 0.0.
            now_s: Current time in seconds.

        Returns:
            List of (cc, channel, value) tuples for each configured band, in BAND_NAMES order.
        """
        results: List[Tuple[int, int, int]] = []

        # Process each configured band in canonical order.
        for band_name in BAND_NAMES:
            if band_name not in self._sims:
                # Band not configured, skip.
                continue

            # Get the level for this band (default to 0.0 if index out of range).
            band_idx = BAND_NAMES.index(band_name)
            level = levels[band_idx] if band_idx < len(levels) else 0.0

            # Feed the level to the band's simulator.
            sim = self._sims[band_name]
            cc_value = sim.feed(level, now_s)

            # Get the config to extract cc number and channel.
            # Find the corresponding band config.
            band_cfg = None
            for cfg_band in self.cfg.bands:
                if cfg_band.name == band_name:
                    band_cfg = cfg_band
                    break

            if band_cfg is not None:
                # Get cc and channel from the deserialized config.
                audio_cfg = AudioReactiveConfig.from_dict(band_cfg.audio_config)
                cc = audio_cfg.cc
                channel = audio_cfg.channel
                results.append((cc, channel, cc_value))

        return results

    def reset(self) -> None:
        """Reset all band simulators.

        Clears state for all bands so the next feed() starts fresh.
        """
        for sim in self._sims.values():
            sim.reset()

    def band_names(self) -> List[str]:
        """Return list of currently configured band names, in canonical order.

        Returns:
            List of band names that are configured (in BAND_NAMES order).
        """
        return [name for name in BAND_NAMES if name in self._sims]

    def slot_count(self) -> int:
        """Return number of configured bands.

        Returns:
            Number of band simulators currently active.
        """
        return len(self._sims)
