"""Mapping recommender engine: suggests improvements to controller mappings.

Given a mapping dict + optional performance stats snapshot, generates actionable
recommendations to improve the mapping (e.g. velocity range, unused triggers,
narrow note ranges).

Pure stdlib only; no Qt dependency so it can run in worker threads.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Any, List, Dict


@dataclass
class Recommendation:
    """A single recommendation for mapping improvement."""

    severity: str  # "info" | "suggestion" | "warning"
    category: str  # "velocity" | "trigger" | "stick" | "button" | "channel" | "performance"
    target_path: str  # dotted path to the relevant mapping field
    current_value: Any  # current value at target_path
    suggested_value: Any  # suggested replacement value
    reason: str  # human-readable explanation
    confidence: float = 0.5  # 0..1; how confident we are in the suggestion

    def __post_init__(self) -> None:
        """Clamp confidence to valid range."""
        self.confidence = max(0.0, min(1.0, self.confidence))

    def to_dict(self) -> dict:
        """Serialize recommendation to dict for JSON round-trip."""
        return {
            "severity": self.severity,
            "category": self.category,
            "target_path": self.target_path,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Recommendation:
        """Deserialize recommendation from dict."""
        return cls(**data)


def recommend(
    mapping_dict: dict,
    stats: Optional[dict] = None,
) -> List[Recommendation]:
    """Generate recommendations for a mapping based on performance stats.

    Args:
        mapping_dict: The mapping configuration dictionary.
        stats: Optional dict with keys:
            - velocity_peak_bucket: int (which bucket has highest count)
            - velocity_mean: float (average velocity)
            - velocity_min: float (minimum velocity recorded)
            - top_notes: list[tuple[int, float]] (note, frequency pairs)
            - l2_mean_pressure: float (0..1)
            - r2_mean_pressure: float (0..1)
            - stuck_notes_count: int
            - total_notes_played: int
            If stats is None or missing keys, fewer recommendations are returned.

    Returns:
        List of Recommendation objects.
    """
    recs: List[Recommendation] = []
    stats = stats or {}

    # Check 1: schema_version is required
    if "schema_version" not in mapping_dict:
        recs.append(
            Recommendation(
                severity="warning",
                category="performance",
                target_path="schema_version",
                current_value=None,
                suggested_value=4,
                reason="schema_version is required for compatibility",
                confidence=0.95,
            )
        )

    # Check 2: velocity peak detection + velocity_max adjustment
    velocity_peak_bucket = stats.get("velocity_peak_bucket")
    if velocity_peak_bucket is not None:
        # Get velocity config; default to velocity_min=0, velocity_max=127
        velocity_config = mapping_dict.get("velocity", {})
        velocity_min = velocity_config.get("velocity_min", 0)
        velocity_max = velocity_config.get("velocity_max", 127)

        # If peak is at the top bucket AND velocity_max < 127, suggest increase
        # Assume 8 buckets by default; peak bucket is 7
        if velocity_peak_bucket >= 6 and velocity_max < 127:
            recs.append(
                Recommendation(
                    severity="suggestion",
                    category="velocity",
                    target_path="velocity.velocity_max",
                    current_value=velocity_max,
                    suggested_value=127,
                    reason="You frequently hit max velocity; raising velocity_max to 127 gives you more dynamic range",
                    confidence=0.85,
                )
            )

    # Check 3: velocity mean too low + velocity_min too high
    velocity_mean = stats.get("velocity_mean")
    if velocity_mean is not None:
        velocity_config = mapping_dict.get("velocity", {})
        velocity_min = velocity_config.get("velocity_min", 0)
        velocity_max = velocity_config.get("velocity_max", 127)

        if velocity_mean < 30 and velocity_min > 30:
            recs.append(
                Recommendation(
                    severity="suggestion",
                    category="velocity",
                    target_path="velocity.velocity_min",
                    current_value=velocity_min,
                    suggested_value=max(0, velocity_min - 20),
                    reason=f"Your average velocity is {velocity_mean:.0f} but velocity_min is {velocity_min}, restricting your dynamic range",
                    confidence=0.8,
                )
            )

    # Check 4: L2 trigger rarely used
    l2_mean_pressure = stats.get("l2_mean_pressure")
    if l2_mean_pressure is not None and l2_mean_pressure < 0.05:
        triggers_config = mapping_dict.get("triggers", {})
        l2_config = triggers_config.get("L2", {})
        recs.append(
            Recommendation(
                severity="suggestion",
                category="trigger",
                target_path="triggers.L2",
                current_value=l2_config if l2_config else "unmapped",
                suggested_value="remove or remap",
                reason=f"L2 trigger mean pressure is {l2_mean_pressure:.2f}; rarely used — consider removing or remapping to a more important function",
                confidence=0.75,
            )
        )

    # Check 5: R2 trigger rarely used
    r2_mean_pressure = stats.get("r2_mean_pressure")
    if r2_mean_pressure is not None and r2_mean_pressure < 0.05:
        triggers_config = mapping_dict.get("triggers", {})
        r2_config = triggers_config.get("R2", {})
        recs.append(
            Recommendation(
                severity="suggestion",
                category="trigger",
                target_path="triggers.R2",
                current_value=r2_config if r2_config else "unmapped",
                suggested_value="remove or remap",
                reason=f"R2 trigger mean pressure is {r2_mean_pressure:.2f}; rarely used — consider removing or remapping to a more important function",
                confidence=0.75,
            )
        )

    # Check 6: Many stuck notes detected
    stuck_notes_count = stats.get("stuck_notes_count", 0)
    if stuck_notes_count > 5:
        recs.append(
            Recommendation(
                severity="warning",
                category="performance",
                target_path="stuck_note_detector",
                current_value=mapping_dict.get("stuck_note_detector", {}),
                suggested_value={"enabled": True, "stuck_after_s": 10.0},
                reason=f"{stuck_notes_count} stuck notes detected in session; enabling stuck_note_detector with auto_release will prevent hanging notes",
                confidence=0.9,
            )
        )

    # Check 7: No buttons mapped
    buttons = mapping_dict.get("buttons", {})
    if isinstance(buttons, dict) and len(buttons) == 0:
        recs.append(
            Recommendation(
                severity="suggestion",
                category="button",
                target_path="buttons",
                current_value={},
                suggested_value="add some button mappings",
                reason="No buttons are currently mapped; consider adding some for percussion or transport controls",
                confidence=0.7,
            )
        )

    # Check 8: Playing very narrow note range
    top_notes = stats.get("top_notes", [])
    if top_notes and len(top_notes) > 0:
        unique_notes = len(top_notes)
        if unique_notes <= 2:
            notes_str = ", ".join([str(note) for note, _ in top_notes])
            recs.append(
                Recommendation(
                    severity="suggestion",
                    category="performance",
                    target_path="left_stick",
                    current_value="current stick config",
                    suggested_value="enable scale quantize mode",
                    reason=f"Playing only {unique_notes} unique note(s) ({notes_str}); consider enabling scale-quantize stick mode for more harmonic variety",
                    confidence=0.65,
                )
            )

    return recs


def recommendations_by_category(recs: List[Recommendation]) -> Dict[str, List[Recommendation]]:
    """Group recommendations by category.

    Args:
        recs: List of Recommendation objects.

    Returns:
        Dict mapping category string to list of recommendations in that category.
    """
    grouped: Dict[str, List[Recommendation]] = {}
    for rec in recs:
        if rec.category not in grouped:
            grouped[rec.category] = []
        grouped[rec.category].append(rec)
    return grouped


def top_n(recs: List[Recommendation], n: int = 5) -> List[Recommendation]:
    """Return top N recommendations sorted by confidence descending.

    Args:
        recs: List of Recommendation objects.
        n: Maximum number to return.

    Returns:
        Sorted list of up to N recommendations.
    """
    sorted_recs = sorted(recs, key=lambda r: r.confidence, reverse=True)
    return sorted_recs[:n]


def format_recommendation(rec: Recommendation) -> str:
    """Format a recommendation as a human-readable single-line string.

    Args:
        rec: Recommendation object.

    Returns:
        Formatted string.
    """
    confidence_pct = int(rec.confidence * 100)
    return (
        f"[{rec.severity.upper()}] {rec.category}: {rec.target_path} "
        f"({confidence_pct}% confidence) — {rec.reason}"
    )
