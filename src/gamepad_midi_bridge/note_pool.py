"""Note pool random picker for generative music — pure stdlib, no Qt."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal, Optional


PickMode = Literal["random", "round_robin", "shuffle_bag", "weighted_random"]


@dataclass
class NotePoolConfig:
    """Configuration for a note pool picker."""

    enabled: bool = False
    notes: list[int] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    mode: str = "random"
    no_repeat_window: int = 0
    seed: Optional[int] = None

    def to_dict(self) -> dict:
        """Round-trip to dict (for JSON serialization)."""
        return {
            "enabled": self.enabled,
            "notes": self.notes,
            "weights": self.weights,
            "mode": self.mode,
            "no_repeat_window": self.no_repeat_window,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NotePoolConfig:
        """Deserialize from dict, clamping and normalizing values."""
        enabled = data.get("enabled", False)
        notes = [max(0, min(127, int(n))) for n in data.get("notes", [])]
        weights = [max(0.0, float(w)) for w in data.get("weights", [])]
        mode = data.get("mode", "random")
        no_repeat_window = max(0, min(32, int(data.get("no_repeat_window", 0))))
        seed = data.get("seed")

        return cls(
            enabled=enabled,
            notes=notes,
            weights=weights,
            mode=mode,
            no_repeat_window=no_repeat_window,
            seed=seed,
        )


class NotePool:
    """Pick random notes from a configured pool with multiple strategies."""

    def __init__(self, cfg: NotePoolConfig):
        """Initialize with config."""
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self._recent: list[int] = []
        self._bag: list[int] = []
        self._index: int = 0

    def pick(self) -> Optional[int]:
        """Pick a note from the pool, or None if empty."""
        if not self.cfg.enabled or not self.cfg.notes:
            return None

        if self.cfg.mode == "round_robin":
            return self._pick_round_robin()
        elif self.cfg.mode == "shuffle_bag":
            return self._pick_shuffle_bag()
        elif self.cfg.mode == "weighted_random":
            return self._pick_weighted_random()
        else:  # "random" or unknown
            return self._pick_random()

    def _pick_random(self) -> int:
        """Pick uniformly random, avoiding no_repeat_window."""
        notes = self.cfg.notes
        window = self.cfg.no_repeat_window

        if window == 0:
            return self.rng.choice(notes)

        # Try up to 16 times to avoid recent picks
        for _ in range(16):
            note = self.rng.choice(notes)
            if note not in self._recent[-window:]:
                self._recent.append(note)
                self._recent = self._recent[-window:]
                return note

        # Fallback: just return a random note and record it
        note = self.rng.choice(notes)
        self._recent.append(note)
        self._recent = self._recent[-window:]
        return note

    def _pick_weighted_random(self) -> int:
        """Pick using weighted distribution."""
        notes = self.cfg.notes
        weights = self.cfg.weights

        # Normalize weights: if empty or mismatched, use equal weights
        if not weights or len(weights) != len(notes):
            normalized_weights = [1.0] * len(notes)
        else:
            normalized_weights = weights

        return self.rng.choices(notes, weights=normalized_weights, k=1)[0]

    def _pick_round_robin(self) -> int:
        """Cycle through notes in order."""
        notes = self.cfg.notes
        note = notes[self._index]
        self._index = (self._index + 1) % len(notes)
        return note

    def _pick_shuffle_bag(self) -> int:
        """Each note once per refill, then shuffle and refill."""
        notes = self.cfg.notes

        if not self._bag:
            self._bag = notes.copy()
            self.rng.shuffle(self._bag)

        note = self._bag.pop()
        return note

    def reset(self) -> None:
        """Clear all state (recent, bag, index)."""
        self._recent = []
        self._bag = []
        self._index = 0

    def set_seed(self, seed: int) -> None:
        """Re-seed RNG and reset state."""
        self.rng = random.Random(seed)
        self.reset()
