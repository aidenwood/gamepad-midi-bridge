"""Mapping slug validator — validates and normalises preset slugs (URL-safe identifiers).

Pure stdlib functions that validate preset names and convert them to kebab-case slugs.
No Qt, no external dependencies. Handles unicode normalisation, reserved word checking,
and length constraints.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import List, Set


# Reserved slug names that cannot be used
RESERVED_SLUGS: Set[str] = {"new", "edit", "delete", "default", "admin", "settings", "untitled", "draft"}

# Slug length constraints
MAX_SLUG_LENGTH: int = 64
MIN_SLUG_LENGTH: int = 2


@dataclass
class SlugValidation:
    """Result of slug validation.

    Attributes:
        valid: True if slug passes all validation checks.
        normalized: The normalised slug (what you'd store in the database).
        errors: List of error messages if validation failed.
        warnings: List of warning messages (non-fatal issues).
    """
    valid: bool
    normalized: str
    errors: List[str]
    warnings: List[str]

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SlugValidation:
        """Deserialize from a plain dict."""
        return cls(
            valid=data.get("valid", False),
            normalized=data.get("normalized", ""),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
        )


def normalize(raw: str) -> str:
    """Normalise a string into a kebab-case slug.

    Applies these transformations in order:
    1. Unicode normalisation (NFC) and accent removal (decompose, remove accents)
    2. Lowercase
    3. Replace whitespace and underscores with hyphens
    4. Strip all non-alphanumeric and non-hyphen characters
    5. Collapse multiple consecutive hyphens into one
    6. Trim leading and trailing hyphens
    7. Truncate to MAX_SLUG_LENGTH

    Args:
        raw: Any string (may contain unicode, spaces, punctuation, etc.)

    Returns:
        A normalised slug string, or empty string if input normalises to empty.

    Examples:
        "My Lead 2!" -> "my-lead-2"
        "__weird__name__" -> "weird-name"
        "Café" -> "cafe"
        "" -> ""
        "   " -> ""
    """
    if not raw:
        return ""

    # Unicode normalisation: decompose (NFD) then strip accents
    # (Café -> Cafe)
    normalized = unicodedata.normalize("NFD", raw)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # Lowercase
    normalized = normalized.lower()

    # Replace whitespace and underscores with hyphens
    normalized = re.sub(r'[\s_]+', '-', normalized)

    # Strip all non-alphanumeric and non-hyphen characters
    normalized = re.sub(r'[^a-z0-9-]', '', normalized)

    # Collapse multiple consecutive hyphens
    normalized = re.sub(r'-+', '-', normalized)

    # Trim leading and trailing hyphens
    normalized = normalized.strip('-')

    # Truncate to max length
    if len(normalized) > MAX_SLUG_LENGTH:
        normalized = normalized[:MAX_SLUG_LENGTH]

    return normalized


def validate(slug: str) -> SlugValidation:
    """Validate a slug string and return detailed validation result.

    Checks for:
    - Empty or whitespace-only strings
    - Length constraints (MIN_SLUG_LENGTH to MAX_SLUG_LENGTH)
    - Illegal characters (after normalisation check)
    - Reserved slug names
    - Warnings if the slug was changed by normalisation

    Args:
        slug: The slug to validate.

    Returns:
        SlugValidation object with valid=True/False, errors, and warnings.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Check for empty or whitespace-only
    if not slug or not slug.strip():
        errors.append("Slug cannot be empty.")
        return SlugValidation(valid=False, normalized="", errors=errors, warnings=warnings)

    # Normalize and check if normalisation changed the slug
    normalized = normalize(slug)

    # Check if normalisation lost the entire slug
    if not normalized:
        errors.append("Slug normalises to empty string (contains only special characters or whitespace).")
        return SlugValidation(valid=False, normalized="", errors=errors, warnings=warnings)

    # Warn if the slug was changed by normalisation
    if slug != normalized:
        warnings.append(f"Slug was normalised from '{slug}' to '{normalized}'.")

    # Check length
    if len(normalized) < MIN_SLUG_LENGTH:
        errors.append(f"Slug is too short (minimum {MIN_SLUG_LENGTH} characters, got {len(normalized)}).")

    if len(normalized) > MAX_SLUG_LENGTH:
        errors.append(f"Slug is too long (maximum {MAX_SLUG_LENGTH} characters, got {len(normalized)}).")

    # Check for illegal characters (if normalisation didn't help)
    if re.search(r'[^a-z0-9-]', normalized):
        errors.append("Slug contains illegal characters (only a-z, 0-9, and hyphens allowed).")

    # Check reserved slugs
    if normalized in RESERVED_SLUGS:
        errors.append(f"Slug '{normalized}' is reserved and cannot be used.")

    # Warn if near max length
    if len(normalized) > MAX_SLUG_LENGTH * 0.85:
        warnings.append(f"Slug is close to maximum length ({len(normalized)}/{MAX_SLUG_LENGTH}).")

    valid = len(errors) == 0

    return SlugValidation(
        valid=valid,
        normalized=normalized,
        errors=errors,
        warnings=warnings,
    )


def is_valid(slug: str) -> bool:
    """Check if a slug is valid (quick boolean check).

    Args:
        slug: The slug to validate.

    Returns:
        True if slug is valid, False otherwise.
    """
    return validate(slug).valid


def suggest_alternatives(slug: str, existing: List[str]) -> List[str]:
    """Suggest alternative slugs with numeric suffixes for a given base slug.

    If the input slug is empty or normalises to empty, returns an empty list.
    Otherwise, returns up to 5 candidate slugs (slug-2, slug-3, ..., slug-6)
    that are not already in the existing list.

    Args:
        slug: The base slug to build alternatives from.
        existing: A list of already-used slugs to avoid.

    Returns:
        A list of up to 5 suggested slugs, or empty list if input is invalid.

    Examples:
        suggest_alternatives("lead", ["lead", "lead-2"])
            -> ["lead-3", "lead-4", "lead-5", "lead-6", "lead-7"]
        suggest_alternatives("", [])
            -> []
        suggest_alternatives("a", [])
            -> [] (normalises to invalid length)
    """
    if not slug or not slug.strip():
        return []

    normalized = normalize(slug)

    # If the slug is too short or invalid, return empty
    if len(normalized) < MIN_SLUG_LENGTH:
        return []

    existing_set = set(existing)
    suggestions: List[str] = []

    # Try numeric suffixes 2-7 (5 suggestions max)
    for suffix in range(2, 8):
        candidate = f"{normalized}-{suffix}"
        if candidate not in existing_set:
            suggestions.append(candidate)
            if len(suggestions) >= 5:
                break

    return suggestions


def slug_from_name(name: str) -> str:
    """Convert a human-readable name to a slug (alias for normalize).

    This is a convenience function that explicitly documents the intent:
    converting a display name like "My Cool Preset!" to a slug like "my-cool-preset".

    Args:
        name: A human-readable name.

    Returns:
        The normalised slug.

    Example:
        slug_from_name("My Cool Preset!") -> "my-cool-preset"
    """
    return normalize(name)
