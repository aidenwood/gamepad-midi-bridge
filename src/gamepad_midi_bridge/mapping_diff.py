"""Pure-function diff over Mapping objects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from .mapping import Mapping


@dataclass
class DiffEntry:
    """A single difference between two mappings."""
    path: str          # e.g. "axes.4" or "l2_trigger.mode"
    left: Any          # value in A (None if missing)
    right: Any         # value in B (None if missing)
    kind: str          # "added" | "removed" | "changed"


def diff_mappings(a: Mapping, b: Mapping) -> List[DiffEntry]:
    """Walk Mapping.to_dict() of both, return ordered DiffEntry list.

    Recursive into dicts (axes, buttons, hats, button_configs, etc).
    Skip identical values; emit only differences.
    """
    a_dict = a.to_dict()
    b_dict = b.to_dict()

    entries: List[DiffEntry] = []

    def walk_diff(a_val: Any, b_val: Any, prefix: str = "") -> None:
        """Recursively walk two dicts/values and emit DiffEntry objects."""
        if isinstance(a_val, dict) and isinstance(b_val, dict):
            # Both are dicts — recurse
            all_keys = set(a_val.keys()) | set(b_val.keys())
            for key in sorted(all_keys):
                new_prefix = f"{prefix}.{key}" if prefix else key
                a_nested = a_val.get(key)
                b_nested = b_val.get(key)

                if key not in a_val:
                    # Key only in B
                    entries.append(DiffEntry(
                        path=new_prefix,
                        left=None,
                        right=b_nested,
                        kind="added"
                    ))
                elif key not in b_val:
                    # Key only in A
                    entries.append(DiffEntry(
                        path=new_prefix,
                        left=a_nested,
                        right=None,
                        kind="removed"
                    ))
                else:
                    # Both have the key — recurse
                    walk_diff(a_nested, b_nested, new_prefix)
        elif isinstance(a_val, dict) or isinstance(b_val, dict):
            # One is dict, other is not — treat as changed
            if a_val != b_val:
                entries.append(DiffEntry(
                    path=prefix,
                    left=a_val,
                    right=b_val,
                    kind="changed"
                ))
        else:
            # Both scalars
            if a_val != b_val:
                entries.append(DiffEntry(
                    path=prefix,
                    left=a_val,
                    right=b_val,
                    kind="changed"
                ))

    walk_diff(a_dict, b_dict)
    return entries
