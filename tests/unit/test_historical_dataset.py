from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.historical_dataset import load_historical_candles

START = datetime(2026, 1, 1, tzinfo=UTC)


def _row(index: int, *, timeframe: str = "5m", symbol: str = "BTCUSDT") -> dict[str, object]:
    opened = START + timedelta(minutes=5 * index)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "open_time": opened.isoformat(),
        "close_time": (opened + timedelta(minutes=5)).isoformat(),
        "open": 100 + index,
        "high": 101 + index,
        "low": 99 + index,
        "close": 100.5 + index,
        "volume": 1000 + index,
        "is_closed": True,
        "source": "fixture",
    }


def test_json_dataset_is_normalized_grouped_and_sorted(tmp_path: Path) -> None:
    path = tmp_path / "candles.json"
    path.write_text(json.dumps([_row(2), _row(0), _row(1)]), encoding="utf-8")

    loaded = load_historical_candles(
        path,
        expected_symbol="BTC/USDT",
        required_timeframes=("5m",),
    )

    assert tuple(loaded) == ("5m",)
    assert [candle.symbol for candle in loaded["5m"]] == ["BTC/USDT"] * 3
    assert [candle.open_time for candle in loaded["5m"]] == sorted(
        candle.open_time for candle in loaded["5m"]
    )


def test_csv_dataset_loads_closed_candles(tmp_path: Path) -> None:
    path = tmp_path / "candles.csv"
    rows = [_row(0), _row(1)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    loaded = load_historical_candles(path, expected_symbol="BTCUSDT")

    assert len(loaded["5m"]) == 2
    assert all(candle.is_closed for candle in loaded["5m"])


def test_duplicate_timestamp_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps([_row(0), _row(0)]), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate candle timestamp"):
        load_historical_candles(path)


def test_active_or_wrong_symbol_dataset_is_rejected(tmp_path: Path) -> None:
    active = _row(0)
    active["is_closed"] = False
    active_path = tmp_path / "active.json"
    active_path.write_text(json.dumps([active]), encoding="utf-8")

    with pytest.raises(ValueError, match="closed candles only"):
        load_historical_candles(active_path)

    symbol_path = tmp_path / "symbol.json"
    symbol_path.write_text(json.dumps([_row(0, symbol="ETHUSDT")]), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match requested symbol"):
        load_historical_candles(symbol_path, expected_symbol="BTCUSDT")


def test_missing_required_timeframe_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    path.write_text(json.dumps([_row(0)]), encoding="utf-8")

    with pytest.raises(ValueError, match="missing timeframes"):
        load_historical_candles(path, required_timeframes=("5m", "15m"))
