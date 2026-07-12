import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.data.cache.candles import CandleCacheKey, FileCandleCache
from apex.domain.models import Candle

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


def make_candle(
    *,
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
    source: str = "binance",
) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=datetime(2026, 7, 12, 11, 30, tzinfo=UTC),
        close_time=datetime(2026, 7, 12, 11, 45, tzinfo=UTC),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=123.45,
        is_closed=True,
        source=source,
    )


def make_key() -> CandleCacheKey:
    return CandleCacheKey(
        provider="binance",
        symbol="BTC/USDT",
        timeframe="15m",
        limit=100,
    )


def test_saves_and_loads_fresh_candles(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    key = make_key()
    candle = make_candle()

    cache_path = cache.save(key, [candle])
    result = cache.load(key, max_age=timedelta(minutes=5))

    assert cache_path.exists()
    assert result is not None
    assert result.candles == (candle,)
    assert result.saved_at == NOW


def test_returns_none_when_entry_is_stale(tmp_path: Path) -> None:
    key = make_key()
    writer = FileCandleCache(
        tmp_path,
        now=lambda: NOW - timedelta(minutes=6),
    )
    writer.save(key, [make_candle()])

    reader = FileCandleCache(tmp_path, now=lambda: NOW)

    assert (
        reader.load(
            key,
            max_age=timedelta(minutes=5),
        )
        is None
    )


def test_exact_freshness_boundary_is_accepted(tmp_path: Path) -> None:
    key = make_key()
    writer = FileCandleCache(
        tmp_path,
        now=lambda: NOW - timedelta(minutes=5),
    )
    writer.save(key, [make_candle()])

    reader = FileCandleCache(tmp_path, now=lambda: NOW)

    assert (
        reader.load(
            key,
            max_age=timedelta(minutes=5),
        )
        is not None
    )


def test_returns_none_for_corrupt_json(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    key = make_key()

    path = cache._path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    assert cache.load(key, max_age=timedelta(minutes=5)) is None


def test_returns_none_for_mismatched_cache_key(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    key = make_key()
    path = cache.save(key, [make_candle()])

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["key"]["timeframe"] = "1h"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert cache.load(key, max_age=timedelta(minutes=5)) is None


def test_rejects_candles_that_do_not_match_key(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)

    with pytest.raises(ValueError, match="do not match"):
        cache.save(
            make_key(),
            [make_candle(symbol="ETH/USDT")],
        )


def test_cache_keys_separate_request_dimensions() -> None:
    base = make_key()

    keys = {
        base.digest,
        CandleCacheKey(
            provider="other",
            symbol=base.symbol,
            timeframe=base.timeframe,
            limit=base.limit,
        ).digest,
        CandleCacheKey(
            provider=base.provider,
            symbol="ETH/USDT",
            timeframe=base.timeframe,
            limit=base.limit,
        ).digest,
        CandleCacheKey(
            provider=base.provider,
            symbol=base.symbol,
            timeframe="1h",
            limit=base.limit,
        ).digest,
        CandleCacheKey(
            provider=base.provider,
            symbol=base.symbol,
            timeframe=base.timeframe,
            limit=50,
        ).digest,
    }

    assert len(keys) == 5


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "provider": "",
                "symbol": "BTC/USDT",
                "timeframe": "15m",
                "limit": 100,
            },
            "provider",
        ),
        (
            {
                "provider": "binance",
                "symbol": "",
                "timeframe": "15m",
                "limit": 100,
            },
            "symbol",
        ),
        (
            {
                "provider": "binance",
                "symbol": "BTC/USDT",
                "timeframe": "",
                "limit": 100,
            },
            "timeframe",
        ),
        (
            {
                "provider": "binance",
                "symbol": "BTC/USDT",
                "timeframe": "15m",
                "limit": 0,
            },
            "limit",
        ),
    ],
)
def test_rejects_invalid_cache_keys(
    kwargs: dict[str, str | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CandleCacheKey(**kwargs)


def test_load_treats_duplicate_candle_series_as_cache_miss(
    tmp_path: Path,
) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    key = make_key()
    path = cache.save(key, [make_candle()])

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["candles"].append(payload["candles"][0])
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert cache.load(key, max_age=timedelta(minutes=5)) is None


def test_load_treats_out_of_order_candle_series_as_cache_miss(
    tmp_path: Path,
) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    key = make_key()
    first = make_candle()
    second = first.model_copy(
        update={
            "open_time": datetime(2026, 7, 12, 11, 15, tzinfo=UTC),
            "close_time": datetime(2026, 7, 12, 11, 30, tzinfo=UTC),
        }
    )

    path = cache._path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": cache.SCHEMA_VERSION,
                "key": cache._serialized_key(key),
                "saved_at": NOW.isoformat(),
                "candles": [
                    first.model_dump(mode="json"),
                    second.model_dump(mode="json"),
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cache.load(key, max_age=timedelta(minutes=5)) is None


def test_save_rejects_invalid_candle_series(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    candle = make_candle()

    with pytest.raises(
        ValueError,
        match="cannot cache invalid candle series",
    ):
        cache.save(make_key(), [candle, candle])


def test_atomic_save_leaves_no_temporary_files(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)

    path = cache.save(make_key(), [make_candle()])

    assert path.exists()
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_repeated_writes_to_same_key_remain_readable(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    key = make_key()

    for _ in range(10):
        cache.save(key, [make_candle()])

    result = cache.load(key, max_age=timedelta(minutes=5))

    assert result is not None
    assert result.candles == (make_candle(),)
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert list(tmp_path.glob(".*.tmp")) == []
