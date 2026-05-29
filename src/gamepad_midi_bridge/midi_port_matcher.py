"""
MIDI port matcher: find the best-matching MIDI port by name pattern.

Pure stdlib module for scoring and matching MIDI port names against
user preferences or search patterns. No Qt, no rtmidi.
"""

import fnmatch
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


def normalize_name(name: str) -> str:
    """
    Normalize a MIDI port name for comparison.

    - Lowercase the name
    - Strip leading/trailing whitespace
    - Remove port-index notation like "(0)", "(1)", " 1", " 2", etc.
    - Remove "MIDI" suffix if present at the end
    - Collapse multiple spaces to single space

    Args:
        name: Raw MIDI port name from the OS

    Returns:
        Normalized name for matching
    """
    name = name.lower().strip()

    # Remove port-index notation: " (0)", " (1)", " 1", " 2", etc.
    # Patterns: " (N)" or " N" at the end, where N is a digit
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    name = re.sub(r'\s+\d+\s*$', '', name)

    # Remove "MIDI" suffix if present at the end (case-insensitive already lowercased)
    name = re.sub(r'\s+midi\s*$', '', name)

    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def score_match(query: str, candidate: str) -> float:
    """
    Score how well a candidate matches a query pattern.

    Scoring hierarchy (descending):
    1. Exact match (case-insensitive) → 1.0
    2. Normalized exact match → 0.95
    3. Substring match (case-insensitive) → 0.7
    4. Substring of normalized → 0.65
    5. Token overlap (Jaccard similarity) → 0.0..0.5
    6. No overlap → 0.0

    Args:
        query: User search pattern
        candidate: MIDI port name to score

    Returns:
        Score from 0.0 to 1.0
    """
    query_lower = query.lower()
    cand_lower = candidate.lower()

    # Exact match (case-insensitive)
    if query_lower == cand_lower:
        return 1.0

    norm_query = normalize_name(query)
    norm_candidate = normalize_name(candidate)

    # Normalized exact match
    if norm_query == norm_candidate:
        return 0.95

    # Substring match (case-insensitive)
    if query_lower in cand_lower or cand_lower in query_lower:
        return 0.7

    # Substring of normalized
    if norm_query in norm_candidate or norm_candidate in norm_query:
        return 0.65

    # Token overlap (Jaccard similarity)
    query_tokens = set(norm_query.split())
    cand_tokens = set(norm_candidate.split())

    if not query_tokens or not cand_tokens:
        return 0.0

    intersection = query_tokens & cand_tokens
    union = query_tokens | cand_tokens

    if not union:
        return 0.0

    jaccard = len(intersection) / len(union)
    # Scale Jaccard to 0.0..0.5 range
    return jaccard * 0.5


def find_best_match(
    query: str, candidates: List[str], min_score: float = 0.5
) -> Optional[str]:
    """
    Find the highest-scoring candidate for a query.

    Args:
        query: Search pattern
        candidates: List of MIDI port names
        min_score: Minimum score threshold (0.0..1.0). Defaults to 0.5.

    Returns:
        Best-matching candidate name, or None if best score < min_score
    """
    if not candidates:
        return None

    matches = find_all_matches(query, candidates, min_score)
    return matches[0][0] if matches else None


def find_all_matches(
    query: str, candidates: List[str], min_score: float = 0.5
) -> List[Tuple[str, float]]:
    """
    Find all candidates matching a query above a threshold.

    Results are sorted by score descending.

    Args:
        query: Search pattern
        candidates: List of MIDI port names
        min_score: Minimum score threshold (0.0..1.0). Defaults to 0.5.

    Returns:
        List of (candidate_name, score) tuples, sorted by score descending
    """
    scores = [(cand, score_match(query, cand)) for cand in candidates]
    matches = [(cand, score) for cand, score in scores if score >= min_score]
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def glob_match(pattern: str, candidates: List[str]) -> List[str]:
    """
    Filter candidates using a glob pattern (case-insensitive).

    Args:
        pattern: Glob pattern (e.g. "*ableton*", "CME*")
        candidates: List of MIDI port names

    Returns:
        List of matching candidate names
    """
    matches = []
    pattern_lower = pattern.lower()
    for cand in candidates:
        if fnmatch.fnmatchcase(cand.lower(), pattern_lower):
            matches.append(cand)
    return matches


@dataclass
class PortPreference:
    """
    User preference for matching a MIDI port.

    Attributes:
        name_fragment: Search pattern (substring, fuzzy match, or glob)
        min_score: Minimum match score threshold (0.0..1.0, clamped).
                   Defaults to 0.5.
        fallback_to_default: If True and no match found, return first
                            available candidate. Defaults to True.
    """

    name_fragment: str
    min_score: float = 0.5
    fallback_to_default: bool = True

    def __post_init__(self):
        """Clamp min_score to valid range."""
        self.min_score = max(0.0, min(1.0, self.min_score))

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name_fragment": self.name_fragment,
            "min_score": self.min_score,
            "fallback_to_default": self.fallback_to_default,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PortPreference":
        """Deserialize from dictionary."""
        return cls(
            name_fragment=data.get("name_fragment", ""),
            min_score=data.get("min_score", 0.5),
            fallback_to_default=data.get("fallback_to_default", True),
        )


def resolve_port(
    pref: PortPreference, available: List[str]
) -> Optional[str]:
    """
    Resolve a port preference against available ports.

    Uses find_best_match to locate the best-matching port. If no match
    and fallback_to_default is True, returns the first available port.

    Args:
        pref: Port preference specification
        available: List of available MIDI port names

    Returns:
        Best-matching port name, first available (if fallback enabled),
        or None if no candidates available
    """
    if not available:
        return None

    best = find_best_match(pref.name_fragment, available, pref.min_score)

    if best is not None:
        return best

    if pref.fallback_to_default:
        return available[0]

    return None
