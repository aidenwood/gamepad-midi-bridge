"""Mapping banks organizer — group mapping slugs into named banks.

A bank groups related mapping presets (e.g. "Live Set 1" = [lead, pad, bass]).
Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from typing import Dict, List, Optional


@dataclass
class MappingBank:
    """A named bank of mapping preset slugs.

    Attributes:
        name: Display name (e.g. "Live Set 1")
        slug: Unique identifier (e.g. "live_set_1")
        preset_slugs: List of mapping preset slugs in this bank
        description: Optional descriptive text
        color: Optional hex color (e.g. "#FF5733") for visual tagging
    """

    name: str
    slug: str
    preset_slugs: List[str] = field(default_factory=list)
    description: str = ""
    color: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> MappingBank:
        """Create from dictionary, handling missing optional fields."""
        # Filter to only known fields to prevent extra keys
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)


@dataclass
class MappingBanksConfig:
    """Configuration for mapping banks.

    Attributes:
        banks: List of MappingBank instances
        max_banks: Maximum number of banks (clamped to 1..1000)
    """

    banks: List[MappingBank] = field(default_factory=list)
    max_banks: int = 32

    def __post_init__(self):
        """Clamp max_banks to valid range."""
        self.max_banks = max(1, min(1000, self.max_banks))

    def to_dict(self) -> Dict:
        """Convert to dictionary, including nested banks."""
        return {
            "banks": [bank.to_dict() for bank in self.banks],
            "max_banks": self.max_banks,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> MappingBanksConfig:
        """Create from dictionary, reconstructing nested banks."""
        banks = [MappingBank.from_dict(b) for b in data.get("banks", [])]
        max_banks = data.get("max_banks", 32)
        return cls(banks=banks, max_banks=max_banks)


class MappingBanksManager:
    """Manage a set of mapping banks."""

    def __init__(self, cfg: MappingBanksConfig):
        """Initialize with a config.

        Args:
            cfg: MappingBanksConfig instance
        """
        self.cfg = cfg

    def create_bank(
        self,
        name: str,
        slug: str,
        description: str = "",
        color: str = "",
    ) -> Optional[MappingBank]:
        """Create a new bank and add to config.

        Returns None if slug already exists or if at max_banks limit.

        Args:
            name: Display name
            slug: Unique identifier
            description: Optional description
            color: Optional hex color

        Returns:
            The new MappingBank, or None if creation failed
        """
        # Refuse duplicate slug
        if self.get_bank(slug) is not None:
            return None

        # Enforce max_banks limit
        if len(self.cfg.banks) >= self.cfg.max_banks:
            return None

        bank = MappingBank(
            name=name,
            slug=slug,
            preset_slugs=[],
            description=description,
            color=color,
        )
        self.cfg.banks.append(bank)
        return bank

    def get_bank(self, slug: str) -> Optional[MappingBank]:
        """Get a bank by slug.

        Args:
            slug: Bank slug to find

        Returns:
            The MappingBank if found, None otherwise
        """
        for bank in self.cfg.banks:
            if bank.slug == slug:
                return bank
        return None

    def delete_bank(self, slug: str) -> bool:
        """Delete a bank by slug.

        Args:
            slug: Bank slug to delete

        Returns:
            True if bank was found and deleted, False otherwise
        """
        original_count = len(self.cfg.banks)
        self.cfg.banks = [b for b in self.cfg.banks if b.slug != slug]
        return len(self.cfg.banks) < original_count

    def add_to_bank(self, bank_slug: str, preset_slug: str) -> bool:
        """Add a preset to a bank (if not already present).

        Args:
            bank_slug: Slug of the bank
            preset_slug: Slug of the preset to add

        Returns:
            True if preset was added, False if bank not found or preset already present
        """
        bank = self.get_bank(bank_slug)
        if bank is None:
            return False

        # Ignore duplicates (preset already in bank)
        if preset_slug in bank.preset_slugs:
            return False

        bank.preset_slugs.append(preset_slug)
        return True

    def remove_from_bank(self, bank_slug: str, preset_slug: str) -> bool:
        """Remove a preset from a bank.

        Args:
            bank_slug: Slug of the bank
            preset_slug: Slug of the preset to remove

        Returns:
            True if preset was found and removed, False otherwise
        """
        bank = self.get_bank(bank_slug)
        if bank is None:
            return False

        original_count = len(bank.preset_slugs)
        bank.preset_slugs = [p for p in bank.preset_slugs if p != preset_slug]
        return len(bank.preset_slugs) < original_count

    def move_preset(
        self, preset_slug: str, from_bank: str, to_bank: str
    ) -> bool:
        """Move a preset from one bank to another.

        Args:
            preset_slug: Slug of the preset
            from_bank: Slug of source bank
            to_bank: Slug of destination bank

        Returns:
            True if move succeeded, False if either bank not found or preset not in source
        """
        from_b = self.get_bank(from_bank)
        to_b = self.get_bank(to_bank)

        if from_b is None or to_b is None:
            return False

        if preset_slug not in from_b.preset_slugs:
            return False

        # Remove from source
        from_b.preset_slugs.remove(preset_slug)

        # Add to destination (avoid duplicates)
        if preset_slug not in to_b.preset_slugs:
            to_b.preset_slugs.append(preset_slug)

        return True

    def find_banks_with(self, preset_slug: str) -> List[MappingBank]:
        """Find all banks containing a preset.

        Args:
            preset_slug: Slug of the preset to find

        Returns:
            List of MappingBank instances containing the preset
        """
        return [b for b in self.cfg.banks if preset_slug in b.preset_slugs]

    def total_presets(self) -> int:
        """Count unique preset slugs across all banks.

        Returns:
            Number of unique presets
        """
        seen = set()
        for bank in self.cfg.banks:
            seen.update(bank.preset_slugs)
        return len(seen)

    def bank_count(self) -> int:
        """Count total number of banks.

        Returns:
            Number of banks
        """
        return len(self.cfg.banks)

    def clear(self) -> None:
        """Remove all banks."""
        self.cfg.banks = []
