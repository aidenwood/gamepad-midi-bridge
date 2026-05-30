"""Velocity curve auto-suggester: recommends a velocity curve preset based on histogram or pull style.

Analyzes either a velocity histogram (distribution of MIDI values) or trigger pull style
to suggest the most appropriate velocity curve. Supports combining both signals for
higher-confidence recommendations.

Pure stdlib, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CurveSuggestion:
    """Recommendation for a velocity curve preset.

    Attributes:
        curve_name: One of the canonical curve modes ("linear", "soft", "hard", "fixed",
                   "exponential", "logarithmic", "s_curve").
        confidence: How confident the suggestion is (0.0..1.0), where 1.0 is certain.
        reason: Human-readable explanation of why this curve was suggested.
    """
    curve_name: str
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        """Normalize curve_name and clamp confidence."""
        from .velocity_curve import VELOCITY_CURVE_MODES

        if self.curve_name not in VELOCITY_CURVE_MODES:
            self.curve_name = "linear"

        self.confidence = max(0.0, min(1.0, self.confidence))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "curve_name": self.curve_name,
            "confidence": float(self.confidence),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurveSuggestion:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to defaults.
        """
        return cls(
            curve_name=data.get("curve_name", "linear"),
            confidence=float(data.get("confidence", 0.0)),
            reason=data.get("reason", ""),
        )


def suggest_from_histogram(buckets: List[int]) -> CurveSuggestion:
    """Analyze a velocity histogram and suggest an appropriate curve.

    Decision logic:
      - Empty histogram (all zeros) → "linear" with low confidence.
      - All activity in bottom 25% of buckets → "soft" curve (boost low velocity).
      - All activity in top 25% of buckets → "hard" curve (penalize low velocity).
      - All activity concentrated in one bucket → "fixed" (low dynamic range).
      - Activity evenly spread across all buckets → "linear" (balanced).
      - Bimodal distribution (peaks at low + high, valley in middle) → "s_curve".

    Confidence is based on how clearly the pattern fits the rule.

    Args:
        buckets: List of bucket counts from a velocity histogram (typically 4..32 buckets).
                Will handle empty lists gracefully.

    Returns:
        CurveSuggestion with curve_name, confidence, and reason.
    """
    if not buckets or all(count == 0 for count in buckets):
        return CurveSuggestion(
            curve_name="linear",
            confidence=0.3,
            reason="No velocity data yet — defaulting to linear curve",
        )

    total = sum(buckets)
    bucket_count = len(buckets)

    # Define activity zones (bottom 25%, middle 50%, top 25%)
    bottom_25_end = max(1, bucket_count // 4)
    top_25_start = max(bottom_25_end + 1, 3 * bucket_count // 4)

    bottom_25_activity = sum(buckets[:bottom_25_end])
    middle_50_activity = sum(buckets[bottom_25_end:top_25_start])
    top_25_activity = sum(buckets[top_25_start:])

    # Rule 1: Concentrated in one bucket
    max_bucket = max(buckets)
    if max_bucket > 0:
        max_bucket_fraction = max_bucket / total
        if max_bucket_fraction > 0.7:
            confidence = min(max_bucket_fraction, 1.0)
            return CurveSuggestion(
                curve_name="fixed",
                confidence=confidence,
                reason=f"Low dynamic range — {int(max_bucket_fraction * 100)}% in one bucket",
            )

    # Rule 2: Bottom 25% dominance
    if bottom_25_activity > 0:
        bottom_fraction = bottom_25_activity / total
        if bottom_fraction > 0.50:
            confidence = min(bottom_fraction, 1.0)
            return CurveSuggestion(
                curve_name="soft",
                confidence=confidence,
                reason="You favour soft touches — boosting low velocities",
            )

    # Rule 3: Top 25% dominance
    if top_25_activity > 0:
        top_fraction = top_25_activity / total
        if top_fraction > 0.50:
            confidence = min(top_fraction, 1.0)
            return CurveSuggestion(
                curve_name="hard",
                confidence=confidence,
                reason="You favour hard hits — penalizing low velocities",
            )

    # Rule 4: Bimodal detection (peaks at low + high, valley in middle)
    if bucket_count >= 4 and bottom_25_activity > 0 and top_25_activity > 0:
        # Check if middle is notably weaker than extremes
        if middle_50_activity > 0:
            middle_fraction = middle_50_activity / total
            extremes_fraction = (bottom_25_activity + top_25_activity) / total

            if middle_fraction < extremes_fraction * 0.6:  # Valley is distinct
                confidence = min(extremes_fraction * 0.9, 1.0)
                return CurveSuggestion(
                    curve_name="s_curve",
                    confidence=confidence,
                    reason="Bimodal pattern — you prefer extremes over middle velocities",
                )

    # Rule 5: Even distribution
    if bucket_count > 0:
        expected_per_bucket = total / bucket_count
        variance = sum((count - expected_per_bucket) ** 2 for count in buckets) / bucket_count
        std_dev = variance ** 0.5

        # If std dev is low relative to mean, distribution is even
        if expected_per_bucket > 0:
            cv = std_dev / expected_per_bucket  # coefficient of variation
            if cv < 0.4:  # Fairly even
                confidence = 1.0 - min(cv, 1.0)
                return CurveSuggestion(
                    curve_name="linear",
                    confidence=confidence,
                    reason="Balanced dynamic range — linear curve recommended",
                )

    # Default fallback
    return CurveSuggestion(
        curve_name="linear",
        confidence=0.5,
        reason="No strong pattern detected — linear curve as default",
    )


def suggest_from_pull_style(style: str) -> CurveSuggestion:
    """Map a trigger pull style to a recommended velocity curve.

    Mappings:
      - "slammy" → "hard" (quick, confident presses need hard curve)
      - "gradual" → "linear" (smooth ramps work well with linear)
      - "feathery" → "soft" (light touches need soft boost)
      - "two_stage" → "s_curve" (plateau then snap mirrors s-curve shape)
      - "twitchy" → "fixed" (erratic inputs benefit from fixed velocity)
      - Unknown styles → "linear" with low confidence

    Args:
        style: One of ("slammy", "gradual", "feathery", "two_stage", "twitchy")
               or any other string.

    Returns:
        CurveSuggestion with curve_name, confidence, and reason.
    """
    style_map = {
        "slammy": ("hard", 0.80, "Slammy style — hard curve for confident presses"),
        "gradual": ("linear", 0.80, "Gradual style — linear curve for smooth ramps"),
        "feathery": ("soft", 0.85, "Feathery style — soft curve to boost light touches"),
        "two_stage": ("s_curve", 0.75, "Two-stage style — s-curve mirrors your plateau-snap pattern"),
        "twitchy": ("fixed", 0.70, "Twitchy style — fixed velocity reduces jitter"),
    }

    if style in style_map:
        curve_name, confidence, reason = style_map[style]
        return CurveSuggestion(
            curve_name=curve_name,
            confidence=confidence,
            reason=reason,
        )

    # Unknown style
    return CurveSuggestion(
        curve_name="linear",
        confidence=0.4,
        reason=f"Unknown pull style '{style}' — defaulting to linear",
    )


def combine(
    histogram_buckets: List[int],
    pull_style: Optional[str] = None,
) -> CurveSuggestion:
    """Combine histogram and optional pull-style signals into a single recommendation.

    Logic:
      - If only histogram provided, return histogram suggestion.
      - If only pull_style provided, return pull_style suggestion.
      - If both provided:
        - If they agree on curve_name, boost confidence (max 1.0) and explain agreement.
        - If they disagree, average confidence and explain trade-off.

    Args:
        histogram_buckets: List of bucket counts from velocity histogram.
        pull_style: Optional trigger pull style string.

    Returns:
        Combined CurveSuggestion.
    """
    histogram_suggestion = suggest_from_histogram(histogram_buckets)

    if pull_style is None:
        return histogram_suggestion

    pull_suggestion = suggest_from_pull_style(pull_style)

    # Both signals available: combine them
    if histogram_suggestion.curve_name == pull_suggestion.curve_name:
        # Agreement: boost confidence
        combined_confidence = min(
            1.0,
            (histogram_suggestion.confidence + pull_suggestion.confidence) / 2.0 + 0.1,
        )
        return CurveSuggestion(
            curve_name=histogram_suggestion.curve_name,
            confidence=combined_confidence,
            reason=f"Histogram and pull style both suggest '{histogram_suggestion.curve_name}' — strong recommendation",
        )
    else:
        # Disagreement: average confidence and weight toward histogram
        # (histogram is usually the stronger signal for fine-tuning)
        combined_confidence = (
            histogram_suggestion.confidence * 0.6 + pull_suggestion.confidence * 0.4
        )
        return CurveSuggestion(
            curve_name=histogram_suggestion.curve_name,
            confidence=combined_confidence,
            reason=f"Histogram suggests '{histogram_suggestion.curve_name}', pull style suggests '{pull_suggestion.curve_name}' — weighting histogram",
        )
