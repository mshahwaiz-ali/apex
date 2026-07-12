import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.data.cache.candles import CandleCacheKey, FileCandleCache
from apex.domain.models import Candle

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


def make_key() -> CandleCacheKey:
    return CandleCacheKey(
        provider="binance",
        symbol="BTC/USDT",
        timeframe="15m",
        limit=10,
    )


def make_candle(open_time: datetime, *, is_closed: bool = True) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=15),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=123.45,
        is_closed=is_closed,
        source="binance",
    )


def valid_series() -> list[Candle]:
    return [
        make_candle(datetime(2026, 7, 12, 11, 15, tzinfo=UTC)),
        make_candle(datetime(2026, 7, 12, 11, 30, tzinfo=UTC)),
        make_candle(
            datetime(2026, 7, 12, 11, 45, tzinfo=UTC),
            is_closed=False,
        ),
    ]


def test_rejects_duplicate_candles_before_save(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    candle = make_candle(datetime(2026, 7, 12, 11, 30, tzinfo=UTC))

    with pytest.raises(ValueError, match="duplicate"):
        cache.save(make_key(), [candle, candle])


def test_rejects_out_of_order_candles_before_save(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    candles = valid_series()

    with pytest.raises(ValueError, match="ordered"):
        cache.save(make_key(), [candles[1], candles[0]])


def test_rejects_missing_interval_before_save(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    candles = [
        make_candle(datetime(2026, 7, 12, 11, 0, tzinfo=UTC)),
        make_candle(datetime(2026, 7, 12, 11, 30, tzinfo=UTC)),
    ]

    with pytest.raises(ValueError, match="missing or inconsistent"):
        cache.save(make_key(), candles)


def test_rejects_active_candle_before_final_position(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    candles = valid_series()

    with pytest.raises(ValueError, match="active candle must be the final"):
        cache.save(make_key(), [candles[2], candles[1]])


def test_corrupt_structural_series_is_ignored_on_load(tmp_path: Path) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    key = make_key()
    path = cache.save(key, valid_series())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["candles"][1]["open_time"] = payload["candles"][0]["open_time"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert cache.load(key, max_age=timedelta(minutes=5)) is None


def test_atomic_write_failure_removes_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FileCandleCache(tmp_path, now=lambda: NOW)

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        cache.save(make_key(), valid_series())

    assert list(tmp_path.glob(".*.tmp")) == []
    assert list(tmp_path.glob("*.json")) == []
