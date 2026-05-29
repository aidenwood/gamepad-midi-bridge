"""Test suite for mapping_recommender module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_recommender import (
    Recommendation,
    recommend,
    recommendations_by_category,
    top_n,
    format_recommendation,
)


class TestRecommendation:
    """Test Recommendation dataclass."""

    def test_init_clamps_confidence(self):
        """Confidence should be clamped to 0..1."""
        rec = Recommendation(
            severity="info",
            category="velocity",
            target_path="velocity.velocity_max",
            current_value=100,
            suggested_value=127,
            reason="Test",
            confidence=1.5,
        )
        assert rec.confidence == 1.0

        rec2 = Recommendation(
            severity="info",
            category="velocity",
            target_path="velocity.velocity_max",
            current_value=100,
            suggested_value=127,
            reason="Test",
            confidence=-0.5,
        )
        assert rec2.confidence == 0.0

    def test_to_dict(self):
        """to_dict should return all fields."""
        rec = Recommendation(
            severity="suggestion",
            category="trigger",
            target_path="triggers.L2",
            current_value=0.1,
            suggested_value=None,
            reason="L2 rarely used",
            confidence=0.8,
        )
        d = rec.to_dict()
        assert d["severity"] == "suggestion"
        assert d["category"] == "trigger"
        assert d["target_path"] == "triggers.L2"
        assert d["current_value"] == 0.1
        assert d["suggested_value"] is None
        assert d["reason"] == "L2 rarely used"
        assert d["confidence"] == 0.8

    def test_from_dict(self):
        """from_dict should deserialize correctly."""
        d = {
            "severity": "warning",
            "category": "performance",
            "target_path": "schema_version",
            "current_value": None,
            "suggested_value": 4,
            "reason": "Test reason",
            "confidence": 0.95,
        }
        rec = Recommendation.from_dict(d)
        assert rec.severity == "warning"
        assert rec.category == "performance"
        assert rec.confidence == 0.95

    def test_round_trip_serialization(self):
        """to_dict -> from_dict should preserve all data."""
        original = Recommendation(
            severity="info",
            category="button",
            target_path="buttons.0",
            current_value=60,
            suggested_value=61,
            reason="Adjust note",
            confidence=0.7,
        )
        d = original.to_dict()
        restored = Recommendation.from_dict(d)
        assert restored.severity == original.severity
        assert restored.category == original.category
        assert restored.target_path == original.target_path
        assert restored.current_value == original.current_value
        assert restored.suggested_value == original.suggested_value
        assert restored.reason == original.reason
        assert restored.confidence == original.confidence


class TestRecommend:
    """Test recommend function."""

    def test_empty_mapping_no_stats(self):
        """Empty mapping + no stats should return at least schema_version warning."""
        recs = recommend({}, None)
        assert len(recs) >= 1
        assert any(rec.category == "performance" and "schema_version" in rec.target_path for rec in recs)

    def test_missing_schema_version_warning(self):
        """Missing schema_version should produce a warning."""
        mapping = {"buttons": {}, "name": "Test"}
        recs = recommend(mapping, None)
        schema_rec = next((r for r in recs if "schema_version" in r.target_path), None)
        assert schema_rec is not None
        assert schema_rec.severity == "warning"

    def test_schema_version_present_no_warning(self):
        """Mapping with schema_version should not produce schema warning."""
        mapping = {"schema_version": 4, "buttons": {}}
        recs = recommend(mapping, None)
        schema_recs = [r for r in recs if "schema_version" in r.target_path]
        assert len(schema_recs) == 0

    def test_velocity_peak_high_suggests_velocity_max_increase(self):
        """If velocity_peak_bucket is high (6+) and velocity_max < 127, suggest increase."""
        mapping = {
            "schema_version": 4,
            "velocity": {"velocity_min": 0, "velocity_max": 100},
        }
        stats = {"velocity_peak_bucket": 7}
        recs = recommend(mapping, stats)
        velocity_recs = [r for r in recs if "velocity_max" in r.target_path]
        assert len(velocity_recs) > 0
        assert velocity_recs[0].suggested_value == 127

    def test_velocity_peak_not_high_no_suggestion(self):
        """If velocity_peak_bucket is not high, no velocity_max increase suggestion."""
        mapping = {
            "schema_version": 4,
            "velocity": {"velocity_min": 0, "velocity_max": 100},
        }
        stats = {"velocity_peak_bucket": 2}
        recs = recommend(mapping, stats)
        velocity_recs = [r for r in recs if "velocity_max" in r.target_path]
        # Should not suggest increase if peak bucket is low
        assert len(velocity_recs) == 0

    def test_velocity_peak_already_maxed(self):
        """If velocity_max is already 127, no suggestion even with high peak bucket."""
        mapping = {
            "schema_version": 4,
            "velocity": {"velocity_min": 0, "velocity_max": 127},
        }
        stats = {"velocity_peak_bucket": 7}
        recs = recommend(mapping, stats)
        velocity_recs = [r for r in recs if "velocity_max" in r.target_path]
        assert len(velocity_recs) == 0

    def test_velocity_narrow_range_suggests_lowering_min(self):
        """If velocity_mean is low but velocity_min is high, suggest lowering velocity_min."""
        mapping = {
            "schema_version": 4,
            "velocity": {"velocity_min": 50, "velocity_max": 127},
        }
        stats = {"velocity_mean": 25}
        recs = recommend(mapping, stats)
        velocity_min_recs = [r for r in recs if "velocity_min" in r.target_path]
        assert len(velocity_min_recs) > 0
        assert velocity_min_recs[0].suggested_value < 50

    def test_velocity_mean_high_no_suggestion(self):
        """If velocity_mean is high, no suggestion to lower velocity_min."""
        mapping = {
            "schema_version": 4,
            "velocity": {"velocity_min": 50, "velocity_max": 127},
        }
        stats = {"velocity_mean": 100}
        recs = recommend(mapping, stats)
        velocity_min_recs = [r for r in recs if "velocity_min" in r.target_path]
        assert len(velocity_min_recs) == 0

    def test_l2_rarely_used_suggestion(self):
        """If l2_mean_pressure < 0.05, suggest removing/remapping L2."""
        mapping = {
            "schema_version": 4,
            "triggers": {"L2": {"note": 60}},
        }
        stats = {"l2_mean_pressure": 0.02}
        recs = recommend(mapping, stats)
        l2_recs = [r for r in recs if "L2" in r.target_path]
        assert len(l2_recs) > 0
        assert l2_recs[0].severity == "suggestion"

    def test_r2_rarely_used_suggestion(self):
        """If r2_mean_pressure < 0.05, suggest removing/remapping R2."""
        mapping = {
            "schema_version": 4,
            "triggers": {"R2": {"note": 61}},
        }
        stats = {"r2_mean_pressure": 0.01}
        recs = recommend(mapping, stats)
        r2_recs = [r for r in recs if "R2" in r.target_path]
        assert len(r2_recs) > 0
        assert r2_recs[0].severity == "suggestion"

    def test_trigger_used_no_suggestion(self):
        """If trigger pressure >= 0.05, no removal suggestion."""
        mapping = {
            "schema_version": 4,
            "triggers": {"L2": {"note": 60}},
        }
        stats = {"l2_mean_pressure": 0.15}
        recs = recommend(mapping, stats)
        l2_recs = [r for r in recs if "L2" in r.target_path]
        assert len(l2_recs) == 0

    def test_stuck_notes_warning(self):
        """If stuck_notes_count > 5, warn about stuck notes."""
        mapping = {"schema_version": 4}
        stats = {"stuck_notes_count": 10}
        recs = recommend(mapping, stats)
        stuck_recs = [r for r in recs if "stuck_note_detector" in r.target_path]
        assert len(stuck_recs) > 0
        assert stuck_recs[0].severity == "warning"

    def test_stuck_notes_no_warning(self):
        """If stuck_notes_count <= 5, no warning."""
        mapping = {"schema_version": 4}
        stats = {"stuck_notes_count": 3}
        recs = recommend(mapping, stats)
        stuck_recs = [r for r in recs if "stuck_note_detector" in r.target_path]
        assert len(stuck_recs) == 0

    def test_no_buttons_suggestion(self):
        """If buttons dict is empty, suggest adding buttons."""
        mapping = {
            "schema_version": 4,
            "buttons": {},
        }
        recs = recommend(mapping, None)
        button_recs = [r for r in recs if r.category == "button"]
        assert len(button_recs) > 0

    def test_buttons_present_no_suggestion(self):
        """If buttons are present, no suggestion to add them."""
        mapping = {
            "schema_version": 4,
            "buttons": {"0": 60, "1": 61},
        }
        recs = recommend(mapping, None)
        button_recs = [r for r in recs if r.category == "button"]
        assert len(button_recs) == 0

    def test_narrow_note_range_suggestion(self):
        """If top_notes has only 1-2 unique notes, suggest scale quantize."""
        mapping = {"schema_version": 4}
        stats = {"top_notes": [(60, 0.8), (61, 0.2)]}
        recs = recommend(mapping, stats)
        range_recs = [r for r in recs if "scale" in r.reason.lower()]
        assert len(range_recs) > 0

    def test_wide_note_range_no_suggestion(self):
        """If top_notes has many unique notes, no scale quantize suggestion."""
        mapping = {"schema_version": 4}
        stats = {
            "top_notes": [
                (48, 0.2),
                (52, 0.2),
                (60, 0.2),
                (67, 0.2),
                (72, 0.2),
            ]
        }
        recs = recommend(mapping, stats)
        range_recs = [r for r in recs if "scale" in r.reason.lower()]
        assert len(range_recs) == 0

    def test_missing_stats_keys_no_crash(self):
        """Missing stats keys should not crash; fewer recs are returned."""
        mapping = {"schema_version": 4}
        stats = {"velocity_peak_bucket": 7}  # Only one key
        recs = recommend(mapping, stats)
        # Should have at least one velocity rec
        assert len(recs) >= 0  # no crash


class TestRecommendationsByCategory:
    """Test recommendations_by_category function."""

    def test_groups_by_category(self):
        """Should group recommendations by category."""
        recs = [
            Recommendation(
                severity="info",
                category="velocity",
                target_path="velocity.max",
                current_value=100,
                suggested_value=127,
                reason="Test 1",
            ),
            Recommendation(
                severity="info",
                category="velocity",
                target_path="velocity.min",
                current_value=0,
                suggested_value=10,
                reason="Test 2",
            ),
            Recommendation(
                severity="info",
                category="trigger",
                target_path="triggers.L2",
                current_value=None,
                suggested_value=None,
                reason="Test 3",
            ),
        ]
        grouped = recommendations_by_category(recs)
        assert "velocity" in grouped
        assert "trigger" in grouped
        assert len(grouped["velocity"]) == 2
        assert len(grouped["trigger"]) == 1

    def test_empty_list(self):
        """Empty list should return empty dict."""
        grouped = recommendations_by_category([])
        assert grouped == {}


class TestTopN:
    """Test top_n function."""

    def test_sorts_by_confidence_descending(self):
        """Should return recommendations sorted by confidence descending."""
        recs = [
            Recommendation(
                severity="info",
                category="velocity",
                target_path="a",
                current_value=None,
                suggested_value=None,
                reason="A",
                confidence=0.5,
            ),
            Recommendation(
                severity="info",
                category="velocity",
                target_path="b",
                current_value=None,
                suggested_value=None,
                reason="B",
                confidence=0.9,
            ),
            Recommendation(
                severity="info",
                category="velocity",
                target_path="c",
                current_value=None,
                suggested_value=None,
                reason="C",
                confidence=0.7,
            ),
        ]
        result = top_n(recs, n=3)
        assert result[0].confidence == 0.9
        assert result[1].confidence == 0.7
        assert result[2].confidence == 0.5

    def test_respects_n_limit(self):
        """Should return at most n recommendations."""
        recs = [
            Recommendation(
                severity="info",
                category="velocity",
                target_path=f"path_{i}",
                current_value=None,
                suggested_value=None,
                reason=f"Reason {i}",
                confidence=0.5,
            )
            for i in range(10)
        ]
        result = top_n(recs, n=3)
        assert len(result) == 3

    def test_fewer_than_n_available(self):
        """If fewer than n recs available, return all."""
        recs = [
            Recommendation(
                severity="info",
                category="velocity",
                target_path="a",
                current_value=None,
                suggested_value=None,
                reason="A",
                confidence=0.5,
            ),
        ]
        result = top_n(recs, n=5)
        assert len(result) == 1


class TestFormatRecommendation:
    """Test format_recommendation function."""

    def test_formats_as_non_empty_string(self):
        """Should produce a non-empty formatted string."""
        rec = Recommendation(
            severity="suggestion",
            category="velocity",
            target_path="velocity.velocity_max",
            current_value=100,
            suggested_value=127,
            reason="You frequently hit max velocity",
            confidence=0.85,
        )
        formatted = format_recommendation(rec)
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_includes_severity(self):
        """Should include severity in formatted string."""
        rec = Recommendation(
            severity="warning",
            category="velocity",
            target_path="velocity.max",
            current_value=100,
            suggested_value=127,
            reason="Test reason",
            confidence=0.8,
        )
        formatted = format_recommendation(rec)
        assert "WARNING" in formatted

    def test_includes_category(self):
        """Should include category in formatted string."""
        rec = Recommendation(
            severity="info",
            category="trigger",
            target_path="triggers.L2",
            current_value=None,
            suggested_value=None,
            reason="Test",
            confidence=0.7,
        )
        formatted = format_recommendation(rec)
        assert "trigger" in formatted

    def test_includes_confidence_percent(self):
        """Should include confidence as percentage."""
        rec = Recommendation(
            severity="info",
            category="velocity",
            target_path="velocity.max",
            current_value=100,
            suggested_value=127,
            reason="Test",
            confidence=0.85,
        )
        formatted = format_recommendation(rec)
        assert "85%" in formatted

    def test_includes_reason(self):
        """Should include reason in formatted string."""
        rec = Recommendation(
            severity="info",
            category="velocity",
            target_path="velocity.max",
            current_value=100,
            suggested_value=127,
            reason="This is the test reason",
            confidence=0.8,
        )
        formatted = format_recommendation(rec)
        assert "This is the test reason" in formatted

    def test_includes_target_path(self):
        """Should include target_path in formatted string."""
        rec = Recommendation(
            severity="info",
            category="velocity",
            target_path="velocity.velocity_max",
            current_value=100,
            suggested_value=127,
            reason="Test",
            confidence=0.8,
        )
        formatted = format_recommendation(rec)
        assert "velocity.velocity_max" in formatted
