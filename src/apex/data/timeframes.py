"""Shared timeframe duration helpers."""

from __future__ import annotations

from datetime import timedelta

TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "8h": timedelta(hours=8),
    "12h": timedelta(hours=12),
    "1D": timedelta(days=1),
    "3D": timedelta(days=3),
    "1W": timedelta(weeks=1),
}


def timeframe_delta(timeframe: str) -> timedelta:
    """Return the configured duration for a supported timeframe."""

    try:
        return TIMEFRAME_DELTAS[timeframe.strip()]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe}") from exc
