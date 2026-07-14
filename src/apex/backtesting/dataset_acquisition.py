"""Provider-independent acquisition of reproducible futures datasets."""

from __future__ import annotations

from datetime import datetime

from apex.backtesting.dataset import FuturesCandleDataset, build_futures_dataset
from apex.data.providers.base import MarketDataProvider

MAXIMUM_DATASET_CANDLES = 10_000


def acquire_futures_dataset(
    *,
    provider: MarketDataProvider,
    symbol: str,
    timeframe: str,
    candle_limit: int,
    extracted_at: datetime,
    dataset_id: str | None = None,
) -> FuturesCandleDataset:
    """Fetch closed candles and bind them to a reproducible dataset manifest."""

    normalized_symbol = symbol.strip()
    normalized_timeframe = timeframe.strip()

    if not normalized_symbol:
        raise ValueError("dataset acquisition symbol cannot be empty")
    if not normalized_timeframe:
        raise ValueError("dataset acquisition timeframe cannot be empty")
    if not 1 <= candle_limit <= MAXIMUM_DATASET_CANDLES:
        raise ValueError(f"dataset candle limit must be between one and {MAXIMUM_DATASET_CANDLES}")
    if extracted_at.tzinfo is None or extracted_at.utcoffset() is None:
        raise ValueError("dataset extraction time must be timezone-aware")

    fetched = tuple(
        provider.fetch_candles(
            normalized_symbol,
            normalized_timeframe,
            limit=candle_limit,
        )
    )
    closed = tuple(candle for candle in fetched if candle.is_closed)

    if not closed:
        raise ValueError("market-data provider returned no closed candles")

    resolved_id = dataset_id.strip() if dataset_id is not None else ""
    if not resolved_id:
        resolved_id = build_dataset_id(
            symbol=closed[0].symbol,
            timeframe=closed[0].timeframe,
            extracted_at=extracted_at,
        )

    return build_futures_dataset(
        dataset_id=resolved_id,
        candles=closed,
        extracted_at=extracted_at,
    )


def build_dataset_id(
    *,
    symbol: str,
    timeframe: str,
    extracted_at: datetime,
) -> str:
    """Build a filesystem-safe deterministic acquisition identifier."""

    if extracted_at.tzinfo is None or extracted_at.utcoffset() is None:
        raise ValueError("dataset extraction time must be timezone-aware")

    normalized_symbol = _identifier_part(symbol)
    normalized_timeframe = _identifier_part(timeframe)
    timestamp = extracted_at.strftime("%Y%m%dT%H%M%SZ")
    return f"{normalized_symbol}-{normalized_timeframe}-{timestamp}"


def _identifier_part(value: str) -> str:
    normalized = "".join(character.lower() for character in value.strip() if character.isalnum())
    if not normalized:
        raise ValueError("dataset identifier component cannot be empty")
    return normalized
