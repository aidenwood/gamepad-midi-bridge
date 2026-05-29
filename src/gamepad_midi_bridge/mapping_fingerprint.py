"""Stable content-hash fingerprinting for mapping dicts.

Produces deterministic SHA-256 hashes for mapping dictionaries, enabling:
- Marketplace deduplication ("is this preset already in your library?")
- Version comparison (has the user modified their mapping?)
- Component diffing (which sections changed?)

Pure stdlib only (hashlib + json). No Qt dependencies.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional


def canonical_json(data: Any) -> str:
    """Convert data to deterministic JSON with sorted keys and no whitespace.

    Rules:
    - Dicts: sort keys recursively
    - Lists: preserve order (don't sort)
    - Sets: convert to sorted list
    - Floats: use repr() for stable representation
    - No whitespace

    Args:
        data: Any JSON-serializable value

    Returns:
        Canonical JSON string with no whitespace
    """

    class CanonicalEncoder(json.JSONEncoder):
        """Custom JSON encoder for canonical form."""

        def encode(self, o: Any) -> str:
            """Encode with custom handling for sets and floats."""
            if isinstance(o, set):
                return super().encode(sorted(o))
            if isinstance(o, float):
                return repr(o)
            return super().encode(o)

        def iterencode(self, o: Any, _one_shot: bool = False) -> Any:
            """Iterencode with custom key sorting for dicts."""
            if isinstance(o, dict):
                # Sort keys and reconstruct
                sorted_dict = {k: o[k] for k in sorted(o.keys())}
                return super().iterencode(sorted_dict, _one_shot)
            return super().iterencode(o, _one_shot)

    # Custom encoder to handle nested dicts and sets
    def _normalize(obj: Any) -> Any:
        """Recursively normalize data structure."""
        if isinstance(obj, dict):
            return {k: _normalize(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, list):
            return [_normalize(item) for item in obj]
        if isinstance(obj, set):
            return sorted(obj)
        return obj

    normalized = _normalize(data)
    return json.dumps(
        normalized,
        separators=(",", ":"),
        ensure_ascii=True,
        sort_keys=True,
        cls=CanonicalEncoder,
    )


def fingerprint(
    mapping_dict: dict, ignore_keys: Optional[List[str]] = None
) -> str:
    """Return SHA-256 hex digest of a mapping dict's canonical JSON.

    Args:
        mapping_dict: The mapping dictionary to fingerprint
        ignore_keys: Top-level keys to exclude from the hash (e.g., ["last_modified"])

    Returns:
        64-character SHA-256 hex digest
    """
    if ignore_keys:
        filtered = {k: v for k, v in mapping_dict.items() if k not in ignore_keys}
    else:
        filtered = mapping_dict

    canonical = canonical_json(filtered)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def short_fingerprint(mapping_dict: dict, length: int = 8) -> str:
    """Return first N characters of the fingerprint.

    Args:
        mapping_dict: The mapping dictionary to fingerprint
        length: Number of characters to return (clamped 4..64, default 8)

    Returns:
        Short hex string
    """
    clamped = max(4, min(length, 64))
    full = fingerprint(mapping_dict)
    return full[:clamped]


def compare(
    a_dict: dict, b_dict: dict, ignore_keys: Optional[List[str]] = None
) -> bool:
    """Return True if two mapping dicts have identical fingerprints.

    Args:
        a_dict: First mapping dict
        b_dict: Second mapping dict
        ignore_keys: Keys to exclude from comparison

    Returns:
        True if fingerprints match
    """
    return fingerprint(a_dict, ignore_keys) == fingerprint(b_dict, ignore_keys)


def fingerprint_components(mapping_dict: dict) -> Dict[str, str]:
    """Return per-section fingerprints for a mapping dict.

    Allows UI to show "only the buttons changed" by comparing individual sections.
    Sections are top-level keys of the mapping dict. Missing sections are ignored.

    Args:
        mapping_dict: The mapping dictionary

    Returns:
        Dict mapping section name to hex digest, e.g. {"buttons": "abc123...", "axes": "def456..."}
    """
    result = {}
    for key, value in mapping_dict.items():
        if value is not None:  # Skip null sections
            result[key] = hashlib.sha256(
                canonical_json(value).encode("utf-8")
            ).hexdigest()
    return result


def diff_summary(a_dict: dict, b_dict: dict) -> List[str]:
    """Return list of section names with differing fingerprints.

    Compares per-section hashes and returns sections where they differ.
    Useful for showing users which parts of a mapping changed.

    Args:
        a_dict: First mapping dict
        b_dict: Second mapping dict

    Returns:
        List of section names with different hashes, empty list if identical
    """
    a_components = fingerprint_components(a_dict)
    b_components = fingerprint_components(b_dict)

    # Sections present in either dict
    all_sections = set(a_components.keys()) | set(b_components.keys())

    diffs = []
    for section in sorted(all_sections):
        a_hash = a_components.get(section)
        b_hash = b_components.get(section)
        if a_hash != b_hash:
            diffs.append(section)

    return diffs
