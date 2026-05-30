"""Tests for velocity_curve_suggester module."""
import pytest

from gamepad_midi_bridge.velocity_curve_suggester import (
    CurveSuggestion,
    suggest_from_histogram,
    suggest_from_pull_style,
    combine,
)


class TestCurveSuggestion:
    """Tests for CurveSuggestion dataclass."""

    def test_curve_suggestion_init(self) -> None:
        """Test basic initialization."""
        suggestion = CurveSuggestion(
            curve_name="linear",
            confidence=0.75,
            reason="test reason",
        )
        assert suggestion.curve_name == "linear"
        assert suggestion.confidence == 0.75
        assert suggestion.reason == "test reason"

    def test_curve_suggestion_invalid_curve_normalized(self) -> None:
        """Test that invalid curve names are normalized to linear."""
        suggestion = CurveSuggestion(
            curve_name="invalid_curve",
            confidence=0.5,
            reason="test",
        )
        assert suggestion.curve_name == "linear"

    def test_curve_suggestion_confidence_clamped_high(self) -> None:
        """Test that confidence > 1.0 is clamped to 1.0."""
        suggestion = CurveSuggestion(
            curve_name="linear",
            confidence=1.5,
            reason="test",
        )
        assert suggestion.confidence == 1.0

    def test_curve_suggestion_confidence_clamped_low(self) -> None:
        """Test that confidence < 0.0 is clamped to 0.0."""
        suggestion = CurveSuggestion(
            curve_name="linear",
            confidence=-0.5,
            reason="test",
        )
        assert suggestion.confidence == 0.0

    def test_curve_suggestion_to_dict(self) -> None:
        """Test serialization to dict."""
        suggestion = CurveSuggestion(
            curve_name="hard",
            confidence=0.85,
            reason="test reason",
        )
        result = suggestion.to_dict()
        assert result["curve_name"] == "hard"
        assert result["confidence"] == 0.85
        assert result["reason"] == "test reason"

    def test_curve_suggestion_from_dict(self) -> None:
        """Test deserialization from dict."""
        data = {
            "curve_name": "soft",
            "confidence": 0.6,
            "reason": "test reason",
        }
        suggestion = CurveSuggestion.from_dict(data)
        assert suggestion.curve_name == "soft"
        assert suggestion.confidence == 0.6
        assert suggestion.reason == "test reason"

    def test_curve_suggestion_round_trip(self) -> None:
        """Test serialization round-trip."""
        original = CurveSuggestion(
            curve_name="s_curve",
            confidence=0.75,
            reason="bimodal pattern detected",
        )
        serialized = original.to_dict()
        restored = CurveSuggestion.from_dict(serialized)
        assert restored.curve_name == original.curve_name
        assert restored.confidence == original.confidence
        assert restored.reason == original.reason


class TestSuggestFromHistogram:
    """Tests for suggest_from_histogram function."""

    def test_empty_histogram(self) -> None:
        """Test that empty histogram returns linear with low confidence."""
        suggestion = suggest_from_histogram([])
        assert suggestion.curve_name == "linear"
        assert suggestion.confidence < 0.5
        assert len(suggestion.reason) > 0

    def test_all_zeros_histogram(self) -> None:
        """Test that all-zero histogram returns linear with low confidence."""
        suggestion = suggest_from_histogram([0, 0, 0, 0, 0, 0, 0, 0])
        assert suggestion.curve_name == "linear"
        assert suggestion.confidence < 0.5

    def test_all_bottom_bucket(self) -> None:
        """Test that activity only in bottom bucket suggests soft curve."""
        # Bottom 25% of 8 buckets is 2 buckets: 0, 1
        suggestion = suggest_from_histogram([50, 50, 0, 0, 0, 0, 0, 0])
        assert suggestion.curve_name == "soft"
        assert suggestion.confidence > 0.5

    def test_all_top_bucket(self) -> None:
        """Test that activity only in top bucket suggests hard curve."""
        # Top 25% of 8 buckets is 2 buckets: 6, 7
        suggestion = suggest_from_histogram([0, 0, 0, 0, 0, 0, 50, 50])
        assert suggestion.curve_name == "hard"
        assert suggestion.confidence > 0.5

    def test_single_bucket_concentrated(self) -> None:
        """Test that >70% in one bucket suggests fixed curve."""
        suggestion = suggest_from_histogram([0, 0, 75, 25, 0, 0, 0, 0])
        assert suggestion.curve_name == "fixed"
        assert suggestion.confidence > 0.7

    def test_even_distribution(self) -> None:
        """Test that even distribution suggests linear curve."""
        suggestion = suggest_from_histogram([10, 10, 10, 10, 10, 10, 10, 10])
        assert suggestion.curve_name == "linear"
        assert suggestion.confidence > 0.5

    def test_bimodal_distribution(self) -> None:
        """Test that bimodal (peaks at extremes, valley in middle) suggests s_curve."""
        # High at bottom (0, 1), high at top (6, 7), low in middle (2-5)
        suggestion = suggest_from_histogram([40, 40, 5, 5, 5, 5, 40, 40])
        assert suggestion.curve_name == "s_curve"
        assert suggestion.confidence > 0.5

    def test_reason_non_empty(self) -> None:
        """Test that all suggestions have non-empty reasons."""
        test_cases = [
            [],
            [0, 0, 0, 0],
            [100, 0, 0, 0],
            [0, 0, 0, 100],
            [25, 25, 25, 25],
            [40, 40, 5, 5],
        ]
        for buckets in test_cases:
            suggestion = suggest_from_histogram(buckets)
            assert len(suggestion.reason) > 0, f"Empty reason for buckets: {buckets}"

    def test_small_histogram_4_buckets(self) -> None:
        """Test with 4 buckets (minimum size)."""
        suggestion = suggest_from_histogram([50, 50, 0, 0])
        # With 4 buckets, bottom 25% = bucket 0, top 25% = bucket 3
        # [50, 50, 0, 0] has 50% in bottom 25% and 50% in middle → pattern not strong
        assert suggestion.curve_name in ["soft", "fixed", "linear"]

    def test_large_histogram_32_buckets(self) -> None:
        """Test with 32 buckets (maximum typical size)."""
        buckets = [1] * 32
        suggestion = suggest_from_histogram(buckets)
        assert suggestion.curve_name == "linear"
        assert suggestion.confidence > 0.5


class TestSuggestFromPullStyle:
    """Tests for suggest_from_pull_style function."""

    def test_slammy_style(self) -> None:
        """Test slammy style maps to hard curve."""
        suggestion = suggest_from_pull_style("slammy")
        assert suggestion.curve_name == "hard"
        assert suggestion.confidence >= 0.75

    def test_gradual_style(self) -> None:
        """Test gradual style maps to linear curve."""
        suggestion = suggest_from_pull_style("gradual")
        assert suggestion.curve_name == "linear"
        assert suggestion.confidence >= 0.75

    def test_feathery_style(self) -> None:
        """Test feathery style maps to soft curve."""
        suggestion = suggest_from_pull_style("feathery")
        assert suggestion.curve_name == "soft"
        assert suggestion.confidence >= 0.80

    def test_two_stage_style(self) -> None:
        """Test two_stage style maps to s_curve."""
        suggestion = suggest_from_pull_style("two_stage")
        assert suggestion.curve_name == "s_curve"
        assert suggestion.confidence >= 0.70

    def test_twitchy_style(self) -> None:
        """Test twitchy style maps to fixed curve."""
        suggestion = suggest_from_pull_style("twitchy")
        assert suggestion.curve_name == "fixed"
        assert suggestion.confidence >= 0.65

    def test_unknown_style(self) -> None:
        """Test unknown style defaults to linear with low confidence."""
        suggestion = suggest_from_pull_style("unknown_style")
        assert suggestion.curve_name == "linear"
        assert suggestion.confidence < 0.5

    def test_reason_non_empty_all_styles(self) -> None:
        """Test that all pull styles have non-empty reasons."""
        styles = ["slammy", "gradual", "feathery", "two_stage", "twitchy", "unknown"]
        for style in styles:
            suggestion = suggest_from_pull_style(style)
            assert len(suggestion.reason) > 0, f"Empty reason for style: {style}"


class TestCombine:
    """Tests for combine function."""

    def test_combine_histogram_only(self) -> None:
        """Test combine with only histogram returns histogram suggestion."""
        histogram_suggestion = combine([50, 50, 0, 0, 0, 0, 0, 0])
        assert histogram_suggestion.curve_name == "soft"

    def test_combine_histogram_and_pull_agree_hard(self) -> None:
        """Test combine when both signals agree on hard."""
        # Histogram says hard (top buckets), pull says slammy (→ hard)
        suggestion = combine([0, 0, 0, 0, 0, 0, 50, 50], pull_style="slammy")
        assert suggestion.curve_name == "hard"
        assert suggestion.confidence > 0.75  # Boosted by agreement
        assert "both suggest" in suggestion.reason.lower()

    def test_combine_histogram_and_pull_agree_soft(self) -> None:
        """Test combine when both signals agree on soft."""
        suggestion = combine([50, 50, 0, 0, 0, 0, 0, 0], pull_style="feathery")
        assert suggestion.curve_name == "soft"
        assert suggestion.confidence > 0.75
        assert "both suggest" in suggestion.reason.lower()

    def test_combine_histogram_and_pull_disagree(self) -> None:
        """Test combine when signals disagree."""
        # Histogram says hard, pull says feathery (→ soft)
        suggestion = combine([0, 0, 0, 0, 0, 0, 50, 50], pull_style="feathery")
        assert suggestion.curve_name == "hard"  # Weights histogram
        assert suggestion.confidence < 1.0  # High confidence on hard signal reduced by disagreement
        assert suggestion.confidence > 0.7  # But still meaningful (histogram is strong)
        assert "suggests" in suggestion.reason.lower()

    def test_combine_confidence_clamped(self) -> None:
        """Test that combined confidence is clamped to 0..1."""
        suggestion = combine([10, 10, 10, 10, 10, 10, 10, 10], pull_style="slammy")
        assert 0.0 <= suggestion.confidence <= 1.0

    def test_combine_reason_non_empty(self) -> None:
        """Test that combine always provides a reason."""
        test_cases = [
            ([], None),
            ([50, 50, 0, 0, 0, 0, 0, 0], None),
            ([50, 50, 0, 0, 0, 0, 0, 0], "slammy"),
            ([0, 0, 0, 0, 0, 0, 50, 50], "feathery"),
        ]
        for histogram, pull_style in test_cases:
            suggestion = combine(histogram, pull_style)
            assert len(suggestion.reason) > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_bucket_histogram(self) -> None:
        """Test histogram with single bucket."""
        suggestion = suggest_from_histogram([100])
        assert suggestion.curve_name == "fixed"
        assert suggestion.confidence > 0.5

    def test_very_small_bucket_counts(self) -> None:
        """Test histogram with very small counts."""
        suggestion = suggest_from_histogram([1, 1, 1, 1, 1, 1, 1, 1])
        assert suggestion.curve_name == "linear"

    def test_wildly_imbalanced_histogram(self) -> None:
        """Test very imbalanced histogram."""
        suggestion = suggest_from_histogram([1000, 0, 0, 0, 0, 0, 0, 0])
        assert suggestion.curve_name == "fixed"
        assert suggestion.confidence > 0.9

    def test_suggestion_immutability_after_creation(self) -> None:
        """Test that suggestion properties don't mutate unexpectedly."""
        suggestion = suggest_from_histogram([50, 50, 0, 0, 0, 0, 0, 0])
        curve_before = suggestion.curve_name
        confidence_before = suggestion.confidence
        reason_before = suggestion.reason

        # Attempt to modify (should not affect returned object)
        _ = suggest_from_histogram([0, 0, 0, 0, 0, 0, 50, 50])

        assert suggestion.curve_name == curve_before
        assert suggestion.confidence == confidence_before
        assert suggestion.reason == reason_before

    def test_all_valid_curve_names(self) -> None:
        """Test that suggestions always return valid curve names."""
        from gamepad_midi_bridge.velocity_curve import VELOCITY_CURVE_MODES

        test_cases = [
            ([], None),
            ([50, 50, 0, 0, 0, 0, 0, 0], None),
            ([0, 0, 0, 0, 0, 0, 50, 50], None),
            ([10, 10, 10, 10, 10, 10, 10, 10], "slammy"),
        ]
        for histogram, pull_style in test_cases:
            suggestion = combine(histogram, pull_style)
            assert suggestion.curve_name in VELOCITY_CURVE_MODES
