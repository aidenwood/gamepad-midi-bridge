"""Unified performance statistics aggregator combining multiple analytics.

Composes note_frequency, note_duration_stats, velocity_histogram, and stuck_note_detector
into a single PerformanceReport facade for UI rendering. Pure stdlib, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from gamepad_midi_bridge.note_frequency import NoteFrequency, NoteFrequencyConfig
from gamepad_midi_bridge.note_duration_stats import NoteDurationStats, NoteDurationConfig
from gamepad_midi_bridge.velocity_histogram import VelocityHistogram, HistogramConfig
from gamepad_midi_bridge.stuck_note_detector import StuckNoteDetector, StuckNoteConfig


# MIDI pitch class names (0=C, 1=C#, 2=D, etc.)
PITCH_CLASS_NAMES = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B"
]


@dataclass
class PerformanceReport:
    """Unified performance report combining all analytics."""

    session_start_s: float
    session_end_s: float
    duration_s: float
    total_notes_played: int
    unique_notes_count: int
    top_notes: list[tuple[int, float]] = field(default_factory=list)
    key_center_guess: Optional[int] = None
    mean_note_duration_s: Optional[float] = None
    note_duration_category: Optional[str] = None
    velocity_peak_bucket: Optional[int] = None
    velocity_mean: Optional[float] = None
    stuck_notes_count: int = 0
    summary_text: str = ""

    def to_dict(self) -> dict:
        """Serialize report to dict for JSON round-trip."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PerformanceReport:
        """Deserialize report from dict."""
        return cls(**data)


class PerformanceStatsTracker:
    """Aggregator facade for all analytics trackers."""

    def __init__(
        self,
        freq_config: Optional[NoteFrequencyConfig] = None,
        duration_config: Optional[NoteDurationConfig] = None,
        histogram_config: Optional[HistogramConfig] = None,
        stuck_config: Optional[StuckNoteConfig] = None,
    ) -> None:
        """Initialize tracker with all sub-trackers using provided or default configs.

        Args:
            freq_config: NoteFrequencyConfig, or None for defaults.
            duration_config: NoteDurationConfig, or None for defaults.
            histogram_config: HistogramConfig, or None for defaults.
            stuck_config: StuckNoteConfig, or None for defaults.
        """
        self._freq_config = freq_config or NoteFrequencyConfig()
        self._duration_config = duration_config or NoteDurationConfig()
        self._histogram_config = histogram_config or HistogramConfig()
        self._stuck_config = stuck_config or StuckNoteConfig(enabled=True, stuck_after_s=10.0)

        # Create tracker instances
        self._frequency = NoteFrequency(self._freq_config)
        self._duration = NoteDurationStats(self._duration_config)
        self._histogram = VelocityHistogram(self._histogram_config)
        self._stuck = StuckNoteDetector(self._stuck_config)

        # Session tracking
        self._session_start_s: Optional[float] = None

    def on_session_start(self, now_s: float) -> None:
        """Mark the start of a session.

        Args:
            now_s: Current time in seconds.
        """
        self._session_start_s = now_s

    def on_note_on(self, note: int, channel: int, velocity: int, now_s: float) -> None:
        """Record a note-on event to all trackers.

        Args:
            note: MIDI note number (0-127).
            channel: MIDI channel (0-15).
            velocity: Note velocity (0-127).
            now_s: Current time in seconds.
        """
        self._frequency.record(note, now_s)
        self._duration.on_note_on(note, channel, now_s)
        self._histogram.record(velocity)
        self._stuck.on_note_on(note, channel, now_s)

    def on_note_off(self, note: int, channel: int, now_s: float) -> None:
        """Record a note-off event to all trackers.

        Args:
            note: MIDI note number (0-127).
            channel: MIDI channel (0-15).
            now_s: Current time in seconds.
        """
        self._duration.on_note_off(note, channel, now_s)
        self._stuck.on_note_off(note, channel, now_s)

    def report(self, now_s: float) -> PerformanceReport:
        """Generate a unified performance report.

        Args:
            now_s: Current time in seconds (end time for the report).

        Returns:
            PerformanceReport with all aggregated analytics.
        """
        # Session timing
        session_start = self._session_start_s if self._session_start_s is not None else now_s
        duration_s = max(0.0, now_s - session_start)

        # Note frequency data
        total_notes = int(self._frequency.total_plays())
        top_notes = self._frequency.top_n(n=5)
        unique_notes = len([n for n in range(128) if self._frequency.count(n) > 0])
        key_center = self._frequency.key_center_guess()

        # Duration data
        mean_duration = self._duration.mean()
        duration_category = self._duration.category()

        # Velocity data
        velocity_peak_bucket = self._histogram.peak_bucket()
        velocity_mean = self._histogram.mean()

        # Stuck notes data
        stuck_notes_list = self._stuck.stuck_notes(now_s)
        stuck_count = len(stuck_notes_list)

        # Generate summary text
        summary = self._generate_summary(
            duration_s=duration_s,
            total_notes=total_notes,
            unique_notes=unique_notes,
            key_center=key_center,
            mean_duration=mean_duration,
            duration_category=duration_category,
            velocity_mean=velocity_mean,
            velocity_peak_bucket=velocity_peak_bucket,
            stuck_count=stuck_count,
        )

        return PerformanceReport(
            session_start_s=session_start,
            session_end_s=now_s,
            duration_s=duration_s,
            total_notes_played=total_notes,
            unique_notes_count=unique_notes,
            top_notes=top_notes,
            key_center_guess=key_center,
            mean_note_duration_s=mean_duration,
            note_duration_category=duration_category,
            velocity_peak_bucket=velocity_peak_bucket,
            velocity_mean=velocity_mean,
            stuck_notes_count=stuck_count,
            summary_text=summary,
        )

    def clear(self) -> None:
        """Clear all trackers and reset session state."""
        self._frequency.clear()
        self._duration.clear()
        self._histogram.clear()
        self._stuck.panic()
        self._session_start_s = None

    @staticmethod
    def _generate_summary(
        duration_s: float,
        total_notes: int,
        unique_notes: int,
        key_center: Optional[int],
        mean_duration: Optional[float],
        duration_category: Optional[str],
        velocity_mean: Optional[float],
        velocity_peak_bucket: Optional[int],
        stuck_count: int,
    ) -> str:
        """Generate 3-5 line human-readable summary.

        Args:
            duration_s: Session duration in seconds.
            total_notes: Total notes played.
            unique_notes: Count of unique notes.
            key_center: Pitch class (0-11) or None.
            mean_duration: Mean note duration in seconds or None.
            duration_category: Category string (stab/short/medium/long/sustained) or None.
            velocity_mean: Mean velocity or None.
            velocity_peak_bucket: Peak bucket index or None.
            stuck_count: Number of stuck notes.

        Returns:
            Multi-line summary string.
        """
        if total_notes == 0:
            return "No session data yet"

        lines = []

        # Line 1: session duration
        minutes = int(duration_s // 60)
        seconds = int(duration_s % 60)
        lines.append(f"Session: {minutes}m {seconds}s")

        # Line 2: notes and key center
        key_name = ""
        if key_center is not None and 0 <= key_center < 12:
            key_name = f", key center: {PITCH_CLASS_NAMES[key_center]}"
        lines.append(f"{total_notes} notes played, {unique_notes} unique{key_name}")

        # Line 3: average note duration
        if duration_category is not None and mean_duration is not None:
            duration_ms = int(mean_duration * 1000)
            lines.append(f"Average note: {duration_category} ({duration_ms}ms)")

        # Line 4: velocity peak
        if velocity_peak_bucket is not None:
            # Estimate velocity range from bucket
            bucket_size = 128 // 8  # Default 8 buckets
            bucket_lo = velocity_peak_bucket * bucket_size
            bucket_hi = (velocity_peak_bucket + 1) * bucket_size - 1
            if velocity_peak_bucket == 7:  # Last bucket
                bucket_hi = 127
            lines.append(f"Velocity peak: {bucket_lo}-{bucket_hi} range")

        # Line 5: stuck notes (if any)
        if stuck_count > 0:
            lines.append(f"{stuck_count} stuck notes detected")
        else:
            lines.append("0 stuck notes detected")

        return "\n".join(lines)
