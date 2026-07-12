"""Small deterministic numerical helpers for feature calculations."""

from __future__ import annotations

import math
from collections.abc import Sequence


def validate_period(period: int) -> None:
    """Validate a positive rolling-window period."""

    if period < 1:
        raise ValueError("period must be at least 1")


def finite_values(values: Sequence[float], *, name: str = "values") -> tuple[float, ...]:
    """Return finite floats or reject unstable numerical input."""

    normalized = tuple(float(value) for value in values)
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    if any(not math.isfinite(value) for value in normalized):
        raise ValueError(f"{name} cannot contain NaN or infinite values")
    return normalized


def rolling_mean(values: Sequence[float], period: int) -> tuple[float | None, ...]:
    """Return an aligned simple rolling mean with ``None`` warm-up values."""

    validate_period(period)
    normalized = finite_values(values)
    if len(normalized) < period:
        raise ValueError(f"period {period} exceeds available values {len(normalized)}")

    output: list[float | None] = [None] * (period - 1)
    window_sum = sum(normalized[:period])
    output.append(window_sum / period)

    for index in range(period, len(normalized)):
        window_sum += normalized[index] - normalized[index - period]
        output.append(window_sum / period)

    return tuple(output)
