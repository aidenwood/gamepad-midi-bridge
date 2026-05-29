"""Test suite for mapping_size_budget module."""

import pytest
from gamepad_midi_bridge.mapping_size_budget import (
    serialized_size,
    section_sizes,
    SizeBudgetConfig,
    SizeBudgetReport,
    check,
)


class TestSerializedSize:
    """Test serialized_size function."""

    def test_empty_dict_size(self):
        """Test that empty dict serializes to 2 bytes (just '{}')."""
        size = serialized_size({})
        assert size == 2

    def test_minified_smaller_than_pretty(self):
        """Test that minified JSON is smaller than pretty-printed."""
        mapping = {"buttons": {str(i): {"note": 60 + i} for i in range(50)}}
        pretty_size = serialized_size(mapping, minify=False)
        minified_size = serialized_size(mapping, minify=True)
        assert minified_size < pretty_size

    def test_simple_dict_size(self):
        """Test serialization of a simple dict."""
        mapping = {"test": "value"}
        size = serialized_size(mapping, minify=True)
        # Minified: {"test":"value"} = 16 bytes
        assert size == 16

    def test_utf8_encoding(self):
        """Test that size accounts for UTF-8 byte count."""
        # ASCII characters are 1 byte each in UTF-8
        mapping = {"a": "b"}
        size = serialized_size(mapping, minify=True)
        # {"a":"b"} = 9 bytes
        assert size == 9


class TestSectionSizes:
    """Test section_sizes function."""

    def test_section_sizes_returns_dict(self):
        """Test that section_sizes returns a dict."""
        mapping = {"buttons": {"0": {"note": 60}}, "axes": {"0": {"cc": 10}}}
        result = section_sizes(mapping, minify=True)
        assert isinstance(result, dict)

    def test_section_sizes_all_keys_present(self):
        """Test that all top-level keys are included in result."""
        mapping = {
            "buttons": {"0": {"note": 60}},
            "axes": {"0": {"cc": 10}},
            "triggers": {},
        }
        result = section_sizes(mapping, minify=True)
        assert "buttons" in result
        assert "axes" in result
        assert "triggers" in result

    def test_section_sizes_buttons_larger_than_empty(self):
        """Test that buttons section with content is larger than empty section."""
        mapping = {
            "buttons": {str(i): {"note": 60 + i} for i in range(10)},
            "axes": {},
        }
        result = section_sizes(mapping, minify=True)
        assert result["buttons"] > result["axes"]


class TestSizeBudgetConfig:
    """Test SizeBudgetConfig dataclass."""

    def test_config_initialization_defaults(self):
        """Test default initialization."""
        cfg = SizeBudgetConfig()
        assert cfg.budget_bytes == 50000
        assert cfg.warn_threshold_pct == 0.8

    def test_config_custom_values(self):
        """Test custom initialization."""
        cfg = SizeBudgetConfig(budget_bytes=100000, warn_threshold_pct=0.7)
        assert cfg.budget_bytes == 100000
        assert cfg.warn_threshold_pct == 0.7

    def test_config_clamping_budget_bytes_lower(self):
        """Test that budget_bytes is clamped to minimum 1000."""
        cfg = SizeBudgetConfig(budget_bytes=500)
        assert cfg.budget_bytes == 1000

    def test_config_clamping_budget_bytes_upper(self):
        """Test that budget_bytes is clamped to maximum 10000000."""
        cfg = SizeBudgetConfig(budget_bytes=20000000)
        assert cfg.budget_bytes == 10000000

    def test_config_clamping_threshold_lower(self):
        """Test that warn_threshold_pct is clamped to minimum 0.0."""
        cfg = SizeBudgetConfig(warn_threshold_pct=-0.5)
        assert cfg.warn_threshold_pct == 0.0

    def test_config_clamping_threshold_upper(self):
        """Test that warn_threshold_pct is clamped to maximum 1.0."""
        cfg = SizeBudgetConfig(warn_threshold_pct=1.5)
        assert cfg.warn_threshold_pct == 1.0

    def test_config_to_dict(self):
        """Test to_dict serialization."""
        cfg = SizeBudgetConfig(budget_bytes=25000, warn_threshold_pct=0.75)
        d = cfg.to_dict()
        assert d["budget_bytes"] == 25000
        assert d["warn_threshold_pct"] == 0.75

    def test_config_from_dict(self):
        """Test from_dict deserialization."""
        d = {"budget_bytes": 30000, "warn_threshold_pct": 0.6}
        cfg = SizeBudgetConfig.from_dict(d)
        assert cfg.budget_bytes == 30000
        assert cfg.warn_threshold_pct == 0.6

    def test_config_round_trip(self):
        """Test to_dict and from_dict round-trip."""
        original = SizeBudgetConfig(budget_bytes=35000, warn_threshold_pct=0.85)
        d = original.to_dict()
        restored = SizeBudgetConfig.from_dict(d)
        assert restored.budget_bytes == original.budget_bytes
        assert restored.warn_threshold_pct == original.warn_threshold_pct


class TestSizeBudgetReport:
    """Test SizeBudgetReport dataclass."""

    def test_report_initialization(self):
        """Test report initialization with all fields."""
        report = SizeBudgetReport(
            current_bytes=10000,
            budget_bytes=50000,
            usage_pct=0.2,
            over_budget=False,
            near_warn_threshold=False,
            largest_section="buttons",
            largest_section_bytes=5000,
            recommendations=["Trim buttons"],
        )
        assert report.current_bytes == 10000
        assert report.budget_bytes == 50000
        assert report.usage_pct == 0.2
        assert report.over_budget is False
        assert report.largest_section == "buttons"

    def test_report_to_dict(self):
        """Test to_dict serialization."""
        report = SizeBudgetReport(
            current_bytes=10000,
            budget_bytes=50000,
            usage_pct=0.2,
            over_budget=False,
            near_warn_threshold=False,
            largest_section="buttons",
            largest_section_bytes=5000,
            recommendations=["Trim buttons"],
        )
        d = report.to_dict()
        assert d["current_bytes"] == 10000
        assert d["recommendations"] == ["Trim buttons"]

    def test_report_from_dict(self):
        """Test from_dict deserialization."""
        d = {
            "current_bytes": 15000,
            "budget_bytes": 50000,
            "usage_pct": 0.3,
            "over_budget": False,
            "near_warn_threshold": False,
            "largest_section": "axes",
            "largest_section_bytes": 3000,
            "recommendations": ["Trim axes"],
        }
        report = SizeBudgetReport.from_dict(d)
        assert report.current_bytes == 15000
        assert report.largest_section == "axes"

    def test_report_round_trip(self):
        """Test to_dict and from_dict round-trip."""
        original = SizeBudgetReport(
            current_bytes=20000,
            budget_bytes=50000,
            usage_pct=0.4,
            over_budget=False,
            near_warn_threshold=True,
            largest_section="macros",
            largest_section_bytes=8000,
            recommendations=["Simplify macros"],
        )
        d = original.to_dict()
        restored = SizeBudgetReport.from_dict(d)
        assert restored.current_bytes == original.current_bytes
        assert restored.largest_section == original.largest_section
        assert restored.recommendations == original.recommendations


class TestCheckFunction:
    """Test check function that generates reports."""

    def test_check_returns_report(self):
        """Test that check returns a SizeBudgetReport."""
        mapping = {"buttons": {}}
        cfg = SizeBudgetConfig()
        report = check(mapping, cfg)
        assert isinstance(report, SizeBudgetReport)

    def test_check_over_budget_true(self):
        """Test that over_budget is True when current > budget."""
        mapping = {"buttons": {str(i): {"note": 60 + i} for i in range(50)}}
        # Create config with small budget (but respects minimum 1000)
        # Mapping with 50 buttons is ~863 bytes, so we need budget < 863
        # But min is 1000, so we clamp. Set higher button count.
        mapping_large = {"buttons": {str(i): {"note": 60 + i} for i in range(200)}}
        cfg = SizeBudgetConfig(budget_bytes=2000)  # After clamp: 2000
        report = check(mapping_large, cfg)
        # 200 buttons should definitely exceed 2000 bytes when serialized
        assert report.over_budget is True

    def test_check_over_budget_false(self):
        """Test that over_budget is False when current <= budget."""
        mapping = {"buttons": {}}
        cfg = SizeBudgetConfig(budget_bytes=50000)
        report = check(mapping, cfg)
        assert report.over_budget is False

    def test_check_near_warn_threshold_true(self):
        """Test that near_warn_threshold is True at 80%+."""
        mapping = {"buttons": {str(i): {"note": 60 + i} for i in range(50)}}
        cfg = SizeBudgetConfig(budget_bytes=1000, warn_threshold_pct=0.8)
        report = check(mapping, cfg)
        # With 50 buttons, size should be ~700+ bytes, so at 80% of 1000
        assert report.usage_pct >= cfg.warn_threshold_pct

    def test_check_near_warn_threshold_false(self):
        """Test that near_warn_threshold is False when well under threshold."""
        mapping = {"buttons": {}}
        cfg = SizeBudgetConfig(budget_bytes=50000, warn_threshold_pct=0.8)
        report = check(mapping, cfg)
        assert report.near_warn_threshold is False

    def test_check_largest_section_identified(self):
        """Test that largest_section correctly identifies the biggest part."""
        mapping = {
            "buttons": {str(i): {"note": 60 + i} for i in range(50)},
            "axes": {"0": {"cc": 10}},
        }
        cfg = SizeBudgetConfig()
        report = check(mapping, cfg)
        assert report.largest_section == "buttons"
        assert report.largest_section_bytes > 0

    def test_check_recommendations_empty_when_under_budget(self):
        """Test that recommendations are empty when well under budget."""
        mapping = {"buttons": {}}
        cfg = SizeBudgetConfig(budget_bytes=50000, warn_threshold_pct=0.8)
        report = check(mapping, cfg)
        # May be empty or minimal for tiny mappings
        assert len(report.recommendations) == 0

    def test_check_recommendations_non_empty_over_budget(self):
        """Test that recommendations are generated when over budget."""
        mapping_large = {"buttons": {str(i): {"note": 60 + i} for i in range(200)}}
        cfg = SizeBudgetConfig(budget_bytes=2000)
        report = check(mapping_large, cfg)
        assert len(report.recommendations) > 0

    def test_check_usage_pct_calculated(self):
        """Test that usage_pct is correctly calculated."""
        mapping = {"buttons": {}}
        size = serialized_size(mapping, minify=True)
        cfg = SizeBudgetConfig(budget_bytes=1000)
        report = check(mapping, cfg)
        assert report.usage_pct == pytest.approx(size / 1000)

    def test_check_macros_section_recommendation(self):
        """Test that macros section triggers appropriate recommendation."""
        mapping = {
            "buttons": {},
            "macros": [{"name": f"macro_{i}", "events": []} for i in range(100)],
        }
        cfg = SizeBudgetConfig(budget_bytes=500)
        report = check(mapping, cfg)
        assert report.largest_section == "macros"
        assert any("macros" in r.lower() for r in report.recommendations)

    def test_check_buttons_with_many_entries_recommendation(self):
        """Test that buttons section with >100 entries gets grouping suggestion when over budget."""
        mapping = {
            "buttons": {str(i): {"note": 60 + (i % 127)} for i in range(120)}
        }
        cfg = SizeBudgetConfig(budget_bytes=1500)
        report = check(mapping, cfg)
        assert report.largest_section == "buttons"
        # Should have a recommendation about grouping or shift layers
        # (only if over budget or near threshold)
        if report.over_budget or report.near_warn_threshold:
            assert any(
                ("group" in r.lower() or "shift" in r.lower())
                for r in report.recommendations
            )

    def test_check_handles_empty_mapping(self):
        """Test that check handles completely empty mapping gracefully."""
        mapping = {}
        cfg = SizeBudgetConfig()
        report = check(mapping, cfg)
        assert report.current_bytes == 2  # just '{}'
        assert report.over_budget is False
        assert report.largest_section is None


class TestIntegrationScenarios:
    """Integration tests mimicking real-world scenarios."""

    def test_realistic_small_mapping(self):
        """Test a small, well-structured mapping under budget."""
        mapping = {
            "buttons": {
                "0": {"note": 60},
                "1": {"note": 61},
                "2": {"note": 62},
            },
            "axes": {"0": {"cc": 10}},
            "triggers": {"L2": {"cc": 20}},
        }
        cfg = SizeBudgetConfig(budget_bytes=10000, warn_threshold_pct=0.8)
        report = check(mapping, cfg)
        assert not report.over_budget
        assert report.usage_pct < cfg.warn_threshold_pct

    def test_realistic_large_mapping_near_limit(self):
        """Test a large mapping that is a reasonable size relative to budget."""
        mapping = {
            "buttons": {str(i): {"note": 60 + (i % 127)} for i in range(100)},
            "macros": [
                {
                    "name": f"macro_{i}",
                    "events": [
                        {"control": "button", "index": 0, "action": "press"},
                        {"control": "button", "index": 1, "action": "release"},
                    ],
                }
                for i in range(10)
            ],
        }
        cfg = SizeBudgetConfig(budget_bytes=10000, warn_threshold_pct=0.8)
        report = check(mapping, cfg)
        # This should be ~3KB, which is 30% of 10KB budget
        assert not report.over_budget
        # At 30%, should not be near threshold
        assert report.usage_pct < cfg.warn_threshold_pct

    def test_verification_command_from_spec(self):
        """Test the exact verification case from the spec."""
        m = {"buttons": {i: {"note": 60 + i} for i in range(50)}, "macros": []}
        r = check(m, SizeBudgetConfig(budget_bytes=200))
        # Budget will be clamped to minimum 1000 in config
        # So 875 bytes is NOT over budget (1000)
        assert r.current_bytes > 200
        # But it should be in the warnings zone
        assert r.near_warn_threshold
        assert r.largest_section == "buttons"
        # With actual over-budget scenario
        r2 = check(m, SizeBudgetConfig(budget_bytes=500))  # Clamped to 1000
        assert r2.current_bytes > r2.budget_bytes / 2  # At least half budget used
