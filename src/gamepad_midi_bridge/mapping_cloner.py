"""Pure-function mapping cloning with optional renames and metadata reset.

Enables safe deep-copying of mapping dicts with optional field overrides and
per-instance metadata reset (timestamps, marketplace IDs, etc).

Pure stdlib only (copy.deepcopy). No Qt dependencies.
"""

import copy
from typing import Any, Callable, Dict, Optional, Set


# Top-level keys that should be reset/cleared when cloning a mapping
# (typically per-instance metadata that shouldn't carry over to the clone)
RESET_KEYS: Set[str] = {
    "slug",
    "marketplace_id",
    "downloaded_at",
    "shared_by",
    "last_modified",
    "checksum",
}


def clone(
    mapping_dict: dict,
    new_name: Optional[str] = None,
    new_description: Optional[str] = None,
    reset_keys: bool = True,
) -> dict:
    """Deep-copy a mapping dict with optional field overwrites and metadata reset.

    The input dict is never modified. Returns a completely independent copy.

    Args:
        mapping_dict: The mapping dictionary to clone
        new_name: If provided, overwrite the "name" field in the clone
        new_description: If provided, overwrite the "description" field in the clone
        reset_keys: If True (default), remove or clear keys in RESET_KEYS.
                   For string values, set to ""; for others, set to None.

    Returns:
        A new mapping dict with requested overwrites and metadata reset applied
    """
    cloned = copy.deepcopy(mapping_dict)

    if new_name is not None:
        cloned["name"] = new_name

    if new_description is not None:
        cloned["description"] = new_description

    if reset_keys:
        for key in RESET_KEYS:
            if key in cloned:
                # Clear all reset keys to empty string (handles most metadata)
                cloned[key] = ""

    return cloned


def clone_with_slug(mapping_dict: dict, new_slug: str) -> dict:
    """Convenience: clone and set the slug field.

    Shorthand for clone() with reset_keys=True that explicitly sets slug.

    Args:
        mapping_dict: The mapping dictionary to clone
        new_slug: The slug value to set in the clone

    Returns:
        A cloned mapping dict with the slug field set and other metadata reset
    """
    cloned = clone(mapping_dict, reset_keys=True)
    cloned["slug"] = new_slug
    return cloned


def rename(mapping_dict: dict, new_name: str) -> dict:
    """Clone a mapping and set a new name.

    Args:
        mapping_dict: The mapping dictionary to clone
        new_name: The new name value

    Returns:
        A cloned mapping dict with the name field updated
    """
    return clone(mapping_dict, new_name=new_name)


def update_metadata(mapping_dict: dict, updates: Dict[str, Any]) -> dict:
    """Clone a mapping and merge top-level key updates into it.

    Args:
        mapping_dict: The mapping dictionary to clone
        updates: Dict of key-value pairs to merge into the clone

    Returns:
        A cloned mapping dict with updates applied at the top level
    """
    cloned = copy.deepcopy(mapping_dict)
    cloned.update(updates)
    return cloned


def strip_personal_data(mapping_dict: dict) -> dict:
    """Clone a mapping and remove sensitive/personal fields.

    Anonymizes a mapping for marketplace upload by removing:
    - shared_by
    - author_email
    - private_notes
    - Any other fields that may contain user-identifiable data

    Args:
        mapping_dict: The mapping dictionary to anonymize

    Returns:
        A cloned mapping dict with personal data fields removed
    """
    personal_keys = {"shared_by", "author_email", "private_notes"}
    cloned = copy.deepcopy(mapping_dict)

    for key in personal_keys:
        cloned.pop(key, None)

    return cloned


def chain(
    mapping_dict: dict, *operations: Callable[[dict], dict]
) -> dict:
    """Apply a sequence of clone/rename/update functions in order.

    Each operation receives the result of the previous one and returns a new dict.
    The input mapping_dict is never modified. Useful for composing multiple
    transformations without intermediate variables.

    Args:
        mapping_dict: The initial mapping dictionary
        *operations: Variable number of functions, each taking (dict) -> dict

    Returns:
        The final mapping dict after all operations applied in sequence
    """
    result = copy.deepcopy(mapping_dict)
    for operation in operations:
        result = operation(result)
    return result
