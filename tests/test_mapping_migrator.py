"""Schema version migrations — v1 → v5 transformations."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_migrator import (
    CURRENT_SCHEMA,
    migrate_v1_to_v2,
    migrate_v2_to_v3,
    migrate_v3_to_v4,
    migrate_v4_to_v5,
    migrate_to_current,
    needs_migration,
    migration_chain,
)


class TestMigrateV1toV2:
    """Test migrate_v1_to_v2: adds triggers and sets schema_version=2."""

    def test_sets_schema_version_2(self):
        d = {"buttons": {0: 60}}
        result = migrate_v1_to_v2(d)
        assert result["schema_version"] == 2

    def test_adds_triggers_if_missing(self):
        d = {"buttons": {0: 60}}
        result = migrate_v1_to_v2(d)
        assert "triggers" in result
        assert result["triggers"] == {}

    def test_preserves_existing_triggers(self):
        d = {"buttons": {0: 60}, "triggers": {4: "bow"}}
        result = migrate_v1_to_v2(d)
        assert result["triggers"] == {4: "bow"}

    def test_preserves_other_fields(self):
        d = {"buttons": {0: 60}, "name": "TestMapping"}
        result = migrate_v1_to_v2(d)
        assert result["name"] == "TestMapping"


class TestMigrateV2toV3:
    """Test migrate_v2_to_v3: adds velocity to buttons, setlist."""

    def test_sets_schema_version_3(self):
        d = {"schema_version": 2}
        result = migrate_v2_to_v3(d)
        assert result["schema_version"] == 3

    def test_adds_setlist_if_missing(self):
        d = {"schema_version": 2}
        result = migrate_v2_to_v3(d)
        assert "setlist" in result
        assert result["setlist"] == []

    def test_preserves_existing_setlist(self):
        d = {"schema_version": 2, "setlist": ["preset1", "preset2"]}
        result = migrate_v2_to_v3(d)
        assert result["setlist"] == ["preset1", "preset2"]

    def test_doesnt_add_velocity_to_flat_buttons(self):
        """Buttons that are ints (flat notes) should not become dicts."""
        d = {"schema_version": 2, "buttons": {0: 60, 1: 62}}
        result = migrate_v2_to_v3(d)
        # Buttons remain ints for v2 presets
        assert result["buttons"] == {0: 60, 1: 62}

    def test_preserves_velocity_if_already_present(self):
        d = {
            "schema_version": 2,
            "buttons": {
                0: {"note": 60, "velocity": 80}
            }
        }
        result = migrate_v2_to_v3(d)
        assert result["buttons"][0]["velocity"] == 80


class TestMigrateV3toV4:
    """Test migrate_v3_to_v4: adds macros and channel."""

    def test_sets_schema_version_4(self):
        d = {"schema_version": 3}
        result = migrate_v3_to_v4(d)
        assert result["schema_version"] == 4

    def test_adds_macros_if_missing(self):
        d = {"schema_version": 3}
        result = migrate_v3_to_v4(d)
        assert "macros" in result
        assert result["macros"] == []

    def test_preserves_existing_macros(self):
        d = {"schema_version": 3, "macros": [{"name": "macro1"}]}
        result = migrate_v3_to_v4(d)
        assert result["macros"] == [{"name": "macro1"}]

    def test_adds_channel_if_missing(self):
        d = {"schema_version": 3}
        result = migrate_v3_to_v4(d)
        assert result["channel"] == 1

    def test_preserves_existing_channel(self):
        d = {"schema_version": 3, "channel": 5}
        result = migrate_v3_to_v4(d)
        assert result["channel"] == 5


class TestMigrateV4toV5:
    """Test migrate_v4_to_v5: adds shift_layer and program_change."""

    def test_sets_schema_version_5(self):
        d = {"schema_version": 4}
        result = migrate_v4_to_v5(d)
        assert result["schema_version"] == 5

    def test_adds_shift_layer_if_missing(self):
        d = {"schema_version": 4}
        result = migrate_v4_to_v5(d)
        assert "shift_layer" in result
        assert result["shift_layer"] is None

    def test_preserves_existing_shift_layer(self):
        d = {"schema_version": 4, "shift_layer": {"buttons": {0: 1}}}
        result = migrate_v4_to_v5(d)
        assert result["shift_layer"] == {"buttons": {0: 1}}

    def test_adds_program_change_if_missing(self):
        d = {"schema_version": 4}
        result = migrate_v4_to_v5(d)
        assert "program_change" in result
        assert result["program_change"] is None

    def test_preserves_existing_program_change(self):
        d = {"schema_version": 4, "program_change": {"enabled": True}}
        result = migrate_v4_to_v5(d)
        assert result["program_change"] == {"enabled": True}


class TestMigrateToCurrentFull:
    """Test migrate_to_current: full pipeline v1 → v5."""

    def test_current_schema_constant(self):
        assert CURRENT_SCHEMA == 5

    def test_v1_to_v5_complete_chain(self):
        """Full v1 → v5 migration."""
        d = {"schema_version": 1, "buttons": {0: 60}}
        result = migrate_to_current(d)

        assert result["schema_version"] == 5
        assert "triggers" in result  # from v1→v2
        assert "setlist" in result   # from v2→v3
        assert "macros" in result    # from v3→v4
        assert "shift_layer" in result  # from v4→v5
        assert "program_change" in result  # from v4→v5

    def test_v5_unchanged(self):
        """Already at v5, no migration needed."""
        d = {"schema_version": 5, "buttons": {0: 60}, "macros": []}
        result = migrate_to_current(d)
        assert result["schema_version"] == 5

    def test_v6_forward_compatible(self):
        """Future schema_version > CURRENT_SCHEMA returns as-is."""
        d = {"schema_version": 6, "buttons": {0: 60}, "future_field": True}
        result = migrate_to_current(d)
        assert result["schema_version"] == 6
        assert result["future_field"] is True

    def test_missing_schema_version_defaults_to_1(self):
        """Missing schema_version treated as v1."""
        d = {"buttons": {0: 60}}
        result = migrate_to_current(d)
        assert result["schema_version"] == 5

    def test_non_int_schema_version_raises(self):
        """Non-int schema_version raises ValueError."""
        d = {"schema_version": "not_an_int"}
        with pytest.raises(ValueError, match="Invalid schema_version"):
            migrate_to_current(d)

    def test_negative_schema_version_raises(self):
        """Negative schema_version raises ValueError."""
        d = {"schema_version": -1}
        with pytest.raises(ValueError, match="Invalid schema_version"):
            migrate_to_current(d)

    def test_input_unchanged(self):
        """Original dict is not mutated."""
        d = {"schema_version": 1, "buttons": {0: 60}}
        original = d.copy()
        result = migrate_to_current(d)

        assert d == original  # Input unchanged
        assert result["schema_version"] == 5  # Result migrated

    def test_deep_copy_applied(self):
        """Nested structures are deep-copied, not referenced."""
        d = {
            "schema_version": 1,
            "buttons": {0: 60},
            "nested": {"key": "value"}
        }
        result = migrate_to_current(d)

        # Modify result's nested
        result["nested"]["key"] = "modified"

        # Original should be unchanged
        assert d["nested"]["key"] == "value"


class TestNeedsMigration:
    """Test needs_migration: bool check for v < CURRENT_SCHEMA."""

    def test_v3_needs_migration(self):
        d = {"schema_version": 3}
        assert needs_migration(d) is True

    def test_v5_does_not_need_migration(self):
        d = {"schema_version": 5}
        assert needs_migration(d) is False

    def test_v6_does_not_need_migration(self):
        d = {"schema_version": 6}
        assert needs_migration(d) is False

    def test_missing_schema_version_defaults_to_1_needs_migration(self):
        d = {}
        assert needs_migration(d) is True


class TestMigrationChain:
    """Test migration_chain: list of target versions."""

    def test_chain_from_v2(self):
        """v2 → v3 → v4 → v5."""
        chain = migration_chain(2)
        assert chain == [3, 4, 5]

    def test_chain_from_v1(self):
        """v1 → v2 → v3 → v4 → v5."""
        chain = migration_chain(1)
        assert chain == [2, 3, 4, 5]

    def test_chain_from_v4(self):
        """v4 → v5."""
        chain = migration_chain(4)
        assert chain == [5]

    def test_chain_from_v5_empty(self):
        """v5 (already current) → empty."""
        chain = migration_chain(5)
        assert chain == []

    def test_chain_from_v6_empty(self):
        """v6 (future) → empty."""
        chain = migration_chain(6)
        assert chain == []
