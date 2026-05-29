"""Tests for mapping_cloner module."""

import pytest

from gamepad_midi_bridge.mapping_cloner import (
    RESET_KEYS,
    chain,
    clone,
    clone_with_slug,
    rename,
    strip_personal_data,
    update_metadata,
)


@pytest.fixture
def sample_mapping() -> dict:
    """A minimal mapping dict for testing."""
    return {
        "name": "Original",
        "description": "A test mapping",
        "slug": "original-slug",
        "marketplace_id": "mp-123456",
        "downloaded_at": "2025-05-30T10:30:00Z",
        "shared_by": "user@example.com",
        "last_modified": "2025-05-30T11:00:00Z",
        "checksum": "abc123def456",
        "buttons": {0: 60, 1: 62},
        "axes": {0: 3, 1: 4},
        "midi_channel": 0,
    }


class TestClone:
    """Tests for the clone() function."""

    def test_clone_returns_equal_dict_when_no_args(self, sample_mapping):
        """clone with no args should deep copy and reset metadata by default."""
        cloned = clone(sample_mapping)
        # With default reset_keys=True, metadata fields should be cleared
        assert cloned["name"] == sample_mapping["name"]  # name is preserved
        assert cloned["buttons"] == sample_mapping["buttons"]  # buttons preserved
        assert cloned["slug"] == ""  # but metadata cleared
        assert cloned is not sample_mapping

    def test_clone_is_non_mutating(self, sample_mapping):
        """clone() should never modify the input."""
        original_copy = sample_mapping.copy()
        clone(sample_mapping, new_name="Modified")
        assert sample_mapping == original_copy

    def test_clone_with_new_name_overwrites_name(self, sample_mapping):
        """clone with new_name should update the name field."""
        cloned = clone(sample_mapping, new_name="Copy")
        assert cloned["name"] == "Copy"
        assert sample_mapping["name"] == "Original"

    def test_clone_with_new_description_overwrites_description(self, sample_mapping):
        """clone with new_description should update the description field."""
        cloned = clone(sample_mapping, new_description="A copy")
        assert cloned["description"] == "A copy"
        assert sample_mapping["description"] == "A test mapping"

    def test_clone_deep_copies_nested_structures(self, sample_mapping):
        """clone should deeply copy nested dicts so modifications don't affect original."""
        cloned = clone(sample_mapping)
        cloned["buttons"][0] = 99
        assert sample_mapping["buttons"][0] == 60

    def test_clone_with_reset_keys_true_clears_metadata(self, sample_mapping):
        """clone with reset_keys=True should clear RESET_KEYS fields (strings to '', others to None)."""
        cloned = clone(sample_mapping, reset_keys=True)
        # All RESET_KEYS fields should be cleared/emptied
        assert cloned["slug"] == ""  # string field → ""
        assert cloned["marketplace_id"] == ""  # string-like → ""
        assert cloned["downloaded_at"] == ""  # string field → ""
        assert cloned["shared_by"] == ""  # string field → ""
        assert cloned["last_modified"] == ""  # string field → ""
        assert cloned["checksum"] == ""  # string field → ""

    def test_clone_with_reset_keys_false_preserves_metadata(self, sample_mapping):
        """clone with reset_keys=False should keep RESET_KEYS fields unchanged."""
        cloned = clone(sample_mapping, reset_keys=False)
        # All metadata should be preserved
        assert cloned["slug"] == sample_mapping["slug"]
        assert cloned["marketplace_id"] == sample_mapping["marketplace_id"]
        assert cloned["downloaded_at"] == sample_mapping["downloaded_at"]
        assert cloned["shared_by"] == sample_mapping["shared_by"]
        assert cloned["last_modified"] == sample_mapping["last_modified"]
        assert cloned["checksum"] == sample_mapping["checksum"]

    def test_clone_handles_missing_reset_keys(self):
        """clone should gracefully handle dicts missing some RESET_KEYS."""
        partial = {"name": "Test", "buttons": {}}
        cloned = clone(partial, reset_keys=True)
        assert cloned["name"] == "Test"
        assert cloned["buttons"] == {}
        # Missing keys should not cause errors
        assert "slug" not in cloned


class TestCloneWithSlug:
    """Tests for the clone_with_slug() convenience function."""

    def test_clone_with_slug_sets_slug_field(self, sample_mapping):
        """clone_with_slug should set the slug and reset other metadata."""
        cloned = clone_with_slug(sample_mapping, "new-slug")
        assert cloned["slug"] == "new-slug"
        assert cloned["marketplace_id"] == ""  # cleared

    def test_clone_with_slug_resets_other_keys(self, sample_mapping):
        """clone_with_slug should reset other RESET_KEYS."""
        cloned = clone_with_slug(sample_mapping, "my-slug")
        assert cloned["marketplace_id"] == ""  # cleared
        assert cloned["downloaded_at"] == ""  # cleared
        assert cloned["last_modified"] == ""  # cleared


class TestRename:
    """Tests for the rename() convenience function."""

    def test_rename_returns_new_dict(self, sample_mapping):
        """rename should return a new dict with updated name."""
        renamed = rename(sample_mapping, "New Name")
        assert renamed["name"] == "New Name"
        assert sample_mapping["name"] == "Original"

    def test_rename_does_not_mutate_input(self, sample_mapping):
        """rename should never modify the input."""
        original_copy = sample_mapping.copy()
        rename(sample_mapping, "Renamed")
        assert sample_mapping == original_copy


class TestUpdateMetadata:
    """Tests for the update_metadata() function."""

    def test_update_metadata_merges_keys(self, sample_mapping):
        """update_metadata should merge provided updates into the clone."""
        updates = {"name": "Updated", "custom_field": "custom_value"}
        updated = update_metadata(sample_mapping, updates)
        assert updated["name"] == "Updated"
        assert updated["custom_field"] == "custom_value"

    def test_update_metadata_does_not_mutate_input(self, sample_mapping):
        """update_metadata should never modify the input."""
        original_copy = sample_mapping.copy()
        update_metadata(sample_mapping, {"name": "Modified"})
        assert sample_mapping == original_copy

    def test_update_metadata_preserves_existing_keys(self, sample_mapping):
        """update_metadata should keep existing keys not in updates."""
        updated = update_metadata(sample_mapping, {"name": "New"})
        assert updated["buttons"] == sample_mapping["buttons"]
        assert updated["axes"] == sample_mapping["axes"]


class TestStripPersonalData:
    """Tests for the strip_personal_data() function."""

    def test_strip_personal_data_removes_sensitive_keys(self, sample_mapping):
        """strip_personal_data should remove shared_by, author_email, private_notes."""
        mapping_with_personal = {
            **sample_mapping,
            "shared_by": "user@example.com",
            "author_email": "author@example.com",
            "private_notes": "Some internal notes",
        }
        stripped = strip_personal_data(mapping_with_personal)
        assert "shared_by" not in stripped
        assert "author_email" not in stripped
        assert "private_notes" not in stripped

    def test_strip_personal_data_preserves_other_keys(self, sample_mapping):
        """strip_personal_data should keep non-sensitive keys."""
        stripped = strip_personal_data(sample_mapping)
        assert stripped["name"] == sample_mapping["name"]
        assert stripped["buttons"] == sample_mapping["buttons"]
        assert stripped["slug"] == sample_mapping["slug"]

    def test_strip_personal_data_handles_missing_personal_keys(self):
        """strip_personal_data should gracefully handle missing personal keys."""
        # Mapping without personal data keys
        minimal = {"name": "Test", "buttons": {0: 60}}
        stripped = strip_personal_data(minimal)
        assert "author_email" not in stripped
        assert "private_notes" not in stripped
        assert "shared_by" not in stripped
        assert stripped == minimal  # Should be equal since no personal data to strip


class TestChain:
    """Tests for the chain() function."""

    def test_chain_applies_multiple_operations(self, sample_mapping):
        """chain should apply operations in order."""
        result = chain(
            sample_mapping,
            lambda m: rename(m, "Step 1"),
            lambda m: update_metadata(m, {"custom": "value"}),
        )
        assert result["name"] == "Step 1"
        assert result["custom"] == "value"

    def test_chain_does_not_mutate_input(self, sample_mapping):
        """chain should never modify the input."""
        original_copy = sample_mapping.copy()
        chain(
            sample_mapping,
            lambda m: rename(m, "Modified"),
            lambda m: update_metadata(m, {"extra": "field"}),
        )
        assert sample_mapping == original_copy

    def test_chain_empty_operations_returns_deep_copy(self, sample_mapping):
        """chain with no operations should return a deep copy."""
        result = chain(sample_mapping)
        assert result == sample_mapping
        assert result is not sample_mapping

    def test_chain_with_clone_and_strip(self, sample_mapping):
        """chain should compose clone + strip_personal_data correctly."""
        mapping_with_personal = {
            **sample_mapping,
            "author_email": "author@example.com",
        }
        result = chain(
            mapping_with_personal,
            lambda m: clone(m, new_name="Cloned"),
            strip_personal_data,
        )
        assert result["name"] == "Cloned"
        assert "author_email" not in result


class TestResetKeys:
    """Tests for the RESET_KEYS set."""

    def test_reset_keys_contains_expected_keys(self):
        """RESET_KEYS should contain the expected metadata fields."""
        expected = {
            "slug",
            "marketplace_id",
            "downloaded_at",
            "shared_by",
            "last_modified",
            "checksum",
        }
        assert RESET_KEYS == expected
