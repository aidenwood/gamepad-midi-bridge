"""DAW autodetection: infer which DAW is running from MIDI port names.

Pure stdlib module for scoring MIDI port names against known DAW port-naming
patterns. No Qt, no rtmidi, no network calls.

Scoring logic:
- For each DAW, compute a confidence score (0..1) based on substring/exact
  keyword matches across the input port names.
- Exact match of a keyword → 1.0 confidence for that keyword.
- Substring match of a keyword → 0.8 confidence for that keyword.
- No match → 0.0 confidence.
- Final DAW confidence = max score across all matched keywords.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# DAW hints: maps DAW slug → list of lowercase keywords.
# Keywords are checked as substrings against normalized port names.
DAW_HINTS: Dict[str, List[str]] = {
    "ableton": ["ableton", "live"],
    "logic": ["logic pro", "logic", "iac driver bus"],
    "fl_studio": ["fl studio", "fruity loops", "image-line"],
    "cubase": ["cubase", "steinberg"],
    "reaper": ["reaper", "reapr"],
    "pro_tools": ["pro tools", "avid"],
    "studio_one": ["studio one", "presonus"],
    "bitwig": ["bitwig"],
}

# Display names for each DAW slug.
DAW_DISPLAY_NAMES: Dict[str, str] = {
    "ableton": "Ableton Live",
    "logic": "Logic Pro",
    "fl_studio": "FL Studio",
    "cubase": "Cubase",
    "reaper": "Reaper",
    "pro_tools": "Pro Tools",
    "studio_one": "Studio One",
    "bitwig": "Bitwig Studio",
}


@dataclass
class DawDetection:
    """Result of DAW detection from MIDI port names.

    Attributes:
        daw_slug: Unique identifier for the DAW (e.g. "ableton")
        display_name: Human-readable name (e.g. "Ableton Live")
        confidence: Confidence score (0.0..1.0)
        matched_port: Port name that triggered the match (or None)
    """

    daw_slug: str
    display_name: str
    confidence: float
    matched_port: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "daw_slug": self.daw_slug,
            "display_name": self.display_name,
            "confidence": self.confidence,
            "matched_port": self.matched_port,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DawDetection:
        """Deserialize from dictionary."""
        return cls(
            daw_slug=data.get("daw_slug", "unknown"),
            display_name=data.get("display_name", "Unknown"),
            confidence=float(data.get("confidence", 0.0)),
            matched_port=data.get("matched_port"),
        )


def score_daw(daw_slug: str, port_names: List[str]) -> Tuple[float, Optional[str]]:
    """Score a single DAW against a list of MIDI port names.

    For each keyword in DAW_HINTS[daw_slug]:
    - Check each port name (normalized to lowercase)
    - Exact match of the entire normalized port → keyword confidence = 1.0
    - Keyword as substring of port name → keyword confidence = 0.8
    - No match → keyword confidence = 0.0

    DAW confidence = max(keyword confidences across all keywords and ports)

    Args:
        daw_slug: DAW identifier (e.g. "ableton")
        port_names: List of MIDI port names to score

    Returns:
        Tuple of (confidence_score, best_matching_port_name)
        Confidence is 0.0..1.0. If no match, returns (0.0, None).
    """
    if daw_slug not in DAW_HINTS:
        return (0.0, None)

    keywords = DAW_HINTS[daw_slug]
    if not keywords or not port_names:
        return (0.0, None)

    best_confidence = 0.0
    best_port = None

    # For each port, check all keywords
    for port in port_names:
        port_lower = port.lower().strip()

        for keyword in keywords:
            keyword_lower = keyword.lower().strip()

            # Exact match (entire normalized port name = keyword)
            if port_lower == keyword_lower:
                if 1.0 > best_confidence:
                    best_confidence = 1.0
                    best_port = port
            # Substring match (keyword is substring of port)
            elif keyword_lower in port_lower:
                if 0.8 > best_confidence:
                    best_confidence = 0.8
                    best_port = port

    return (best_confidence, best_port)


def detect(port_names: List[str]) -> List[DawDetection]:
    """Detect all DAWs from a list of MIDI port names.

    Scores each DAW in DAW_HINTS against the port list. Returns non-zero
    confidence results sorted by confidence descending.

    Args:
        port_names: List of MIDI port names

    Returns:
        List of DawDetection, sorted by confidence descending.
        Empty list if no matches found.
    """
    results = []

    for daw_slug in DAW_HINTS:
        confidence, matched_port = score_daw(daw_slug, port_names)

        if confidence > 0.0:
            display_name = DAW_DISPLAY_NAMES.get(daw_slug, daw_slug)
            detection = DawDetection(
                daw_slug=daw_slug,
                display_name=display_name,
                confidence=confidence,
                matched_port=matched_port,
            )
            results.append(detection)

    # Sort by confidence descending
    results.sort(key=lambda d: d.confidence, reverse=True)
    return results


def best_guess(
    port_names: List[str], min_confidence: float = 0.3
) -> Optional[DawDetection]:
    """Return the top-scored DAW if above the confidence threshold.

    Args:
        port_names: List of MIDI port names
        min_confidence: Minimum confidence threshold (0.0..1.0, clamped).
                       Defaults to 0.3.

    Returns:
        Top-scored DawDetection if confidence >= min_confidence,
        or None if no match above threshold.
    """
    # Clamp min_confidence to valid range
    min_confidence = max(0.0, min(1.0, min_confidence))

    detections = detect(port_names)
    if detections and detections[0].confidence >= min_confidence:
        return detections[0]

    return None


def daw_display_name(slug: str) -> str:
    """Get human-readable display name for a DAW slug.

    Args:
        slug: DAW identifier (e.g. "ableton")

    Returns:
        Display name (e.g. "Ableton Live"), or slug uppercased
        if slug not found.
    """
    return DAW_DISPLAY_NAMES.get(slug, slug.upper().replace("_", " "))
