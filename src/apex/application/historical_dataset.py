"""Strict local JSON/CSV historical candle dataset loading."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from apex.application.symbols import normalize_market_symbol
from apex.domain.models import Candle

_REQUIRED_FIELDS = {
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def load_historical_candles(
    path: Path,
    *,
    expected_symbol: str | None = None,
    required_timeframes: Iterable[str] = (),
) -> Mapping[str, tuple[Candle, ...]]:
    """Load, validate, sort, and group a closed-candle JSON or CSV dataset."""

    if not path.is_file():
        raise ValueError(f"historical dataset does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        rows = _load_json_rows(path)
    elif suffix == ".csv":
        rows = _load_csv_rows(path)
    else:
        raise ValueError("historical dataset must use .json or .csv")

    candles = tuple(_parse_row(row, index) for index, row in enumerate(rows, start=1))
    if not candles:
        raise ValueError("historical dataset cannot be empty")

    canonical_expected = normalize_market_symbol(expected_symbol) if expected_symbol else None
    grouped: dict[str, list[Candle]] = defaultdict(list)
    seen: set[tuple[str, str, datetime]] = set()
    for candle in candles:
        canonical = normalize_market_symbol(candle.symbol)
        if canonical_expected is not None and canonical != canonical_expected:
            raise ValueError(
                f"dataset symbol {canonical} does not match requested symbol {canonical_expected}"
            )
        if not candle.is_closed:
            raise ValueError("historical datasets must contain closed candles only")
        key = (canonical, candle.timeframe, candle.open_time)
        if key in seen:
            raise ValueError(
                f"duplicate candle timestamp for {canonical} {candle.timeframe}: "
                f"{candle.open_time.isoformat()}"
            )
        seen.add(key)
        grouped[candle.timeframe].append(candle.model_copy(update={"symbol": canonical}))

    missing = set(required_timeframes).difference(grouped)
    if missing:
        raise ValueError(f"historical dataset is missing timeframes: {sorted(missing)}")

    normalized = {
        timeframe: tuple(sorted(items, key=lambda candle: candle.open_time))
        for timeframe, items in sorted(grouped.items())
    }
    return MappingProxyType(normalized)


def _load_json_rows(path: Path) -> list[Mapping[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON historical dataset: {exc}") from exc

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("candles"), list):
        rows = payload["candles"]
    elif isinstance(payload, dict):
        rows = []
        for timeframe, items in payload.items():
            if not isinstance(items, list):
                raise ValueError("JSON timeframe values must be candle lists")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("JSON candles must be objects")
                rows.append({**item, "timeframe": item.get("timeframe", timeframe)})
    else:
        raise ValueError("JSON dataset must be a candle list or timeframe mapping")

    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSON candles must be objects")
    return rows


def _load_csv_rows(path: Path) -> list[Mapping[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise ValueError(f"unable to read CSV historical dataset: {exc}") from exc


def _parse_row(row: Mapping[str, Any], index: int) -> Candle:
    missing = _REQUIRED_FIELDS.difference(row)
    if missing:
        raise ValueError(f"dataset row {index} is missing fields: {sorted(missing)}")
    try:
        return Candle(
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            open_time=_parse_datetime(row["open_time"]),
            close_time=_parse_datetime(row["close_time"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            is_closed=_parse_bool(row.get("is_closed", True)),
            source=str(row.get("source", "historical-file")),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid historical dataset row {index}: {exc}") from exc


def _parse_datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("candle timestamps must be timezone-aware")
    return parsed


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")
