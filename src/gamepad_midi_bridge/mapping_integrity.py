"""Integrity verification for mapping dictionaries.

Provides HMAC-style signing and verification for mapping presets, enabling:
- Marketplace download verification (detect tampering)
- Signer identification and timestamping
- Plain hash mode for unsigned mappings
- Constant-time comparison to prevent timing attacks

Pure stdlib only (hashlib + hmac + dataclasses + json). No Qt dependencies.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from gamepad_midi_bridge.mapping_fingerprint import canonical_json


@dataclass
class IntegrityStamp:
    """Signed integrity stamp for a mapping.

    Attributes:
        algorithm: Hash algorithm used ("sha256" or "hmac_sha256")
        hash: Hex digest of the integrity hash
        version: Format version of this stamp (default "1.0")
        signer: Optional name/ID of the signer (can be empty for unsigned)
        timestamp_s: When the stamp was created (Unix timestamp, 0 for none)
    """

    algorithm: str
    hash: str
    version: str = "1.0"
    signer: str = ""
    timestamp_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert stamp to dict for JSON serialization.

        Returns:
            Dict with all stamp fields
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "IntegrityStamp":
        """Create stamp from dict.

        Args:
            data: Dict with stamp fields

        Returns:
            IntegrityStamp instance

        Raises:
            KeyError: If required fields (algorithm, hash) are missing
            TypeError: If types don't match expected
        """
        return IntegrityStamp(
            algorithm=data["algorithm"],
            hash=data["hash"],
            version=data.get("version", "1.0"),
            signer=data.get("signer", ""),
            timestamp_s=data.get("timestamp_s", 0.0),
        )


def compute_hash(
    mapping_dict: dict, ignore_keys: Optional[List[str]] = None
) -> str:
    """Compute SHA-256 hash of a mapping dict's canonical JSON.

    Args:
        mapping_dict: The mapping dictionary to hash
        ignore_keys: Top-level keys to exclude from the hash

    Returns:
        64-character SHA-256 hex digest
    """
    if ignore_keys:
        filtered = {k: v for k, v in mapping_dict.items() if k not in ignore_keys}
    else:
        filtered = mapping_dict

    canonical = canonical_json(filtered)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_hmac(
    mapping_dict: dict,
    secret: str,
    ignore_keys: Optional[List[str]] = None,
) -> str:
    """Compute HMAC-SHA-256 hash of a mapping dict's canonical JSON.

    Args:
        mapping_dict: The mapping dictionary to hash
        secret: Secret key for HMAC
        ignore_keys: Top-level keys to exclude from the hash

    Returns:
        64-character HMAC-SHA-256 hex digest
    """
    if ignore_keys:
        filtered = {k: v for k, v in mapping_dict.items() if k not in ignore_keys}
    else:
        filtered = mapping_dict

    canonical = canonical_json(filtered)
    return hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def stamp(
    mapping_dict: dict,
    signer: str = "",
    now_s: float = 0.0,
    secret: Optional[str] = None,
    ignore_keys: Optional[List[str]] = None,
) -> IntegrityStamp:
    """Create an IntegrityStamp for a mapping dict.

    Args:
        mapping_dict: The mapping dictionary to stamp
        signer: Optional name/ID of the signer
        now_s: Timestamp in seconds (0 to omit)
        secret: Secret for HMAC signing; if None, uses plain SHA-256
        ignore_keys: Top-level keys to exclude from the hash

    Returns:
        IntegrityStamp with algorithm, hash, version, signer, timestamp
    """
    if secret:
        algorithm = "hmac_sha256"
        hash_value = compute_hmac(mapping_dict, secret, ignore_keys)
    else:
        algorithm = "sha256"
        hash_value = compute_hash(mapping_dict, ignore_keys)

    return IntegrityStamp(
        algorithm=algorithm,
        hash=hash_value,
        version="1.0",
        signer=signer,
        timestamp_s=now_s,
    )


def verify(
    mapping_dict: dict,
    stamp: IntegrityStamp,
    secret: Optional[str] = None,
    ignore_keys: Optional[List[str]] = None,
) -> bool:
    """Verify a mapping dict against an IntegrityStamp.

    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.

    Args:
        mapping_dict: The mapping dictionary to verify
        stamp: The IntegrityStamp to check against
        secret: Secret for HMAC verification; required if stamp.algorithm is "hmac_sha256"
        ignore_keys: Top-level keys to exclude from the hash

    Returns:
        True if the mapping's hash matches the stamp, False otherwise
    """
    if stamp.algorithm == "hmac_sha256":
        if not secret:
            return False
        recomputed = compute_hmac(mapping_dict, secret, ignore_keys)
    elif stamp.algorithm == "sha256":
        recomputed = compute_hash(mapping_dict, ignore_keys)
    else:
        return False

    return hmac.compare_digest(recomputed, stamp.hash)


def attach_stamp(mapping_dict: dict, stamp: IntegrityStamp) -> dict:
    """Attach an IntegrityStamp to a mapping dict.

    Returns a new dict with `_integrity` key set to stamp.to_dict().
    Does not modify the input dict.

    Args:
        mapping_dict: The mapping dictionary
        stamp: The IntegrityStamp to attach

    Returns:
        New dict with _integrity key added
    """
    result = dict(mapping_dict)
    result["_integrity"] = stamp.to_dict()
    return result


def detach_stamp(mapping_dict: dict) -> Tuple[dict, Optional[IntegrityStamp]]:
    """Remove and parse IntegrityStamp from a mapping dict.

    Returns a new dict without `_integrity` key and the parsed stamp (or None).

    Args:
        mapping_dict: The mapping dictionary

    Returns:
        Tuple of (mapping_without_integrity, parsed_stamp_or_None)
    """
    result = dict(mapping_dict)
    stamp_data = result.pop("_integrity", None)

    if stamp_data is None:
        return result, None

    try:
        stamp_obj = IntegrityStamp.from_dict(stamp_data)
        return result, stamp_obj
    except (KeyError, TypeError, ValueError):
        return result, None


def verify_attached(
    mapping_dict: dict, secret: Optional[str] = None
) -> bool:
    """Verify a mapping dict with an attached _integrity stamp.

    Detaches the stamp and verifies the mapping against it.

    Args:
        mapping_dict: The mapping dictionary (with _integrity key)
        secret: Secret for HMAC verification

    Returns:
        True if stamp is present and valid, False otherwise
    """
    mapping_clean, stamp_obj = detach_stamp(mapping_dict)

    if stamp_obj is None:
        return False

    return verify(mapping_clean, stamp_obj, secret)
