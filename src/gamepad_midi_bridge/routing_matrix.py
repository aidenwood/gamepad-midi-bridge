"""16x16 channel routing matrix for MIDI input→output mapping.

Allows complex channel routing: splitting (one input → multiple outputs),
merging (multiple inputs → one output), and broadcasting. Pure data + helpers,
no side effects.

Default routing is identity: each input channel routes only to itself (channel 1→1,
2→2, ..., 16→16). Routes can be added/removed freely; a channel with multiple
True entries in its row broadcasts to all those outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoutingMatrixConfig:
    """Configuration for the channel routing matrix.

    Attributes:
        enabled: If True, apply routing. If False, all messages pass through unchanged.
        matrix: 16x16 boolean matrix where matrix[in_ch][out_ch] = True means
                route input channel in_ch to output channel out_ch.
                Stored as list of lists; automatically padded/trimmed to 16x16
                on deserialize.
        pass_through_unrouted: If True, input channels with no routes in their row
                               pass through to their own channel number (same as identity).
                               If False, unrouted channels produce no output.
    """

    enabled: bool = False
    matrix: list[list[bool]] = field(
        default_factory=lambda: [[i == j for j in range(16)] for i in range(16)]
    )
    pass_through_unrouted: bool = False

    def __post_init__(self) -> None:
        """Enforce 16x16 matrix on init."""
        self._ensure_16x16()

    def _ensure_16x16(self) -> None:
        """Pad or trim matrix to exactly 16x16."""
        # Ensure outer list is 16 rows
        if len(self.matrix) < 16:
            self.matrix.extend([
                [False] * 16 for _ in range(16 - len(self.matrix))
            ])
        else:
            self.matrix = self.matrix[:16]

        # Ensure each row is 16 columns
        for i in range(16):
            if len(self.matrix[i]) < 16:
                self.matrix[i].extend([False] * (16 - len(self.matrix[i])))
            else:
                self.matrix[i] = self.matrix[i][:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for storage/serialization.

        Returns:
            A dict with keys 'enabled', 'matrix', and 'pass_through_unrouted'.
        """
        return {
            "enabled": self.enabled,
            "matrix": [row.copy() for row in self.matrix],
            "pass_through_unrouted": self.pass_through_unrouted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingMatrixConfig:
        """Deserialize from a dictionary with safe defaults.

        Args:
            data: A dictionary with optional keys 'enabled', 'matrix',
                  'pass_through_unrouted'. Missing keys use defaults.
                  Matrix is padded/trimmed to 16x16.

        Returns:
            A new RoutingMatrixConfig instance.
        """
        enabled = data.get("enabled", False)
        pass_through = data.get("pass_through_unrouted", False)

        # Default to identity matrix
        matrix = data.get("matrix", [
            [i == j for j in range(16)] for i in range(16)
        ])

        # Ensure matrix is a list of lists (in case of corrupted data)
        if not isinstance(matrix, list):
            matrix = [[i == j for j in range(16)] for i in range(16)]
        else:
            matrix = [row if isinstance(row, list) else [False] * 16
                      for row in matrix]

        cfg = cls(enabled=enabled, matrix=matrix, pass_through_unrouted=pass_through)
        cfg._ensure_16x16()  # Pad/trim to 16x16
        return cfg


class RoutingMatrix:
    """16x16 channel routing matrix for MIDI input→output mapping.

    Manages which input channels route to which output channels.
    All channel numbers are 1-based (1..16).
    """

    def __init__(self, cfg: RoutingMatrixConfig) -> None:
        """Initialize routing matrix from config.

        Args:
            cfg: RoutingMatrixConfig instance. Config matrix is copied;
                 any changes to config.matrix after init do not affect this instance.
        """
        self.enabled = cfg.enabled
        self.pass_through_unrouted = cfg.pass_through_unrouted
        # Deep copy the matrix to isolate from config changes
        self.matrix = [row.copy() for row in cfg.matrix]

    def route(self, in_channel_1_16: int) -> list[int]:
        """Return list of output channels for a given input channel.

        Args:
            in_channel_1_16: Input channel number (1..16). Clamped to valid range.

        Returns:
            List of 1-based output channel numbers. Returns empty list if no routes
            and pass_through_unrouted is False. Returns [in_channel_1_16] if that
            channel has no routes but pass_through_unrouted is True.
        """
        # Clamp input channel to 1..16
        in_ch = max(1, min(in_channel_1_16, 16))
        idx = in_ch - 1

        # Collect all True entries in this row
        routes = [i + 1 for i in range(16) if self.matrix[idx][i]]

        if routes:
            return routes

        # No routes found
        if self.pass_through_unrouted:
            return [in_ch]
        return []

    def set_route(
        self, in_ch: int, out_ch: int, enabled: bool = True
    ) -> None:
        """Set a single route from input channel to output channel.

        Args:
            in_ch: Input channel (1..16). Clamped to valid range.
            out_ch: Output channel (1..16). Clamped to valid range.
            enabled: If True, enable the route. If False, disable it.
        """
        in_idx = max(0, min(in_ch - 1, 15))
        out_idx = max(0, min(out_ch - 1, 15))
        self.matrix[in_idx][out_idx] = enabled

    def toggle_route(self, in_ch: int, out_ch: int) -> bool:
        """Toggle a route from input to output channel.

        Args:
            in_ch: Input channel (1..16). Clamped to valid range.
            out_ch: Output channel (1..16). Clamped to valid range.

        Returns:
            The new route state (True = enabled, False = disabled).
        """
        in_idx = max(0, min(in_ch - 1, 15))
        out_idx = max(0, min(out_ch - 1, 15))
        self.matrix[in_idx][out_idx] = not self.matrix[in_idx][out_idx]
        return self.matrix[in_idx][out_idx]

    def is_routed(self, in_ch: int, out_ch: int) -> bool:
        """Check if a route is enabled.

        Args:
            in_ch: Input channel (1..16). Clamped to valid range.
            out_ch: Output channel (1..16). Clamped to valid range.

        Returns:
            True if route is enabled, False otherwise.
        """
        in_idx = max(0, min(in_ch - 1, 15))
        out_idx = max(0, min(out_ch - 1, 15))
        return self.matrix[in_idx][out_idx]

    def clear_row(self, in_ch: int) -> None:
        """Zero all routes for a given input channel.

        Args:
            in_ch: Input channel (1..16). Clamped to valid range.
        """
        idx = max(0, min(in_ch - 1, 15))
        self.matrix[idx] = [False] * 16

    def clear_all(self) -> None:
        """Zero the entire routing matrix."""
        self.matrix = [[False] * 16 for _ in range(16)]

    def set_identity(self) -> None:
        """Reset matrix to identity: each input → only itself."""
        self.matrix = [[i == j for j in range(16)] for i in range(16)]

    def set_broadcast(self, in_ch: int) -> None:
        """Make an input channel broadcast to all 16 output channels.

        Args:
            in_ch: Input channel (1..16). Clamped to valid range.
        """
        idx = max(0, min(in_ch - 1, 15))
        self.matrix[idx] = [True] * 16

    def set_merge(self, out_ch: int) -> None:
        """Make all 16 input channels feed into a single output channel.

        Args:
            out_ch: Output channel (1..16). Clamped to valid range.
        """
        out_idx = max(0, min(out_ch - 1, 15))
        for i in range(16):
            self.matrix[i][out_idx] = True

    def total_routes(self) -> int:
        """Count total number of enabled routes (True entries).

        Returns:
            Number of True entries in the entire matrix.
        """
        return sum(sum(row) for row in self.matrix)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for storage/serialization.

        Returns:
            A dict with keys 'enabled', 'matrix', and 'pass_through_unrouted'.
        """
        return {
            "enabled": self.enabled,
            "matrix": [row.copy() for row in self.matrix],
            "pass_through_unrouted": self.pass_through_unrouted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingMatrix:
        """Deserialize from a dictionary.

        Args:
            data: A dictionary with optional keys 'enabled', 'matrix',
                  'pass_through_unrouted'. Delegates to RoutingMatrixConfig.from_dict
                  for safe deserialization.

        Returns:
            A new RoutingMatrix instance.
        """
        cfg = RoutingMatrixConfig.from_dict(data)
        return cls(cfg)
