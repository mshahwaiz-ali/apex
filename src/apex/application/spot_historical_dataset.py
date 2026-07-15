"""Deterministic multi-symbol historical spot dataset acquisition and manifests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apex.application.symbols import normalize_market_symbol
from apex.data.providers.base import HistoricalRangeMarketDataProvider
from apex.domain.models import Candle

SPOT_HISTORICAL_DATASET_SCHEMA_VERSION = 1


class SpotHistoricalDatasetManifest(BaseModel):
    """Canonical manifest for one immutable historical spot dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SPOT_HISTORICAL_DATASET_SCHEMA_VERSION
    dataset_id: str
    provider: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    start_time: datetime
    end_time: datetime
    candle_count: int = Field(ge=1)
    symbol_timeframe_counts: dict[str, int]
    dataset_sha256: str


@dataclass(frozen=True, slots=True)
class SpotHistoricalDatasetResult:
    manifest: SpotHistoricalDatasetManifest
    rows: tuple[dict[str, Any], ...]


def acquire_spot_historical_dataset(
    *,
    dataset_id: str,
    provider: HistoricalRangeMarketDataProvider,
    symbols: Sequence[str],
    timeframes: Sequence[str],
    start_time: datetime,
    end_time: datetime,
) -> SpotHistoricalDatasetResult:
    """Fetch, validate, deduplicate, and hash one historical spot dataset."""

    normalized_id = dataset_id.strip()
    if not normalized_id:
        raise ValueError("historical spot dataset id cannot be blank")
    normalized_symbols = tuple(sorted({normalize_market_symbol(symbol) for symbol in symbols}))
    normalized_timeframes = tuple(sorted({item.strip() for item in timeframes if item.strip()}))
    if not normalized_symbols:
        raise ValueError("historical spot dataset requires at least one symbol")
    if not normalized_timeframes:
        raise ValueError("historical spot dataset requires at least one timeframe")

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for symbol in normalized_symbols:
        for timeframe in normalized_timeframes:
            candles = provider.fetch_candles_range(
                symbol,
                timeframe,
                start_time=start_time,
                end_time=end_time,
            )
            canonical = _canonical_candles(
                candles,
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
            )
            key = f"{symbol}:{timeframe}"
            counts[key] = len(canonical)
            rows.extend(_serialize_candle(candle) for candle in canonical)

    rows.sort(key=lambda row: (row["open_time"], row["symbol"], row["timeframe"]))
    if not rows:
        raise ValueError("historical spot dataset contains no closed candles")
    dataset_hash = hash_spot_historical_rows(rows)
    manifest = SpotHistoricalDatasetManifest(
        dataset_id=normalized_id,
        provider=provider.name,
        symbols=normalized_symbols,
        timeframes=normalized_timeframes,
        start_time=start_time,
        end_time=end_time,
        candle_count=len(rows),
        symbol_timeframe_counts=dict(sorted(counts.items())),
        dataset_sha256=dataset_hash,
    )
    return SpotHistoricalDatasetResult(manifest=manifest, rows=tuple(rows))


def write_spot_historical_dataset(
    *,
    result: SpotHistoricalDatasetResult,
    records_path: Path,
    manifest_path: Path,
    force: bool = False,
) -> None:
    """Write canonical JSONL records and a sorted JSON manifest atomically."""

    for path in (records_path, manifest_path):
        if path.exists() and not force:
            raise FileExistsError(f"refusing to overwrite existing historical dataset file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    records_text = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in result.rows
    )
    _atomic_write(records_path, records_text)
    manifest_text = json.dumps(
        result.manifest.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    ) + "\n"
    _atomic_write(manifest_path, manifest_text)


def load_spot_historical_rows(path: Path) -> tuple[dict[str, Any], ...]:
    """Load canonical historical rows and reject malformed JSONL records."""

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        loaded = json.loads(line)
        if not isinstance(loaded, dict):
            raise ValueError(f"historical spot row {line_number} must be an object")
        rows.append(loaded)
    if not rows:
        raise ValueError("historical spot records file is empty")
    return tuple(rows)


def hash_spot_historical_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    """Return the stable SHA-256 of canonical JSONL row content."""

    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _canonical_candles(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[Candle, ...]:
    values = {
        candle.open_time: candle
        for candle in candles
        if candle.is_closed
        and candle.symbol.upper() == symbol
        and candle.timeframe == timeframe
        and start_time <= candle.open_time < end_time
    }
    ordered = tuple(sorted(values.values(), key=lambda candle: candle.open_time))
    if not ordered:
        raise ValueError(f"no closed candles for {symbol} {timeframe} in requested range")
    return ordered


def _serialize_candle(candle: Candle) -> dict[str, Any]:
    return {
        "symbol": candle.symbol.upper(),
        "timeframe": candle.timeframe,
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


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
