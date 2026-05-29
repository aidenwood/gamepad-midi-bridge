"""Tests for MappingTagRegistry."""

import pytest
from gamepad_midi_bridge.mapping_tags import TagsConfig, MappingTagRegistry


class TestTagsConfig:
    """Tests for TagsConfig dataclass."""

    def test_config_defaults(self):
        """Config uses sensible defaults."""
        cfg = TagsConfig()
        assert cfg.max_tags_per_preset == 20
        assert cfg.max_total_tags == 5000

    def test_config_clamp_max_tags_per_preset_low(self):
        """Config clamps max_tags_per_preset < 1 to 1."""
        cfg = TagsConfig(max_tags_per_preset=0)
        assert cfg.max_tags_per_preset == 1

    def test_config_clamp_max_tags_per_preset_high(self):
        """Config clamps max_tags_per_preset > 256 to 256."""
        cfg = TagsConfig(max_tags_per_preset=500)
        assert cfg.max_tags_per_preset == 256

    def test_config_clamp_max_total_tags_low(self):
        """Config clamps max_total_tags < 100 to 100."""
        cfg = TagsConfig(max_total_tags=50)
        assert cfg.max_total_tags == 100

    def test_config_clamp_max_total_tags_high(self):
        """Config clamps max_total_tags > 1000000 to 1000000."""
        cfg = TagsConfig(max_total_tags=2000000)
        assert cfg.max_total_tags == 1000000

    def test_config_to_dict(self):
        """Config.to_dict() serializes all fields."""
        cfg = TagsConfig(max_tags_per_preset=30, max_total_tags=10000)
        d = cfg.to_dict()
        assert d["max_tags_per_preset"] == 30
        assert d["max_total_tags"] == 10000

    def test_config_from_dict(self):
        """TagsConfig.from_dict() deserializes correctly."""
        d = {"max_tags_per_preset": 25, "max_total_tags": 3000}
        cfg = TagsConfig.from_dict(d)
        assert cfg.max_tags_per_preset == 25
        assert cfg.max_total_tags == 3000


class TestMappingTagRegistry:
    """Tests for MappingTagRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry."""
        cfg = TagsConfig()
        return MappingTagRegistry(cfg)

    def test_empty_tags_for(self, registry):
        """tags_for returns [] for unknown preset."""
        assert registry.tags_for("unknown") == []

    def test_add_tag_normalizes_lowercase(self, registry):
        """add_tag normalizes to lowercase."""
        assert registry.add_tag("lead", "SYNTH") is True
        assert registry.tags_for("lead") == ["synth"]

    def test_add_tag_strips_whitespace(self, registry):
        """add_tag strips whitespace."""
        assert registry.add_tag("lead", "  synth  ") is True
        assert registry.tags_for("lead") == ["synth"]

    def test_add_tag_rejects_empty(self, registry):
        """add_tag rejects empty/whitespace-only tags."""
        assert registry.add_tag("lead", "") is False
        assert registry.add_tag("lead", "   ") is False
        assert registry.tags_for("lead") == []

    def test_add_tag_dedupes(self, registry):
        """add_tag returns False on duplicate."""
        assert registry.add_tag("lead", "synth") is True
        assert registry.add_tag("lead", "synth") is False
        assert registry.add_tag("lead", "SYNTH") is False
        assert len(registry.tags_for("lead")) == 1

    def test_tags_for_returns_sorted(self, registry):
        """tags_for returns sorted list."""
        registry.add_tag("lead", "synth")
        registry.add_tag("lead", "bright")
        registry.add_tag("lead", "aaa")
        assert registry.tags_for("lead") == ["aaa", "bright", "synth"]

    def test_presets_with_returns_sorted(self, registry):
        """presets_with returns sorted list."""
        registry.add_tag("preset_a", "synth")
        registry.add_tag("preset_b", "synth")
        registry.add_tag("preset_c", "synth")
        assert registry.presets_with("synth") == ["preset_a", "preset_b", "preset_c"]

    def test_presets_with_case_insensitive(self, registry):
        """presets_with is case-insensitive."""
        registry.add_tag("preset_a", "synth")
        assert registry.presets_with("SYNTH") == ["preset_a"]

    def test_find_any_union(self, registry):
        """find_any returns union of presets."""
        registry.add_tag("lead", "synth")
        registry.add_tag("lead", "bright")
        registry.add_tag("pad", "synth")
        registry.add_tag("pad", "ambient")
        assert set(registry.find_any(["synth"])) == {"lead", "pad"}
        assert set(registry.find_any(["ambient"])) == {"pad"}
        assert set(registry.find_any(["synth", "bright"])) == {"lead", "pad"}

    def test_find_all_intersection(self, registry):
        """find_all returns intersection of presets."""
        registry.add_tag("lead", "synth")
        registry.add_tag("lead", "bright")
        registry.add_tag("pad", "synth")
        registry.add_tag("pad", "ambient")
        assert registry.find_all(["synth"]) == ["lead", "pad"]
        assert registry.find_all(["synth", "bright"]) == ["lead"]
        assert registry.find_all(["synth", "ambient"]) == ["pad"]
        assert registry.find_all(["synth", "ambient", "bright"]) == []

    def test_find_all_empty(self, registry):
        """find_all with empty list returns []."""
        registry.add_tag("lead", "synth")
        assert registry.find_all([]) == []

    def test_find_any_empty(self, registry):
        """find_any with empty list returns []."""
        registry.add_tag("lead", "synth")
        assert registry.find_any([]) == []

    def test_all_tags_returns_tuples_sorted_by_count(self, registry):
        """all_tags returns (tag, count) sorted by count desc."""
        registry.add_tag("lead", "synth")
        registry.add_tag("pad", "synth")
        registry.add_tag("bass", "synth")
        registry.add_tag("lead", "bright")
        registry.add_tag("pad", "ambient")
        tags_with_counts = registry.all_tags()
        assert ("synth", 3) in tags_with_counts
        assert ("bright", 1) in tags_with_counts
        assert ("ambient", 1) in tags_with_counts
        assert tags_with_counts[0][0] == "synth"  # synth has highest count

    def test_tag_count(self, registry):
        """tag_count returns unique tag count."""
        registry.add_tag("lead", "synth")
        registry.add_tag("lead", "bright")
        registry.add_tag("pad", "synth")
        assert registry.tag_count() == 2

    def test_preset_count(self, registry):
        """preset_count returns preset count."""
        registry.add_tag("lead", "synth")
        registry.add_tag("pad", "synth")
        registry.add_tag("bass", "bright")
        assert registry.preset_count() == 3

    def test_suggest_by_prefix(self, registry):
        """suggest returns tags starting with prefix."""
        registry.add_tag("p1", "synth")
        registry.add_tag("p2", "synth-bright")
        registry.add_tag("p3", "synth-ambient")
        registry.add_tag("p4", "ambient")
        suggests = registry.suggest("synth")
        assert "synth" in suggests
        assert "synth-bright" in suggests
        assert "synth-ambient" in suggests
        assert "ambient" not in suggests

    def test_suggest_case_insensitive(self, registry):
        """suggest is case-insensitive."""
        registry.add_tag("p1", "synth")
        registry.add_tag("p2", "synth-bright")
        suggests = registry.suggest("SYNTH")
        assert "synth" in suggests
        assert "synth-bright" in suggests

    def test_suggest_sorted_by_frequency(self, registry):
        """suggest sorts by frequency descending."""
        registry.add_tag("p1", "synth")
        registry.add_tag("p2", "synth")
        registry.add_tag("p3", "synth")
        registry.add_tag("p4", "synth-bright")
        registry.add_tag("p5", "synth-bright")
        registry.add_tag("p6", "synth-ambient")
        suggests = registry.suggest("synth")
        assert suggests[0] == "synth"  # 3 uses
        assert suggests[1] == "synth-bright"  # 2 uses
        assert suggests[2] == "synth-ambient"  # 1 use

    def test_suggest_with_limit(self, registry):
        """suggest respects limit parameter."""
        registry.add_tag("p1", "a")
        registry.add_tag("p2", "ab")
        registry.add_tag("p3", "abc")
        registry.add_tag("p4", "abcd")
        suggests = registry.suggest("a", limit=2)
        assert len(suggests) == 2

    def test_suggest_empty_prefix(self, registry):
        """suggest with empty prefix returns []."""
        registry.add_tag("p1", "synth")
        assert registry.suggest("") == []

    def test_remove_tag_deletes(self, registry):
        """remove_tag deletes a tag."""
        registry.add_tag("lead", "synth")
        registry.add_tag("lead", "bright")
        assert registry.remove_tag("lead", "synth") is True
        assert registry.tags_for("lead") == ["bright"]

    def test_remove_tag_cleans_empty_preset(self, registry):
        """remove_tag removes empty preset entries."""
        registry.add_tag("lead", "synth")
        assert registry.preset_count() == 1
        registry.remove_tag("lead", "synth")
        assert registry.preset_count() == 0

    def test_remove_tag_cleans_empty_tag(self, registry):
        """remove_tag removes empty tag index entries."""
        registry.add_tag("lead", "synth")
        assert registry.tag_count() == 1
        registry.remove_tag("lead", "synth")
        assert registry.tag_count() == 0

    def test_remove_tag_returns_false_unknown(self, registry):
        """remove_tag returns False for unknown preset/tag."""
        assert registry.remove_tag("unknown", "synth") is False
        registry.add_tag("lead", "synth")
        assert registry.remove_tag("lead", "unknown") is False

    def test_clear_empties(self, registry):
        """clear() empties all tags."""
        registry.add_tag("lead", "synth")
        registry.add_tag("pad", "synth")
        registry.add_tag("bass", "bright")
        registry.clear()
        assert registry.tag_count() == 0
        assert registry.preset_count() == 0

    def test_max_tags_per_preset_limit_enforced(self, registry):
        """add_tag enforces max_tags_per_preset limit."""
        cfg = TagsConfig(max_tags_per_preset=3)
        limited_registry = MappingTagRegistry(cfg)
        assert limited_registry.add_tag("lead", "a") is True
        assert limited_registry.add_tag("lead", "b") is True
        assert limited_registry.add_tag("lead", "c") is True
        assert limited_registry.add_tag("lead", "d") is False
        assert len(limited_registry.tags_for("lead")) == 3

    def test_rename_tag_updates_all_uses(self, registry):
        """rename_tag updates tag globally."""
        registry.add_tag("lead", "synth")
        registry.add_tag("pad", "synth")
        registry.add_tag("bass", "synth")
        count = registry.rename_tag("synth", "synth-pad")
        assert count == 3
        assert registry.tag_count() == 1
        assert registry.tags_for("lead") == ["synth-pad"]
        assert registry.tags_for("pad") == ["synth-pad"]
        assert registry.tags_for("bass") == ["synth-pad"]

    def test_rename_tag_rejects_invalid(self, registry):
        """rename_tag rejects invalid renames."""
        registry.add_tag("lead", "synth")
        assert registry.rename_tag("", "new") == 0
        assert registry.rename_tag("synth", "") == 0
        assert registry.rename_tag("unknown", "new") == 0

    def test_rename_tag_rejects_duplicate(self, registry):
        """rename_tag rejects rename if new tag exists."""
        registry.add_tag("lead", "synth")
        registry.add_tag("pad", "bright")
        assert registry.rename_tag("synth", "bright") == 0

    def test_rename_tag_noop_identical(self, registry):
        """rename_tag returns 0 if old == new."""
        registry.add_tag("lead", "synth")
        assert registry.rename_tag("synth", "synth") == 0

    def test_rename_tag_case_insensitive(self, registry):
        """rename_tag is case-insensitive."""
        registry.add_tag("lead", "synth")
        count = registry.rename_tag("SYNTH", "bright")
        assert count == 1
        assert registry.tags_for("lead") == ["bright"]

    def test_round_trip_serialization_config(self):
        """TagsConfig round-trips through dict."""
        cfg = TagsConfig(max_tags_per_preset=30, max_total_tags=8000)
        d = cfg.to_dict()
        cfg2 = TagsConfig.from_dict(d)
        assert cfg2.max_tags_per_preset == 30
        assert cfg2.max_total_tags == 8000


class TestMappingTagRegistryScenarios:
    """Integration tests for realistic usage scenarios."""

    def test_music_production_workflow(self):
        """Realistic music production tagging scenario."""
        cfg = TagsConfig()
        registry = MappingTagRegistry(cfg)

        # Create some presets with multiple tags
        registry.add_tag("lead", "synth")
        registry.add_tag("lead", "bright")
        registry.add_tag("lead", "melodic")

        registry.add_tag("pad", "synth")
        registry.add_tag("pad", "ambient")
        registry.add_tag("pad", "warm")

        registry.add_tag("bass", "synth")
        registry.add_tag("bass", "deep")
        registry.add_tag("bass", "warm")

        # Search for "synth" presets
        synth_presets = registry.presets_with("synth")
        assert set(synth_presets) == {"lead", "pad", "bass"}

        # Search for "warm" presets
        warm_presets = registry.presets_with("warm")
        assert set(warm_presets) == {"pad", "bass"}

        # Find presets with both synth AND warm
        both = registry.find_all(["synth", "warm"])
        assert set(both) == {"pad", "bass"}

        # Find presets with synth OR melodic
        either = registry.find_any(["synth", "melodic"])
        assert set(either) == {"lead", "pad", "bass"}

    def test_tag_suggestion_workflow(self):
        """Tag suggestion for user input."""
        cfg = TagsConfig()
        registry = MappingTagRegistry(cfg)

        # Create presets
        registry.add_tag("p1", "synth")
        registry.add_tag("p2", "synth-bright")
        registry.add_tag("p3", "synth-ambient")
        registry.add_tag("p4", "synth-dark")
        registry.add_tag("p5", "pad")

        # User types "syn" - suggest completions
        suggestions = registry.suggest("syn")
        assert "synth" in suggestions

        # User types "synth-" - suggest sub-tags
        suggestions = registry.suggest("synth-")
        assert "synth-bright" in suggestions
        assert "synth-ambient" in suggestions
        assert "synth-dark" in suggestions

    def test_tag_stats_reporting(self):
        """Generate stats about tags."""
        cfg = TagsConfig()
        registry = MappingTagRegistry(cfg)

        registry.add_tag("p1", "synth")
        registry.add_tag("p2", "synth")
        registry.add_tag("p3", "synth")
        registry.add_tag("p1", "bright")
        registry.add_tag("p2", "bright")
        registry.add_tag("p4", "ambient")

        stats = registry.all_tags()
        assert len(stats) == 3
        assert stats[0] == ("synth", 3)
        assert stats[1][0] == "bright"  # 2 uses
        assert stats[2] == ("ambient", 1)
