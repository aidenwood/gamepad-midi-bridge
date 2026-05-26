"""Stick drift calibration.

Samples stick axes while the user keeps their hands off, records the average
resting position per axis, then the bridge subtracts that offset from every
read. Same algorithm as the original script, refactored out of the main loop
so the GUI can drive it with progress signals.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from .controller import ControllerReader
from .mapping import STICK_AXES


SEVERE_DRIFT_THRESHOLD = 0.30   # warn the user; controller probably needs repair
SIGNIFICANT_THRESHOLD = 0.05


@dataclass
class CalibrationResult:
    offsets: Dict[int, float]
    severe_axes: list
    significant_axes: list


def calibrate(
    reader: ControllerReader,
    duration_sec: float = 1.0,
    sample_count: int = 60,
    on_progress: Optional[Callable[[float], None]] = None,
) -> CalibrationResult:
    """Run a single calibration sweep. Caller must ensure the controller is at rest.

    `on_progress` is called with a 0.0..1.0 fraction after each sample, so the GUI
    can update a progress bar without coupling to the calibration loop.
    """
    axes_to_calibrate: Iterable[int] = [
        a for a in sorted(STICK_AXES) if a < reader.num_axes()
    ]
    samples: Dict[int, list] = {axis: [] for axis in axes_to_calibrate}

    interval = duration_sec / max(sample_count, 1)
    for i in range(sample_count):
        reader.pump()
        for axis in axes_to_calibrate:
            samples[axis].append(reader.get_axis(axis))
        if on_progress is not None:
            on_progress((i + 1) / sample_count)
        time.sleep(interval)

    offsets = {
        axis: (sum(vals) / len(vals) if vals else 0.0)
        for axis, vals in samples.items()
    }
    severe = [a for a, v in offsets.items() if abs(v) > SEVERE_DRIFT_THRESHOLD]
    significant = [
        a for a, v in offsets.items()
        if SIGNIFICANT_THRESHOLD < abs(v) <= SEVERE_DRIFT_THRESHOLD
    ]
    return CalibrationResult(offsets=offsets, severe_axes=severe, significant_axes=significant)
