"""
Mapping share-link encoder: compress mapping dicts to URL-safe strings and back.

Pure stdlib (json + zlib + base64) with no external dependencies.
"""

import base64
import json
import zlib
from typing import Any, Dict, Optional


def encode(mapping_dict: dict) -> str:
    """
    Serialize a mapping dict to a compressed, URL-safe base64 string.

    Args:
        mapping_dict: The mapping dictionary to encode

    Returns:
        URL-safe base64-encoded string (no padding)
    """
    json_str = json.dumps(mapping_dict, separators=(',', ':'), sort_keys=True)
    compressed = zlib.compress(json_str.encode('utf-8'))
    b64 = base64.urlsafe_b64encode(compressed).decode('ascii')
    # Remove padding for cleaner URLs
    return b64.rstrip('=')


def decode(share_str: str) -> dict:
    """
    Decompress a share link back to a mapping dict.

    Args:
        share_str: The encoded share string

    Returns:
        The original mapping dictionary

    Raises:
        ValueError: If the string is corrupt, not proper base64, zlib, or JSON
    """
    try:
        # Re-add padding for base64 decoding
        padding = 4 - (len(share_str) % 4)
        if padding != 4:
            share_str = share_str + ('=' * padding)

        compressed = base64.urlsafe_b64decode(share_str.encode('ascii'))
        json_str = zlib.decompress(compressed).decode('utf-8')
        return json.loads(json_str)
    except (ValueError, TypeError, zlib.error) as e:
        raise ValueError(f"Failed to decode share link: {e}") from e


def is_share_link(s: str) -> bool:
    """
    Check if a string looks like a valid share link (non-raising).

    Args:
        s: String to check

    Returns:
        True if s decodes cleanly, False otherwise (never raises)
    """
    if not isinstance(s, str) or not s:
        return False

    try:
        decode(s)
        return True
    except (ValueError, TypeError):
        return False


def compress_ratio(mapping_dict: dict) -> float:
    """
    Calculate compression ratio: len(encoded) / len(json).

    Args:
        mapping_dict: The mapping dictionary

    Returns:
        Ratio as a float (1.0 = no compression, < 1.0 = compressed, > 1.0 = expanded)
    """
    json_str = json.dumps(mapping_dict, separators=(',', ':'), sort_keys=True)
    encoded = encode(mapping_dict)

    if not json_str:
        return 0.0

    return len(encoded) / len(json_str)


def wrap_in_url(
    share_str: str,
    base_url: str = "https://midi.aidxn.com/import?p="
) -> str:
    """
    Prepend a base URL to the share string.

    Args:
        share_str: The encoded share string
        base_url: The base URL to prepend (default: midi.aidxn.com import endpoint)

    Returns:
        Full URL string
    """
    return f"{base_url}{share_str}"


def extract_from_url(
    url: str,
    base_url: str = "https://midi.aidxn.com/import?p="
) -> Optional[str]:
    """
    Extract the share string from a URL.

    Args:
        url: The full URL
        base_url: The expected base URL (default: midi.aidxn.com import endpoint)

    Returns:
        The share string if URL matches base_url, else None
    """
    if not url.startswith(base_url):
        return None

    return url[len(base_url):]


def safe_encode(
    mapping_dict: dict,
    max_length: int = 2000
) -> Optional[str]:
    """
    Encode a mapping dict if the result fits within max_length.

    Args:
        mapping_dict: The mapping dictionary to encode
        max_length: Maximum allowed length (default: 2000 chars)

    Returns:
        Encoded string if within max_length, else None
    """
    encoded = encode(mapping_dict)

    if len(encoded) <= max_length:
        return encoded

    return None
