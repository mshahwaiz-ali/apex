"""Leakage-resistant chronological train/calibration/final partitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class ChronologicalSplit:
    training: tuple[int, ...]
    calibration: tuple[int, ...]
    final_test: tuple[int, ...]
    purged: tuple[int, ...]


def chronological_split(
    timestamps: tuple[datetime, ...],
    *,
    horizon: timedelta = timedelta(0),
    embargo: timedelta = timedelta(0),
) -> ChronologicalSplit:
    """Use 60/20/20 ordering and remove rows whose outcome horizon crosses a boundary."""

    if not timestamps:
        raise ValueError("chronological split requires timestamped rows")
    if tuple(sorted(timestamps)) != timestamps or len(set(timestamps)) != len(timestamps):
        raise ValueError("timestamps must be unique and chronological")
    if horizon < timedelta(0) or embargo < timedelta(0):
        raise ValueError("purge horizon and embargo cannot be negative")
    size = len(timestamps)
    train_end = max(1, int(size * 0.60))
    calibration_end = max(train_end + 1, int(size * 0.80)) if size >= 3 else train_end
    calibration_end = min(calibration_end, size)
    boundaries = tuple(timestamps[index] for index in (train_end, calibration_end) if index < size)
    purged = {
        index
        for index, timestamp in enumerate(timestamps)
        if any(
            timestamp < boundary <= timestamp + horizon
            or boundary <= timestamp < boundary + embargo
            for boundary in boundaries
        )
    }
    return ChronologicalSplit(
        training=tuple(index for index in range(0, train_end) if index not in purged),
        calibration=tuple(
            index for index in range(train_end, calibration_end) if index not in purged
        ),
        final_test=tuple(index for index in range(calibration_end, size) if index not in purged),
        purged=tuple(sorted(purged)),
    )
