"""Deterministic historical candle dataset export."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from apex.application.symbols import normalize_market_symbol
from apex.domain.models import Candle

DATASET_SCHEMA_VERSION = 1


def build_dataset_payload(
    *,
    symbol: str,
    candles_by_timeframe: Mapping[str, Sequence[Candle]],
    source: str,
    created_at: datetime | None = None,
) -> dict[str, object]:
    """Build a schema-versioned dataset containing closed candles only."""
    canonical = normalize_market_symbol(symbol)
    ordered_timeframes = tuple(sorted(candles_by_timeframe))
    rows: list[dict[str, object]] = []
    for timeframe in ordered_timeframes:
        closed = sorted(
            (candle for candle in candles_by_timeframe[timeframe] if candle.is_closed),
            key=lambda candle: (candle.open_time, candle.close_time),
        )
        rows.extend(_serialize_candle(candle, canonical, timeframe) for candle in closed)
    if not rows:
        raise ValueError("dataset export requires at least one closed candle")
    timestamp = created_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("dataset creation time must be timezone-aware")
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "symbol": canonical,
        "created_at": timestamp.isoformat(),
        "source": source,
        "timeframes": list(ordered_timeframes),
        "candles": rows,
    }


def write_dataset(path: Path, payload: Mapping[str, object], *, force: bool = False) -> None:
    """Write UTF-8 JSON atomically while protecting existing files."""
    if path.exists() and not force:
        raise ValueError(f"refusing to overwrite existing dataset: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _serialize_candle(candle: Candle, symbol: str, timeframe: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "open_time": candle.open_time.isoformat(),
        "close_time": candle.close_time.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "is_closed": True,
        "source": candle.source,
    }
