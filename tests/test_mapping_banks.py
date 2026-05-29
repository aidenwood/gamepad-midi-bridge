"""Tests for mapping_banks module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_banks import (
    MappingBank,
    MappingBanksConfig,
    MappingBanksManager,
)


def make_manager() -> MappingBanksManager:
    """Fresh manager for each test."""
    return MappingBanksManager(MappingBanksConfig())


# ---------------------------------------------------------------------------
# MappingBank: creation and serialization
# ---------------------------------------------------------------------------


def test_mapping_bank_default_fields():
    """MappingBank initializes with sensible defaults."""
    bank = MappingBank(name="Live", slug="live")
    assert bank.name == "Live"
    assert bank.slug == "live"
    assert bank.preset_slugs == []
    assert bank.description == ""
    assert bank.color == ""


def test_mapping_bank_round_trip_serialization():
    """MappingBank.to_dict / from_dict preserves state."""
    bank = MappingBank(
        name="Live Set 1",
        slug="live_set_1",
        preset_slugs=["lead", "pad"],
        description="Main performance set",
        color="#FF5733",
    )
    data = bank.to_dict()
    restored = MappingBank.from_dict(data)

    assert restored.name == bank.name
    assert restored.slug == bank.slug
    assert restored.preset_slugs == bank.preset_slugs
    assert restored.description == bank.description
    assert restored.color == bank.color


def test_mapping_bank_from_dict_handles_missing_optional():
    """from_dict doesn't crash if optional fields are missing."""
    data = {"name": "Minimal", "slug": "minimal"}
    bank = MappingBank.from_dict(data)
    assert bank.name == "Minimal"
    assert bank.slug == "minimal"
    assert bank.preset_slugs == []
    assert bank.description == ""
    assert bank.color == ""


# ---------------------------------------------------------------------------
# MappingBanksConfig: initialization and serialization
# ---------------------------------------------------------------------------


def test_mapping_banks_config_default():
    """MappingBanksConfig has sensible defaults."""
    cfg = MappingBanksConfig()
    assert cfg.banks == []
    assert cfg.max_banks == 32


def test_mapping_banks_config_clamp_max_banks():
    """max_banks is clamped to 1..1000."""
    cfg_low = MappingBanksConfig(max_banks=0)
    assert cfg_low.max_banks == 1

    cfg_high = MappingBanksConfig(max_banks=5000)
    assert cfg_high.max_banks == 1000

    cfg_ok = MappingBanksConfig(max_banks=50)
    assert cfg_ok.max_banks == 50


def test_mapping_banks_config_round_trip_serialization():
    """MappingBanksConfig.to_dict / from_dict preserves nested banks."""
    bank1 = MappingBank(name="Live", slug="live", preset_slugs=["lead", "pad"])
    bank2 = MappingBank(name="Practice", slug="practice", preset_slugs=["scales"])
    cfg = MappingBanksConfig(banks=[bank1, bank2], max_banks=64)

    data = cfg.to_dict()
    restored = MappingBanksConfig.from_dict(data)

    assert len(restored.banks) == 2
    assert restored.banks[0].slug == "live"
    assert restored.banks[0].preset_slugs == ["lead", "pad"]
    assert restored.banks[1].slug == "practice"
    assert restored.max_banks == 64


# ---------------------------------------------------------------------------
# MappingBanksManager: bank lifecycle
# ---------------------------------------------------------------------------


def test_manager_empty_by_default():
    """Fresh manager has no banks."""
    m = make_manager()
    assert m.bank_count() == 0


def test_manager_create_bank():
    """create_bank appends a new bank."""
    m = make_manager()
    bank = m.create_bank("Live", "live")
    assert bank is not None
    assert bank.name == "Live"
    assert bank.slug == "live"
    assert m.bank_count() == 1


def test_manager_create_bank_with_optional_fields():
    """create_bank accepts description and color."""
    m = make_manager()
    bank = m.create_bank(
        "Practice",
        "practice",
        description="Daily warmup",
        color="#00FF00",
    )
    assert bank.description == "Daily warmup"
    assert bank.color == "#00FF00"


def test_manager_create_bank_duplicate_slug_refused():
    """create_bank returns None if slug already exists."""
    m = make_manager()
    bank1 = m.create_bank("Live", "live")
    assert bank1 is not None
    bank2 = m.create_bank("Live Again", "live")
    assert bank2 is None
    assert m.bank_count() == 1


def test_manager_get_bank():
    """get_bank retrieves a bank by slug."""
    m = make_manager()
    created = m.create_bank("Live", "live")
    found = m.get_bank("live")
    assert found is created
    assert found.name == "Live"


def test_manager_get_bank_not_found():
    """get_bank returns None if slug doesn't exist."""
    m = make_manager()
    found = m.get_bank("nonexistent")
    assert found is None


def test_manager_delete_bank():
    """delete_bank removes a bank."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.create_bank("Practice", "practice")
    assert m.bank_count() == 2

    deleted = m.delete_bank("live")
    assert deleted is True
    assert m.bank_count() == 1
    assert m.get_bank("live") is None
    assert m.get_bank("practice") is not None


def test_manager_delete_bank_not_found():
    """delete_bank returns False if bank doesn't exist."""
    m = make_manager()
    deleted = m.delete_bank("nonexistent")
    assert deleted is False


# ---------------------------------------------------------------------------
# MappingBanksManager: preset management
# ---------------------------------------------------------------------------


def test_manager_add_to_bank():
    """add_to_bank appends a preset slug."""
    m = make_manager()
    m.create_bank("Live", "live")
    added = m.add_to_bank("live", "lead")
    assert added is True
    bank = m.get_bank("live")
    assert "lead" in bank.preset_slugs


def test_manager_add_to_bank_duplicate_ignored():
    """add_to_bank ignores duplicate presets in same bank."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.add_to_bank("live", "lead")
    added2 = m.add_to_bank("live", "lead")
    assert added2 is False
    bank = m.get_bank("live")
    assert bank.preset_slugs.count("lead") == 1


def test_manager_add_to_bank_not_found():
    """add_to_bank returns False if bank doesn't exist."""
    m = make_manager()
    added = m.add_to_bank("nonexistent", "lead")
    assert added is False


def test_manager_remove_from_bank():
    """remove_from_bank deletes a preset from a bank."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.add_to_bank("live", "lead")
    m.add_to_bank("live", "pad")

    removed = m.remove_from_bank("live", "lead")
    assert removed is True
    bank = m.get_bank("live")
    assert "lead" not in bank.preset_slugs
    assert "pad" in bank.preset_slugs


def test_manager_remove_from_bank_not_found():
    """remove_from_bank returns False if bank or preset not found."""
    m = make_manager()
    m.create_bank("Live", "live")
    removed = m.remove_from_bank("live", "nonexistent")
    assert removed is False


# ---------------------------------------------------------------------------
# MappingBanksManager: preset movement
# ---------------------------------------------------------------------------


def test_manager_move_preset():
    """move_preset transfers a preset between banks."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.create_bank("Practice", "practice")
    m.add_to_bank("live", "lead")

    moved = m.move_preset("lead", "live", "practice")
    assert moved is True
    assert "lead" not in m.get_bank("live").preset_slugs
    assert "lead" in m.get_bank("practice").preset_slugs


def test_manager_move_preset_bank_not_found():
    """move_preset returns False if either bank doesn't exist."""
    m = make_manager()
    m.create_bank("Live", "live")
    moved = m.move_preset("lead", "live", "nonexistent")
    assert moved is False


def test_manager_move_preset_preset_not_in_source():
    """move_preset returns False if preset not in source bank."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.create_bank("Practice", "practice")
    moved = m.move_preset("nonexistent", "live", "practice")
    assert moved is False


def test_manager_move_preset_to_same_bank_deduped():
    """move_preset moving to same bank still works (dedup)."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.add_to_bank("live", "lead")
    # Move from same to same — dedup on add
    moved = m.move_preset("lead", "live", "live")
    # Preset was removed, then re-added (no dup because it's the same operation)
    assert "lead" in m.get_bank("live").preset_slugs


# ---------------------------------------------------------------------------
# MappingBanksManager: queries
# ---------------------------------------------------------------------------


def test_manager_find_banks_with():
    """find_banks_with returns all banks containing a preset."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.create_bank("Practice", "practice")
    m.create_bank("Ambient", "ambient")

    m.add_to_bank("live", "pad")
    m.add_to_bank("practice", "pad")
    m.add_to_bank("ambient", "lead")

    found = m.find_banks_with("pad")
    assert len(found) == 2
    slugs = {b.slug for b in found}
    assert slugs == {"live", "practice"}


def test_manager_find_banks_with_not_found():
    """find_banks_with returns empty list if preset not in any bank."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.add_to_bank("live", "lead")
    found = m.find_banks_with("nonexistent")
    assert found == []


def test_manager_total_presets():
    """total_presets counts unique presets across all banks."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.create_bank("Practice", "practice")

    m.add_to_bank("live", "lead")
    m.add_to_bank("live", "pad")
    m.add_to_bank("practice", "lead")  # dup across banks is fine
    m.add_to_bank("practice", "bass")

    # lead appears in both, but counted once; pad, bass counted once each
    assert m.total_presets() == 3


def test_manager_total_presets_empty():
    """total_presets returns 0 with no banks or presets."""
    m = make_manager()
    assert m.total_presets() == 0


# ---------------------------------------------------------------------------
# MappingBanksManager: limits
# ---------------------------------------------------------------------------


def test_manager_max_banks_limit_enforced():
    """create_bank returns None when at max_banks limit."""
    cfg = MappingBanksConfig(max_banks=3)
    m = MappingBanksManager(cfg)

    b1 = m.create_bank("Bank1", "bank1")
    b2 = m.create_bank("Bank2", "bank2")
    b3 = m.create_bank("Bank3", "bank3")
    b4 = m.create_bank("Bank4", "bank4")

    assert b1 is not None
    assert b2 is not None
    assert b3 is not None
    assert b4 is None  # Over limit
    assert m.bank_count() == 3


# ---------------------------------------------------------------------------
# MappingBanksManager: state management
# ---------------------------------------------------------------------------


def test_manager_clear():
    """clear empties all banks."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.create_bank("Practice", "practice")
    m.add_to_bank("live", "lead")

    m.clear()
    assert m.bank_count() == 0
    assert m.total_presets() == 0


def test_manager_clear_then_create_new():
    """After clear, can create new banks again."""
    m = make_manager()
    m.create_bank("Live", "live")
    m.clear()
    bank = m.create_bank("Fresh", "fresh")
    assert bank is not None
    assert m.bank_count() == 1


# ---------------------------------------------------------------------------
# Integration: real-world scenario
# ---------------------------------------------------------------------------


def test_real_world_live_set_organization():
    """Real-world: organize presets into named "live set" banks."""
    m = make_manager()

    # Create two live sets
    live_set_1 = m.create_bank("Live Set 1", "live_set_1", color="#FF5733")
    practice = m.create_bank("Practice", "practice", color="#33FF57")

    assert live_set_1 is not None
    assert practice is not None

    # Populate Live Set 1
    m.add_to_bank("live_set_1", "lead")
    m.add_to_bank("live_set_1", "pad")
    m.add_to_bank("live_set_1", "bass")

    # Populate Practice
    m.add_to_bank("practice", "scales")
    m.add_to_bank("practice", "drums")

    # Check counts
    assert m.bank_count() == 2
    assert m.total_presets() == 5
    assert len(m.get_bank("live_set_1").preset_slugs) == 3
    assert len(m.get_bank("practice").preset_slugs) == 2

    # Find all banks with "pad"
    pad_banks = m.find_banks_with("pad")
    assert len(pad_banks) == 1
    assert pad_banks[0].slug == "live_set_1"

    # Move "scales" from practice to live_set_1
    moved = m.move_preset("scales", "practice", "live_set_1")
    assert moved is True
    assert len(m.get_bank("practice").preset_slugs) == 1
    assert len(m.get_bank("live_set_1").preset_slugs) == 4
    assert m.total_presets() == 5  # Still 5 unique


def test_real_world_serialization_round_trip():
    """Real-world: save and restore entire bank structure."""
    # Create
    m1 = make_manager()
    m1.create_bank("Live", "live", color="#FF5733")
    m1.add_to_bank("live", "lead")
    m1.add_to_bank("live", "pad")

    # Serialize
    data = m1.cfg.to_dict()

    # Restore
    m2 = MappingBanksManager(MappingBanksConfig.from_dict(data))

    # Verify
    assert m2.bank_count() == 1
    bank = m2.get_bank("live")
    assert bank is not None
    assert bank.preset_slugs == ["lead", "pad"]
    assert bank.color == "#FF5733"
