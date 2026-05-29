"""Schema version migrations for mapping dict → dict transformations.

Pure stdlib + dict transforms, no Qt, no mapping imports.
Each migration function takes a dict at schema_version N and returns dict at N+1.
"""
from __future__ import annotations

import copy
from typing import Callable, Dict, List


CURRENT_SCHEMA: int = 5

MIGRATIONS: Dict[int, Callable[[dict], dict]] = {}


def migrate_v1_to_v2(d: dict) -> dict:
    """V1 → V2: Add default triggers config.

    v2 added per-trigger shaping options (triggers dict).
    """
    d["triggers"] = d.get("triggers", {})
    d["schema_version"] = 2
    return d


def migrate_v2_to_v3(d: dict) -> dict:
    """V2 → V3: Ensure velocity on all buttons, add setlist.

    v3 added per-button velocity control and setlist support.
    """
    buttons = d.get("buttons", {})
    if isinstance(buttons, dict):
        for key in buttons:
            if isinstance(buttons[key], dict):
                # Already a dict (button config), ensure velocity
                if "velocity" not in buttons[key]:
                    buttons[key]["velocity"] = 100

    d["setlist"] = d.get("setlist", [])
    d["schema_version"] = 3
    return d


def migrate_v3_to_v4(d: dict) -> dict:
    """V3 → V4: Add macros list and channel default.

    v4 added macro support and ensured global channel defaults.
    """
    d["macros"] = d.get("macros", [])
    if "channel" not in d:
        d["channel"] = 1
    d["schema_version"] = 4
    return d


def migrate_v4_to_v5(d: dict) -> dict:
    """V4 → V5: Add shift_layer and program_change.

    v5 adds shift-layer overlay support and program-change preset hotswap.
    """
    if "shift_layer" not in d:
        d["shift_layer"] = None
    if "program_change" not in d:
        d["program_change"] = None
    d["schema_version"] = 5
    return d


# Populate the migrations registry
MIGRATIONS[1] = migrate_v1_to_v2
MIGRATIONS[2] = migrate_v2_to_v3
MIGRATIONS[3] = migrate_v3_to_v4
MIGRATIONS[4] = migrate_v4_to_v5


def needs_migration(mapping_dict: dict) -> bool:
    """Return True if schema_version < CURRENT_SCHEMA."""
    schema_version = mapping_dict.get("schema_version", 1)
    return int(schema_version) < CURRENT_SCHEMA


def migration_chain(from_version: int) -> List[int]:
    """Return the sequence of target versions traversed.

    For example, migration_chain(2) returns [3, 4, 5]
    because migrations from v2 go through v3, v4, then v5.
    """
    if from_version >= CURRENT_SCHEMA:
        return []

    chain = []
    current = from_version
    while current < CURRENT_SCHEMA:
        current += 1
        chain.append(current)
    return chain


def migrate_to_current(mapping_dict: dict) -> dict:
    """Apply all migrations to bring dict to CURRENT_SCHEMA.

    Returns a NEW dict (deep copy). Input is never mutated.

    Args:
        mapping_dict: dict with optional 'schema_version' key (defaults to 1).

    Returns:
        New dict at CURRENT_SCHEMA with all migrations applied.

    Raises:
        ValueError: if schema_version is non-int or < 1.

    Forward-compatible: if schema_version > CURRENT_SCHEMA, returns a copy as-is.
    """
    # Deep copy to avoid mutating input
    result = copy.deepcopy(mapping_dict)

    # Get schema_version, default to 1
    schema_version = result.get("schema_version", 1)

    # Validate schema_version
    try:
        schema_version = int(schema_version)
    except (ValueError, TypeError):
        raise ValueError(
            f"Invalid schema_version: {schema_version!r}. "
            "Must be an integer or missing (defaults to 1)."
        )

    if schema_version < 1:
        raise ValueError(
            f"Invalid schema_version: {schema_version}. "
            "Must be >= 1."
        )

    # Forward-compatible: if newer than current, return as-is
    if schema_version > CURRENT_SCHEMA:
        return result

    # Apply migrations in order
    while schema_version < CURRENT_SCHEMA:
        if schema_version not in MIGRATIONS:
            raise ValueError(
                f"No migration found for schema_version {schema_version}."
            )
        migration_func = MIGRATIONS[schema_version]
        result = migration_func(result)
        schema_version = result.get("schema_version", schema_version + 1)

    return result
