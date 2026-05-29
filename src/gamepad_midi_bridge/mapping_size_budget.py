"""Mapping JSON size budget helper and analytics.

Measures serialized mapping size, warns when it exceeds a budget, and suggests
what to trim. Pure stdlib (json only), no Qt dependencies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class SizeBudgetConfig:
    """Configuration for mapping size budget constraints.

    Attributes:
        budget_bytes: Maximum allowed size in bytes (clamped 1000..10000000).
                     Typical max: 50000 bytes (50 KB).
        warn_threshold_pct: Usage percentage at which to warn (0..1).
                           Default 0.8 means warn at 80% of budget.
    """

    budget_bytes: int = 50000
    warn_threshold_pct: float = 0.8

    def __post_init__(self) -> None:
        """Clamp values to valid ranges."""
        self.budget_bytes = max(1000, min(self.budget_bytes, 10000000))
        self.warn_threshold_pct = max(0.0, min(self.warn_threshold_pct, 1.0))

    def to_dict(self) -> dict:
        """Serialize to dict for JSON round-trip.

        Returns:
            Dictionary representation suitable for json.dumps.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SizeBudgetConfig:
        """Deserialize from dict.

        Args:
            d: Dictionary with 'budget_bytes' and 'warn_threshold_pct' keys.

        Returns:
            New SizeBudgetConfig instance.
        """
        return cls(
            budget_bytes=d.get("budget_bytes", 50000),
            warn_threshold_pct=d.get("warn_threshold_pct", 0.8),
        )


@dataclass
class SizeBudgetReport:
    """Analysis and recommendations for mapping size.

    Attributes:
        current_bytes: Actual serialized size in bytes (minified).
        budget_bytes: Configured maximum in bytes.
        usage_pct: Percentage of budget used (0..1+).
        over_budget: True if current_bytes > budget_bytes.
        near_warn_threshold: True if usage_pct >= warn_threshold_pct.
        largest_section: Top-level key with largest serialized size, or None.
        largest_section_bytes: Byte count of largest_section.
        recommendations: List of human-readable trim suggestions (1-3 items).
    """

    current_bytes: int
    budget_bytes: int
    usage_pct: float
    over_budget: bool
    near_warn_threshold: bool
    largest_section: Optional[str]
    largest_section_bytes: int
    recommendations: List[str]

    def to_dict(self) -> dict:
        """Serialize to dict for JSON round-trip.

        Returns:
            Dictionary representation suitable for json.dumps.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SizeBudgetReport:
        """Deserialize from dict.

        Args:
            d: Dictionary with report fields.

        Returns:
            New SizeBudgetReport instance.
        """
        return cls(
            current_bytes=d.get("current_bytes", 0),
            budget_bytes=d.get("budget_bytes", 50000),
            usage_pct=d.get("usage_pct", 0.0),
            over_budget=d.get("over_budget", False),
            near_warn_threshold=d.get("near_warn_threshold", False),
            largest_section=d.get("largest_section"),
            largest_section_bytes=d.get("largest_section_bytes", 0),
            recommendations=d.get("recommendations", []),
        )


def serialized_size(mapping_dict: dict, minify: bool = False) -> int:
    """Measure JSON serialized size of a mapping dict.

    Args:
        mapping_dict: The mapping dictionary to measure.
        minify: If True, serialize with no whitespace. If False, use default
               json.dumps formatting (with newlines/spaces). Minified is smaller.

    Returns:
        Byte count of utf-8 encoded JSON string.
    """
    if minify:
        json_str = json.dumps(mapping_dict, separators=(",", ":"))
    else:
        json_str = json.dumps(mapping_dict)

    return len(json_str.encode("utf-8"))


def section_sizes(mapping_dict: dict, minify: bool = True) -> Dict[str, int]:
    """Break down serialized size by top-level section.

    Useful for identifying which part of the mapping is largest.

    Args:
        mapping_dict: The mapping dictionary to analyze.
        minify: If True, serialize sections minified; if False, pretty-printed.

    Returns:
        Dict mapping {section_name: byte_count} for each top-level key.
    """
    result = {}

    for key, value in mapping_dict.items():
        # Serialize just this section
        section_dict = {key: value}
        size = serialized_size(section_dict, minify=minify)
        result[key] = size

    return result


def check(mapping_dict: dict, cfg: SizeBudgetConfig) -> SizeBudgetReport:
    """Analyze a mapping against size budget and generate recommendations.

    Computes current serialized size (minified), calculates usage percentage,
    identifies the largest section, and generates 1-3 actionable recommendations.

    Args:
        mapping_dict: The mapping dictionary to analyze.
        cfg: Size budget configuration with budget_bytes and warn_threshold_pct.

    Returns:
        SizeBudgetReport with current usage, warnings, and suggestions.
    """
    # Measure current size (minified for tighter estimate)
    current_bytes = serialized_size(mapping_dict, minify=True)
    usage_pct = current_bytes / cfg.budget_bytes if cfg.budget_bytes > 0 else 0.0
    over_budget = current_bytes > cfg.budget_bytes
    near_warn_threshold = usage_pct >= cfg.warn_threshold_pct

    # Find largest section
    section_sizes_dict = section_sizes(mapping_dict, minify=True)
    largest_section = None
    largest_section_bytes = 0

    if section_sizes_dict:
        largest_section = max(section_sizes_dict, key=section_sizes_dict.get)
        largest_section_bytes = section_sizes_dict[largest_section]

    # Generate recommendations (1-3 items)
    recommendations: List[str] = []

    if over_budget or near_warn_threshold:
        # Check if macros section is the culprit
        if largest_section == "macros":
            recommendations.append(
                f"Macros section is {largest_section_bytes} bytes. Consider simplifying macro definitions or removing unused ones."
            )
        # Check if buttons section is large with many entries
        elif largest_section == "buttons":
            button_count = len(mapping_dict.get("buttons", {}))
            if button_count > 100:
                recommendations.append(
                    f"Buttons section has {button_count} entries. Consider grouping similar buttons or using shift layers instead."
                )
            else:
                recommendations.append(
                    f"Buttons section is {largest_section_bytes} bytes. Review for duplicate or unused button mappings."
                )
        # Suggest axes, triggers, sticks
        elif largest_section in ("axes", "triggers", "left_stick", "right_stick"):
            recommendations.append(
                f"{largest_section.replace('_', ' ').title()} section is {largest_section_bytes} bytes. Simplify or remove unused entries."
            )
        else:
            recommendations.append(
                f"{largest_section.replace('_', ' ').title()} section is the largest at {largest_section_bytes} bytes. Consider trimming it."
            )

        # Add second recommendation if still over or near threshold
        if over_budget or usage_pct >= cfg.warn_threshold_pct:
            if largest_section not in ("macros", "buttons") and (
                "buttons" in mapping_dict or "macros" in mapping_dict
            ):
                if len(recommendations) == 1:
                    recommendations.append(
                        "Review secondary sections (buttons, macros) for redundant entries."
                    )

        # Add third recommendation if significantly over budget
        if over_budget and len(recommendations) < 3:
            recommendations.append(
                "Consider using mapping_merge to split this preset into multiple smaller presets that you load selectively."
            )

    return SizeBudgetReport(
        current_bytes=current_bytes,
        budget_bytes=cfg.budget_bytes,
        usage_pct=usage_pct,
        over_budget=over_budget,
        near_warn_threshold=near_warn_threshold,
        largest_section=largest_section,
        largest_section_bytes=largest_section_bytes,
        recommendations=recommendations,
    )
