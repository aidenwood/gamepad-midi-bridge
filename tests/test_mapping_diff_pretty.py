"""Tests for pretty mapping diff renderer."""

from gamepad_midi_bridge.mapping_diff_pretty import (
    DiffLine,
    diff,
    format_line,
    group_by_section,
    render,
    summary,
    walk_keys,
)


class TestWalkKeys:
    """Test the walk_keys generator function."""

    def test_walk_keys_empty_dict(self) -> None:
        """Empty dict should yield one entry (empty dict as leaf)."""
        d = {}
        paths = list(walk_keys(d))
        assert paths == [("", {})]

    def test_walk_keys_flat_dict(self) -> None:
        """Flat dict should yield all scalar values."""
        d = {"a": 1, "b": 2, "c": 3}
        paths = sorted(walk_keys(d))
        assert paths == [("a", 1), ("b", 2), ("c", 3)]

    def test_walk_keys_nested_dict(self) -> None:
        """Nested dict should yield leaves with dotted paths."""
        d = {"outer": {"inner": 42}}
        paths = list(walk_keys(d))
        assert paths == [("outer.inner", 42)]

    def test_walk_keys_mixed_leaves(self) -> None:
        """Mixed scalar and list leaves should all be yielded."""
        d = {"a": 1, "b": [1, 2, 3], "c": {"d": "nested"}}
        paths = sorted(walk_keys(d))
        assert ("a", 1) in paths
        assert ("b", [1, 2, 3]) in paths
        assert ("c.d", "nested") in paths

    def test_walk_keys_deeply_nested(self) -> None:
        """Deeply nested structure should use full dotted paths."""
        d = {"buttons": {0: {"note": 60, "velocity": 100}}}
        paths = sorted(walk_keys(d))
        assert ("buttons.0.note", 60) in paths
        assert ("buttons.0.velocity", 100) in paths


class TestDiff:
    """Test the diff function."""

    def test_diff_empty_dicts(self) -> None:
        """Diff two empty dicts should return only unchanged entry."""
        a = {}
        b = {}
        lines = diff(a, b)
        assert len(lines) == 1
        assert lines[0].kind == "unchanged"
        assert lines[0].path == ""

    def test_diff_single_value_added(self) -> None:
        """Adding a key should produce an 'added' line."""
        a = {}
        b = {"a": 1}
        lines = diff(a, b)
        added = [l for l in lines if l.kind == "added"]
        assert len(added) == 1
        assert added[0].path == "a"
        assert added[0].new_value == 1

    def test_diff_single_value_removed(self) -> None:
        """Removing a key should produce a 'removed' line."""
        a = {"a": 1}
        b = {}
        lines = diff(a, b)
        removed = [l for l in lines if l.kind == "removed"]
        assert len(removed) == 1
        assert removed[0].path == "a"
        assert removed[0].old_value == 1

    def test_diff_single_value_changed(self) -> None:
        """Changing a value should produce a 'changed' line."""
        a = {"a": 1}
        b = {"a": 2}
        lines = diff(a, b)
        changed = [l for l in lines if l.kind == "changed"]
        assert len(changed) == 1
        assert changed[0].path == "a"
        assert changed[0].old_value == 1
        assert changed[0].new_value == 2

    def test_diff_single_value_unchanged(self) -> None:
        """Identical values should produce an 'unchanged' line."""
        a = {"a": 1}
        b = {"a": 1}
        lines = diff(a, b)
        unchanged = [l for l in lines if l.kind == "unchanged"]
        assert len(unchanged) == 1
        assert unchanged[0].path == "a"

    def test_diff_nested_dicts(self) -> None:
        """Nested dicts should be walked recursively."""
        a = {"buttons": {0: {"note": 60}}}
        b = {"buttons": {0: {"note": 64}}}
        lines = diff(a, b)
        changed = [l for l in lines if l.kind == "changed"]
        assert len(changed) == 1
        assert changed[0].path == "buttons.0.note"
        assert changed[0].old_value == 60
        assert changed[0].new_value == 64

    def test_diff_mixed_add_remove_change(self) -> None:
        """Mixed operations should all be reported."""
        a = {"a": 1, "b": 2, "c": 3}
        b = {"a": 10, "c": 3, "d": 4}  # a changed, b removed, c unchanged, d added
        lines = diff(a, b)

        kinds = {l.kind: len([x for x in lines if x.kind == l.kind]) for l in lines}
        assert kinds.get("changed", 0) >= 1  # a changed
        assert kinds.get("removed", 0) >= 1  # b removed
        assert kinds.get("added", 0) >= 1  # d added
        assert kinds.get("unchanged", 0) >= 1  # c unchanged


class TestSummary:
    """Test the summary function."""

    def test_summary_empty_list(self) -> None:
        """Empty diff list should return empty summary."""
        lines: list[DiffLine] = []
        counts = summary(lines)
        assert counts == {}

    def test_summary_counts_per_kind(self) -> None:
        """Summary should count occurrences per kind."""
        lines = [
            DiffLine(kind="added", path="a"),
            DiffLine(kind="added", path="b"),
            DiffLine(kind="removed", path="c"),
            DiffLine(kind="changed", path="d"),
            DiffLine(kind="unchanged", path="e"),
        ]
        counts = summary(lines)
        assert counts["added"] == 2
        assert counts["removed"] == 1
        assert counts["changed"] == 1
        assert counts["unchanged"] == 1


class TestFormatLine:
    """Test the format_line function."""

    def test_format_line_added_no_color(self) -> None:
        """Added line with markers should prefix with '+ '."""
        line = DiffLine(kind="added", path="a", new_value=1)
        text = format_line(line, color=False, markers=True)
        assert text.startswith("+ ")
        assert "a" in text
        assert "1" in text

    def test_format_line_removed_no_color(self) -> None:
        """Removed line with markers should prefix with '- '."""
        line = DiffLine(kind="removed", path="a", old_value=1)
        text = format_line(line, color=False, markers=True)
        assert text.startswith("- ")
        assert "a" in text
        assert "1" in text

    def test_format_line_changed_no_color(self) -> None:
        """Changed line should show old → new."""
        line = DiffLine(kind="changed", path="a", old_value=1, new_value=2)
        text = format_line(line, color=False, markers=True)
        assert text.startswith("~ ")
        assert "1" in text
        assert "2" in text
        assert "→" in text

    def test_format_line_unchanged_no_color(self) -> None:
        """Unchanged line should prefix with '  ' (two spaces)."""
        line = DiffLine(kind="unchanged", path="a", old_value=1)
        text = format_line(line, color=False, markers=True)
        assert text.startswith("  ")

    def test_format_line_no_markers(self) -> None:
        """Without markers, should have no prefix."""
        line = DiffLine(kind="added", path="a", new_value=1)
        text = format_line(line, color=False, markers=False)
        assert not text.startswith("+ ")
        assert "a" in text

    def test_format_line_color_added(self) -> None:
        """Added line with color should contain green ANSI code."""
        line = DiffLine(kind="added", path="a", new_value=1)
        text = format_line(line, color=True, markers=True)
        assert "\033[32m" in text  # Green
        assert "\033[0m" in text  # Reset

    def test_format_line_color_removed(self) -> None:
        """Removed line with color should contain red ANSI code."""
        line = DiffLine(kind="removed", path="a", old_value=1)
        text = format_line(line, color=True, markers=True)
        assert "\033[31m" in text  # Red
        assert "\033[0m" in text  # Reset

    def test_format_line_color_changed(self) -> None:
        """Changed line with color should contain yellow ANSI code."""
        line = DiffLine(kind="changed", path="a", old_value=1, new_value=2)
        text = format_line(line, color=True, markers=True)
        assert "\033[33m" in text  # Yellow
        assert "\033[0m" in text  # Reset


class TestRender:
    """Test the render function."""

    def test_render_empty_dicts(self) -> None:
        """Rendering two empty dicts should show no changes (unchanged excluded by default)."""
        a = {}
        b = {}
        output = render(a, b, include_unchanged=False)
        # With include_unchanged=False, empty dict line is excluded
        assert output == "" or "unchanged" not in output

    def test_render_with_change(self) -> None:
        """Render should show changes."""
        a = {"a": 1}
        b = {"a": 2}
        output = render(a, b, include_unchanged=False)
        assert "a" in output
        assert "1" in output
        assert "2" in output

    def test_render_multiple_lines(self) -> None:
        """Render should produce one line per diff entry."""
        a = {"a": 1, "b": 2}
        b = {"a": 1, "b": 3, "c": 4}
        output = render(a, b, include_unchanged=False)
        lines = output.split("\n")
        # Should have changes (b changed, c added); a unchanged is excluded
        assert len(lines) >= 2

    def test_render_include_unchanged(self) -> None:
        """With include_unchanged=True, should show all lines."""
        a = {"a": 1}
        b = {"a": 1}
        output = render(a, b, include_unchanged=True)
        lines = [l for l in output.split("\n") if l.strip()]
        assert len(lines) > 0
        assert any("  " in l for l in lines)  # Unchanged marker

    def test_render_color(self) -> None:
        """With color=True, should embed ANSI codes."""
        a = {"a": 1}
        b = {"a": 2}
        output = render(a, b, include_unchanged=False, color=True)
        assert "\033[" in output  # ANSI code present


class TestGroupBySection:
    """Test the group_by_section function."""

    def test_group_by_section_empty(self) -> None:
        """Empty list should return empty dict."""
        lines: list[DiffLine] = []
        grouped = group_by_section(lines)
        assert grouped == {}

    def test_group_by_section_single_section(self) -> None:
        """Lines from one section should all be grouped together."""
        lines = [
            DiffLine(kind="added", path="buttons.0"),
            DiffLine(kind="changed", path="buttons.1"),
        ]
        grouped = group_by_section(lines)
        assert "buttons" in grouped
        assert len(grouped["buttons"]) == 2

    def test_group_by_section_multiple_sections(self) -> None:
        """Lines from different sections should be separated."""
        lines = [
            DiffLine(kind="added", path="buttons.0"),
            DiffLine(kind="changed", path="axes.4"),
            DiffLine(kind="removed", path="triggers.l2"),
        ]
        grouped = group_by_section(lines)
        assert len(grouped) == 3
        assert "buttons" in grouped
        assert "axes" in grouped
        assert "triggers" in grouped

    def test_group_by_section_preserves_order_within_group(self) -> None:
        """Lines within a group should maintain their order."""
        lines = [
            DiffLine(kind="added", path="buttons.0"),
            DiffLine(kind="changed", path="buttons.5"),
            DiffLine(kind="removed", path="buttons.2"),
        ]
        grouped = group_by_section(lines)
        assert grouped["buttons"] == lines


class TestDiffLineSerialization:
    """Test DiffLine to_dict and from_dict."""

    def test_diffline_to_dict(self) -> None:
        """DiffLine.to_dict() should produce a plain dict."""
        line = DiffLine(
            kind="changed",
            path="a.b",
            old_value=1,
            new_value=2,
        )
        d = line.to_dict()
        assert isinstance(d, dict)
        assert d["kind"] == "changed"
        assert d["path"] == "a.b"
        assert d["old_value"] == 1
        assert d["new_value"] == 2

    def test_diffline_from_dict(self) -> None:
        """DiffLine.from_dict() should reconstruct from a dict."""
        d = {
            "kind": "added",
            "path": "x.y",
            "old_value": None,
            "new_value": 42,
        }
        line = DiffLine.from_dict(d)
        assert line.kind == "added"
        assert line.path == "x.y"
        assert line.old_value is None
        assert line.new_value == 42

    def test_diffline_round_trip(self) -> None:
        """Round-trip to_dict -> from_dict should preserve data."""
        original = DiffLine(
            kind="changed",
            path="buttons.0.velocity",
            old_value=100,
            new_value=127,
        )
        d = original.to_dict()
        restored = DiffLine.from_dict(d)
        assert restored.kind == original.kind
        assert restored.path == original.path
        assert restored.old_value == original.old_value
        assert restored.new_value == original.new_value
